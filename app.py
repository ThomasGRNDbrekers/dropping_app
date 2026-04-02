import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")

# De key als één doorlopende tekst (zonder handmatige \n tekens)
RAW_KEY_CLEAN = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCmjmyJdooPgSK4qzqBm2BXvjvwPV2Yuh5tOQbKlGuqt1eJrz43QscbkuFBvBNMQHs9z7nyys9HRgZBpsd9KaaIeNVX5fmK2u509EI5Uy2TpEPdpnkguqX1Bq3DMVbSZtSoZfpwLg+tpqyiMtr5PH6e36bKVagmROzSjY8UerA+khIDr4Olv9ZJjGivB/1yxoSiSSZvmcQyc0KkEdPH4++QH9H8toK6qtHuBns2dEU2DThK/r6GObtSr+b9QwENUG69lrnJMeGupFJku2OSuDlAoj7pTnNUG/WPJG8HYV7wLP2er5g7/osuYk/aLQSB877P+acNSj5FU1vQ1wI349yRAgMBAAECggEABSmdOuIMG7irmjiBfN6zbOjSPAs05VzggE9wEtOopi8eZR/D0Ivu9r914LcbDIYjo8n2aCyJ4fpNS5fnL02dEjYXm8y+sEOCuGiRTGxT+XNyIJLORpnOdtK1DFuxRp6GGS2nBnbhCMeFqpXjtG2/+X3ycitXRc9lXU3iuVZns9q/qAx5NWZAzTd1C7f7lQu+fM4DJSoozEJxwvjUChGDiSsgsJuc++afa83eUQp1v/oJ4i6F2Lp15v7ICeK00DU2GNu4NiOXkIsc7OtetNdE9xrHxxVBuk262zH1FN/ocwKP69Jw9+/YbJwx93h5AYkVxlhqE8Dct7Eeb8Z9V/GAmQKBgQDYxF3vKHgh0iYeLXa5wXGc9JEVJonZH+Yas2yFQuY66th9IpiYFUvczCzY5M3Of7ROErnH98E5Sj0RvexlpR7ROahVPfS7asB2wLNWfO6k6rLl3otTb+Wftb4DsI1z3wzqr7/rz79Nl/6n3Dw94UgfYqfuRLAZoqECamUh1YpVSQKBgQDEs5sVAGlwIl1LadMCsVZ53/iAyyB2pzZW2MzgY25DN7pwmDtMxNTr+SfM5Qfj3ziflh7+v3R5eBDoqlkmU6IZg2Mg5zKJsi9hlVgTXBRuFnugU0SzOHK+RMuQrcz+T73U+eLUb0uHkY3JFWd6DUZnJpiywrfbUJj4jI9yByj1CQKBgCvRhiuSQraThKEVD6r9L7pKtglQgQ0jJaDAJG/L1j6SurCRDcewhmVb4LT3i6LyrcAaiPOjYavzFeVAP0lM163zudOBcrdwHPfkfFw/ZP5xcziEhCWZnuRFP69lTF0UVEcdfP6yrkkBdOV01Z/gaUjoF92xy9iY4edPDLi5ovE4BAoGBAMOBCFjdae7MGRJFgjcg76R+2c2ZFxEXrUiwfyFfck5Y63PRus7YrBBGOirKUQdJ7Euht/jXbfr1PUkjVyxi37CgCDzBzldRxQoml73WPXAV5JY7bQL8zf8S/Yk1VZRGyZUPMUaXv+hk4RnFrm1/GESZ9hdmtbrD5ubTPhfFyg2RAoGAaLqVkPG13Z0bBVyUnSKjHHxcPrLHziwGdAoETO9MfVxVWyDcIW7xXcO1myAP2WJJSi5tdzqcwcyEAr94faCVgX1WbjYqkhjl0TzkpGyj0QcJuzRrOJPCggaAJrHokPyKvRklGI/a6pc4k5Jb0bFNAavRu0PHwhFJmlcLGe8eEDk="

