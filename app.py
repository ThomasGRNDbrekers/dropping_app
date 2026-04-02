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
FINISH_COORDS = [51.2435, 4.4452]
START_PUNTEN = 1000.0
TIJD_DOEL_UUR = 5
PUNTEN_PER_SEC = START_PUNTEN / (TIJD_DOEL_UUR * 3600)
REFRESH_RATE = 30  # Automatische verversing elke 30 seconden

def get_distance_to_line(p_cur, p_start, p_fin):
    try:
        y3, x3 = p_cur
        y1, x1 = p_start
        y2, x2 = p_fin
        px, py = x2-x1, y2-y1
        norm = px*px + py*py
        if norm == 0: return 0
        u = max(0, min(1, ((x3-x1)*px + (y3-y1)*py) / float(norm)))
        dx, dy = (x1 + u*px) - x3, (y1 + u*py) - y3
        return math.sqrt(dx*dx + dy*dy) * 111
    except: return 0

# --- 2. DATABASE ---
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
    numeric_cols = ['Score', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Last_Update']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 3. INLOGGEN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip().upper()
    if st.button("Start"):
        if t_name == "THOMASBAAS":
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
    # --- 4. ADMIN PANEL ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db_as_df()
        st.dataframe(df)
        
        # Auto-refresh voor admin om locaties te zien
        st.empty() 
        time.sleep(1) # Voorkomt dat admin interface te zwaar wordt

        target = st.selectbox("Kies Team:", df['Teamnaam'].unique())
        msg = st.text_area("Nieuwe Opdracht")
        pts = st.number_input("Punten indicatie", value=50)
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Push Opdracht"):
                df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}"
                save_df_to_db(df); st.success("Gezonden!")
        with c2:
            if st.button("Keur Goed & Tel Punten Bij"):
                val = str(df.loc[df['Teamnaam'] == target, 'Alarm'].values[0])
                bonus = float(val.split('|')[0]) if '|' in val else 0
                df.loc[df['Teamnaam'] == target, 'Score'] += bonus
                df.loc[df['Teamnaam'] == target, 'Alarm'] = "GEEN"
                save_df_to_db(df); st.rerun()

    # --- 5. DEELNEMER PANEL ---
    else:
        # JAVASCRIPT VOOR GPS & AUTO-REFRESH
        # Dit haalt de locatie uit de browser en herlaadt de pagina elke X seconden
        st.components.v1.html(f"""
            <script>
            function getLocation() {{
              if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition(function(position) {{
                    console.log("GPS Gevangen");
                }});
              }}
            }}
            getLocation();
            setTimeout(function(){{ window.location.reload(); }}, {REFRESH_RATE * 1000});
            </script>
        """, height=0)

        df = get_db_as_df()
        team_idx = df['Teamnaam'] == st.session_state.team
        my_data = df[team_idx].iloc[0]

        # Automatische Score-afname & Afwijking opslaan
        if my_data['Fase'] == "DROPPING":
            nu = time.time()
            dt = nu - float(my_data['Last_Update'])
            
            # Hier simuleren we de afwijking-straf
            # In een ideale wereld haal je hier de live GPS van de browser binnen, 
            # maar voor nu doen we de berekening op de laatst bekende 'Cur_Lat'
            dist = get_distance_to_line([my_data['Cur_Lat'], my_data['Cur_Lon']], [my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS)
            straf = 1 + (dist * 3) 
            nieuwe_score = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC * straf))
            
            df.loc[team_idx, 'Score'] = nieuwe_score
            df.loc[team_idx, 'Last_Update'] = nu
            save_df_to_db(df)
            my_data['Score'] = nieuwe_score

        # UI
        st.title(f"Team: {st.session_state.team}")
        st.header(f"🏆 Score: {int(my_data['Score'])} pnt")

        # ALARM CHECK (Verschijnt direct bij refresh)
        if "|" in str(my_data['Alarm']):
            pts, txt = str(my_data['Alarm']).split("|")
            st.error(f"🚨 NIEUWE OPDRACHT: {txt}")
            st.info(f"Hiermee verdien je {pts} punten!")
            st.stop() # Blokkeert de kaart totdat Admin het wist (na goedkeuring)

        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.subheader("Selecteer je startlocatie")
            m = folium.Map(location=[51.2, 4.4], zoom_start=12)
            st_data = st_folium(m, width=700, height=400, key="start_map")
            if st_data and st_data.get("last_clicked"):
                clicked = st_data["last_clicked"]
                if st.button("Bevestig Startlocatie"):
                    df.loc[team_idx, 'Start_Lat'] = clicked['lat']
                    df.loc[team_idx, 'Start_Lon'] = clicked['lng']
                    df.loc[team_idx, 'Cur_Lat'] = clicked['lat']
                    df.loc[team_idx, 'Cur_Lon'] = clicked['lng']
                    df.loc[team_idx, 'Fase'] = "DROPPING"
                    df.loc[team_idx, 'Last_Update'] = time.time()
                    save_df_to_db(df); st.rerun()
        else:
            # KAART TONEN
            start = [my_data['Start_Lat'], my_data['Start_Lon']]
            m = folium.Map(location=start, zoom_start=14)
            folium.Marker(start, tooltip="Start").add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
            folium.PolyLine([start, FINISH_COORDS], color="green", dash_array='10').add_to(m)
            st_folium(m, width=700, height=500)
            st.caption(f"Laatste update: {time.strftime('%H:%M:%S')}. Volgende over {REFRESH_RATE} sec.")

        if st.button("Log uit"):
            st.session_state.logged_in = False
            st.rerun()
