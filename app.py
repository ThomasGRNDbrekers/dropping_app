import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time
import math

# --- 1. INITIALISATIE ---
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
    
    # CRUCIALE FIX: Dwing kolommen naar getallen om TypeError te voorkomen
    num_cols = ['Score', 'Last_Update', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
    df['Teamnaam'] = df['Teamnaam'].astype(str).str.upper()
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        # Alles als tekst naar de sheet schrijven is prima, Pandas heeft het nu intern als getal
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 4. DASHBOARDS ---

@st.fragment(run_every=10)
def show_admin_dashboard():
    st.title("🕹️ Thomas Baas Control")
    df = get_db_as_df()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        m = folium.Map(location=FINISH_COORDS, zoom_start=13)
        folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red')).add_to(m)
        for _, row in df.iterrows():
            if float(row['Cur_Lat']) != 0:
                folium.Marker([row['Cur_Lat'], row['Cur_Lon']], tooltip=row['Teamnaam']).add_to(m)
        st_folium(m, width="100%", height=450, key="admin_map_live")

    with col2:
        st.write("### Live Teams")
        st.dataframe(df[['Teamnaam', 'Score', 'Fase']], hide_index=True)
        
        with st.expander("Nieuwe Opdracht"):
            target = st.selectbox("Team:", df['Teamnaam'].unique() if not df.empty else ["GEEN TEAMS"])
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
    # De GPS Bridge script
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
    
    if not any(team_idx):
        st.error("Team niet gevonden. Log opnieuw in.")
        st.session_state.logged_in = False
        st.rerun()

    my_data = df[team_idx].iloc[0]

    # Sync GPS & Score
    if gps_val:
        df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [float(gps_val['lat']), float(gps_val['lon'])]
        if my_data['Fase'] == "DROPPING":
            nu = time.time()
            dt = nu - float(my_data['Last_Update'] or nu)
            df.loc[team_idx, 'Score'] = max(0.0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
            df.loc[team_idx, 'Last_Update'] = nu
        save_df_to_db(df)
        # Update lokale variabele na opslaan
        my_data = df[team_idx].iloc[0]

    st.header(f"Team: {st.session_state.team} | 🏆 {int(my_data['Score'])}")
    
    # Alarm/Timer
    if "|" in str(my_data['Alarm']):
        parts = str(my_data['Alarm']).split("|")
        if len(parts) == 3:
            pts, task, dl = parts
            sec_over = int(float(dl) - time.time())
            if sec_over > 0:
                st.error(f"🚨 {task} (+{pts}) | ⏳ {sec_over // 60}m {sec_over % 60}s")
            else: st.warning(f"⌛ TIJD OM: {task}")

    # Kaart logica
    if my_data['Fase'] == "LOCATIE_KIEZEN":
        st.info("Kies je startpunt op de kaart.")
        m = folium.Map(location=FINISH_COORDS, zoom_start=15)
        out = st_folium(m, width=700, height=350, key="start_map_user")
        if out and out.get("last_clicked"):
            if st.button("BEVESTIG STARTPUNT"):
                c = out["last_clicked"]
                df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [float(c['lat']), float(c['lng']), float(c['lat']), float(c['lng']), "DROPPING", time.time()]
                save_df_to_db(df)
                st.rerun()
    else:
        dist = math.sqrt((float(my_data['Cur_Lat'])-float(my_data['Start_Lat']))**2 + (float(my_data['Cur_Lon'])-float(my_data['Start_Lon']))**2) * 111000
        is_blind = dist > 2
        m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
        if is_blind:
            folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
        folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green").add_to(m)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
        folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
        st_folium(m, width=700, height=450, key="live_map_user")

# --- 5. HOOFD LOGICA ---

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    name = st.text_input("Teamnaam").strip().upper()
    pw = st.text_input("Wachtwoord (Admin)", type="password")
    
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
                new_row.update({"Teamnaam": name, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": float(START_PUNTEN), "Last_Update": time.time(), "Start_Lat": 0.0, "Start_Lon": 0.0, "Cur_Lat": 0.0, "Cur_Lon": 0.0})
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.logged_in = True
            st.session_state.role = "user"
            st.session_state.team = name
            st.rerun()
else:
    if st.session_state.role == "admin":
        show_admin_dashboard()
    else:
        show_user_dashboard()
        
    if st.sidebar.button("Uitloggen"):
        st.session_state.logged_in = False
        st.rerun()
