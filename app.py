"""
Cheapest Flight Finder - website version (Streamlit).

Run on your PC:   streamlit run app.py
Put online:       deploy this folder on Streamlit Community Cloud (share.streamlit.io)
"""

import os
import time
from datetime import date, timedelta
from urllib.parse import quote

import streamlit as st

# Optional SerpApi key, set in Streamlit Cloud -> app settings -> Secrets
try:
    if "SERPAPI_KEY" in st.secrets:
        os.environ["SERPAPI_KEY"] = st.secrets["SERPAPI_KEY"]
except Exception:
    pass

import cheapest_flight as cf

# ------------------------------------------------------------------ airports
AIRPORTS = {
    # Morocco
    "CMN": "Casablanca, Morocco",
    "RAK": "Marrakech, Morocco",
    "RBA": "Rabat, Morocco",
    "FEZ": "Fes, Morocco",
    "TNG": "Tangier, Morocco",
    "AGA": "Agadir, Morocco",
    "OUD": "Oujda, Morocco",
    "NDR": "Nador, Morocco",
    # Tunisia
    "TUN": "Tunis, Tunisia",
    "MIR": "Monastir, Tunisia",
    "DJE": "Djerba, Tunisia",
    "NBE": "Enfidha, Tunisia",
    # Algeria / Egypt
    "ALG": "Algiers, Algeria",
    "CAI": "Cairo, Egypt",
    # Europe
    "CDG": "Paris Charles de Gaulle, France",
    "ORY": "Paris Orly, France",
    "MRS": "Marseille, France",
    "LYS": "Lyon, France",
    "BRU": "Brussels, Belgium",
    "AMS": "Amsterdam, Netherlands",
    "MAD": "Madrid, Spain",
    "BCN": "Barcelona, Spain",
    "FCO": "Rome, Italy",
    "FRA": "Frankfurt, Germany",
    "LHR": "London Heathrow, UK",
    "IST": "Istanbul, Turkey",
    # Gulf / Americas
    "DXB": "Dubai, UAE",
    "DOH": "Doha, Qatar",
    "JED": "Jeddah, Saudi Arabia",
    "YUL": "Montreal, Canada",
    "JFK": "New York JFK, USA",
}
OTHER = "Other (type the code)"
OPTIONS = list(AIRPORTS) + [OTHER]


def airport_label(code):
    return f"{AIRPORTS[code]}  ({code})" if code in AIRPORTS else code


def airport_picker(label, default, key):
    choice = st.selectbox(label, OPTIONS, index=OPTIONS.index(default),
                          format_func=airport_label, key=key)
    if choice == OTHER:
        code = st.text_input("3-letter airport code", max_chars=3, key=key + "_code",
                             placeholder="e.g. LGW").strip().upper()
        return code
    return choice


# ------------------------------------------------------------------ search
@st.cache_data(ttl=900, show_spinner=False)   # reuse results for 15 min
def run_search(origin, dest, day, ret, adults, seat, max_stops, currency):
    errors = []
    offers = cf.search(origin, dest, day, ret, adults, seat, max_stops, currency,
                       verbose=False, errors=errors)
    return offers, errors


def google_link(origin, dest, day, ret):
    text = f"Flights from {origin} to {dest} on {day}"
    if ret:
        text += f" returning {ret}"
    return "https://www.google.com/travel/flights?q=" + quote(text)


# ------------------------------------------------------------------ page
st.set_page_config(page_title="Cheapest Flight Finder", page_icon="✈️", layout="centered")
st.title("✈️ Cheapest Flight Finder")
st.caption("Live prices from Google Flights. Pick your trip and press Search.")

trip = st.radio("Trip", ["One-way", "Round trip"], horizontal=True)

