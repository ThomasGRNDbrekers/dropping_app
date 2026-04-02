import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time
import math
from datetime import datetime

# --- 1. CONFIGURATIE & WISKUNDE ---
st.set_page_config(page_title="Dropping 2026 Admin", layout="wide")
FINISH_COORDS = [51.2435, 4.4452]
START_PUNTEN = 1000
TOTALE_TIJD_SECONDEN = 5 * 3600  # 5 uur
PUNTEN_PER_SEC = START_PUNTEN / TOTALE_TIJD_SECONDEN # Basis afname

def get_distance_to_line(p3, p1, p2):
    """Berekent de afstand van huidige locatie (p3) tot de ideale lijn (p1-p2) in km."""
    y3, x3 = p3
    y1, x1 = p1
    y2, x2 = p2
    
    # Vereenvoudigde berekening voor korte afstanden (Euclidisch)
    # Voor echte precisie op grote afstand is Haversine nodig, maar dit volstaat voor een dropping.
    px = x2 - x1
    py = y2 - y1
    norm = px*px + py*py
    if norm == 0: return 0
    u = ((x3 - x1) * px + (y3 - y1) * py) / float(norm)
    if u > 1: u = 1
    elif u < 0: u = 0
    x = x1 + u * px
    y = y1 + u * py
    dx = x - x3
    dy = y - y3
    dist = math.sqrt(dx*dx + dy*dy) * 111 # Omzetten naar km (benadering)
    return dist

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
        st.error(f"Verbindingsfout: {e}")
        return None

def get_db_as_df():
    cols = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]
    ws = get_ss_worksheet()
    if ws is None: return pd.DataFrame(columns=cols)
    data = ws.get_all_records()
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=cols)
    # Zet scores en coordinaten om naar getallen
    for c in ["Score", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- 3. LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip()
    if st.button("Start"):
        if t_name == "THOMASBAAS":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name:
            df = get_db_as_df()
            if t_name not in df['Teamnaam'].values:
                new_row = {"Teamnaam": t_name, "Leden": "", "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", 
                           "Score": START_PUNTEN, "Last_Update": time.time(), 
                           "Start_Lat": 0, "Start_Lon": 0, "Cur_Lat": 0, "Cur_Lon": 0}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
    # --- 4. ADMIN PANEL ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room Master")
        df = get_db_as_df()
        st.dataframe(df)
        
        st.divider()
        target = st.selectbox("Selecteer Team:", df['Teamnaam'].unique())
        col1, col2 = st.columns(2)
        with col1:
            msg = st.text_area("Opdracht Tekst")
            punten_opdracht = st.number_input("Te verdienen punten:", value=50)
        with col2:
            st.write("Acties:")
            if st.button(f"PUSH OPDRACHT NAAR {target}"):
                df.loc[df['Teamnaam'] == target, 'Alarm'] = f"PUNTEN:{punten_opdracht}|{msg}"
                save_df_to_db(df)
                st.success("Opdracht verzonden!")
            
            if st.button(f"KEUR OPDRACHT GOED VOOR {target}"):
                # Zoek de punten uit de 'Alarm' kolom of handmatig
                bonus = st.number_input("Bonus toekennen:", value=punten_opdracht, key="bonus_approve")
                df.loc[df['Teamnaam'] == target, 'Score'] += bonus
                df.loc[df['Teamnaam'] == target, 'Alarm'] = "GEEN"
                save_df_to_db(df)
                st.success(f"{bonus} punten bijgeteld!")
                st.rerun()

    # --- 5. DEELNEMER PANEL ---
    else:
        # Locatie tracking script (vraagt GPS van telefoon)
        st.components.v1.html("""
            <script>
            navigator.geolocation.watchPosition(function(position) {
                window.parent.postMessage({
                    type: 'streamlit:set_component_value',
                    value: {lat: position.coords.latitude, lon: position.coords.longitude}
                }, '*');
            });
            </script>
        """, height=0)

        df = get_db_as_df()
        team_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]
        
        # PUNTEN BEREKENING (Tijd + Afwijking)
        if team_data['Fase'] == "DROPPING":
            nu = time.time()
            verstreken = nu - float(team_data['Last_Update'])
            
            # Bereken afwijking van de lijn
            cur_pos = [team_data['Cur_Lat'], team_data['Cur_Lon']]
            start_pos = [team_data['Start_Lat'], team_data['Start_Lon']]
            afwijking = get_distance_to_line(cur_pos, start_pos, FINISH_COORDS)
            
            # Straf-factor: hoe verder van de lijn, hoe sneller punten weg
            # Elke km afwijking verdubbelt de afnamesnelheid
            straf_factor = 1 + (afwijking * 2) 
            min_punten = verstreken * PUNTEN_PER_SEC * straf_factor
            
            nieuwe_score = max(0, team_data['Score'] - min_punten)
            
            # Update database met nieuwe score en tijdstip
            df.loc[df['Teamnaam'] == st.session_state.team, 'Score'] = nieuwe_score
            df.loc[df['Teamnaam'] == st.session_state.team, 'Last_Update'] = nu
            save_df_to_db(df)
            team_data['Score'] = nieuwe_score # Voor directe weergave

        # UI
        st.title(f"Team: {st.session_state.team}")
        
        # Opdracht check
        if "PUNTEN:" in str(team_data['Alarm']):
            pts = team_data['Alarm'].split("|")[0].replace("PUNTEN:", "")
            inhoud = team_data['Alarm'].split("|")[1]
            st.warning(f"🎁 NIEUWE OPDRACHT: Verdien {pts} punten!")
            st.write(inhoud)
            if st.button("Ik ga aan de slag"):
                # Verander de status zodat ze de kaart weer zien, maar de opdracht blijft staan voor admin
                st.info("Succes! De admin zal de punten toevoegen na goedkeuring.")

        col1, col2 = st.columns(2)
        col1.metric("🏆 Actuele Score", f"{int(team_data['Score'])} / 1000")
        
        if team_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Kies je startlocatie op de kaart.")
            m = folium.Map(location=[51.2, 4.4], zoom_start=11)
            st_data = st_folium(m, width="100%", height=400)
            if st_data and st_data['last_clicked'] and st.button("Start Dropping"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lat'] = st_data['last_clicked']['lat']
                df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lon'] = st_data['last_clicked']['lng']
                df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "DROPPING"
                df.loc[df['Teamnaam'] == st.session_state.team, 'Last_Update'] = time.time()
                save_df_to_db(df); st.rerun()
        else:
            # Kaart met ideale lijn
            start = [team_data['Start_Lat'], team_data['Start_Lon']]
            m = folium.Map(location=start, zoom_start=14)
            folium.PolyLine([start, FINISH_COORDS], color="green", dash_array='10', tooltip="Ideale Lijn").add_to(m)
            folium.Marker(start, tooltip="Start").add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red')).add_to(m)
            st_folium(m, width="100%", height=500)
            st.caption("Auto-refresh elke 30 sec.")
            time.sleep(30)
            st.rerun()
