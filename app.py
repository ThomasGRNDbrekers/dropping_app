import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide", initial_sidebar_state="collapsed")

# Hardcoded credentials om TOML/Secrets fouten te omzeilen
SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "dropping2026",
    "private_key_id": "ff7a191a74fb7123d318f50728b527dcfc09bcc9",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDFPr2jz214sdnZ\naOYDhviCBsAmny1/iZhwEe45+uw25953vRSpUXf5fsLF6OHtZSxNR+IGqANRp0BV\nqgrK7X/ytpFQitfMelMDnKrKfnGqhOpJPGrO52z8+OpKGOQPXMSZmjRd79US3cjB\nm24C8igLh3tLuFL0LbGG/GPN2LpBQ8/7zAp1Xo6x82gMrGCy1PEEQyqm/YrKOBCk\nnJDBPz/CDIvDSzIIXOrwnz9x/P5eqvynFJrO5v9Kye+xH7Os14BtG7Q24GF92GG4\n2FR4F2FCHb5nH6msLCdUX3iYC+6mTmJnPpVEqnQqSmILfuw/+20t9K887nSxiPmh\n0PSdr30tAgMBAAECggEAD//rSfd4Ybm1hONI2IDmisTplHMa3Eqo7PBQvW8bTEc0\niSHIjwUpgPlqwGXdYRBw+UeAhWSJY7fNf2q8FjgRMKWQCzM+rDAWU0eY+rTVMLfi\n5ElsauJOuYTRxmxsoCAONN0owcpDo6njZWxfo7QJEl8Cne1dUerHSNPoyZ4QBQf1\nSFjMs2TZYl16DtwuQmmQ4PYvodaBhqtVGZjFaizGHu3BXjZT2kTojGakQz9qQd+l\nrJSo8iJG+4xt4htt8QQys6AK6t9JSWIVnbfScM79dJY3CqlV/0QAQ2tz7TGlGguN\vmlyWMyyTiH6l+ypLSYMe8TPQSaiaVUQ1/i9SgHrEQKBgQD3gib6kKYLSr1stsVx\nqNMsQiXircrDnZB9bQc/y0zVHBmRl30cOttAhk5ibCozbMgCT1Rz+vi7DEmquR57\ncdLDB8dbtBoOJzeGB7pexqkOXifRwFzipJLvfrQ7y+VPk2kC0TIYsDdAF2syAKaH\YYQVXfeXIx9axwBYrhsKFHnSUQKBgQDMAyEnNSJrIWArf8k9bqMDG0ml7JU6GxKQ\nbneLHITFkpWd9VsDjRPdAQrRJEHfLSvEXHpUHLo7kYWU9S49KkQAgV9Y53mBZS13\nCSkoBYfA3MsUZdxeXcTxL5n0/HSmzTswZzZPOrjCZOxvh0Fmm5dQ6z4jsC06B5Sr\n1VkyHJOKHQKBgQCGTOgro9uFWwvH9rDSSKI1bLsz8cuJM3EYrdV2JzFMnc+98W5g\nqAsaSwYzX6/ScZ9hqXwQ5siabkN20LYak5uiWhEx0Fsm/N6i6oSVMsS+2BZROUjt\nbhGQxLa1j6Cg+kLL1YmSXePM8ignXLT/1skd8vwK1XMJBdxJQkfHw26K0QKBgAYy\piQxygzlI63OoQd7v/oNLyyaRmJQhjzbDkisoh/6dw8ocA5oj8zsBi8aYeHs1mKN\nyK2bfdDnd95xoGj9SrmVNJdX2Ookb8ApCBYOLPSgAI9rFMnNIXmOT6gQr16N55lt\n2UmI6CoHtOMigcsjOPKdYvLknEsiBdM+lQofsh/FAoGBAKfZniAjAVKSqUJ8ivqu\n8qAnnIE6af3T2i7zHmyJPuj6fMlUPuQyuUhjOosxstHFrlDYUP2uuVbQhGxU4Pve\nw1ApbCpYLI6kF2b1M6xGKvT4iIdSWjtIZThoYrDUGITIqtiFUFox+9DICfX8h90z\n8LrBdsW6x75evTZx5kdH/pax\n-----END PRIVATE KEY-----\n",
    "client_email": "dropping2026@dropping2026.iam.gserviceaccount.com",
    "token_uri": "https://oauth2.googleapis.com/token",
}

# Verbinding maken via gspread
@st.cache_resource
def get_ss_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI")
    return sh.worksheet("Data")

try:
    ws = get_ss_worksheet()
except Exception as e:
    st.error(f"⚠️ Kan geen verbinding maken met Google Sheets: {e}")
    st.stop()

# --- 2. DATA FUNCTIES ---
def get_db():
    # Haalt alle rijen op en zet ze in een DataFrame
    data = ws.get_all_records()
    return pd.DataFrame(data)

def save_to_db(df):
    # gspread verwacht een lijst van lijsten inclusief headers
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

# --- 3. LOGICA & HELPER FUNCTIES ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    return R * 2 * asin(sqrt(a))

FINISH_COORDS = (51.2435, 4.4452) # JC Bouckenborgh

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- UI ---
if not st.session_state.logged_in:
    st.title("📍 Dropping 2026 - Login")
    team_naam = st.text_input("Teamnaam (bijv. 'De Bosuilen')").strip()
    leden = st.text_input("Namen van de leden")
    
    if st.button("Start Dropping"):
        if team_naam and (leden or team_naam == "THOMASBAAS"):
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
        else:
            st.warning("Vul aub een teamnaam en leden in.")

else:
    # --- ADMIN SECTIE ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db()
        st.write("### Status van alle teams")
        st.dataframe(df)
        
        st.divider()
        target_team = st.selectbox("Selecteer Team voor Alarm", df['Teamnaam'].unique())
        alarm_msg = st.text_input("Bericht (bijv: 'Loop 100m terug!')")
        
        if st.button("Verstuur naar team"):
            df.loc[df['Teamnaam'] == target_team, 'Alarm'] = alarm_msg
            save_to_db(df)
            st.success("Alarm verzonden!")

    # --- TEAM SECTIE ---
    else:
        df = get_db()
        # Data ophalen voor specifiek team
        my_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]
        
        st.header(f"Team: {st.session_state.team}")
        
        # Alarm melding
        if my_data['Alarm'] != "GEEN":
            st.error(f"🚨 BOODSCHAP VAN DE LEIDING: \n\n {my_data['Alarm']}")
            if st.button("Gelezen en begrepen"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                save_to_db(df)
                st.rerun()

        if my_data['Fase'] == "START":
            st.info("Welkom bij de dropping! Druk op de knop zodra je op je startpunt bent.")
            if st.button("BEVESTIG STARTPUNT"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "BEZIG"
                save_to_db(df)
                st.rerun()
        else:
            # Afstand berekenen (fictief startpunt voor demo, vervang door GPS indien gewenst)
            dist = haversine(51.21, 4.41, FINISH_COORDS[0], FINISH_COORDS[1])
            st.metric("Afstand tot JC Bouckenborgh", f"{round(dist, 2)} km")
            
            # Kaart
            m = folium.Map(location=[51.2194, 4.4025], zoom_start=13)
            folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red', icon='flag')).add_to(m)
            
            st_folium(m, width="100%", height=400)
            
            if st.button("Locatie updaten"):
                st.toast("Locatie doorgegeven!")
