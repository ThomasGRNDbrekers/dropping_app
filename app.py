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
TIJD_DOEL_UUR = 5 
PUNTEN_PER_SEC = START_PUNTEN / (TIJD_DOEL_UUR * 3600)
EXPECTED_COLS = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]

# --- 2. DB FUNCTIES ---
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
    for c in ['Score', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Last_Update']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 3. LOGIN LOGIC ---
if 'team' not in st.session_state:
    st.session_state.team = None
    st.session_state.role = None

# Login Scherm
if not st.session_state.team:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip().upper()
    t_pass = st.text_input("Wachtwoord (enkel Admin)", type="password")
    
    if st.button("Inloggen"):
        if t_name == "THOMASBAAS" and t_pass == "bobodropping":
            st.session_state.team, st.session_state.role = "ADMIN", "admin"
            st.rerun()
        elif t_name:
            df = get_db_as_df()
            if t_name not in df['Teamnaam'].values:
                new_row = {c: (0.0 if i > 3 else "") for i, c in enumerate(EXPECTED_COLS)}
                new_row.update({"Teamnaam": t_name, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": START_PUNTEN, "Last_Update": time.time()})
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role = t_name, "user"
            st.rerun()
else:
    # --- 4. ADMIN SECTIE ---
    if st.session_state.role == "admin":
        st.title("🕹️ Thomas Baas Control")
        df = get_db_as_df()
        
        # Kaart
        m = folium.Map(location=FINISH_COORDS, zoom_start=13)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red', icon='flag')).add_to(m)
        for _, row in df.iterrows():
            if row['Cur_Lat'] != 0:
                folium.Marker([row['Cur_Lat'], row['Cur_Lon']], tooltip=row['Teamnaam']).add_to(m)
        st_folium(m, width="100%", height=400, key="admin_map")
        
        st.dataframe(df)

        # Opdrachten
        with st.expander("Nieuwe Opdracht"):
            target = st.selectbox("Team:", df['Teamnaam'].unique())
            msg = st.text_input("Wat is de opdracht?")
            pts = st.number_input("Punten", 50)
            mins = st.number_input("Minuten", 10)
            if st.button("Verstuur naar Team"):
                deadline = time.time() + (mins * 60)
                df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}|{deadline}"
                save_df_to_db(df); st.rerun()

        if st.button("Uitloggen"):
            st.session_state.team = None
            st.rerun()

        # FORCE REFRESH ADMIN
        st.components.v1.html("<script>setTimeout(() => { window.parent.location.reload(); }, 12000);</script>", height=0)

    # --- 5. USER SECTIE ---
    else:
        # GPS BRIDGE
        st.components.v1.html("""
            <script>
            function getLocation() {
                navigator.geolocation.getCurrentPosition((pos) => {
                    window.parent.postMessage({
                        type: 'streamlit:set_component_value',
                        value: {lat: pos.coords.latitude, lon: pos.coords.longitude, t: Date.now()},
                        key: 'gps_sync'
                    }, '*');
                }, (err) => { alert("GPS Error: " + err.message); }, {enableHighAccuracy: true});
            }
            // Elke 8 seconden pushen
            setInterval(getLocation, 8000);
            </script>
        """, height=0)

        gps_val = st.session_state.get("gps_sync")
        df = get_db_as_df()
        team_idx = df['Teamnaam'] == st.session_state.team
        my_data = df[team_idx].iloc[0]

        # Score & Sync
        if gps_val:
            df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [gps_val['lat'], gps_val['lon']]
            if my_data['Fase'] == "DROPPING":
                dt = time.time() - float(my_data['Last_Update'])
                df.loc[team_idx, 'Score'] = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
                df.loc[team_idx, 'Last_Update'] = time.time()
            save_df_to_db(df)
            my_data = df[team_idx].iloc[0]

        st.header(f"Team: {st.session_state.team} | 🏆 {int(my_data['Score'])}")
        
        # GPS Wake-up knop
        if not gps_val:
            if st.button("📍 KLIK HIER OM LIVE GPS TE STARTEN"):
                st.rerun()

        # Alarm & Klok
        if "|" in str(my_data['Alarm']):
            pts, task, dl = str(my_data['Alarm']).split("|")
            sec_over = int(float(dl) - time.time())
            if sec_over > 0:
                st.error(f"🚨 {task} (+{pts} ptn) | ⏳ {sec_over // 60}m {sec_over % 60}s")
            else:
                st.warning(f"⌛ TIJD OM: {task}")

        # Fase Kaart
        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Klik op de kaart waar je nu bent.")
            m = folium.Map(location=[51.244, 4.450], zoom_start=15)
            if gps_val: folium.Marker([gps_val['lat'], gps_val['lon']], icon=folium.Icon(color='blue')).add_to(m)
            out = st_folium(m, width=700, height=400, key="start_map")
            if out and out.get("last_clicked"):
                c = out["last_clicked"]
                if st.button("BEVESTIG STARTPUNT"):
                    df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [c['lat'], c['lng'], c['lat'], c['lng'], "DROPPING", time.time()]
                    save_df_to_db(df); st.rerun()
        else:
            # Blind mode
            dist = math.sqrt((my_data['Cur_Lat']-my_data['Start_Lat'])**2 + (my_data['Cur_Lon']-my_data['Start_Lon'])**2) * 111000
            is_blind = dist > 3
            m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
            if is_blind:
                folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
                st.warning("🙈 BLIND MODE")
            folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green", weight=5).add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
            folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
            st_folium(m, width=700, height=450, key="live_map")

        # FORCE REFRESH USER
        st.components.v1.html("<script>setTimeout(() => { window.parent.location.reload(); }, 10000);</script>", height=0)
