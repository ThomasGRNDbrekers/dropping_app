import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time
import math

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")

FINISH_COORDS = [51.2443, 4.4505]
START_PUNTEN = 1000.0
PUNTEN_PER_SEC = START_PUNTEN / (5 * 3600)
EXPECTED_COLS = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]

# --- 2. DATABASE FUNCTIES (Cache tegen API Errors) ---
@st.cache_resource
def get_ss_worksheet():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except: return None

def get_db_as_df():
    ws = get_ss_worksheet()
    if not ws: return pd.DataFrame(columns=EXPECTED_COLS)
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=EXPECTED_COLS)
        num_cols = ['Score', 'Last_Update', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon']
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        df['Teamnaam'] = df['Teamnaam'].astype(str).str.upper()
        st.session_state.last_df = df
        return df
    except:
        return st.session_state.get("last_df", pd.DataFrame(columns=EXPECTED_COLS))

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        try:
            ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())
        except: pass

# --- 3. LOGIN LOGICA ---
if "team" not in st.session_state:
    params = st.query_params
    st.session_state.team = params.get("t")
    st.session_state.role = params.get("r")

if not st.session_state.team:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip().upper()
    t_pass = st.text_input("Wachtwoord (Admin)", type="password")
    if st.button("Start"):
        role = "admin" if t_name == "THOMASBAAS" and t_pass == "bobodropping" else "user"
        st.session_state.update({"team": t_name, "role": role})
        st.query_params.update({"t": t_name, "r": role})
        st.rerun()

# --- 4. ADMIN DASHBOARD (FRAGMENT) ---
elif st.session_state.role == "admin":
    st.title("🕹️ Control Room")
    
    @st.fragment(run_every=10)
    def admin_view():
        df = get_db_as_df()
        m = folium.Map(location=FINISH_COORDS, zoom_start=12)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
        for _, row in df.iterrows():
            if float(row['Cur_Lat']) != 0:
                folium.Marker([row['Cur_Lat'], row['Cur_Lon']], tooltip=row['Teamnaam']).add_to(m)
        st_folium(m, width="100%", height=400, key="admin_map")
        st.dataframe(df[['Teamnaam', 'Score', 'Fase']], hide_index=True)
        
        with st.expander("Opdracht sturen"):
            target = st.selectbox("Team:", df['Teamnaam'].unique())
            msg = st.text_input("Bericht")
            if st.button("Push"):
                dl = time.time() + 600
                df.loc[df['Teamnaam'] == target, 'Alarm'] = f"50|{msg}|{dl}"
                save_df_to_db(df); st.success("Gezonden")

    admin_view()
    if st.sidebar.button("Log uit"):
        st.query_params.clear(); st.session_state.clear(); st.rerun()

# --- 5. USER DASHBOARD (FRAGMENT) ---
else:
    # DE GPS BRIDGE (Buiten het fragment om verbinding te houden)
    st.components.v1.html("""
    <div id="gps-box" style="background:#ff4b4b; color:white; padding:15px; border-radius:10px; text-align:center; cursor:pointer;">
        <b>KLIK HIER OM GPS TE STARTEN</b>
    </div>
    <script>
    const box = document.getElementById('gps-box');
    box.onclick = function() {
        navigator.geolocation.watchPosition((pos) => {
            window.parent.postMessage({
                type: 'streamlit:set_component_value',
                value: {lat: pos.coords.latitude, lon: pos.coords.longitude, ts: Date.now()},
                key: 'gps_data'
            }, '*');
            box.style.background = "#28a745";
            box.innerHTML = "✅ GPS VERBONDEN";
        }, (err) => { alert("Check instellingen!"); }, {enableHighAccuracy: true});
    };
    </script>
    """, height=80)

    @st.fragment(run_every=5)
    def user_view():
        df = get_db_as_df()
        team_idx = df['Teamnaam'] == st.session_state.team
        my_data = df[team_idx].iloc[0]
        
        # Locatie update
        gps = st.session_state.get("gps_data")
        if gps:
            df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [gps['lat'], gps['lon']]
            if my_data['Fase'] == "DROPPING":
                nu = time.time()
                dt = nu - float(my_data['Last_Update'] or nu)
                df.loc[team_idx, 'Score'] = max(0.0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
                df.loc[team_idx, 'Last_Update'] = nu
            save_df_to_db(df)
            my_data = df[team_idx].iloc[0]

        st.header(f"🏆 {int(my_data['Score'])} ptn")
        
        # Alarm
        if "|" in str(my_data['Alarm']):
            pts, task, dl = str(my_data['Alarm']).split("|")
            over = int(float(dl) - time.time())
            if over > 0: st.error(f"🚨 {task} ({over//60}m {over%60}s)")

        # Kaart
        if my_data['Fase'] == "LOCATIE_KIEZEN":
            m = folium.Map(location=FINISH_COORDS, zoom_start=14)
            out = st_folium(m, width=700, height=400, key="picker")
            if out and out.get("last_clicked"):
                if st.button("BEVESTIG START"):
                    c = out["last_clicked"]
                    df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [c['lat'], c['lng'], c['lat'], c['lng'], "DROPPING", time.time()]
                    save_df_to_db(df); st.rerun()
        else:
            dist = math.sqrt((my_data['Cur_Lat']-my_data['Start_Lat'])**2 + (my_data['Cur_Lon']-my_data['Start_Lon'])**2) * 111000
            is_blind = dist > 5
            m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
            if is_blind: folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
            folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green").add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
            folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
            st_folium(m, width=700, height=400, key="map")

    user_view()
    if st.sidebar.button("Uitloggen"):
        st.query_params.clear(); st.session_state.clear(); st.rerun()
