import os
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# ----------------------------------------------------
# 1. CONFIGURAZIONE PAGINA & BRANDING
# ----------------------------------------------------
page_icon = "logo.png" if os.path.exists("logo.png") else "🏨"

st.set_page_config(
    page_title="Al Badiya Management",
    page_icon=page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Mostra il logo nella barra laterale
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)

st.sidebar.title("Al Badiya")
st.sidebar.caption("Revenue Management & Gestione Struttura")

# ----------------------------------------------------
# 2. CONNESSIONE SUPABASE
# ----------------------------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", "https://tua-url.supabase.co"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", "tua-publishable-key"))

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = get_supabase_client()
except Exception as e:
    st.sidebar.error(f"Errore connessione DB: {e}")
    supabase = None

# ----------------------------------------------------
# 3. CARICAMENTO DATI
# ----------------------------------------------------
def load_bookings():
    if not supabase:
        return pd.DataFrame()
    try:
        res = supabase.table("bookings").select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame()

        # Riconoscimento data check-in per ordinamento
        if "check_in" in df.columns:
            df["_check_in_dt"] = pd.to_datetime(df["check_in"], errors="coerce").dt.date
        elif "data_in" in df.columns:
            df["_check_in_dt"] = pd.to_datetime(df["data_in"], errors="coerce").dt.date

        # Converti i campi finanziari in numerici
        for col in ["gross_price", "net_price", "commission", "cleaning_fee", "nights"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

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

        # Identifica importo spesa
        for col in df.columns:
            c_low = col.lower()
            if any(k in c_low for k in ["amount", "importo", "spesa", "costo", "total", "price"]):
                df["amount"] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
                break
        if "amount" not in df.columns:
            df["amount"] = 0.0

        return df
    except Exception as e:
        st.error(f"Errore caricamento spese: {e}")
        return pd.DataFrame()

def get_seasonality_factor(dt: date):
    # Capodanno (28 Dicembre - 3 Gennaio)
    if (dt.month == 12 and dt.day >= 28) or (dt.month == 1 and dt.day <= 3):
        return 1.45, "Capodanno (+45%)"
    # Festività natalizie o primavera
    if (dt.month == 12 and dt.day >= 20) or (dt.month == 4 and 10 <= dt.day <= 25):
        return 1.25, "Alta Stagione (+25%)"
    # Weekend (Venerdì e Sabato)
    if dt.weekday() in [4, 5]:
        return 1.15, "Weekend (+15%)"
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

    # Ricavi calcolati da gross_price (o net_price se preferisci)
    if not df_b.empty and "gross_price" in df_b.columns:
        total_revenue = df_b["gross_price"].sum()
        total_net = df_b["net_price"].sum() if "net_price" in df_b.columns else total_revenue
    else:
        total_revenue = 0.0
        total_net = 0.0

    total_bills = df_exp["amount"].sum() if not df_exp.empty else 0.0
    net_margin = total_net - total_bills

    col1, col2, col3 = st.columns(3)
    col1.metric("Ricavi Lordi (Gross)", f"€ {total_revenue:,.2f}")
    col2.metric("Spese Operative", f"€ {total_bills:,.2f}")
    margin_pct = (net_margin / total_revenue * 100) if total_revenue > 0 else 0.0
    col3.metric("Margine Netto Reale", f"€ {net_margin:,.2f}", delta=f"{margin_pct:.1f}%")

    st.markdown("---")
    st.subheader("Tabella Prenotazioni Registrate")

    if not df_b.empty:
        # Colonne preferenziali e ripulite (niente created_at, niente colonne tecniche)
        colonne_ordinate = [
            c for c in ["check_in", "check_out", "nights", "gross_price", "commission", "cleaning_fee", "net_price", "month", "year"]
            if c in df_b.columns
        ]
        
        # Se ci sono altre colonne utili nel database non escluse, mostrale prima di escludere created_at
        altre_colonne = [c for c in df_b.columns if c not in colonne_ordinate and c != "created_at" and not c.startswith("_")]
        display_cols = colonne_ordinate + altre_colonne

        if "_check_in_dt" in df_b.columns:
            df_display = df_b.sort_values(by="_check_in_dt", ascending=False)[display_cols]
        else:
            df_display = df_b[display_cols]

        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("Nessuna prenotazione presente nel database.")

# ----------------------------------------------------
# SEZIONE 2: NUOVA PRENOTAZIONE
# ----------------------------------------------------
elif menu == "Nuova Prenotazione":
    st.title("📝 Inserimento Nuova Prenotazione (€)")
    with st.form("booking_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        check_in = col1.date_input("Data Check-in", value=date.today())
        check_out = col2.date_input("Data Check-out", value=date.today() + timedelta(days=1))

        col3, col4 = st.columns(2)
        nights = col3.number_input("Numero Notti", min_value=1, value=max((check_out - check_in).days, 1))
        gross_price = col4.number_input("Prezzo Lordo (€)", min_value=0.0, step=5.0, value=70.0)

        col5, col6 = st.columns(2)
        commission = col5.number_input("Commissioni (€)", min_value=0.0, step=1.0, value=10.0)
        cleaning_fee = col6.number_input("Costi Pulizie (€)", min_value=0.0, step=1.0, value=10.0)

        net_price = max(0.0, gross_price - commission - cleaning_fee)
        st.info(f"💡 Ricavo Netto Calcolato: **€ {net_price:.2f}**")

        submitted = st.form_submit_button("💾 Salva Prenotazione")

        if submitted:
            if check_out <= check_in:
                st.error("La data di check-out deve essere successiva al check-in.")
            else:
                new_data = {
                    "check_in": check_in.isoformat(),
                    "check_out": check_out.isoformat(),
                    "nights": int(nights),
                    "gross_price": float(gross_price),
                    "commission": float(commission),
                    "cleaning_fee": float(cleaning_fee),
                    "net_price": float(net_price),
                    "month": check_in.strftime("%Y-%m-01"),
                    "year": check_in.year
                }
                try:
                    supabase.table("bookings").insert(new_data).execute()
                    st.success("Prenotazione salvata con successo!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore durante il salvataggio: {e}")

# ----------------------------------------------------
# SEZIONE 3: REGISTRO SPESE
# ----------------------------------------------------
elif menu == "Registro Spese":
    st.title("⚡ Spese Operative (€)")
    
    with st.expander("➕ Registra Nuova Spesa"):
        with st.form("bill_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            bill_type = col1.selectbox("Categoria Spesa", ["Elettricità", "Acqua", "Internet", "Manutenzione", "Forniture", "Pulizie", "Altro"])
            bill_date = col2.date_input("Data Spesa", value=date.today())

            col3, col4 = st.columns(2)
            amount = col3.number_input("Importo (€)", min_value=0.0, step=5.0, value=30.0)
            notes = col4.text_input("Note")

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
                    st.success("Spesa registrata!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}")

    st.markdown("---")
    st.subheader("Storico Spese")
    df_exp = load_bills()
    if not df_exp.empty:
        cols_exp = [c for c in df_exp.columns if c != "created_at" and not c.startswith("_")]
        st.dataframe(df_exp[cols_exp], use_container_width=True)
    else:
        st.info("Nessuna spesa presente.")

# ----------------------------------------------------
# SEZIONE 4: FORECAST & PRICING DINAMICO (COERENTE AI TUOI PREZZI REALI)
# ----------------------------------------------------
elif menu == "Forecast & Pricing Dinamico":
    st.title("🎯 Revenue Management: Tariffe Giornaliere Consigliate")
    st.write("Calcolo delle tariffe ottimali per notte basato sullo storico reale delle tue prenotazioni.")

    df_b = load_bookings()
    
    # Calcola il prezzo medio reale a notte dal database (default € 70 se vuoto)
    if not df_b.empty and "gross_price" in df_b.columns and "nights" in df_b.columns:
        valid_b = df_b[df_b["nights"] > 0]
        if not valid_b.empty:
            avg_night_rate = (valid_b["gross_price"] / valid_b["nights"]).median()
        else:
            avg_night_rate = 70.0
    else:
        avg_night_rate = 70.0

    col_c1, col_c2 = st.columns(2)
    base_price = col_c1.number_input("Tariffa Base Feriale per Notte (€)", value=float(round(avg_night_rate, 2)), step=5.0)
    target_date = col_c2.date_input("Data di Riferimento", value=date.today())

    factor, desc = get_seasonality_factor(target_date)

    # Prezzo Minimo accettabile (Floor: -15% rispetto alla base per garantire occupazione)
    # Prezzo Ottimale di vendita (Target: prezzo base + stagionalità)
    price_floor = (base_price * 0.85) * factor
    price_target = base_price * factor

    st.markdown("### Raccomandazione Tariffaria per Notte")
    st.info(f"Periodo Rilevato ({target_date.strftime('%d/%m/%Y')}): **{desc}**")

    m1, m2 = st.columns(2)
    m1.metric("Prezzo Minimo Accettabile (Floor)", f"€ {price_floor:,.2f}", help="Soglia minima per riempire i buchi infrasettimanali")
    m2.metric("Prezzo Ottimale di Vendita (Target)", f"€ {price_target:,.2f}", help="Tariffa consigliata per massimizzare il ricavo")

    st.markdown("---")
    st.subheader("Forecast Prezzi Prossimi 7 Giorni")
    
    forecast_days = [target_date + timedelta(days=i) for i in range(7)]
    forecast_data = []
    for d in forecast_days:
        f_fact, f_desc = get_seasonality_factor(d)
        forecast_data.append({
            "Data": d.strftime("%d/%m (%a)"),
            "Periodo": f_desc,
            "Prezzo Minimo (€)": f"€ {round((base_price * 0.85) * f_fact, 2):.2f}",
            "Prezzo Consigliato (€)": f"€ {round(base_price * f_fact, 2):.2f}"
        })
    st.table(pd.DataFrame(forecast_data))

# ----------------------------------------------------
# SEZIONE 5: CALENDARIO VISIVO OCCUPAZIONE
# ----------------------------------------------------
elif menu == "Calendario":
    import altair as alt
    
    st.title("📅 Calendario Occupazione")
    df_b = load_bookings()

    if not df_b.empty and "check_in" in df_b.columns and "check_out" in df_b.columns:
        st.write("Colpo d'occhio sulle date occupate:")
        
        # Prepariamo i dati per il grafico visivo
        df_cal = df_b.copy()
        df_cal["check_in"] = pd.to_datetime(df_cal["check_in"])
        df_cal["check_out"] = pd.to_datetime(df_cal["check_out"])
        df_cal["Struttura"] = "Al Badiya" # Asse Y fisso per la struttura
        
        # Creiamo la Timeline Visiva (Gantt Chart)
        chart = alt.Chart(df_cal).mark_bar(cornerRadius=4, height=40).encode(
            x=alt.X('check_in:T', title='Linea del Tempo'),
            x2='check_out:T',
            y=alt.Y('Struttura:N', title='', axis=alt.Axis(labels=False, ticks=False)),
            color=alt.Color('gross_price:Q', scale=alt.Scale(scheme='blues'), title='Prezzo (€)'),
            tooltip=[
                alt.Tooltip('check_in:T', title='Check-in', format='%d/%m/%Y'),
                alt.Tooltip('check_out:T', title='Check-out', format='%d/%m/%Y'),
                alt.Tooltip('nights:Q', title='Notti'),
                alt.Tooltip('gross_price:Q', title='Prezzo Lordo (€)')
            ]
        ).properties(height=150)
        
        st.altair_chart(chart, use_container_width=True)

        # Tabella di riepilogo sottostante formattata in Euro
        st.markdown("---")
        st.write("Dettaglio prenotazioni confermate:")
        
        display_cols = [c for c in ["check_in", "check_out", "nights", "gross_price", "net_price"] if c in df_b.columns]
        df_table = df_b[display_cols].copy()
        
        # Rinomina le intestazioni
        df_table = df_table.rename(columns={
            "check_in": "Check-in",
            "check_out": "Check-out",
            "nights": "Notti",
            "gross_price": "Prezzo Lordo",
            "net_price": "Prezzo Netto"
        })
        
        # Formatta i prezzi con il simbolo € e 2 decimali
        if "Prezzo Lordo" in df_table.columns:
            df_table["Prezzo Lordo"] = df_table["Prezzo Lordo"].apply(lambda x: f"€ {float(x):,.2f}")
        if "Prezzo Netto" in df_table.columns:
            df_table["Prezzo Netto"] = df_table["Prezzo Netto"].apply(lambda x: f"€ {float(x):,.2f}")
            
        st.dataframe(df_table, use_container_width=True)
    else:
        st.info("Nessuna prenotazione disponibile per generare il calendario.")