import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components
import time
import math

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Dropping 2026", layout="wide")

FINISH_COORDS = [51.2443, 4.4505]
START_PUNTEN = 1000.0
PUNTEN_PER_SEC = START_PUNTEN / (5 * 3600)
EXPECTED_COLS = [
    "Teamnaam","Leden","Fase","Alarm","Score","Last_Update",
    "Start_Lat","Start_Lon","Cur_Lat","Cur_Lon"
]

# ---------------- DATABASE ----------------
@st.cache_resource
def get_ws():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds).open_by_key(
            "13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI"
        ).sheet1
    except:
        return None


def get_df():
    ws = get_ws()
    if not ws:
        return pd.DataFrame(columns=EXPECTED_COLS)

    data = ws.get_all_records()
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=EXPECTED_COLS)

    for c in ['Score','Last_Update','Start_Lat','Start_Lon','Cur_Lat','Cur_Lon']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    df['Teamnaam'] = df['Teamnaam'].astype(str).str.upper()
    return df


def save_df(df):
    ws = get_ws()
    if ws:
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# ---------------- LOGIN ----------------
if "team" not in st.session_state:
    params = st.query_params
    if "t" in params and "r" in params:
        st.session_state.team = params["t"]
        st.session_state.role = params["r"]
    else:
        st.session_state.team = None

# ---------------- LOGIN SCREEN ----------------
if not st.session_state.team:
    st.title("📍 Dropping 2026")

    team = st.text_input("Teamnaam").strip().upper()
    leden = st.text_input("Teamleden")
    pw = st.text_input("Admin wachtwoord", type="password")

    if st.button("Start"):
        if team == "THOMASBAAS" and pw == "bobodropping":
            st.session_state.team = "ADMIN"
            st.session_state.role = "admin"
        else:
            df = get_df()
            if team not in df['Teamnaam'].values:
                new = {c: 0.0 for c in EXPECTED_COLS}
                new.update({
                    "Teamnaam": team,
                    "Leden": leden,
                    "Fase": "LOCATIE_KIEZEN",
                    "Alarm": "GEEN",
                    "Score": START_PUNTEN,
                    "Last_Update": time.time()
                })
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                save_df(df)

            st.session_state.team = team
            st.session_state.role = "user"

        st.query_params["t"] = st.session_state.team
        st.query_params["r"] = st.session_state.role
        st.rerun()

# ---------------- ADMIN ----------------
elif st.session_state.role == "admin":
    st.title("🕹️ Control Room")

    st_autorefresh(interval=5000, key="adminrefresh")

    df = get_df()

    m = folium.Map(location=FINISH_COORDS, zoom_start=13)
    folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)

    for _, r in df.iterrows():
        if r['Cur_Lat'] != 0:
            folium.Marker([r['Cur_Lat'], r['Cur_Lon']], tooltip=r['Teamnaam']).add_to(m)

    st_folium(m, height=400)

    st.dataframe(df[['Teamnaam','Score','Fase']], use_container_width=True)

# ---------------- PLAYER ----------------
else:
    st_autorefresh(interval=3000, key="playerrefresh")

    # 🔥 REALTIME GPS VIA JS
    components.html("""
    <script>
    function sendPos(pos){
        const data = {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude
        };
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: data
        }, '*');
    }

    if (navigator.geolocation) {
        navigator.geolocation.watchPosition(sendPos, function(err){
            console.log(err);
        }, {
            enableHighAccuracy: true,
            maximumAge: 0,
            timeout: 5000
        });
    }
    </script>
    """, height=0)

    df = get_df()
    team_idx = df['Teamnaam'] == st.session_state.team

    if df[team_idx].empty:
        st.warning("⚠️ Team data niet gevonden, herladen...")
        st.rerun()

    my = df[team_idx].iloc[0]

    gps = st.session_state.get("_component_value")

    st.write("GPS debug:", gps)

    # Score update (altijd veilig)
    if my['Fase'] == "DROPPING":
        dt = time.time() - float(my['Last_Update'])
        df.loc[team_idx, 'Score'] = max(0.0, float(my['Score']) - dt * PUNTEN_PER_SEC)
        df.loc[team_idx, 'Last_Update'] = time.time()

    # GPS update (veilig)
    if gps and isinstance(gps, dict) and 'lat' in gps and 'lon' in gps:
        df.loc[team_idx, ['Cur_Lat','Cur_Lon']] = [gps['lat'], gps['lon']]

    save_df(df)
    my = df[team_idx].iloc[0]

    st.header(f"🏆 {st.session_state.team} — {int(my['Score'])} punten")

    # FASE
    if my['Fase'] == "LOCATIE_KIEZEN":
        st.info("Klik startlocatie")
        m = folium.Map(location=FINISH_COORDS, zoom_start=15)
        out = st_folium(m, height=400)

        if out and out.get("last_clicked"):
            if st.button("Bevestig"):
                c = out['last_clicked']
                df.loc[team_idx, ['Start_Lat','Start_Lon','Cur_Lat','Cur_Lon','Fase','Last_Update']] = [
                    c['lat'], c['lng'], c['lat'], c['lng'], "DROPPING", time.time()
                ]
                save_df(df)
                st.rerun()
    else:
        # veilige distance
        if my['Cur_Lat'] != 0 and my['Start_Lat'] != 0:
            dist = math.sqrt(
                (my['Cur_Lat']-my['Start_Lat'])**2 +
                (my['Cur_Lon']-my['Start_Lon'])**2
            ) * 111000
        else:
            dist = 0

        m = folium.Map(location=[my['Cur_Lat'], my['Cur_Lon']], zoom_start=17)

        folium.PolyLine([
            [my['Start_Lat'], my['Start_Lon']],
            FINISH_COORDS
        ], color="green", weight=5).add_to(m)

        folium.Marker([my['Cur_Lat'], my['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)

        st_folium(m, height=500)

    if st.button("Logout"):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()
