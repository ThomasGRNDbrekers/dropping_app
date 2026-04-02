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
# TEST-MODUS: We zetten de tijd op 1 uur voor snelle visuele afname
TIJD_DOEL_UUR = 1 
PUNTEN_PER_SEC = START_PUNTEN / (TIJD_DOEL_UUR * 3600)
REFRESH_RATE = 10 

# --- HELPERS ---
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
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- AUTH ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'alarm_acknowledged' not in st.session_state:
    st.session_state.alarm_acknowledged = False

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
    # --- ADMIN ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db_as_df()
        st.dataframe(df)
        target = st.selectbox("Kies Team:", df['Teamnaam'].unique())
        msg = st.text_area("Opdracht")
        pts = st.number_input("Punten", value=50)
        if st.button("Push Opdracht"):
            df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}"
            save_df_to_db(df); st.success("Gezonden!")
        if st.button("Keur Goed & Tel Bij"):
            val = str(df.loc[df['Teamnaam'] == target, 'Alarm'].values[0])
            bonus = float(val.split('|')[0]) if '|' in val else 0
            df.loc[df['Teamnaam'] == target, 'Score'] += bonus
            df.loc[df['Teamnaam'] == target, 'Alarm'] = "GEEN"
            save_df_to_db(df); st.rerun()
        st.components.v1.html(f"<script>setTimeout(function(){{ window.location.reload(); }}, 15000);</script>", height=0)

    # --- USER ---
    else:
        df = get_db_as_df()
        team_idx = df['Teamnaam'] == st.session_state.team
        if not team_idx.any():
            st.session_state.logged_in = False
            st.rerun()
        
        my_data = df[team_idx].iloc[0]

        # AUTO-REFRESH & GPS SCRIPT
        st.components.v1.html(f"""
            <script>
            setTimeout(function(){{ window.location.reload(); }}, {REFRESH_RATE * 1000});
            </script>
        """, height=0)

        # Score berekening
        if my_data['Fase'] == "DROPPING":
            nu = time.time()
            dt = nu - float(my_data['Last_Update'])
            dist = get_distance_to_line([my_data['Cur_Lat'], my_data['Cur_Lon']], [my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS)
            straf = 1 + (dist * 5) # Straffactor verhoogd voor test
            nieuwe_score = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC * straf))
            df.loc[team_idx, 'Score'] = nieuwe_score
            df.loc[team_idx, 'Last_Update'] = nu
            save_df_to_db(df)
            my_data['Score'] = nieuwe_score

        # UI HEADER
        c1, c2 = st.columns([3, 1])
        c1.title(f"Team: {st.session_state.team}")
        c2.write(f"🔄 Sync in {REFRESH_RATE}s")
        st.progress(1.0) # Visuele indicatie van tijd (optioneel)

        # ALARM LOGICA
        if "|" in str(my_data['Alarm']):
            pts, txt = str(my_data['Alarm']).split("|")
            if not st.session_state.alarm_acknowledged:
                st.markdown(f"""
                    <div style="background-color:#ff4b4b;padding:20px;border-radius:10px;text-align:center;animation:blinker 1s linear infinite;cursor:pointer;">
                        <h2 style="color:white;">🚨 NIEUWE OPDRACHT (+{pts} ptn)</h2>
                        <p style="color:white;font-size:18px;">{txt}</p>
                        <p style="color:white;font-size:12px;">(Klik op de knop hieronder om de kaart te zien)</p>
                    </div>
                    <style>@keyframes blinker{{50%{{opacity:0.3;}}}}</style>
                """, unsafe_allow_html=True)
                if st.button("GELEZEN - TOON KAART"):
                    st.session_state.alarm_acknowledged = True
                    st.rerun()
                st.stop()
            else:
                st.info(f"📌 Huidige Opdracht: {txt} (+{pts} ptn)")
                if st.button("Toon Alarm opnieuw"):
                    st.session_state.alarm_acknowledged = False
                    st.rerun()
        else:
            st.session_state.alarm_acknowledged = False

        st.subheader(f"🏆 Score: {int(my_data['Score'])}")

        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Kies je dropping-locatie op de kaart.")
            m = folium.Map(location=[51.2, 4.4], zoom_start=12)
            st_data = st_folium(m, width=700, height=400, key="start_map")
            if st_data and st_data.get("last_clicked"):
                clicked = st_data["last_clicked"]
                if st.button("BEVESTIG STARTPUNT"):
                    df.loc[team_idx, 'Start_Lat'] = clicked['lat']
                    df.loc[team_idx, 'Start_Lon'] = clicked['lng']
                    df.loc[team_idx, 'Cur_Lat'] = clicked['lat']
                    df.loc[team_idx, 'Cur_Lon'] = clicked['lng']
                    df.loc[team_idx, 'Fase'] = "DROPPING"
                    df.loc[team_idx, 'Last_Update'] = time.time()
                    save_df_to_db(df); st.rerun()
        else:
            # KAART MET HUIDIGE LOCATIE (Cur_Lat/Lon)
            start = [my_data['Start_Lat'], my_data['Start_Lon']]
            current = [my_data['Cur_Lat'], my_data['Cur_Lon']]
            
            m = folium.Map(location=current, zoom_start=15)
            folium.Marker(start, tooltip="Start", icon=folium.Icon(color='gray')).add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red', icon='flag')).add_to(m)
            folium.PolyLine([start, FINISH_COORDS], color="green", weight=2, dash_array='5').add_to(m)
            
            # De "Live" locatie van het team
            folium.Marker(current, tooltip="Jullie zijn hier", icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
            # Voeg een cirkel toe om de huidige locatie te benadrukken
            folium.Circle(current, radius=50, color='blue', fill=True, opacity=0.3).add_to(m)
            
            st_folium(m, width=700, height=500)

        if st.button("Log uit"):
            st.session_state.logged_in = False
            st.rerun()
