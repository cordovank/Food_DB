from __future__ import annotations
import streamlit as st

def show_message(msg: dict | None):
    if not msg:
        return
    kind = msg.get("kind", "info")
    text = msg.get("text", "")
    if kind == "success":
        st.success(text)
    elif kind == "warning":
        st.warning(text)
    elif kind == "error":
        st.error(text)
    else:
        st.info(text)