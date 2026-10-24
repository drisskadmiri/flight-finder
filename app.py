"""
Kadmiri Flight Search Engine - website version (Streamlit).

Run on your PC:   streamlit run app.py
Put online:       deploy this folder on Streamlit Community Cloud (share.streamlit.io)
"""

import html
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
    # Switzerland
    "GVA": "Geneva, Switzerland",
    "ZRH": "Zurich, Switzerland",
    "BSL": "Basel-Mulhouse, Switzerland/France",
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
    "LGW": "London Gatwick, UK",
    "NCE": "Nice, France",
    "TLS": "Toulouse, France",
    "MXP": "Milan Malpensa, Italy",
    "MUC": "Munich, Germany",
    "VIE": "Vienna, Austria",
    "IST": "Istanbul, Turkey",
    # Gulf / Americas
    "DXB": "Dubai, UAE",
    "DOH": "Doha, Qatar",
    "JED": "Jeddah, Saudi Arabia",
    "YUL": "Montreal, Canada",
    "JFK": "New York JFK, USA",
}
OPTIONS = list(AIRPORTS)


def airport_label(code):
    return f"{AIRPORTS[code]}  ({code})" if code in AIRPORTS else code


def airport_picker(label, default, key):
    """Pick from the list, or type any 3-letter airport code (e.g. LIS)."""
    choice = st.selectbox(label, OPTIONS, index=OPTIONS.index(default),
                          format_func=airport_label, key=key,
                          accept_new_options=True,
                          help="Not in the list? Type the 3-letter airport code, e.g. LIS")
    return resolve_airport(choice)


def resolve_airport(text):
    """Turn what was picked or typed into an airport code.

    Accepts a code ("gva"), a full label ("Geneva, Switzerland  (GVA)")
    or a city name ("Geneva", "zurich").
    """
    t = (text or "").strip()
    if not t:
        return ""
    if t.upper() in AIRPORTS:
        return t.upper()
    if "(" in t and t.endswith(")"):
        return t[t.rfind("(") + 1:-1].strip().upper()
    low = t.lower()
    for code, name in AIRPORTS.items():            # city name typed
        if name.lower().startswith(low) or name.split(",")[0].lower() == low:
            return code
    return t.upper()


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


# ------------------------------------------------------------------ design
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');

:root{
  --ink:#0b1b3a; --sky1:#0b1b3a; --sky2:#13306b; --sky3:#1e4fa3;
  --sun1:#ff7a59; --sun2:#ffb347; --card:rgba(255,255,255,.07);
  --line:rgba(255,255,255,.14); --text:#eef3ff; --muted:#a9b8d9; --good:#2ed3a0;
}
html, body, [class*="css"], .stApp { font-family:'Poppins',sans-serif; }
.stApp{
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(255,179,71,.25), transparent 60%),
    radial-gradient(900px 500px at -10% 10%, rgba(30,79,163,.55), transparent 60%),
    linear-gradient(180deg, var(--sky1) 0%, var(--sky2) 55%, #0d2350 100%);
  background-attachment: fixed;
}
header[data-testid="stHeader"]{ background:transparent; }
.block-container{ padding-top:2rem; max-width:860px; }

