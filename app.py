import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import re

# --- 1. CONFIGURATIE & MAP SETTINGS ---
st.set_page_config(page_title="Dropping 2026 - Control Center", layout="wide")
FINISH_COORDS = [51.2435, 4.4452]

def fix_key(key):
    """Schoont de sleutel extreem grondig op voor Google Auth."""
    if not key:
        return ""
    # Haal headers eraf
    core = key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
    # Verwijder ALLE tekens die NIET base64 zijn (hou alleen A-Z, a-z, 0-9, +, /)
    clean_core = re.sub(r'[^A-Za-z0-9+/]', '', core)
    # Voeg correcte padding toe (= tekens aan het einde)
    missing_padding = len(clean_core) % 4
    if missing_padding:
        clean_core += '=' * (4 - missing_padding)
    # Bouw PEM formaat opnieuw op
    formatted = "-----BEGIN PRIVATE KEY-----\n"
    for i in range(0, len(clean_core), 64):
        formatted += clean_core[i:i+64] + "\n"
    formatted += "-----END PRIVATE KEY-----\n"
    return formatted

@st.cache_resource
def get_ss_worksheet():
    try:
        # Haal info uit Streamlit Secrets
        secret_info = dict(st.secrets["gcp_service_account"])
        secret_info["private_key"] = fix_key(secret_info["private_key"])
        
        creds = Credentials.from_service_account_info(
            secret_info, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        # We openen specifiek de sheet met de ID die je gaf
        return client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except Exception as e:
        st.error(f"Verbindingsfout met Google: {e}")
        return None

def get_db_as_df():
    default_df = pd.DataFrame(columns=["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Timer", "Start_Lat", "Start_Lon"])
    ws = get_ss_worksheet()
    if ws is None:
        return default_df
    try:
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else default_df
    except:
        return default_df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        try:
            ws.clear()
            # Headers + Data wegschrijven
            ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())
        except Exception as e:
            st.error(f"Fout bij opslaan naar Google Sheets: {e}")

# --- 2. AUTHENTICATIE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip()
    l_names = st.text_input("Namen Leden")
    
    if st.button("Inloggen / Starten"):
        if t_name == "THOMASBAAS":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name and l_names:
            df = get_db_as_df()
            # Registreer nieuw team als het nog niet bestaat
            if t_name not in df['Teamnaam'].astype(str).values:
                new_row = {
                    "Teamnaam": t_name, "Leden": l_names, "Fase": "LOCATIE_KIEZEN", 
                    "Alarm": "GEEN", "Score": 0, "Timer": "01:00:00", 
                    "Start_Lat": 0.0, "Start_Lon": 0.0
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
        else:
            st.warning("Vul aub beide velden in.")
else:
    # --- 3. ADMIN PANEL (CONTROL ROOM) ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room (Master)")
        df = get_db_as_df()
        st.write("### Live Overzicht")
        st.dataframe(df, use_container_width=True)
        
        if not df.empty:
            st.divider()
            target = st.selectbox("Selecteer Team voor acties:", df['Teamnaam'].unique())
            c1, c2, c3 = st.columns(3)
            with c1:
                preset = st.selectbox("Opdracht versturen:", ["Eigen tekst...", "🚨 BACK ON TRACK!", "📸 FOTO OPDRACHT", "🧩 RAADSEL"])
                custom = st.text_input("Vrij bericht:")
                msg = custom if custom else preset
                if st.button("Push naar Team"):
                    df.loc[df['Teamnaam'] == target, 'Alarm'] = msg
                    save_df_to_db(df); st.success("Gepusht!")
            with c2:
                new_t = st.text_input("Update Timer (bijv. 00:45:00)")
                if st.button("Bevestig Tijd"):
                    df.loc[df['Teamnaam'] == target, 'Timer'] = new_t
                    save_df_to_db(df); st.success("Klok aangepast!")
            with c3:
                new_s = st.number_input("Update Score", value=0)
                if st.button("Bevestig Punten"):
                    df.loc[df['Teamnaam'] == target, 'Score'] = new_s
                    save_df_to_db(df); st.success("Score bijgewerkt!")
        
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

    # --- 4. TEAM DASHBOARD ---
    else:
        # Auto-refresh elke 15 seconden voor de deelnemers
        st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", height=0)
        
        df = get_db_as_df()
        # Zoek data van dit specifieke team
        team_rows = df[df['Teamnaam'].astype(str) == st.session_state.team]
        
        if not team_rows.empty:
            my_data = team_rows.iloc[0]
            
            # Popup bij Alarm/Opdracht
            if str(my_data['Alarm']) != "GEEN":
                st.error(f"🚨 **NIEUWE OPDRACHT:** {my_data['Alarm']}")
                if st.button("Gelezen & Uitvoeren"):
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                    save_df_to_db(df); st.rerun()
                st.stop()

            st.title(f"Team: {st.session_state.team}")
            col1, col2 = st.columns(2)
            col1.metric("⏳ Tijd over", my_data['Timer'])
            col2.metric("🏆 Score", f"{my_data['Score']} Pnt")

            # FASE 1: Startlocatie doorgeven
            if my_data['Fase'] == "LOCATIE_KIEZEN":
                st.subheader("Geef jullie dropping-locatie door")
                m = folium.Map(location=[51.2, 4.4], zoom_start=11)
                st_data = st_folium(m, width="100%", height=400)
                if st_data and st_data['last_clicked']:
                    lat, lon = st_data['last_clicked']['lat'], st_data['last_clicked']['lng']
                    if st.button(f"Bevestig deze locatie"):
                        df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lat'] = lat
                        df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lon'] = lon
                        df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "DROPPING"
                        save_df_to_db(df); st.rerun()
            
            # FASE 2: De Route naar de Finish
            else:
                st.subheader("🗺️ Jullie Koers")
                start = [float(my_data['Start_Lat']), float(my_data['Start_Lon'])]
                m = folium.Map(location=start, zoom_start=14)
                folium.Marker(start, tooltip="Jullie Start").add_to(m)
                folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red', icon='flag')).add_to(m)
                # De Hulplijn
                folium.PolyLine([start, FINISH_COORDS], color="blue", weight=3, opacity=0.7, dash_array='10').add_to(m)
                st_folium(m, width="100%", height=500)
        else:
            st.error("Teamgegevens niet gevonden. Log opnieuw in.")

        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()
