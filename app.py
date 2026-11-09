import os
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from supabase import create_client, Client
import matplotlib.pyplot as plt

# ----------------------------------------------------
# 1. CONFIGURAZIONE PAGINA E BRANDING
# ----------------------------------------------------
page_icon = "logo.png" if os.path.exists("logo.png") else "🏨"

st.set_page_config(
    page_title="Al Badiya Management",
    page_icon=page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

import base64

# Imposta il logo come icona ufficiale per la schermata Home di iPhone/Android
def setup_home_screen_icon(image_path="logo.png"):
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            encoded_img = base64.b64encode(f.read()).decode("utf-8")
        st.markdown(
            f"""
            <link rel="apple-touch-icon" href="data:image/png;base64,{encoded_img}">
            <link rel="apple-touch-icon-precomposed" href="data:image/png;base64,{encoded_img}">
            <link rel="shortcut icon" href="data:image/png;base64,{encoded_img}">
            """,
            unsafe_allow_html=True
        )

setup_home_screen_icon("logo.png")

# Visualizzazione Logo Al Badiya nella barra laterale
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)

st.sidebar.title("Al Badiya")
st.sidebar.caption("Revenue Management & Gestione Struttura")

# ----------------------------------------------------
# 2. CONNESSIONE SUPABASE
# ----------------------------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", "hhttps://rkicgvfzoptideeaylog.supabase.co"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", "tsb_publishable_pWP_qrEggQdTlbqeNiX1Tg_KsrHkyeg"))

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = get_supabase_client()
except Exception as e:
    st.sidebar.error(f"Errore connessione DB: {e}")
    supabase = None

# ----------------------------------------------------
# 3. FUNZIONI DATI (TUTTO 100% IN EURO ORIGINALE)
# ----------------------------------------------------
def load_bookings():
    if not supabase:
        return pd.DataFrame()
    try:
        res = supabase.table("bookings").select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame()

        # Riconoscimento colonna data check-in per ordinamento cronologico
        for col in df.columns:
            c_low = col.lower()
            if any(k in c_low for k in ["check_in", "checkin", "data_in", "arrivo", "start"]):
                df["_check_in_dt"] = pd.to_datetime(df[col], errors="coerce").dt.date
                break

        # Riconoscimento colonna del prezzo/totale (valore puro in Euro)
        price_col_found = None
        for col in df.columns:
            c_low = col.lower()
            if any(k in c_low for k in ["total_price", "price", "prezzo", "totale", "importo", "ricavo", "tariffa"]):
                price_col_found = col
                break

        if price_col_found:
            df["Prezzo (€)"] = pd.to_numeric(df[price_col_found], errors="coerce").fillna(0.0).round(2)
        else:
            df["Prezzo (€)"] = 0.0

        return df
    except Exception as e:
        st.error(f"Errore caricamento prenotazioni: {e}")
        return pd.DataFrame()

def load_bills():
    if not supabase:
        return pd.DataFrame()
    try:
        res = supabase.table("bills").select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame()

        # Riconoscimento colonna importo spesa (valore puro in Euro)
        amount_col_found = None
        for col in df.columns:
            c_low = col.lower()
            if any(k in c_low for k in ["amount", "importo", "spesa", "costo", "total", "price"]):
                amount_col_found = col
                break

        if amount_col_found:
            df["Importo (€)"] = pd.to_numeric(df[amount_col_found], errors="coerce").fillna(0.0).round(2)
        else:
            df["Importo (€)"] = 0.0

        return df
    except Exception as e:
        st.error(f"Errore caricamento spese: {e}")
        return pd.DataFrame()

def get_seasonality_factor(dt: date):
    # Capodanno (28 Dicembre - 3 Gennaio)
    if (dt.month == 12 and dt.day >= 28) or (dt.month == 1 and dt.day <= 3):
        return 1.60, "Capodanno (+60%)"
    # Festività / Ponti primaverili
    if (dt.month == 12 and dt.day >= 20) or (dt.month == 4 and 10 <= dt.day <= 25):
        return 1.30, "Alta Stagione (+30%)"
    # Weekend (Venerdì e Sabato notte)
    if dt.weekday() in [4, 5]:
        return 1.20, "Weekend (+20%)"
    return 1.00, "Standard (Feriale)"

