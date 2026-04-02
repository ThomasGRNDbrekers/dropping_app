import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time
import math
from streamlit_javascript import st_javascript

# --- 1. CONFIG ---
st.set_page_config(page_title="Dropping 2026", layout="wide")
FINISH_COORDS = [51.2435, 4.4452]
START_PUNTEN = 1000.0
TIJD_DOEL_UUR = 1 # TEST MODUS (SNEL)
PUNTEN_PER_SEC = START_PUNTEN / (TIJD_DOEL_UUR * 3600)
REFRESH_RATE = 10 
BLIND_MODE_DISTANCE = 0.002 # 2 meter voor de test

# --- HELPERS ---
def haversine_distance(p1, p2):
    if p1 == [0,0] or p2 == [0,0]: return 0
    lat1, lon1 = p1
    lat2, lon2 = p2
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

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
    cols = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]
    if not ws: return pd.DataFrame(columns=cols)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if df.empty or "Teamnaam" not in df.columns: return pd.DataFrame(columns=cols)
    for c in ['Score', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Last_Update']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws and not df.empty:
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
                new_row = {"Teamnaam": t_name, "Leden": "", "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": START_PUNTEN, "Last_Update": time.time(), "Start_Lat": 0.0, "Start_Lon": 0.0, "Cur_Lat": 0.0, "Cur_Lon": 0.0}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
    # --- ADMIN (THOMAS BAAS) ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        st.components.v1.html(f"<script>setTimeout(function(){{ window.location.reload(); }}, 15000);</script>", height=0)
        df = get_db_as_df()
        
        m_admin = folium.Map(location=FINISH_COORDS, zoom_start=13)
        for i, row in df.iterrows():
            if row['Cur_Lat'] != 0:
                folium.Marker([row['Cur_Lat'], row['Cur_Lon']], tooltip=row['Teamnaam'], icon=folium.Icon(color='blue')).add_to(m_admin)
        st_folium(m_admin, width="100%", height=400, key="admin_map")
        
        st.dataframe(df)
        target = st.selectbox("Team:", df['Teamnaam'].unique())
        msg = st.text_area("Opdracht")
        pts = st.number_input("Punten", value=50)
        if st.button("Push Opdracht"):
            df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}"; save_df_to_db(df); st.rerun()
        if st.button("Goedkeuren"):
            val = str(df.loc[df['Teamnaam'] == target, 'Alarm'].values[0])
            bonus = float(val.split('|')[0]) if '|' in val else 0
            df.loc[df['Teamnaam'] == target, 'Score'] += bonus
            df.loc[df['Teamnaam'] == target, 'Alarm'] = "GEEN"; save_df_to_db(df); st.rerun()

    # --- USER ---
    else:
        # GEAVANCEERDE GPS OPHALEN
        loc_js = st_javascript("""
            new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(
                    (pos) => resolve({lat: pos.coords.latitude, lon: pos.coords.longitude}),
                    (err) => resolve(null),
                    {enableHighAccuracy: true}
                );
            });
        """)

        df = get_db_as_df()
        team_idx = df['Teamnaam'] == st.session_state.team
        my_data = df[team_idx].iloc[0]

        # Update Live Locatie als JS data geeft
        if loc_js and isinstance(loc_js, dict):
            df.loc[team_idx, ['Cur_Lat', 'Cur_Lon']] = [loc_js['lat'], loc_js['lon']]
            # Bereken score direct
            nu = time.time()
            dt = nu - float(my_data['Last_Update'])
            dist_to_line = get_distance_to_line([loc_js['lat'], loc_js['lon']], [my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS)
            dist_from_start = haversine_distance([my_data['Start_Lat'], my_data['Start_Lon']], [loc_js['lat'], loc_js['lon']])
            
            straf = 1 + (dist_to_line * 10) if dist_from_start > BLIND_MODE_DISTANCE else 1
            nieuwe_score = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC * straf))
            
            df.loc[team_idx, 'Score'] = nieuwe_score
            df.loc[team_idx, 'Last_Update'] = nu
            save_df_to_db(df)
            my_data = df[team_idx].iloc[0] # Herlaad lokale data

        # UI
        st.title(f"🏆 {int(my_data['Score'])} pnt")
        st.write(f"📡 GPS Status: {'✅ Verbonden' if loc_js else '❌ Zoeken naar locatie...'}")
        
        if "|" in str(my_data['Alarm']):
            st.error(f"🚨 OPDRACHT: {str(my_data['Alarm']).split('|')[1]}")

        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Kies je startpunt op de kaart.")
            m = folium.Map(location=[51.2, 4.4], zoom_start=12)
            st_data = st_folium(m, width=700, height=400, key="start_map")
            if st_data and st_data.get("last_clicked"):
                if st.button("BEVESTIG START"):
                    c = st_data["last_clicked"]
                    df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon']] = [c['lat'], c['lng'], c['lat'], c['lng']]
                    df.loc[team_idx, 'Fase'] = "DROPPING"; df.loc[team_idx, 'Last_Update'] = time.time()
                    save_df_to_db(df); st.rerun()
        else:
            dist_from_start = haversine_distance([my_data['Start_Lat'], my_data['Start_Lon']], [my_data['Cur_Lat'], my_data['Cur_Lon']])
            is_blind = dist_from_start > BLIND_MODE_DISTANCE
            
            if is_blind:
                st.warning("🙈 BLIND MODE ACTIEF! Gebruik de lijn.")
                m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=18, tiles=None)
                folium.TileLayer(tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr='Blind').add_to(m)
            else:
                st.success(f"Nog {round((BLIND_MODE_DISTANCE - dist_from_start)*1000)}m tot Blind Mode")
                m = folium.Map(location=[my_data['Cur_Lat'], my_data['Cur_Lon']], zoom_start=16)

            folium.PolyLine([[my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS], color="green", weight=4, dash_array='10').add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
            folium.Marker([my_data['Cur_Lat'], my_data['Cur_Lon']], icon=folium.Icon(color='blue', icon='user')).add_to(m)
            st_folium(m, width=700, height=500, key="user_map")

        # Auto-reload timer (JS)
        st.components.v1.html(f"<script>setTimeout(function(){{ window.location.reload(); }}, {REFRESH_RATE * 1000});</script>", height=0)

        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()
