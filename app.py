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

# FINISH COORDS: JC Bouckenborgh
FINISH_COORDS = [51.2443, 4.4505]
START_PUNTEN = 1000.0
TIJD_DOEL_UUR = 5 
PUNTEN_PER_SEC = START_PUNTEN / (TIJD_DOEL_UUR * 3600)
EXPECTED_COLS = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]

# --- 2. DATABASE CONNECTIE ---
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
    # Zorg dat Teamnaam altijd string is voor vergelijking
    df['Teamnaam'] = df['Teamnaam'].astype(str).str.upper()
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 3. AUTO-LOGIN VIA URL ---
# Check of er al een team in de URL staat (bijv. na een harde refresh)
query_params = st.query_params
if "team" in query_params and "role" in query_params:
    st.session_state.team = query_params["team"]
    st.session_state.role = query_params["role"]

# --- 4. LOGIN SCHERM ---
if "team" not in st.session_state:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip().upper()
    t_pass = st.text_input("Wachtwoord (enkel Admin)", type="password")
    
    if st.button("Inloggen"):
        if t_name == "THOMASBAAS" and t_pass == "bobodropping":
            st.session_state.team, st.session_state.role = "ADMIN", "admin"
            st.query_params["team"] = "ADMIN"
            st.query_params["role"] = "admin"
            st.rerun()
        elif t_name:
            df = get_db_as_df()
            if t_name not in df['Teamnaam'].values:
                new_row = {c: "" for c in EXPECTED_COLS}
                new_row.update({"Teamnaam": t_name, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": START_PUNTEN, "Last_Update": time.time()})
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role = t_name, "user"
            st.query_params["team"] = t_name
            st.query_params["role"] = "user"
            st.rerun()

# --- 5. DE DASHBOARDS (MET AUTO-REFRESH ZONDER LOGOUT) ---
else:
    # ADMIN DASHBOARD
    if st.session_state.role == "admin":
        st.title("🕹️ Thomas Baas Control")
        
        # Gebruik een fragment voor de automatische updates
        @st.fragment(run_every=10)
        def admin_view():
            df = get_db_as_df()
            col1, col2 = st.columns([2, 1])
            
            with col1:
                m = folium.Map(location=FINISH_COORDS, zoom_start=13)
                folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red')).add_to(m)
                for _, row in df.iterrows():
                    if float(row['Cur_Lat'] or 0) != 0:
                        folium.Marker([row['Cur_Lat'], row['Cur_Lon']], tooltip=row['Teamnaam']).add_to(m)
                st_folium(m, width="100%", height=400, key="admin_map")
            
            with col2:
                st.write("### Teams Status")
                st.dataframe(df[['Teamnaam', 'Score', 'Fase']], hide_index=True)

            # Opdrachten sectie binnen het fragment
            with st.expander("Pushen & Beheren"):
                target = st.selectbox("Selecteer Team:", df['Teamnaam'].unique())
                msg = st.text_input("Opdracht bericht")
                pts = st.number_input("Punten", 50)
                mins = st.number_input("Tijd (min)", 10)
                if st.button("Verstuur Opdracht"):
                    deadline = time.time() + (mins * 60)
                    df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}|{deadline}"
                    save_df_to_db(df)
                    st.success("Gezonden!")

        admin_view()
        
        if st.button("Uitloggen"):
            st.query_params.clear()
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

    # USER DASHBOARD
    else:
        st.header(f"Team: {st.session_state.team}")
        
        # GPS Bridge Script (Zorgt dat browser GPS blijft sturen)
        st.components.v1.html("""
            <script>
            function getLoc() {
                navigator.geolocation.getCurrentPosition((pos) => {
                    window.parent.postMessage({
                        type: 'streamlit:set_component_value',
                        value: {lat: pos.coords.latitude, lon: pos.coords.longitude, t: Date.now()},
                        key: 'gps_sync'
                    }, '*');
                }, (err) => console.log(err), {enableHighAccuracy: true});
            }
            setInterval(getLoc, 7000); 
            getLoc();
            </script>
        """, height=0)

        @st.fragment(run_every=7)
        def user_view():
            gps_val = st.session_state.get("gps_sync")
            df = get_db_as_df()
            team_idx = df['Teamnaam'] == st.session_state.team
            my_data = df[team_idx].iloc[0]

            # Update Positie & Score
            if gps_val:
                df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [gps_val['lat'], gps_val['lon']]
                if my_data['Fase'] == "DROPPING":
                    dt = time.time() - float(my_data['Last_Update'] or time.time())
                    df.loc[team_idx, 'Score'] = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
                    df.loc[team_idx, 'Last_Update'] = time.time()
                save_df_to_db(df)
            
            st.subheader(f"🏆 Score: {int(my_data['Score'])}")

            # Alarm / Opdracht
            if "|" in str(my_data['Alarm']):
                pts, task, dl = str(my_data['Alarm']).split("|")
                sec_over = int(float(dl) - time.time())
                if sec_over > 0:
                    st.error(f"🚨 {task} (+{pts}) | ⏳ {sec_over // 60}m {sec_over % 60}s")
                else: st.warning(f"⌛ TIJD OM: {task}")

            # Kaart
            if my_data['Fase'] == "LOCATIE_KIEZEN":
                st.info("Kies je huidige positie op de kaart.")
                m = folium.Map(location=[51.244, 4.450], zoom_start=15)
                out = st_folium(m, width=700, height=350, key="user_start_map")
                if out and out.get("last_clicked"):
                    if st.button("BEVESTIG STARTPUNT"):
                        c = out["last_clicked"]
                        df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [c['lat'], c['lng'], c['lat'], c['lng'], "DROPPING", time.time()]
                        save_df_to_db(df); st.rerun()
            else:
                # Blind mode logica
                dist = math.sqrt((float(my_data['Cur_Lat'])-float(my_data['Start_Lat']))**2) * 111000
                is_blind = dist > 3
                m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
                if is_blind:
                    folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
                folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green").add_to(m)
                folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
                folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
                st_folium(m, width=700, height=450, key="user_live_map")

        user_view()
        
        if st.button("Log uit"):
            st.query_params.clear()
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
