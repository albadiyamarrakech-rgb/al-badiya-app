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
# Verifica se il logo è presente nella stessa cartella per usarlo come icona
page_icon = "logo.png" if os.path.exists("logo.png") else "🏨"

st.set_page_config(
    page_title="Al Badiya Management",
    page_icon=page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Mostra il logo nella barra laterale se disponibile
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)

st.sidebar.title("Al Badiya")
st.sidebar.caption("Revenue Management & Gestione Struttura")

# ----------------------------------------------------
# 2. CONNESSIONE SUPABASE
# ----------------------------------------------------
# Le credenziali vengono lette dai Secrets di Streamlit oppure da variabili d'ambiente
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", "https://rkicgvfzoptideeaylog.supabase.co"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", "sb_publishable_pWP_qrEggQdTlbqeNiX1Tg_KsrHkyeg"))

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = get_supabase_client()
except Exception as e:
    st.sidebar.error(f"Errore connessione DB: {e}")
    supabase = None

# ----------------------------------------------------
# 3. FUNZIONI DATI (BOOKINGS & BILLS)
# ----------------------------------------------------
def load_bookings():
    if not supabase:
        return pd.DataFrame()
    res = supabase.table("bookings").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df["check_in"] = pd.to_datetime(df["check_in"]).dt.date
        df["check_out"] = pd.to_datetime(df["check_out"]).dt.date
        df["total_price"] = pd.to_numeric(df["total_price"], errors="coerce").fillna(0.0)
    return df

def load_bills():
    if not supabase:
        return pd.DataFrame()
    res = supabase.table("bills").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    return df

# Festività di punta Al Badiya (Capodanno, festività primaverili/autunnali)
def get_seasonality_factor(dt: date):
    # Capodanno (28 Dicembre - 3 Gennaio)
    if (dt.month == 12 and dt.day >= 28) or (dt.month == 1 and dt.day <= 3):
        return 1.60, "Capodanno (+60%)"
    # Festività invernali / Pasquali / ponti
    if (dt.month == 12 and dt.day >= 20) or (dt.month == 4 and 10 <= dt.day <= 25):
        return 1.30, "Alta Stagione / Festività (+30%)"
    # Weekend (Venerdì e Sabato notte)
    if dt.weekday() in [4, 5]:
        return 1.20, "Weekend (+20%)"
    return 1.00, "Standard (Feriale)"

# ----------------------------------------------------
# 4. NAVIGAZIONE PRINCIPALE
# ----------------------------------------------------
menu = st.sidebar.radio(
    "Navigazione",
    ["Dashboard & KPI", "Nuova Prenotazione", "Registro Bollette & Spese", "Forecast & Pricing Dinamico", "Calendario"]
)

# ----------------------------------------------------
# SEZIONE 1: DASHBOARD & KPI
# ----------------------------------------------------
if menu == "Dashboard & KPI":
    st.title("📊 Dashboard Finanziaria & KPI")
    df_b = load_bookings()
    df_exp = load_bills()

    total_revenue = df_b["total_price"].sum() if not df_b.empty else 0.0
    total_bills = df_exp["amount"].sum() if not df_exp.empty else 0.0
    net_margin = total_revenue - total_bills

    col1, col2, col3 = st.columns(3)
    col1.metric("Ricavi Totali", f"{total_revenue:,.2f} MAD")
    col2.metric("Spese / Bollette", f"{total_bills:,.2f} MAD")
    col3.metric("Margine Operativo Netto", f"{net_margin:,.2f} MAD", delta=f"{(net_margin/total_revenue*100) if total_revenue else 0:.1f}%")

    st.markdown("---")
    st.subheader("Ultime Prenotazioni Registrate")
    if not df_b.empty:
        st.dataframe(df_b.sort_values(by="check_in", ascending=False).head(10), use_container_width=True)
    else:
        st.info("Nessuna prenotazione presente nel database.")