def get_google_key():
    # Bouw de key handmatig op met keiharde regeleinden
    key = "-----BEGIN PRIVATE KEY-----\n"
    # We knippen de lange string in stukjes van 64 tekens (standaard PEM formaat)
    for i in range(0, len(RAW_KEY_CLEAN), 64):
        key += RAW_KEY_CLEAN[i:i+64] + "\n"
    key += "-----END PRIVATE KEY-----\n"
    return key

FINISH_COORDS = [51.2435, 4.4452]

@st.cache_resource
def get_ss_worksheet():
    info = {
        "type": "service_account",
        "project_id": "dropping2026",
        "private_key": get_google_key(),
        "client_email": "droping-final@dropping2026.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds).open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").worksheet("Data")

def get_db():
    return pd.DataFrame(get_ss_worksheet().get_all_records())

def save_to_db(df):
    ws = get_ss_worksheet()
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

# --- 2. AUTH ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip()
    l_names = st.text_input("Leden")
    if st.button("Start"):
        if t_name == "THOMASBAAS":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name and l_names:
            df = get_db()
            if t_name not in df['Teamnaam'].values:
                new = {"Teamnaam": t_name, "Leden": l_names, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": 0, "Timer": "00:00", "Start_Lat": 0.0, "Start_Lon": 0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True).fillna(0)
                save_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
    # --- 3. ADMIN PANEL ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db()
        st.dataframe(df)
        
        target = st.selectbox("Kies Team", df['Teamnaam'].unique())
        c1, c2, c3 = st.columns(3)
        with c1:
            msg = st.text_input("Push Opdracht")
            if st.button("Stuur"):
                df.loc[df['Teamnaam'] == target, 'Alarm'] = msg
                save_to_db(df); st.success("Gepusht!")
        with c2:
            new_time = st.text_input("Timer (bijv. 45:00)")
            if st.button("Update Tijd"):
                df.loc[df['Teamnaam'] == target, 'Timer'] = new_time
                save_to_db(df); st.success("Tijd aangepast!")
        with c3:
            new_pts = st.number_input("Punten", value=0)
            if st.button("Update Score"):
                df.loc[df['Teamnaam'] == target, 'Score'] = new_pts
                save_to_db(df); st.success("Score aangepast!")
        
        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()

    # --- 4. TEAM DASHBOARD ---
    else:
        # Auto-refresh (15 sec)
        st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", height=0)
        
        df = get_db()
        my_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]

        if my_data['Alarm'] != "GEEN":
            st.error(f"⚠️ **OPDRACHT:** {my_data['Alarm']}")
            if st.button("Gelezen"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                save_to_db(df); st.rerun()

        st.title(f"Team: {st.session_state.team}")
        col1, col2 = st.columns(2)
        col1.metric("Timer", my_data['Timer'])
        col2.metric("Score", f"{my_data['Score']} Pnt")

        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Waar denken jullie dat je bent? Klik op de kaart!")
            m = folium.Map(location=[51.0, 4.0], zoom_start=2) 
            st_data = st_folium(m, width=700, height=400)
            if st_data and st_data['last_clicked']:
                lat, lon = st_data['last_clicked']['lat'], st_data['last_clicked']['lng']
                if st.button(f"Bevestig dit startpunt"):
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lat'] = lat
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lon'] = lon
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "DROPPING"
                    save_to_db(df); st.rerun()
        else:
            start_coords = [my_data['Start_Lat'], my_data['Start_Lon']]
            m = folium.Map(location=start_coords, zoom_start=13)
            folium.Marker(start_coords, tooltip="Start").add_to(m)
            folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red')).add_to(m)
            folium.PolyLine([start_coords, FINISH_COORDS], color="blue", dash_array='10').add_to(m)
            st_folium(m, width=700, height=500)

        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()
