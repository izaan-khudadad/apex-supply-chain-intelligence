"""Starter Streamlit dashboard for the Apex supply-chain sample data."""

from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from db_config import create_mysql_engine, has_mysql_secrets


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "apex_supply_chain.db"
CSV_DATA_DIR = Path(__file__).resolve().parent / "data" / "simulated"

st.set_page_config(page_title="Apex Supply Chain Intelligence", page_icon="📦", layout="wide")


@st.cache_data
def load_data(database_modified: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load from MySQL locally, SQLite as a fallback, or CSV for hosted demos."""
    query = """
        SELECT s.*, p.category, p.product_name,
               c.carrier_name, c.service_type,
               r.destination_city, r.destination_state, r.distance_miles
        FROM shipments AS s
        LEFT JOIN products AS p ON p.product_id = s.product_id
        LEFT JOIN carriers AS c ON c.carrier_id = s.carrier_id
        LEFT JOIN routes AS r ON r.route_id = s.route_id
    """
    summary_query = """
        SELECT summary.*, carriers.carrier_name
        FROM carrier_monthly_summary AS summary
        JOIN carriers ON carriers.carrier_id = summary.carrier_id
    """
    if has_mysql_secrets():
        engine = create_mysql_engine()
        try:
            with engine.connect() as connection:
                shipments = pd.read_sql_query(
                    query,
                    connection,
                    parse_dates=["order_date", "estimated_delivery_date", "actual_delivery_date"],
                )
                monthly_summary = pd.read_sql_query(summary_query, connection)
        finally:
            engine.dispose()
    elif DATABASE_PATH.is_file():
        with sqlite3.connect(DATABASE_PATH) as connection:
            shipments = pd.read_sql_query(
                query,
                connection,
                parse_dates=["order_date", "estimated_delivery_date", "actual_delivery_date"],
            )
            monthly_summary = pd.read_sql_query(summary_query, connection)
    else:
        # Streamlit Community Cloud will not contain the local SQLite file or
        # MySQL credentials. The included fictional CSV snapshot makes a safe demo.
        shipments = pd.read_csv(
            CSV_DATA_DIR / "shipments.csv",
            parse_dates=["order_date", "estimated_delivery_date"],
        )
        shipments["actual_delivery_date"] = pd.to_datetime(
            shipments["actual_delivery_date"], errors="coerce"
        )
        products = pd.read_csv(CSV_DATA_DIR / "products.csv")[["product_id", "category", "product_name"]]
        carriers = pd.read_csv(CSV_DATA_DIR / "carriers.csv")[["carrier_id", "carrier_name", "service_type"]]
        routes = pd.read_csv(CSV_DATA_DIR / "routes.csv")[["route_id", "destination_city", "destination_state", "distance_miles"]]
        shipments = shipments.merge(products, on="product_id", how="left")
        shipments = shipments.merge(carriers, on="carrier_id", how="left")
        shipments = shipments.merge(routes, on="route_id", how="left")
        shipments["month"] = shipments["order_date"].dt.strftime("%Y-%m")
        shipments["completed_flag"] = shipments["status"].isin(["Delivered", "Delayed"]).astype(int)
        shipments["on_time_flag"] = shipments["status"].eq("Delivered").astype(int)
        shipments["delayed_flag"] = shipments["status"].eq("Delayed").astype(int)
        monthly_summary = shipments.groupby(["month", "carrier_id"], as_index=False).agg(
            shipment_count=("shipment_id", "count"),
            completed_shipments=("completed_flag", "sum"),
            on_time_shipments=("on_time_flag", "sum"),
            delayed_shipments=("delayed_flag", "sum"),
            average_delivery_delay_days=("delivery_delay_days", "mean"),
            total_shipping_cost_usd=("shipping_cost_usd", "sum"),
            average_shipping_cost_usd=("shipping_cost_usd", "mean"),
        )
        completed_count = monthly_summary["completed_shipments"].where(
            monthly_summary["completed_shipments"] > 0
        )
        monthly_summary["on_time_rate_pct"] = (
            monthly_summary["on_time_shipments"].div(completed_count).mul(100)
        )
        monthly_summary = monthly_summary.merge(carriers[["carrier_id", "carrier_name"]], on="carrier_id", how="left")
        monthly_summary["month"] = pd.to_datetime(monthly_summary["month"] + "-01")
    shipments["order_month"] = shipments["order_date"].dt.to_period("M").dt.to_timestamp()
    if not pd.api.types.is_datetime64_any_dtype(monthly_summary["month"]):
        monthly_summary["month"] = pd.to_datetime(monthly_summary["month"].astype(str) + "-01")
    return shipments, monthly_summary


st.title("📦 Apex Supply Chain Intelligence")
if has_mysql_secrets():
    st.caption("Connected to MySQL. All shipment records are simulated and fictional.")
elif DATABASE_PATH.is_file():
    st.caption("Using local SQLite. All shipment records are simulated and fictional.")
else:
    st.caption("Hosted demo using the included simulated CSV snapshot. All records are fictional.")

try:
    cache_stamp = DATABASE_PATH.stat().st_mtime if DATABASE_PATH.is_file() else (CSV_DATA_DIR / "shipments.csv").stat().st_mtime
    shipments, monthly_summary = load_data(cache_stamp)
except FileNotFoundError as error:
    st.error(f"Could not find required project data: {error.filename}")
    st.info("Run `python pipeline.py` first, and include data/simulated/ in the deployed repository.")
    st.stop()
except (SQLAlchemyError, ValueError) as error:
    st.error(f"Could not load the project database: {error}")
    st.info("Check your MySQL settings in .streamlit/secrets.toml, then run `python pipeline.py`.")
    st.stop()

st.sidebar.header("Filters")
statuses = sorted(shipments["status"].dropna().unique().tolist())
selected_statuses = st.sidebar.multiselect("Shipment status", statuses, default=statuses)
categories = sorted(shipments["category"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect("Product category", categories, default=categories)
carrier_names = sorted(shipments["carrier_name"].dropna().unique().tolist())
selected_carriers = st.sidebar.multiselect("Carrier", carrier_names, default=carrier_names)

filtered = shipments[
    shipments["status"].isin(selected_statuses)
    & shipments["category"].isin(selected_categories)
    & shipments["carrier_name"].isin(selected_carriers)
].copy()

completed = filtered[filtered["status"].isin(["Delivered", "Delayed"])]
on_time_rate = (completed["status"].eq("Delivered").mean() * 100) if not completed.empty else 0
late_count = int(filtered["status"].eq("Delayed").sum())
average_cost = filtered["shipping_cost_usd"].mean() if not filtered.empty else 0

metric_columns = st.columns(4)
metric_columns[0].metric("Shipments", f"{len(filtered):,}")
metric_columns[1].metric("On-time delivery", f"{on_time_rate:.1f}%", help="Share of delivered and delayed shipments that arrived on time.")
metric_columns[2].metric("Delayed shipments", f"{late_count:,}")
metric_columns[3].metric("Average shipping cost", f"${average_cost:,.2f}")

st.subheader("Shipment activity")
chart_left, chart_right = st.columns(2)

with chart_left:
    st.markdown("**Shipments by order month**")
    if filtered.empty:
        st.info("No shipments match these filters.")
    else:
        monthly = filtered.groupby("order_month").size().rename("Shipments")
        st.line_chart(monthly)

with chart_right:
    st.markdown("**Shipment status**")
    status_counts = filtered["status"].value_counts().rename("Shipments")
    if status_counts.empty:
        st.info("No shipments match these filters.")
    else:
        st.bar_chart(status_counts)

st.subheader("Carrier performance")
if filtered.empty:
    st.info("No shipments match these filters.")
else:
    carrier_summary = filtered.groupby("carrier_name").agg(
        Shipments=("shipment_id", "count"),
        Average_shipping_cost_usd=("shipping_cost_usd", "mean"),
        Delayed_shipments=("status", lambda values: int(values.eq("Delayed").sum())),
    )
    carrier_summary["Average_shipping_cost_usd"] = carrier_summary["Average_shipping_cost_usd"].round(2)
    st.dataframe(carrier_summary.sort_values("Shipments", ascending=False), width="stretch")

st.subheader("Monthly carrier KPIs")
st.caption("Precomputed by the pipeline. The carrier filter applies here; status and category filters do not change this all-shipment summary.")
summary_filtered = monthly_summary[monthly_summary["carrier_name"].isin(selected_carriers)]
if summary_filtered.empty:
    st.info("Select at least one carrier to view its monthly KPIs.")
else:
    kpi_left, kpi_right = st.columns(2)
    with kpi_left:
        st.markdown("**Monthly shipping cost**")
        monthly_cost = summary_filtered.groupby("month")["total_shipping_cost_usd"].sum().rename("Shipping cost (USD)")
        st.line_chart(monthly_cost)
    with kpi_right:
        st.markdown("**On-time delivery rate by carrier**")
        on_time_by_carrier = summary_filtered.pivot(
            index="month", columns="carrier_name", values="on_time_rate_pct"
        ).sort_index()
        st.line_chart(on_time_by_carrier)
    with st.expander("View monthly carrier KPI table"):
        st.dataframe(
            summary_filtered.sort_values(["month", "carrier_name"], ascending=[False, True]),
            width="stretch",
            hide_index=True,
        )

with st.expander("View shipment records"):
    visible_columns = [
        "shipment_id", "order_date", "product_id", "product_name", "category", "supplier_id",
        "warehouse_id", "destination_city", "destination_state", "carrier_name", "quantity",
        "shipping_cost_usd", "estimated_delivery_date", "actual_delivery_date", "delivery_delay_days", "status",
    ]
    st.dataframe(filtered[visible_columns], width="stretch", hide_index=True)

st.caption("Tip: use the filters in the sidebar to compare product categories, carriers, and delivery statuses.")
