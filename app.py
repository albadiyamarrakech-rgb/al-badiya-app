import os
import calendar
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from supabase import create_client, Client
import base64

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

if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)

st.sidebar.title("Al Badiya")
st.sidebar.caption("Revenue Management & Gestione Struttura")

# ----------------------------------------------------
# 2. CONNESSIONE SUPABASE
# ----------------------------------------------------
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
# 3. CARICAMENTO DATI
# ----------------------------------------------------
def load_bookings():
    if not supabase:
        return pd.DataFrame()
    try:
        res = supabase.table("bookings").select("*").execute()
        df = pd.DataFrame(res.data)
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
        return df
    except Exception as e:
        st.error(f"Errore caricamento spese: {e}")
        return pd.DataFrame()

def get_seasonality_factor(dt: date):
    if (dt.month == 12 and dt.day >= 28) or (dt.month == 1 and dt.day <= 3):
        return 1.45, "Capodanno (+45%)"
    if (dt.month == 12 and dt.day >= 20) or (dt.month == 4 and 10 <= dt.day <= 25):
        return 1.25, "Alta Stagione (+25%)"
    if dt.weekday() in [4, 5]:
        return 1.15, "Weekend (+15%)"
    return 1.00, "Standard (Feriale)"

# ----------------------------------------------------
# 4. NAVIGAZIONE PRINCIPALE
# ----------------------------------------------------
menu = st.sidebar.radio(
    "Navigazione",
    ["Bookings", "Nuova Prenotazione", "Registro Spese", "Report Annuale", "Forecast & Pricing Dinamico", "Calendario"]
)

