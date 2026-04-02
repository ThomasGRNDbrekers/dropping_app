import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time
import math

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026 - Master Control", layout="wide")
FINISH_COORDS = [51.2443, 4.4505] # JC Bouckenborgh
START_PUNTEN = 1000.0
TIJD_DOEL_UUR = 5 
PUNTEN_PER_SEC = START_PUNTEN / (TIJD_DOEL_UUR * 3600)
REFRESH_RATE = 10 
BLIND_MODE_DISTANCE = 0.002 # 2 meter voor test
EXPECTED_COLS = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]

# --- HELPERS ---
def haversine_distance(p1, p2):
    if not p1 or not p2 or p1[0] == 0 or p2[0] == 0: return 0
    lat1, lon1, lat2, lon2 = p1[0], p1[1], p2[0], p2[1]
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_distance_to_line(p_cur, p_start, p_fin):
    try:
        y3, x3 = p_cur
        y1, x1 = p_start
        y2, x2 = p_fin
        px, py = x2-x1, y2-y1
        norm = px*px + py*py
        if norm == 0: return 0
        u = max(0, min(1, ((x3-x1)*px + (y3-y1)*py) / float(norm)))
        return math.sqrt(((x1 + u*px) - x3)**2 + ((y1 + u*py) - y3)**2) * 111
    except: return 0

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
    except: # Als de sheet echt helemaal leeg is of geen headers heeft
        ws.update([EXPECTED_COLS])
        return pd.DataFrame(columns=EXPECTED_COLS)
        
    df = pd.DataFrame(data)
    
    # Check of de headers kloppen, zo niet: herstel ze
    if df.empty or "Teamnaam" not in df.columns:
        ws.clear()
        ws.update([EXPECTED_COLS])
        return pd.DataFrame(columns=EXPECTED_COLS)
    
    # Numerieke conversie
    num_cols = ['Score', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Last_Update']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws and not df.empty:
        # Altijd headers + data opslaan
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip().upper()
    t_pass = st.text_input("Wachtwoord (enkel Admin)", type="password")
    if st.button("Aanmelden"):
        if t_name == "THOMASBAAS" and t_pass == "bobodropping":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name:
            df = get_db_as_df()
            if t_name not in df['Teamnaam'].astype(str).values:
                new_row = {c: "" for c in EXPECTED_COLS}
                new_row.update({"Teamnaam": t_name, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": START_PUNTEN, "Last_Update": time.time(), "Start_Lat": 0.0, "Start_Lon": 0.0, "Cur_Lat": 0.0, "Cur_Lon": 0.0})
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
    # --- THOMAS BAAS (ADMIN) ---
    if st.session_state.role == "admin":
        st.title("🕹️ Thomas Baas - Master Control")
        df = get_db_as_df()
        
        # Admin Overzichtskaart
        m_admin = folium.Map(location=FINISH_COORDS, zoom_start=13)
        folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red', icon='flag')).add_to(m_admin)
        for i, row in df.iterrows():
            if row['Cur_Lat'] != 0:
                folium.Marker([row['Cur_Lat'], row['Cur_Lon']], 
                              tooltip=f"{row['Teamnaam']}", 
                              icon=folium.Icon(color='blue' if i%2==0 else 'orange')).add_to(m_admin)
        st_folium(m_admin, width="100%", height=400, key="admin_map")
        
        st.dataframe(df)

        st.subheader("🚀 Acties")
        col1, col2 = st.columns(2)
        with col1:
            target = st.selectbox("Selecteer Team:", df['Teamnaam'].unique() if not df.empty else [])
            msg = st.text_input("Opdracht")
            pts_val = st.number_input("Punten Bonus", 50)
            mins = st.number_input("Tijd (min)", 10)
            if st.button("Pushen"):
                deadline = time.time() + (mins * 60)
                df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts_val}|{msg}|{deadline}"
                save_df_to_db(df); st.rerun()
        
        with col2:
            if st.button("✅ Opdracht voltooid"):
                val = str(df.loc[df['Teamnaam'] == target, 'Alarm'].values[0])
                bonus = float(val.split('|')[0]) if '|' in val else 0
                df.loc[df['Teamnaam'] == target, 'Score'] += bonus
                df.loc[df['Teamnaam'] == target, 'Alarm'] = "GEEN"; save_df_to_db(df); st.rerun()

        st.components.v1.html("<script>setTimeout(()=>window.location.reload(), 15000)</script>", height=0)

    # --- DEELNEMERS (USER) ---
    else:
        # Smartphone GPS Forceer Script
        st.components.v1.html("""
            <script>
            function pushLoc(pos) {
                window.parent.postMessage({
                    type: 'streamlit:set_component_value',
                    value: {lat: pos.coords.latitude, lon: pos.coords.longitude, t: Date.now()},
                    key: 'gps_sync'
                }, '*');
            }
            navigator.geolocation.watchPosition(pushLoc, (err) => console.log(err), {enableHighAccuracy: true, maximumAge: 0});
            </script>
        """, height=0)

        gps_val = st.session_state.get("gps_sync")
        df = get_db_as_df()
        team_idx = df['Teamnaam'] == st.session_state.team
        my_data = df[team_idx].iloc[0]

        # GPS & Score Sync
        if gps_val:
            cur_pos = [gps_val['lat'], gps_val['lon']]
            df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = cur_pos
            if my_data['Fase'] == "DROPPING":
                nu = time.time()
                dt = nu - float(my_data['Last_Update'])
                dist_line = get_distance_to_line(cur_pos, [my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS)
                dist_start = haversine_distance([my_data['Start_Lat'], my_data['Start_Lon']], cur_pos)
                straf = 1 + (dist_line * 15) if dist_start > BLIND_MODE_DISTANCE else 1
                df.loc[team_idx, 'Score'] = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC * straf))
                df.loc[team_idx, 'Last_Update'] = nu
            save_df_to_db(df)
            my_data = df[team_idx].iloc[0]

        st.title(f"🏆 {int(my_data['Score'])} pnt")
        
        # Alarm & Timer UI
        if "|" in str(my_data['Alarm']):
            pts, task, dl = str(my_data['Alarm']).split("|")
            sec_over = int(float(dl) - time.time())
            st.error(f"🚨 {task} (+{pts} ptn)")
            if sec_over > 0:
                st.metric("Tijd over", f"{sec_over // 60}m {sec_over % 60}s")
            else: st.warning("⌛ Tijd is verstreken!")

        # Kaart Fases
        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Kies je droppingpunt. Blauw bolletje = JOUW GPS.")
            center = [gps_val['lat'], gps_val['lon']] if gps_val else [51.244, 4.450]
            m = folium.Map(location=center, zoom_start=17)
            if gps_val: folium.Marker(center, icon=folium.Icon(color='blue', icon='user')).add_to(m)
            st_data = st_folium(m, width=700, height=400, key="start_map")
            if st_data and st_data.get("last_clicked"):
                if st.button("BEVESTIG STARTPUNT"):
                    c = st_data["last_clicked"]
                    df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon']] = [c['lat'], c['lng'], c['lat'], c['lng']]
                    df.loc[team_idx, 'Fase'] = "DROPPING"; df.loc[team_idx, 'Last_Update'] = time.time()
                    save_df_to_db(df); st.rerun()
        else:
            dist_start = haversine_distance([my_data['Start_Lat'], my_data['Start_Lon']], [my_data['Cur_Lat'], my_data['Cur_Lon']])
            is_blind = dist_start > BLIND_MODE_DISTANCE
            m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None if is_blind else "OpenStreetMap")
            if is_blind:
                st.warning("🙈 BLIND MODE")
                folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='B').add_to(m)
            
            folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green", weight=5, dash_array='10').add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red', icon='flag')).add_to(m)
            folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue')).add_to(m)
            st_folium(m, width=700, height=500, key="live_map")

        st.components.v1.html(f"<script>setTimeout(()=>window.location.reload(), {REFRESH_RATE * 1000})</script>", height=0)
