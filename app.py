"""Smart Delivery & Logistics Network -- Kalyani dashboard.

Run with: streamlit run app.py

Pages live in ui/pages.py, map layers in ui/layers.py, styling in ui/style.py
and .streamlit/config.toml. The algorithms themselves are in src/.
"""

import streamlit as st

st.set_page_config(
    page_title="Smart Delivery Network · Kalyani",
    page_icon=":material/local_shipping:",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={"About": "Smart Delivery Network: Algorithms II group project by Akash Chakraborty, Anipriyo Mandal and Arpan Mandal. Computational geometry on OpenStreetMap data of the Kalyani region."},
)

from ui import pages, style  # noqa: E402  (page config must come first)
from ui.state import sidebar  # noqa: E402

style.inject()
st.session_state["ctx"] = sidebar()

nav = st.navigation(
    [
        st.Page(pages.network, title="Network map", icon=":material/map:", default=True),
        st.Page(pages.river, title="River crossing", icon=":material/water:", url_path="river"),
        st.Page(pages.coverage, title="Coverage planner", icon=":material/radar:", url_path="coverage"),
        st.Page(pages.walkthrough, title="Walkthrough", icon=":material/footprint:", url_path="walkthrough"),
        st.Page(pages.data, title="Data", icon=":material/table_rows:", url_path="data"),
        st.Page(pages.about, title="How it works", icon=":material/menu_book:", url_path="how-it-works"),
    ],
    position="top",
)
nav.run()