# ----------------------------------------------------
# 4. NAVIGAZIONE PRINCIPALE
# ----------------------------------------------------
menu = st.sidebar.radio(
    "Navigazione",
    ["Dashboard & KPI", "Nuova Prenotazione", "Registro Spese", "Forecast & Pricing Dinamico", "Calendario"]
)

# ----------------------------------------------------
# SEZIONE 1: DASHBOARD & KPI
# ----------------------------------------------------
if menu == "Dashboard & KPI":
    st.title("📊 Dashboard Finanziaria & KPI (€)")
    df_b = load_bookings()
    df_exp = load_bills()

    total_revenue = df_b["Prezzo (€)"].sum() if not df_b.empty else 0.0
    total_bills = df_exp["Importo (€)"].sum() if not df_exp.empty else 0.0
    net_margin = total_revenue - total_bills

    col1, col2, col3 = st.columns(3)
    col1.metric("Ricavi Totali", f"€ {total_revenue:,.2f}")
    col2.metric("Spese Totali", f"€ {total_bills:,.2f}")
    margin_pct = (net_margin / total_revenue * 100) if total_revenue > 0 else 0.0
    col3.metric("Margine Operativo Netto", f"€ {net_margin:,.2f}", delta=f"{margin_pct:.1f}%")

    st.markdown("---")
    st.subheader("Tabella Prenotazioni Registrate")
    
    if not df_b.empty:
        cols_to_show = [c for c in df_b.columns if not c.startswith("_")]
        if "_check_in_dt" in df_b.columns:
            st.dataframe(df_b.sort_values(by="_check_in_dt", ascending=False)[cols_to_show], use_container_width=True)
        else:
            st.dataframe(df_b[cols_to_show], use_container_width=True)
    else:
        st.info("Nessuna prenotazione presente nel database.")

