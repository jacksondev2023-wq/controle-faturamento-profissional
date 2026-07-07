import streamlit as st
import pandas as pd
from components.editable_table import editable_table

st.title("Test")
html = """
<table class="sheet-table">
  <tr><th>Operadora</th><th>Faturado</th></tr>
  <tr><td>UNIMED</td><td><input class="editable-cell" id="fat_1_hm_unimed" type="number" value="100.50"></td></tr>
</table>
"""
res = editable_table(html, key="test_table")
if res:
    st.write("Changed:", res)
