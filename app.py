# the thing above saves everythign below it into a python file
# A jypter command tha tsaves the cell's contents into a pyhton file name app.py
import psycopg
import pandas as pd

import streamlit as st
st.title("Customer Inactivity Prediction Dashboard") # dispaly a l;arge title on the webpage
st.write("Customer purchasing behavior and inactivity analysis")

def connect_to_database():
    conn = psycopg.connect(
        st.secrets["NEON_DATABASE_URL"]
    )
    return conn

con = connect_to_database()
st.success("Successfully connected to PostgreSQL")

col1, col2, col3 = st.columns(3)

with con.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cursor.fetchone()[0]

with col1:
    st.metric("Total transactions:", total_transactions)

with con.cursor() as cursor:
    cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM transactions")
    total_amount_of_customers = cursor.fetchone()[0]

with col2:
    st.metric("Total unique customers:",  total_amount_of_customers)

with con.cursor() as cursor:
    cursor.execute("SELECT SUM(transaction_line_amount) FROM transactions")
    total_revenue = cursor.fetchone()[0]

with col3:
    st.metric("Total revenue:", total_revenue)

with con.cursor() as cursor:
    cursor.execute("""SELECT customer_id, SUM(transaction_line_amount) as total
    FROM transactions
    GROUP BY customer_id
    ORDER BY total DESC
    LIMIT 10""")

    top_10_customers = cursor.fetchall()

    top_customers_df = pd.DataFrame(top_10_customers, columns=["Customer ID", "Total Spending"])

    top_customers_df["Total Spending"] = top_customers_df["Total Spending"].astype(float)

st.write("Top 10 customers", top_customers_df)

st.bar_chart(
    top_customers_df,
    x = "Customer ID",
    y = "Total Spending"
)

with con.cursor() as cursor:
    cursor.execute("""
    SELECT DATE_TRUNC('month', invoice_date) AS month,
       SUM(transaction_line_amount) AS total_revenue
FROM transactions
GROUP BY month
ORDER BY month ASC;""")

    months = cursor.fetchall()

    month_df = pd.DataFrame(months, columns=["Month", "Total Revenue"])

    month_df["Total Revenue"] = month_df["Total Revenue"].astype(float)

st.write("Monthly Revenue", month_df)

st.line_chart(
    data=month_df,
    x="Month",
    y="Total Revenue"
)

with con.cursor() as cursor:
    cursor.execute("""SELECT customer_id, COUNT(DISTINCT invoice) 
                    FROM transactions
                    GROUP BY customer_id
                    ORDER BY COUNT(DISTINCT invoice) DESC"""
                  )

    distinct_customers = cursor.fetchall()
    distinct_customer_dict = {}

    for distinct_customer, purchase_count in distinct_customers:
        distinct_customer_dict[distinct_customer]  = purchase_count


selected_customer = st.selectbox(
    "Choose a customer ID:",
        options = list(distinct_customer_dict.keys()),
    format_func = lambda customer_id: f"Customer {customer_id} - {distinct_customer_dict[customer_id]} purchases"
)

with con.cursor() as cursor:
    cursor.execute("""SELECT invoice, invoice_date, transaction_line_amount
                        FROM transactions 
                        WHERE customer_id = %s
                        ORDER BY invoice_date ASC
                        """,
                  (selected_customer,)
                  )

    specific_customer = cursor.fetchall()

    specific_customer_df = pd.DataFrame(specific_customer, columns = ["Invoice", "Invoice_Date", "Transaction Amount"])

    specific_customer_df["Transaction Amount"] = specific_customer_df["Transaction Amount"].astype(float)

with con.cursor() as cursor:
    cursor.execute("""SELECT COUNT(DISTINCT invoice)
                        FROM transactions
                        WHERE customer_id = %s
                        """,
                   (selected_customer,)
                  )
    customer_purchase_count = cursor.fetchone()[0]





st.write("Selected Customer:", selected_customer)

st.metric("Customer Purchases", customer_purchase_count)

st.write("Customer Purchase History")

st.dataframe(specific_customer_df)

with con.cursor() as cursor:
    cursor.execute("SELECT MAX(invoice_date) FROM transactions WHERE customer_id = %s",
                  (selected_customer,))
    last_purchase_date = cursor.fetchone()[0]

st.write("Last Purchase Date:", last_purchase_date)

with con.cursor() as cursor:
    cursor.execute("SELECT MAX(invoice_date) FROM transactions")
    reference_date = cursor.fetchone()[0]# as the date we're rpetending is today
# Our dataset ends in December 2011, so we use its latest transaction date as our 
# historical refernce point instead of October 2026

st.write("Dataset Reference Date:", reference_date)

days_since_last_purchase = (reference_date - last_purchase_date).days

st.metric("Days Since Last Purchase", days_since_last_purchase)

unique_purchases_df = specific_customer_df[
    ["Invoice", "Invoice_Date"]
    ].drop_duplicates(subset=["Invoice"]).sort_values(by="Invoice_Date")

st.subheader("Customer Purchase Timeline")

unique_purchases_df["Purchase Date"] = unique_purchases_df["Invoice_Date"].dt.date

purchase_days_df = unique_purchases_df.drop_duplicates(subset=["Purchase Date"]).copy()


purchase_days_df["Purchase Date"] = pd.to_datetime(purchase_days_df["Purchase Date"])

purchase_days_df["Purchase Gap (Days)"] = purchase_days_df["Purchase Date"].diff().dt.days

typical_purchase_gap = purchase_days_df["Purchase Gap (Days)"].median()

if pd.notna(typical_purchase_gap):
    st.metric("Typical Purchase Gap (DAYS)", typical_purchase_gap)
else:
    st.metric("Typical Purchase Gap (Days)", "N/A")
    st.info("A purchase gap requires purchases on at least two different days")

if (
    customer_purchase_count >= 10
    and pd.notna(typical_purchase_gap)
    and typical_purchase_gap> 0):

    st.success("Customer is eligible for inactivity analysis")

    inactivity_threshold = typical_purchase_gap * 5
    st.metric("Inactivity Threshold(DAYS)", inactivity_threshold)

    days_until_inactive = inactivity_threshold - days_since_last_purchase

    if days_until_inactive > 0:
        st.metric("Days Until Inactive", days_until_inactive)
    elif days_until_inactive == 0:
        st.metric("Days Past Inactivity Threshold", 0)
    else:
        st.metric("Days past Inactivity Threshold", abs(days_until_inactive))

    if days_since_last_purchase >= inactivity_threshold:
        st.error("Customer is inactive")
    elif days_until_inactive <= 7:
        st.warning("Customer is approaching inactivity!")
    else:
        st.success("Customer is not inactive")
else:
    st.warning(
        "Inactivity analysis unavailable: Customer needs at least 10 distinct purchases "
        "and a valid purchase gap greater than 0 days"
    )

st.dataframe(unique_purchases_df)

st.subheader("Customer Purchase Gap Analysis")
st.dataframe(purchase_days_df)



con.close()