# ----------------------------------------------------
# SEZIONE 2: NUOVA PRENOTAZIONE
# ----------------------------------------------------
elif menu == "Nuova Prenotazione":
    st.title("📝 Inserimento Nuova Prenotazione (€)")
    with st.form("booking_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        guest_name = col1.text_input("Nome Ospite / Canale (es. Booking, Airbnb, Diretto)")
        num_guests = col2.number_input("Numero Ospiti", min_value=1, max_value=20, value=2)

        col3, col4 = st.columns(2)
        check_in = col3.date_input("Data Check-in", value=date.today())
        check_out = col4.date_input("Data Check-out", value=date.today() + timedelta(days=2))

        col5, col6 = st.columns(2)
        total_price = col5.number_input("Prezzo Totale Concordato (€)", min_value=0.0, step=10.0, value=120.0)
        status = col6.selectbox("Stato Pagamento", ["Confermata", "Acconto Versato", "In Sospeso", "Cancellata"])

        submitted = st.form_submit_button("💾 Salva Prenotazione")

        if submitted:
            if check_out <= check_in:
                st.error("La data di check-out deve essere successiva al check-in.")
            elif not guest_name:
                st.error("Inserisci il nome o il canale di prenotazione.")
            else:
                new_data = {
                    "guest_name": guest_name,
                    "num_guests": num_guests,
                    "check_in": check_in.isoformat(),
                    "check_out": check_out.isoformat(),
                    "total_price": float(total_price),
                    "status": status
                }
                try:
                    supabase.table("bookings").insert(new_data).execute()
                    st.success(f"Prenotazione per {guest_name} salvata con successo!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio: {e}")

# ----------------------------------------------------
# SEZIONE 3: REGISTRO SPESE
# ----------------------------------------------------
elif menu == "Registro Spese":
    st.title("⚡ Spese Operative (€)")
    
    with st.expander("➕ Registra Nuova Spesa"):
        with st.form("bill_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            bill_type = col1.selectbox("Categoria Spesa", ["Elettricità", "Acqua", "Internet / Wifi", "Manutenzione", "Forniture", "Pulizie", "Altro"])
            bill_date = col2.date_input("Data Spesa", value=date.today())

            col3, col4 = st.columns(2)
            amount = col3.number_input("Importo (€)", min_value=0.0, step=5.0, value=30.0)
            notes = col4.text_input("Note aggiuntive")

            btn_bill = st.form_submit_button("Salva Spesa")
            if btn_bill:
                bill_data = {
                    "category": bill_type,
                    "date": bill_date.isoformat(),
                    "amount": float(amount),
                    "notes": notes
                }
                try:
                    supabase.table("bills").insert(bill_data).execute()
                    st.success("Spesa registrata con successo!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio: {e}")

    st.markdown("---")
    st.subheader("Storico Spese")
    df_exp = load_bills()
    if not df_exp.empty:
        cols_exp_show = [c for c in df_exp.columns if not c.startswith("_")]
        st.dataframe(df_exp[cols_exp_show], use_container_width=True)
    else:
        st.info("Nessuna spesa inserita finora.")

# ----------------------------------------------------
# SEZIONE 4: FORECAST & PRICING DINAMICO
# ----------------------------------------------------
elif menu == "Forecast & Pricing Dinamico":
    st.title("🎯 Revenue Management: Calcolo Tariffe (€)")
    st.write("Modello di pricing a copertura dei costi con markup protetto.")

    df_exp = load_bills()
    total_bills = df_exp["Importo (€)"].sum() if not df_exp.empty else 1200.0
    estimated_daily_cost = total_bills / 30 if total_bills > 0 else 40.0

    col_c1, col_c2 = st.columns(2)
    base_cost = col_c1.number_input("Costo Unitario Base Giornaliero Stimato (€)", value=float(round(estimated_daily_cost, 2)), step=2.0)
    target_date = col_c2.date_input("Seleziona Giorno per Preventivo", value=date.today())

    factor, desc = get_seasonality_factor(target_date)

    MARKUP_FLOOR = 2.88
    MARKUP_TARGET = 3.50

    price_floor = (base_cost * MARKUP_FLOOR) * factor
    price_target = (base_cost * MARKUP_TARGET) * factor

    st.markdown("### Raccomandazione Tariffaria")
    st.info(f"Fattore Periodo ({target_date.strftime('%d/%m/%Y')}): **{desc}**")

    m1, m2 = st.columns(2)
    m1.metric("Prezzo Minimo Protetto (Floor 2.88x)", f"€ {price_floor:,.2f}", help="Soglia minima protetta")
    m2.metric("Prezzo Ottimale di Vendita (Target 3.50x)", f"€ {price_target:,.2f}", help="Prezzo target per massima marginalità")

    st.markdown("---")
    st.subheader("Forecast Prossimi 7 Giorni")
    
    forecast_days = [target_date + timedelta(days=i) for i in range(7)]
    forecast_data = []
    for d in forecast_days:
        f_fact, f_desc = get_seasonality_factor(d)
        forecast_data.append({
            "Data": d.strftime("%d/%m (%a)"),
            "Periodo": f_desc,
            "Prezzo Minimo (€)": f"€ {round((base_cost * MARKUP_FLOOR) * f_fact, 2):.2f}",
            "Prezzo Target (€)": f"€ {round((base_cost * MARKUP_TARGET) * f_fact, 2):.2f}"
        })
    st.table(pd.DataFrame(forecast_data))

# ----------------------------------------------------
# SEZIONE 5: CALENDARIO
# ----------------------------------------------------
elif menu == "Calendario":
    st.title("📅 Calendario Occupazione")
    df_b = load_bookings()

    if not df_b.empty:
        st.write("Elenco prenotazioni:")
        cols_cal_show = [c for c in df_b.columns if not c.startswith("_")]
        st.dataframe(df_b[cols_cal_show], use_container_width=True)
    else:
        st.info("Nessuna prenotazione disponibile.")