# ----------------------------------------------------
# SEZIONE 1: BOOKINGS
# ----------------------------------------------------
if menu == "Bookings":
    st.title("📊 Bookings (€)")
    df_b = load_bookings()
    df_exp = load_bills()

    # Assicurati che le colonne di calcolo siano numeriche
    if not df_b.empty:
        for c in ["gross_price", "net_price"]:
            if c in df_b.columns:
                df_b[c] = pd.to_numeric(df_b[c], errors="coerce").fillna(0.0)

    if not df_exp.empty:
        if "amount" in df_exp.columns:
            df_exp["amount"] = pd.to_numeric(df_exp["amount"], errors="coerce").fillna(0.0)

    total_revenue = df_b["gross_price"].sum() if not df_b.empty and "gross_price" in df_b.columns else 0.0
    total_net = df_b["net_price"].sum() if not df_b.empty and "net_price" in df_b.columns else total_revenue
    total_bills = df_exp["amount"].sum() if not df_exp.empty and "amount" in df_exp.columns else 0.0
    net_margin = total_net - total_bills

    col1, col2, col3 = st.columns(3)
    col1.metric("Ricavi Lordi (Gross)", f"€ {total_revenue:,.2f}")
    col2.metric("Spese Operative", f"€ {total_bills:,.2f}")
    margin_pct = (net_margin / total_revenue * 100) if total_revenue > 0 else 0.0
    col3.metric("Margine Netto Reale", f"€ {net_margin:,.2f}", delta=f"{margin_pct:.1f}%")

    st.markdown("---")
    st.subheader("Tabella Prenotazioni Registrate")

    if not df_b.empty:
        ordine_ideale = [
            "id", "client", "nationality", "channel", 
            "check_in", "check_out", "nights", 
            "gross_price", "commission", "cleaning_fee", "net_price"
        ]
        
        display_cols = [c for c in ordine_ideale if c in df_b.columns]
        df_display = df_b[display_cols].copy()
        
        rename_dict = {
            "id": "ID",
            "client": "Ospite",
            "nationality": "Nazionalità",
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
        
        for col in ["Lordo (€)", "Comm. (€)", "Pulizie (€)", "Netto (€)"]:
            if col in df_display.columns:
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce').apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "0.00")
        
        if "Check-in" in df_display.columns:
            df_display["Check-in"] = pd.to_datetime(df_display["Check-in"]).dt.date
            df_display = df_display.sort_values(by="Check-in", ascending=False)
            
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna prenotazione presente nel database.")

# ----------------------------------------------------
# SEZIONE 2: NUOVA PRENOTAZIONE (DATA ENTRY)
# ----------------------------------------------------
elif menu == "Nuova Prenotazione":
    st.title("📝 Inserimento Nuova Prenotazione (€)")
    
    # Gestione dello svuotamento campi dopo il salvataggio
    if "reset_form" not in st.session_state:
        st.session_state.reset_form = False

    if st.session_state.reset_form:
        # Rimossa anche la chiave in_clean
        for key in ["in_client", "in_nat", "in_contact", "in_gross"]:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.reset_form = False

    # Prima riga: Ospite e Nazionalità
    col1, col2 = st.columns(2)
    client = col1.text_input("Nome Ospite", key="in_client")
    nationality = col2.text_input("Nazionalità", key="in_nat")
    
    # Seconda riga: Contatto e Canale
    col3, col4 = st.columns(2)
    contact = col3.text_input("Contatto (Tel/Email)", key="in_contact")
    canali_disponibili = ["Ali", "Booking", "Airbnb", "Younes", "Ayoub"]
    channel = col4.selectbox("Canale", canali_disponibili, key="in_chan")
    
    # Terza riga: Date
    col5, col6 = st.columns(2)
    check_in = col5.date_input("Data Check-in", value=date.today(), key="in_ci")
    check_out = col6.date_input("Data Check-out", value=date.today() + timedelta(days=1), key="in_co")

    # Calcolo Notti Invisibile in background (sempre almeno 1 notte)
    nights = max((check_out - check_in).days, 1)
    
    # Quarta riga: Prezzo Lordo e Commissioni
    col7, col8 = st.columns(2)
    gross_price = col7.number_input("Prezzo Lordo (€)", min_value=0.0, step=5.0, value=70.0, key="in_gross")

    # Calcolo commissioni in tempo reale
    if channel in ["Ali", "Ayoub"]:
        commission_auto = 10.0 * nights
        fee_type = "Dealer"
    elif channel == "Booking":
        commission_auto = gross_price * 0.19
        fee_type = "E-Platform"
    elif channel == "Airbnb":
        commission_auto = gross_price * 0.155
        fee_type = "E-Platform"
    elif channel == "Younes":
        commission_auto = 0.0
        fee_type = "None"
    else:
        commission_auto = 0.0
        fee_type = "None"

    # Commissioni calcolate automaticamente e affiancate al prezzo
    commission = col8.number_input("Commissioni (calcolate in automatico €)", value=float(commission_auto), disabled=True)

    # Costo pulizie fisso in background
    cleaning_fee = 10.0

    net_price = max(0.0, gross_price - commission - cleaning_fee)
    
    # Mostriamo notti calcolate, pulizie e netto nel riquadro riassuntivo
    st.info(f"💡 Notti calcolate: **{nights}** | Pulizie fisse: **€ 10.00** | Ricavo Netto: **€ {net_price:.2f}**")

    if st.button("💾 Salva Prenotazione"):
        if check_out <= check_in:
            st.error("La data di check-out deve essere successiva al check-in.")
        elif not client:
            st.error("Inserisci il Nome Ospite.")
        else:
            try:
                df_temp = load_bookings()
                if not df_temp.empty and "id" in df_temp.columns and pd.notnull(df_temp["id"].max()):
                    next_id = int(df_temp["id"].max()) + 1
                else:
                    next_id = 1

                new_data = {
                    "id": next_id,
                    "client": client,
                    "nationality": nationality,
                    "contact": contact, 
                    "channel": channel,
                    "fee_type": fee_type,
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
                
                supabase.table("bookings").insert(new_data).execute()
                st.success("Prenotazione salvata con successo!")
                
                st.session_state.reset_form = True
                st.rerun()
            except Exception as e:
                st.error(f"Errore durante il salvataggio: {e}")

    # --- TABELLA COMPLETA IN DATA ENTRY (MODIFICABILE) ---
    st.markdown("---")
    st.subheader("Modifica Rapida Prenotazioni")
    st.write("Fai doppio clic su qualsiasi cella per modificare il valore (stile Excel), poi premi il pulsante sotto per aggiornare il database.")
    
    df_b = load_bookings()
    if not df_b.empty:
        cols_to_edit = [
            "id", "client", "nationality", "contact", "channel", 
            "check_in", "check_out", "nights", 
            "gross_price", "commission", "cleaning_fee", "net_price"
        ]
        
        display_cols = [c for c in cols_to_edit if c in df_b.columns]
        df_edit = df_b[display_cols].copy()
        
        if "check_in" in df_edit.columns:
            df_edit["check_in"] = pd.to_datetime(df_edit["check_in"]).dt.date
        if "check_out" in df_edit.columns:
            df_edit["check_out"] = pd.to_datetime(df_edit["check_out"]).dt.date
            
        if "check_in" in df_edit.columns:
            df_edit = df_edit.sort_values(by="check_in", ascending=False).reset_index(drop=True)
            
        edited_df = st.data_editor(
            df_edit,
            use_container_width=True,
            hide_index=True,
            key="booking_editor",
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "client": st.column_config.TextColumn("Ospite"),
                "nationality": st.column_config.TextColumn("Nazionalità"),
                "contact": st.column_config.TextColumn("Contatto"), 
                "channel": st.column_config.SelectboxColumn("Canale", options=["Ali", "Booking", "Airbnb", "Younes", "Ayoub", "Diretto"]),
                "check_in": st.column_config.DateColumn("Check-in"),
                "check_out": st.column_config.DateColumn("Check-out"),
                "nights": st.column_config.NumberColumn("Notti", min_value=1),
                "gross_price": st.column_config.NumberColumn("Lordo (€)", format="%.2f €"),
                "commission": st.column_config.NumberColumn("Comm. (€)", format="%.2f €"),
                "cleaning_fee": st.column_config.NumberColumn("Pulizie (€)", format="%.2f €"),
                "net_price": st.column_config.NumberColumn("Netto (€)", format="%.2f €")
            }
        )
        
        if st.button("🔄 Salva Modifiche Tabella"):
            changes = st.session_state.booking_editor["edited_rows"]
            if changes:
                try:
                    for row_idx, updates in changes.items():
                        booking_id = int(df_edit.iloc[row_idx]["id"])
                        db_update = {}
                        
                        for col, val in updates.items():
                            if col in ["check_in", "check_out"]:
                                db_update[col] = str(val)[:10] 
                            else:
                                db_update[col] = val
                                
                        supabase.table("bookings").update(db_update).eq("id", booking_id).execute()
                        
                    st.success("✅ Tutte le modifiche sono state salvate nel database!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore durante l'aggiornamento: {e}")
            else:
                st.info("Nessuna modifica rilevata. Cambia qualche valore facendo doppio clic su una cella prima di salvare.")
    else:
        st.info("Nessuna prenotazione presente.")

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
                # Struttura adattata per accogliere i DB generici se utilizzati
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
        df_exp_display = df_exp[cols_exp].copy()
        
        # Capitalizza la prima lettera di ogni colonna
        rename_exp = {col: col.capitalize() for col in df_exp_display.columns}
        
        # Aggiunge il simbolo € e forza a 2 decimali per le colonne note come finanziarie
        fin_cols = ['electricity', 'water', 'internet', 'extra', 'total_bills', 'amount', 'category']
        for col in fin_cols:
            if col in df_exp_display.columns and pd.api.types.is_numeric_dtype(df_exp_display[col]):
                 rename_exp[col] = f"{col.capitalize()} (€)"
                 df_exp_display[col] = pd.to_numeric(df_exp_display[col], errors='coerce').apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "0.00")
                 
        df_exp_display = df_exp_display.rename(columns=rename_exp)
        
        if "Month" in df_exp_display.columns:
            try:
                df_exp_display["Month"] = pd.to_datetime(df_exp_display["Month"]).dt.date
            except:
                pass
                
        st.dataframe(df_exp_display, use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna spesa presente.")

# ----------------------------------------------------
# SEZIONE: REPORT ANNUALE (RIEPILOGO & TOTAL COSTS)
# ----------------------------------------------------
elif menu == "Report Annuale":
    st.title("📈 Report Annuale & Analisi Costi (€)")

    df_b = load_bookings()
    df_exp = load_bills()

    if df_b.empty:
        st.info("Nessuna prenotazione disponibile per generare il report.")
    else:
        # --- PREPARAZIONE DATI PRENOTAZIONI ---
        df_b = df_b.copy()
        if "year" not in df_b.columns or df_b["year"].isna().any():
            df_b["year"] = pd.to_datetime(df_b["check_in"], errors="coerce").dt.year

        df_b = df_b.dropna(subset=["year"])
        df_b["year"] = df_b["year"].astype(int)

        for col in ["nights", "gross_price", "net_price", "commission", "cleaning_fee"]:
            if col in df_b.columns:
                df_b[col] = pd.to_numeric(df_b[col], errors="coerce").fillna(0.0)
            else:
                df_b[col] = 0.0

        # Aggregazione prenotazioni per anno
        b_yearly = df_b.groupby("year").agg(
            num_prenotazioni=("id", "count"),
            num_notti=("nights", "sum"),
            gross_price=("gross_price", "sum"),
            net_price=("net_price", "sum"),
            commissioni=("commission", "sum"),
            pulizie=("cleaning_fee", "sum")
        ).reset_index()

        # --- PREPARAZIONE DATI SPESE (BILLS) ---
        if not df_exp.empty:
            df_exp = df_exp.copy()

            # Individua la colonna anno/data disponibile in bills
            if "year" in df_exp.columns and df_exp["year"].notna().any():
                df_exp["year"] = pd.to_numeric(df_exp["year"], errors="coerce")
            elif "month" in df_exp.columns:
                df_exp["year"] = pd.to_datetime(df_exp["month"], errors="coerce").dt.year
            elif "date" in df_exp.columns:
                df_exp["year"] = pd.to_datetime(df_exp["date"], errors="coerce").dt.year
            else:
                df_exp["year"] = np.nan

            # Individua la colonna importo (total_bills oppure amount)
            bill_col = "total_bills" if "total_bills" in df_exp.columns else ("amount" if "amount" in df_exp.columns else None)

            if bill_col:
                df_exp[bill_col] = pd.to_numeric(df_exp[bill_col], errors="coerce").fillna(0.0)
                exp_yearly = df_exp.dropna(subset=["year"]).groupby("year")[bill_col].sum().reset_index()
                exp_yearly["year"] = exp_yearly["year"].astype(int)
                exp_yearly = exp_yearly.rename(columns={bill_col: "total_bills"})
            else:
                exp_yearly = pd.DataFrame(columns=["year", "total_bills"])
        else:
            exp_yearly = pd.DataFrame(columns=["year", "total_bills"])

        # --- UNIONE DATI PER ANNO ---
        report = pd.merge(b_yearly, exp_yearly, on="year", how="outer").fillna(0.0)
        report = report.sort_values(by="year", ascending=True)
        report["year"] = report["year"].astype(int).astype(str)

        # Calcoli richiesti
        report["total_costs"] = report["commissioni"] + report["pulizie"] + report["total_bills"]
        report["net_profit"] = report["net_price"] - report["total_costs"]

        # ====================================================
        # TABELLA 1: RIEPILOGO ANNUALE
        # ====================================================
        st.subheader("Riepilogo Annuale")

        tab1 = report[[
            "year", "num_prenotazioni", "num_notti",
            "gross_price", "net_price", "total_costs", "net_profit"
        ]].copy()

        # Riga Totale complessivo
        totale_1 = pd.DataFrame([{
            "year": "Totale complessivo",
            "num_prenotazioni": tab1["num_prenotazioni"].sum(),
            "num_notti": tab1["num_notti"].sum(),
            "gross_price": tab1["gross_price"].sum(),
            "net_price": tab1["net_price"].sum(),
            "total_costs": tab1["total_costs"].sum(),
            "net_profit": tab1["net_profit"].sum()
        }])
        tab1 = pd.concat([tab1, totale_1], ignore_index=True)

        # Formattazione
        tab1["num_prenotazioni"] = tab1["num_prenotazioni"].astype(int)
        tab1["num_notti"] = tab1["num_notti"].astype(int)
        for col in ["gross_price", "net_price", "total_costs", "net_profit"]:
            tab1[col] = tab1[col].apply(lambda x: f"€ {x:,.2f}")

        tab1 = tab1.rename(columns={
            "year": "Anno",
            "num_prenotazioni": "Numero Prenotazioni",
            "num_notti": "Numero Notti",
            "gross_price": "Gross Price (€)",
            "net_price": "Net Price (€)",
            "total_costs": "Total Costs (€)",
            "net_profit": "Net Profit (€)"
        })

        st.dataframe(tab1, use_container_width=True, hide_index=True)

        # ====================================================
        # TABELLA 2: DETTAGLIO TOTAL COSTS
        # ====================================================
        st.markdown("---")
        st.subheader("Dettaglio Total Costs")

        tab2 = report[["year", "commissioni", "pulizie", "total_bills"]].copy()

        # Riga Totale complessivo
        totale_2 = pd.DataFrame([{
            "year": "Totale complessivo",
            "commissioni": tab2["commissioni"].sum(),
            "pulizie": tab2["pulizie"].sum(),
            "total_bills": tab2["total_bills"].sum()
        }])
        tab2 = pd.concat([tab2, totale_2], ignore_index=True)

        # Formattazione
        for col in ["commissioni", "pulizie", "total_bills"]:
            tab2[col] = tab2[col].apply(lambda x: f"€ {x:,.2f}")

        tab2 = tab2.rename(columns={
            "year": "Anno",
            "commissioni": "Commissioni (€)",
            "pulizie": "Pulizie (€)",
            "total_bills": "Total Bills (€)"
        })

        st.dataframe(tab2, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# SEZIONE 4: FORECAST & PRICING DINAMICO
# ----------------------------------------------------
elif menu == "Forecast & Pricing Dinamico":
    st.title("🎯 Revenue Management: Tariffe Giornaliere Consigliate")
    st.write("Calcolo delle tariffe ottimali per notte basato sullo storico reale delle tue prenotazioni.")

    df_b = load_bookings()
    
    if not df_b.empty and "gross_price" in df_b.columns and "nights" in df_b.columns:
        valid_b = df_b[df_b["nights"] > 0]
        if not valid_b.empty:
            valid_b["gross_price"] = pd.to_numeric(valid_b["gross_price"], errors="coerce")
            valid_b["nights"] = pd.to_numeric(valid_b["nights"], errors="coerce")
            avg_night_rate = (valid_b["gross_price"] / valid_b["nights"]).median()
        else:
            avg_night_rate = 70.0
    else:
        avg_night_rate = 70.0

    if pd.isna(avg_night_rate) or avg_night_rate == 0:
        avg_night_rate = 70.0

    col_c1, col_c2 = st.columns(2)
    base_price = col_c1.number_input("Tariffa Base Feriale per Notte (€)", value=float(round(avg_night_rate, 2)), step=5.0)
    target_date = col_c2.date_input("Data di Riferimento", value=date.today())

    factor, desc = get_seasonality_factor(target_date)

    price_floor = (base_price * 0.85) * factor
    price_target = base_price * factor

    st.markdown("### Raccomandazione Tariffaria per Notte")
    st.info(f"Periodo Rilevato ({target_date.strftime('%d/%m/%Y')}): **{desc}**")

    m1, m2 = st.columns(2)
    m1.metric("Prezzo Minimo Accettabile (Floor)", f"€ {price_floor:,.2f}", help="Soglia minima per riempire i buchi")
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
    
    st.title("📅 Calendario Occupazione")
    
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        sel_month = st.selectbox("Mese", range(1, 13), index=date.today().month - 1)
    with col2:
        sel_year = st.selectbox("Anno", [date.today().year, date.today().year + 1])
        
    df_b = load_bookings()
    
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

    cal = calendar.monthcalendar(sel_year, sel_month)
    giorni_settimana = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    
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
    
    for day_name in giorni_settimana:
        html_content += f"<div class='cal-header'>{day_name}</div>"
        
    for week in cal:
        for day in week:
            if day == 0:
                html_content += "<div class='cal-day empty'></div>"
            else:
                current_date = date(sel_year, sel_month, day)
                is_occupied = current_date in occupied_dates
                is_past = current_date < date.today()
                
                base_price = 70
                if current_date.weekday() in [4, 5]: 
                    base_price += 15
                
                css_class = "cal-day occupied" if (is_occupied or is_past) else "cal-day"
                badge = "Occupato" if is_occupied else "Min. 1 notte"
                
                html_content += f"<div class='{css_class}'>"
                html_content += f"<div class='day-num'>{day}</div>"
                html_content += f"<div class='day-price'>{base_price} €</div>"
                html_content += f"<div class='day-badge'>{badge}</div>"
                html_content += "</div>"
    
    html_content += "</div>"
    
    st.markdown(html_content, unsafe_allow_html=True)