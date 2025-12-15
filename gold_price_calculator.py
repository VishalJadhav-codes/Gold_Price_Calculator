# =====================================================
# IMPORT LIBRARIES
# =====================================================
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta
import os

# -----------------------------------------------------
# Optional: ReportLab for PDF Invoice
# -----------------------------------------------------
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# =====================================================
# APP CONFIGURATION
# =====================================================
st.set_page_config(page_title="Gold Shop & Price Tool", layout="wide")

os.makedirs("invoices", exist_ok=True)
os.makedirs("exports", exist_ok=True)

# ---- Session State Safe Init ----
if "transactions" not in st.session_state:
    st.session_state["transactions"] = []

if "bill_counter" not in st.session_state:
    st.session_state["bill_counter"] = 0

if "last_bill" not in st.session_state:
    st.session_state["last_bill"] = None


# =====================================================
# DARK MODE
# =====================================================
def inject_dark_mode(dark: bool):
    if dark:
        st.markdown(
            """
            <style>
            .main { background-color: #0e1117; color: #e6eef6; }
            </style>
            """,
            unsafe_allow_html=True
        )


# =====================================================
# PURITY MAPPING
# =====================================================
PURITY = {24: 0.999, 22: 0.916, 20: 0.833, 18: 0.750}


# =====================================================
# HISTORICAL PRICE (SIMULATED)
# =====================================================
def simulate_historical(base_rate_24k, days=90, volatility=0.01):
    dates = [datetime.today() - timedelta(days=i) for i in range(days)][::-1]
    price = base_rate_24k
    prices = []

    for _ in range(days):
        price *= (1 + np.random.normal(0, volatility))
        prices.append(max(price, 1000))

    return pd.DataFrame({"date": dates, "price_24k": prices})


# =====================================================
# PRICE CONVERSION
# =====================================================
def price_for_carat(price_24k, carat):
    return price_24k * (PURITY[carat] / PURITY[24])


# =====================================================
# BILL NUMBER
# =====================================================
def generate_bill_number():
    st.session_state["bill_counter"] += 1
    today = datetime.now().strftime("%Y%m%d")
    return f"INV-{today}-{st.session_state['bill_counter']:04d}"


# =====================================================
# PDF INVOICE
# =====================================================
def generate_invoice_pdf(bill):
    path = f"invoices/{bill['bill_no']}.pdf"
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    y = h - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "GOLD SHOP INVOICE")

    y -= 40
    c.setFont("Helvetica", 10)
    for k, v in bill.items():
        c.drawString(50, y, f"{k.replace('_',' ').title()}: {v}")
        y -= 18

    c.showPage()
    c.save()
    return path


# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.header("Settings")

dark_mode = st.sidebar.checkbox("Dark Mode")
inject_dark_mode(dark_mode)

manual_24k = st.sidebar.number_input(
    "Manual 24K Rate (₹/gram)", 1000.0, 20000.0, 6000.0
)

shop_mode = st.sidebar.checkbox("Enable Shop Mode", value=True)


# =====================================================
# MAIN LAYOUT
# =====================================================
col_left, col_right = st.columns([2, 1])


# =====================================================
# LEFT COLUMN
# =====================================================
with col_left:

    st.header("Gold Price Calculator")

    with st.form("calc_form"):
        carat = st.selectbox("Carat", [24, 22, 20, 18], index=1)
        grams = st.number_input("Weight (grams)", 0.01, value=10.0)
        item_name = st.text_input("Item Name", "Gold Ring")
        making_type = st.radio("Making Charge Type", ["% of gold value", "₹ per gram"])
        making_val = st.number_input("Making Value", 0.0, value=2.0)
        wastage_percent = st.number_input("Wastage (%)", 0.0, value=0.0)
        hallmark_charge = st.number_input("Hallmark Charge (₹)", 0.0, value=50.0)
        gst = st.number_input("GST (%)", 0.0, value=3.0)
        submitted = st.form_submit_button("Calculate")

    if submitted:
        rate_per_g = price_for_carat(manual_24k, carat)
        effective_grams = grams * (1 + wastage_percent / 100)
        gold_value = rate_per_g * effective_grams

        making_charge = (
            gold_value * making_val / 100
            if making_type == "% of gold value"
            else making_val * effective_grams
        )

        pre_tax = gold_value + making_charge + hallmark_charge
        gst_amount = pre_tax * gst / 100
        final_price = pre_tax + gst_amount

        bill_no = generate_bill_number()

        st.session_state["last_bill"] = {
            "bill_no": bill_no,
            "item": item_name,
            "carat": carat,
            "grams": grams,
            "gold_value": round(gold_value, 2),
            "making_charge": round(making_charge, 2),
            "gst": round(gst_amount, 2),
            "final_price": round(final_price, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        st.metric("Final Bill (₹)", f"{final_price:,.2f}")
        st.write(f"Invoice No: **{bill_no}**")

    # ---------- SAVE + PDF ----------
    if shop_mode and st.session_state["last_bill"]:
        if st.button("💾 Save Transaction"):
            st.session_state["transactions"].append(st.session_state["last_bill"])
            st.success("Transaction Saved")

        if REPORTLAB_AVAILABLE:
            pdf = generate_invoice_pdf(st.session_state["last_bill"])
            with open(pdf, "rb") as f:
                st.download_button("📄 Download Invoice", f, file_name=os.path.basename(pdf))


# =====================================================
# RIGHT COLUMN
# =====================================================
with col_right:

    st.header("Shop Dashboard")

    if st.session_state["transactions"]:
        df = pd.DataFrame(st.session_state["transactions"])
        st.dataframe(df.sort_values("timestamp", ascending=False))
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode(),
            "transactions.csv"
        )
    else:
        st.info("No transactions saved yet.")
