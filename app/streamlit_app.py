from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import BusFilters, Database

st.set_page_config(
    page_title="Redbus Bus Explorer",
    page_icon="🚌",
    layout="wide",
)

st.title("Redbus Data Explorer")
st.caption("Filter government & private bus listings scraped from redbus.in")


@st.cache_resource
def get_db() -> Database:
    return Database()


def load_filter_options(db: Database) -> tuple[list[str], list[str]]:
    try:
        routes = db.get_distinct_values("route_name")
        bustypes = db.get_distinct_values("bustype")
        return routes, bustypes
    except Exception:
        return [], []


def render_sidebar(db: Database) -> BusFilters:
    routes, bustypes = load_filter_options(db)
    st.sidebar.header("Filters")

    selected_routes = st.sidebar.multiselect(
        "Route",
        options=routes,
        default=routes[:1] if len(routes) == 1 else [],
    )
    selected_types = st.sidebar.multiselect("Bus type", options=bustypes)

    price_bounds = (0.0, 5000.0)
    if routes:
        try:
            df_prices = db.fetch_buses()
            if not df_prices.empty and df_prices["price"].notna().any():
                pmin = float(df_prices["price"].min())
                pmax = float(df_prices["price"].max())
                price_bounds = (max(0, pmin), max(pmin + 1, pmax))
        except Exception:
            pass

    price_range = st.sidebar.slider(
        "Price range (₹)",
        min_value=float(price_bounds[0]),
        max_value=float(price_bounds[1]),
        value=price_bounds,
    )
    min_rating = st.sidebar.slider("Minimum star rating", 0.0, 5.0, 0.0, 0.5)
    min_seats = st.sidebar.number_input("Minimum seats available", 0, 100, 0)
    government_only = st.sidebar.checkbox("Government / state transport only")
    search_name = st.sidebar.text_input("Search bus name")

    return BusFilters(
        route_names=selected_routes or None,
        bustypes=selected_types or None,
        min_price=price_range[0],
        max_price=price_range[1],
        min_rating=min_rating if min_rating > 0 else None,
        min_seats=int(min_seats) if min_seats > 0 else None,
        government_only=government_only,
        search_busname=search_name.strip() or None,
    )


def render_metrics(df: pd.DataFrame) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Buses shown", len(df))
    c2.metric("Routes", df["route_name"].nunique() if not df.empty else 0)
    c3.metric(
        "Avg price (₹)",
        f"{df['price'].mean():.0f}" if not df.empty and df["price"].notna().any() else "—",
    )
    c4.metric(
        "Govt. buses",
        int(df["is_government"].sum()) if not df.empty and "is_government" in df else 0,
    )


def render_charts(df: pd.DataFrame) -> None:
    if df.empty:
        return
    col1, col2 = st.columns(2)
    with col1:
        if df["price"].notna().any():
            fig = px.histogram(df, x="price", color="route_name", title="Price distribution")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        if df["star_rating"].notna().any():
            fig = px.box(df, x="route_name", y="star_rating", title="Ratings by route")
            st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    db = get_db()
    filters = render_sidebar(db)

    try:
        df = db.fetch_buses(filters)
        stats = db.get_stats()
    except Exception as exc:
        st.error(
            f"Could not load data: {exc}\n\n"
            "Run `python run_scraper.py --init-db` then `python run_scraper.py` first."
        )
        return

    if stats["total_buses"] == 0:
        st.warning(
            "No data in the database yet. Run the scraper:\n\n"
            "`python run_scraper.py --init-db`\n"
            "`python run_scraper.py`"
        )
        return

    st.subheader("Results")
    render_metrics(df)
    render_charts(df)

    display_cols = [
        "route_name",
        "busname",
        "bustype",
        "departing_time",
        "duration",
        "reaching_time",
        "star_rating",
        "price",
        "seats_available",
        "is_government",
    ]
    show = df[[c for c in display_cols if c in df.columns]]
    st.dataframe(
        show,
        use_container_width=True,
        column_config={
            "route_link": st.column_config.LinkColumn("Route link"),
            "is_government": st.column_config.CheckboxColumn("Govt."),
            "price": st.column_config.NumberColumn("Price (₹)", format="₹%.0f"),
        },
    )

    with st.expander("Export filtered data"):
        st.download_button(
            "Download CSV",
            show.to_csv(index=False).encode("utf-8"),
            file_name="redbus_filtered.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
