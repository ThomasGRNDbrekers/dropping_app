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

# Finish Coördinaten (JC Bouckenborgh)
FINISH_COORDS = [51.2443, 4.4505]
START_PUNTEN = 1000.0
PUNTEN_PER_SEC = START_PUNTEN / (5 * 3600)
EXPECTED_COLS = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]

# --- 2. DATABASE FUNCTIES ---
@st.cache_resource
def get_ss_worksheet():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except:
        st.error("Google Sheets verbinding mislukt. Controleer je Secrets.")
        return None

def get_db_as_df():
    ws = get_ss_worksheet()
    if not ws: return pd.DataFrame(columns=EXPECTED_COLS)
    data = ws.get_all_records()
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=EXPECTED_COLS)
    # Dwing numerieke kolommen naar float om crashes te voorkomen
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

# --- 3. LOGIN BEHEER (URL & SESSION) ---
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
    t_pass = st.text_input("Wachtwoord (enkel Admin)", type="password")
    
    if st.button("Start Dropping"):
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
    st.title("🕹️ Control Room: Thomas Baas")
    df = get_db_as_df()
    
    m = folium.Map(location=FINISH_COORDS, zoom_start=12)
    folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red', icon='flag'), tooltip="FINISH").add_to(m)
    for _, row in df.iterrows():
        if float(row['Cur_Lat']) != 0:
            folium.Marker([row['Cur_Lat'], row['Cur_Lon']], 
                          tooltip=f"{row['Teamnaam']} ({int(row['Score'])} ptn)",
                          icon=folium.Icon(color='blue')).add_to(m)
    
    st_folium(m, width="100%", height=400, key="admin_map")
    st.dataframe(df[['Teamnaam', 'Score', 'Fase', 'Alarm']], hide_index=True)
    
    with st.expander("Nieuwe Opdracht Pushen"):
        target = st.selectbox("Selecteer Team:", df['Teamnaam'].unique() if not df.empty else ["Geen teams"])
        msg = st.text_input("Wat is de opdracht?")
        mins = st.number_input("Tijdslimiet (minuten)", 10)
        if st.button("Verstuur Alarm"):
            deadline = time.time() + (mins * 60)
            df.loc[df['Teamnaam'] == target, 'Alarm'] = f"50|{msg}|{deadline}"
            save_df_to_db(df)
            st.success(f"Opdracht naar {target} gestuurd!")

    if st.sidebar.button("Uitloggen"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()

    # Automatische verversing van de Control Room
    time.sleep(15)
    st.rerun()

# --- 6. DEELNEMERS DASHBOARD ---
else:
    # GPS ACTIVATIE KNOP (Cruciaal voor browser permissies)
    st.components.v1.html("""
    <div style="background-color: #f0f2f6; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #d1d3d8;">
        <button id="gps_btn" style="background-color: #ff4b4b; color: white; border: none; padding: 15px; font-size: 16px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold;">
            📡 ACTIVEER LIVE GPS (KLIK HIER)
        </button>
        <p id="status" style="margin-top: 8px; font-size: 12px; color: #555;">GPS status: Niet verbonden</p>
    </div>
    <script>
    const btn = document.getElementById('gps_btn');
    const status = document.getElementById('status');
    btn.onclick = function() {
        navigator.geolocation.watchPosition((pos) => {
            window.parent.postMessage({
                type: 'streamlit:set_component_value',
                value: {lat: pos.coords.latitude, lon: pos.coords.longitude},
                key: 'gps'
            }, '*');
            btn.innerHTML = "✅ GPS VERBONDEN";
            btn.style.backgroundColor = "#28a745";
            status.innerHTML = "Locatie wordt live gedeeld met Control Room";
        }, (err) => {
            alert("GPS Fout: Zorg dat locatie aan staat in je browser-instellingen.");
            status.innerHTML = "Fout: " + err.message;
        }, {enableHighAccuracy: true, maximumAge: 0});
    };
    </script>
    """, height=130)

    df = get_db_as_df()
    team_idx = df['Teamnaam'] == st.session_state.team
    if not any(team_idx):
        st.error("Team niet gevonden. Log opnieuw in.")
        st.session_state.clear()
        st.rerun()
    
    my_data = df[team_idx].iloc[0]
    
    # GPS Verwerking
    gps = st.session_state.get("gps")
    if gps:
        df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [float(gps['lat']), float(gps['lon'])]
        if my_data['Fase'] == "DROPPING":
            nu = time.time()
            dt = nu - float(my_data['Last_Update'] or nu)
            df.loc[team_idx, 'Score'] = max(0.0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC))
            df.loc[team_idx, 'Last_Update'] = nu
        save_df_to_db(df)
        my_data = df[team_idx].iloc[0]

    st.header(f"Team: {st.session_state.team} | 🏆 {int(my_data['Score'])} ptn")
    
    # Alarm & Aftelklok
    if "|" in str(my_data['Alarm']):
        pts, task, dl = str(my_data['Alarm']).split("|")
        over = int(float(dl) - time.time())
        if over > 0:
            st.error(f"🚨 OPDRACHT: {task}\n\n⌛ TIJD OVER: {over // 60}m {over % 60}s")
        else:
            st.warning(f"⌛ TIJD IS OM: {task}")

    # Kaart Fase Logica
    if my_data['Fase'] == "LOCATIE_KIEZEN":
        st.info("Stap 1: Klik op de kaart waar je bent afgezet en druk op Bevestig.")
        m = folium.Map(location=FINISH_COORDS, zoom_start=14)
        out = st_folium(m, width=700, height=400, key="picker")
        if out and out.get("last_clicked"):
            if st.button("BEVESTIG STARTPUNT"):
                c = out["last_clicked"]
                df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Fase', 'Last_Update']] = [c['lat'], c['lng'], c['lat'], c['lng'], "DROPPING", time.time()]
                save_df_to_db(df)
                st.rerun()
    else:
        # Blind Mode logica
        dist = math.sqrt((float(my_data['Cur_Lat'])-float(my_data['Start_Lat']))**2 + (float(my_data['Cur_Lon'])-float(my_data['Start_Lon']))**2) * 111000
        is_blind = dist > 5
        m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
        if is_blind:
            folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
            st.warning("🙈 BLIND MODE ACTIEF: Gebruik de kompaslijn!")
        
        folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green", weight=5).add_to(m)
        folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red', icon='flag')).add_to(m)
        folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
        st_folium(m, width=700, height=500, key="live_map")

    if st.sidebar.button("Uitloggen"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()

    # Verversen voor de klok
    time.sleep(10)
    st.rerun()
