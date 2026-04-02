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

# --- 2. DATABASE CONNECTIE ---
@st.cache_resource
def get_ss_worksheet():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        return client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except Exception as e:
        st.error(f"Google Connection Error: {e}")
        return None

def get_db_as_df():
    ws = get_ss_worksheet()
    cols = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]
    if not ws: return pd.DataFrame(columns=cols)
    
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    
    # Als de sheet leeg is of kolommen mist, herstel deze
    if df.empty or "Teamnaam" not in df.columns:
        return pd.DataFrame(columns=cols)

    # Forceer types voor berekeningen
    numeric_cols = ['Score', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Last_Update']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        # Zorg dat alle kolommen aanwezig zijn bij opslaan
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 3. AUTHENTICATIE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam (Admin = THOMASBAAS)").strip().upper()
    
    if st.button("Start / Login"):
        if t_name == "THOMASBAAS":
            st.session_state.role = "admin"
            st.session_state.logged_in = True
            st.rerun()
        elif t_name:
            df = get_db_as_df()
            # Controleer of team al bestaat
            if t_name not in df['Teamnaam'].astype(str).values:
                new_row = {
                    "Teamnaam": t_name, "Leden": "", "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", 
                    "Score": START_PUNTEN, "Last_Update": time.time(), 
                    "Start_Lat": 0.0, "Start_Lon": 0.0, "Cur_Lat": 0.0, "Cur_Lon": 0.0
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            
            st.session_state.team = t_name
            st.session_state.role = "user"
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.warning("Vul een teamnaam in.")

else:
    # --- 4. ADMIN PANEL ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db_as_df()
        st.write("Live Data uit Google Sheets:")
        st.dataframe(df, use_container_width=True)
        
        if not df.empty:
            target = st.selectbox("Selecteer Team:", df['Teamnaam'].unique())
            col1, col2 = st.columns(2)
            with col1:
                msg = st.text_input("Nieuwe Opdracht")
                pts = st.number_input("Punten waard (indicatie)", value=50)
                if st.button("Push Opdracht"):
                    df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}"
                    save_df_to_db(df)
                    st.success("Verzonden!")
            with col2:
                if st.button("Keur Goed & Tel Punten Bij"):
                    alarm_val = str(df.loc[df['Teamnaam'] == target, 'Alarm'].values[0])
                    bonus = float(alarm_val.split('|')[0]) if '|' in alarm_val else 0
                    df.loc[df['Teamnaam'] == target, 'Score'] += bonus
                    df.loc[df['Teamnaam'] == target, 'Alarm'] = "GEEN"
                    save_df_to_db(df)
                    st.rerun()

        if st.button("Logout Admin"):
            st.session_state.logged_in = False
            st.rerun()

    # --- 5. DEELNEMER PANEL ---
    else:
        df = get_db_as_df()
        # Haal data van specifiek team op
        team_mask = df['Teamnaam'] == st.session_state.team
        if not team_mask.any():
            st.error("Team niet gevonden. Log opnieuw in.")
            st.session_state.logged_in = False
            st.button("Terug naar Login")
            st.stop()
            
        my_data = df[team_mask].iloc[0]

        # Score berekening als het spel bezig is
        if my_data['Fase'] == "DROPPING":
            nu = time.time()
            dt = nu - float(my_data['Last_Update'])
            # Alleen score aftrekken als er tijd is verstreken
            if dt > 5: # Elke 5 sec updaten om API te sparen
                afwijking = get_distance_to_line([my_data['Cur_Lat'], my_data['Cur_Lon']], 
                                                [my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS)
                straf = 1 + (afwijking * 3)
                nieuwe_score = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC * straf))
                
                df.loc[team_mask, 'Score'] = nieuwe_score
                df.loc[team_mask, 'Last_Update'] = nu
                save_df_to_db(df)
                # We verversen de lokale variabele voor de UI
                my_data['Score'] = nieuwe_score

        # UI Scherm
        st.title(f"Team: {st.session_state.team}")
        st.header(f"🏆 Score: {int(my_data['Score'])} pnt")

        # Opdracht tonen
        if "|" in str(my_data['Alarm']):
            pts_ind, txt = str(my_data['Alarm']).split("|")
            st.warning(f"🔔 OPDRACHT ({pts_ind} ptn): {txt}")

        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.subheader("Selecteer je startlocatie")
            m = folium.Map(location=[51.2, 4.4], zoom_start=12)
            st_data = st_folium(m, width=700, height=400, key="start_picker")
            
            if st_data and st_data.get("last_clicked"):
                lat, lon = st_data["last_clicked"]["lat"], st_data["last_clicked"]["lng"]
                # Toon een marker waar geklikt is
                folium.Marker([lat, lon]).add_to(m)
                if st.button(f"Bevestig start op {round(lat,4)}, {round(lon,4)}"):
                    df.loc[team_mask, 'Start_Lat'] = lat
                    df.loc[team_mask, 'Start_Lon'] = lon
                    df.loc[team_mask, 'Cur_Lat'] = lat
                    df.loc[team_mask, 'Cur_Lon'] = lon
                    df.loc[team_mask, 'Fase'] = "DROPPING"
                    df.loc[team_mask, 'Last_Update'] = time.time()
                    save_df_to_db(df)
                    st.rerun()
        else:
            # Kaart tijdens dropping
            st.info("Jullie zijn onderweg naar de finish!")
            start = [my_data['Start_Lat'], my_data['Start_Lon']]
            m_play = folium.Map(location=start, zoom_start=14)
            folium.Marker(start, tooltip="Start", icon=folium.Icon(color='blue')).add_to(m_play)
            folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red')).add_to(m_play)
            folium.PolyLine([start, FINISH_COORDS], color="green", dash_array='10').add_to(m_play)
            st_folium(m_play, width=700, height=450)
            
            if st.button("Handmatige GPS Update"):
                st.rerun()

        if st.button("Logout Team"):
            st.session_state.logged_in = False
            st.rerun()
