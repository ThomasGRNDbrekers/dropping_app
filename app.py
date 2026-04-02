import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time
import math

# --- 1. INITIALISATIE (MOET BOVENAAN) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.team = None
    st.session_state.role = None

# --- 2. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")
FINISH_COORDS = [51.2443, 4.4505]
START_PUNTEN = 1000.0
TIJD_DOEL_UUR = 5 
PUNTEN_PER_SEC = START_PUNTEN / (TIJD_DOEL_UUR * 3600)
EXPECTED_COLS = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]

# --- 3. DATABASE FUNCTIES ---
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
    data = ws.get_all_records()
    if not data:
        ws.update([EXPECTED_COLS])
        return pd.DataFrame(columns=EXPECTED_COLS)
    df = pd.DataFrame(data)
    df['Teamnaam'] = df['Teamnaam'].astype(str).str.upper()
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 4. HET DASHBOARD (FRAGMENTEN) ---

@st.fragment(run_every=10)
def show_admin_dashboard():
    st.title("🕹️ Thomas Baas Control")
    df = get_db_as_df()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        m = folium.Map(location=FINISH_COORDS, zoom_start=13)
        folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red')).add_to(m)
        for _, row in df.iterrows():
            try:
                lat, lon = float(row['Cur_Lat']), float(row['Cur_Lon'])
                if lat != 0:
                    folium.Marker([lat, lon], tooltip=row['Teamnaam']).add_to(m)
            except: continue
        st_folium(m, width="100%", height=450, key="admin_map_live")

    with col2:
        st.write("### Live Teams")
        st.dataframe(df[['Teamnaam', 'Score', 'Fase']], hide_index=True)
        
        with st.expander("Nieuwe Opdracht"):
            target = st.selectbox("Team:", df['Teamnaam'].unique())
            msg = st.text_input("Bericht")
            pts = st.number_input("Punten", 50)
            mins = st.number_input("Tijd (min)", 10)
            if st.button("Push naar Team"):
                deadline = time.time() + (mins * 60)
                df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}|{deadline}"
                save_df_to_db(df)
                st.success("Verzonden!")

@st.fragment(run_every=7)
def show_user_dashboard():
    # JavaScript voor GPS (moet in het fragment voor updates)
    st.components.v1.html("""
        <script>
        navigator.geolocation.getCurrentPosition((pos) => {
            window.parent.postMessage({
                type: 'streamlit:set_component_value',
                value: {lat: pos.coords.latitude, lon: pos.coords.longitude, t: Date.now()},
                key: 'gps_sync'
            }, '*');
        }, (err) => {}, {enableHighAccuracy: true});
        </script>
    """, height=0)

    gps_val = st.session_state.get("gps_sync")
    df = get_db_as_df()
    team_idx = df['Teamnaam'] == st.session_state.team
    my_data = df[team_idx].iloc[0]

    # Sync
    if gps_val:
        df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [gps_val['lat'], gps_val['lon']]
        if my_data['Fase'] == "DROPPING":
            dt = time.time() - float(my_data['Last_Update'] or time.time())
            df.loc[team_idx, 'Score'] = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
            df.loc[team_idx, 'Last_Update'] = time.time()
        save_df_to_db(df)

    st.header(f"Team: {st.session_state.team} | 🏆 {int(my_data['Score'])}")
    
    # Alarm/Timer
    if "|" in str(my_data['Alarm']):
        pts, task, dl = str(my_data['Alarm']).split("|")
        sec_over = int(float(dl) - time.time())
        if sec_over > 0:
            st.error(f"🚨 {task} (+{pts}) | ⏳ {sec_over // 60}m {sec_over % 60}s")
        else: st.warning(f"⌛ TIJD OM: {task}")

    # Kaart
    if my_data['Fase'] == "LOCATIE_KIEZEN":
        st.info("Kies je startpunt.")
        m = folium.Map(location=FINISH_COORDS, zoom_start=15)
        out = st_folium(m, width=700, height=350, key="start_map_user")
        if out and out.get("last_clicked"):
            if st.button("BEVESTIG START"):
                c = out["last_clicked"]
                df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [c['lat'], c['lng'], c['lat'], c['lng'], "DROPPING", time.time()]
                save_df_to_db(df); st.rerun()
    else:
        dist = math.sqrt((float(my_data['Cur_Lat'])-float(my_data['Start_Lat']))**2) * 111000
        is_blind = dist > 2
        m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
        if is_blind:
            folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
        folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green").add_to(m)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
        folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
        st_folium(m, width=700, height=450, key="live_map_user")

# --- 5. DE HOOFD-LOGICA (LOGIN CHECK) ---

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    name = st.text_input("Teamnaam").strip().upper()
    pw = st.text_input("Wachtwoord (voor Admin)", type="password")
    
    if st.button("Inloggen"):
        if name == "THOMASBAAS" and pw == "bobodropping":
            st.session_state.logged_in = True
            st.session_state.role = "admin"
            st.session_state.team = "ADMIN"
            st.rerun()
        elif name:
            df = get_db_as_df()
            if name not in df['Teamnaam'].values:
                new_row = {c: "" for c in EXPECTED_COLS}
                new_row.update({"Teamnaam": name, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": START_PUNTEN, "Last_Update": time.time()})
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.logged_in = True
            st.session_state.role = "user"
            st.session_state.team = name
            st.rerun()
else:
    # Als we ingelogd zijn, toon de dashboards
    if st.session_state.role == "admin":
        show_admin_dashboard()
    else:
        show_user_dashboard()
        
    if st.sidebar.button("Uitloggen"):
        st.session_state.logged_in = False
        st.rerun()
