import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")

# Verbinding maken met de ingebouwde Streamlit connector
# Deze haalt nu automatisch alles uit de 'Secrets' die je net hebt ingevuld
conn = st.connection("gsheets", type=GSheetsConnection)

def get_db():
    return conn.read(ttl=1) # Leest de sheet die in Secrets staat

def save_to_db(df):
    conn.update(data=df)

# --- 2. HELPER FUNCTIES ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    return R * 2 * asin(sqrt(a))

FINISH_COORDS = (51.2435, 4.4452)

# --- 3. LOGICA ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026 - Login")
    team_naam = st.text_input("Teamnaam").strip()
    leden = st.text_input("Namen van de leden")
    
    if st.button("Start Dropping"):
        if team_naam and (leden or team_naam == "THOMASBAAS"):
            try:
                df = get_db()
                if team_naam == "THOMASBAAS":
                    st.session_state.role = "admin"
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    if team_naam not in df['Teamnaam'].values:
                        new_row = {
                            "Teamnaam": team_naam, "Leden": leden, 
                            "Start_Lat": 0.0, "Start_Lon": 0.0, 
                            "Huidige_Lat": 0.0, "Huidige_Lon": 0.0, 
                            "Score": 0, "Fase": "START", "Alarm": "GEEN"
                        }
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        save_to_db(df)
                    
                    st.session_state.team = team_naam
                    st.session_state.role = "user"
                    st.session_state.logged_in = True
                    st.rerun()
            except Exception as e:
                st.error(f"Verbindingsfout: {e}")
        else:
            st.warning("Vul aub een teamnaam en leden in.")

else:
    # --- ADMIN SECTIE ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db()
        st.dataframe(df)
        
        target_team = st.selectbox("Team voor Alarm", df['Teamnaam'].unique())
        alarm_msg = st.text_input("Bericht")
        if st.button("Verstuur"):
            df.loc[df['Teamnaam'] == target_team, 'Alarm'] = alarm_msg
            save_to_db(df)
            st.success("Verzonden!")
    
    # --- USER SECTIE ---
    else:
        df = get_db()
        my_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]
        st.header(f"Team: {st.session_state.team}")
        
        if my_data['Alarm'] != "GEEN":
            st.error(f"🚨 BERICHT: {my_data['Alarm']}")
            if st.button("Gelezen"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                save_to_db(df)
                st.rerun()

        if my_data['Fase'] == "START":
            if st.button("BEVESTIG STARTPUNT"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "BEZIG"
                save_to_db(df)
                st.rerun()
        else:
            st.metric("Afstand tot Finish", "Berekend...")
            m = folium.Map(location=[51.2194, 4.4025], zoom_start=13)
            folium.Marker(FINISH_COORDS, tooltip="FINISH").add_to(m)
            st_folium(m, width="100%", height=400)
