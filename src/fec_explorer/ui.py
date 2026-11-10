"""Shared UI helpers."""
import streamlit as st

def show_sql(statement, params=()):
    with st.expander('View SQL'):
        st.code(statement, language='sql')
        if params:
            st.caption('Bound parameter values (in order)')
            st.json(list(params))
