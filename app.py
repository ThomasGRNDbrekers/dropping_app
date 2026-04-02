import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time
import math

# --- 1. CONFIGURATIE & SETUP ---
st.set_page_config(page_title="Dropping 2026", layout="wide")

# JavaScript voor Persistent Login (LocalStorage)
st.components.v1.html("""
<script>
    const savedTeam = localStorage.getItem('dropping_team');
    const savedRole = localStorage.getItem('dropping_role');
    if (savedTeam && !window.parent.location.href.includes('auth=true')) {
        window.parent.postMessage({
            type: 'streamlit:set_component_value', 
            value: {team: savedTeam, role: savedRole}, 
            key: 'ls_login'
        }, '*');
    }
</script>
""", height=0)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Verwerk automatische login vanuit LocalStorage
ls = st.session_state.get("ls_login")
if ls and not st.session_state.logged_in:
    st.session_state.update({"team": ls['team'], "role": ls['role'], "logged_in": True})

FINISH_COORDS = [51.2443, 4.4505] # JC Bouckenborgh
START_PUNTEN = 1000.0
PUNTEN_PER_SEC = START_PUNTEN / (5 * 3600) # Doel: 5 uur
EXPECTED_COLS = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]

# --- 2. DATABASE (GOOGLE SHEETS) ---
@st.cache_resource
def get_ss_worksheet():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except Exception as e:
        st.error(f"Database connectie mislukt: {e}")
        return None

def get_db_as_df():
    ws = get_ss_worksheet()
    if not ws: return pd.DataFrame(columns=EXPECTED_COLS)
    
    data = ws.get_all_records()
    if data:
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(columns=EXPECTED_COLS)
    
    # Dwing numerieke types om TypeErrors te voorkomen
    num_cols = ['Score', 'Last_Update', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    
    df['Teamnaam'] = df['Teamnaam'].astype(str).str.upper()
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 3. DASHBOARDS ---

@st.fragment(run_every=10) # Admin ververst elke 10 sec
def show_admin_dashboard():
    st.title("🕹️ Thomas Baas Control Monitor")
    df = get_db_as_df()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📍 Live Overzicht")
        m = folium.Map(location=FINISH_COORDS, zoom_start=13)
        folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red', icon='flag')).add_to(m)
        for _, row in df.iterrows():
            if float(row['Cur_Lat']) != 0:
                folium.Marker([row['Cur_Lat'], row['Cur_Lon']], 
                              tooltip=f"{row['Teamnaam']} ({int(row['Score'])} pnt)",
                              icon=folium.Icon(color='blue')).add_to(m)
        st_folium(m, width="100%", height=500, key="admin_map")

    with col2:
        st.subheader("📊 Teams")
        st.dataframe(df[['Teamnaam', 'Score', 'Fase']], hide_index=True)
        
        st.subheader("🚀 Alarm Versturen")
        team_list = df['Teamnaam'].unique() if not df.empty else []
        target = st.selectbox("Selecteer Team:", team_list if len(team_list)>0 else ["Geen teams"])
        msg = st.text_input("Opdracht tekst")
        mins = st.number_input("Tijdslimiet (min)", 10)
        if st.button("Push naar Team"):
            deadline = time.time() + (mins * 60)
            df.loc[df['Teamnaam'] == target, 'Alarm'] = f"50|{msg}|{deadline}"
            save_df_to_db(df)
            st.success("Verzonden!")

@st.fragment(run_every=5) # User ververst elke 5 sec voor GPS & Klok
def show_user_dashboard():
    # GPS Bridge: stuurt locatie naar Streamlit
    st.components.v1.html("""
    <script>
        navigator.geolocation.getCurrentPosition((pos) => {
            window.parent.postMessage({
                type: 'streamlit:set_component_value',
                value: {lat: pos.coords.latitude, lon: pos.coords.longitude},
                key: 'gps_coord'
            }, '*');
        }, (err) => {}, {enableHighAccuracy: true});
    </script>
    """, height=0)

    gps = st.session_state.get("gps_coord")
    df = get_db_as_df()
    team_idx = df['Teamnaam'] == st.session_state.team
    if not any(team_idx): return
    my_data = df[team_idx].iloc[0]

    # Score & Locatie verwerking
    if gps:
        df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [float(gps['lat']), float(gps['lon'])]
        if my_data['Fase'] == "DROPPING":
            nu = time.time()
            dt = nu - float(my_data['Last_Update'] or nu)
            df.loc[team_idx, 'Score'] = max(0.0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
            df.loc[team_idx, 'Last_Update'] = nu
        save_df_to_db(df)
        my_data = df[team_idx].iloc[0]

    st.header(f"Team: {st.session_state.team} | 🏆 Score: {int(my_data['Score'])}")
    
    # Alarm & Aftelklok
    alarm_str = str(my_data['Alarm'])
    if "|" in alarm_str:
        pts, task, dl = alarm_str.split("|")
        sec_over = int(float(dl) - time.time())
        if sec_over > 0:
            st.error(f"🚨 OPDRACHT: {task} (+{pts} ptn)\n\n⌛ Tijd over: {sec_over // 60}m {sec_over % 60}s")
        else:
            st.warning(f"⌛ TIJD IS OM: {task}")

    # Kaart Fases
    if my_data['Fase'] == "LOCATIE_KIEZEN":
        st.info("Klik op de kaart waar je bent gedropt om te starten.")
        m = folium.Map(location=FINISH_COORDS, zoom_start=14)
        out = st_folium(m, width=700, height=400, key="picker")
        if out and out.get("last_clicked"):
            if st.button("BEVESTIG STARTPUNT"):
                c = out["last_clicked"]
                df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [float(c['lat']), float(c['lng']), float(c['lat']), float(c['lng']), "DROPPING", time.time()]
                save_df_to_db(df)
                st.rerun()
    else:
        # Blind Mode logica
        dist = math.sqrt((float(my_data['Cur_Lat'])-float(my_data['Start_Lat']))**2 + (float(my_data['Cur_Lon'])-float(my_data['Start_Lon']))**2) * 111000
        is_blind = dist > 5 # Blind mode na 5 meter
        m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
        if is_blind:
            folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
            st.warning("🙈 Blind Mode: Geen stratenplan meer zichtbaar!")
        
        folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green", weight=5).add_to(m)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red', icon='flag')).add_to(m)
        folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
        st_folium(m, width=700, height=500, key="live_map")

# --- 4. LOGIN & LOGOUT ---
if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    name = st.text_input("Teamnaam").strip().upper()
    pw = st.text_input("Wachtwoord (Admin)", type="password")
    if st.button("Inloggen"):
        role = "admin" if name == "THOMASBAAS" and pw == "bobodropping" else "user"
        st.session_state.update({"logged_in": True, "team": name, "role": role})
        # JS om login lokaal op te slaan
        st.components.v1.html(f"""
        <script>
            localStorage.setItem('dropping_team', '{name}');
            localStorage.setItem('dropping_role', '{role}');
            window.parent.location.reload();
        </script>
        """, height=0)
        st.rerun()
else:
    if st.session_state.role == "admin":
        show_admin_dashboard()
    else:
        show_user_dashboard()
    
    if st.sidebar.button("Log uit"):
        st.components.v1.html("<script>localStorage.clear(); window.parent.location.reload();</script>", height=0)
