import os
import io
import calendar
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from supabase import create_client, Client

st.set_page_config(page_title="Al Badiya Management", layout="wide")

st.title("📊 Al Badiya Management System")

# --- CONNESSIONE A SUPABASE ---
SUPABASE_URL = "https://rkicgvfzoptideeaylog.supabase.co" 
SUPABASE_KEY = "sb_publishable_pWP_qrEggQdTlbqeNiX1Tg_KsrHkyeg"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

def load_cloud_data():
    res_bookings = supabase.table("bookings").select("*").order("id", desc=False).execute()
    res_bills = supabase.table("bills").select("*").order("id", desc=False).execute()

    df_b = pd.DataFrame(res_bookings.data) if res_bookings.data else pd.DataFrame()
    df_bi = pd.DataFrame(res_bills.data) if res_bills.data else pd.DataFrame()

    return df_b, df_bi

try:
    df_bookings_raw, df_bills_raw = load_cloud_data()

    # --- NORMALIZZAZIONE E PULIZIA DATI BOOKINGS ---
    if not df_bookings_raw.empty:
        df_bookings_view = df_bookings_raw.copy()
        col_rename = {
            "id": "N Revs",
            "client": "Client",
            "channel": "Channel",
            "fee_type": "Fee Type",
            "contact": "Contact",
            "n_people": "N People",
            "nationality": "Nationality",
            "check_in": "Check-In",
            "check_out": "Check-Out",
            "nights": "Nights",
            "gross_price": "Gross Price",
            "commission": "Commission",
            "cleaning_fee": "Cleaning Fee",
            "net_price": "Net Price",
            "month": "Month",
            "year": "Year"
        }
        df_bookings_view = df_bookings_view.rename(columns=col_rename)

        df_bookings_view["Check-In_dt"] = pd.to_datetime(df_bookings_view["Check-In"], errors="coerce")
        df_bookings_view["Check-Out_dt"] = pd.to_datetime(df_bookings_view["Check-Out"], errors="coerce")
        df_bookings_view["Year"] = df_bookings_view["Check-In_dt"].dt.year.fillna(0).astype(int)
        df_bookings_view["Month_num"] = df_bookings_view["Check-In_dt"].dt.month

        for col in ["Gross Price", "Commission", "Cleaning Fee", "Net Price", "Nights"]:
            if col in df_bookings_view.columns:
                df_bookings_view[col] = pd.to_numeric(df_bookings_view[col], errors="coerce").fillna(0)
    else:
        df_bookings_view = pd.DataFrame()

    # --- NORMALIZZAZIONE E PULIZIA DATI BILLS ---
    if not df_bills_raw.empty:
        df_bills_view = df_bills_raw.copy()
        col_rename_bills = {
            "id": "ID",
            "year": "Year",
            "month": "Month",
            "nights": "Nights",
            "electricity": "Electricity",
            "water": "Water",
            "internet": "Internet",
            "extra": "Extra",
            "total_bills": "Total Bills",
            "notes": "Notes"
        }
        df_bills_view = df_bills_view.rename(columns=col_rename_bills)

        df_bills_view["Month_dt"] = pd.to_datetime(df_bills_view["Month"], errors="coerce")
        df_bills_view["Year"] = df_bills_view["Month_dt"].dt.year.fillna(0).astype(int)
        df_bills_view["Month_num"] = df_bills_view["Month_dt"].dt.month

        for col in ["Electricity", "Water", "Internet", "Extra", "Total Bills"]:
            if col in df_bills_view.columns:
                df_bills_view[col] = pd.to_numeric(df_bills_view[col], errors="coerce").fillna(0)

        if not df_bookings_view.empty:
            notti_per_mese = df_bookings_view.groupby(["Year", "Month_num"])["Nights"].sum().reset_index()
            df_bills_view = pd.merge(df_bills_view, notti_per_mese, left_on=["Year", "Month_num"], right_on=["Year", "Month_num"], how="left", suffixes=("", "_calc"))
            if "Nights_calc" in df_bills_view.columns:
                df_bills_view["Nights"] = df_bills_view["Nights_calc"].fillna(0)
                df_bills_view = df_bills_view.drop(columns=["Nights_calc"])

        df_bills_view["Month_Display"] = df_bills_view["Month_dt"].dt.strftime("%b-%y")
    else:
        df_bills_view = pd.DataFrame()

    # --- NAVIGAZIONE LATERALE ---
    sezione = st.sidebar.radio(
        "Seleziona Sezione",
        [
            "Dashboard KPI", 
            "Prenotazioni (Bookings)", 
            "➕ Nuova Prenotazione", 
            "Spese (Bills)", 
            "🔮 Forecast & Pricing (Annuale)", 
            "📅 Calendario Dinamico (Mese)",
            "📥 Esporta Excel"
        ]
    )

    # ==========================================
    # 1. DASHBOARD KPI
    # ==========================================
    if sezione == "Dashboard KPI":
        st.header("📈 Dashboard Analitica e Indicatori KPI (Live Cloud)")

        kpi_scelta = st.selectbox(
            "Seleziona il modulo di analisi:",
            [
                "1. Channel Performance KPI",
                "2. Bills per Anno",
                "3. Revenue per Anno",
                "4. Costo Unitario x Night"
            ]
        )

        if kpi_scelta == "1. Channel Performance KPI" and not df_bookings_view.empty:
            st.subheader("1. Performance per Canale di Vendita")
            anni_singoli = sorted([y for y in df_bookings_view["Year"].unique() if y > 0], reverse=True)
            opzioni_anno = ["Tutti gli anni"] + [str(y) for y in anni_singoli]
            anno_selezionato = st.selectbox("Filtra per Anno", opzioni_anno, index=0)

            if anno_selezionato == "Tutti gli anni":
                df_filtrato = df_bookings_view[df_bookings_view["Year"] > 0]
                titolo_periodo = "Tutti gli anni"
            else:
                df_filtrato = df_bookings_view[df_bookings_view["Year"] == int(anno_selezionato)]
                titolo_periodo = anno_selezionato

            pivot_channel = df_filtrato.groupby("Channel").agg({
                "Nights": "sum",
                "Commission": "sum",
                "Cleaning Fee": "sum",
                "Net Price": "sum",
                "Gross Price": "sum"
            }).reset_index()

            total_gross = pivot_channel["Gross Price"].sum()
            pivot_channel["KPI %"] = (pivot_channel["Gross Price"] / total_gross * 100) if total_gross > 0 else 0

            totale_row = pd.DataFrame({
                "Channel": ["Totale"],
                "Nights": [pivot_channel["Nights"].sum()],
                "Commission": [pivot_channel["Commission"].sum()],
                "Cleaning Fee": [pivot_channel["Cleaning Fee"].sum()],
                "Net Price": [pivot_channel["Net Price"].sum()],
                "Gross Price": [pivot_channel["Gross Price"].sum()],
                "KPI %": [100.0]
            })
            pivot_channel = pd.concat([pivot_channel, totale_row], ignore_index=True)

            config_channel = {
                "Channel": st.column_config.TextColumn("Canale"),
                "Nights": st.column_config.NumberColumn("Notti", format="%d"),
                "Commission": st.column_config.NumberColumn("Commissione", format="€ %.2f"),
                "Cleaning Fee": st.column_config.NumberColumn("Cleaning Fee", format="€ %.2f"),
                "Net Price": st.column_config.NumberColumn("Net Price", format="€ %.2f"),
                "Gross Price": st.column_config.NumberColumn("Gross Price", format="€ %.2f"),
                "KPI %": st.column_config.NumberColumn("Quota %", format="%.2f%%"),
            }
            st.dataframe(pivot_channel, column_config=config_channel, hide_index=True)

            st.markdown("---")
            df_pie = pivot_channel[pivot_channel["Channel"] != "Totale"]
            if not df_pie.empty and total_gross > 0:
                fig, ax = plt.subplots(figsize=(6, 4))
                brand_colors = {"Airbnb": "#FF5A5F", "Booking": "#003580"}
                palette = ["#2E75B6", "#70AD47", "#FFC000", "#41719C", "#ED7D31", "#5B9BD5"]
                colors = [brand_colors.get(ch, palette[i % len(palette)]) for i, ch in enumerate(df_pie["Channel"])]

                ax.pie(
                    df_pie["Gross Price"],
                    labels=df_pie["Channel"],
                    autopct="%1.1f%%",
                    startangle=90,
                    colors=colors,
                    pctdistance=0.75,
                    wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
                    textprops=dict(size=9, weight="bold")
                )
                ax.set_title(f"Ripartizione Gross Price ({titolo_periodo})", fontsize=12, pad=12, weight="bold")
                
                c1, c2, c3 = st.columns([1, 2, 1])
                with c2:
                    st.pyplot(fig)

        elif kpi_scelta == "2. Bills per Anno" and not df_bills_view.empty:
            st.subheader("2. Consumi e Spese (Bills) per Anno")
            pivot_bills = df_bills_view[df_bills_view["Year"] > 0].groupby("Year").agg({
                "Nights": "sum",
                "Extra": "sum",
                "Electricity": "sum",
                "Internet": "sum",
                "Water": "sum",
                "Total Bills": "sum"
            }).reset_index()

            pivot_bills["Unit Cost (€/Night)"] = pivot_bills.apply(
                lambda row: (row["Total Bills"] / row["Nights"]) if row["Nights"] > 0 else 0, axis=1
            )

            total_bills_sum = pivot_bills["Total Bills"].sum()
            total_nights_sum = pivot_bills["Nights"].sum()
            pivot_bills["KPI %"] = (pivot_bills["Total Bills"] / total_bills_sum * 100) if total_bills_sum > 0 else 0

            totale_bills_row = pd.DataFrame({
                "Year": ["Totale"],
                "Nights": [total_nights_sum],
                "Extra": [pivot_bills["Extra"].sum()],
                "Electricity": [pivot_bills["Electricity"].sum()],
                "Internet": [pivot_bills["Internet"].sum()],
                "Water": [pivot_bills["Water"].sum()],
                "Total Bills": [total_bills_sum],
                "Unit Cost (€/Night)": [(total_bills_sum / total_nights_sum) if total_nights_sum > 0 else 0],
                "KPI %": [100.0]
            })
            pivot_bills = pd.concat([pivot_bills, totale_bills_row], ignore_index=True)

            config_bills_kpi = {
                "Year": st.column_config.TextColumn("Anno"),
                "Nights": st.column_config.NumberColumn("Notti", format="%d"),
                "Extra": st.column_config.NumberColumn("Extra", format="€ %.2f"),
                "Electricity": st.column_config.NumberColumn("Electricity", format="€ %.2f"),
                "Internet": st.column_config.NumberColumn("Internet", format="€ %.2f"),
                "Water": st.column_config.NumberColumn("Water", format="€ %.2f"),
                "Total Bills": st.column_config.NumberColumn("Total Bills", format="€ %.2f"),
                "Unit Cost (€/Night)": st.column_config.NumberColumn("Costo/Notte", format="€ %.2f"),
                "KPI %": st.column_config.NumberColumn("Quota %", format="%.2f%%"),
            }
            st.dataframe(pivot_bills, column_config=config_bills_kpi, hide_index=True)

        elif kpi_scelta == "3. Revenue per Anno" and not df_bookings_view.empty:
            st.subheader("3. Sintesi Ricavi e Profitto Netto per Anno")
            pivot_rev = df_bookings_view[df_bookings_view["Year"] > 0].groupby("Year").agg({
                "Client": "count",
                "Nights": "sum",
                "Commission": "sum",
                "Cleaning Fee": "sum",
                "Gross Price": "sum",
                "Net Price": "sum"
            }).rename(columns={"Client": "Bookings"}).reset_index()

            pivot_rev["Net Profit"] = pivot_rev["Net Price"] * 0.8
            total_net_profit = pivot_rev["Net Profit"].sum()
            pivot_rev["KPI %"] = (pivot_rev["Net Profit"] / total_net_profit * 100) if total_net_profit > 0 else 0

            totale_rev_row = pd.DataFrame({
                "Year": ["Totale"],
                "Bookings": [pivot_rev["Bookings"].sum()],
                "Nights": [pivot_rev["Nights"].sum()],
                "Commission": [pivot_rev["Commission"].sum()],
                "Cleaning Fee": [pivot_rev["Cleaning Fee"].sum()],
                "Gross Price": [pivot_rev["Gross Price"].sum()],
                "Net Price": [pivot_rev["Net Price"].sum()],
                "Net Profit": [pivot_rev["Net Profit"].sum()],
                "KPI %": [100.0]
            })
            pivot_rev = pd.concat([pivot_rev, totale_rev_row], ignore_index=True)

            config_rev = {
                "Year": st.column_config.TextColumn("Anno"),
                "Bookings": st.column_config.NumberColumn("Prenotazioni", format="%d"),
                "Nights": st.column_config.NumberColumn("Notti", format="%d"),
                "Commission": st.column_config.NumberColumn("Commissioni", format="€ %.2f"),
                "Cleaning Fee": st.column_config.NumberColumn("Cleaning Fee", format="€ %.2f"),
                "Gross Price": st.column_config.NumberColumn("Gross Price", format="€ %.2f"),
                "Net Price": st.column_config.NumberColumn("Net Price", format="€ %.2f"),
                "Net Profit": st.column_config.NumberColumn("Net Profit (80%)", format="€ %.2f"),
                "KPI %": st.column_config.NumberColumn("Quota %", format="%.2f%%"),
            }
            st.dataframe(pivot_rev, column_config=config_rev, hide_index=True)

        elif kpi_scelta == "4. Costo Unitario x Night" and not df_bookings_view.empty and not df_bills_view.empty:
            st.subheader("4. Costo Unitario e Pricing Strategy per Notte")
            notti_anno = df_bookings_view[df_bookings_view["Year"] > 0].groupby("Year")["Nights"].sum()
            comm_anno = df_bookings_view[df_bookings_view["Year"] > 0].groupby("Year")["Commission"].sum()
            clean_anno = df_bookings_view[df_bookings_view["Year"] > 0].groupby("Year")["Cleaning Fee"].sum()

            bills_anno = df_bills_view[df_bills_view["Year"] > 0].groupby("Year").agg({
                "Extra": "sum",
                "Electricity": "sum",
                "Internet": "sum",
                "Water": "sum",
                "Total Bills": "sum"
            })

            df_costi = bills_anno.copy()
            df_costi["Nights"] = notti_anno
            df_costi["Channel Fee"] = comm_anno
            df_costi["Cleaning Fee"] = clean_anno
            df_costi = df_costi.fillna(0)

            unit_table = pd.DataFrame()
            unit_table["Nights"] = df_costi["Nights"]

            for col in ["Extra", "Electricity", "Internet", "Water", "Total Bills", "Channel Fee", "Cleaning Fee"]:
                unit_table[col] = df_costi.apply(
                    lambda row: (row[col] / row["Nights"]) if row["Nights"] > 0 else 0, axis=1
                )

            unit_table["Total Costs"] = unit_table[["Extra", "Electricity", "Internet", "Water", "Channel Fee", "Cleaning Fee"]].sum(axis=1)
            unit_table["Mark up"] = 3.50
            unit_table["Final Price"] = unit_table["Total Costs"] * unit_table["Mark up"]

            unit_table = unit_table.reset_index()

            tot_nights = unit_table["Nights"].sum()
            tot_row = {"Year": "Totale", "Nights": tot_nights}
            for col in ["Extra", "Electricity", "Internet", "Water", "Total Bills", "Channel Fee", "Cleaning Fee"]:
                tot_row[col] = (df_costi[col].sum() / tot_nights) if tot_nights > 0 else 0
            
            tot_row["Total Costs"] = sum([tot_row[c] for c in ["Extra", "Electricity", "Internet", "Water", "Channel Fee", "Cleaning Fee"]])
            tot_row["Mark up"] = 3.50
            tot_row["Final Price"] = tot_row["Total Costs"] * tot_row["Mark up"]

            unit_table = pd.concat([unit_table, pd.DataFrame([tot_row])], ignore_index=True)

            config_unit = {
                "Year": st.column_config.TextColumn("Anno"),
                "Nights": st.column_config.NumberColumn("Notti", format="%d"),
                "Extra": st.column_config.NumberColumn("Extra", format="€ %.2f"),
                "Electricity": st.column_config.NumberColumn("Electricity", format="€ %.2f"),
                "Internet": st.column_config.NumberColumn("Internet", format="€ %.2f"),
                "Water": st.column_config.NumberColumn("Water", format="€ %.2f"),
                "Total Bills": st.column_config.NumberColumn("Total Bills", format="€ %.2f"),
                "Channel Fee": st.column_config.NumberColumn("Commission", format="€ %.2f"),
                "Cleaning Fee": st.column_config.NumberColumn("Cleaning", format="€ %.2f"),
                "Total Costs": st.column_config.NumberColumn("Total Costs", format="€ %.2f"),
                "Mark up": st.column_config.NumberColumn("Mark up", format="%.2f"),
                "Final Price": st.column_config.NumberColumn("Final Price", format="€ %.2f"),
            }
            st.dataframe(unit_table, column_config=config_unit, hide_index=True)

    # ==========================================
    # 2. PRENOTAZIONI (EDIT & DELETE IN CLOUD)
    # ==========================================
    elif sezione == "Prenotazioni (Bookings)":
        st.header("📋 Registro Prenotazioni Cloud")
        st.info("💡 Fai doppio clic per modificare i valori, oppure seleziona una o più righe e premi 'Canc' o 'Delete' per eliminarle. Clicca poi su 'Sincronizza Modifiche' per salvare nel cloud.")

        colonne_mostrate = [
            "N Revs", "Client", "Channel", "Fee Type", "Contact", 
            "N People", "Nationality", "Check-In", "Check-Out", 
            "Nights", "Gross Price", "Commission", "Cleaning Fee", "Net Price"
        ]

        df_editor = df_bookings_view[colonne_mostrate].copy()
        df_editor["Check-In"] = pd.to_datetime(df_editor["Check-In"], errors="coerce").dt.date
        df_editor["Check-Out"] = pd.to_datetime(df_editor["Check-Out"], errors="coerce").dt.date

        editor_config = {
            "N Revs": st.column_config.NumberColumn("ID", disabled=True),
            "Commission": st.column_config.NumberColumn("Commission", format="€ %.2f"),
            "Gross Price": st.column_config.NumberColumn("Gross Price", format="€ %.2f"),
            "Cleaning Fee": st.column_config.NumberColumn("Cleaning Fee", format="€ %.2f"),
            "Net Price": st.column_config.NumberColumn("Net Price", format="€ %.2f"),
            "Check-In": st.column_config.DateColumn("Check-In", format="DD/MM/YYYY"),
            "Check-Out": st.column_config.DateColumn("Check-Out", format="DD/MM/YYYY"),
        }

        edited_df = st.data_editor(
            df_editor,
            num_rows="dynamic",
            column_config=editor_config,
            hide_index=True,
            key="bookings_editor"
        )

        if st.button("💾 Sincronizza Modifiche su Supabase"):
            try:
                id_originali = set(df_editor["N Revs"].dropna().astype(int))
                id_rimasti = set(edited_df["N Revs"].dropna().astype(int))
                id_da_cancellare = list(id_originali - id_rimasti)

                if id_da_cancellare:
                    supabase.table("bookings").delete().in_("id", id_da_cancellare).execute()

                updated_records = []
                for _, r in edited_df.iterrows():
                    d_in = pd.to_datetime(r["Check-In"]).date() if pd.notna(r["Check-In"]) else None
                    d_out = pd.to_datetime(r["Check-Out"]).date() if pd.notna(r["Check-Out"]) else None
                    
                    record = {
                        "id": int(r["N Revs"]),
                        "client": str(r["Client"]) if pd.notna(r["Client"]) else "",
                        "channel": str(r["Channel"]) if pd.notna(r["Channel"]) else "",
                        "fee_type": str(r.get("Fee Type", "")) if pd.notna(r.get("Fee Type")) else "",
                        "contact": str(r.get("Contact", "")) if pd.notna(r.get("Contact")) else "",
                        "n_people": int(r.get("N People", 1)) if pd.notna(r.get("N People")) else 1,
                        "nationality": str(r.get("Nationality", "")) if pd.notna(r.get("Nationality")) else "",
                        "check_in": str(d_in) if d_in else None,
                        "check_out": str(d_out) if d_out else None,
                        "nights": int(r.get("Nights", 0)) if pd.notna(r.get("Nights")) else 0,
                        "gross_price": float(r.get("Gross Price", 0)) if pd.notna(r.get("Gross Price")) else 0.0,
                        "commission": float(r.get("Commission", 0)) if pd.notna(r.get("Commission")) else 0.0,
                        "cleaning_fee": float(r.get("Cleaning Fee", 10)) if pd.notna(r.get("Cleaning Fee")) else 10.0,
                        "net_price": float(r.get("Net Price", 0)) if pd.notna(r.get("Net Price")) else 0.0,
                        "month": d_in.strftime("%Y-%m-01") if d_in else None,
                        "year": d_in.year if d_in else 0
                    }
                    updated_records.append(record)

                if updated_records:
                    supabase.table("bookings").upsert(updated_records).execute()

                st.success("✅ Modifiche e cancellazioni sincronizzate con successo!")
                st.rerun()
            except Exception as ex:
                st.error(f"Errore durante la sincronizzazione: {ex}")

    # ==========================================
    # 3. NUOVA PRENOTAZIONE (SCRITTURA DIRETTA)
    # ==========================================
    elif sezione == "➕ Nuova Prenotazione":
        st.header("➕ Nuova Prenotazione Cloud")

        with st.form("form_prenotazione_cloud", clear_on_submit=True):
            st.info("Calcolo automatico di Commissioni, Spese pulizia (10€) e ID 'N Revs'.")

            col1, col2 = st.columns(2)
            with col1:
                client = st.text_input("Nome Cliente *")
                channel = st.selectbox("Canale di Vendita *", ["Ali", "Ayoub", "Younes", "Booking", "Airbnb", "Altro"])
                n_people = st.number_input("Numero Persone", min_value=1, max_value=5, step=1)
                nationality = st.text_input("Nazionalità")
                contact = st.text_input("Contatto (Telefono)")

            with col2:
                check_in = st.date_input("Data di Check-In *")
                check_out = st.date_input("Data di Check-Out *")
                gross_price = st.number_input("Prezzo Lordo (Gross Price) € *", min_value=0.0, step=10.0, format="%.2f")

            submitted = st.form_submit_button("🚀 Salva Subito nel Cloud")

            if submitted:
                if not client:
                    st.error("Il Nome Cliente è obbligatorio!")
                elif check_out <= check_in:
                    st.error("La data di Check-Out deve essere successiva al Check-In!")
                else:
                    nights = (check_out - check_in).days
                    cleaning_fee = 10.0

                    if channel == "Airbnb":
                        fee_type = "E-Platform"
                        commission = gross_price * 0.155
                    elif channel == "Booking":
                        fee_type = "E-Platform"
                        commission = gross_price * 0.19
                    elif channel == "Younes":
                        fee_type = "None"
                        commission = 0.0
                    else:
                        fee_type = "Dealer"
                        commission = 10.0 * nights

                    net_price = gross_price - commission - cleaning_fee

                    res_max = supabase.table("bookings").select("id").order("id", desc=True).limit(1).execute()
                    last_id = res_max.data[0]["id"] if res_max.data else 0
                    new_id = last_id + 1

                    nuovo_record = {
                        "id": new_id,
                        "client": client,
                        "channel": channel,
                        "fee_type": fee_type,
                        "contact": contact,
                        "n_people": n_people,
                        "nationality": nationality,
                        "check_in": str(check_in),
                        "check_out": str(check_out),
                        "nights": nights,
                        "gross_price": gross_price,
                        "commission": round(commission, 2),
                        "cleaning_fee": cleaning_fee,
                        "net_price": round(net_price, 2),
                        "month": check_in.strftime("%Y-%m-01"),
                        "year": check_in.year
                    }

                    try:
                        supabase.table("bookings").insert(nuovo_record).execute()
                        st.success(f"✅ Prenotazione creata sul Cloud! ID #{new_id} | Notti: {nights} | Netto: {net_price:.2f}€")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Errore durante l'inserimento: {ex}")

    # ==========================================
    # 4. SPESE (BILLS)
    # ==========================================
    elif sezione == "Spese (Bills)":
        st.header("💡 Registro Spese e Bollette")

        if not df_bills_view.empty:
            df_bills_show = df_bills_view[["Year", "Month_Display", "Nights", "Electricity", "Water", "Internet", "Extra", "Total Bills", "Notes"]].copy()
            df_bills_show = df_bills_show.rename(columns={"Month_Display": "Month"})

            df_bills_show["Unit Cost (€/Night)"] = df_bills_show.apply(
                lambda row: (row["Total Bills"] / row["Nights"]) if row["Nights"] > 0 else 0, axis=1
            )

            config_bills = {
                "Year": st.column_config.TextColumn("Anno"),
                "Month": st.column_config.TextColumn("Mese"),
                "Nights": st.column_config.NumberColumn("Notti", format="%d"),
                "Electricity": st.column_config.NumberColumn("Electricity", format="€ %.2f"),
                "Water": st.column_config.NumberColumn("Water", format="€ %.2f"),
                "Internet": st.column_config.NumberColumn("Internet", format="€ %.2f"),
                "Extra": st.column_config.NumberColumn("Extra", format="€ %.2f"),
                "Total Bills": st.column_config.NumberColumn("Total Bills", format="€ %.2f"),
                "Unit Cost (€/Night)": st.column_config.NumberColumn("Costo Unitario (€/Notte)", format="€ %.2f"),
                "Notes": st.column_config.TextColumn("Note")
            }
            st.dataframe(df_bills_show, column_config=config_bills, hide_index=True)

    # ==========================================
    # 5. FORECAST & PRICING ANNUALE
    # ==========================================
    elif sezione == "🔮 Forecast & Pricing (Annuale)":
        st.header("🔮 Forecast Economico e Pricing Strategy (2026 - 2027)")
        st.info("Consuntivo effettivo (**Actual**) fino a Ottobre 2026. Da Novembre 2026 a Dicembre 2027 calcolo del **Budget/Forecast** basato sul costo unitario storico consolidato e sul markup protetto (minimo 2.88).")

        hist_b = df_bookings_view[df_bookings_view["Year"] < 2026]
        hist_bi = df_bills_view[df_bills_view["Year"] < 2026]

        tot_hist_nights = hist_b["Nights"].sum()
        tot_hist_comm = hist_b["Commission"].sum()
        tot_hist_clean = hist_b["Cleaning Fee"].sum()
        tot_hist_bills = hist_bi["Total Bills"].sum()

        unit_cost_base = ((tot_hist_bills + tot_hist_comm + tot_hist_clean) / tot_hist_nights) if tot_hist_nights > 0 else 14.31

        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
        c_kpi1.metric("Costo Unitario Base (Storico)", f"€ {unit_cost_base:.2f} / notte")
        c_kpi2.metric("Markup Floor (Minimo)", "2.88x", delta="Soglia protetta")
        c_kpi3.metric("Markup Target (Standard)", "3.50x")

        st.markdown("---")

        monthly_hist = df_bookings_view[df_bookings_view["Year"] > 0].groupby(["Year", "Month_num"]).agg({
            "Nights": "sum",
            "Gross Price": "sum"
        }).reset_index()
        monthly_hist["ADR"] = monthly_hist.apply(
            lambda r: (r["Gross Price"] / r["Nights"]) if r["Nights"] > 0 else 0.0, axis=1
        )

        month_names = {
            1: "01 - Gen", 2: "02 - Feb", 3: "03 - Mar", 4: "04 - Apr",
            5: "05 - Mag", 6: "06 - Giu", 7: "07 - Lug", 8: "08 - Ago",
            9: "09 - Set", 10: "10 - Ott", 11: "11 - Nov", 12: "12 - Dic"
        }

        rows_forecast = []
        periodi = [(2026, m) for m in range(1, 13)] + [(2027, m) for m in range(1, 13)]

        for y, m in periodi:
            ly_row = monthly_hist[(monthly_hist["Year"] == y - 1) & (monthly_hist["Month_num"] == m)]
            price_ly = float(ly_row["ADR"].iloc[0]) if not ly_row.empty else 0.0

            if y == 2026 and m <= 10:
                stato = "Actual"
                curr_row = monthly_hist[(monthly_hist["Year"] == y) & (monthly_hist["Month_num"] == m)]
                notti = int(curr_row["Nights"].iloc[0]) if not curr_row.empty else 0
                price_fct = float(curr_row["ADR"].iloc[0]) if not curr_row.empty else 0.0
                markup_used = (price_fct / unit_cost_base) if unit_cost_base > 0 and price_fct > 0 else 0.0
                cost_base = unit_cost_base
                revenue = price_fct * notti
            else:
                stato = "Budget"
                ly_nights = int(ly_row["Nights"].iloc[0]) if not ly_row.empty else 0
                notti = ly_nights if ly_nights > 0 else 14
                default_markup = 2.88 if m in [1, 2, 11] else 3.50
                markup_used = default_markup
                cost_base = unit_cost_base
                price_fct = round(cost_base * markup_used, 2)
                revenue = round(price_fct * notti, 2)

            var_pct = ((price_fct - price_ly) / price_ly * 100) if price_ly > 0 else 0.0

            rows_forecast.append({
                "Year": y,
                "Month_num": m,
                "Mese": month_names[m],
                "Stato": stato,
                "Notti": notti,
                "Costo Base": cost_base,
                "Mark up": markup_used,
                "Price LY": price_ly,
                "Price FCT / Actual": price_fct,
                "Var vs LY %": var_pct,
                "Revenue (€)": revenue
            })

        df_fct = pd.DataFrame(rows_forecast)

        col_cfg_fct = {
            "Year": st.column_config.TextColumn("Anno"),
            "Mese": st.column_config.TextColumn("Mese"),
            "Stato": st.column_config.TextColumn("Stato"),
            "Notti": st.column_config.NumberColumn("Notti", format="%d"),
            "Costo Base": st.column_config.NumberColumn("Costo Base", format="€ %.2f"),
            "Mark up": st.column_config.NumberColumn("Mark up", format="%.2f", min_value=2.88),
            "Price LY": st.column_config.NumberColumn("Price LY (ADR)", format="€ %.2f"),
            "Price FCT / Actual": st.column_config.NumberColumn("Price FCT / Actual", format="€ %.2f"),
            "Var vs LY %": st.column_config.NumberColumn("Var %", format="%.1f%%"),
            "Revenue (€)": st.column_config.NumberColumn("Ricavo Previsto", format="€ %.2f"),
        }

        filtro_anno_fct = st.radio("Anno di Analisi:", ["2026", "2027", "Tutto il Biennio"], horizontal=True)

        if filtro_anno_fct == "2026":
            df_fct_view = df_fct[df_fct["Year"] == 2026].drop(columns=["Month_num"])
        elif filtro_anno_fct == "2027":
            df_fct_view = df_fct[df_fct["Year"] == 2027].drop(columns=["Month_num"])
        else:
            df_fct_view = df_fct.drop(columns=["Month_num"])

        st.dataframe(df_fct_view, column_config=col_cfg_fct, hide_index=True)

    # ==========================================
    # 6. CALENDARIO DINAMICO & FORECAST GIORNALIERO
    # ==========================================
    elif sezione == "📅 Calendario Dinamico (Mese)":
        st.header("📅 Calendario Dinamico & Pricing Giornaliero")
        st.write("Analisi tariffaria giornaliera che adatta il prezzo base ai **weekend (+20%)**, alle **festività/Capodanno (+35% / +60%)** e allo storico dell'anno precedente.")

        # Parametri costo base storico
        hist_b = df_bookings_view[df_bookings_view["Year"] < 2026]
        hist_bi = df_bills_view[df_bills_view["Year"] < 2026]
        tot_hist_nights = hist_b["Nights"].sum()
        tot_hist_costs = hist_bi["Total Bills"].sum() + hist_b["Commission"].sum() + hist_b["Cleaning Fee"].sum()
        unit_cost = (tot_hist_costs / tot_hist_nights) if tot_hist_nights > 0 else 14.31

        col_sel1, col_sel2, col_sel3 = st.columns(3)
        with col_sel1:
            sel_anno = st.selectbox("Anno:", [2026, 2027], index=0)
        with col_sel2:
            nomi_mesi_it = [
                "1 - Gennaio", "2 - Febbraio", "3 - Marzo", "4 - Aprile", 
                "5 - Maggio", "6 - Giugno", "7 - Luglio", "8 - Agosto", 
                "9 - Settembre", "10 - Ottobre", "11 - Novembre", "12 - Dicembre"
            ]
            sel_mese_str = st.selectbox("Mese:", nomi_mesi_it, index=10) # Default Novembre
            sel_mese = int(sel_mese_str.split(" - ")[0])
        with col_sel3:
            markup_floor = st.number_input("Markup Minimo (Floor):", value=2.88, min_value=2.00, step=0.05, format="%.2f")

        prezzo_floor_assoluto = round(unit_cost * markup_floor, 2)
        st.caption(f"ℹ️ **Costo Base:** € {unit_cost:.2f}/notte | **Prezzo Minimo Floor (x{markup_floor:.2f}):** € {prezzo_floor_assoluto:.2f}")

        # Costruzione del calendario del mese
        num_days = calendar.monthrange(sel_anno, sel_mese)[1]
        giorni_settimana = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

        # Espansione delle prenotazioni su singoli giorni per matching rapido
        # Storico anno precedente per Price LY
        def get_booking_for_date(target_date, df_source):
            if df_source.empty:
                return None
            for _, b in df_source.iterrows():
                if pd.notna(b["Check-In_dt"]) and pd.notna(b["Check-Out_dt"]):
                    d_in = b["Check-In_dt"].date()
                    d_out = b["Check-Out_dt"].date()
                    # Se la data cade nel soggiorno (la notte di soggiorno)
                    if d_in <= target_date < d_out:
                        adr = (b["Gross Price"] / b["Nights"]) if b["Nights"] > 0 else 0
                        return {"client": b["Client"], "channel": b["Channel"], "adr": adr, "gross": b["Gross Price"]}
            return None

        righe_calendario = []

        for day in range(1, num_days + 1):
            curr_date = date(sel_anno, sel_mese, day)
            weekday_idx = curr_date.weekday()
            nome_giorno = giorni_settimana[weekday_idx]
            is_weekend = weekday_idx in [4, 5]  # Venerdì o Sabato sera

            # Riconoscimento Festività speciali
            tipo_giorno = "Standard"
            moltiplicatore_evento = 1.0

            # Capodanno / Natale / Ponti
            if sel_mese == 12 and day == 31:
                tipo_giorno = "🎉 Notte di San Silvestro / Capodanno"
                moltiplicatore_evento = 1.60
            elif sel_mese == 1 and day == 1:
                tipo_giorno = "🎉 Capodanno"
                moltiplicatore_evento = 1.50
            elif sel_mese == 12 and day in [24, 25, 26]:
                tipo_giorno = "🎄 Festività Natalizie"
                moltiplicatore_evento = 1.35
            elif sel_mese == 12 and day in [6, 7, 8]:
                tipo_giorno = "⭐ Ponte Immacolata"
                moltiplicatore_evento = 1.30
            elif sel_mese == 8 and day in [14, 15]:
                tipo_giorno = "☀️ Ferragosto"
                moltiplicatore_evento = 1.40
            elif is_weekend:
                tipo_giorno = "Weekend"
                moltiplicatore_evento = 1.20

            # Markup base applicato (3.50 target standard)
            base_markup = 3.50
            effettivo_markup = max(markup_floor, base_markup * moltiplicatore_evento)
            prezzo_calcolato = round(unit_cost * effettivo_markup, 2)

            # Cerca se l'anno precedente c'era una prenotazione lo stesso giorno
            date_ly = date(sel_anno - 1, sel_mese, day)
            b_ly = get_booking_for_date(date_ly, df_bookings_view)
            price_ly = b_ly["adr"] if b_ly else 0.0

            # Cerca se oggi c'è già una prenotazione confermata
            b_now = get_booking_for_date(curr_date, df_bookings_view)

            if b_now:
                stato_giorno = "🔴 VENDUTO"
                dettaglio_booking = f"{b_now['client']} ({b_now['channel']})"
                prezzo_finale_giorno = b_now["adr"]
            else:
                stato_giorno = "🟢 DISPONIBILE"
                dettaglio_booking = "—"
                # Il prezzo consigliato è il massimo tra il prezzo calcolato e il minimo floor
                prezzo_finale_giorno = max(prezzo_calcolato, prezzo_floor_assoluto)

            righe_calendario.append({
                "Data": curr_date.strftime("%d/%m/%Y"),
                "Giorno": nome_giorno,
                "Tipo Data": tipo_giorno,
                "Stato": stato_giorno,
                "Prenotazione": dettaglio_booking,
                "Price LY": price_ly,
                "Floor Minimo": prezzo_floor_assoluto,
                "Prezzo Forecast / Applicato": round(prezzo_finale_giorno, 2),
            })

        df_cal = pd.DataFrame(righe_calendario)

        config_cal = {
            "Data": st.column_config.TextColumn("Data"),
            "Giorno": st.column_config.TextColumn("Giorno"),
            "Tipo Data": st.column_config.TextColumn("Tipologia Tariffaria"),
            "Stato": st.column_config.TextColumn("Stato"),
            "Prenotazione": st.column_config.TextColumn("Ospite Attuale"),
            "Price LY": st.column_config.NumberColumn("Prezzo LY", format="€ %.2f"),
            "Floor Minimo": st.column_config.NumberColumn("Prezzo Floor (Min)", format="€ %.2f"),
            "Prezzo Forecast / Applicato": st.column_config.NumberColumn("Prezzo Suggerito / Effettivo", format="€ %.2f"),
        }

        st.dataframe(df_cal, column_config=config_cal, hide_index=True)

        # Statistiche veloci del mese
        notti_occupate = len(df_cal[df_cal["Stato"] == "🔴 VENDUTO"])
        notti_libere = num_days - notti_occupate
        adr_medio_mese = df_cal["Prezzo Forecast / Applicato"].mean()

        m1, m2, m3 = st.columns(3)
        m1.metric("Notti Vendute / Confermate", f"{notti_occupate} / {num_days}")
        m2.metric("Notti Disponibili da Vendere", f"{notti_libere} notti")
        m3.metric("Tariffa Media Consigliata (ADR)", f"€ {adr_medio_mese:.2f}")

    # ==========================================
    # 7. ESPORTA EXCEL A RICHIESTA
    # ==========================================
    elif sezione == "📥 Esporta Excel":
        st.header("📥 Esportazione Dati in Excel")
        st.write("Genera una copia aggiornata in formato `.xlsx` con tutti i dati attuali presenti nel cloud.")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_bookings_view.to_excel(writer, sheet_name="BOOKINGS", index=False)
            if not df_bills_view.empty:
                df_bills_view.to_excel(writer, sheet_name="BILLS", index=False)

        st.download_button(
            label="⬇️ Scarica draft al badiya.xlsx Aggiornato",
            data=buffer.getvalue(),
            file_name=f"al_badiya_backup_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

except Exception as e:
    st.error(f"Errore durante l'elaborazione dei dati: {e}")