/* ---------- hero */
.hero{
  position:relative; overflow:hidden; border-radius:24px; padding:34px 30px 30px;
  background:linear-gradient(135deg, #1e4fa3 0%, #3a6fd8 45%, #ff7a59 100%);
  box-shadow:0 20px 50px rgba(0,0,0,.35); margin-bottom:22px; color:#fff;
}
.hero:before{ /* stars */
  content:""; position:absolute; inset:0; opacity:.35;
  background-image:radial-gradient(2px 2px at 20% 30%, #fff, transparent 60%),
    radial-gradient(1.5px 1.5px at 70% 20%, #fff, transparent 60%),
    radial-gradient(1.5px 1.5px at 40% 70%, #fff, transparent 60%),
    radial-gradient(2px 2px at 85% 60%, #fff, transparent 60%),
    radial-gradient(1px 1px at 55% 40%, #fff, transparent 60%);
}
.hero .kicker{ font-size:.85rem; letter-spacing:.22em; text-transform:uppercase; opacity:.9; font-weight:600; }
.hero h1{ font-size:2.3rem; line-height:1.15; margin:.35rem 0 .5rem; font-weight:800; color:#fff; padding:0; }
.hero h1 span{ background:linear-gradient(90deg,#fff,#ffe2b8); -webkit-background-clip:text; background-clip:text; color:transparent; }
.hero p{ margin:0; opacity:.92; font-size:1rem; max-width:520px; }
.hero svg{ position:absolute; right:-10px; top:14px; width:260px; opacity:.95; }
.hero .chips{ margin-top:16px; display:flex; gap:8px; flex-wrap:wrap; }
.hero .chip{ background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.3);
  padding:5px 12px; border-radius:999px; font-size:.8rem; font-weight:500; }
@media (max-width:640px){ .hero h1{font-size:1.7rem;} .hero svg{ width:150px; opacity:.35; } }

/* ---------- widgets on dark background */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label,
.stRadio label p, .stCheckbox label p, [data-testid="stMarkdownContainer"] p,
.stSlider label p { color:var(--text) !important; }
[data-testid="stForm"]{
  background:var(--card); border:1px solid var(--line) !important; border-radius:22px;
  padding:22px 22px 10px; backdrop-filter: blur(8px); box-shadow:0 12px 34px rgba(0,0,0,.25);
}
[data-testid="stFormSubmitButton"] button, .stButton button{
  background:linear-gradient(90deg,var(--sun1),var(--sun2)) !important; color:#1b1030 !important;
  border:0 !important; border-radius:14px !important; font-weight:700 !important;
  font-size:1.05rem !important; padding:.75rem 1rem !important;
  box-shadow:0 10px 24px rgba(255,122,89,.35); transition:transform .15s ease;
}
[data-testid="stFormSubmitButton"] button:hover{ transform:translateY(-1px); }
[data-testid="stFormSubmitButton"] button p{ color:#1b1030 !important; font-weight:700; }
.stRadio [role="radiogroup"]{ background:var(--card); border:1px solid var(--line);
  border-radius:999px; padding:6px 14px; width:fit-content; }
[data-testid="stExpander"]{ background:var(--card); border:1px solid var(--line); border-radius:14px; }
[data-testid="stExpander"] summary p{ color:var(--text) !important; }

[data-testid="stTooltipIcon"] svg, [data-testid="stTooltipHoverTarget"] svg{
  color:var(--muted) !important; stroke:var(--muted) !important; }
[data-testid="stSlider"] [data-testid="stTickBarMin"], [data-testid="stSlider"] div[data-testid="stThumbValue"]{
  color:var(--sun2) !important; }

/* ---------- results */
.section-title{ color:var(--text); font-weight:700; font-size:1.3rem; margin:26px 0 10px; }
.section-title small{ color:var(--muted); font-weight:500; font-size:.85rem; margin-left:8px; }
.best{
  border-radius:22px; padding:22px; margin-bottom:6px;
  background:linear-gradient(135deg, rgba(46,211,160,.18), rgba(30,79,163,.35));
  border:1px solid rgba(46,211,160,.55); box-shadow:0 14px 36px rgba(0,0,0,.3); color:var(--text);
}
.badge{ display:inline-block; background:var(--good); color:#06281e; font-weight:700;
  font-size:.75rem; padding:4px 10px; border-radius:999px; letter-spacing:.04em; }
.badge.alt{ background:rgba(255,255,255,.14); color:var(--text); }
.flight{
  display:grid; grid-template-columns: 1.2fr 2.6fr 1fr; gap:14px; align-items:center;
  background:var(--card); border:1px solid var(--line); border-radius:18px;
  padding:16px 18px; margin:10px 0; color:var(--text); transition:border-color .15s ease;
}
.flight:hover{ border-color:rgba(255,179,71,.6); }
.best .flight{ background:transparent; border:0; padding:12px 0 0; margin:0; }
.airline{ font-weight:600; font-size:.98rem; }
.airline small{ display:block; color:var(--muted); font-weight:400; font-size:.78rem; margin-top:2px; }
.route{ display:flex; align-items:center; gap:10px; }
.pt{ text-align:center; min-width:62px; }
.pt b{ display:block; font-size:1.25rem; font-weight:700; }
.pt span{ color:var(--muted); font-size:.8rem; font-weight:500; }
.pt sup{ color:var(--sun2); font-size:.7rem; font-weight:700; }
.path{ flex:1; text-align:center; color:var(--muted); font-size:.75rem; }
.path .bar{ position:relative; height:2px; margin:6px 0;
  background:repeating-linear-gradient(90deg, rgba(255,255,255,.5) 0 6px, transparent 6px 11px); }
.path .bar:after{ content:"✈"; position:absolute; right:-4px; top:-10px; font-size:14px; color:var(--sun2); }
.path .dot{ position:absolute; top:-3px; width:8px; height:8px; border-radius:50%; background:var(--sun2); }
.direct{ color:var(--good); font-weight:600; }
.price{ text-align:right; }
.price b{ display:block; font-size:1.45rem; font-weight:800; color:#fff; }
.price span{ color:var(--muted); font-size:.75rem; }
.best .price b{ font-size:1.9rem; color:#7ff0c9; }
.note{ color:var(--muted); font-size:.82rem; margin-top:8px; }
.footer{ text-align:center; color:var(--muted); font-size:.8rem; margin:34px 0 10px; }
[data-testid="stLinkButton"] a{
  border-radius:12px !important; border:1px solid rgba(255,179,71,.7) !important;
  background:rgba(255,179,71,.12) !important; color:#ffd59a !important; font-weight:600 !important;
}
[data-testid="stLinkButton"] a p{ color:#ffd59a !important; }
@media (max-width:640px){
  .flight{ grid-template-columns:1fr; gap:8px; }
  .price{ text-align:left; }
}
</style>
"""

HERO = """
<div class="hero">
  <svg viewBox="0 0 260 120" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 100 C 80 20, 170 20, 240 70" stroke="white" stroke-opacity=".7"
          stroke-width="2.5" stroke-dasharray="6 8" stroke-linecap="round"/>
    <circle cx="10" cy="100" r="5" fill="#ffe2b8"/>
    <circle cx="240" cy="70" r="5" fill="#ffe2b8"/>
    <g transform="translate(150 22) rotate(18)">
      <path d="M0 14 L44 10 L58 0 L66 0 L58 12 L76 12 C82 12 82 18 76 18 L58 18 L66 30 L58 30 L44 20 L0 16 Z"
            fill="white"/>
    </g>
  </svg>
  <div class="kicker">Kadmiri · Live fares</div>
  <h1>Welcome to <span>Kadmiri</span><br>Flight Search Engine</h1>
  <p>Find the cheapest flight in seconds. Pick where you fly from and to, choose your dates, and we search live prices for you.</p>
  <div class="chips">
    <div class="chip">✈ Live Google Flights prices</div>
    <div class="chip">📅 Flexible dates</div>
    <div class="chip">💸 Cheapest first</div>
  </div>
</div>
"""


def esc(x):
    return html.escape(str(x))


def flight_card(o, round_trip, best=False):
    """One flight as an HTML card."""
    first, last = o.legs[0], o.legs[-1]
    dep_t, arr_t = first.depart[-5:], last.arrive[-5:]
    try:
        plus = (date.fromisoformat(last.arrive[:10]) - date.fromisoformat(first.depart[:10])).days
    except ValueError:
        plus = 0
    plus_html = f"<sup>+{plus}</sup>" if plus > 0 else ""
    via = [l.destination for l in o.legs[:-1]]
    if o.stops == 0:
        stops_html = '<span class="direct">Direct</span>'
    else:
        stops_html = f"{o.stops} stop{'s' if o.stops > 1 else ''} · via {esc(', '.join(via))}"
    dots = "".join(f'<i class="dot" style="left:{(i + 1) * 100 / (len(via) + 1):.0f}%"></i>'
                   for i in range(len(via)))
    day_txt = date.fromisoformat(o.date).strftime("%a %d %b")
    kind = "round trip total" if round_trip else "one-way"
    return f"""
<div class="flight">
  <div class="airline">{esc(', '.join(o.airlines) or 'Airline')}<small>{day_txt}</small></div>
  <div class="route">
    <div class="pt"><b>{esc(dep_t)}</b><span>{esc(first.origin)}</span></div>
    <div class="path">{esc(cf.hm(o.duration_min))}<div class="bar">{dots}</div>{stops_html}</div>
    <div class="pt"><b>{esc(arr_t)}{plus_html}</b><span>{esc(last.destination)}</span></div>
  </div>
  <div class="price"><b>{o.price:,.0f} {esc(o.currency)}</b><span>{kind}</span></div>
</div>"""


# ------------------------------------------------------------------ page
st.set_page_config(page_title="Kadmiri Flight Search Engine", page_icon="✈️", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(HERO, unsafe_allow_html=True)

trip = st.radio("Trip type", ["One-way", "Round trip"], horizontal=True,
                label_visibility="collapsed")

with st.form("search"):
    c1, c2 = st.columns(2)
    with c1:
        origin = airport_picker("🛫 From", "TUN", "from")
    with c2:
        dest = airport_picker("🛬 To", "CMN", "to")

    c3, c4 = st.columns(2)
    with c3:
        depart = st.date_input("📅 Departure", value=date.today() + timedelta(days=30),
                               min_value=date.today(), format="DD/MM/YYYY")
    with c4:
        ret_date = st.date_input("📅 Return", value=date.today() + timedelta(days=37),
                                 min_value=date.today(), format="DD/MM/YYYY",
                                 disabled=(trip == "One-way"),
                                 help="Only used for round trips")

    c5, c6, c7 = st.columns(3)
    with c5:
        adults = st.number_input("👤 Passengers", 1, 9, 1)
    with c6:
        currency = st.selectbox("💱 Currency", ["USD", "EUR", "CHF", "MAD", "TND", "EGP", "CAD", "GBP"])
    with c7:
        seat = st.selectbox("💺 Class", ["economy", "premium-economy", "business", "first"],
                            format_func=lambda s: s.replace("-", " ").title())

    flex = st.slider("Flexible dates: also check this many days before / after", 0, 3, 0)
    direct_only = st.checkbox("Direct flights only")

    submitted = st.form_submit_button("🔍  Search the cheapest flights", use_container_width=True,
                                      type="primary")

if submitted:
    round_trip = trip == "Round trip"
    if len(origin) != 3 or len(dest) != 3:
        st.error("Please choose an airport, or type a valid 3-letter airport code (e.g. GVA).")
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
    progress = st.progress(0.0, text="✈ Searching live fares...")
    for i, d in enumerate(days, 1):
        r = (d + timedelta(trip_len)).isoformat() if round_trip else None
        progress.progress(i / len(days), text=f"✈ Searching {d:%d/%m/%Y}...")
        offers, errors = run_search(origin, dest, d.isoformat(), r, int(adults), seat,
                                    0 if direct_only else None, currency)
        all_offers += offers
        all_errors += errors
        if len(days) > 1 and i < len(days):
            time.sleep(1.0)
    progress.empty()

    if not all_offers:
        st.warning("No flights found for this search. Try other dates or airports.")
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

    # ---- cheapest
    st.markdown('<div class="section-title">Best price found</div>', unsafe_allow_html=True)
    note = ("Times shown are for the outbound flight. The price includes the return."
            if round_trip else "Price per trip for all passengers selected.")
    st.markdown(f'<div class="best"><span class="badge">★ CHEAPEST</span>'
                f'{flight_card(best, round_trip, best=True)}'
                f'<div class="note">{note}</div></div>', unsafe_allow_html=True)
    ret_for_best = ((date.fromisoformat(best.date) + timedelta(trip_len)).isoformat()
                    if round_trip else None)
    st.link_button("Book / see details on Google Flights  →",
                   google_link(origin, dest, best.date, ret_for_best), use_container_width=True)

    # ---- all results
    others = all_offers[1:16]
    if others:
        st.markdown(f'<div class="section-title">More options<small>{len(all_offers)} flights found'
                    f' · cheapest first</small></div>', unsafe_allow_html=True)
        st.markdown("".join(flight_card(o, round_trip) for o in others), unsafe_allow_html=True)

    with st.expander("See all results as a table"):
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

st.markdown('<div class="footer">Kadmiri Flight Search Engine · Prices change quickly — '
            'always confirm on the airline or Google Flights before paying.</div>',
            unsafe_allow_html=True)
