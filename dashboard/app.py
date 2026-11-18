"""KariyerRadar dashboard'u — giriş noktası ve sayfa yönlendirici.

Çalıştırma:  streamlit run dashboard/app.py
"""

import streamlit as st

st.set_page_config(page_title="KariyerRadar", page_icon="📡", layout="wide")

pages = st.navigation(
    [
        st.Page("home.py", title="Genel Bakış", icon=":material/radar:", default=True),
        st.Page("pages/1_Trendler.py", title="Trendler", icon=":material/trending_up:"),
        st.Page("pages/2_Ilan_Arama.py", title="İlan Arama", icon=":material/search:"),
    ]
)
pages.run()
