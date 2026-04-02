import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- 1. CONFIGURATIE & OPDRACHTEN ---
st.set_page_config(page_title="Dropping 2026 Admin", layout="wide")
FINISH_COORDS = [51.2435, 4.4452]

# Hier kun je al je opdrachten vooraf definiëren
OPDRACHTEN_LIJST = {
    "Geen": {"tekst": "GEEN", "tijd": None, "punten": 0},
    "📸 Foto bij Kerktoren": {"tekst": "Maak een creatieve groepsfoto bij de dichtstbijzijnde kerktoren!", "tijd": "-00:10:00", "punten": 10},
    "🧩 Het Raadsel": {"tekst": "Wat wordt natter naarmate het meer droogt? (Antwoord: Handdoek)", "tijd": "-00:05:00", "punten": 5},
    "🏃 Snelheidsloop": {"tekst": "Ren 500 meter in de richting van de finish!", "tijd": "-00:15:00", "punten": 20},
    "🚨 Terug naar start": {"tekst": "Helaas, loop 200 meter terug voor de volgende aanwijzing.", "tijd": "+00:05:00", "punten": 0}
}

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
    cols = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Timer", "Start_Lat", "Start_Lon"]
    ws = get_ss_worksheet()
    if ws is None: return pd.DataFrame(columns=cols)
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=cols)
        df['Start_Lat'] = pd.to_numeric(df['Start_Lat'], errors='coerce').fillna(0.0)
        df['Start_Lon'] = pd.to_numeric(df['Start_Lon'], errors='coerce').fillna(0.0)
        df['Score'] = pd.to_numeric(df['Score'], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=cols)

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
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
            if t_name not in df['Teamnaam'].astype(str).values:
                new_row = {"Teamnaam": t_name, "Leden": l_names, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": 0, "Timer": "01:00:00", "Start_Lat": 0.0, "Start_Lon": 0.0}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
    # --- 3. ADMIN PANEL (CONTROL ROOM) ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room Master")
        df = get_db_as_df()
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        st.subheader("🚀 Opdracht & Punten Pushen")
        
        col_t, col_o = st.columns([1, 2])
        with col_t:
            target = st.selectbox("Kies Team:", df['Teamnaam'].unique())
        with col_o:
            opdracht_naam = st.selectbox("Kies Opdracht uit lijst:", list(OPDRACHTEN_LIJST.keys()))
        
        sel = OPDRACHTEN_LIJST[opdracht_naam]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            final_msg = st.text_area("Bericht tekst:", value=sel['tekst'], height=100)
        with c2:
            current_timer = df.loc[df['Teamnaam'] == target, 'Timer'].values[0]
            new_timer = st.text_input("Nieuwe Timer (HH:MM:SS):", value=current_timer)
            st.caption(f"Suggestie: {sel['tijd'] if sel['tijd'] else 'Geen wijziging'}")
        with c3:
            current_score = int(df.loc[df['Teamnaam'] == target, 'Score'].values[0])
            new_score = st.number_input("Nieuwe Totaalscore:", value=current_score + sel['punten'])

        if st.button(f"PUSH ALLES NAAR {target}", type="primary"):
            df.loc[df['Teamnaam'] == target, 'Alarm'] = final_msg
            df.loc[df['Teamnaam'] == target, 'Timer'] = new_timer
            df.loc[df['Teamnaam'] == target, 'Score'] = new_score
            save_df_to_db(df)
            st.success(f"✅ Opdracht, tijd en score gepusht naar {target}!")
            st.rerun()

        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()

    # --- 4. TEAM PANEL ---
    else:
        st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", height=0)
        df = get_db_as_df()
        my_team = df[df['Teamnaam'] == st.session_state.team]
        
        if not my_team.empty:
            my_data = my_team.iloc[0]
            if str(my_data['Alarm']) != "GEEN":
                st.error(f"🚨 **NIEUWE OPDRACHT:** \n\n {my_data['Alarm']}")
                if st.button("GELEZEN & START"):
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                    save_df_to_db(df); st.rerun()
                st.stop()

            st.title(f"Team: {st.session_state.team}")
            c_a, c_b = st.columns(2)
            c_a.metric("⏳ Tijd over", my_data['Timer'])
            c_b.metric("🏆 Score", f"{my_data['Score']} Pnt")

            if my_data['Fase'] == "LOCATIE_KIEZEN":
                st.info("Kies je startlocatie op de kaart:")
                m = folium.Map(location=[51.2, 4.4], zoom_start=11)
                st_data = st_folium(m, width="100%", height=400)
                if st_data and st_data['last_clicked']:
                    if st.button("Bevestig Locatie"):
                        df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lat'] = st_data['last_clicked']['lat']
                        df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lon'] = st_data['last_clicked']['lng']
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
