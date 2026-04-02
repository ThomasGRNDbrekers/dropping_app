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

# --- 2. DATABASE FUNCTIES (Met API-beveiliging) ---
@st.cache_resource
def get_ss_worksheet():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except:
        return None

@st.cache_data(ttl=10) # Cache data voor 10 sec om API-errors te voorkomen
def fetch_data_safe():
    ws = get_ss_worksheet()
    if ws:
        try:
            return ws.get_all_records()
        except:
            return None
    return None

def get_db_as_df():
    data = fetch_data_safe()
    
    # Gebruik cache uit session_state als de API weigert
    if data is None:
        if "last_df" in st.session_state:
            return st.session_state.last_df
        return pd.DataFrame(columns=EXPECTED_COLS)

    df = pd.DataFrame(data) if data else pd.DataFrame(columns=EXPECTED_COLS)
    
    # Numerieke conversie
    num_cols = ['Score', 'Last_Update', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    
    df['Teamnaam'] = df['Teamnaam'].astype(str).str.upper()
    st.session_state.last_df = df
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        try:
            ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())
        except:
            st.warning("Opslaan mislukt (API druk), probeer zo dadelijk opnieuw.")

# --- 3. LOGIN BEHEER ---
if "team" not in st.session_state:
    params = st.query_params
    if "t" in params and "r" in params:
        st.session_state.team = params["t"]
        st.session_state.role = params["r"]
    else:
        st.session_state.team = None

# --- 4. LOGIN SCHERM ---
if not st.session_state.team:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip().upper()
    t_pass = st.text_input("Wachtwoord (Admin)", type="password")
    
    if st.button("Start"):
        if t_name == "THOMASBAAS" and t_pass == "bobodropping":
            st.session_state.team, st.session_state.role = "ADMIN", "admin"
        elif t_name:
            df = get_db_as_df()
            if t_name not in df['Teamnaam'].values:
                new_row = {c: 0.0 for c in EXPECTED_COLS}
                new_row.update({"Teamnaam": t_name, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": START_PUNTEN, "Last_Update": time.time()})
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role = t_name, "user"
        
        if st.session_state.team:
            st.query_params["t"] = st.session_state.team
            st.query_params["r"] = st.session_state.role
            st.rerun()

# --- 5. ADMIN DASHBOARD ---
elif st.session_state.role == "admin":
    st.title("🕹️ Control Room")
    df = get_db_as_df()
    
    m = folium.Map(location=FINISH_COORDS, zoom_start=12)
    folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red', icon='flag')).add_to(m)
    for _, row in df.iterrows():
        if float(row['Cur_Lat']) != 0:
            folium.Marker([row['Cur_Lat'], row['Cur_Lon']], tooltip=row['Teamnaam']).add_to(m)
    
    st_folium(m, width="100%", height=400, key="admin_map")
    st.dataframe(df[['Teamnaam', 'Score', 'Fase', 'Alarm']], hide_index=True)
    
    with st.expander("Opdracht Pushen"):
        target = st.selectbox("Team:", df['Teamnaam'].unique() if not df.empty else ["-"])
        msg = st.text_input("Bericht")
        mins = st.number_input("Minuten", 10)
        if st.button("Verstuur"):
            deadline = time.time() + (mins * 60)
            df.loc[df['Teamnaam'] == target, 'Alarm'] = f"50|{msg}|{deadline}"
            save_df_to_db(df)
            st.success("Verzonden!")

    if st.sidebar.button("Uitloggen"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()

    time.sleep(20) # Rustiger voor de API
    st.rerun()

# --- 6. DEELNEMERS DASHBOARD ---
else:
    # GPS KNOP VOOR BROWSER PERMISSIE
    st.components.v1.html("""
    <div style="background-color: #f0f2f6; padding: 10px; border-radius: 8px; text-align: center;">
        <button id="gps_btn" style="background-color: #ff4b4b; color: white; border: none; padding: 15px; font-size: 16px; border-radius: 8px; width: 100%; font-weight: bold;">
            📡 ACTIVEER LIVE GPS
        </button>
    </div>
    <script>
    const btn = document.getElementById('gps_btn');
    btn.onclick = function() {
        navigator.geolocation.watchPosition((pos) => {
            window.parent.postMessage({
                type: 'streamlit:set_component_value',
                value: {lat: pos.coords.latitude, lon: pos.coords.longitude},
                key: 'gps'
            }, '*');
            btn.innerHTML = "✅ GPS ACTIEF";
            btn.style.backgroundColor = "#28a745";
        }, (err) => { alert("Zet je GPS aan in browser instellingen!"); }, 
        {enableHighAccuracy: true, maximumAge: 0});
    };
    </script>
    """, height=100)

    df = get_db_as_df()
    team_idx = df['Teamnaam'] == st.session_state.team
    if not any(team_idx): st.rerun()
    my_data = df[team_idx].iloc[0]
    
    gps = st.session_state.get("gps")
    if gps:
        # Update alleen bij significante beweging om API te sparen
        if abs(float(my_data['Cur_Lat']) - gps['lat']) > 0.00005:
            df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [gps['lat'], gps['lon']]
            if my_data['Fase'] == "DROPPING":
                nu = time.time()
                dt = nu - float(my_data['Last_Update'] or nu)
                df.loc[team_idx, 'Score'] = max(0.0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
                df.loc[team_idx, 'Last_Update'] = nu
            save_df_to_db(df)
            my_data = df[team_idx].iloc[0]

    st.header(f"Team: {st.session_state.team} | 🏆 {int(my_data['Score'])} ptn")
    
    # Klok
    if "|" in str(my_data['Alarm']):
        pts, task, dl = str(my_data['Alarm']).split("|")
        over = int(float(dl) - time.time())
        if over > 0: st.error(f"🚨 {task} | ⏳ {over // 60}m {over % 60}s")
        else: st.warning(f"⌛ TIJD OM: {task}")

    # Fase Kaart
    if my_data['Fase'] == "LOCATIE_KIEZEN":
        st.info("Duid je startpunt aan op de kaart.")
        m = folium.Map(location=FINISH_COORDS, zoom_start=15)
        out = st_folium(m, width=700, height=400, key="picker")
        if out and out.get("last_clicked"):
            if st.button("BEVESTIG START"):
                c = out["last_clicked"]
                df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [c['lat'], c['lng'], c['lat'], c['lng'], "DROPPING", time.time()]
                save_df_to_db(df)
                st.rerun()
    else:
        dist = math.sqrt((float(my_data['Cur_Lat'])-float(my_data['Start_Lat']))**2 + (float(my_data['Cur_Lon'])-float(my_data['Start_Lon']))**2) * 111000
        is_blind = dist > 5
        m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
        if is_blind:
            folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
        folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green", weight=5).add_to(m)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
        folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
        st_folium(m, width=700, height=500, key="map")

    if st.sidebar.button("Uitloggen"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()

    time.sleep(15)
    st.rerun()
