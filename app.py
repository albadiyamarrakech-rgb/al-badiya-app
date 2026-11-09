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
        # Ordine logico basato sul tuo file Excel
        ordine_ideale = [
            "id", "client", "channel", 
            "check_in", "check_out", "nights", 
            "gross_price", "commission", "cleaning_fee", "net_price"
        ]
        
        # Filtra solo le colonne effettivamente presenti nel database
        display_cols = [c for c in ordine_ideale if c in df_b.columns]
        df_display = df_b[display_cols].copy()
        
        # Rinomina le intestazioni per renderle eleganti
        rename_dict = {
            "id": "ID",
            "client": "Ospite",
            "channel": "Canale",
            "check_in": "Check-in",
            "check_out": "Check-out",
            "nights": "Notti",
            "gross_price": "Lordo (€)",
            "commission": "Comm. (€)",
            "cleaning_fee": "Pulizie (€)",
            "net_price": "Netto (€)"
        }
        df_display = df_display.rename(columns=rename_dict)
        
        # Ordina cronologicamente dal check-in più recente
        if "Check-in" in df_display.columns:
            df_display["Check-in"] = pd.to_datetime(df_display["Check-in"]).dt.date
            df_display = df_display.sort_values(by="Check-in", ascending=False)
            
        st.dataframe(df_display, use_container_width=True, hide_index=True)
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
# SEZIONE 5: CALENDARIO VISIVO A GRIGLIA
# ----------------------------------------------------
elif menu == "Calendario":
    import calendar
    
    st.title("📅 Calendario Occupazione")
    
    # Selettori per Mese e Anno
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        sel_month = st.selectbox("Mese", range(1, 13), index=date.today().month - 1)
    with col2:
        sel_year = st.selectbox("Anno", [date.today().year, date.today().year + 1])
        
    df_b = load_bookings()
    
    # 1. Calcola tutti i giorni occupati dalle prenotazioni
    occupied_dates = set()
    if not df_b.empty and "check_in" in df_b.columns and "check_out" in df_b.columns:
        for _, row in df_b.iterrows():
            try:
                ci = pd.to_datetime(row["check_in"]).date()
                co = pd.to_datetime(row["check_out"]).date()
                delta = co - ci
                for i in range(delta.days):
                    occupied_dates.add(ci + timedelta(days=i))
            except:
                pass

    # 2. Genera la struttura del mese
    cal = calendar.monthcalendar(sel_year, sel_month)
    giorni_settimana = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    
    # 3. Costruzione stringa HTML (Senza indentazioni per evitare il blocco codice)
    html_content = ""
    html_content += "<style>"
    html_content += ".cal-container { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; font-family: sans-serif; margin-top: 20px; }"
    html_content += ".cal-header { text-align: center; font-size: 0.9em; color: #a3a8b8; margin-bottom: 5px; }"
    html_content += ".cal-day { border: 1px solid #333; border-radius: 8px; padding: 10px; min-height: 100px; display: flex; flex-direction: column; justify-content: space-between; background-color: #262730; color: #fff; }"
    html_content += ".cal-day.empty { border: none; background: transparent; }"
    html_content += ".cal-day.occupied { opacity: 0.4; background-color: #1a1a24; border-color: #222; }"
    html_content += ".cal-day.occupied .day-num { text-decoration: line-through; color: #888; }"
    html_content += ".day-num { font-size: 1.2em; font-weight: bold; margin-bottom: 5px; }"
    html_content += ".day-price { font-size: 0.95em; color: #ddd; }"
    html_content += ".day-badge { font-size: 0.75em; background-color: #444; padding: 3px 6px; border-radius: 4px; margin-top: 5px; display: inline-block; color: #bbb; }"
    html_content += "</style>"
    
    html_content += "<div class='cal-container'>"
    
    # Intestazioni dei giorni
    for day_name in giorni_settimana:
        html_content += f"<div class='cal-header'>{day_name}</div>"
        
    # Celle dei giorni
    for week in cal:
        for day in week:
            if day == 0:
                html_content += "<div class='cal-day empty'></div>"
            else:
                current_date = date(sel_year, sel_month, day)
                is_occupied = current_date in occupied_dates
                is_past = current_date < date.today()
                
                base_price = 70
                if current_date.weekday() in [4, 5]: # Ven e Sab costano di più
                    base_price += 15
                
                css_class = "cal-day occupied" if (is_occupied or is_past) else "cal-day"
                badge = "Occupato" if is_occupied else "Min. 1 notte"
                
                # Inserimento campi senza rientri per la corretta lettura in Streamlit
                html_content += f"<div class='{css_class}'>"
                html_content += f"<div class='day-num'>{day}</div>"
                html_content += f"<div class='day-price'>{base_price} €</div>"
                html_content += f"<div class='day-badge'>{badge}</div>"
                html_content += "</div>"
    
    html_content += "</div>"
    
    # Renderizza HTML puro senza farlo interpretare come testo
    st.markdown(html_content, unsafe_allow_html=True)