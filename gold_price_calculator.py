import streamlit as st
import pandas as pd
import numpy as np
import requests
import altair as alt
import os
from datetime import datetime, timedelta

# App Config
st.set_page_config(page_title="Gold Shop & Price Tool", layout="wide", initial_sidebar_state="expanded")

# Helper : Dark Mode CSS
def inject_dark_mode(dark: bool):
    if dark:
        st.markdown(
            """

            <style>
            .main { background-color: #0e1117; color: #e6eef6; }
            .stButton>button { background-color:#1f6feb; color:#fff }
            .st-breadcrumb, css-1d391kg { color:#0e6eef6 }
            .css-1kyxreq{background-color:#0e1117}
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("", unsafe_allow_html=True)

# Helper: Purity factor
PURITY = {24: 0.999, 22: 0.916, 20: 0.833, 18: 0.750}

# Historical Price Genrater
def simulate_historical(base_rate_24k: float, days: int = 60, volatility: float = 0.01):
    """
    Create a simple realistic-looking historical series using geometric Brownian-like walk.
    Returns DataFrame with date and price_24k.
    """
    dates = [datetime.today().date() - timedelta(days=i) for i in range(days)][::-1]
    prices = []
    price = base_rate_24k
    for _ in range(days):
        shock = np.random.normal(loc=0.0, scale=volatility) # Small daily percent move
        price = max(1000.0, price * (1 + shock))
        prices.append(price)
    df_hist = pd.DataFrame({"data": dates, "Price_24k": prices})
    return df_hist

# Utitlity: Compute 22k price from 24k
def price_for_carat(price_24k, carat):
    # Purity Fraction Approach
    if carat in PURITY:
        return price_24k * PURITY[carat] / PURITY[24] # relative to 24k
    else:
        return price_24k * (carat / 24.0)

# UI: Sidebar Controls
st.sidebar.header("Setting & Rates")

# Dark Mode Toggle
dark_mode = st.sidebar.checkbox("Dark Mode", value=False)
inject_dark_mode(dark_mode)

# Manual override / fallback  rate (per gram for 24k)
manual_24k = st.sidebar.number_input("Manual 24k rate (₹/gram) - fallback", min_value=1000.0, max_value=20000.0, value=6000.0, step=1.0)

# Toggle : show shop mode
shop_mode = st.sidebar.checkbox("Enable Professional Shop Mode", value=True)

# Main Layout
col_left, col_right = st.columns([2,1])

with col_left:
    st.header("Gold Price Calculator")

    # User Inputs
    with st.form("calc_form"):
        st.subheader("Enter item details")
        col1, col2, col3 = st.columns(3)
        with col1:
            carat = st.selectbox("Carat (Purity)", options=[24, 22, 20, 18], index=1)
            grams = st.number_input("Weight (grams)", min_value=0.01, value=10.0)
            item_name = st.text_input("Item decription (optional)", value="Gold Ring")
        with col2:
            making_type = st.radio("Making charge type", options=["% of gold", "₹per gram"], index=0)
            making_val = st.number_input("Making value (percent or ₹)", min_value=0.0, value=2.0, step=0.1)
            wastage_percent = st.number_input("Wastage (%)", min_value=0.0, value=0.0, step=0.1)
        with col3:
            hallmark = st.selectbox("Hallmark", options=["Yes", "No"], index=0)
            hallmark_charge = st.number_input("Hallmark charge (₹)", min_value=0.0, value=50.0, step=1.0)
            gst = st.number_input("GST (%)", min_value=0.0, value=3.0, step=0.1)

        submitted = st.form_submit_button("Calculate & Analyze")

    if submitted:
        # compute prices
        purity_factor = PURITY.get(carat, carat/24.0)
        rate_per_g = price_for_carat(rate_24k, carat) # Price adjusted for carat
        # adjust for wastage: some shops add to grams
        effective_grams = grams * (1 + wastage_percent/100.0)
        gold_value = rate_per_g * effective_grams

        # making charge
        if making_type == "% of gold value":
            making_charge = gold_value * (making_val / 100.0)
        else:
            making_charge = making_val * effective_grams

        pre_tax = gold_value + hallmark_charge + making_charge
        gst_amount = pre_tax * (gst / 100.0)
        final_price = pre_tax + gst_amount

        # Display result card
        st.subheader("🧾Final Price")
        st.metric(label="Final Bill (₹)", value=f"{final_price:,.2f}")

        # Detailed result card
        breakdown = {
            "Rate (24K) ₹/g": rate_24k,
            f"Rate ({carat}k) ₹/g": rate_per_g,
            "Gross grams (with wastage)": effective_grams,
            "Gold value (₹)": gold_value,
            "Making charge (₹)": making_charge,
            "Hallmark (₹)": hallmark_charge,
            "Pre-tax total (₹)": pre_tax,
            "GST amount (₹)": gst_amount,
            "Final price (₹)": final_price
        }
        df_break = pd.DataFrame(list(breakdown.items()), columns=["Part", "Amount"])
        st.table(df_break)

        # Save transaction option (shop mode)
        if shop_mode:
            st.subheader("💾 Save Transaction")
            if "transactions" not in st.session_state:
                st.session_state["transactions"] = []
            if st.button("Save this transaction"):
                tx = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "item": item_name,
                    "carat": carat,
                    "grams": grams,
                    "wastage_%": wastage_percent,
                    "effective_grams": round(effective_grams, 3),
                    "rate_per_g": round(rate_per_g, 2),
                    "gold_value": round(gold_value, 2),
                    "making_charge": round(making_charge, 2),
                    "hallmark": hallmark_charge,
                    "gst": gst,
                    "final_price": round(final_price, 2)
                }
                st.session_state["transactions"].append(tx)
                st.success("Transactions saved in current session.")

        # Graphs: breakdown bar chart (gold value vs others)
        chart_df = pdDataFrame({
            "component": ["Gold Value", "Making", "Hallmark", "GST"],
            "amount": [gold_value, making_charge, hallmark_charge, gst_amount]
        })
        bar = alt.Chart(chart_df).mark_bar().encode(
            x=alt.X("component", sort=None),
            y="amount"
        ).properties(width=600, height=300, title="Price Components")
        st.altair_chart(bar, use_container_width=True)

        # Historical Charge : simulate
        hist = simulate_historical(base_24k, days=90, volatility=0.008)

        # add carat adjusted series
        hist[f"price_{carat}k"]=hist["price_24k"]*(PURITY.get(carat, carat/24.0)/PURITY[24])

        # Altair time series
        hist_chart = alt.Chart(hist).transform_fold(
            fold=["price_24k", f"price_{carat}k"],
            as_=["key", "value"]
        ).mark_line().encode(
            x="date:T",
            y="value:Q",
            color="key:N"
        ).properties(title="Historical Price (simulated)", width=900, height=300)
        st.altair_chart(hist_chart, use_container_width=True)

with col_right:
    st.header("Shop Dashboard")
    # Show saved transactions
    if "transactions" in st.session_state and len(st.session_state["transactions"])>0:
        tx_df = pd.DataFrame(st.session_state["transactions"])
        st.dataframe(tx_df.sort_values("timestamp", ascending=False))
        # Download saved transactions as CSV
        csv = tx_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Transactions CSV", data=csv, file_name="transactions.csv", mime="text/csv")
    else:
        st.info("No transactions saved in this session yet. save transactions from the calculator to see them here.")

    st.markdown("----")
    st.header("Tools & Tips")
    st.write("""
    - Use the **Manual 24k rate** in the sidebar if you don't have a live API key.
    - Wastage (%) is often applied by retailers; common value: 0-3%.
    - Making charges can be perecent of gold value or fixed ₹ per gram.
    - GST on gold jewellery in India is commonly 3% but check current rules.
    """)
# Footer / Dark mode inject
inject_dark_mode(dark_mode)
st.markdown("---")
st.caption("Built for learning & shop workflows - extend with a real API key to enable live market rates.")