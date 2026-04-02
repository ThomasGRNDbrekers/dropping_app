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

# --- 2. DATABASE FUNCTIES ---
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
        if not data: 
            ws.update([EXPECTED_COLS])
            return pd.DataFrame(columns=EXPECTED_COLS)
        df = pd.DataFrame(data)
        num_cols = ['Score', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Last_Update']
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        return df
    except:
        return pd.DataFrame(columns=EXPECTED_COLS)

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws and not df.empty:
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 3. PERSISTENT LOGIN (Browser Memory) ---
st.components.v1.html(f"""
    <script>
    const team = localStorage.getItem('dropping_team');
    if (team && !window.location.href.includes('team=')) {{
        window.parent.postMessage({{type: 'streamlit:set_component_value', value: team, key: 'stored_team'}}, '*');
    }}
    </script>
""", height=0)

if st.session_state.get('stored_team') and 'team' not in st.session_state:
    st.session_state.team = st.session_state.stored_team
    st.session_state.logged_in = True
    st.session_state.role = "user"

# --- 4. LOGIN SCHERM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip().upper()
    t_pass = st.text_input("Wachtwoord (enkel voor Admin)", type="password")
    
    if st.button("Start Dropping"):
        if t_name == "THOMASBAAS" and t_pass == "bobodropping":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name:
            st.components.v1.html(f"<script>localStorage.setItem('dropping_team', '{t_name}');</script>", height=0)
            df = get_db_as_df()
            if t_name not in df['Teamnaam'].astype(str).values:
                new_row = {c: "" for c in EXPECTED_COLS}
                new_row.update({"Teamnaam": t_name, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": START_PUNTEN, "Last_Update": time.time()})
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()

else:
    # --- 5. ADMIN (THOMAS BAAS) ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db_as_df()
        
        m = folium.Map(location=FINISH_COORDS, zoom_start=13)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
        for _, row in df.iterrows():
            if row['Cur_Lat'] != 0:
                folium.Marker([row['Cur_Lat'], row['Cur_Lon']], tooltip=row['Teamnaam']).add_to(m)
        st_folium(m, width="100%", height=400)
        
        st.write(f"Aantal actieve teams: {len(df)}")
        st.dataframe(df)

        with st.expander("Push Opdracht"):
            target = st.selectbox("Team:", df['Teamnaam'].unique())
            msg = st.text_input("Opdracht")
            pts = st.number_input("Punten", 50)
            mins = st.number_input("Minuten", 10)
            if st.button("Verstuur"):
                deadline = time.time() + (mins * 60)
                df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}|{deadline}"
                save_df_to_db(df); st.rerun()

        # Auto-refresh voor Admin
        st.components.v1.html("<script>setTimeout(()=>window.location.reload(), 10000)</script>", height=0)

    # --- 6. DEELNEMERS ---
    else:
        # GEAVANCEERDE GPS & TIMER SCRIPT
        st.components.v1.html("""
            <script>
            function pushGPS() {
                navigator.geolocation.getCurrentPosition((pos) => {
                    window.parent.postMessage({
                        type: 'streamlit:set_component_value',
                        value: {lat: pos.coords.latitude, lon: pos.coords.longitude, t: Date.now()},
                        key: 'gps_sync'
                    }, '*');
                }, (err) => { console.error(err); }, {enableHighAccuracy: true});
            }
            setInterval(pushGPS, 5000);
            pushGPS(); // Eerste keer direct
            </script>
        """, height=0)

        gps_val = st.session_state.get("gps_sync")
        df = get_db_as_df()
        team_idx = df['Teamnaam'] == st.session_state.team
        my_data = df[team_idx].iloc[0]

        # Score & Locatie Sync
        if gps_val:
            df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [gps_val['lat'], gps_val['lon']]
            if my_data['Fase'] == "DROPPING":
                dt = time.time() - float(my_data['Last_Update'])
                # Strafberekening (afwijking van lijn)
                df.loc[team_idx, 'Score'] = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
                df.loc[team_idx, 'Last_Update'] = time.time()
            save_df_to_db(df)
            my_data = df[team_idx].iloc[0]

        st.header(f"Team: {st.session_state.team} | 🏆 {int(my_data['Score'])}")
        
        # Live Aftelklok Opdracht
        if "|" in str(my_data['Alarm']):
            pts, task, dl = str(my_data['Alarm']).split("|")
            sec_over = int(float(dl) - time.time())
            if sec_over > 0:
                st.error(f"🚨 {task} (+{pts} ptn) | ⏳ {sec_over // 60}m {sec_over % 60}s")
            else: st.warning(f"⌛ TIJD OM: {task}")

        # Kaart Logic
        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Duid je startpunt aan op de kaart.")
            center = [gps_val['lat'], gps_val['lon']] if gps_val else [51.244, 4.450]
            m = folium.Map(location=center, zoom_start=17)
            if gps_val: folium.Marker(center, icon=folium.Icon(color='blue', icon='user')).add_to(m)
            st_data = st_folium(m, width=700, height=400, key="start_map")
            if st_data and st_data.get("last_clicked"):
                if st.button("BEVESTIG START"):
                    c = st_data["last_clicked"]
                    df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [c['lat'], c['lng'], c['lat'], c['lng'], "DROPPING", time.time()]
                    save_df_to_db(df); st.rerun()
        else:
            # Blind Mode Check
            lat_start, lon_start = my_data['Start_Lat'], my_data['Start_Lon']
            dist = math.sqrt((my_data['Cur_Lat']-lat_start)**2 + (my_data['Cur_Lon']-lon_start)**2) * 111000
            is_blind = dist > 2 # 2 meter drempel
            
            m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
            if is_blind:
                folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
            
            folium.PolyLine([[lat_start, lon_start], FINISH_COORDS], color="green", weight=5, dash_array='10').add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
            folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
            st_folium(m, width=700, height=500, key="live_map")

        if st.button("Log uit"):
            st.components.v1.html("<script>localStorage.removeItem('dropping_team'); window.location.reload();</script>", height=0)

        # Auto-refresh
        st.components.v1.html("<script>setTimeout(()=>window.location.reload(), 10000)</script>", height=0)