with st.form("search"):
    c1, c2 = st.columns(2)
    with c1:
        origin = airport_picker("From", "TUN", "from")
    with c2:
        dest = airport_picker("To", "CMN", "to")

    c3, c4 = st.columns(2)
    with c3:
        depart = st.date_input("Departure date", value=date.today() + timedelta(days=30),
                               min_value=date.today(), format="DD/MM/YYYY")
    with c4:
        ret_date = st.date_input("Return date", value=date.today() + timedelta(days=37),
                                 min_value=date.today(), format="DD/MM/YYYY",
                                 disabled=(trip == "One-way"),
                                 help="Only used for round trips")

    c5, c6, c7 = st.columns(3)
    with c5:
        adults = st.number_input("Passengers", 1, 9, 1)
    with c6:
        currency = st.selectbox("Currency", ["USD", "EUR", "MAD", "TND", "EGP", "CAD", "GBP"])
    with c7:
        seat = st.selectbox("Class", ["economy", "premium-economy", "business", "first"],
                            format_func=lambda s: s.replace("-", " ").title())

    flex = st.slider("Also check days before / after (find the cheapest day)", 0, 3, 0)
    direct_only = st.checkbox("Direct flights only")

    submitted = st.form_submit_button("🔍 Search flights", use_container_width=True,
                                      type="primary")

if submitted:
    round_trip = trip == "Round trip"
    if len(origin) != 3 or len(dest) != 3:
        st.error("Please enter valid 3-letter airport codes.")
        st.stop()
    if origin == dest:
        st.error("From and To must be different.")
        st.stop()
    if round_trip and ret_date < depart:
        st.error("The return date must be after the departure date.")
        st.stop()

    trip_len = (ret_date - depart).days if round_trip else None
    days = [depart + timedelta(d) for d in range(-flex, flex + 1)]
    days = [d for d in days if d >= date.today()]

    all_offers, all_errors = [], []
    progress = st.progress(0.0, text="Searching...")
    for i, d in enumerate(days, 1):
        r = (d + timedelta(trip_len)).isoformat() if round_trip else None
        progress.progress(i / len(days), text=f"Searching {d:%d/%m/%Y}...")
        offers, errors = run_search(origin, dest, d.isoformat(), r, int(adults), seat,
                                    0 if direct_only else None, currency)
        all_offers += offers
        all_errors += errors
        if len(days) > 1 and i < len(days):
            time.sleep(1.0)
    progress.empty()

    if not all_offers:
        st.warning("No flights found for this search.")
        if all_errors:
            with st.expander("Details"):
                for e in all_errors:
                    st.write("•", e)
        st.link_button("Try on Google Flights",
                       google_link(origin, dest, depart.isoformat(),
                                   ret_date.isoformat() if round_trip else None))
        st.stop()

    all_offers.sort(key=lambda o: o.price)
    best = all_offers[0]
    kind = "round trip, total" if round_trip else "one-way"

    # ---- cheapest card
    st.subheader("Cheapest flight")
    with st.container(border=True):
        a, b, c = st.columns(3)
        a.metric("Price", f"{best.price:,.0f} {best.currency}")
        a.caption(kind)
        b.metric("Stops", "Direct" if best.stops == 0 else str(best.stops))
        c.metric("Duration", cf.hm(best.duration_min))
        st.write(f"**{', '.join(best.airlines)}**")
        for leg in best.legs:
            st.write(f"🛫 {leg.origin} {leg.depart}  →  🛬 {leg.destination} {leg.arrive}")
        if round_trip:
            st.caption("Times shown are for the outbound flight. Price includes the return.")
        ret_for_best = ((date.fromisoformat(best.date) + timedelta(trip_len)).isoformat()
                        if round_trip else None)
        st.link_button("Book / see details on Google Flights",
                       google_link(origin, dest, best.date, ret_for_best))

    # ---- all results
    st.subheader(f"All results ({len(all_offers)})")
    rows = [{
        "Price": f"{o.price:,.0f} {o.currency}",
        "Date": date.fromisoformat(o.date).strftime("%d/%m/%Y"),
        "Airline": ", ".join(o.airlines),
        "Stops": "Direct" if o.stops == 0 else o.stops,
        "Duration": cf.hm(o.duration_min),
        "Departs": o.legs[0].depart[-5:] if o.legs else "",
        "Arrives": o.legs[-1].arrive[-5:] if o.legs else "",
        "Route": " → ".join([o.legs[0].origin] + [l.destination for l in o.legs]) if o.legs else "",
    } for o in all_offers]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("Prices can change quickly. Always confirm on the airline or Google Flights before paying.")
