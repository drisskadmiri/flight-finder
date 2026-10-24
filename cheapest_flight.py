#!/usr/bin/env python3
"""
cheapest_flight.py - find the cheapest flight from A to B in real time.

Data sources (auto-switch):
  1. SerpApi Google Flights API  -> used if SERPAPI_KEY is set (official, most reliable)
  2. fast-flights (Google Flights) -> free, no key; used otherwise, or as a fallback

Setup:
  pip install fast-flights requests

Examples:
  # one-way
  python cheapest_flight.py CAI CMN 2026-11-20

  # round trip
  python cheapest_flight.py CAI CMN 2026-11-20 --return 2026-11-27

  # check +/- 3 days around the date to find the cheapest day
  python cheapest_flight.py CAI CMN 2026-11-20 --flex 3

  # keep watching: re-check every 30 min, alert when price drops below 250
  python cheapest_flight.py CAI CMN 2026-11-20 --watch 30 --alert 250

  # use SerpApi (free account at serpapi.com)
  export SERPAPI_KEY=your_key        (Windows: set SERPAPI_KEY=your_key)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


# ----------------------------------------------------------------- data model
@dataclass
class Leg:
    origin: str
    destination: str
    depart: str          # "YYYY-MM-DD HH:MM"
    arrive: str
    airline: str = ""
    flight_no: str = ""


@dataclass
class Offer:
    price: float
    currency: str
    airlines: list[str]
    duration_min: int
    stops: int
    legs: list[Leg] = field(default_factory=list)
    date: str = ""
    source: str = ""


# ------------------------------------------------------------- SerpApi source
SERP_CLASS = {"economy": 1, "premium-economy": 2, "business": 3, "first": 4}
SERP_STOPS = {None: 0, 0: 1, 1: 2, 2: 3}   # our max_stops -> SerpApi "stops"


def search_serpapi(origin, dest, day, ret, adults, seat, max_stops, currency, key):
    import requests

    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": dest,
        "outbound_date": day,
        "type": 1 if ret else 2,            # 1 = round trip, 2 = one-way
        "currency": currency,
        "hl": "en",
        "adults": adults,
        "travel_class": SERP_CLASS[seat],
        "stops": SERP_STOPS.get(max_stops, 0),
        "api_key": key,
    }
    if ret:
        params["return_date"] = ret

    r = requests.get("https://serpapi.com/search.json", params=params, timeout=60)
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])

    offers = []
    for item in data.get("best_flights", []) + data.get("other_flights", []):
        if "price" not in item:
            continue
        legs = [
            Leg(
                origin=s["departure_airport"]["id"],
                destination=s["arrival_airport"]["id"],
                depart=s["departure_airport"].get("time", ""),
                arrive=s["arrival_airport"].get("time", ""),
                airline=s.get("airline", ""),
                flight_no=s.get("flight_number", ""),
            )
            for s in item.get("flights", [])
        ]
        offers.append(Offer(
            price=float(item["price"]),
            currency=currency,
            airlines=sorted({l.airline for l in legs if l.airline}),
            duration_min=int(item.get("total_duration", 0)),
            stops=max(len(legs) - 1, 0),
            legs=legs,
            date=day,
            source="SerpApi",
        ))
    return offers


def layover_minutes(legs):
    """Total connection time between legs (same airport, so local times compare fine)."""
    total = 0
    for a, b in zip(legs, legs[1:]):
        try:
            t1 = datetime.strptime(a.arrive, "%Y-%m-%d %H:%M")
            t2 = datetime.strptime(b.depart, "%Y-%m-%d %H:%M")
            total += max(int((t2 - t1).total_seconds() // 60), 0)
        except ValueError:
            pass
    return total


# -------------------------------------------------------- fast-flights source
# Cookies that tell Google we already accepted its consent screen
# (otherwise users in Europe / some regions get "Before you continue" instead of flights).
GOOGLE_CONSENT_COOKIES = {
    "CONSENT": "YES+cb",
    "SOCS": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmVuIAEaBgiAo_CmBg",
}
DEBUG_HTML = "google_flights_debug.html"


def fetch_google_html(q):
    """Download the Google Flights page ourselves so we can send consent cookies."""
    from primp import Client

    client = Client(impersonate="chrome_145", impersonate_os="windows",
                    referer=True, cookie_store=True)
    res = client.get("https://www.google.com/travel/flights",
                     params=q.params(), cookies=GOOGLE_CONSENT_COOKIES, timeout=40)
    return res.text


def get_flights(q):
    from fast_flights.parser import parse

    html = fetch_google_html(q)
    if 'class="ds:1"' not in html and "ds:1" not in html:
        # Not a results page: save it so we can see what Google sent.
        with open(DEBUG_HTML, "w", encoding="utf-8") as fh:
            fh.write(html)
        low = html.lower()
        if "unusual traffic" in low or "recaptcha" in low or "/sorry/" in low:
            why = "Google is showing a robot check (too many searches from your network)"
        elif "consent.google" in low or "before you continue" in low:
            why = "Google is showing its cookie consent page"
        else:
            why = "Google returned a page without flight results"
        raise RuntimeError(f"{why}. Saved it to {DEBUG_HTML} - open it in a browser to look.")
    return parse_all(html)


def parse_all(html):
    """Read BOTH flight lists on the Google page ("top" and "other" flights).

    The fast-flights library only reads one list, which can hide flights
    (often the direct ones). Each item is parsed defensively.
    """
    import json
    from types import SimpleNamespace as NS
    from selectolax.lexbor import LexborHTMLParser
    from fast_flights.parser import _parse_time

    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    js = script.text()
    data = js.split("data:", 1)[1].rsplit(",", 1)[0]
    if data.endswith("errorHasStatus: true"):
        return []
    payload = json.loads(data)

    results, seen = [], set()
    for idx in (2, 3):
        try:
            items = payload[idx][0] or []
        except (IndexError, TypeError):
            continue
        for k in items:
            try:
                flight = k[0]
                price = k[1][0][1]
                segs = []
                for s in flight[2]:
                    segs.append(NS(
                        from_airport=NS(code=s[3]),
                        to_airport=NS(code=s[6]),
                        departure=NS(date=tuple(s[20]), time=_parse_time(s[8])),
                        arrival=NS(date=tuple(s[21]), time=_parse_time(s[10])),
                        duration=s[11] or 0,
                    ))
                key = (price, tuple((x.from_airport.code, x.departure.date, x.departure.time)
                                    for x in segs))
                if not price or key in seen:
                    continue
                seen.add(key)
                results.append(NS(price=price, airlines=flight[1] or [], flights=segs))
            except (IndexError, TypeError, KeyError):
                continue
    return results


def search_fast_flights(origin, dest, day, ret, adults, seat, max_stops, currency):
    from fast_flights import FlightQuery, Passengers, create_query

    flights = [FlightQuery(date=day, from_airport=origin, to_airport=dest)]
    if ret:
        flights.append(FlightQuery(date=ret, from_airport=dest, to_airport=origin))

    q = create_query(
        flights=flights,
        trip="round-trip" if ret else "one-way",
        seat=seat,
        passengers=Passengers(adults=adults),
        currency=currency,
        language="en-US",
        max_stops=max_stops,
    )

    def fmt(dt):
        (y, m, d), (hh, mm) = dt.date, dt.time
        return f"{y:04d}-{m:02d}-{d:02d} {hh or 0:02d}:{mm or 0:02d}"

    offers = []
    for f in get_flights(q):
        if not f.price:
            continue
        legs = [
            Leg(s.from_airport.code, s.to_airport.code, fmt(s.departure), fmt(s.arrival))
            for s in f.flights
        ]
        offers.append(Offer(
            price=float(f.price),
            currency=currency,
            airlines=list(f.airlines),
            duration_min=sum(s.duration for s in f.flights) + layover_minutes(legs),
            stops=max(len(f.flights) - 1, 0),
            legs=legs,
            date=day,
            source="Google Flights",
        ))
    return offers


# ---------------------------------------------------------------- dispatcher
def search(origin, dest, day, ret, adults, seat, max_stops, currency, verbose=True,
           errors=None):
    """Try SerpApi first if a key exists, otherwise / on failure use fast-flights.

    Pass a list as `errors` to collect problem messages (used by the website).
    """
    key = os.environ.get("SERPAPI_KEY")
    if errors is None:
        errors = []
    sources = []
    if key:
        sources.append(("SerpApi", lambda: search_serpapi(
            origin, dest, day, ret, adults, seat, max_stops, currency, key)))
    sources.append(("Google Flights", lambda: search_fast_flights(
        origin, dest, day, ret, adults, seat, max_stops, currency)))

    for name, fn in sources:
        try:
            offers = fn()
            if offers:
                return sorted(offers, key=lambda o: o.price)
            errors.append(f"{name}: no results")
        except ImportError as e:
            errors.append(f"{name}: missing package - run: pip install {e.name}")
        except Exception as e:
            errors.append(f"{name}: {e}")
        if verbose and len(sources) > 1 and name != sources[-1][0]:
            print(f"  ! {errors[-1]} -> trying next source...")
    if verbose:
        for e in errors:
            print(f"  ! {e}")
    return []


# ------------------------------------------------------------------- output
def hm(minutes):
    return f"{minutes // 60}h{minutes % 60:02d}m" if minutes else "?"


def print_offers(offers, top, round_trip=False):
    if round_trip:
        print("\nNote: PRICE is the total for the round trip; times shown are the OUTBOUND flight.")
    print(f"\n{'#':>2}  {'PRICE':>10}  {'DATE':10}  {'STOPS':6}  {'DURATION':8}  AIRLINE(S)")
    print("-" * 73)
    for i, o in enumerate(offers[:top], 1):
        stops = "direct" if o.stops == 0 else str(o.stops)
        print(f"{i:>2}  {o.price:>6.0f} {o.currency:3}  {o.date:10}  {stops:6}  "
              f"{hm(o.duration_min):8}  {', '.join(o.airlines)[:30]}")
    best = offers[0]
    kind = "round trip total" if round_trip else "one-way"
    print(f"\nCHEAPEST: {best.price:.0f} {best.currency} {kind}  ({best.source})")
    for l in best.legs:
        extra = f"  {l.airline} {l.flight_no}".rstrip()
        print(f"   {l.origin} {l.depart}  ->  {l.destination} {l.arrive}{extra}")


def run_once(a):
    base = datetime.strptime(a.date, "%Y-%m-%d").date()
    trip_len = None
    if a.ret:
        trip_len = (datetime.strptime(a.ret, "%Y-%m-%d").date() - base).days
        if trip_len < 0:
            sys.exit("Return date must be after departure date.")

    days = [base + timedelta(d) for d in range(-a.flex, a.flex + 1)]
    days = [d for d in days if d >= date.today()]

    all_offers = []
    for d in days:
        ret = (d + timedelta(trip_len)).isoformat() if trip_len is not None else None
        label = f"{d}" + (f" -> back {ret}" if ret else "")
        print(f"Searching {a.origin} -> {a.dest}  {label} ...")
        all_offers += search(a.origin, a.dest, d.isoformat(), ret, a.adults,
                             a.seat, a.max_stops, a.currency)
        if len(days) > 1:
            time.sleep(1.5)    # be polite between requests

    all_offers.sort(key=lambda o: o.price)
    if all_offers:
        print_offers(all_offers, a.top, round_trip=bool(a.ret))
    else:
        print("\nNo flights found. Check airport codes (IATA, e.g. CAI, CMN, JFK) and dates.")
    return all_offers[0] if all_offers else None


# --------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description="Find the cheapest flight from A to B.")
    p.add_argument("origin", type=str.upper, help="From airport IATA code, e.g. CAI")
    p.add_argument("dest", type=str.upper, help="To airport IATA code, e.g. CMN")
    p.add_argument("date", help="Departure date YYYY-MM-DD")
    p.add_argument("--return", dest="ret", help="Return date YYYY-MM-DD (makes it a round trip)")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--seat", default="economy", choices=list(SERP_CLASS))
    p.add_argument("--max-stops", type=int, choices=[0, 1, 2], help="0 = direct only")
    p.add_argument("--currency", default="USD", type=str.upper)
    p.add_argument("--flex", type=int, default=0, help="Also search +/- N days around the date")
    p.add_argument("--top", type=int, default=10, help="How many results to show")
    p.add_argument("--watch", type=float, metavar="MIN", help="Re-check every MIN minutes")
    p.add_argument("--alert", type=float, metavar="PRICE", help="Alert when price <= PRICE")
    a = p.parse_args()

    try:
        datetime.strptime(a.date, "%Y-%m-%d")
    except ValueError:
        sys.exit("Date must be YYYY-MM-DD")

    if not a.watch:
        run_once(a)
        return

    lowest = None
    print(f"Watching every {a.watch:g} min. Press Ctrl+C to stop.")
    try:
        while True:
            print(f"\n=== {datetime.now():%Y-%m-%d %H:%M} ===")
            best = run_once(a)
            if best:
                if lowest is None or best.price < lowest:
                    if lowest is not None:
                        print(f"\n*** PRICE DROP: {lowest:.0f} -> {best.price:.0f} {best.currency} ***\a")
                    lowest = best.price
                if a.alert and best.price <= a.alert:
                    print(f"\n*** ALERT: {best.price:.0f} {best.currency} is at or below "
                          f"your target {a.alert:.0f}! ***\a")
            time.sleep(a.watch * 60)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
