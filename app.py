import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt
import time

# --- 1. CONFIGURATIE & VERBINDING ---
st.set_page_config(page_title="Dropping 2026", layout="wide")

# De credentials direct in de code om TOML-fouten te vermijden
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
def get_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    client = gspread.authorize(creds)
    # Gebruik je Sheet ID (uit de URL van je browser)
    sh = client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI")
    return sh.worksheet("Data")

ws = get_worksheet()

# --- 2. DATA FUNCTIES ---
def get_db():
    data = ws.get_all_records()
    return pd.DataFrame(data)

def save_to_db(df):
    # Update de hele sheet (headers + data)
    ws.update([df.columns.values.tolist()] + df.values.tolist())

# --- 3. HELPER FUNCTIES ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    return R * 2 * asin(sqrt(a))

# --- 4. LOGICA ---
FINISH_COORDS = (51.2435, 4.4452) # JC Bouckenborgh

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026 - Inloggen")
    team_naam = st.text_input("Teamnaam").strip()
    leden = st.text_input("Namen van de leden (komma gescheiden)")
    
    if st.button("Start Dropping"):
        if team_naam and leden:
            df = get_db()
            if team_naam == "THOMASBAAS":
                st.session_state.role = "admin"
                st.session_state.logged_in = True
                st.rerun()
            else:
                # Check of team al bestaat, anders toevoegen
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
            st.warning("Vul aub alle velden in.")

else:
    # --- ADMIN SECTIE ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db()
        st.dataframe(df)
        
        target_team = st.selectbox("Kies Team", df['Teamnaam'].unique())
        alarm_msg = st.text_input("Nieuw Alarmbericht")
        
        if st.button("Verstuur Alarm"):
            df.loc[df['Teamnaam'] == target_team, 'Alarm'] = alarm_msg
            save_to_db(df)
            st.success(f"Alarm verstuurd naar {target_team}")

    # --- USER SECTIE ---
    else:
        df = get_db()
        my_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]
        
        st.title(f"🚩 Team: {st.session_state.team}")
        
        # Check op Alarms (Push notificatie simulatie)
        if my_data['Alarm'] != "GEEN":
            st.error(f"🚨 ALERT: {my_data['Alarm']}")
            if st.button("Ik heb het begrepen"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                save_to_db(df)
                st.rerun()

        # Fase 1: Startlocatie bepalen
        if my_data['Fase'] == "START":
            st.info("Druk op de knop zodra je gedropt bent!")
            if st.button("IK BEN GEDROPT - Leg mijn startpunt vast"):
                # Hier zou je JS kunnen gebruiken voor echte locatie, we simuleren nu even
                # Voor de demo vragen we de gebruiker om toestemming via de browser later
                st.success("Locatie vastgelegd! (In een echte omgeving pakken we nu je GPS)")
                df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "BEZIG"
                save_to_db(df)
                st.rerun()

        # Fase 2: De Kaart
        else:
            dist = haversine(51.2, 4.4, FINISH_COORDS[0], FINISH_COORDS[1]) # Demo afstand
            st.metric("Afstand tot JC Bouckenborgh", f"{round(dist, 2)} km")
            
            m = folium.Map(location=[51.2194, 4.4025], zoom_start=12)
            folium.Marker(FINISH_COORDS, tooltip="FINISH: JC Bouckenborgh", icon=folium.Icon(color='red')).add_to(m)
            # Voeg hier de lijn toe van start naar finish als de coördinaten er zijn
            st_folium(m, width=700)
            
            if st.button("Update mijn locatie"):
                st.toast("Locatie bijgewerkt in de database!")