# ----------------------------------------------------
# SEZIONE 2: NUOVA PRENOTAZIONE
# ----------------------------------------------------
elif menu == "Nuova Prenotazione":
    st.title("📝 Inserimento Nuova Prenotazione")
    with st.form("booking_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        guest_name = col1.text_input("Nome Ospite / Canale (es. Booking, Airbnb)")
        num_guests = col2.number_input("Numero Ospiti", min_value=1, max_value=20, value=2)

        col3, col4 = st.columns(2)
        check_in = col3.date_input("Data Check-in", value=date.today())
        check_out = col4.date_input("Data Check-out", value=date.today() + timedelta(days=2))

        col5, col6 = st.columns(2)
        total_price = col5.number_input("Prezzo Totale Concordato (MAD)", min_value=0.0, step=50.0, value=1200.0)
        status = col6.selectbox("Stato Pagamento", ["Confermata", "Acconto Versato", "In Sospeso", "Cancellata"])

        submitted = st.form_submit_button("💾 Salva Prenotazione su Cloud")

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
                except Exception as e:
                    st.error(f"Errore nel salvataggio su Supabase: {e}")

# ----------------------------------------------------
# SEZIONE 3: REGISTRO BOLLETTE & SPESE
# ----------------------------------------------------
elif menu == "Registro Bollette & Spese":
    st.title("⚡ Spese Operative & Bollette")
    
    with st.expander("➕ Registra Nuova Bolletta / Spesa"):
        with st.form("bill_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            bill_type = col1.selectbox("Categoria Spesa", ["Elettricità", "Acqua", "Internet / Wifi", "Manutenzione", "Forniture", "Altro"])
            bill_date = col2.date_input("Data Spesa", value=date.today())

            col3, col4 = st.columns(2)
            amount = col3.number_input("Importo (MAD)", min_value=0.0, step=10.0, value=300.0)
            notes = col4.text_input("Note aggiuntive (es. periodo fattura)")

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
                except Exception as e:
                    st.error(f"Errore: {e}")

    st.markdown("---")
    st.subheader("Storico Spese")
    df_exp = load_bills()
    if not df_exp.empty:
        st.dataframe(df_exp.sort_values(by="date", ascending=False), use_container_width=True)
    else:
        st.info("Nessuna spesa inserita finora.")

# ----------------------------------------------------
# SEZIONE 4: FORECAST & PRICING DINAMICO
# ----------------------------------------------------
elif menu == "Forecast & Pricing Dinamico":
    st.title("🎯 Revenue Management: Calcolo Prezzi")
    st.write("Modello tariffario basato sui costi unitari con soglia di markup protetta.")

    df_exp = load_bills()
    total_bills = df_exp["amount"].sum() if not df_exp.empty else 15000.0
    
    # Stima costo medio giornaliero base (default 30 gg mese o storico)
    estimated_daily_cost = total_bills / 30 if total_bills > 0 else 350.0

    col_c1, col_c2 = st.columns(2)
    base_cost = col_c1.number_input("Costo Unitario Base Giornaliero Stimato (MAD)", value=float(round(estimated_daily_cost, 2)), step=10.0)
    target_date = col_c2.date_input("Seleziona Giorno per Preventivo", value=date.today())

    factor, desc = get_seasonality_factor(target_date)

    # Parametri di Revenue Management protetto
    MARKUP_FLOOR = 2.88
    MARKUP_TARGET = 3.50

    price_floor = (base_cost * MARKUP_FLOOR) * factor
    price_target = (base_cost * MARKUP_TARGET) * factor

    st.markdown("### Raccomandazione Tariffaria")
    st.info(f"Fattore Applicato per la data ({target_date.strftime('%d/%m/%Y')}): **{desc}**")

    m1, m2 = st.columns(2)
    m1.metric("Prezzo Minimo Protetto (Floor 2.88x)", f"{price_floor:,.2f} MAD", help="Prezzo al di sotto del quale non scendere nemmeno in bassa domanda")
    m2.metric("Prezzo Ottimale di Vendita (Target 3.50x)", f"{price_target:,.2f} MAD", help="Prezzo consigliato per massimizzare la marginalità")

    # Simulazione mese intero
    st.markdown("---")
    st.subheader(f"Forecast Settimanale ({target_date.strftime('%B %Y')})")
    
    forecast_days = [target_date + timedelta(days=i) for i in range(7)]
    forecast_data = []
    for d in forecast_days:
        f_fact, f_desc = get_seasonality_factor(d)
        forecast_data.append({
            "Data": d.strftime("%d/%m (%a)"),
            "Periodo": f_desc,
            "Prezzo Minimo (MAD)": round((base_cost * MARKUP_FLOOR) * f_fact, 2),
            "Prezzo Target (MAD)": round((base_cost * MARKUP_TARGET) * f_fact, 2)
        })
    st.table(pd.DataFrame(forecast_data))

# ----------------------------------------------------
# SEZIONE 5: CALENDARIO MENSILE
# ----------------------------------------------------
elif menu == "Calendario":
    st.title("📅 Calendario Occupazione")
    df_b = load_bookings()

    if not df_b.empty:
        df_active = df_b[df_b["status"] != "Cancellata"]
        st.write("Visualizzazione date occupate:")
        
        selected_month = st.selectbox("Seleziona Mese", options=list(range(1, 13)), index=date.today().month - 1)
        
        # Filtro per mese
        month_bookings = []
        for _, row in df_active.iterrows():
            if row["check_in"].month == selected_month or row["check_out"].month == selected_month:
                month_bookings.append({
                    "Ospite": row["guest_name"],
                    "In": row["check_in"].strftime("%d/%m/%Y"),
                    "Out": row["check_out"].strftime("%d/%m/%Y"),
                    "Stato": row["status"],
                    "Totale MAD": row["total_price"]
                })
        
        if month_bookings:
            st.dataframe(pd.DataFrame(month_bookings), use_container_width=True)
        else:
            st.info("Nessuna prenotazione attiva per questo mese.")
    else:
        st.info("Nessun dato di prenotazione disponibile.")