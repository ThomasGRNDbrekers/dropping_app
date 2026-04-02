import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")
FINISH_COORDS = [51.2435, 4.4452]

@st.cache_resource
def get_ss_worksheet():
    try:
        # Haal de gegevens uit Streamlit Secrets
        info = dict(st.secrets["gcp_service_account"])
        
        # Zorg dat de enters in de private key goed gelezen worden
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(
            info, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        # Gebruik je specifieke Sheet ID
        return client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except Exception as e:
        st.error(f"Verbindingsfout: {e}")
        return None

def get_db_as_df():
    # Altijd terugvallen op de juiste kolommen als er iets misgaat
    cols = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Timer", "Start_Lat", "Start_Lon"]
    ws = get_ss_worksheet()
    if ws is None:
        return pd.DataFrame(columns=cols)
    try:
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame(columns=cols)
    except:
        return pd.DataFrame(columns=cols)

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        # Alles naar strings converteren om JSON-fouten in de API te voorkomen
        data_to_save = [df.columns.values.tolist()] + df.values.astype(str).tolist()
        ws.clear()
        ws.update(data_to_save)

# --- 2. AUTHENTICATIE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip()
    l_names = st.text_input("Namen Leden")
    
    if st.button("Start"):
        if t_name == "THOMASBAAS":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name and l_names:
            df = get_db_as_df()
            # Controleer of kolom 'Teamnaam' bestaat (voorkomt KeyError)
            if 'Teamnaam' in df.columns:
                if t_name not in df['Teamnaam'].astype(str).values:
                    new_row = {
                        "Teamnaam": t_name, "Leden": l_names, "Fase": "LOCATIE_KIEZEN", 
                        "Alarm": "GEEN", "Score": "0", "Timer": "01:00:00", 
                        "Start_Lat": "0.0", "Start_Lon": "0.0"
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    save_df_to_db(df)
                st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
                st.rerun()
            else:
                st.error("De Google Sheet kolom 'Teamnaam' is niet gevonden. Controleer de eerste rij van je sheet!")
        else:
            st.warning("Vul aub beide velden in.")

else:
    # --- 3. ADMIN PANEL ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db_as_df()
        st.dataframe(df, use_container_width=True)
        
        if not df.empty and 'Teamnaam' in df.columns:
            target = st.selectbox("Team aanpassen:", df['Teamnaam'].unique())
            c1, c2, c3 = st.columns(3)
            with c1:
                msg = st.text_input("Nieuwe Opdracht")
                if st.button("Verstuur"):
                    df.loc[df['Teamnaam'] == target, 'Alarm'] = msg
                    save_df_to_db(df); st.success("Gepusht!")
            with c2:
                new_t = st.text_input("Timer (HH:MM:SS)")
                if st.button("Zet Tijd"):
                    df.loc[df['Teamnaam'] == target, 'Timer'] = new_t
                    save_df_to_db(df); st.success("Tijd aangepast!")
            with c3:
                new_s = st.number_input("Punten", value=0)
                if st.button("Zet Score"):
                    df.loc[df['Teamnaam'] == target, 'Score'] = str(new_s)
                    save_df_to_db(df); st.success("Score aangepast!")
        
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

    # --- 4. TEAM PANEL ---
    else:
        # Auto-refresh
        st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", height=0)
        df = get_db_as_df()
        
        if 'Teamnaam' in df.columns:
            my_team_df = df[df['Teamnaam'].astype(str) == st.session_state.team]
            if not my_team_df.empty:
                my_data = my_team_df.iloc[0]
                
                if str(my_data['Alarm']) != "GEEN":
                    st.error(f"🚨 **OPDRACHT:** {my_data['Alarm']}")
                    if st.button("Gelezen"):
                        df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                        save_df_to_db(df); st.rerun()
                    st.stop()

                st.title(f"Team: {st.session_state.team}")
                col1, col2 = st.columns(2)
                col1.metric("Tijd over", my_data['Timer'])
                col2.metric("Score", f"{my_data['Score']} Pnt")

                if my_data['Fase'] == "LOCATIE_KIEZEN":
                    st.info("Kies je dropping-locatie op de kaart:")
                    m = folium.Map(location=[51.2, 4.4], zoom_start=11)
                    st_data = st_folium(m, width="100%", height=400)
                    if st_data and st_data['last_clicked']:
                        lat, lon = st_data['last_clicked']['lat'], st_data['last_clicked']['lng']
                        if st.button("Bevestig Locatie"):
                            df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lat'] = str(lat)
                            df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lon'] = str(lon)
                            df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "DROPPING"
                            save_df_to_db(df); st.rerun()
                else:
                    start = [float(my_data['Start_Lat']), float(my_data['Start_Lon'])]
                    m = folium.Map(location=start, zoom_start=14)
                    folium.Marker(start, tooltip="Start").add_to(m)
                    folium.Marker(FINISH_COORDS, tooltip="Finish", icon=folium.Icon(color='red')).add_to(m)
                    folium.PolyLine([start, FINISH_COORDS], color="blue", dash_array='10').add_to(m)
                    st_folium(m, width="100%", height=500)
            
        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()
