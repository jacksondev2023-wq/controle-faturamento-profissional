
from pathlib import Path
from datetime import datetime
from html import escape
from urllib.parse import quote, unquote
import hashlib
import hmac
import io
import json
import os
import pandas as pd
import streamlit as st
from components.editable_table import editable_table
import time
import altair as alt
from streamlit_sortables import sort_items

from src.acerto_contas import (
    build_automatic_settlements,
    build_branch_net_summary,
    format_settlements_for_copy,
)
from src.consolidado_component import consolidado_inline_table
from src.etl import (
    MONTHS,
    DEFAULT_DEPARA,
    DEFAULT_OPERADORA_DEPARA,
    read_first_sheet,
    prepare_faturamento,
    prepare_contabilidade,
    build_consolidado,
    parse_dinamica_workbook,
    dinamica_to_raw_tables,
    DINAMICA_COLUMNS,
    norm_text,
)

ROOT = Path(__file__).resolve().parent

# Importa camada de abstração de banco (SQLite local ou PostgreSQL em cloud)
from src.db import (
    get_con as _db_get_con,
    read_table as _db_read_table,
    write_table as _db_write_table,
    append_table as _db_append_table,
    execute_sql as _db_execute_sql,
    fetch_sql as _db_fetch_sql,
    table_columns as _db_table_columns,
    add_column as _db_add_column,
    ensure_table as _db_ensure_table,
    is_cloud as _db_is_cloud,
    auto_migrate_from_sqlite as _db_auto_migrate,
    sync_cloud_seed_if_newer as _db_sync_cloud_seed,
    DB_PATH,
)

st.set_page_config(
    page_title="Controle Executivo | Faturamento x Recebimento",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

CORPORATE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
    --navy: #001F4E;
    --navy-2: #001A42;
    --ink: #11131A;
    --muted: #5F6472;
    --line: #C7CBD7;
    --soft-line: #DFE2EA;
    --canvas: #F7F5FC;
    --card: #FFFFFF;
    --blue: #002E7A;
    --danger: #C10007;
    --warning: #D76B00;
}
html, body, [class*="css"] {
    font-family: "Inter", sans-serif;
}
.stApp {
    background: var(--canvas);
}
.block-container {
    padding: 1.6rem 2.4rem 2.4rem 2.4rem;
    max-width: none;
}
header[data-testid="stHeader"] {
    background: transparent;
    height: 0;
}
[data-testid="stToolbar"] {
    display: none;
}
[data-testid="collapsedControl"] {
    color: #001F4E;
}
section[data-testid="stSidebar"] {
    background: var(--navy) !important;
    border-right: 1px solid rgba(255,255,255,0.08);
    min-width: 244px !important;
    width: 244px !important;
}
section[data-testid="stSidebar"] > div {
    background: var(--navy) !important;
    padding: 18px 16px 20px 16px;
}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
    display: none;
}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    padding-top: 0;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.22);
    border-radius: 5px;
    background: rgba(255,255,255,0.03);
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
section[data-testid="stSidebar"] [data-testid="stExpander"] label,
section[data-testid="stSidebar"] [data-testid="stExpander"] p {
    color: rgba(255,255,255,0.86) !important;
}
.fixed-sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    width: 244px;
    height: 100vh;
    z-index: 9999;
    background: var(--navy);
    border-right: 1px solid rgba(255,255,255,0.08);
    padding: 18px 16px 20px 16px;
    box-sizing: border-box;
    overflow-y: auto;
}
.side-brand {
    margin-bottom: 32px;
}
.side-brand h1 {
    color: #FFFFFF;
    font-size: 1.35rem;
    line-height: 1.65rem;
    font-weight: 800;
    margin: 0;
    white-space: nowrap;
}
.side-brand p {
    color: rgba(255,255,255,0.76);
    font-size: 0.84rem;
    margin: 8px 0 0 0;
}
.side-nav {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.side-nav a,
.menu-toggle {
    height: 40px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 12px;
    border-radius: 3px;
    color: rgba(255,255,255,0.82);
    text-decoration: none;
    font-size: 0.86rem;
    font-weight: 500;
}
.menu-toggle {
    margin-bottom: 14px;
    border: 1px solid rgba(255,255,255,0.18);
}
.side-nav a:hover,
.menu-toggle:hover {
    background: rgba(255,255,255,0.08);
    color: #FFFFFF;
    text-decoration: none;
}
.side-nav a span,
.menu-toggle span {
    color: inherit !important;
}
.side-nav a.active {
    background: #A9BFF6;
    color: #244D9A;
    font-weight: 800;
}
.side-nav a.active .nav-icon {
    color: #628AE8 !important;
}
.nav-icon {
    width: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #B8C6E8;
    font-size: 1rem;
}
.side-params-note {
    color: rgba(255,255,255,0.64);
    font-size: 0.75rem;
    line-height: 1.15rem;
    border-top: 1px solid rgba(255,255,255,0.16);
    margin-top: 26px;
    padding-top: 14px;
}
[data-testid="stMetricValue"] {font-size: 1.6rem;}
.app-topbar-title {
    color: #001945;
    font-size: 1.35rem;
    font-weight: 800;
    padding-bottom: 10px;
    border-bottom: 3px solid #001945;
    display: inline-block;
}
.app-topbar-section {
    color: #3C404C;
    font-size: 1.05rem;
    font-weight: 500;
    margin-left: 16px;
}
.topbar-line {
    border-bottom: 1px solid var(--line);
    margin: 8px -2.4rem 34px -2.4rem;
}
.page-title {
    color: var(--ink);
    font-size: 2.15rem;
    font-weight: 800;
    line-height: 2.65rem;
    letter-spacing: -0.02em;
    margin-bottom: 8px;
}
.page-subtitle {
    color: #303340;
    font-size: 1rem;
    line-height: 1.55rem;
    max-width: 760px;
    margin-bottom: 24px;
}
.panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--card);
    padding: 20px;
}
.table-panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--card);
    overflow: hidden;
}
.filter-band {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #FFFFFF;
    padding: 18px 20px 8px 20px;
    margin-bottom: 20px;
}
.filter-band-title {
    color: #202431;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.section-title {
    color: var(--ink);
    font-size: 1.3rem;
    font-weight: 800;
    margin: 0 0 16px 0;
}
.card {
    padding: 18px 20px;
    border-radius: 8px;
    border: 1px solid var(--line);
    background: var(--card);
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}
.depara-hero {
    padding: 20px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: transparent;
    margin-bottom: 18px;
}
.depara-hero-title {
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--ink);
    margin-bottom: 2px;
}
.depara-hero-subtitle {
    color: var(--muted);
    font-size: 0.92rem;
}
.depara-toolbar {
    padding: 16px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: transparent;
    margin: 16px 0 18px 0;
}
.field-chip {
    display: inline-block;
    padding: 7px 10px;
    margin: 3px 4px 3px 0;
    border-radius: 999px;
    background: #E1E2E8;
    color: #2F3340;
    font-size: 0.76rem;
    font-weight: 600;
}
.upload-panel {
    padding: 22px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--card);
    min-height: 100%;
}
.upload-panel h4 {
    margin-bottom: 2px;
    font-size: 1.25rem;
    color: var(--ink);
}
.kpi-card {
    padding: 18px 20px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--card);
    min-height: 122px;
}
.kpi-label {
    color: #202431;
    font-size: 0.72rem;
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.04em;
}
.kpi-value {
    color: #06134A;
    font-size: 1.55rem;
    font-weight: 800;
    margin-top: 12px;
}
.kpi-note {
    color: var(--muted);
    font-size: 0.78rem;
    margin-top: 8px;
}
.kpi-alert {
    border-color: #FECACA;
    background: #FFF7F7;
}
.kpi-alert .kpi-label,
.kpi-alert .kpi-value {
    color: #B42318;
}
.comment-panel {
    padding: 16px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--card);
}
.export-panel {
    padding: 24px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #F1F0F7;
}
.export-card {
    padding: 22px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--card);
    min-height: 170px;
}
.export-card-active {
    border-color: #001945;
    box-shadow: 0 0 0 1px #001945;
}
.export-card-title {
    color: var(--ink);
    font-size: 1.15rem;
    font-weight: 800;
    margin-bottom: 12px;
}
.export-card-text {
    color: #2F3340;
    font-size: 0.95rem;
    line-height: 1.45rem;
}
.issue-card {
    border: 1px solid var(--line);
    border-left: 4px solid #697080;
    border-radius: 8px;
    background: var(--card);
    padding: 18px;
    min-height: 132px;
}
.issue-card-critical {border-color: #FFB3B3; border-left-color: #C10007;}
.issue-card-high {border-left-color: #E26D00;}
.issue-card-medium {border-left-color: #F39C12;}
.issue-card-low {border-left-color: #697080;}
.issue-severity {
    float: right;
    padding: 3px 10px;
    font-size: 0.72rem;
    font-weight: 800;
    background: #FFE2E2;
    color: #9A0000;
}
.issue-value {
    clear: both;
    font-size: 1.8rem;
    font-weight: 800;
    color: var(--ink);
    margin-top: 18px;
}
.issue-label {
    color: #343845;
    font-size: 0.92rem;
    margin-top: 4px;
}
.pending-row {
    margin-bottom: 15px;
}
.pending-row-top {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 0.82rem;
    font-weight: 800;
    color: var(--ink);
    text-transform: uppercase;
}
.pending-row-value {color: var(--danger);}
.bar-track {
    height: 8px;
    border-radius: 99px;
    background: #E3E4EA;
    overflow: hidden;
    margin-top: 8px;
}
.bar-fill {
    height: 100%;
    background: #C40010;
    border-radius: 99px;
}
.dashboard-chart {
    height: 300px;
    display: flex;
    align-items: end;
    gap: 22px;
    padding: 18px 18px 24px 18px;
    border-left: 1px solid #D7DAE4;
    border-bottom: 1px solid #D7DAE4;
    background:
        linear-gradient(to top, #E8EAF1 1px, transparent 1px) 0 0 / 100% 20%;
}
.dashboard-bar-group {
    flex: 1;
    min-width: 88px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: end;
    height: 100%;
}
.dashboard-bar {
    width: 76%;
    max-width: 240px;
    min-height: 8px;
    border-radius: 3px 3px 0 0;
    background: #00245D;
}
.dashboard-bar:nth-child(1) {
    background: #6F7F9C;
}
.dashboard-bar-label {
    margin-top: 12px;
    color: #1E2230;
    font-size: 0.82rem;
    font-weight: 700;
}
.native-table-wrap {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #FFFFFF;
    overflow: auto;
    max-height: 540px;
}
.native-table {
    border-collapse: collapse;
    width: 100%;
    min-width: 1180px;
    font-size: 0.86rem;
    color: #11131A;
    table-layout: auto;
}
.native-table th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: #00245D;
    color: #FFFFFF;
    padding: 13px 14px;
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    border-right: 1px solid rgba(255,255,255,0.14);
    white-space: nowrap;
}
.native-table th.faturamento-col {
    background: #001945;
    color: #FFFFFF;
    box-shadow: inset 0 -3px 0 #C10007;
}
.native-table td {
    padding: 13px 14px;
    border-bottom: 1px solid #DDE1EA;
    border-right: 1px solid #EEF0F5;
    background: #FFFFFF;
    vertical-align: middle;
    overflow-wrap: anywhere;
}
.native-table td.obs-col {
    white-space: normal;
    line-height: 1.45;
    vertical-align: top;
}
.native-table .obs-full {
    display: block;
    max-width: min(1220px, calc(100vw - 180px));
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
}
.native-table td.faturamento-col {
    background: #F2F6FF !important;
    color: #001945;
    font-weight: 900;
    box-shadow: inset 3px 0 0 #00245D;
}
.native-table tr:nth-child(even) td {
    background: #FAFAFD;
}
.native-table td.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}
.native-table td.strong {
    font-weight: 800;
    color: #001945;
}
.native-table tr.total-row td {
    background: #E3E3E8;
    font-size: 1rem;
    font-weight: 800;
}
.native-table tr.unit-total-row td {
    background: #EEF2F8 !important;
    color: #001945;
    font-weight: 900;
    border-top: 2px solid #BFC6D3;
}
.native-table tr.detail-row td:first-child {
    color: #697080;
}
.native-table tr.obs-note-row td {
    background: #FFFFFF;
    color: #172033;
    padding: 10px 14px 16px 14px;
    border-bottom: 1px solid #DDE1EA;
    white-space: normal;
    line-height: 1.45;
}
.native-table tr.unit-total-note-row td {
    background: #EEF2F8 !important;
    color: #001945;
    font-weight: 800;
}
.obs-note-label {
    display: block;
    color: #5F6472;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.native-table tr.grand-total-row td {
    background: #D9DCE5 !important;
    color: #001945;
    font-size: 1rem;
    font-weight: 900;
    border-top: 2px solid #001945;
}
.pivot-table-wrap {
    max-height: 620px;
}
.pivot-table {
    width: max-content;
    min-width: 100%;
}
.pivot-table th:first-child,
.pivot-table th:nth-child(2) {
    min-width: 220px;
}
.pivot-table td:first-child,
.pivot-table td:nth-child(2) {
    min-width: 220px;
}
.pivot-table .obs-col {
    min-width: 420px;
    max-width: 560px;
    white-space: normal;
    word-break: break-word;
}
.pivot-table th:not(:first-child):not(:nth-child(2)):not(.obs-col),
.pivot-table td:not(:first-child):not(:nth-child(2)):not(.obs-col) {
    min-width: 142px;
}
.sheet-pivot-wrap {
    max-height: none;
}
.sheet-pivot {
    width: 100%;
    min-width: 1180px;
    table-layout: fixed;
}
.sheet-pivot th,
.sheet-pivot td {
    padding: 4px 6px;
    font-size: 0.86rem;
    line-height: 1.2;
}
.sheet-pivot th:first-child,
.sheet-pivot td:first-child {
    width: 255px;
}
.sheet-pivot th.sheet-money-col,
.sheet-pivot td.sheet-money-col {
    width: 134px;
}
.sheet-pivot th.sheet-fat-col {
    background: #FFC000 !important;
    color: #000000 !important;
    text-align: center;
}
.sheet-pivot th.sheet-obs-col {
    background: #244392 !important;
    color: #FFFFFF !important;
    text-align: center;
}
.sheet-pivot td.sheet-obs-col {
    width: 390px;
    background: #FFF2CC !important;
    color: #000000;
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: normal;
    vertical-align: top;
}
.sheet-pivot td.fat-month-4 {
    background: #D9D9D9 !important;
}
.sheet-pivot tr.unit-total-row td {
    background: #DDEBF7 !important;
    color: #001945;
    border-top: 2px solid #2F75B5;
    border-bottom: 1px solid #2F75B5;
    font-weight: 900;
}
.sheet-pivot tr.detail-row td {
    border-bottom: 1px solid #2FA8E1;
}
.sheet-pivot tr.detail-row td:first-child {
    color: #001945;
    font-weight: 500;
}
.native-table tr.director-alert-row td,
.native-table tr.signal-verde td,
.native-table tr.signal-amarelo td,
.native-table tr.signal-vermelho td,
.sheet-pivot tr.alert-row td,
.sheet-pivot tr.signal-verde td,
.sheet-pivot tr.signal-amarelo td,
.sheet-pivot tr.signal-vermelho td {
    background: #FFF1F1 !important;
}
.native-table tr.signal-verde td,
.sheet-pivot tr.signal-verde td {
    background: #F0FFF5 !important;
}
.native-table tr.signal-amarelo td,
.sheet-pivot tr.signal-amarelo td {
    background: #FFF8E1 !important;
}
.native-table tr.signal-vermelho td,
.sheet-pivot tr.signal-vermelho td {
    background: #FFF1F1 !important;
}
.native-table tr.director-alert-row td:first-child,
.native-table tr.signal-vermelho td:first-child,
.sheet-pivot tr.alert-row td:first-child,
.sheet-pivot tr.signal-vermelho td:first-child {
    background: #FF0000 !important;
    color: #FFFFFF !important;
    font-weight: 900;
}
.native-table tr.signal-amarelo td:first-child,
.sheet-pivot tr.signal-amarelo td:first-child {
    background: #FFC000 !important;
    color: #11131A !important;
    font-weight: 900;
}
.native-table tr.signal-verde td:first-child,
.sheet-pivot tr.signal-verde td:first-child {
    background: #00A651 !important;
    color: #FFFFFF !important;
    font-weight: 900;
}
.sheet-pivot tr.unit-alert-row td:first-child {
    box-shadow: inset 5px 0 0 #FF0000;
}
.sheet-pivot tr.unit-signal-amarelo td:first-child {
    box-shadow: inset 5px 0 0 #FFC000;
}
.sheet-pivot tr.unit-signal-verde td:first-child {
    box-shadow: inset 5px 0 0 #00A651;
}
.sheet-line-cell {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 22px;
}
.sheet-line-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.sheet-row-signal-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex: 0 0 auto;
}
.sheet-signal-dot {
    width: 13px;
    height: 13px;
    display: inline-block;
    border-radius: 999px;
    border: 1px solid #8A91A1;
    background: #FFFFFF;
    opacity: 0.56;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.65);
}
.sheet-signal-dot:hover {
    opacity: 1;
    transform: scale(1.08);
}
.sheet-signal-dot.is-active {
    opacity: 1;
    outline: 2px solid #001F4E;
    outline-offset: 1px;
}
.sheet-signal-dot.signal-dot-none {
    background: #FFFFFF;
}
.sheet-signal-dot.signal-dot-verde {
    background: #00A651;
    border-color: #007F3E;
}
.sheet-signal-dot.signal-dot-amarelo {
    background: #FFC000;
    border-color: #B98900;
}
.sheet-signal-dot.signal-dot-vermelho {
    background: #FF0000;
    border-color: #B00000;
}
.director-alert-badge {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 3px;
    background: #FF0000;
    color: #FFFFFF;
    font-size: 0.72rem;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
}
.director-alert-panel {
    border: 1px solid #FFB4B4;
    border-left: 5px solid #FF0000;
    border-radius: 8px;
    background: #FFF7F7;
    padding: 14px 16px;
    margin: 8px 0 16px 0;
}
.director-alert-panel strong {
    color: #A40000;
}
.signal-editor-panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #FFFFFF;
    padding: 10px 12px;
    margin-bottom: 8px;
}
.signal-editor-title {
    color: #001945;
    font-size: 0.82rem;
    font-weight: 900;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.column-config-panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #FFFFFF;
    padding: 14px 16px 12px 16px;
    margin: 8px 0 16px 0;
}
.column-config-title {
    color: #001945;
    font-size: 0.86rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 4px;
}
.column-config-help {
    color: #5F6472;
    font-size: 0.82rem;
    margin-bottom: 12px;
}
.status-pill {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 3px;
    background: #E7E9EF;
    color: #323744;
    font-weight: 700;
    font-size: 0.76rem;
}
.status-pill.alert {
    background: #FFD9D9;
    color: #A40000;
}
.status-pill.ok {
    background: #DDF4E5;
    color: #006D2E;
}
.status-pill.warn {
    background: #FFF0C2;
    color: #8A4B00;
}
.stDataFrame, [data-testid="stDataFrame"] {
    border-radius: 8px;
}
.stSelectbox label,
.stMultiSelect label,
.stNumberInput label {
    color: #252936 !important;
    font-weight: 700 !important;
}
div[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border-color: var(--line) !important;
    color: #11131A !important;
    min-height: 44px;
}
div[data-baseweb="select"] span,
div[data-baseweb="select"] input,
div[data-baseweb="select"] svg {
    color: #11131A !important;
    fill: #11131A !important;
}
.stMultiSelect [data-baseweb="tag"],
div[data-baseweb="select"] [data-baseweb="tag"] {
    background: #00245D !important;
    border-color: #00245D !important;
    color: #FFFFFF !important;
}
.stMultiSelect [data-baseweb="tag"] span,
.stMultiSelect [data-baseweb="tag"] svg,
div[data-baseweb="select"] [data-baseweb="tag"] span,
div[data-baseweb="select"] [data-baseweb="tag"] svg {
    color: #FFFFFF !important;
    fill: #FFFFFF !important;
}
.stMultiSelect [data-baseweb="tag"] *,
div[data-baseweb="select"] [data-baseweb="tag"] * {
    color: #FFFFFF !important;
    fill: #FFFFFF !important;
}
.stMultiSelect [data-baseweb="tag"] button,
div[data-baseweb="select"] [data-baseweb="tag"] button {
    color: #FFFFFF !important;
}
.stButton > button,
.stDownloadButton > button {
    border-radius: 2px;
    min-height: 44px;
    font-weight: 700;
}
.stButton > button {
    background: #FFFFFF !important;
    border: 1px solid var(--line) !important;
    color: #001945 !important;
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: #001F4E !important;
    border-color: #001F4E !important;
    color: #FFFFFF !important;
}
.stDownloadButton > button {
    background: #001F4E !important;
    border-color: #001F4E !important;
    color: #FFFFFF !important;
}
div[data-testid="stFileUploader"] section {
    border: 2px dashed #C7CBD7;
    background: #F7F5FC;
    min-height: 160px;
}
div[data-testid="stFileUploader"] button {
    border-radius: 4px;
}
section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    justify-content: flex-start;
    border: 1px solid rgba(255,255,255,0.16);
    background: rgba(255,255,255,0.04);
    color: #FFFFFF;
    border-radius: 5px;
    min-height: 42px;
    font-weight: 650;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    border-color: rgba(255,255,255,0.38);
    background: rgba(255,255,255,0.10);
    color: #FFFFFF;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #FFFFFF !important;
    border-color: #FFFFFF !important;
    color: #001F4E !important;
}
section[data-testid="stSidebar"] .stButton > button p {
    color: inherit !important;
}
.small-muted {color:#667085; font-size: 0.88rem;}
h1, h2, h3 {letter-spacing: -0.02em;}
</style>
"""
st.markdown(CORPORATE_CSS, unsafe_allow_html=True)

def runtime_secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    try:
        auth = st.secrets.get("auth", {})
        if name.lower() in auth:
            return str(auth[name.lower()]).strip()
    except Exception:
        pass
    return ""

def require_app_password():
    expected_password = runtime_secret("APP_PASSWORD")
    if not expected_password:
        return
    if st.session_state.get("app_authenticated", False):
        return

    st.markdown(
        """
        <style>
        .block-container {
            max-width: 560px !important;
            padding-top: 12vh !important;
        }
        [data-testid="stForm"] {
            background: #FFFFFF;
            border: 1px solid #D8DCE7;
            border-radius: 8px;
            padding: 26px 28px 22px 28px;
            box-shadow: 0 18px 44px rgba(0, 31, 78, 0.12);
        }
        [data-testid="stForm"] label p {
            color: #001F4E !important;
            font-weight: 700 !important;
        }
        .auth-header {
            text-align: center;
            margin-bottom: 18px;
        }
        .auth-kicker {
            color: #5F6472;
            font-size: 0.84rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .auth-title {
            color: #001F4E;
            font-size: 2rem;
            font-weight: 850;
            line-height: 1.05;
            margin-top: 8px;
        }
        .auth-subtitle {
            color: #5F6472;
            font-size: 0.98rem;
            margin-top: 8px;
        }
        </style>
        <div class="auth-header">
            <div class="auth-kicker">Acesso restrito</div>
            <div class="auth-title">Controle Executivo</div>
            <div class="auth-subtitle">Faturamento x Recebimento</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("app_login_form"):
        password = st.text_input("Senha do portal", type="password")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if submitted:
            if hmac.compare_digest(password, expected_password):
                st.session_state["app_authenticated"] = True
                st.rerun()
            st.error("Senha invalida.")
    st.stop()

require_app_password()

def render_logout_button():
    if not runtime_secret("APP_PASSWORD"):
        return
    if not st.session_state.get("app_authenticated", False):
        return
    st.sidebar.divider()
    if st.sidebar.button("Sair", key="app_logout_button", use_container_width=True):
        st.session_state.pop("app_authenticated", None)
        st.rerun()

REPORT_TYPES = [
    {
        "label": "Relatório Executivo Excel",
        "short": "Executivo",
        "description": "KPIs, visão consolidada, bases opcionais, comentários e inconsistências em um pacote gerencial.",
    },
    {
        "label": "Consolidado Analítico",
        "short": "Analítico",
        "description": "Base conciliada por unidade e operadora, com faturamento, recebimentos, diferença e status.",
    },
    {
        "label": "Relatório de Inconsistências",
        "short": "Auditoria",
        "description": "Desvios de DE/PARA, linhas zeradas, chaves incompatíveis e alertas de qualidade.",
    },
    {
        "label": "Base de Faturamento Original",
        "short": "Faturamento",
        "description": "Extração tratada da origem de faturamento IW, preservando rastreabilidade do arquivo.",
    },
    {
        "label": "Base de Contabilidade Original",
        "short": "Contabilidade",
        "description": "Extração tratada de recebimentos/contabilidade, com valores bruto e líquido.",
    },
]

NAV_ITEMS = [
    ("dashboard", "Dashboard Executivo", "▦"),
    ("consolidado", "Consolidado", "▣"),
    ("importacoes", "Importações", "⇧"),
    ("depara", "DE/PARA", "↔"),
    ("comentarios", "Comentários", "▤"),
    ("inconsistencias", "Inconsistências", "ⓘ"),
    ("exportacoes", "Exportações", "⇩"),
    ("configuracoes", "Configurações", "⚙"),
]

NAV_ID_TO_PAGE = {page_id: label for page_id, label, _ in NAV_ITEMS}

def render_sidebar_nav() -> str:
    selected_id = st.query_params.get("p", st.session_state.get("current_page_id", "dashboard"))
    if selected_id not in NAV_ID_TO_PAGE:
        selected_id = "dashboard"
    st.session_state["current_page_id"] = selected_id
    menu_mode = st.query_params.get("menu", st.session_state.get("menu_mode", "full"))
    if menu_mode not in {"full", "compact"}:
        menu_mode = "full"
    st.session_state["menu_mode"] = menu_mode
    is_compact = menu_mode == "compact"

    st.markdown(
        f"""
        <style>
        section[data-testid="stSidebar"] {{
            min-width: {'72px' if is_compact else '244px'} !important;
            width: {'72px' if is_compact else '244px'} !important;
        }}
        section[data-testid="stSidebar"] > div {{
            padding: {'14px 8px' if is_compact else '18px 16px 20px 16px'} !important;
        }}
        {'section[data-testid="stSidebar"] .side-brand p, section[data-testid="stSidebar"] .side-brand h1, section[data-testid="stSidebar"] [data-testid="stExpander"] { display: none !important; }' if is_compact else ''}
        {'section[data-testid="stSidebar"] .stButton > button { justify-content: center; padding-left: 0.35rem; padding-right: 0.35rem; }' if is_compact else ''}
        </style>
        """,
        unsafe_allow_html=True,
    )

    def switch_page(page_id: str, mode: str):
        st.session_state["current_page_id"] = page_id
        st.session_state["menu_mode"] = mode
        st.query_params["p"] = page_id
        st.query_params["menu"] = mode
        st.rerun()

    toggle_mode = "full" if is_compact else "compact"
    toggle_label = "Expandir menu" if is_compact else "Recolher menu"
    st.sidebar.markdown(
        '<div class="side-brand">'
        '<h1>Controle Executivo</h1>'
        '<p>Faturamento x Recebimento</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    toggle_button_label = ">>" if is_compact else f"<< {toggle_label}"
    if st.sidebar.button(toggle_button_label, key="nav_toggle", use_container_width=True):
        switch_page(selected_id, toggle_mode)

    for page_id, label, icon in NAV_ITEMS:
        button_label = icon if is_compact else f"{icon} {label}"
        if st.sidebar.button(
            button_label,
            key=f"nav_{page_id}",
            type="primary" if page_id == selected_id else "secondary",
            use_container_width=True,
        ):
            switch_page(page_id, menu_mode)

    render_logout_button()
    return NAV_ID_TO_PAGE[selected_id]

def render_global_parameters():
    if "fat_months" not in st.session_state:
        st.session_state["fat_months"] = [3, 4, 5]
    if "rec_months" not in st.session_state:
        st.session_state["rec_months"] = [3, 4, 5, 6]

    with st.sidebar.expander("Parâmetros da análise", expanded=False):
        year = st.number_input("Ano de referência", min_value=2020, max_value=2035, value=2026, step=1)
        
        fat_months = st.multiselect(
            "Mês(es) do faturamento",
            options=list(MONTHS.keys()),
            default=st.session_state["fat_months"],
            format_func=lambda x: MONTHS[x],
            key="fat_months_input",
            on_change=lambda: st.session_state.update({"fat_months": st.session_state["fat_months_input"]})
        )
        rec_months = st.multiselect(
            "Mês(es) de recebimento",
            options=list(MONTHS.keys()),
            default=st.session_state["rec_months"],
            format_func=lambda x: MONTHS[x],
            key="rec_months_input",
            on_change=lambda: st.session_state.update({"rec_months": st.session_state["rec_months_input"]})
        )
    return int(year), fat_months, rec_months

def render_topbar(section: str, excel_data: bytes | None = None):
    left, refresh_col, export_col = st.columns([5, 1, 1])
    with left:
        st.markdown(
            f"""
            <span class="app-topbar-title">Faturamento x Recebimento</span>
            <span class="app-topbar-section">{section}</span>
            """,
            unsafe_allow_html=True,
        )
    with refresh_col:
        if st.button("Atualizar base", use_container_width=True, key=f"refresh_{section}"):
            st.cache_data.clear()
            st.rerun()
    with export_col:
        if excel_data:
            st.download_button(
                "Exportar Excel",
                data=excel_data,
                file_name="RELATORIO_EXECUTIVO_FAT_X_REC.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
                key=f"top_export_{section}",
            )
    st.markdown('<div class="topbar-line"></div>', unsafe_allow_html=True)

def render_page_header(title: str, subtitle: str = ""):
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)

def get_con():
    return _db_get_con()

def init_db_if_needed():
    if not _db_is_cloud() and not DB_PATH.exists():
        from scripts.seed_database import seed_database
        seed_database()

def _db_cache_token() -> str:
    if _db_is_cloud():
        return "cloud"
    try:
        return str(DB_PATH.stat().st_mtime_ns)
    except Exception:
        return "local-missing"

@st.cache_data(show_spinner=False, ttl=300)
def _cached_read_table(name: str, token: str) -> pd.DataFrame:
    return _db_read_table(name)

@st.cache_data(show_spinner=False, ttl=300)
def _cached_fetch_sql(sql: str, params: tuple | None, token: str) -> pd.DataFrame:
    return _db_fetch_sql(sql, params)

def clear_data_caches():
    try:
        _cached_read_table.clear()
        _cached_fetch_sql.clear()
        load_operational_tables.clear()
        df_to_excel_bytes.clear()
    except Exception:
        try:
            st.cache_data.clear()
        except Exception:
            pass

def read_table(name: str) -> pd.DataFrame:
    return _cached_read_table(name, _db_cache_token()).copy()

def write_table(name: str, df: pd.DataFrame, mode: str = "replace"):
    _db_write_table(name, df, mode)
    clear_data_caches()

def append_table(name: str, df: pd.DataFrame):
    _db_append_table(name, df)
    clear_data_caches()

def ensure_visual_preferences_table():
    _db_ensure_table(
        """
        CREATE TABLE IF NOT EXISTS visual_preferences (
            pref_key TEXT PRIMARY KEY,
            payload TEXT,
            updated_at TEXT
        )
        """
    )
    # Garante índice único (necessário caso a tabela tenha sido criada pelo to_sql sem PK)
    try:
        _db_execute_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_visual_pref_key ON visual_preferences(pref_key)"
        )
    except Exception:
        pass

def load_visual_preference(pref_key: str):
    ensure_visual_preferences_table()
    try:
        row = _db_fetch_sql(
            "SELECT payload FROM visual_preferences WHERE pref_key = ?",
            (pref_key,),
        )
        if row.empty:
            return None
        return json.loads(str(row["payload"].iloc[0] or "null"))
    except Exception:
        return None

def save_visual_preference(pref_key: str, payload):
    ensure_visual_preferences_table()
    payload_json = json.dumps(payload, ensure_ascii=False)
    updated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        _db_execute_sql(
            """
            INSERT INTO visual_preferences (pref_key, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(pref_key) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (pref_key, payload_json, updated_at),
        )
    except Exception:
        # Fallback para bases antigas sem indice unico aplicado.
        _db_execute_sql("DELETE FROM visual_preferences WHERE pref_key = ?", (pref_key,))
        _db_execute_sql(
            "INSERT INTO visual_preferences (pref_key, payload, updated_at) VALUES (?, ?, ?)",
            (pref_key, payload_json, updated_at),
        )
    clear_data_caches()

def delete_visual_preference(pref_key: str):
    ensure_visual_preferences_table()
    _db_execute_sql("DELETE FROM visual_preferences WHERE pref_key = ?", (pref_key,))
    clear_data_caches()

def ensure_base_dinamica_table():
    _db_ensure_table(
        """
        CREATE TABLE IF NOT EXISTS base_dinamica (
            linha_origem INTEGER,
            unidade_original TEXT,
            unidade_padrao TEXT,
            operadora_original TEXT,
            operadora_padrao TEXT,
            faturado_marco REAL,
            faturado_abril REAL,
            rec_bruto_marco REAL,
            rec_liquido_marco REAL,
            rec_bruto_abril REAL,
            rec_liquido_abril REAL,
            rec_bruto_maio REAL,
            rec_liquido_maio REAL,
            alerta_diretoria INTEGER,
            sinal_diretoria TEXT,
            observacao TEXT,
            origem_arquivo TEXT,
            atualizado_em TEXT
        )
        """
    )
    cols = _db_table_columns("base_dinamica")
    type_hint = {
        "linha_origem": "INTEGER",
        "faturado_marco": "REAL",
        "faturado_abril": "REAL",
        "rec_bruto_marco": "REAL",
        "rec_liquido_marco": "REAL",
        "rec_bruto_abril": "REAL",
        "rec_liquido_abril": "REAL",
        "rec_bruto_maio": "REAL",
        "rec_liquido_maio": "REAL",
        "alerta_diretoria": "INTEGER",
        "sinal_diretoria": "TEXT",
    }
    for col in DINAMICA_COLUMNS:
        if col not in cols:
            _db_add_column("base_dinamica", col, type_hint.get(col, "TEXT"))

DIRECTOR_SIGNAL_OPTIONS = ["Sem marcador", "Verde", "Amarelo", "Vermelho"]
DIRECTOR_SIGNAL_VALUES = {
    "SEM MARCADOR": "",
    "LIMPAR": "",
    "CLEAR": "",
    "NONE": "",
    "VERDE": "verde",
    "AMARELO": "amarelo",
    "VERMELHO": "vermelho",
}
DIRECTOR_SIGNAL_LABELS = {
    "": "Sem marcador",
    "verde": "Verde",
    "amarelo": "Amarelo",
    "vermelho": "Vermelho",
}
DIRECTOR_SIGNAL_PRIORITY = {"vermelho": 3, "amarelo": 2, "verde": 1, "": 0}
DIRECTOR_SIGNAL_QUERY_KEY = "signal_key"
DIRECTOR_SIGNAL_QUERY_VALUE = "signal"
CONSOLIDADO_INLINE_COMPONENT_KEY = "consolidado_inline_table"

def normalize_director_signal(value) -> str:
    key = norm_text(value)
    if key in DIRECTOR_SIGNAL_VALUES:
        return DIRECTOR_SIGNAL_VALUES[key]
    if key in {"RED", "CRITICO", "CRITICA", "ALERTA"}:
        return "vermelho"
    if key in {"YELLOW", "ATENCAO", "ATENÇÃO"}:
        return "amarelo"
    if key in {"GREEN", "OK"}:
        return "verde"
    return ""

def aggregate_director_signal(values) -> str:
    signals = [normalize_director_signal(value) for value in values]
    return max(signals, key=lambda value: DIRECTOR_SIGNAL_PRIORITY.get(value, 0), default="")

def director_signal_class(value) -> str:
    signal = normalize_director_signal(value)
    return f"signal-{signal}" if signal else ""

def director_signal_action_href(target_key: str, signal: str) -> str:
    menu_mode = str(st.session_state.get("menu_mode", "full") or "full")
    signal_param = signal or "limpar"
    return (
        f"?p=consolidado&menu={quote(menu_mode, safe='')}"
        f"&{DIRECTOR_SIGNAL_QUERY_KEY}={quote(str(target_key or ''), safe='')}"
        f"&{DIRECTOR_SIGNAL_QUERY_VALUE}={quote(str(signal_param), safe='')}"
    )

def get_query_param(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "")

def clear_director_signal_query_params():
    for param in [DIRECTOR_SIGNAL_QUERY_KEY, DIRECTOR_SIGNAL_QUERY_VALUE]:
        try:
            del st.query_params[param]
        except KeyError:
            pass

def normalize_base_dinamica(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy() if df is not None else pd.DataFrame(columns=DINAMICA_COLUMNS)
    for col in DINAMICA_COLUMNS:
        if col not in out:
            out[col] = 0.0 if col in {
                "linha_origem", "alerta_diretoria", "faturado_marco", "faturado_abril", "rec_bruto_abril",
                "rec_liquido_abril", "rec_bruto_maio", "rec_liquido_maio",
            } else ""
    out = out[DINAMICA_COLUMNS].copy()
    numeric_cols = [
        "linha_origem", "alerta_diretoria", "faturado_marco", "faturado_abril", "rec_bruto_marco",
        "rec_liquido_marco", "rec_bruto_abril", "rec_liquido_abril",
        "rec_bruto_maio", "rec_liquido_maio",
    ]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out["linha_origem"] = out["linha_origem"].astype(int)
    out["sinal_diretoria"] = out["sinal_diretoria"].apply(normalize_director_signal)
    legacy_red = (out["alerta_diretoria"] > 0) & (out["sinal_diretoria"] == "")
    out.loc[legacy_red, "sinal_diretoria"] = "vermelho"
    out["alerta_diretoria"] = (out["sinal_diretoria"] == "vermelho").astype(int)
    for col in [c for c in DINAMICA_COLUMNS if c not in numeric_cols]:
        out[col] = out[col].fillna("").astype(str).str.strip()
    mask = (out["unidade_original"] != "") & (out["operadora_original"] != "")
    out = out[mask].reset_index(drop=True)
    out.loc[out["unidade_padrao"] == "", "unidade_padrao"] = out.loc[out["unidade_padrao"] == "", "unidade_original"]
    out.loc[out["operadora_padrao"] == "", "operadora_padrao"] = out.loc[out["operadora_padrao"] == "", "operadora_original"]
    return out

def refresh_depara_from_base(base: pd.DataFrame):
    if base.empty:
        return
    units = pd.concat([
        base[["unidade_original", "unidade_padrao"]].rename(columns={"unidade_original": "sigla_origem", "unidade_padrao": "nome_padrao"}),
        read_table("de_para_unidades"),
    ], ignore_index=True)
    ops = pd.concat([
        base[["operadora_original", "operadora_padrao"]].rename(columns={"operadora_original": "sigla_origem", "operadora_padrao": "nome_padrao"}),
        read_table("de_para_operadoras"),
    ], ignore_index=True)
    for table_name, df in [("de_para_unidades", units), ("de_para_operadoras", ops)]:
        df = df[["sigla_origem", "nome_padrao"]].fillna("").astype(str)
        df["sigla_origem"] = df["sigla_origem"].str.strip()
        df["nome_padrao"] = df["nome_padrao"].str.strip()
        df = df[df["sigla_origem"] != ""]
        df["_key"] = df["sigla_origem"].apply(norm_text)
        df = df.drop_duplicates(subset="_key", keep="first").drop(columns="_key").reset_index(drop=True)
        write_table(table_name, df)

def replace_base_dinamica(base: pd.DataFrame, source_name: str, year: int = 2026):
    ensure_base_dinamica_table()
    base = normalize_base_dinamica(base)
    if "origem_arquivo" in base:
        base.loc[base["origem_arquivo"].fillna("").astype(str).str.strip() == "", "origem_arquivo"] = source_name
    base["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    write_table("base_dinamica", base)
    fat_generated, cont_generated = dinamica_to_raw_tables(base, year=int(year), origem=source_name)
    write_table("faturamento", fat_generated)
    write_table("contabilidade", cont_generated)
    refresh_depara_from_base(base)
    return base, fat_generated, cont_generated

def merge_base_dinamica(existing: pd.DataFrame, incoming: pd.DataFrame, selected_columns: list[str], source_name: str) -> pd.DataFrame:
    existing = normalize_base_dinamica(existing)
    incoming = normalize_base_dinamica(incoming)
    selected = [col for col in selected_columns if col in DINAMICA_COLUMNS]
    identity_cols = ["linha_origem", "unidade_original", "unidade_padrao", "operadora_original", "operadora_padrao"]
    selected = list(dict.fromkeys(identity_cols + selected + ["origem_arquivo", "atualizado_em"]))
    if existing.empty:
        merged = incoming.copy()
        for col in DINAMICA_COLUMNS:
            if col not in selected and col not in identity_cols:
                merged[col] = "" if col in {"observacao", "origem_arquivo", "atualizado_em"} else 0
        return normalize_base_dinamica(merged)

    out = existing.copy()
    out["_key"] = out["unidade_padrao"].apply(norm_text) + "||" + out["operadora_padrao"].apply(norm_text)
    incoming = incoming.copy()
    incoming["_key"] = incoming["unidade_padrao"].apply(norm_text) + "||" + incoming["operadora_padrao"].apply(norm_text)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    for _, row in incoming.iterrows():
        key = row["_key"]
        mask = out["_key"] == key
        if mask.any():
            idx = out.index[mask][0]
            for col in identity_cols:
                if col != "linha_origem" and str(row.get(col, "")).strip():
                    out.loc[idx, col] = row.get(col, out.loc[idx, col])
            for col in selected_columns:
                if col == "observacao":
                    new_obs = str(row.get(col, "") or "").strip()
                    old_obs = str(out.loc[idx, col] or "").strip() if col in out else ""
                    if new_obs and new_obs not in old_obs:
                        out.loc[idx, col] = f"{old_obs} | {new_obs}" if old_obs else new_obs
                elif col in out:
                    out.loc[idx, col] = row.get(col, out.loc[idx, col])
            out.loc[idx, "origem_arquivo"] = source_name
            out.loc[idx, "atualizado_em"] = now
        else:
            new_row = {col: 0 for col in DINAMICA_COLUMNS}
            for col in ["unidade_original", "unidade_padrao", "operadora_original", "operadora_padrao", "observacao", "origem_arquivo", "atualizado_em"]:
                new_row[col] = ""
            for col in identity_cols + selected_columns:
                if col in DINAMICA_COLUMNS:
                    new_row[col] = row.get(col, new_row.get(col, ""))
            new_row["origem_arquivo"] = source_name
            new_row["atualizado_em"] = now
            out = pd.concat([out, pd.DataFrame([new_row])], ignore_index=True)

    return normalize_base_dinamica(out.drop(columns="_key", errors="ignore"))

@st.cache_data(show_spinner=False, ttl=300)
def load_operational_tables(year: int = 2026) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ensure_base_dinamica_table()
    ensure_lancamentos_manuais_table()
    base = normalize_base_dinamica(read_table("base_dinamica"))
    fat_generated = read_table("faturamento")
    cont_generated = read_table("contabilidade")
    
    if not base.empty:
        fat_hist, cont_hist = dinamica_to_raw_tables(base, year=int(year), origem="base_dinamica")
        fat_generated = pd.concat([fat_hist, fat_generated], ignore_index=True) if not fat_generated.empty else fat_hist
        cont_generated = pd.concat([cont_hist, cont_generated], ignore_index=True) if not cont_generated.empty else cont_hist

    
    # Injeta Lançamentos Manuais
    try:
        lanc = read_table("lancamentos_manuais")
        if not lanc.empty:
            lanc_year = lanc[lanc["ano_referencia"].fillna(year).astype(int) == int(year)]
            
            fat_manuais = lanc_year[lanc_year["tipo_lancamento"] == "Faturamento Extra"].copy()
            if not fat_manuais.empty:
                fat_extra = pd.DataFrame({
                    "nf": fat_manuais["id"],
                    "unidade_original": fat_manuais["unidade_padrao"],
                    "unidade_padrao": fat_manuais["unidade_padrao"],
                    "operadora_original": fat_manuais["operadora_padrao"],
                    "operadora_padrao": fat_manuais["operadora_padrao"],
                    "paciente": fat_manuais["motivo"],
                    "valor_faturado": pd.to_numeric(fat_manuais["valor"], errors="coerce").fillna(0),
                    "mes_faturamento": fat_manuais["mes_referencia"].astype(int),
                    "ano_faturamento": fat_manuais["ano_referencia"].astype(int),
                    "origem_arquivo": "AJUSTE_MANUAL",
                    "fonte": "MANUAL"
                })
                fat_generated = pd.concat([fat_generated, fat_extra], ignore_index=True)
                
            cont_manuais = lanc_year[lanc_year["tipo_lancamento"] == "Recebimento Extra"].copy()
            if not cont_manuais.empty:
                cont_extra = pd.DataFrame({
                    "nf": cont_manuais["id"],
                    "unidade_original": cont_manuais["unidade_padrao"],
                    "unidade_padrao": cont_manuais["unidade_padrao"],
                    "operadora_original": cont_manuais["operadora_padrao"],
                    "operadora_padrao": cont_manuais["operadora_padrao"],
                    "valor_bruto": pd.to_numeric(cont_manuais["valor"], errors="coerce").fillna(0),
                    "valor_liquido": pd.to_numeric(cont_manuais["valor"], errors="coerce").fillna(0),
                    "data_pago": pd.NaT,
                    "mes_recebimento": cont_manuais["mes_referencia"].astype(int),
                    "ano_recebimento": cont_manuais["ano_referencia"].astype(int),
                    "observacao_original": cont_manuais["motivo"],
                    "observacao_fiscal": cont_manuais["motivo"],
                    "origem_arquivo": "AJUSTE_MANUAL",
                    "fonte": "MANUAL"
                })
                cont_generated = pd.concat([cont_generated, cont_extra], ignore_index=True)
    except Exception:
        pass

    return fat_generated, cont_generated, base

def ensure_importacoes_table():
    _db_ensure_table(
        """
        CREATE TABLE IF NOT EXISTS importacoes (
            data_hora TEXT,
            tipo_arquivo TEXT,
            nome_arquivo TEXT,
            mes_ano_identificado TEXT,
            qtd_linhas INTEGER,
            status TEXT,
            usuario TEXT,
            detalhes TEXT,
            hash_arquivo TEXT
        )
        """
    )

def register_importacao(
    tipo_arquivo: str,
    nome_arquivo: str,
    mes_ano_identificado: str,
    qtd_linhas: int,
    status: str,
    detalhes: str = "",
    hash_arquivo: str = "",
    usuario: str = "sistema",
):
    ensure_importacoes_table()
    row = pd.DataFrame([{
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "tipo_arquivo": tipo_arquivo,
        "nome_arquivo": nome_arquivo,
        "mes_ano_identificado": mes_ano_identificado,
        "qtd_linhas": int(qtd_linhas or 0),
        "status": status,
        "usuario": usuario,
        "detalhes": detalhes,
        "hash_arquivo": hash_arquivo,
    }])
    append_table("importacoes", row)

def ensure_exportacoes_table():
    _db_ensure_table(
        """
        CREATE TABLE IF NOT EXISTS exportacoes (
            exportacao_id TEXT,
            data_hora TEXT,
            tipo_relatorio TEXT,
            formato TEXT,
            nome_arquivo TEXT,
            periodo TEXT,
            qtd_linhas INTEGER,
            status TEXT,
            usuario TEXT,
            detalhes TEXT,
            observacao_manual TEXT
        )
        """
    )
    cols = _db_table_columns("exportacoes")
    if "exportacao_id" not in cols:
        _db_add_column("exportacoes", "exportacao_id", "TEXT")
    if "observacao_manual" not in cols:
        _db_add_column("exportacoes", "observacao_manual", "TEXT")

    # Preencher exportacao_id para linhas que não têm
    try:
        rows_df = _cached_fetch_sql(
            "SELECT data_hora, tipo_relatorio, formato, nome_arquivo, periodo, exportacao_id FROM exportacoes",
            None,
            _db_cache_token(),
        )
        if not rows_df.empty:
            needs_update = rows_df[rows_df["exportacao_id"].fillna("").str.strip() == ""]
            for idx, row in needs_update.iterrows():
                source = f"{idx}|{row['data_hora']}|{row['tipo_relatorio']}|{row['formato']}|{row['nome_arquivo']}|{row['periodo']}"
                new_id = hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]
                _db_execute_sql(
                    "UPDATE exportacoes SET exportacao_id = ? WHERE data_hora = ? AND nome_arquivo = ? AND (exportacao_id IS NULL OR exportacao_id = '')",
                    (new_id, row["data_hora"], row["nome_arquivo"]),
                )
    except Exception:
        pass

def register_exportacao(
    tipo_relatorio: str,
    formato: str,
    nome_arquivo: str,
    periodo: str,
    qtd_linhas: int,
    status: str = "Pronto",
    detalhes: str = "",
    usuario: str = "sistema",
):
    ensure_exportacoes_table()
    source = f"{datetime.now().isoformat()}|{tipo_relatorio}|{formato}|{nome_arquivo}|{periodo}|{usuario}"
    row = pd.DataFrame([{
        "exportacao_id": hashlib.sha1(source.encode("utf-8")).hexdigest()[:16],
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "tipo_relatorio": tipo_relatorio,
        "formato": formato,
        "nome_arquivo": nome_arquivo,
        "periodo": periodo,
        "qtd_linhas": int(qtd_linhas or 0),
        "status": status,
        "usuario": usuario.strip() or "sistema",
        "detalhes": detalhes,
        "observacao_manual": "",
    }])
    append_table("exportacoes", row)

def ensure_inconsistencias_table():
    _db_ensure_table(
        """
        CREATE TABLE IF NOT EXISTS inconsistencias_manuais (
            inconsistencia_id TEXT,
            tipo TEXT,
            origem TEXT,
            valor_encontrado TEXT,
            status TEXT,
            acao_recomendada TEXT,
            observacao_manual TEXT,
            atualizado_por TEXT,
            atualizado_em TEXT
        )
        """
    )

def file_already_imported(file_hash: str, tipo_arquivo: str) -> bool:
    if not file_hash:
        return False
    ensure_importacoes_table()
    try:
        result = _cached_fetch_sql(
            """
            SELECT COUNT(*) AS n
            FROM importacoes
            WHERE hash_arquivo = ?
              AND tipo_arquivo = ?
              AND status IN ('Importado com sucesso', 'Importado com avisos', 'Base inicial')
            """,
            (file_hash, tipo_arquivo),
            _db_cache_token(),
        )
        return int(result["n"].iloc[0]) > 0
    except Exception:
        return False

def hash_local_file_if_exists(filename: str) -> str:
    path = ROOT / "data" / "raw" / str(filename)
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_upload_dataframe(uploaded_file) -> tuple[pd.DataFrame, str]:
    data = uploaded_file.getvalue()
    file_hash = hashlib.sha256(data).hexdigest()
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        try:
            return pd.read_csv(io.BytesIO(data), sep=None, engine="python"), file_hash
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(data), sep=None, engine="python", encoding="latin1"), file_hash
    xls = pd.ExcelFile(io.BytesIO(data))
    return pd.read_excel(io.BytesIO(data), sheet_name=xls.sheet_names[0]), file_hash

def identify_period_label(df: pd.DataFrame, month_col: str, year_col: str) -> str:
    if df.empty or month_col not in df or year_col not in df:
        return "-"
    ref = (
        df[[month_col, year_col]]
        .dropna()
        .drop_duplicates()
        .sort_values([year_col, month_col])
    )
    labels = []
    for _, row in ref.iterrows():
        try:
            month = int(row[month_col])
            year_value = int(row[year_col])
            labels.append(f"{MONTHS.get(month, month)}/{year_value}")
        except Exception:
            continue
    if not labels:
        return "-"
    if len(labels) > 4:
        return ", ".join(labels[:4]) + f" +{len(labels) - 4}"
    return ", ".join(labels)

def seed_importacoes_from_current_base(fat: pd.DataFrame, cont: pd.DataFrame):
    ensure_importacoes_table()
    current = read_table("importacoes")
    if not current.empty:
        if "hash_arquivo" in current and "nome_arquivo" in current:
            needs_hash = current["hash_arquivo"].fillna("").astype(str).str.strip() == ""
            if needs_hash.any():
                current.loc[needs_hash, "hash_arquivo"] = current.loc[needs_hash, "nome_arquivo"].apply(hash_local_file_if_exists)
                write_table("importacoes", current)
        return
    if not fat.empty:
        fat_name = str(fat["origem_arquivo"].dropna().iloc[0]) if "origem_arquivo" in fat and fat["origem_arquivo"].notna().any() else "Base inicial"
        register_importacao(
            "Faturamento IW",
            fat_name,
            identify_period_label(fat, "mes_faturamento", "ano_faturamento"),
            len(fat),
            "Base inicial",
            "Registro criado automaticamente a partir da base SQLite existente.",
            hash_local_file_if_exists(fat_name),
        )
    if not cont.empty:
        cont_name = str(cont["origem_arquivo"].dropna().iloc[0]) if "origem_arquivo" in cont and cont["origem_arquivo"].notna().any() else "Base inicial"
        register_importacao(
            "Contabilidade/Recebimentos",
            cont_name,
            identify_period_label(cont, "mes_recebimento", "ano_recebimento"),
            len(cont),
            "Base inicial",
            "Registro criado automaticamente a partir da base SQLite existente.",
            hash_local_file_if_exists(cont_name),
        )

def fmt_money(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def html_text(value) -> str:
    try:
        if pd.isna(value):
            text = ""
        else:
            text = str(value)
    except Exception:
        text = str(value or "")
    return escape(text).replace("$", "&#36;")

def fmt_money_html(v) -> str:
    return html_text(fmt_money(v))

def fmt_pct(v):
    try:
        return f"{float(v)*100:.2f}%".replace(".", ",")
    except Exception:
        return "0,00%"

def fmt_pct_display(v):
    try:
        return f"{float(v):.1f}%".replace(".", ",")
    except Exception:
        return "0,0%"

def as_bool_flag(value) -> bool:
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass
    if isinstance(value, str):
        return norm_text(value) in {"1", "SIM", "S", "TRUE", "VERDADEIRO", "X", "ALERTA"}
    try:
        return float(value) > 0
    except Exception:
        return bool(value)

def director_alert_badge(value=True) -> str:
    if not as_bool_flag(value):
        return ""
    return '<span class="director-alert-badge">Alerta diretoria</span>'

def short_label(value, max_len: int = 34) -> str:
    text = "" if pd.isna(value) else str(value)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."

def obs_text_html(value) -> str:
    text = html_text(value)
    return text.replace(" | ", "<br>")

def status_pill(status: str) -> str:
    label = html_text(status or "")
    key = norm_text(label)
    css = "status-pill"
    if key in {"PENDENTE", "CRITICA", "CRITICO", "ACIMA DO FATURADO"}:
        css += " alert"
    elif key in {"RECEBIDO"}:
        css += " ok"
    elif key in {"PARCIAL", "A REVISAR"}:
        css += " warn"
    return f'<span class="{css}">{label}</span>'

def is_numeric_value(value) -> bool:
    try:
        if pd.isna(value):
            return False
        float(value)
        return True
    except Exception:
        return False

def render_native_table(
    df: pd.DataFrame,
    columns: list[str],
    labels: dict[str, str],
    money_cols: set[str] | None = None,
    pct_cols: set[str] | None = None,
    status_cols: set[str] | None = None,
    strong_cols: set[str] | None = None,
    highlight_cols: set[str] | None = None,
    max_rows: int = 30,
):
    money_cols = money_cols or set()
    pct_cols = pct_cols or set()
    status_cols = status_cols or set()
    strong_cols = strong_cols or set()
    highlight_cols = highlight_cols or set()
    columns = [col for col in columns if col in df.columns]
    view = df.head(max_rows).copy()

    head = "".join(
        f'<th class="{"faturamento-col" if col in highlight_cols else ""}">{html_text(labels.get(col, col))}</th>'
        for col in columns
    )
    body_rows = []
    for _, row in view.iterrows():
        is_total = str(row.get("unidade_padrao", "")).upper().startswith("TOTAIS")
        is_director_alert = as_bool_flag(row.get("alerta_diretoria", 0))
        signal_class = director_signal_class(row.get("sinal_diretoria", "vermelho" if is_director_alert else ""))
        cells = []
        for col in columns:
            value = row.get(col, "")
            css = []
            if col in money_cols or col in pct_cols or is_numeric_value(value):
                css.append("num")
            if col in strong_cols or is_total:
                css.append("strong")
            if col in highlight_cols:
                css.append("faturamento-col")
            if "observ" in col:
                css.append("obs-col")
            if col in money_cols:
                content = fmt_money_html(value)
            elif col in pct_cols:
                content = html_text(fmt_pct_display(value))
            elif col in status_cols:
                content = status_pill(str(value))
            elif col == "alerta_diretoria":
                content = director_alert_badge(value)
            elif "observ" in col:
                content = f'<span class="obs-full">{obs_text_html(value)}</span>' if str(value or "").strip() else ""
            else:
                max_len = 76 if "observ" in col else 42
                title = html_text(value)
                content = html_text(short_label(value, max_len))
                if "observ" in col and title:
                    content = f'<span title="{title}">{content}</span>'
            cells.append(f'<td class="{" ".join(css)}">{content}</td>')
        row_classes = []
        if is_total:
            row_classes.append("total-row")
        if is_director_alert:
            row_classes.append("director-alert-row")
        if signal_class:
            row_classes.append(signal_class)
        row_class = f' class="{" ".join(row_classes)}"' if row_classes else ""
        body_rows.append(f"<tr{row_class}>{''.join(cells)}</tr>")

    st.markdown(
        f"""
        <div class="native-table-wrap">
            <table class="native-table">
                <thead><tr>{head}</tr></thead>
                <tbody>{''.join(body_rows)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

def build_column_config(state_key: str, columns: list[str], labels: dict[str, str], locked: set[str] | None = None) -> pd.DataFrame:
    locked = locked or set()
    base = pd.DataFrame([
        {
            "coluna": col,
            "nome": labels.get(col, col),
            "visivel": True,
            "ordem": idx + 1,
            "fixa": "Sim" if col in locked else "Não",
        }
        for idx, col in enumerate(columns)
    ])

    saved_payload = load_visual_preference(f"{state_key}_columns")
    saved = pd.DataFrame(saved_payload) if isinstance(saved_payload, list) else pd.DataFrame()
    if not saved.empty and {"coluna", "visivel", "ordem"}.issubset(saved.columns):
        base = base.merge(
            saved[["coluna", "visivel", "ordem"]].rename(columns={"visivel": "visivel_salva", "ordem": "ordem_salva"}),
            on="coluna",
            how="left",
        )
        base["visivel"] = base["visivel_salva"].combine_first(base["visivel"]).astype(bool)
        base["ordem"] = pd.to_numeric(base["ordem_salva"], errors="coerce").combine_first(base["ordem"])
        base = base.drop(columns=["visivel_salva", "ordem_salva"])

    base.loc[base["coluna"].isin(locked), "visivel"] = True
    base["ordem"] = pd.to_numeric(base["ordem"], errors="coerce").fillna(9999)
    return base

def configure_columns(state_key: str, columns: list[str], labels: dict[str, str], locked: set[str] | None = None) -> list[str]:
    locked = locked or set()
    config = build_column_config(state_key, columns, labels, locked)
    visible = config[config["visivel"]].sort_values(["ordem", "nome"])["coluna"].tolist()
    locked_order = [col for col in columns if col in locked]
    return locked_order + [col for col in visible if col in columns and col not in locked]

def render_column_settings(state_key: str, title: str, columns: list[str], labels: dict[str, str], locked: set[str] | None = None):
    locked = locked or set()
    version_key = f"{state_key}_column_config_version"
    version = int(st.session_state.get(version_key, 0))
    base = build_column_config(state_key, columns, labels, locked)

    st.markdown(f"### {title}")
    st.caption("Use esta área para preparar a visão antes da apresentação. As abas principais mostram apenas os dados.")
    optional_cols = [col for col in columns if col not in locked]
    default_visible = base[(base["visivel"]) & (~base["coluna"].isin(locked))]["coluna"].tolist()
    visible_optional = st.multiselect(
        "Colunas visíveis",
        options=optional_cols,
        default=[col for col in default_visible if col in optional_cols],
        format_func=lambda col: labels.get(col, col),
        key=f"{state_key}_settings_visible_columns_{version}",
    )
    base["visivel"] = base["coluna"].isin(locked) | base["coluna"].isin(visible_optional)
    ordered_df = base[base["visivel"]].sort_values(["ordem", "nome"]).copy()
    movable_cols = [col for col in ordered_df["coluna"].tolist() if col not in locked]
    sortable_label_to_col: dict[str, str] = {}
    sortable_items: list[str] = []
    for col in movable_cols:
        label = labels.get(col, col)
        item = label
        if item in sortable_label_to_col:
            item = f"{label} ({col})"
        sortable_label_to_col[item] = col
        sortable_items.append(item)

    sorted_items = []
    if sortable_items:
        st.caption("Arraste as colunas abaixo para definir a ordem de exibição.")
        sorted_items = sort_items(
            sortable_items,
            direction="vertical",
            custom_style="""
            .sortable-component {
                border: 1px solid #C7CBD7;
                border-radius: 8px;
                background: #FFFFFF;
                padding: 10px;
            }
            .sortable-component.vertical .sortable-item {
                border: 1px solid #DDE1EA;
                border-radius: 6px;
                background: #F8FAFC;
                color: #001945;
                font-weight: 700;
                text-align: left;
                padding: 10px 12px;
                margin-bottom: 8px;
                cursor: grab;
            }
            .sortable-component.vertical .sortable-item:active {
                cursor: grabbing;
            }
            """,
            key=f"{state_key}_settings_sortable_columns_{version}",
        )
    else:
        st.caption("Somente colunas fixas estão visíveis nesta configuração.")

    order_cols = [col for col in columns if col in locked]
    order_cols += [sortable_label_to_col[item] for item in sorted_items if item in sortable_label_to_col]
    order_map = {col: idx + 1 for idx, col in enumerate(order_cols)}

    chosen = base.copy()
    chosen.loc[chosen["coluna"].isin(locked), "visivel"] = True
    chosen["ordem"] = chosen["coluna"].map(order_map).fillna(9999)
    chosen_to_save = chosen[["coluna", "visivel", "ordem"]].copy()
    chosen_to_save["visivel"] = chosen_to_save["visivel"].astype(bool)
    chosen_to_save["ordem"] = pd.to_numeric(chosen_to_save["ordem"], errors="coerce").fillna(9999).astype(int)

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Salvar preferências de colunas", type="primary", key=f"{state_key}_save_columns"):
            save_visual_preference(f"{state_key}_columns", chosen_to_save.to_dict("records"))
            st.success("Preferências de colunas salvas.")
            st.rerun()
    with c2:
        if st.button("Restaurar colunas padrão", key=f"{state_key}_reset_columns"):
            delete_visual_preference(f"{state_key}_columns")
            st.session_state[version_key] = version + 1
            st.rerun()

def get_visible_kpis(state_key: str, items: list[tuple[str, str]]) -> list[str]:
    valid = [key for key, _ in items]
    saved = load_visual_preference(f"{state_key}_kpis")
    if saved is None:
        return valid
    if isinstance(saved, dict):
        saved = saved.get("visible", valid)
    elif isinstance(saved, list) and not saved:
        return valid
    return [key for key in saved if key in valid]

def render_kpi_settings(state_key: str, title: str, items: list[tuple[str, str]]):
    version_key = f"{state_key}_kpi_config_version"
    version = int(st.session_state.get(version_key, 0))
    selected = get_visible_kpis(state_key, items)
    st.markdown(f"### {title}")
    selected_widget = st.multiselect(
        "Cards visíveis",
        options=[item_key for item_key, _ in items],
        default=selected,
        format_func=lambda item_key: dict(items).get(item_key, item_key),
        key=f"{state_key}_settings_kpis_{version}",
    )
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Salvar preferências de cards", type="primary", key=f"{state_key}_save_kpis"):
            save_visual_preference(f"{state_key}_kpis", {"visible": selected_widget})
            st.success("Preferências de cards salvas.")
            st.rerun()
    with c2:
        if st.button("Restaurar cards padrão", key=f"{state_key}_reset_kpis"):
            delete_visual_preference(f"{state_key}_kpis")
            st.session_state[version_key] = version + 1
            st.rerun()

def render_kpi_row(state_key: str, cards: list[dict]):
    items = [(card["key"], card["label"]) for card in cards]
    visible_keys = set(get_visible_kpis(state_key, items))
    visible_cards = [card for card in cards if card["key"] in visible_keys]
    if not visible_cards:
        return
    cols = st.columns(len(visible_cards))
    for col, card in zip(cols, visible_cards):
        with col:
            render_kpi_card(
                card["label"],
                card["value"],
                card.get("note", ""),
                alert=bool(card.get("alert", False)),
            )

def row_observacoes_text(row: pd.Series) -> str:
    parts = []
    fiscal = str(row.get("observacao_fiscal", "") or "").strip()
    manual = str(row.get("comentario_manual", "") or "").strip()
    if fiscal:
        parts.append(fiscal)
    if manual:
        parts.append(f"Manual: {manual}")
    return " | ".join(parts)

def add_observacoes_consolidadas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "observacao_fiscal" not in out:
        out["observacao_fiscal"] = ""
    if "comentario_manual" not in out:
        out["comentario_manual"] = ""
    out["observacoes_consolidadas"] = out.apply(row_observacoes_text, axis=1)
    return out

def merge_manual_comments(consolidado: pd.DataFrame, ano: int, meses: list[int]) -> pd.DataFrame:
    if consolidado.empty:
        return add_observacoes_consolidadas(consolidado)
    ensure_comentarios_table()
    comentarios = read_table("comentarios_manuais")
    out = consolidado.copy()
    out["comentario_manual"] = ""
    if comentarios.empty:
        return add_observacoes_consolidadas(out)

    for col in ["unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia", "comentario_manual"]:
        if col not in comentarios:
            comentarios[col] = ""

    meses_validos = {int(m) for m in meses if str(m).strip()}
    comentarios_ref = comentarios.copy()
    comentarios_ref["mes_referencia"] = pd.to_numeric(comentarios_ref["mes_referencia"], errors="coerce").fillna(0).astype(int)
    comentarios_ref["ano_referencia"] = pd.to_numeric(comentarios_ref["ano_referencia"], errors="coerce").fillna(0).astype(int)
    
    # Filtrar vazios e ordenar do mais recente para o mais antigo
    comentarios_ref = comentarios_ref[comentarios_ref["comentario_manual"].fillna("").astype(str).str.strip() != ""]
    if comentarios_ref.empty:
        return add_observacoes_consolidadas(out)
        
    comentarios_ref = comentarios_ref.sort_values(["ano_referencia", "mes_referencia"], ascending=[False, False])
    
    mask_current = (comentarios_ref["ano_referencia"] == int(ano)) & (comentarios_ref["mes_referencia"].isin(meses_validos))
    current_df = comentarios_ref[mask_current].copy()
    historical_df = comentarios_ref[~mask_current].copy()
    
    grouped_current = pd.Series(dtype=str)
    if not current_df.empty:
        current_df["comentario_manual"] = current_df.apply(
            lambda row: f"{MONTHS.get(int(row['mes_referencia']), row['mes_referencia'])}: {str(row['comentario_manual']).strip()}", axis=1)
        grouped_current = current_df.groupby(["unidade_padrao", "operadora_padrao"], dropna=False)["comentario_manual"].apply(lambda vals: " | ".join(dict.fromkeys(v for v in vals if str(v).strip())))
        
    grouped_historical = pd.Series(dtype=str)
    if not historical_df.empty:
        historical_df["comentario_manual"] = historical_df.apply(
            lambda row: f"(Herdado {MONTHS.get(int(row['mes_referencia']), row['mes_referencia'])}/{int(row['ano_referencia'])}): {str(row['comentario_manual']).strip()}", axis=1)
        grouped_historical = historical_df.groupby(["unidade_padrao", "operadora_padrao"], dropna=False).first()["comentario_manual"]
        
    combined = grouped_current.copy() if not grouped_current.empty else pd.Series(dtype=str)
    
    if not grouped_historical.empty:
        if combined.empty:
            combined = grouped_historical
        else:
            missing = grouped_historical.index.difference(combined.index)
            combined = pd.concat([combined, grouped_historical.loc[missing]])
            
    if combined.empty:
        return add_observacoes_consolidadas(out)
        
    combined_df = combined.reset_index(name="comentario_manual_comentado")
    out = out.merge(combined_df, on=["unidade_padrao", "operadora_padrao"], how="left")
    out["comentario_manual"] = out["comentario_manual_comentado"].fillna("").astype(str)
    out = out.drop(columns=["comentario_manual_comentado"])
    
    return add_observacoes_consolidadas(out)

def merge_base_dinamica_observations(consolidado: pd.DataFrame, base_dinamica: pd.DataFrame) -> pd.DataFrame:
    if consolidado.empty or base_dinamica is None or base_dinamica.empty:
        return consolidado
    # Determina a coluna de observação disponível
    obs_col = None
    if "observacao" in base_dinamica.columns:
        obs_col = "observacao"
    elif "observacao_fiscal" in base_dinamica.columns:
        obs_col = "observacao_fiscal"
    if obs_col is None:
        return consolidado
    base = base_dinamica.copy()
    # Garante colunas necessárias
    for col in ["unidade_padrao", "operadora_padrao", "sinal_diretoria", "alerta_diretoria"]:
        if col not in base.columns:
            base[col] = "" if col != "alerta_diretoria" else 0
    # Coluna de ordem (pode não existir no schema novo)
    if "linha_origem" not in base.columns:
        base["linha_origem"] = range(1, len(base) + 1)
    grouped = (
        base.groupby(["unidade_padrao", "operadora_padrao"], dropna=False)
        .agg(
            observacao_dinamica=(obs_col, lambda values: " | ".join(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))),
            alerta_diretoria_base=("alerta_diretoria", lambda values: int(pd.to_numeric(values, errors="coerce").fillna(0).max() > 0)),
            sinal_diretoria_base=("sinal_diretoria", aggregate_director_signal),
            ordem_base_dinamica=("linha_origem", "min"),
        )
        .reset_index()
    )
    out = consolidado.merge(grouped, on=["unidade_padrao", "operadora_padrao"], how="left")
    if "observacao_fiscal" not in out:
        out["observacao_fiscal"] = ""
    mask = out["observacao_dinamica"].fillna("").astype(str).str.strip() != ""
    out.loc[mask, "observacao_fiscal"] = out.loc[mask, "observacao_dinamica"]
    out["sinal_diretoria"] = out.get("sinal_diretoria_base", "").fillna("").astype(str).apply(normalize_director_signal)
    legacy_red = (pd.to_numeric(out.get("alerta_diretoria_base", 0), errors="coerce").fillna(0) > 0) & (out["sinal_diretoria"] == "")
    out.loc[legacy_red, "sinal_diretoria"] = "vermelho"
    out["alerta_diretoria"] = (out["sinal_diretoria"] == "vermelho").astype(int)
    out = out.drop(columns=["observacao_dinamica", "alerta_diretoria_base", "sinal_diretoria_base"], errors="ignore")

    # Enriquece com observações históricas do consolidado_historico
    # para linhas que ainda não têm observacao_fiscal preenchida
    # Usa match exato + fallback por substring (cobre nomes que mudaram entre meses)
    try:
        hist = read_table("consolidado_historico")
        if not hist.empty and "observacao_fiscal" in hist.columns:
            hist_filtered = hist[hist["observacao_fiscal"].fillna("").astype(str).str.strip().ne("")].copy()
            if not hist_filtered.empty:
                hist_obs = (
                    hist_filtered
                    .groupby(["unidade_padrao", "operadora_padrao"])["observacao_fiscal"]
                    .apply(lambda vals: " | ".join(dict.fromkeys(
                        v.strip() for v in vals.fillna("").astype(str) if v.strip()
                    )))
                    .reset_index()
                    .rename(columns={"observacao_fiscal": "_hist_obs"})
                )
                if not hist_obs.empty:
                    # Constrói dict de obs por (unidade, operadora) antes do merge
                    hist_obs_dict = {
                        (str(r["unidade_padrao"]).strip().upper(), str(r["operadora_padrao"]).strip().upper()): str(r["_hist_obs"])
                        for _, r in hist_obs.iterrows()
                        if str(r.get("_hist_obs", "")).strip()
                    }
                    # Passo 1: merge exato por unidade+operadora
                    out = out.merge(hist_obs, on=["unidade_padrao", "operadora_padrao"], how="left")
                    empty_mask = out["observacao_fiscal"].fillna("").astype(str).str.strip() == ""
                    out.loc[empty_mask, "observacao_fiscal"] = out.loc[empty_mask, "_hist_obs"].fillna("")
                    out = out.drop(columns=["_hist_obs"], errors="ignore")

                    # Passo 2: fallback por substring para nomes que mudaram entre meses
                    still_empty = out["observacao_fiscal"].fillna("").astype(str).str.strip() == ""
                    if still_empty.any():
                        for i in out[still_empty].index:
                            u_curr = str(out.at[i, "unidade_padrao"]).strip().upper()
                            o_curr = str(out.at[i, "operadora_padrao"]).strip().upper()
                            for (u_h, o_h), obs_text in hist_obs_dict.items():
                                u_match = u_h in u_curr or u_curr in u_h
                                o_match = o_h == o_curr or o_h in o_curr or o_curr in o_h
                                if u_match and o_match:
                                    out.at[i, "observacao_fiscal"] = obs_text
                                    break
    except Exception:
        pass  # consolidado_historico pode não existir

    return out

def consolidado_pivot_column_spec(filtered: pd.DataFrame, fat_months: list[int], rec_months: list[int]) -> tuple[list[str], dict[str, str], set[str], set[str]]:
    display_cols = ["unidade_padrao", "operadora_padrao"]
    for month in fat_months:
        col = f"fat_{month}"
        if col in filtered:
            display_cols.append(col)
    display_cols.append("faturado")
    for month in rec_months:
        for col in [f"rec_bruto_{month}", f"rec_liquido_{month}"]:
            if col in filtered:
                display_cols.append(col)
    display_cols += [
        "total_recebido_bruto",
        "total_recebido_liquido",
        "diferenca_pendente",
        "perc_recebido_total",
        "status",
    ]
    display_cols = [col for col in display_cols if col in filtered.columns]

    labels = {
        "unidade_padrao": "Unidade",
        "operadora_padrao": "Operadora",
        "faturado": "Faturamento Total",
        "total_recebido_bruto": "Rec. bruto total",
        "total_recebido_liquido": "Rec. líquido total",
        "diferenca_pendente": "Dif. pendente",
        "perc_recebido_total": "% recebido",
        "status": "Status",
        "alerta_diretoria": "Alerta",
        "observacoes_consolidadas": "Observações",
    }
    money_cols = {"faturado", "total_recebido_bruto", "total_recebido_liquido", "diferenca_pendente"}
    for month in fat_months:
        if f"fat_{month}" in display_cols:
            labels[f"fat_{month}"] = f"Fat. {MONTHS.get(month, month)}"
            money_cols.add(f"fat_{month}")
    for month in rec_months:
        if f"rec_bruto_{month}" in display_cols:
            labels[f"rec_bruto_{month}"] = f"Rec. bruto {MONTHS.get(month, month)}"
            money_cols.add(f"rec_bruto_{month}")
        if f"rec_liquido_{month}" in display_cols:
            labels[f"rec_liquido_{month}"] = f"Rec. líquido {MONTHS.get(month, month)}"
            money_cols.add(f"rec_liquido_{month}")

    numeric_cols = {
        col for col in display_cols
        if col not in {"unidade_padrao", "operadora_padrao", "status", "observacoes_consolidadas"}
    }
    return display_cols, labels, money_cols, numeric_cols

def render_consolidado_pivot_table(filtered: pd.DataFrame, fat_months: list[int], rec_months: list[int]):
    display_cols, labels, money_cols, numeric_cols = consolidado_pivot_column_spec(filtered, fat_months, rec_months)
    display_cols = configure_columns(
        "consolidado",
        display_cols,
        labels,
        locked={"unidade_padrao", "operadora_padrao"},
    )
    table_cols = [col for col in display_cols if col != "observacoes_consolidadas"]
    col_span = max(1, len(table_cols))

    def aggregate_row(group: pd.DataFrame, unidade: str, operadora: str, status: str, obs: str) -> dict:
        row = {}
        total_fat = float(pd.to_numeric(group.get("faturado", 0), errors="coerce").fillna(0).sum()) if "faturado" in group else 0
        total_rec = float(pd.to_numeric(group.get("total_recebido_bruto", 0), errors="coerce").fillna(0).sum()) if "total_recebido_bruto" in group else 0
        for col in table_cols:
            if col == "unidade_padrao":
                row[col] = unidade
            elif col == "operadora_padrao":
                row[col] = operadora
            elif col == "status":
                row[col] = status
            elif col == "observacoes_consolidadas":
                row[col] = obs
            elif col == "perc_recebido_total":
                row[col] = (total_rec / total_fat * 100) if total_fat else 0
            elif col in numeric_cols:
                row[col] = pd.to_numeric(group[col], errors="coerce").fillna(0).sum()
            else:
                row[col] = ""
        return row

    rows: list[tuple[str, dict, str]] = []
    sort_cols = ["unidade_padrao", "diferenca_pendente"] if "diferenca_pendente" in filtered else ["unidade_padrao"]
    filtered_sorted = filtered.sort_values(sort_cols, ascending=[True, False] if len(sort_cols) == 2 else True).copy()
    for unidade, group in filtered_sorted.groupby("unidade_padrao", dropna=False, sort=True):
        rows.append((
            "unit-total-row",
            aggregate_row(group, str(unidade), f"Total da unidade ({group['operadora_padrao'].nunique()} operadoras)", "Subtotal", ""),
            "",
        ))
        details = group.sort_values("diferenca_pendente", ascending=False) if "diferenca_pendente" in group else group
        for _, detail in details.iterrows():
            detail_row = {}
            for col in table_cols:
                if col == "unidade_padrao":
                    detail_row[col] = ""
                elif col == "operadora_padrao":
                    detail_row[col] = str(detail.get(col, ""))
                elif col == "perc_recebido_total":
                    detail_row[col] = float(detail.get(col, 0) or 0) * 100
                else:
                    detail_row[col] = detail.get(col, "")
            obs_text = str(detail.get("observacoes_consolidadas", "") or "").strip()
            operadora_note = str(detail.get("operadora_padrao", "") or "").strip()
            note = f"{operadora_note}: {obs_text}" if obs_text and operadora_note else obs_text
            rows.append(("detail-row", detail_row, note))
    rows.append(("grand-total-row", aggregate_row(filtered, "TOTAL GERAL", "", "Total", ""), ""))

    def column_css(col: str) -> str:
        classes = []
        if col == "faturado" or col.startswith("fat_"):
            classes.append("faturamento-col")
        if col == "observacoes_consolidadas":
            classes.append("obs-col")
        return " ".join(classes)

    head = "".join(f'<th class="{column_css(col)}">{html_text(labels.get(col, col))}</th>' for col in table_cols)
    body = []
    for row_class, row, note in rows:
        cells = []
        for col in table_cols:
            value = row.get(col, "")
            classes = [column_css(col)]
            if col in money_cols or col == "perc_recebido_total":
                classes.append("num")
            if row_class in {"unit-total-row", "grand-total-row"}:
                classes.append("strong")
            if col in money_cols:
                content = fmt_money_html(value)
            elif col == "perc_recebido_total":
                content = html_text(fmt_pct_display(value))
            elif col == "status":
                content = status_pill(str(value))
            elif col == "observacoes_consolidadas":
                content = f'<span class="obs-full">{obs_text_html(value)}</span>' if str(value or "").strip() else ""
            else:
                title = html_text(value)
                content = html_text(short_label(value, 58 if col == "observacoes_consolidadas" else 42))
                if col == "observacoes_consolidadas" and title:
                    content = f'<span title="{title}">{content}</span>'
            cells.append(f'<td class="{" ".join(c for c in classes if c)}">{content}</td>')
        body.append(f'<tr class="{row_class}">{"".join(cells)}</tr>')
        if note:
            note_row_class = "unit-total-note-row" if row_class == "unit-total-row" else "obs-note-row"
            note_label = "Resumo de observações" if row_class == "unit-total-row" else "Observação"
            body.append(
                f'<tr class="{note_row_class}"><td colspan="{col_span}">'
                f'<span class="obs-note-label">{note_label}</span>'
                f'<span class="obs-full">{obs_text_html(note)}</span>'
                f'</td></tr>'
            )

    st.markdown(
        f"""
        <div class="native-table-wrap pivot-table-wrap">
            <table class="native-table pivot-table">
                <thead><tr>{head}</tr></thead>
                <tbody>{''.join(body)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_consolidado_sheet_table(filtered: pd.DataFrame, fat_months: list[int], rec_months: list[int], year: int, enable_signal_actions: bool = False):
    fat_cols = [f"fat_{month}" for month in fat_months if f"fat_{month}" in filtered]
    rec_cols = [f"rec_bruto_{month}" for month in rec_months if f"rec_bruto_{month}" in filtered]
    table_cols = ["linha_label", *fat_cols, *rec_cols, "observacoes_consolidadas"]
    money_cols = set(fat_cols + rec_cols)

    labels = {
        "linha_label": "Unidade / Operadora",
        "observacoes_consolidadas": "Observação",
    }
    for month in fat_months:
        col = f"fat_{month}"
        if col in table_cols:
            labels[col] = f"Faturado {MONTHS.get(month, month)}"
    for month in rec_months:
        col = f"rec_bruto_{month}"
        if col in table_cols:
            labels[col] = f"Rec. Bruto {MONTHS.get(month, month)}"

    def money_or_blank_html(value) -> str:
        try:
            if abs(float(value or 0)) < 0.005:
                return ""
        except Exception:
            return ""
        return fmt_money_html(value)

    def unit_total_row(group: pd.DataFrame, unidade: str) -> dict:
        row = {"linha_label": unidade, "observacoes_consolidadas": ""}
        for col in money_cols:
            row[col] = pd.to_numeric(group[col], errors="coerce").fillna(0).sum()
        return row

    def signal_actions_html(target_key: str, current_signal: str) -> str:
        if not enable_signal_actions or not target_key:
            return ""
        dots = []
        for signal, label, css_class in [
            ("", "Sem marcador", "none"),
            ("verde", "Verde", "verde"),
            ("amarelo", "Amarelo", "amarelo"),
            ("vermelho", "Vermelho", "vermelho"),
        ]:
            active = " is-active" if normalize_director_signal(current_signal) == signal else ""
            dots.append(
                f'<a class="sheet-signal-dot signal-dot-{css_class}{active}" '
                f'href="{director_signal_action_href(target_key, signal)}" '
                f'target="_self" title="Marcar {html_text(label)}" aria-label="Marcar {html_text(label)}"></a>'
            )
        return f'<span class="sheet-row-signal-actions">{"".join(dots)}</span>'

    work = filtered.copy()
    # unit_order already comes sorted from the passed filtered df, so we preserve its unique order
    unit_order = work["unidade_padrao"].drop_duplicates().tolist()


    rows: list[tuple[str, dict]] = []
    for unidade in unit_order:
        group = work[work["unidade_padrao"].astype(str) == str(unidade)].copy()
        unit_signal = aggregate_director_signal(group["sinal_diretoria"]) if "sinal_diretoria" in group else ""
        if not unit_signal and "alerta_diretoria" in group and group["alerta_diretoria"].apply(as_bool_flag).any():
            unit_signal = "vermelho"
        unit_class = "unit-total-row"
        if unit_signal == "vermelho":
            unit_class += " unit-alert-row"
        elif unit_signal:
            unit_class += f" unit-signal-{unit_signal}"
        rows.append((unit_class, unit_total_row(group, str(unidade))))
        details = group # It is already sorted correctly from the outside!
        for idx, detail in details.iterrows():
            row = {"linha_label": str(detail.get("operadora_padrao", ""))}
            for col in money_cols:
                row[col] = detail.get(col, "")
            row["observacoes_consolidadas"] = str(detail.get("observacoes_consolidadas", "") or "").strip()
            signal = normalize_director_signal(detail.get("sinal_diretoria", ""))
            if not signal and as_bool_flag(detail.get("alerta_diretoria", 0)):
                signal = "vermelho"
            row["_target_key"] = norm_text(detail.get("unidade_padrao", "")) + "||" + norm_text(detail.get("operadora_padrao", ""))
            row["_signal"] = signal
            row["_idx"] = idx
            row["_unidade"] = str(detail.get("unidade_padrao", ""))
            row["_operadora"] = str(detail.get("operadora_padrao", ""))
            detail_class = f"detail-row signal-{signal}" if signal else "detail-row"
            rows.append((detail_class, row))

    def column_css(col: str) -> str:
        classes = []
        if col.startswith("fat_"):
            classes += ["sheet-money-col", "sheet-fat-col", f"fat-month-{col.split('_')[-1]}"]
        elif col.startswith("rec_bruto_"):
            classes.append("sheet-money-col")
        if col == "observacoes_consolidadas":
            classes.append("sheet-obs-col")
        return " ".join(classes)

    head = "".join(f'<th class="{column_css(col)}">{html_text(labels.get(col, col))}</th>' for col in table_cols)
    body = []
    for row_class, row in rows:
        cells = []
        for col in table_cols:
            value = row.get(col, "")
            classes = [column_css(col)]
            if col in money_cols:
                classes.append("num")
                if row_class.startswith("detail-row"):
                    idx = row.get("_idx")
                    cell_id = f"{idx}||{col}"
                    val_str = f"{float(value or 0):.2f}"
                    # Don't show 0.00 to make it cleaner, like money_or_blank_html
                    if abs(float(value or 0)) < 0.005: val_str = ""
                    content = f'<input class="editable-cell" id="{cell_id}" type="text" value="{val_str}">'
                else:
                    content = money_or_blank_html(value)
            elif col == "observacoes_consolidadas":
                content = f'<span class="obs-full">{obs_text_html(value)}</span>' if str(value or "").strip() else ""
            else:
                title = html_text(value)
                content = html_text(short_label(value, 46))
                if title:
                    content = f'<span title="{title}">{content}</span>'
                if col == "linha_label" and row_class.startswith("detail-row"):
                    actions = signal_actions_html(str(row.get("_target_key", "")), str(row.get("_signal", "")))
                    content = f'<span class="sheet-line-label" title="{title}">{html_text(short_label(value, 34))}</span>{actions}'
                    content = f'<div class="sheet-line-cell">{content}</div>'
            if row_class.startswith("unit-total-row"):
                classes.append("strong")
            cells.append(f'<td class="{" ".join(c for c in classes if c)}">{content}</td>')
        body.append(f'<tr class="{row_class}">{"".join(cells)}</tr>')

    st.markdown(
        f"""
        <div class="native-table-wrap pivot-table-wrap sheet-pivot-wrap">
            <table class="native-table pivot-table sheet-pivot">
                <thead><tr>{head}</tr></thead>
                <tbody>{''.join(body)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

def build_consolidado_inline_payload(filtered: pd.DataFrame, fat_months: list[int], rec_months: list[int]) -> dict:
    fat_cols = [f"fat_{month}" for month in fat_months if f"fat_{month}" in filtered]
    rec_cols = [f"rec_bruto_{month}" for month in rec_months if f"rec_bruto_{month}" in filtered]
    money_cols = fat_cols + rec_cols

    columns = [{"key": "linha_label", "label": "Unidade / Operadora", "kind": "label"}]
    columns.extend(
        {"key": col, "label": f"Faturado {MONTHS.get(month, month)}", "kind": "fat", "month": int(month)}
        for month, col in [(month, f"fat_{month}") for month in fat_months]
        if col in fat_cols
    )
    columns.extend(
        {"key": col, "label": f"Rec. Bruto {MONTHS.get(month, month)}", "kind": "money", "month": int(month)}
        for month, col in [(month, f"rec_bruto_{month}") for month in rec_months]
        if col in rec_cols
    )
    columns.append({
        "key": "observacoes_consolidadas",
        "label": "Observa\u00e7\u00e3o",
        "kind": "observation",
    })

    fresh_base = read_table("base_dinamica")
    fresh_lookup: dict[str, dict] = {}
    if not fresh_base.empty:
        fresh_base = fresh_base.copy()
        # Determina qual coluna de observação existe no DB
        obs_col = "observacao" if "observacao" in fresh_base.columns else (
            "observacao_fiscal" if "observacao_fiscal" in fresh_base.columns else None
        )
        if "sinal_diretoria" not in fresh_base.columns:
            fresh_base["sinal_diretoria"] = ""
        fresh_base["_key"] = (
            fresh_base["unidade_padrao"].fillna("").astype(str).apply(norm_text)
            + "||"
            + fresh_base["operadora_padrao"].fillna("").astype(str).apply(norm_text)
        )
        for key, group in fresh_base.groupby("_key", dropna=False):
            observations = []
            if obs_col:
                observations = [
                    str(value).strip()
                    for value in group[obs_col].fillna("").astype(str)
                    if str(value).strip()
                ]
            fresh_lookup[str(key)] = {
                "signal": aggregate_director_signal(group["sinal_diretoria"]),
                "observation": " | ".join(dict.fromkeys(observations)),
            }

    # Enriquece com observações históricas de consolidado_historico
    # Usa match exato primeiro, depois fallback por prefixo/substring de unidade+operadora
    try:
        hist_table = read_table("consolidado_historico")
        if not hist_table.empty and "observacao_fiscal" in hist_table.columns:
            hist_with_obs = hist_table[
                hist_table["observacao_fiscal"].fillna("").astype(str).str.strip().ne("")
            ].copy()
            if not hist_with_obs.empty:
                hist_with_obs["_key"] = (
                    hist_with_obs["unidade_padrao"].fillna("").astype(str).apply(norm_text)
                    + "||"
                    + hist_with_obs["operadora_padrao"].fillna("").astype(str).apply(norm_text)
                )
                hist_obs_map = (
                    hist_with_obs.groupby("_key")[["observacao_fiscal", "unidade_padrao", "operadora_padrao"]]
                    .agg(
                        obs=("observacao_fiscal", lambda vals: " | ".join(dict.fromkeys(
                            v.strip() for v in vals.fillna("").astype(str) if v.strip()
                        ))),
                        u_norm=("unidade_padrao", lambda x: norm_text(x.iloc[0])),
                        o_norm=("operadora_padrao", lambda x: norm_text(x.iloc[0])),
                    )
                )
                # 1) Match exato
                for key, row_h in hist_obs_map.iterrows():
                    obs_text = row_h["obs"]
                    if not obs_text:
                        continue
                    if key in fresh_lookup:
                        if not fresh_lookup[key].get("observation"):
                            fresh_lookup[key]["observation"] = obs_text
                    else:
                        fresh_lookup[key] = {"signal": "", "observation": obs_text}

                # 2) Fallback: para chaves do hist sem match exato, tenta encontrar
                #    chave em fresh_lookup que contenha a unidade+operadora do hist como prefixo/substring
                for hist_key, row_h in hist_obs_map.iterrows():
                    obs_text = row_h["obs"]
                    if not obs_text:
                        continue
                    if hist_key in fresh_lookup:
                        continue  # já foi resolvido no passo 1
                    u_h = row_h["u_norm"]  # ex: "natal home care"
                    o_h = row_h["o_norm"]  # ex: "cnu"
                    # Procura chaves do fresh_lookup que contenham u_h e o_h como substrings
                    for fl_key in list(fresh_lookup.keys()):
                        if u_h in fl_key and o_h in fl_key:
                            if not fresh_lookup[fl_key].get("observation"):
                                fresh_lookup[fl_key]["observation"] = obs_text
                            break
                    else:
                        # Ainda sem match: adiciona com a chave original do histórico
                        fresh_lookup[hist_key] = {"signal": "", "observation": obs_text}
    except Exception:
        pass  # consolidado_historico pode não existir em todos os ambientes

    work = filtered.copy()
    if "ordem_base_dinamica" not in work:
        work["ordem_base_dinamica"] = range(1, len(work) + 1)
    work["ordem_base_dinamica"] = pd.to_numeric(
        work["ordem_base_dinamica"],
        errors="coerce",
    ).fillna(999999)

    def money_or_blank(value) -> str:
        try:
            if abs(float(value or 0)) < 0.005:
                return ""
        except Exception:
            return ""
        return fmt_money(value)

    unit_order = (
        work.groupby("unidade_padrao", dropna=False)["ordem_base_dinamica"]
        .min()
        .sort_values()
        .index
        .tolist()
    )

    rows = []
    for unidade in unit_order:
        group = work[work["unidade_padrao"].astype(str) == str(unidade)].copy()
        details = group.sort_values(
            ["ordem_base_dinamica", "operadora_padrao"],
            ascending=[True, True],
        )

        detail_rows = []
        for _, detail in details.iterrows():
            unidade_value = str(detail.get("unidade_padrao", "") or "")
            operadora_value = str(detail.get("operadora_padrao", "") or "")
            row_key = norm_text(unidade_value) + "||" + norm_text(operadora_value)
            fresh = fresh_lookup.get(row_key)

            if fresh is not None:
                signal = normalize_director_signal(fresh.get("signal", ""))
                observation = str(fresh.get("observation", "") or "").strip()
                if not observation:
                    observation = str(detail.get("observacoes_consolidadas", "") or "").strip()
            else:
                signal = normalize_director_signal(detail.get("sinal_diretoria", ""))
                observation = str(detail.get("observacoes_consolidadas", "") or "").strip()

            if not signal and as_bool_flag(detail.get("alerta_diretoria", 0)):
                signal = "vermelho"

            values_dict = {col: money_or_blank(detail.get(col, 0)) for col in money_cols}
            values_dict["observacoes_consolidadas"] = str(detail.get("observacoes_consolidadas", "") or "").strip()
            detail_rows.append({
                "type": "detail",
                "unidade": unidade_value,
                "operadora": operadora_value,
                "label": operadora_value,
                "signal": signal,
                "observation": observation,
                "manualComment": str(detail.get("comentario_manual", "") or "").strip(),
                "values": values_dict,
            })

        unit_signal = aggregate_director_signal(row["signal"] for row in detail_rows)
        unit_values = {
            col: money_or_blank(pd.to_numeric(group[col], errors="coerce").fillna(0).sum())
            for col in money_cols
        }
        rows.append({
            "type": "unit",
            "label": str(unidade),
            "signal": unit_signal,
            "values": unit_values,
        })
        rows.extend(detail_rows)

    return {"columns": columns, "rows": rows}

def render_consolidado_inline_table(filtered: pd.DataFrame, fat_months: list[int], rec_months: list[int]):
    error_message = st.session_state.pop("consolidado_inline_error", "")
    if error_message:
        st.error(error_message)

    payload = build_consolidado_inline_payload(filtered, fat_months, rec_months)
    consolidado_inline_table(
        data=payload,
        key=CONSOLIDADO_INLINE_COMPONENT_KEY,
        on_action_change=persist_consolidado_inline_action,
        width="stretch",
        height="content",
        isolate_styles=True,
    )

def dashboard_bar_chart_html(rec_df: pd.DataFrame) -> str:
    if rec_df.empty:
        return '<div class="small-muted">Sem recebimentos para os meses selecionados.</div>'
    max_value = float(rec_df["Recebido Bruto"].max() or 1)
    colors = ["#C6CCD8", "#9EAABC", "#70809B", "#3F567C", "#00245D", "#52678E"]
    bars = []
    for idx, row in rec_df.iterrows():
        value = float(row["Recebido Bruto"] or 0)
        month_label = html_text(row["Mês"])
        height = max(3, int((value / max_value) * 92))
        bars.append(
            f"""
            <div class="dashboard-bar-group" title="{fmt_money_html(value)}">
                <div class="dashboard-bar" style="height:{height}%; background:{colors[idx % len(colors)]};"></div>
                <div class="dashboard-bar-label">{month_label}</div>
            </div>
            """
        )
    return f'<div class="dashboard-chart">{"".join(bars)}</div>'

import pandas as pd
import io

def generate_consolidado_inline_excel(payload: dict) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        pd.DataFrame().to_excel(writer, index=False, sheet_name="Consolidado")
        wb = writer.book
        ws = writer.sheets["Consolidado"]
        ws.freeze_panes(1, 0)
        
        # Formats
        header_fmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "border": 1, "align": "center", "valign": "vcenter"})
        header_fat_fmt = wb.add_format({"bold": True, "font_color": "#000000", "bg_color": "#FFD966", "border": 1, "align": "center", "valign": "vcenter"})
        
        unit_fmt = wb.add_format({"bold": True, "bg_color": "#002E7A", "font_color": "white", "border": 1})
        unit_money_fmt = wb.add_format({"bold": True, "bg_color": "#002E7A", "font_color": "white", "border": 1, "align": "right", "num_format": 'R$ #,##0.00'})
        
        detail_fmt = wb.add_format({"border": 1})
        detail_money_fmt = wb.add_format({"border": 1, "align": "right", "num_format": 'R$ #,##0.00'})
        detail_fat_money_fmt = wb.add_format({"border": 1, "align": "right", "bg_color": "#F2F2F2", "num_format": 'R$ #,##0.00'})
        obs_fmt = wb.add_format({"border": 1, "bg_color": "#FFF2CC"})
        
        # Write headers
        columns = payload["columns"]
        for col_idx, col in enumerate(columns):
            label = str(col["label"]).upper()
            fmt = header_fat_fmt if col["kind"] == "fat" else header_fmt
            ws.write(0, col_idx, label, fmt)
            
            # Set column widths
            if col["key"] == "linha_label":
                ws.set_column(col_idx, col_idx, 38)
            elif col["kind"] == "observation":
                ws.set_column(col_idx, col_idx, 55)
            else:
                ws.set_column(col_idx, col_idx, 18)
        
        # Write rows
        current_row = 1
        for row in payload["rows"]:
            if row["type"] == "unit":
                ws.write(current_row, 0, str(row["label"]).upper(), unit_fmt)
                for col_idx, col in enumerate(columns[1:], 1):
                    if col["kind"] in ("money", "fat"):
                        val = row["values"].get(col["key"], "")
                        try:
                            if val: val = float(val)
                        except: pass
                        ws.write(current_row, col_idx, val if val != "" else 0, unit_money_fmt)
                    elif col["kind"] == "observation":
                        ws.write(current_row, col_idx, "", unit_fmt)
            else:
                operadora = row["label"]
                if row.get("signal"):
                    operadora = f"[{row['signal'].upper()}] {operadora}"
                ws.write(current_row, 0, operadora, detail_fmt)
                
                for col_idx, col in enumerate(columns[1:], 1):
                    if col["kind"] in ("money", "fat"):
                        val = row["values"].get(col["key"], "")
                        try:
                            if val: val = float(val)
                        except: pass
                        fmt = detail_fat_money_fmt if col["kind"] == "fat" else detail_money_fmt
                        ws.write(current_row, col_idx, val if val != "" else 0, fmt)
                    elif col["kind"] == "observation":
                        # Pega observacao do fresh_lookup (row.observation) ou do consolidado (values dict)
                        obs = str(row.get("observation", "") or "").strip()
                        if not obs:
                            obs = str(row.get("values", {}).get("observacoes_consolidadas", "") or "").strip()
                        if row.get("manualComment"):
                            manual = str(row["manualComment"]).strip()
                            obs = f"{obs} | Manual: {manual}" if obs else f"Manual: {manual}"
                        ws.write(current_row, col_idx, obs, obs_fmt)
            current_row += 1
            
    return output.getvalue()

@st.cache_data(show_spinner=False)
def df_to_excel_bytes(consolidado: pd.DataFrame, fat: pd.DataFrame, cont: pd.DataFrame, inconsistencias: pd.DataFrame) -> bytes:
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        dashboard = pd.DataFrame({
            "Métrica": [
                "Total Faturado",
                "Total Recebido Bruto",
                "Total Recebido Líquido",
                "Diferença Pendente",
                "% Recebido Total",
            ],
            "Valor": [
                consolidado["faturado"].sum() if "faturado" in consolidado else 0,
                consolidado["total_recebido_bruto"].sum() if "total_recebido_bruto" in consolidado else 0,
                consolidado["total_recebido_liquido"].sum() if "total_recebido_liquido" in consolidado else 0,
                consolidado["diferenca_pendente"].sum() if "diferenca_pendente" in consolidado else 0,
                (consolidado["total_recebido_bruto"].sum() / consolidado["faturado"].sum()) if ("faturado" in consolidado and consolidado["faturado"].sum() > 0) else 0,
            ]
        })
        dashboard.to_excel(writer, sheet_name="Dashboard", index=False, startrow=2)
        
        # --- Build formatted Consolidado for Excel ---
        # Get money columns
        money_cols = [c for c in consolidado.columns if c.startswith("fat_") or c.startswith("rec_")]
        
        # Create a visually grouped dataframe
        vis_rows = []
        if "ordem_base_dinamica" not in consolidado:
            consolidado["ordem_base_dinamica"] = range(1, len(consolidado) + 1)
        
        work = consolidado.copy()
        work["ordem_base_dinamica"] = pd.to_numeric(work["ordem_base_dinamica"], errors="coerce").fillna(999999)
        unit_order = work.groupby("unidade_padrao", dropna=False)["ordem_base_dinamica"].min().sort_values().index.tolist()
        
        total_row_indices = []
        current_idx = 1 # Header is 0
        
        for unidade in unit_order:
            group = work[work["unidade_padrao"].astype(str) == str(unidade)]
            
            # Unit total row
            row = {"UNIDADE / OPERADORA": str(unidade)}
            for c in consolidado.columns:
                if c not in ["UNIDADE / OPERADORA", "unidade_padrao", "operadora_padrao", "ordem_base_dinamica"]:
                    if c in money_cols:
                        row[c] = pd.to_numeric(group[c], errors="coerce").fillna(0).sum()
                    else:
                        row[c] = ""
            vis_rows.append(row)
            total_row_indices.append(current_idx)
            current_idx += 1
            
            # Detail rows
            details = group.sort_values(["ordem_base_dinamica", "operadora_padrao"])
            for _, detail in details.iterrows():
                d_row = {"UNIDADE / OPERADORA": str(detail.get("operadora_padrao", ""))}
                for c in consolidado.columns:
                    if c not in ["UNIDADE / OPERADORA", "unidade_padrao", "operadora_padrao", "ordem_base_dinamica"]:
                        d_row[c] = detail.get(c, "")
                vis_rows.append(d_row)
                current_idx += 1
                
        consolidado_vis = pd.DataFrame(vis_rows)
        # Drop columns that shouldn't be displayed if they exist and aren't needed
        cols_to_drop = ["unidade_padrao", "operadora_padrao", "ordem_base_dinamica", "sinal_diretoria", "alerta_diretoria"]
        consolidado_vis = consolidado_vis.drop(columns=[c for c in cols_to_drop if c in consolidado_vis], errors="ignore")
        
        # Capitalize headers for display
        rename_dict = {}
        for c in consolidado_vis.columns:
            if c.startswith("fat_"):
                month = c.split("_")[1]
                rename_dict[c] = f"FATURADO {month.upper()}"
            elif c.startswith("rec_bruto_"):
                month = c.split("_")[2]
                rename_dict[c] = f"REC. BRUTO {month.upper()}"
            elif c.startswith("rec_liquido_"):
                month = c.split("_")[2]
                rename_dict[c] = f"REC. LÍQUIDO {month.upper()}"
            elif c == "observacoes_consolidadas":
                rename_dict[c] = "OBSERVAÇÃO"
        consolidado_vis = consolidado_vis.rename(columns=rename_dict)
        
        consolidado_vis.to_excel(writer, sheet_name="Consolidado", index=False)
        fat.to_excel(writer, sheet_name="Faturamento Base", index=False)
        cont.to_excel(writer, sheet_name="Contabilidade Base", index=False)
        inconsistencias.to_excel(writer, sheet_name="Inconsistencias", index=False)
        
        wb = writer.book
        money_fmt = wb.add_format({"num_format": 'R$ #,##0.00', "border": 1})
        faturamento_money_fmt = wb.add_format({"num_format": 'R$ #,##0.00', "border": 1, "bg_color": "#FFF2CC", "font_color": "#000000"})
        pct_fmt = wb.add_format({"num_format": '0.00%', "border": 1})
        header_fmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "border": 1})
        faturamento_header_fmt = wb.add_format({"bold": True, "font_color": "#000000", "bg_color": "#FFC000", "border": 1})
        title_fmt = wb.add_format({"bold": True, "font_size": 16, "font_color": "#17365D"})
        
        # Formats for unit total row
        unit_total_fmt = wb.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1, "top": 2, "bottom": 2})
        unit_total_money_fmt = wb.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1, "top": 2, "bottom": 2, "num_format": 'R$ #,##0.00'})
        
        for sheet_name, df in [
            ("Dashboard", dashboard),
            ("Consolidado", consolidado_vis),
            ("Faturamento Base", fat),
            ("Contabilidade Base", cont),
            ("Inconsistencias", inconsistencias),
        ]:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            if sheet_name == "Dashboard":
                ws.write(0, 0, "CONTROLE EXECUTIVO DE FATURAMENTO VS RECEBIMENTOS", title_fmt)
                ws.set_column(0, 0, 28)
                ws.set_column(1, 1, 20)
            else:
                for col_num, col_name in enumerate(df.columns):
                    col_key = str(col_name).lower()
                    is_faturamento = "faturado" in col_key or "faturamento" in col_key or "fat_" in col_key
                    ws.write(0, col_num, col_name, faturamento_header_fmt if is_faturamento else header_fmt)
                    width = min(max(len(str(col_name)) + 2, 12), 48)
                    if col_name == "UNIDADE / OPERADORA": width = 35
                    if col_name == "OBSERVAÇÃO" or "obs" in col_key: width = 50
                    ws.set_column(col_num, col_num, width)
                    
                if not df.empty:
                    for idx, col in enumerate(df.columns):
                        c = str(col).lower()
                        is_faturamento = "faturado" in c or "faturamento" in c or "fat_" in c
                        is_money = any(k in c for k in ["valor", "faturado", "recebido", "diferenca", "rec_bruto", "rec_liquido", "bruto", "liquido", "fat_"])
                        
                        if is_money:
                            ws.set_column(idx, idx, 18, faturamento_money_fmt if is_faturamento else money_fmt)
                        elif "perc" in c or "%" in c:
                            ws.set_column(idx, idx, 14, pct_fmt)
                            
                # Apply row formatting for Consolidado
                if sheet_name == "Consolidado":
                    for row_idx in total_row_indices:
                        for col_num, col_name in enumerate(df.columns):
                            c = str(col_name).lower()
                            is_money = any(k in c for k in ["valor", "faturado", "recebido", "diferenca", "rec_bruto", "rec_liquido", "bruto", "liquido", "fat_"])
                            val = df.iloc[row_idx - 1, col_num]
                            if pd.isna(val): val = ""
                            ws.write(row_idx, col_num, val, unit_total_money_fmt if is_money else unit_total_fmt)
                            
        output.seek(0)
        return output.read()
def months_to_label(months: list[int], year: int) -> str:
    if not months:
        return "-"
    labels = []
    for month in months:
        try:
            labels.append(f"{MONTHS.get(int(month), month)}/{int(year)}")
        except Exception:
            labels.append(str(month))
    return ", ".join(labels)

def report_period_label(fat_months: list[int], rec_months: list[int], year: int) -> str:
    return f"Fat: {months_to_label(fat_months, year)} | Rec: {months_to_label(rec_months, year)}"

def sanitize_file_stem(value: str) -> str:
    cleaned = norm_text(value).lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in cleaned)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "relatorio"

def default_export_filename(report_type: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{sanitize_file_stem(report_type)}_{stamp}"

def clean_sheet_name(name: str) -> str:
    cleaned = str(name)
    for char in "[]:*?/\\":
        cleaned = cleaned.replace(char, " ")
    cleaned = " ".join(cleaned.split())
    return (cleaned[:31].strip() or "Relatorio")

def ensure_export_dataframe(df: pd.DataFrame, message: str) -> pd.DataFrame:
    if df is None or (df.empty and len(df.columns) == 0):
        return pd.DataFrame({"Mensagem": [message]})
    return df.copy()

def build_dashboard_summary(consolidado: pd.DataFrame, fat_months: list[int], rec_months: list[int], year: int) -> pd.DataFrame:
    dash = prepare_dashboard_consolidado(consolidado)
    rows = [
        {"Categoria": "Parâmetro", "Indicador": "Competência faturamento", "Valor": months_to_label(fat_months, year), "Detalhe": ""},
        {"Categoria": "Parâmetro", "Indicador": "Mês recebimento", "Valor": months_to_label(rec_months, year), "Detalhe": ""},
        {"Categoria": "Parâmetro", "Indicador": "Gerado em", "Valor": datetime.now().strftime("%d/%m/%Y %H:%M"), "Detalhe": ""},
    ]
    if dash.empty:
        rows.append({"Categoria": "Resumo", "Indicador": "Status", "Valor": "Sem dados", "Detalhe": "Não há consolidado para os parâmetros atuais."})
        return pd.DataFrame(rows)

    total_fat = dash["faturado"].sum() if "faturado" in dash else 0
    total_bruto = dash["total_recebido_bruto"].sum() if "total_recebido_bruto" in dash else 0
    total_liq = dash["total_recebido_liquido"].sum() if "total_recebido_liquido" in dash else 0
    pendente = dash["diferenca_pendente"].sum() if "diferenca_pendente" in dash else 0
    perc = total_bruto / total_fat if total_fat else 0
    rows.extend([
        {"Categoria": "KPI", "Indicador": "Total faturado", "Valor": fmt_money(total_fat), "Detalhe": "Competência selecionada"},
        {"Categoria": "KPI", "Indicador": "Recebido bruto", "Valor": fmt_money(total_bruto), "Detalhe": "Recebimentos selecionados"},
        {"Categoria": "KPI", "Indicador": "Recebido líquido", "Valor": fmt_money(total_liq), "Detalhe": "Após retenções"},
        {"Categoria": "KPI", "Indicador": "Diferença pendente", "Valor": fmt_money(pendente), "Detalhe": "Faturado - recebido bruto"},
        {"Categoria": "KPI", "Indicador": "% recebido", "Valor": fmt_pct(perc), "Detalhe": "Bruto sobre faturado"},
        {"Categoria": "KPI", "Indicador": "Unidades", "Valor": dash["unidade_padrao"].nunique() if "unidade_padrao" in dash else 0, "Detalhe": "Com movimento"},
        {"Categoria": "KPI", "Indicador": "Operadoras", "Valor": dash["operadora_padrao"].nunique() if "operadora_padrao" in dash else 0, "Detalhe": "Com movimento"},
    ])
    if "status" in dash:
        for status, qtd in dash["status"].value_counts().sort_index().items():
            rows.append({"Categoria": "Status", "Indicador": status, "Valor": int(qtd), "Detalhe": "Quantidade de combinações unidade/operadora"})
    return pd.DataFrame(rows)

def build_comentarios_export(fat: pd.DataFrame, cont: pd.DataFrame, fat_months: list[int], rec_months: list[int], year: int) -> pd.DataFrame:
    ensure_comentarios_table()
    comentarios = read_table("comentarios_manuais")
    frames = []
    for month in fat_months:
        consolidado_mes = build_consolidado(fat, cont, [int(month)], rec_months, year=int(year)) if not fat.empty or not cont.empty else pd.DataFrame()
        grid = build_comentarios_grid(consolidado_mes, comentarios, int(month), int(year))
        if not grid.empty:
            grid = grid.copy()
            grid.insert(0, "competencia_faturamento", f"{MONTHS.get(int(month), month)}/{int(year)}")
            frames.append(grid)
    if not frames:
        return pd.DataFrame(columns=[
            "competencia_faturamento", "unidade_padrao", "operadora_padrao", "mes_ano",
            "observacao_fiscal", "comentario_manual", "status_comentario",
            "diferenca_pendente", "perc_recebido_total", "atualizado_por", "atualizado_em",
        ])
    return pd.concat(frames, ignore_index=True)

def build_report_sheets(
    report_type: str,
    consolidado: pd.DataFrame,
    fat: pd.DataFrame,
    cont: pd.DataFrame,
    inconsistencias: pd.DataFrame,
    comentarios: pd.DataFrame,
    fat_months: list[int],
    rec_months: list[int],
    year: int,
    include_dashboard: bool,
    include_bases: bool,
    include_comments: bool,
    include_inconsistencies: bool,
) -> dict[str, pd.DataFrame]:
    dash_consolidado = prepare_dashboard_consolidado(consolidado)
    sheets: dict[str, pd.DataFrame] = {}

    if report_type == "Relatório Executivo Excel":
        if include_dashboard:
            sheets["Dashboard"] = build_dashboard_summary(consolidado, fat_months, rec_months, year)
        sheets["Consolidado"] = ensure_export_dataframe(dash_consolidado, "Sem consolidado para os parâmetros selecionados.")
        if include_bases:
            sheets["Faturamento Base"] = ensure_export_dataframe(fat, "Sem base de faturamento carregada.")
            sheets["Contabilidade Base"] = ensure_export_dataframe(cont, "Sem base de contabilidade carregada.")
        if include_comments:
            sheets["Comentarios"] = ensure_export_dataframe(comentarios, "Sem comentários cadastrados para os parâmetros selecionados.")
        if include_inconsistencies:
            sheets["Inconsistencias"] = ensure_export_dataframe(inconsistencias, "Sem inconsistências identificadas.")
        return sheets

    if report_type == "Consolidado Analítico":
        sheets["Consolidado"] = ensure_export_dataframe(dash_consolidado, "Sem consolidado para os parâmetros selecionados.")
        if include_dashboard:
            sheets["Dashboard"] = build_dashboard_summary(consolidado, fat_months, rec_months, year)
        if include_bases:
            sheets["Faturamento Base"] = ensure_export_dataframe(fat, "Sem base de faturamento carregada.")
            sheets["Contabilidade Base"] = ensure_export_dataframe(cont, "Sem base de contabilidade carregada.")
        if include_comments:
            sheets["Comentarios"] = ensure_export_dataframe(comentarios, "Sem comentários cadastrados para os parâmetros selecionados.")
        if include_inconsistencies:
            sheets["Inconsistencias"] = ensure_export_dataframe(inconsistencias, "Sem inconsistências identificadas.")
        return sheets

    if report_type == "Relatório de Inconsistências":
        sheets["Inconsistencias"] = ensure_export_dataframe(inconsistencias, "Sem inconsistências identificadas.")
        if include_dashboard:
            sheets["Dashboard"] = build_dashboard_summary(consolidado, fat_months, rec_months, year)
        if include_comments:
            sheets["Comentarios"] = ensure_export_dataframe(comentarios, "Sem comentários cadastrados para os parâmetros selecionados.")
        return sheets

    if report_type == "Base de Faturamento Original":
        return {"Faturamento Base": ensure_export_dataframe(fat, "Sem base de faturamento carregada.")}

    if report_type == "Base de Contabilidade Original":
        return {"Contabilidade Base": ensure_export_dataframe(cont, "Sem base de contabilidade carregada.")}

    return {"Relatorio": pd.DataFrame({"Mensagem": ["Tipo de relatório não reconhecido."]})}

def build_export_excel_bytes(sheets: dict[str, pd.DataFrame], title: str) -> bytes:
    output = io.BytesIO()
    if not sheets:
        sheets = {"Relatorio": pd.DataFrame({"Mensagem": ["Nenhum conteúdo selecionado para exportação."]})}

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        used_names: set[str] = set()
        written = []
        for raw_name, df in sheets.items():
            base_name = clean_sheet_name(raw_name)
            sheet_name = base_name
            suffix = 2
            while sheet_name in used_names:
                sheet_name = clean_sheet_name(f"{base_name[:27]} {suffix}")
                suffix += 1
            used_names.add(sheet_name)

            frame = ensure_export_dataframe(df, "Sem dados para esta aba.")
            startrow = 2 if sheet_name == "Dashboard" else 0
            frame.to_excel(writer, sheet_name=sheet_name, index=False, startrow=startrow)
            written.append((sheet_name, frame, startrow))

        wb = writer.book
        money_fmt = wb.add_format({"num_format": 'R$ #,##0.00', "border": 1})
        pct_fmt = wb.add_format({"num_format": '0.00%', "border": 1})
        number_fmt = wb.add_format({"num_format": '#,##0', "border": 1})
        header_fmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "border": 1})
        title_fmt = wb.add_format({"bold": True, "font_size": 16, "font_color": "#17365D"})
        subtitle_fmt = wb.add_format({"font_color": "#667085", "italic": True})

        for sheet_name, df, startrow in written:
            ws = writer.sheets[sheet_name]
            header_row = startrow
            ws.freeze_panes(header_row + 1, 0)
            if sheet_name == "Dashboard":
                ws.write(0, 0, title.upper(), title_fmt)
                ws.write(1, 0, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", subtitle_fmt)

            for col_num, col_name in enumerate(df.columns):
                ws.write(header_row, col_num, col_name, header_fmt)
                sample_width = 0
                if not df.empty and col_name in df:
                    sample_width = int(df[col_name].fillna("").astype(str).str.len().head(80).max() or 0)
                width = min(max(len(str(col_name)) + 2, sample_width + 2, 12), 44)
                c = str(col_name).lower()
                if any(k in c for k in ["faturado", "recebido", "diferenca", "bruto", "liquido", "pendente"]) or c.startswith("valor_"):
                    ws.set_column(col_num, col_num, max(width, 16), money_fmt)
                elif "perc" in c or "%" in c:
                    ws.set_column(col_num, col_num, max(width, 12), pct_fmt)
                elif "qtd" in c or "quantidade" in c:
                    ws.set_column(col_num, col_num, max(width, 10), number_fmt)
                else:
                    ws.set_column(col_num, col_num, width)

    output.seek(0)
    return output.read()

def select_csv_export_frame(
    report_type: str,
    consolidado: pd.DataFrame,
    fat: pd.DataFrame,
    cont: pd.DataFrame,
    inconsistencias: pd.DataFrame,
    comentarios: pd.DataFrame,
    fat_months: list[int],
    rec_months: list[int],
    year: int,
) -> pd.DataFrame:
    if report_type == "Relatório Executivo Excel":
        return build_dashboard_summary(consolidado, fat_months, rec_months, year)
    if report_type == "Consolidado Analítico":
        return prepare_dashboard_consolidado(consolidado)
    if report_type == "Relatório de Inconsistências":
        return inconsistencias
    if report_type == "Base de Faturamento Original":
        return fat
    if report_type == "Base de Contabilidade Original":
        return cont
    if report_type == "Comentários Financeiros":
        return comentarios
    return pd.DataFrame()

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    frame = ensure_export_dataframe(df, "Sem dados para os parâmetros selecionados.")
    return frame.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")

def export_rows_count(sheets: dict[str, pd.DataFrame]) -> int:
    return int(sum(len(df) for df in sheets.values() if isinstance(df, pd.DataFrame)))

def add_inconsistencia(
    rows: list[dict],
    severidade: str,
    tipo: str,
    origem: str,
    descricao: str,
    valor_encontrado: str,
    acao_recomendada: str,
    status: str = "Pendente",
    qtd: int = 1,
):
    rows.append({
        "severidade": severidade,
        "tipo": tipo,
        "origem": origem,
        "descricao": descricao,
        "valor_encontrado": valor_encontrado,
        "acao_recomendada": acao_recomendada,
        "status": status,
        "qtd": int(qtd),
    })

def inconsistencia_id(row: pd.Series | dict) -> str:
    parts = [
        str(row.get("tipo", "")),
        str(row.get("origem", "")),
        str(row.get("descricao", "")),
        str(row.get("valor_encontrado", "")),
    ]
    return hashlib.sha1("|".join(map(norm_text, parts)).encode("utf-8")).hexdigest()[:16]

def build_inconsistencias(
    fat: pd.DataFrame,
    cont: pd.DataFrame,
    depara: pd.DataFrame,
    depara_operadoras: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows = []
    known = set(depara["nome_padrao"].apply(norm_text)) | set(depara["sigla_origem"].apply(norm_text))
    unit_sources: dict[str, dict] = {}
    for table_name, df, col in [("Faturamento", fat, "unidade_original"), ("Contabilidade", cont, "unidade_original")]:
        if not df.empty and col in df:
            for unidade in {v for v in df[col].dropna().astype(str) if v.strip()}:
                key = norm_text(unidade)
                unit_sources.setdefault(key, {"valor": unidade, "origens": set()})
                unit_sources[key]["origens"].add(table_name)
    for key, item in sorted(unit_sources.items(), key=lambda kv: norm_text(kv[1]["valor"])):
        if key not in known:
            origem = "/".join(sorted(item["origens"]))
            add_inconsistencia(
                rows,
                "Crítica",
                "DE/PARA Unidade",
                origem,
                f"Unidade ainda não mapeada no DE/PARA: {item['valor']}",
                item["valor"],
                "Cadastrar a unidade na aba DE/PARA de Unidades.",
            )

    if depara_operadoras is not None and not depara_operadoras.empty:
        known_ops = set(depara_operadoras["nome_padrao"].apply(norm_text)) | set(depara_operadoras["sigla_origem"].apply(norm_text))
        operator_sources: dict[str, dict] = {}
        for table_name, df, col in [("Faturamento", fat, "operadora_original"), ("Contabilidade", cont, "operadora_original")]:
            if not df.empty and col in df:
                for operadora in {v for v in df[col].dropna().astype(str) if v.strip()}:
                    key = norm_text(operadora)
                    operator_sources.setdefault(key, {"valor": operadora, "origens": set()})
                    operator_sources[key]["origens"].add(table_name)
        for key, item in sorted(operator_sources.items(), key=lambda kv: norm_text(kv[1]["valor"])):
            if key not in known_ops:
                origem = "/".join(sorted(item["origens"]))
                add_inconsistencia(
                    rows,
                    "Crítica",
                    "DE/PARA Operadora",
                    origem,
                    f"Operadora ainda não mapeada no DE/PARA: {item['valor']}",
                    item["valor"],
                    "Cadastrar a operadora na aba DE/PARA de Operadoras.",
                )

    for table_name, df, value_col, file_col in [
        ("Faturamento", fat, "valor_faturado", "origem_arquivo"),
        ("Contabilidade", cont, "valor_bruto", "origem_arquivo"),
    ]:
        if not df.empty and value_col in df:
            values = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
            zero_rows = df[values == 0]
            if not zero_rows.empty:
                for arquivo, group in zero_rows.groupby(file_col, dropna=False) if file_col in zero_rows else [("Base carregada", zero_rows)]:
                    add_inconsistencia(
                        rows,
                        "Média",
                        "Linha Zerada",
                        str(arquivo),
                        f"{len(group)} linha(s) com {value_col} zerado.",
                        "R$ 0,00",
                        "Revisar se a linha deve ser mantida, corrigida ou ignorada no consolidado.",
                        status="A revisar",
                        qtd=len(group),
                    )

    for table_name, df, month_col, file_col in [
        ("Faturamento", fat, "mes_faturamento", "origem_arquivo"),
        ("Contabilidade", cont, "mes_recebimento", "origem_arquivo"),
    ]:
        if not df.empty and month_col in df:
            months = pd.to_numeric(df[month_col], errors="coerce")
            invalid_rows = df[months.isna() | ~months.between(1, 12)]
            if not invalid_rows.empty:
                for arquivo, group in invalid_rows.groupby(file_col, dropna=False) if file_col in invalid_rows else [("Base carregada", invalid_rows)]:
                    add_inconsistencia(
                        rows,
                        "Alta",
                        "Mês Inválido",
                        str(arquivo),
                        f"{len(group)} linha(s) com mês inválido em {month_col}.",
                        "Mês vazio ou fora de 1-12",
                        "Corrigir a competência/mês no arquivo de origem e reprocessar.",
                        qtd=len(group),
                    )

    if not fat.empty and not cont.empty and "nf" in fat and "nf" in cont:
        fat_nfs = {str(v).strip().removesuffix(".0") for v in fat["nf"].dropna() if str(v).strip()}
        cont_nfs = {str(v).strip().removesuffix(".0") for v in cont["nf"].dropna() if str(v).strip()}
        if fat_nfs and cont_nfs and not (fat_nfs & cont_nfs):
            add_inconsistencia(
                rows,
                "Baixa",
                "Chave Incompatível",
                "Faturamento/Contabilidade",
                "ID Doc do faturamento e Nº NF da contabilidade não possuem interseção; validação por NF foi ignorada.",
                f"{len(fat_nfs)} IDs faturamento x {len(cont_nfs)} NFs contabilidade",
                "Confirmar a chave correta de vínculo ou criar tabela de relacionamento entre ID Doc e NF.",
                status="Informativo",
            )
        else:
            for nf in sorted(list(cont_nfs - fat_nfs))[:500]:
                add_inconsistencia(rows, "Alta", "NF sem Faturamento", "Contabilidade", "NF recebida não localizada no faturamento bruto carregado.", nf, "Verificar se o faturamento bruto correspondente foi importado.")
            for nf in sorted(list(fat_nfs - cont_nfs))[:500]:
                add_inconsistencia(rows, "Média", "NF sem Recebimento", "Faturamento", "NF faturada ainda não localizada nos recebimentos carregados.", nf, "Acompanhar recebimento ou validar se a contabilidade do período foi importada.")

    columns = ["severidade", "tipo", "origem", "descricao", "valor_encontrado", "acao_recomendada", "status", "qtd"]
    return pd.DataFrame(rows, columns=columns)

def merge_inconsistencias_manuais(inc: pd.DataFrame, manual: pd.DataFrame | None = None) -> pd.DataFrame:
    ensure_inconsistencias_table()
    if inc.empty:
        cols = [
            "inconsistencia_id", "severidade", "tipo", "origem", "descricao",
            "valor_encontrado", "acao_recomendada", "status", "observacao_manual",
            "atualizado_por", "atualizado_em", "qtd",
        ]
        return pd.DataFrame(columns=cols)

    out = inc.copy()
    out["inconsistencia_id"] = out.apply(inconsistencia_id, axis=1)
    if manual is None:
        manual = read_table("inconsistencias_manuais")

    for col in ["observacao_manual", "atualizado_por", "atualizado_em"]:
        out[col] = ""

    if manual is None or manual.empty or "inconsistencia_id" not in manual:
        return out

    manual_cols = [
        "inconsistencia_id", "status", "acao_recomendada",
        "observacao_manual", "atualizado_por", "atualizado_em",
    ]
    manual_ref = manual[[col for col in manual_cols if col in manual]].copy()
    merged = out.merge(manual_ref, on="inconsistencia_id", how="left", suffixes=("", "_manual"))

    for col in ["status", "acao_recomendada", "observacao_manual", "atualizado_por", "atualizado_em"]:
        manual_col = f"{col}_manual"
        if manual_col in merged:
            mask = merged[manual_col].fillna("").astype(str).str.strip() != ""
            merged.loc[mask, col] = merged.loc[mask, manual_col]
            merged = merged.drop(columns=manual_col)
    return merged

def save_inconsistencias_grid(edited: pd.DataFrame, manual: pd.DataFrame, usuario: str):
    ensure_inconsistencias_table()
    required = [
        "inconsistencia_id", "tipo", "origem", "valor_encontrado",
        "status", "acao_recomendada", "observacao_manual",
    ]
    for col in required:
        if col not in edited:
            edited[col] = ""

    save = edited[required].copy().fillna("").astype(str)
    save["observacao_manual"] = save["observacao_manual"].str.strip()
    save["atualizado_por"] = usuario.strip() or "sistema"
    save["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    save = save[
        (save["inconsistencia_id"].str.strip() != "")
        & (
            (save["status"].str.strip() != "")
            | (save["acao_recomendada"].str.strip() != "")
            | (save["observacao_manual"].str.strip() != "")
        )
    ]

    if manual is None or manual.empty:
        manual = pd.DataFrame(columns=[
            "inconsistencia_id", "tipo", "origem", "valor_encontrado",
            "status", "acao_recomendada", "observacao_manual",
            "atualizado_por", "atualizado_em",
        ])

    edited_ids = set(save["inconsistencia_id"].tolist())
    keep = manual[~manual["inconsistencia_id"].isin(edited_ids)].copy() if "inconsistencia_id" in manual else manual.iloc[0:0].copy()
    final = pd.concat([keep, save], ignore_index=True)
    write_table("inconsistencias_manuais", final)

def source_values_for_depara(df: pd.DataFrame, column: str) -> pd.Series:
    if not df.empty and column in df:
        return df[column].dropna().astype(str).map(str.strip).replace("", pd.NA).dropna()
    return pd.Series(dtype=str)

def build_depara_grid(mapping: pd.DataFrame, source_values: pd.Series) -> pd.DataFrame:
    base = mapping.copy()
    for col in ["sigla_origem", "nome_padrao"]:
        if col not in base:
            base[col] = ""
    base = base[["sigla_origem", "nome_padrao"]].fillna("").astype(str)

    mapped_keys = set(base["sigla_origem"].apply(norm_text))
    used_values = sorted({v for v in source_values.dropna().astype(str) if v.strip()}, key=norm_text)
    used_keys = {norm_text(v) for v in used_values}

    pending_rows = [
        {"sigla_origem": value, "nome_padrao": ""}
        for value in used_values
        if norm_text(value) not in mapped_keys
    ]
    if pending_rows:
        base = pd.concat([pd.DataFrame(pending_rows), base], ignore_index=True)

    grid = base.drop_duplicates(subset=["sigla_origem"], keep="last").copy()
    grid["status"] = grid.apply(
        lambda row: "Pendente" if not norm_text(row["nome_padrao"]) else "Mapeado",
        axis=1,
    )
    grid["em_uso"] = grid["sigla_origem"].apply(lambda value: "Sim" if norm_text(value) in used_keys else "Não")
    grid["ultima_atualizacao"] = "-"
    grid["_ordem"] = grid["status"].map({"Pendente": 0, "Mapeado": 1}).fillna(2)
    return (
        grid.sort_values(["_ordem", "sigla_origem"], key=lambda col: col.map(norm_text) if col.name == "sigla_origem" else col)
        .drop(columns="_ordem")
        .reset_index(drop=True)
    )

def filter_depara_grid(grid: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query:
        return grid
    needle = norm_text(query)
    mask = (
        grid["sigla_origem"].apply(norm_text).str.contains(needle, regex=False)
        | grid["nome_padrao"].apply(norm_text).str.contains(needle, regex=False)
        | grid["status"].apply(norm_text).str.contains(needle, regex=False)
    )
    return grid[mask].reset_index(drop=True)

def depara_to_save(edited: pd.DataFrame) -> pd.DataFrame:
    out = edited[["sigla_origem", "nome_padrao"]].copy()
    out = out.fillna("").astype(str)
    out["sigla_origem"] = out["sigla_origem"].str.strip()
    out["nome_padrao"] = out["nome_padrao"].str.strip()
    out = out[out["sigla_origem"] != ""]
    out["_key"] = out["sigla_origem"].apply(norm_text)
    out = out.drop_duplicates(subset="_key", keep="last").drop(columns="_key")
    return out.reset_index(drop=True)


def source_values_for_depara_operadoras(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty and "unidade_padrao" in df and "operadora_original" in df:
        return df[["unidade_padrao", "operadora_original"]].dropna().drop_duplicates()
    return pd.DataFrame(columns=["unidade_padrao", "operadora_original"])

def build_depara_operadoras_grid(mapping: pd.DataFrame, source_values: pd.DataFrame) -> pd.DataFrame:
    base = mapping.copy()
    for col in ["unidade_origem", "sigla_origem", "nome_padrao"]:
        if col not in base:
            base[col] = ""
    base = base[["unidade_origem", "sigla_origem", "nome_padrao"]].fillna("").astype(str)

    # Cria chaves combinadas para rastrear o que ta mapeado
    def make_key(u, o):
        return f"{norm_text(u)}|{norm_text(o)}"

    mapped_keys = set(base.apply(lambda r: make_key(r["unidade_origem"], r["sigla_origem"]), axis=1))
    
    used_pairs = []
    if not source_values.empty:
        for _, row in source_values.iterrows():
            u, o = str(row["unidade_padrao"]).strip(), str(row["operadora_original"]).strip()
            if o:
                used_pairs.append((u, o))
                
    used_keys = {make_key(u, o) for u, o in used_pairs}

    pending_rows = []
    for u, o in used_pairs:
        if make_key(u, o) not in mapped_keys:
            pending_rows.append({"unidade_origem": u, "sigla_origem": o, "nome_padrao": ""})

    if pending_rows:
        base = pd.concat([pd.DataFrame(pending_rows), base], ignore_index=True)

    grid = base.drop_duplicates(subset=["unidade_origem", "sigla_origem"], keep="last").copy()
    grid["status"] = grid.apply(
        lambda row: "Pendente" if not norm_text(row["nome_padrao"]) else "Mapeado",
        axis=1,
    )
    grid["em_uso"] = grid.apply(lambda row: "Sim" if make_key(row["unidade_origem"], row["sigla_origem"]) in used_keys else "Não", axis=1)
    grid["ultima_atualizacao"] = "-"
    grid["_ordem"] = grid["status"].map({"Pendente": 0, "Mapeado": 1}).fillna(2)
    return (
        grid.sort_values(["_ordem", "unidade_origem", "sigla_origem"], key=lambda col: col.map(norm_text) if col.name in ("unidade_origem", "sigla_origem") else col)
        .drop(columns="_ordem")
        .reset_index(drop=True)
    )


def find_mapping_gaps(fat_df, cont_df):
    if fat_df.empty or cont_df.empty:
        import pandas as pd
        return pd.DataFrame()
        
    ops_cont = set(cont_df['operadora_padrao'].dropna().apply(norm_text))
    mask = ~fat_df['operadora_padrao'].apply(norm_text).isin(ops_cont) & fat_df['operadora_padrao'].notna() & (fat_df['operadora_padrao'] != "")
    
    gaps = fat_df[mask][['unidade_original', 'operadora_original', 'operadora_padrao']].drop_duplicates()
    return gaps.reset_index(drop=True)

def apply_gap_fixes_and_reprocess(fixes):
    import pandas as pd
    if fixes.empty:
        return
        
    current_depara = read_table("de_para_operadoras_fat")
    new_rules = fixes.rename(columns={
        "unidade_original": "unidade_origem",
        "operadora_original": "sigla_origem",
        "operadora_correta": "nome_padrao"
    })
    
    final_depara = pd.concat([current_depara, new_rules], ignore_index=True)
    final_depara["_key"] = final_depara["unidade_origem"].apply(norm_text) + "|" + final_depara["sigla_origem"].apply(norm_text)
    final_depara = final_depara.drop_duplicates(subset="_key", keep="last").drop(columns="_key")
    write_table("de_para_operadoras_fat", final_depara)
    
    fat_df = read_table("faturamento")
    if not fat_df.empty:
        from src.etl import standardize_operator
        fat_df["operadora_padrao"] = standardize_operator(
            fat_df["unidade_original"],
            fat_df["operadora_original"],
            depara=final_depara
        )
        write_table("faturamento", fat_df)
    clear_data_caches()

def render_gap_manager():
    st.subheader("Análise de Gaps (Faturamento vs Recebido)")
    st.markdown("Mapeie as operadoras que estão no Faturamento mas não foram encontradas na Contabilidade. Ao salvar, o histórico de Faturamento será atualizado automaticamente.")
    
    fat_df = read_table("faturamento")
    cont_df = read_table("contabilidade")
    
    gaps = find_mapping_gaps(fat_df, cont_df)
    
    if gaps.empty:
        st.success("Não há gaps de mapeamento. Todas as operadoras do Faturamento coincidem com o Recebido!")
        return
        
    st.warning(f"Foram encontrados {len(gaps)} mapeamentos sem correspondência na Contabilidade.")
    
    ops_cont_list = [""] + sorted(list(cont_df['operadora_padrao'].dropna().unique()))
    
    with st.form("gap_mapping_form"):
        grid_data = gaps.copy()
        grid_data["operadora_correta"] = ""
        
        edited = st.data_editor(
            grid_data,
            column_config={
                "unidade_original": st.column_config.TextColumn("Unidade Orig. (Fat)", disabled=True),
                "operadora_original": st.column_config.TextColumn("Operadora Orig. (Fat)", disabled=True),
                "operadora_padrao": st.column_config.TextColumn("Padrão Atual (Fat)", disabled=True),
                "operadora_correta": st.column_config.SelectboxColumn(
                    "Mapear para (Recebido)",
                    help="Selecione a operadora correta da Contabilidade",
                    options=ops_cont_list,
                    required=False
                )
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed"
        )
        
        if st.form_submit_button("Salvar Mapeamentos e Reprocessar Histórico", type="primary"):
            to_fix = edited[edited["operadora_correta"].str.strip() != ""]
            if not to_fix.empty:
                with st.spinner("Reprocessando o histórico de faturamento com as novas regras..."):
                    apply_gap_fixes_and_reprocess(to_fix)
                st.success(f"{len(to_fix)} regras salvas e histórico reprocessado!")
                st.rerun()
            else:
                st.info("Nenhum mapeamento preenchido.")

def render_depara_operadoras_manager(
    title: str,
    description: str,
    mapping: pd.DataFrame,
    source_values: pd.DataFrame,
    table_name: str,
    key_prefix: str,
):
    grid = build_depara_operadoras_grid(mapping, source_values)
    pending = int((grid["status"] == "Pendente").sum())
    mapped = int((grid["status"] == "Mapeado").sum())
    used = int((grid["em_uso"] == "Sim").sum())
    standards = int(grid.loc[grid["nome_padrao"].astype(str).str.strip() != "", "nome_padrao"].apply(norm_text).nunique())

    st.markdown(
        f'''
        <div class="depara-hero">
            <div class="depara-hero-title">{title}</div>
            <div class="depara-hero-subtitle">{description}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Itens não mapeados", pending)
    c2.metric("Mapeamentos ativos", mapped)
    c3.metric("Origens em uso", used)
    c4.metric("Padrões distintos", standards)
    
    st.markdown('<div class="depara-toolbar">', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([1.5, 1, 1, 1])
    search = f1.text_input("Buscar", placeholder="Buscar operadora...", label_visibility="collapsed", key=f"{key_prefix}_search")
    
    opts_unidade = ["Todas (Unidades)"] + sorted(grid["unidade_origem"].unique().tolist())
    filter_unit = f2.selectbox("Filtrar Unidade", opts_unidade, key=f"{key_prefix}_funit", label_visibility="collapsed")
    
    filter_em_uso = f3.selectbox("Em Uso", ["Todos (Em uso)", "Sim", "Não"], key=f"{key_prefix}_fuso", label_visibility="collapsed")
    filter_status = f4.selectbox("Status", ["Todos (Status)", "Pendente", "Mapeado"], key=f"{key_prefix}_fstatus", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = grid.copy()
    if search:
        q = search.lower()
        filtered = filtered[
            filtered["sigla_origem"].str.lower().str.contains(q, na=False) |
            filtered["nome_padrao"].str.lower().str.contains(q, na=False) |
            filtered["unidade_origem"].str.lower().str.contains(q, na=False)
        ]
    if filter_unit != "Todas (Unidades)":
        filtered = filtered[filtered["unidade_origem"] == filter_unit]
    if filter_em_uso != "Todos (Em uso)":
        filtered = filtered[filtered["em_uso"] == filter_em_uso]
    if filter_status != "Todos (Status)":
        filtered = filtered[filtered["status"] == filter_status]

    edited = st.data_editor(
        filtered,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"{key_prefix}_editor",
        disabled=["status", "em_uso", "ultima_atualizacao"],
        column_config={
            "unidade_origem": st.column_config.TextColumn("Unidade Origem", width="medium"),
            "sigla_origem": st.column_config.TextColumn("Nome de origem", width="medium", required=True),
            "nome_padrao": st.column_config.TextColumn("Nome padrão", width="medium"),
            "status": st.column_config.TextColumn("Status", width="small"),
            "em_uso": st.column_config.TextColumn("Em uso", width="small"),
            "ultima_atualizacao": st.column_config.TextColumn("Última atualização", width="small"),
        },
    )

    if not edited.equals(filtered):
        if st.button("Salvar Alterações", key=f"{key_prefix}_save", type="primary", use_container_width=True):
            save_df = edited[["unidade_origem", "sigla_origem", "nome_padrao"]].copy()
            final_db = mapping.copy()
            for col in ["unidade_origem", "sigla_origem", "nome_padrao"]:
                if col not in final_db: final_db[col] = ""
            
            # Remove antigas que foram editadas
            for _, r in save_df.iterrows():
                final_db = final_db[~((final_db["unidade_origem"] == r["unidade_origem"]) & (final_db["sigla_origem"] == r["sigla_origem"]))]
            
            final_db = pd.concat([final_db, save_df], ignore_index=True)
            final_db = final_db.dropna(subset=["sigla_origem"])
            final_db = final_db[final_db["sigla_origem"].str.strip() != ""]
            final_db = final_db.drop_duplicates(subset=["unidade_origem", "sigla_origem"], keep="last")
            
            write_table(table_name, final_db)
            st.success("Mapeamentos salvos! Recarregue a página (F5) para aplicar.")


def render_depara_manager(
    title: str,
    description: str,
    mapping: pd.DataFrame,
    source_values: pd.Series,
    table_name: str,
    key_prefix: str,
    search_placeholder: str,
):
    grid = build_depara_grid(mapping, source_values)
    pending = int((grid["status"] == "Pendente").sum())
    mapped = int((grid["status"] == "Mapeado").sum())
    used = int((grid["em_uso"] == "Sim").sum())
    standards = int(grid.loc[grid["nome_padrao"].astype(str).str.strip() != "", "nome_padrao"].apply(norm_text).nunique())

    st.markdown(
        f"""
        <div class="depara-hero">
            <div class="depara-hero-title">{title}</div>
            <div class="depara-hero-subtitle">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Itens não mapeados", pending)
    c2.metric("Mapeamentos ativos", mapped)
    c3.metric("Origens em uso", used)
    c4.metric("Padrões distintos", standards)

    st.markdown('<div class="depara-toolbar">', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([2, 1, 1])
    search = f1.text_input("Buscar", placeholder=search_placeholder, label_visibility="collapsed", key=f"{key_prefix}_search")
    filter_em_uso = f2.selectbox("Em Uso", ["Todos (Em uso)", "Sim", "Não"], key=f"{key_prefix}_fuso", label_visibility="collapsed")
    filter_status = f3.selectbox("Status", ["Todos (Status)", "Pendente", "Mapeado"], key=f"{key_prefix}_fstatus", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = filter_depara_grid(grid, search)
    if filter_em_uso != "Todos (Em uso)":
        filtered = filtered[filtered["em_uso"] == filter_em_uso]
    if filter_status != "Todos (Status)":
        filtered = filtered[filtered["status"] == filter_status]
    edited = st.data_editor(
        filtered,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"{key_prefix}_editor",
        disabled=["status", "em_uso", "ultima_atualizacao"],
        column_config={
            "sigla_origem": st.column_config.TextColumn("Nome de origem", required=True),
            "nome_padrao": st.column_config.TextColumn("Nome padrão"),
            "status": st.column_config.SelectboxColumn("Status", options=["Mapeado", "Pendente"]),
            "em_uso": st.column_config.TextColumn("Em uso"),
            "ultima_atualizacao": st.column_config.TextColumn("Última atualização"),
        },
    )

    left, right = st.columns([2, 3])
    with left:
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Salvar alterações", type="primary", key=f"{key_prefix}_save"):
                base_to_save = depara_to_save(edited)
                untouched = mapping[
                    ~mapping["sigla_origem"].apply(norm_text).isin(base_to_save["sigla_origem"].apply(norm_text))
                ][["sigla_origem", "nome_padrao"]]
                write_table(table_name, pd.concat([untouched, base_to_save], ignore_index=True))
                st.success("DE/PARA salvo.")
                st.rerun()
        with col_btn2:
            import io
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                mapping.to_excel(writer, index=False, sheet_name="DE_PARA")
            st.download_button(
                "Extrair para Excel",
                data=buf.getvalue(),
                file_name=f"{table_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}_export_excel"
            )
    with right:
        st.caption(f"Mostrando {len(filtered)} de {len(grid)} registros.")

def count_inconsistencias(df: pd.DataFrame, tipo: str) -> int:
    if df.empty or "tipo" not in df or "qtd" not in df:
        return 0
    return int(df.loc[df["tipo"] == tipo, "qtd"].sum())

def render_inconsistencias(inc: pd.DataFrame):
    ensure_inconsistencias_table()
    manual = read_table("inconsistencias_manuais")
    inc = merge_inconsistencias_manuais(inc, manual)

    render_page_header(
        "Inconsistências Identificadas",
        "Auditoria automatizada de dados carregados e mapeamentos DE/PARA pendentes.",
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_issue_card("Unidades sem DE/PARA", count_inconsistencias(inc, "DE/PARA Unidade"), "CRÍTICO", "issue-card-critical")
    with c2:
        render_issue_card("Operadoras sem DE/PARA", count_inconsistencias(inc, "DE/PARA Operadora"), "CRÍTICO", "issue-card-critical")
    with c3:
        render_issue_card("Arquivos duplicados", count_inconsistencias(inc, "Arquivo Duplicado"), "ALTO", "issue-card-high")
    with c4:
        render_issue_card("Linhas zeradas", count_inconsistencias(inc, "Linha Zerada"), "MÉDIO", "issue-card-medium")
    with c5:
        render_issue_card("Chaves incompatíveis", count_inconsistencias(inc, "Chave Incompatível"), "BAIXA", "issue-card-low")

    st.divider()
    st.markdown('<div class="table-panel">', unsafe_allow_html=True)
    top_left, top_right = st.columns([2, 1])
    with top_left:
        st.markdown('<div class="section-title" style="padding: 18px 20px 0 20px;">Registro de Auditoria</div>', unsafe_allow_html=True)
    with top_right:
        query = st.text_input("Buscar inconsistência", placeholder="Buscar por origem...", label_visibility="collapsed")
    f1, f2 = st.columns([1, 1])
    severidades = ["Todas"] + sorted(inc["severidade"].dropna().unique().tolist()) if not inc.empty else ["Todas"]
    status_options = ["Todos"] + sorted(inc["status"].dropna().unique().tolist()) if not inc.empty else ["Todos"]
    with f1:
        selected_severity = st.selectbox("Severidade", severidades)
    with f2:
        selected_status = st.selectbox("Status", status_options)

    filtered = inc.copy()
    if selected_severity != "Todas":
        filtered = filtered[filtered["severidade"] == selected_severity]
    if selected_status != "Todos":
        filtered = filtered[filtered["status"] == selected_status]
    if query:
        needle = norm_text(query)
        search_cols = ["tipo", "origem", "descricao", "valor_encontrado", "acao_recomendada", "status", "observacao_manual"]
        mask = pd.Series(False, index=filtered.index)
        for col in search_cols:
            if col in filtered:
                mask = mask | filtered[col].fillna("").astype(str).apply(norm_text).str.contains(needle, regex=False)
        filtered = filtered[mask]

    if filtered.empty:
        st.success("Nenhuma inconsistência encontrada para os filtros selecionados.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    severity_order = {"Crítica": 0, "Alta": 1, "Média": 2, "Baixa": 3}
    filtered = (
        filtered.assign(_ordem=filtered["severidade"].map(severity_order).fillna(9))
        .sort_values(["_ordem", "tipo", "origem"])
        .drop(columns="_ordem")
    )
    user = st.text_input("Responsável pela atualização", value="sistema", key="inconsistencias_usuario")
    editable = filtered.copy()
    edited = st.data_editor(
        editable,
        width="stretch",
        hide_index=True,
        key="inconsistencias_editor",
        disabled=[
            "inconsistencia_id", "severidade", "tipo", "origem", "descricao",
            "valor_encontrado", "qtd", "atualizado_por", "atualizado_em",
        ],
        column_order=[
            "inconsistencia_id",
            "severidade",
            "tipo",
            "origem",
            "descricao",
            "valor_encontrado",
            "acao_recomendada",
            "status",
            "observacao_manual",
            "atualizado_por",
            "atualizado_em",
            "qtd",
        ],
        column_config={
            "inconsistencia_id": st.column_config.TextColumn("ID"),
            "severidade": st.column_config.TextColumn("Severidade"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "origem": st.column_config.TextColumn("Origem"),
            "descricao": st.column_config.TextColumn("Descrição"),
            "valor_encontrado": st.column_config.TextColumn("Valor encontrado"),
            "acao_recomendada": st.column_config.TextColumn("Ação recomendada"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["Pendente", "A revisar", "Em tratamento", "Resolvido", "Ignorado", "Informativo"],
            ),
            "observacao_manual": st.column_config.TextColumn("Observação manual", width="large"),
            "atualizado_por": st.column_config.TextColumn("Atualizado por"),
            "atualizado_em": st.column_config.TextColumn("Atualizado em"),
            "qtd": st.column_config.NumberColumn("Qtd.", format="%d"),
        },
    )
    left, right = st.columns([1, 4])
    with left:
        if st.button("Salvar auditoria", type="primary", key="salvar_inconsistencias"):
            save_inconsistencias_grid(edited, manual, user)
            st.success("Inconsistências atualizadas.")
            st.rerun()
    with right:
        st.caption("Edite status, ação recomendada e observação manual. Os demais campos são gerados automaticamente pela auditoria.")
    st.caption(f"Mostrando {len(filtered)} de {len(inc)} registros de auditoria.")
    st.markdown("</div>", unsafe_allow_html=True)

def count_quality_warnings(df: pd.DataFrame, value_cols: list[str], month_cols: list[str]) -> int:
    warnings = 0
    for col in value_cols:
        if col in df:
            warnings += int((pd.to_numeric(df[col], errors="coerce").fillna(0) == 0).sum())
    for col in month_cols:
        if col in df:
            months = pd.to_numeric(df[col], errors="coerce")
            warnings += int((months.isna() | ~months.between(1, 12)).sum())
    return warnings

def process_import_file(tipo: str, uploaded_file, year: int, depara: pd.DataFrame, depara_operadoras: pd.DataFrame) -> tuple[bool, str]:
    file_hash = ""
    try:
        raw, file_hash = read_upload_dataframe(uploaded_file)
        if file_already_imported(file_hash, tipo):
            register_importacao(
                tipo,
                uploaded_file.name,
                "-",
                len(raw),
                "Duplicidade detectada",
                "Arquivo não processado porque o mesmo conteúdo já consta no histórico.",
                file_hash,
            )
            return False, "Duplicidade detectada. O arquivo não foi importado novamente."

        if tipo == "Faturamento IW":
            processed = prepare_faturamento(raw, depara, depara_operadoras=depara_operadoras, fallback_year=int(year), origem=uploaded_file.name)
            atual = read_table("faturamento")
            final = pd.concat([atual, processed], ignore_index=True) if not atual.empty else processed
            write_table("faturamento", final)
            period = identify_period_label(processed, "mes_faturamento", "ano_faturamento")
            warning_count = count_quality_warnings(processed, ["valor_faturado"], ["mes_faturamento"])
        else:
            processed = prepare_contabilidade(raw, depara, depara_operadoras=depara_operadoras, fallback_year=int(year), origem=uploaded_file.name)
            atual = read_table("contabilidade")
            final = pd.concat([atual, processed], ignore_index=True) if not atual.empty else processed
            write_table("contabilidade", final)
            period = identify_period_label(processed, "mes_recebimento", "ano_recebimento")
            warning_count = count_quality_warnings(processed, ["valor_bruto", "valor_liquido"], ["mes_recebimento"])

        status = "Importado com avisos" if warning_count else "Importado com sucesso"
        details = f"{warning_count} aviso(s) de qualidade identificados." if warning_count else "Arquivo processado sem avisos críticos."
        register_importacao(tipo, uploaded_file.name, period, len(processed), status, details, file_hash)
        return True, f"{tipo} importado: {len(processed)} linhas. {details}"
    except Exception as exc:
        register_importacao(
            tipo,
            getattr(uploaded_file, "name", "Arquivo sem nome"),
            "-",
            0,
            "Erro de estrutura",
            str(exc),
            file_hash,
        )
        return False, f"Erro ao processar {tipo}: {exc}"

DINAMICA_IMPORT_LABELS = {
    "faturado_marco": "Faturamento Março",
    "faturado_abril": "Faturamento Abril",
    "rec_bruto_marco": "Recebido Bruto Março",
    "rec_liquido_marco": "Recebido Líquido Março",
    "rec_bruto_abril": "Recebido Bruto Abril",
    "rec_liquido_abril": "Recebido Líquido Abril",
    "rec_bruto_maio": "Recebido Bruto Maio",
    "alerta_diretoria": "Alerta vermelho diretoria",
    "rec_liquido_maio": "Recebido Líquido Maio",
    "observacao": "Observações",
}

def detected_dinamica_columns(base: pd.DataFrame) -> list[str]:
    detected = []
    for col in DINAMICA_IMPORT_LABELS:
        if col not in base:
            continue
        if col == "observacao":
            if base[col].fillna("").astype(str).str.strip().ne("").any():
                detected.append(col)
        elif pd.to_numeric(base[col], errors="coerce").fillna(0).abs().sum() > 0:
            detected.append(col)
    return detected

def process_dinamica_upload(uploaded_file, year: int, mode: str, selected_columns: list[str]) -> tuple[bool, str]:
    file_hash = ""
    tipo = "Base consolidada DINAMICA"
    try:
        data = uploaded_file.getvalue()
        file_hash = hashlib.sha256(data).hexdigest()
        base = parse_dinamica_workbook(io.BytesIO(data), origem=uploaded_file.name)
        if mode == "Complementar base atual":
            base = merge_base_dinamica(read_table("base_dinamica"), base, selected_columns, uploaded_file.name)
        else:
            keep_cols = set(selected_columns) | {"linha_origem", "unidade_original", "unidade_padrao", "operadora_original", "operadora_padrao", "origem_arquivo", "atualizado_em"}
            for col in DINAMICA_COLUMNS:
                if col not in keep_cols:
                    base[col] = "" if col in {"observacao", "origem_arquivo", "atualizado_em"} else 0
        base, fat_generated, cont_generated = replace_base_dinamica(base, uploaded_file.name, year=int(year))
        register_importacao(
            tipo,
            uploaded_file.name,
            "Fat: Mar/Abr/2026 | Rec: Abr/Mai/2026",
            len(base),
            "Base substituída",
            f"Base dinâmica importada. {len(fat_generated)} linhas de faturamento e {len(cont_generated)} linhas de recebimento geradas pelo sistema.",
            file_hash,
        )
        st.cache_data.clear()
        action = "complementada" if mode == "Complementar base atual" else "substituída"
        return True, f"Base {action} com {len(base)} linhas de unidade/operadora. Totais recalculados pelo sistema."
    except Exception as exc:
        register_importacao(
            tipo,
            getattr(uploaded_file, "name", "Arquivo sem nome"),
            "-",
            0,
            "Erro de estrutura",
            str(exc),
            file_hash,
        )
        return False, f"Erro ao processar a aba DINAMICA: {exc}"

def render_field_chips(fields: list[str]):
    st.markdown("".join([f'<span class="field-chip">{field}</span>' for field in fields]), unsafe_allow_html=True)

def render_dynamic_base_import_panel(year: int):
    st.markdown(
        """
        <div class="upload-panel">
            <h4>Base Consolidada DINAMICA</h4>
            <div class="small-muted">Substitui toda a base atual a partir da aba DINAMICA. Linhas de total/subtotal da planilha são ignoradas.</div>
            <div style="height: 10px"></div>
            <div class="small-muted"><strong>Campos esperados</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_field_chips([
        "UNIDADES X OPERADORA",
        "Faturado Março",
        "Faturado Abril",
        "Rec. Bruto Março",
        "Rec. Líquido Março",
        "Rec. Bruto Abr",
        "Rec. Líquido Abr",
        "Rec. Bruto Mai",
        "Alerta vermelho",
        "Rec. Líquido Mai",
        "Observação",
    ])
    uploaded = st.file_uploader(
        "Upload da base DINAMICA",
        type=["xlsx"],
        key="dinamica_upload",
        label_visibility="collapsed",
    )
    if uploaded:
        st.caption(f"Arquivo selecionado: `{uploaded.name}`")
        try:
            preview_base = parse_dinamica_workbook(io.BytesIO(uploaded.getvalue()), origem=uploaded.name)
            detected = detected_dinamica_columns(preview_base)
            st.caption(f"{len(preview_base)} linhas analíticas detectadas. Colunas detectadas: {', '.join(DINAMICA_IMPORT_LABELS[c] for c in detected) or 'nenhuma'}")
        except Exception as exc:
            preview_base = pd.DataFrame()
            detected = []
            st.warning(f"Não foi possível ler a aba DINAMICA: {exc}")
    else:
        detected = []
    mode = st.selectbox(
        "Modo de importação",
        ["Complementar base atual", "Substituir toda a base"],
        key="dinamica_import_mode",
        help="Use complementar para acrescentar/atualizar colunas de outro mês sem apagar as demais colunas já importadas.",
    )
    selected_columns = st.multiselect(
        "Colunas a carregar",
        options=list(DINAMICA_IMPORT_LABELS.keys()),
        default=detected,
        format_func=lambda col: DINAMICA_IMPORT_LABELS[col],
        key="dinamica_import_columns",
    )
    if st.button("Importar colunas selecionadas", type="primary", key="dinamica_upload_process", disabled=uploaded is None or not selected_columns):
        ok, message = process_dinamica_upload(uploaded, year, mode, selected_columns)
        if ok:
            st.success(message)
            st.rerun()
        else:
            st.warning(message)

def render_import_panel(
    title: str,
    subtitle: str,
    fields: list[str],
    uploader_label: str,
    uploader_key: str,
    button_label: str,
    tipo: str,
    year: int,
    depara: pd.DataFrame,
    depara_operadoras: pd.DataFrame,
):
    st.markdown(
        f"""
        <div class="upload-panel">
            <h4>{title}</h4>
            <div class="small-muted">{subtitle}</div>
            <div style="height: 10px"></div>
            <div class="small-muted"><strong>Campos esperados</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_field_chips(fields)
    uploaded = st.file_uploader(uploader_label, type=["xlsx", "csv"], key=uploader_key, label_visibility="collapsed")
    if uploaded:
        st.caption(f"Arquivo selecionado: `{uploaded.name}`")
    if st.button(button_label, type="primary", key=f"{uploader_key}_process", disabled=uploaded is None):
        ok, message = process_import_file(tipo, uploaded, year, depara, depara_operadoras)
        if ok:
            st.success(message)
        else:
            st.warning(message)

def render_import_history():
    ensure_importacoes_table()
    history = read_table("importacoes")
    st.subheader("Histórico de importações")
    if history.empty:
        st.info("Nenhuma importação registrada ainda.")
        return

    query = st.text_input("Buscar histórico", placeholder="Buscar por arquivo, tipo, período, status ou usuário...")
    filtered = history.copy()
    if query:
        needle = norm_text(query)
        mask = pd.Series(False, index=filtered.index)
        for col in ["tipo_arquivo", "nome_arquivo", "mes_ano_identificado", "status", "usuario", "detalhes"]:
            if col in filtered:
                mask = mask | filtered[col].fillna("").astype(str).apply(norm_text).str.contains(needle, regex=False)
        filtered = filtered[mask]

    if not filtered.empty:
        filtered = filtered.iloc[::-1].reset_index(drop=True)

    render_native_table(
        filtered,
        [
            "data_hora",
            "tipo_arquivo",
            "nome_arquivo",
            "mes_ano_identificado",
            "qtd_linhas",
            "status",
            "usuario",
            "detalhes",
        ],
        labels={
            "data_hora": "Data/hora",
            "tipo_arquivo": "Tipo de arquivo",
            "nome_arquivo": "Nome do arquivo",
            "mes_ano_identificado": "Mês/ano",
            "qtd_linhas": "Qtd. linhas",
            "status": "Status",
            "usuario": "Usuário",
            "detalhes": "Detalhes",
        },
        status_cols={"status"},
        strong_cols={"nome_arquivo"},
        max_rows=20,
    )
    st.caption(f"Mostrando {len(filtered)} de {len(history)} registros.")

def dashboard_status(row: pd.Series) -> str:
    faturado = float(row.get("faturado", 0) or 0)
    recebido = float(row.get("total_recebido_bruto", 0) or 0)
    perc = float(row.get("perc_recebido_total", 0) or 0)
    if faturado <= 0 and recebido > 0:
        return "Recebido sem faturamento"
    if faturado <= 0:
        return "Sem faturamento"
    if perc >= 1.05:
        return "Acima do faturado"
    if perc >= 0.95:
        return "Recebido"
    if recebido > 0:
        return "Parcial"
    return "Pendente"

def prepare_dashboard_consolidado(consolidado: pd.DataFrame) -> pd.DataFrame:
    if consolidado.empty:
        return consolidado
    out = consolidado.copy()
    if "alerta_diretoria" not in out:
        out["alerta_diretoria"] = 0
    if "sinal_diretoria" not in out:
        out["sinal_diretoria"] = ""
    out["sinal_diretoria"] = out["sinal_diretoria"].apply(normalize_director_signal)
    legacy_red = out["alerta_diretoria"].apply(as_bool_flag) & (out["sinal_diretoria"] == "")
    out.loc[legacy_red, "sinal_diretoria"] = "vermelho"
    out["alerta_diretoria"] = (out["sinal_diretoria"] == "vermelho").astype(int)
    out["status"] = out.apply(dashboard_status, axis=1)
    out["chave_executiva"] = out["unidade_padrao"].astype(str) + " | " + out["operadora_padrao"].astype(str)
    return out

def render_kpi_card(label: str, value: str, note: str = "", alert: bool = False):
    css_class = "kpi-card kpi-alert" if alert else "kpi-card"
    safe_label = html_text(label)
    safe_value = html_text(value)
    safe_note = html_text(note)
    st.markdown(
        f"""
        <div class="{css_class}">
            <div class="kpi-label">{safe_label}</div>
            <div class="kpi-value">{safe_value}</div>
            <div class="kpi-note">{safe_note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_issue_card(label: str, value: int, severity: str, css_class: str):
    st.markdown(
        f"""
        <div class="issue-card {css_class}">
            <span class="issue-severity">{severity}</span>
            <div class="issue-value">{value}</div>
            <div class="issue-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def pending_list_html(pending: pd.DataFrame) -> str:
    if pending.empty:
        return '<div class="small-muted">Não há pendências positivas no recorte selecionado.</div>'
    max_value = float(pending["diferenca_pendente"].max() or 1)
    rows = []
    for _, row in pending.head(5).iterrows():
        label = html_text(short_label(row.get("unidade_padrao", ""), 30))
        value = float(row.get("diferenca_pendente", 0) or 0)
        width = max(6, min(100, int((value / max_value) * 100)))
        rows.append(
            f"""
            <div class="pending-row">
                <div class="pending-row-top">
                    <span>{label}</span>
                    <span class="pending-row-value">{fmt_money_html(value)}</span>
                </div>
                <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
            </div>
            """
        )
    return "".join(rows)

def dashboard_detail_column_spec(df: pd.DataFrame) -> tuple[list[str], dict[str, str], set[str]]:
    fat_detail_cols = sorted(
        [col for col in df.columns if col.startswith("fat_")],
        key=lambda col: int(col.split("_", 1)[1]) if col.split("_", 1)[1].isdigit() else 99,
    )
    table_cols = [
        "unidade_padrao",
        "operadora_padrao",
        *fat_detail_cols,
        "faturado",
        "total_recebido_bruto",
        "total_recebido_liquido",
        "diferenca_pendente",
        "perc_recebido_total",
        "status",
        "alerta_diretoria",
        "observacoes_consolidadas",
    ]
    table_cols = [col for col in table_cols if col in df.columns]
    labels = {
        "unidade_padrao": "Unidade",
        "operadora_padrao": "Operadora",
        "faturado": "Faturamento Total",
        "total_recebido_bruto": "Rec. bruto",
        "total_recebido_liquido": "Rec. líquido",
        "diferenca_pendente": "Dif. pendente",
        "perc_recebido_total": "% recebido",
        "status": "Status",
        "alerta_diretoria": "Alerta",
        "observacoes_consolidadas": "Observações",
    }
    for col in fat_detail_cols:
        month = int(col.split("_", 1)[1])
        labels[col] = f"Fat. {MONTHS.get(month, month)}"
    return table_cols, labels, set(fat_detail_cols)

def render_dashboard_executivo(consolidado: pd.DataFrame, rec_months: list[int], fat: pd.DataFrame, cont: pd.DataFrame, depara: pd.DataFrame, depara_operadoras: pd.DataFrame):
    dash = prepare_dashboard_consolidado(consolidado)
    if dash.empty:
        st.warning("Ainda não há dados suficientes para consolidar com os parâmetros escolhidos.")
        return

    f1, f2, f3 = st.columns([1, 1, 1])
    unidade_opts = sorted(dash["unidade_padrao"].dropna().astype(str).unique().tolist())
    operadora_opts = sorted(dash["operadora_padrao"].dropna().astype(str).unique().tolist())
    status_opts = sorted(dash["status"].dropna().astype(str).unique().tolist())
    with f1:
        selected_unit = st.selectbox("Unidade/filial", ["Todas"] + unidade_opts)
    with f2:
        selected_op = st.selectbox("Operadora", ["Todas"] + operadora_opts)
    with f3:
        selected_status = st.selectbox("Status", ["Todos"] + status_opts)

    filtered = dash.copy()
    if selected_unit != "Todas":
        filtered = filtered[filtered["unidade_padrao"] == selected_unit]
    if selected_op != "Todas":
        filtered = filtered[filtered["operadora_padrao"] == selected_op]
    if selected_status != "Todos":
        filtered = filtered[filtered["status"] == selected_status]

    if filtered.empty:
        st.info("Nenhuma linha encontrada para os filtros selecionados.")
        return

    total_fat = filtered["faturado"].sum()
    total_bruto = filtered["total_recebido_bruto"].sum()
    total_liq = filtered["total_recebido_liquido"].sum()
    pendente = filtered["diferenca_pendente"].sum()
    perc = total_bruto / total_fat if total_fat else 0
    unidades = filtered["unidade_padrao"].nunique()
    operadoras = filtered["operadora_padrao"].nunique()
    alertas_diretoria = int(filtered["alerta_diretoria"].apply(as_bool_flag).sum()) if "alerta_diretoria" in filtered else 0

    render_kpi_row("dashboard", [
        {"key": "total_faturado", "label": "Total Faturado", "value": fmt_money(total_fat), "note": "Competência selecionada"},
        {"key": "recebido_bruto", "label": "Recebido Bruto", "value": fmt_money(total_bruto), "note": "Recebimentos selecionados"},
        {"key": "recebido_liquido", "label": "Recebido Líquido", "value": fmt_money(total_liq), "note": "Após retenções"},
        {"key": "diferenca_pendente", "label": "Diferença Pendente", "value": fmt_money(pendente), "note": "Faturado - recebido bruto", "alert": pendente > 0},
        {"key": "alertas_diretoria", "label": "Alertas Vermelhos", "value": str(alertas_diretoria), "note": "Marcados para diretoria", "alert": alertas_diretoria > 0},
        {"key": "perc_recebido", "label": "% Recebido", "value": fmt_pct(perc), "note": "Bruto sobre faturado"},
    ])

    st.caption(f"{unidades} unidades e {operadoras} operadoras com movimento no recorte selecionado.")

    chart_col, side_col = st.columns([2, 1])
    with chart_col:
        rec_data = []
        for m in rec_months:
            col = f"rec_bruto_{m}"
            if col in filtered:
                rec_data.append({"Mês": MONTHS[m], "Recebido Bruto": filtered[col].sum()})
        rec_df = pd.DataFrame(rec_data)
        st.markdown(
            f"""
            <div class="panel">
                <div class="section-title">Recebido Bruto por Mês</div>
                {dashboard_bar_chart_html(rec_df)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with side_col:
        pending = (
            filtered[filtered["diferenca_pendente"] > 0]
            .sort_values("diferenca_pendente", ascending=False)
            .head(5)
            .copy()
        )
        st.markdown(
            f"""
            <div class="panel">
                <div class="section-title">Top Pendências por Unidade</div>
                {pending_list_html(pending)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    t1, t2 = st.columns([4, 1])
    with t1:
        st.markdown('<div class="section-title">Top Pendências Detalhadas</div>', unsafe_allow_html=True)
    with t2:
        st.caption("Ver todas")
    table_cols, labels, fat_detail_cols = dashboard_detail_column_spec(filtered)
    top = filtered.sort_values("diferenca_pendente", ascending=False)[table_cols].head(20).copy()
    if "perc_recebido_total" in top:
        top["perc_recebido_total"] = top["perc_recebido_total"] * 100
    table_cols = configure_columns(
        "dashboard_detalhado",
        table_cols,
        labels,
        locked={"unidade_padrao", "operadora_padrao"},
    )
    render_native_table(
        top,
        table_cols,
        labels=labels,
        money_cols={"faturado", *fat_detail_cols, "total_recebido_bruto", "total_recebido_liquido", "diferenca_pendente"},
        pct_cols={"perc_recebido_total"},
        status_cols={"status"},
        strong_cols={"unidade_padrao"},
        highlight_cols={"faturado", *fat_detail_cols},
        max_rows=20,
    )

    with st.expander("Alertas executivos"):
        table_cols = [
            "Indicador",
            "Qtd.",
        ]
        inconsistencias = build_inconsistencias(fat, cont, depara, depara_operadoras)
        op_sem_depara = count_inconsistencias(inconsistencias, "DE/PARA Operadora")
        un_sem_depara = count_inconsistencias(inconsistencias, "DE/PARA Unidade")
        linhas_zeradas = count_inconsistencias(inconsistencias, "Linha Zerada")
        acima = int((filtered["status"] == "Acima do faturado").sum())
        parcial = int((filtered["status"] == "Parcial").sum())
        pendentes = int((filtered["status"] == "Pendente").sum())
        alerts = pd.DataFrame([
            {"Indicador": "Operadoras sem DE/PARA", "Qtd.": op_sem_depara},
            {"Indicador": "Unidades sem DE/PARA", "Qtd.": un_sem_depara},
            {"Indicador": "Linhas zeradas", "Qtd.": linhas_zeradas},
            {"Indicador": "Recebido acima do faturado", "Qtd.": acima},
            {"Indicador": "Recebimento parcial", "Qtd.": parcial},
            {"Indicador": "Sem recebimento", "Qtd.": pendentes},
        ])
        render_native_table(
            alerts,
            table_cols,
            labels={"Indicador": "Indicador", "Qtd.": "Qtd."},
            strong_cols={"Indicador"},
            max_rows=10,
        )

def ensure_comentarios_table():
    _db_ensure_table(
        """
        CREATE TABLE IF NOT EXISTS comentarios_manuais (
            unidade_padrao TEXT,
            operadora_padrao TEXT,
            mes_referencia INTEGER,
            ano_referencia INTEGER,
            comentario_manual TEXT,
            atualizado_por TEXT,
            atualizado_em TEXT
        )
        """
    )

def ensure_lancamentos_manuais_table():
    _db_ensure_table(
        """
        CREATE TABLE IF NOT EXISTS lancamentos_manuais (
            id TEXT PRIMARY KEY,
            unidade_padrao TEXT,
            operadora_padrao TEXT,
            mes_referencia INTEGER,
            ano_referencia INTEGER,
            tipo_lancamento TEXT,
            valor REAL,
            motivo TEXT,
            atualizado_por TEXT,
            atualizado_em TEXT
        )
        """
    )

def build_diferenca_unidade_summary(filtered: pd.DataFrame) -> pd.DataFrame:
    if filtered.empty:
        return pd.DataFrame()
    work = filtered.copy()
    if "alerta_diretoria" not in work:
        work["alerta_diretoria"] = 0
    work["alerta_diretoria"] = work["alerta_diretoria"].apply(lambda value: int(as_bool_flag(value)))
    summary = (
        work.groupby("unidade_padrao", dropna=False)
        .agg(
            qtd_operadoras=("operadora_padrao", "nunique"),
            faturado=("faturado", "sum"),
            total_recebido_bruto=("total_recebido_bruto", "sum"),
            total_recebido_liquido=("total_recebido_liquido", "sum"),
            diferenca_pendente=("diferenca_pendente", "sum"),
            alertas_vermelhos=("alerta_diretoria", "sum"),
            observacoes=("observacoes_consolidadas", lambda values: int(sum(1 for value in values if str(value or "").strip()))),
        )
        .reset_index()
    )
    summary["perc_recebido_total"] = summary.apply(
        lambda row: (float(row["total_recebido_bruto"]) / float(row["faturado"])) if float(row["faturado"] or 0) else 0,
        axis=1,
    )
    summary["status"] = summary.apply(dashboard_status, axis=1)
    summary["alerta_diretoria"] = (summary["alertas_vermelhos"] > 0).astype(int)
    return summary.sort_values(["alerta_diretoria", "diferenca_pendente"], ascending=[False, False]).reset_index(drop=True)

def render_diferenca_unidade_tab(filtered: pd.DataFrame):
    summary = build_diferenca_unidade_summary(filtered)
    if summary.empty:
        st.info("Nenhum resumo por unidade encontrado para os filtros selecionados.")
        return

    total_dif = summary["diferenca_pendente"].sum()
    unidades_alerta = int((summary["alerta_diretoria"] > 0).sum())
    unidades_criticas = int((summary["perc_recebido_total"] < 0.8).sum())
    pior_unidade = str(summary.sort_values("diferenca_pendente", ascending=False)["unidade_padrao"].iloc[0])

    render_kpi_row("diferenca_unidade", [
        {"key": "dif_total", "label": "Diferenca Total", "value": fmt_money(total_dif), "note": "Faturado - recebido bruto", "alert": total_dif > 0},
        {"key": "unidades_alerta", "label": "Unidades em Vermelho", "value": str(unidades_alerta), "note": "Com alerta da diretoria", "alert": unidades_alerta > 0},
        {"key": "unidades_criticas", "label": "Unidades Criticas", "value": str(unidades_criticas), "note": "Recebimento bruto abaixo de 80%", "alert": unidades_criticas > 0},
        {"key": "maior_dif", "label": "Maior Diferenca", "value": short_label(pior_unidade, 24), "note": fmt_money(summary["diferenca_pendente"].max()), "alert": summary["diferenca_pendente"].max() > 0},
    ])

    table = summary.copy()
    table["perc_recebido_total"] = table["perc_recebido_total"] * 100
    columns = [
        "alerta_diretoria",
        "unidade_padrao",
        "qtd_operadoras",
        "faturado",
        "total_recebido_bruto",
        "total_recebido_liquido",
        "diferenca_pendente",
        "perc_recebido_total",
        "status",
        "alertas_vermelhos",
        "observacoes",
    ]
    labels = {
        "alerta_diretoria": "Alerta",
        "unidade_padrao": "Unidade",
        "qtd_operadoras": "Operadoras",
        "faturado": "Faturamento",
        "total_recebido_bruto": "Rec. bruto",
        "total_recebido_liquido": "Rec. liquido",
        "diferenca_pendente": "Dif. pendente",
        "perc_recebido_total": "% recebido",
        "status": "Status",
        "alertas_vermelhos": "Alertas",
        "observacoes": "Obs.",
    }
    st.markdown('<div class="section-title">Consolidado da diferenca por unidade</div>', unsafe_allow_html=True)
    render_native_table(
        table,
        columns,
        labels=labels,
        money_cols={"faturado", "total_recebido_bruto", "total_recebido_liquido", "diferenca_pendente"},
        pct_cols={"perc_recebido_total"},
        status_cols={"status"},
        strong_cols={"unidade_padrao"},
        max_rows=60,
    )
    st.caption(f"{len(summary)} unidades no recorte selecionado.")

def render_acerto_contas_executive_view(filtered: pd.DataFrame):
    if filtered is None or filtered.empty:
        return

    st.markdown('<div class="section-title">Visao executiva dos acertos</div>', unsafe_allow_html=True)
    st.caption(
        "Valores do recorte filtrado. Saldo positivo indica valor a receber; "
        "saldo negativo indica valor a repassar."
    )

    branch_summary = build_branch_net_summary(filtered)
    operator_summary = (
        filtered.groupby("operadora", as_index=False)
        .agg(
            valor_acerto=("valor_acerto", "sum"),
            filiais_fiscais=("filial_fiscal_pagadora", "nunique"),
            filiais_recebedoras=("filial_faturadora_recebedora", "nunique"),
        )
        .sort_values("valor_acerto", ascending=False)
        .reset_index(drop=True)
    )
    total_filtered = float(operator_summary["valor_acerto"].sum())
    operator_summary["participacao"] = operator_summary["valor_acerto"].apply(
        lambda value: float(value) / total_filtered if total_filtered else 0.0
    )
    operator_summary["valor_formatado"] = operator_summary["valor_acerto"].apply(fmt_money)
    operator_summary["participacao_formatada"] = operator_summary["participacao"].apply(
        lambda value: f"{float(value) * 100:.1f}%".replace(".", ",")
    )

    chart_left, chart_right = st.columns([1.08, 0.92], gap="large")
    with chart_left:
        st.markdown("##### Posicao liquida por filial")
        if branch_summary.empty:
            st.info("Sem saldo por filial para o recorte selecionado.")
        else:
            branch_chart_data = branch_summary.copy()
            branch_chart_data["posicao"] = branch_chart_data["saldo_liquido"].apply(
                lambda value: "A receber" if float(value) > 0 else (
                    "A repassar" if float(value) < 0 else "Zerado"
                )
            )
            branch_chart_data["valor_liquido"] = branch_chart_data["saldo_liquido"].abs()
            branch_chart_data["saldo_formatado"] = branch_chart_data["saldo_liquido"].apply(fmt_money)
            branch_chart_data["valor_liquido_formatado"] = branch_chart_data["valor_liquido"].apply(fmt_money)
            branch_chart_data["repassar_formatado"] = branch_chart_data["total_a_pagar"].apply(fmt_money)
            branch_chart_data["receber_formatado"] = branch_chart_data["total_a_receber"].apply(fmt_money)

            max_net_value = max(float(branch_chart_data["valor_liquido"].max()), 1.0)
            net_domain = [0, max_net_value * 1.28]
            y_branch = alt.Y(
                "filial:N",
                title=None,
                sort=alt.SortField("valor_liquido", order="descending"),
                axis=alt.Axis(labelLimit=190),
            )
            x_net_value = alt.X(
                "valor_liquido:Q",
                title="Valor liquido (R$)",
                scale=alt.Scale(domain=net_domain),
                axis=alt.Axis(format="~s"),
            )
            branch_tooltip = [
                alt.Tooltip("filial:N", title="Filial"),
                alt.Tooltip("posicao:N", title="Posicao"),
                alt.Tooltip("saldo_formatado:N", title="Saldo liquido"),
                alt.Tooltip("repassar_formatado:N", title="Total a repassar"),
                alt.Tooltip("receber_formatado:N", title="Total a receber"),
            ]
            branch_base = alt.Chart(branch_chart_data).encode(y=y_branch)
            branch_bars = branch_base.mark_bar(size=18, cornerRadiusEnd=3).encode(
                x=x_net_value,
                color=alt.Color(
                    "posicao:N",
                    title=None,
                    scale=alt.Scale(
                        domain=["A receber", "A repassar", "Zerado"],
                        range=["#0B3473", "#D89B00", "#8A9099"],
                    ),
                    legend=alt.Legend(orient="top"),
                ),
                tooltip=branch_tooltip,
            )
            branch_labels = (
                alt.Chart(branch_chart_data)
                .mark_text(align="left", baseline="middle", dx=5, color="#22252A", fontSize=11)
                .encode(
                    x=alt.X("valor_liquido:Q", scale=alt.Scale(domain=net_domain)),
                    y=y_branch,
                    text="valor_liquido_formatado:N",
                )
            )
            branch_chart = (
                (branch_bars + branch_labels)
                .properties(height=max(290, len(branch_chart_data) * 30))
                .configure_view(stroke=None)
                .configure_axis(
                    labelColor="#30343B",
                    titleColor="#30343B",
                    gridColor="#E2E5EA",
                    domainColor="#C6CBD2",
                )
                .configure_legend(labelColor="#30343B")
            )
            st.altair_chart(branch_chart, width="stretch")

    with chart_right:
        st.markdown("##### Acertos por operadora")
        operator_chart_data = operator_summary.head(12).copy()
        max_operator = max(float(operator_chart_data["valor_acerto"].max()), 1.0)
        y_operator = alt.Y(
            "operadora:N",
            title=None,
            sort=alt.SortField("valor_acerto", order="descending"),
            axis=alt.Axis(labelLimit=180),
        )
        operator_bars = (
            alt.Chart(operator_chart_data)
            .mark_bar(size=18, color="#244F94", cornerRadiusEnd=3)
            .encode(
                x=alt.X(
                    "valor_acerto:Q",
                    title="Valor dos acertos (R$)",
                    scale=alt.Scale(domain=[0, max_operator * 1.28]),
                    axis=alt.Axis(format="~s"),
                ),
                y=y_operator,
                tooltip=[
                    alt.Tooltip("operadora:N", title="Operadora"),
                    alt.Tooltip("valor_formatado:N", title="Valor dos acertos"),
                    alt.Tooltip("participacao_formatada:N", title="Participacao"),
                    alt.Tooltip("filiais_fiscais:Q", title="Filiais que repassam"),
                    alt.Tooltip("filiais_recebedoras:Q", title="Filiais que recebem"),
                ],
            )
        )
        operator_labels = (
            alt.Chart(operator_chart_data)
            .mark_text(align="left", baseline="middle", dx=5, color="#22252A", fontSize=11)
            .encode(
                x=alt.X("valor_acerto:Q", scale=alt.Scale(domain=[0, max_operator * 1.28])),
                y=y_operator,
                text="valor_formatado:N",
            )
        )
        operator_chart = (
            (operator_bars + operator_labels)
            .properties(height=max(290, len(operator_chart_data) * 30))
            .configure_view(stroke=None)
            .configure_axis(
                labelColor="#30343B",
                titleColor="#30343B",
                gridColor="#E2E5EA",
                domainColor="#C6CBD2",
            )
        )
        st.altair_chart(operator_chart, width="stretch")
        if len(operator_summary) > 12:
            st.caption(f"Exibindo as 12 maiores de {len(operator_summary)} operadoras no recorte.")

    flow_summary = (
        filtered.groupby(
            ["filial_fiscal_pagadora", "filial_faturadora_recebedora"],
            as_index=False,
        )
        .agg(
            valor_acerto=("valor_acerto", "sum"),
            qtd_operadoras=("operadora", "nunique"),
        )
    )
    flow_summary["valor_formatado"] = flow_summary["valor_acerto"].apply(fmt_money)
    st.markdown("##### Mapa de repasses entre filiais")
    st.caption(
        "Nas linhas, a filial fiscal que recebeu o recurso e deve repassar. "
        "Nas colunas, a filial de atendimento/faturamento que deve receber."
    )
    flow_chart = (
        alt.Chart(flow_summary)
        .mark_rect(cornerRadius=2)
        .encode(
            x=alt.X(
                "filial_faturadora_recebedora:N",
                title="Atendimento/faturamento que recebe",
                sort=sorted(flow_summary["filial_faturadora_recebedora"].unique().tolist()),
                axis=alt.Axis(labelAngle=-32, labelLimit=150),
            ),
            y=alt.Y(
                "filial_fiscal_pagadora:N",
                title="Fiscal que repassa",
                sort=sorted(flow_summary["filial_fiscal_pagadora"].unique().tolist()),
                axis=alt.Axis(labelLimit=190),
            ),
            color=alt.Color(
                "valor_acerto:Q",
                title="Valor do acerto",
                scale=alt.Scale(range=["#EEF3FB", "#0B3473"]),
                legend=alt.Legend(format="~s"),
            ),
            tooltip=[
                alt.Tooltip("filial_fiscal_pagadora:N", title="Fiscal que repassa"),
                alt.Tooltip(
                    "filial_faturadora_recebedora:N",
                    title="Atendimento/faturamento que recebe",
                ),
                alt.Tooltip("valor_formatado:N", title="Valor do acerto"),
                alt.Tooltip("qtd_operadoras:Q", title="Operadoras"),
            ],
        )
        .properties(height=max(300, flow_summary["filial_fiscal_pagadora"].nunique() * 38))
        .configure_view(stroke="#D5DAE1")
        .configure_axis(
            labelColor="#30343B",
            titleColor="#30343B",
            domainColor="#C6CBD2",
        )
        .configure_legend(labelColor="#30343B", titleColor="#30343B")
    )
    st.altair_chart(flow_chart, width="stretch")


def render_acerto_contas_tab(
    consolidado: pd.DataFrame,
    fat_months: list[int],
    year: int,
):
    source = consolidado.copy()
    fresh_base = normalize_base_dinamica(read_table("base_dinamica"))
    if not fresh_base.empty:
        fresh_observations = (
            fresh_base.groupby(["unidade_padrao", "operadora_padrao"], dropna=False)["observacao"]
            .apply(lambda values: " | ".join(
                dict.fromkeys(str(value).strip() for value in values if str(value).strip())
            ))
            .reset_index()
            .rename(columns={"observacao": "observacao_fiscal_atual"})
        )
        source = source.merge(
            fresh_observations,
            on=["unidade_padrao", "operadora_padrao"],
            how="left",
        )
        if "observacao_fiscal" not in source:
            source["observacao_fiscal"] = ""
        source["observacao_fiscal"] = source["observacao_fiscal_atual"].where(
            source["observacao_fiscal_atual"].notna(),
            source["observacao_fiscal"],
        )
        source = source.drop(columns=["observacao_fiscal_atual"], errors="ignore")

    settlements = build_automatic_settlements(
        source,
        fat_months,
        int(year),
        read_table("de_para_unidades"),
    )
    if settlements.empty:
        st.info("Nenhum acerto de contas foi identificado automaticamente.")
        return

    ready = settlements[settlements["status"] == "Pronto"].copy()
    pending = settlements[settlements["status"] != "Pronto"].copy()
    total_value = float(ready["valor_acerto"].sum()) if not ready.empty else 0.0
    transfer_pairs = (
        ready[["filial_fiscal_pagadora", "filial_faturadora_recebedora"]]
        .drop_duplicates()
        .shape[0]
        if not ready.empty
        else 0
    )
    repasser_count = ready["filial_fiscal_pagadora"].nunique() if not ready.empty else 0

    render_kpi_row("acerto_contas", [
        {
            "key": "valor_acerto",
            "label": "Valor dos Acertos",
            "value": fmt_money(total_value),
            "note": "Repasses automaticos prontos",
        },
        {
            "key": "transferencias",
            "label": "Relacoes entre Filiais",
            "value": str(transfer_pairs),
            "note": "Fiscal que repassa para faturadora",
        },
        {
            "key": "repassadoras",
            "label": "Filiais com Repasse",
            "value": str(repasser_count),
            "note": "Receberam recurso e devem repassar",
        },
        {
            "key": "pendencias",
            "label": "Pendencias",
            "value": str(len(pending)),
            "note": "Fora do total automatico",
            "alert": len(pending) > 0,
        },
    ])

    filter_1, filter_2, filter_3, filter_4 = st.columns([0.8, 1.2, 1.2, 1.2])
    with filter_1:
        selected_competence = st.selectbox(
            "Competencia do acerto",
            ["Todas"] + ready["competencia"].drop_duplicates().tolist(),
            key="acerto_competencia",
        )
    with filter_2:
        selected_payer = st.selectbox(
            "Fiscal que recebeu e deve repassar",
            ["Todas"] + sorted(ready["filial_fiscal_pagadora"].dropna().unique().tolist()),
            key="acerto_pagadora",
        )
    with filter_3:
        selected_receiver = st.selectbox(
            "Atendimento/faturamento que deve receber",
            ["Todas"] + sorted(ready["filial_faturadora_recebedora"].dropna().unique().tolist()),
            key="acerto_recebedora",
        )
    with filter_4:
        selected_operator = st.selectbox(
            "Operadora do acerto",
            ["Todas"] + sorted(ready["operadora"].dropna().unique().tolist()),
            key="acerto_operadora",
        )

    filtered = ready.copy()
    if selected_competence != "Todas":
        filtered = filtered[filtered["competencia"] == selected_competence]
    if selected_payer != "Todas":
        filtered = filtered[filtered["filial_fiscal_pagadora"] == selected_payer]
    if selected_receiver != "Todas":
        filtered = filtered[filtered["filial_faturadora_recebedora"] == selected_receiver]
    if selected_operator != "Todas":
        filtered = filtered[filtered["operadora"] == selected_operator]

    if filtered.empty:
        st.info("Nenhuma transferencia encontrada para os filtros selecionados.")
    else:
        render_acerto_contas_executive_view(filtered)

        st.markdown('<div class="section-title">Transferencias sugeridas</div>', unsafe_allow_html=True)
        display = filtered[[
            "competencia",
            "filial_fiscal_pagadora",
            "filial_faturadora_recebedora",
            "operadora",
            "valor_acerto",
        ]].copy()
        display["valor_acerto"] = display["valor_acerto"].apply(fmt_money)
        display = display.rename(columns={
            "competencia": "Competencia",
            "filial_fiscal_pagadora": "Fiscal que recebeu e deve repassar",
            "filial_faturadora_recebedora": "Atendimento/faturamento que deve receber",
            "operadora": "Operadora",
            "valor_acerto": "Valor do acerto",
        })
        st.dataframe(display, hide_index=True, width="stretch", height=min(640, 38 + len(display) * 35))

        st.markdown('<div class="section-title">Texto para acerto de contas</div>', unsafe_allow_html=True)
        st.code(format_settlements_for_copy(filtered), language=None, wrap_lines=True)

        summary = build_branch_net_summary(filtered)
        if not summary.empty:
            summary["posicao"] = summary["saldo_liquido"].apply(
                lambda value: "Receber" if float(value) > 0 else (
                    "Repassar" if float(value) < 0 else "Zerado"
                )
            )
            summary["valor_liquido"] = summary["saldo_liquido"].abs()
            summary_display = summary[[
                "filial",
                "total_a_pagar",
                "total_a_receber",
                "posicao",
                "valor_liquido",
            ]].copy()
            for col in ["total_a_pagar", "total_a_receber", "valor_liquido"]:
                summary_display[col] = summary_display[col].apply(fmt_money)
            summary_display = summary_display.rename(columns={
                "filial": "Filial",
                "total_a_pagar": "Total a repassar",
                "total_a_receber": "Total a receber",
                "posicao": "Posicao liquida",
                "valor_liquido": "Valor liquido",
            })
            st.markdown('<div class="section-title">Resumo liquido por filial</div>', unsafe_allow_html=True)
            st.dataframe(summary_display, hide_index=True, width="stretch")

    if not pending.empty:
        with st.expander(f"Pendencias para revisao ({len(pending)})", expanded=False):
            pending_display = pending[[
                "competencia",
                "filial_fiscal_pagadora",
                "filial_faturadora_recebedora",
                "operadora",
                "valor_acerto",
                "status",
                "observacao_origem",
            ]].copy()
            pending_display["valor_acerto"] = pending_display["valor_acerto"].apply(fmt_money)
            pending_display = pending_display.rename(columns={
                "competencia": "Competencia",
                "filial_fiscal_pagadora": "Fiscal que recebeu e deve repassar",
                "filial_faturadora_recebedora": "Atendimento/faturamento que deve receber",
                "operadora": "Operadora",
                "valor_acerto": "Valor identificado",
                "status": "Pendencia",
                "observacao_origem": "Observacao de origem",
            })
            st.dataframe(pending_display, hide_index=True, width="stretch")

def save_director_alerts(edited: pd.DataFrame, base: pd.DataFrame, year: int) -> int:
    base = normalize_base_dinamica(base)
    if base.empty:
        return 0
    edited = edited.copy()
    for col in ["unidade_padrao", "operadora_padrao", "alerta_diretoria"]:
        if col not in edited:
            edited[col] = ""
    base["_key"] = base["unidade_padrao"].apply(norm_text) + "||" + base["operadora_padrao"].apply(norm_text)
    edited["_key"] = edited["unidade_padrao"].apply(norm_text) + "||" + edited["operadora_padrao"].apply(norm_text)
    changed = 0
    for _, row in edited.iterrows():
        key = row["_key"]
        if not key.strip("|"):
            continue
        new_value = int(as_bool_flag(row.get("alerta_diretoria", 0)))
        mask = base["_key"] == key
        if not mask.any():
            continue
        old_values = pd.to_numeric(base.loc[mask, "alerta_diretoria"], errors="coerce").fillna(0).astype(int)
        if not old_values.eq(new_value).all():
            changed += 1
        base.loc[mask, "alerta_diretoria"] = new_value
    replace_base_dinamica(base.drop(columns="_key", errors="ignore"), "Marcacao portal alerta diretoria", year=int(year))
    return changed

def render_director_alert_editor(scoped: pd.DataFrame, base: pd.DataFrame, year: int):
    if scoped.empty:
        st.info("Nenhuma linha disponivel para marcacao com os filtros atuais.")
        return
    if base is None or base.empty:
        st.warning("A marcacao vermelha depende da base dinamica importada. Importe a base consolidada antes de editar alertas.")
        return

    st.markdown(
        """
        <div class="director-alert-panel">
            <strong>Marcacao vermelha da diretoria</strong><br>
            Use o checkbox para sinalizar linhas que precisam ficar gritantes no consolidado. Ao salvar, a linha passa a abrir em vermelho no portal.
        </div>
        """,
        unsafe_allow_html=True,
    )

    grid = scoped[[
        "alerta_diretoria",
        "unidade_padrao",
        "operadora_padrao",
        "diferenca_pendente",
        "perc_recebido_total",
        "status",
        "observacoes_consolidadas",
    ]].copy()
    grid["alerta_diretoria"] = grid["alerta_diretoria"].apply(as_bool_flag)
    grid["perc_recebido_total"] = grid["perc_recebido_total"] * 100
    grid = grid.sort_values(["alerta_diretoria", "diferenca_pendente"], ascending=[False, False]).reset_index(drop=True)

    edited = st.data_editor(
        grid,
        width="stretch",
        hide_index=True,
        key="director_alert_editor",
        disabled=[
            "unidade_padrao",
            "operadora_padrao",
            "diferenca_pendente",
            "perc_recebido_total",
            "status",
            "observacoes_consolidadas",
        ],
        column_order=[
            "alerta_diretoria",
            "unidade_padrao",
            "operadora_padrao",
            "diferenca_pendente",
            "perc_recebido_total",
            "status",
            "observacoes_consolidadas",
        ],
        column_config={
            "alerta_diretoria": st.column_config.CheckboxColumn("Vermelho"),
            "unidade_padrao": st.column_config.TextColumn("Unidade"),
            "operadora_padrao": st.column_config.TextColumn("Operadora"),
            "diferenca_pendente": st.column_config.NumberColumn("Dif. pendente", format="R$ %.2f"),
            "perc_recebido_total": st.column_config.NumberColumn("% recebido", format="%.1f%%"),
            "status": st.column_config.TextColumn("Status"),
            "observacoes_consolidadas": st.column_config.TextColumn("Observacoes", width="large"),
        },
    )

    left, right = st.columns([1, 4])
    with left:
        if st.button("Salvar alertas", type="primary", key="save_director_alerts"):
            changed = save_director_alerts(edited, base, year)
            st.success(f"Alertas salvos. {changed} linha(s) alterada(s).")
            st.rerun()
    with right:
        qtd_alerta = int(edited["alerta_diretoria"].apply(as_bool_flag).sum()) if "alerta_diretoria" in edited else 0
        st.caption(f"{qtd_alerta} linhas marcadas em vermelho no recorte exibido.")

def render_analitico_base_editor(filtered: pd.DataFrame, base: pd.DataFrame, year: int):
    base = normalize_base_dinamica(base)
    if filtered.empty:
        st.info("Nenhuma linha disponivel no recorte atual para editar.")
        return
    if base.empty:
        st.warning("A edicao do analitico depende da base dinamica importada.")
        return

    visible_keys = set(
        filtered["unidade_padrao"].apply(norm_text) + "||" + filtered["operadora_padrao"].apply(norm_text)
    )
    working = base.copy().reset_index(drop=True)
    working["_row_id"] = range(len(working))
    working["_key"] = working["unidade_padrao"].apply(norm_text) + "||" + working["operadora_padrao"].apply(norm_text)
    editable = working[working["_key"].isin(visible_keys)].copy()

    if editable.empty:
        st.info("Nenhuma linha da base dinamica corresponde ao recorte exibido.")
        return

    editable["alerta_diretoria"] = editable["alerta_diretoria"].apply(as_bool_flag)
    editable = editable.sort_values(["unidade_padrao", "linha_origem", "operadora_padrao"]).reset_index(drop=True)

    value_cols = [
        "alerta_diretoria",
        "faturado_marco",
        "faturado_abril",
        "rec_bruto_marco",
        "rec_liquido_marco",
        "rec_bruto_abril",
        "rec_liquido_abril",
        "rec_bruto_maio",
        "rec_liquido_maio",
        "observacao",
    ]
    identity_cols = ["_row_id", "unidade_padrao", "operadora_padrao"]
    column_order = identity_cols + value_cols

    edited = st.data_editor(
        editable[column_order],
        width="stretch",
        hide_index=True,
        key="analitico_base_editor",
        disabled=identity_cols,
        column_order=column_order,
        column_config={
            "_row_id": st.column_config.NumberColumn("ID", format="%d"),
            "unidade_padrao": st.column_config.TextColumn("Unidade"),
            "operadora_padrao": st.column_config.TextColumn("Operadora"),
            "alerta_diretoria": st.column_config.CheckboxColumn("Vermelho"),
            "faturado_marco": st.column_config.NumberColumn("Faturado Marco", format="R$ %.2f"),
            "faturado_abril": st.column_config.NumberColumn("Faturado Abril", format="R$ %.2f"),
            "rec_bruto_marco": st.column_config.NumberColumn("Rec. Bruto Marco", format="R$ %.2f"),
            "rec_liquido_marco": st.column_config.NumberColumn("Rec. Liquido Marco", format="R$ %.2f"),
            "rec_bruto_abril": st.column_config.NumberColumn("Rec. Bruto Abril", format="R$ %.2f"),
            "rec_liquido_abril": st.column_config.NumberColumn("Rec. Liquido Abril", format="R$ %.2f"),
            "rec_bruto_maio": st.column_config.NumberColumn("Rec. Bruto Maio", format="R$ %.2f"),
            "rec_liquido_maio": st.column_config.NumberColumn("Rec. Liquido Maio", format="R$ %.2f"),
            "observacao": st.column_config.TextColumn("Observacao", width="large"),
        },
    )

    left, right = st.columns([1, 4])
    with left:
        if st.button("Salvar analitico", type="primary", key="save_analitico_base_editor"):
            updated = working.drop(columns="_key", errors="ignore").copy()
            changed_rows = 0
            for _, row in edited.iterrows():
                row_id = pd.to_numeric(row.get("_row_id"), errors="coerce")
                if pd.isna(row_id):
                    continue
                row_id = int(row_id)
                mask = updated["_row_id"] == row_id
                if not mask.any():
                    continue
                before = updated.loc[mask, value_cols].copy()
                for col in value_cols:
                    if col == "alerta_diretoria":
                        updated.loc[mask, col] = int(as_bool_flag(row.get(col, False)))
                    else:
                        updated.loc[mask, col] = row.get(col, updated.loc[mask, col].iloc[0])
                after = updated.loc[mask, value_cols].copy()
                if not before.reset_index(drop=True).equals(after.reset_index(drop=True)):
                    changed_rows += 1
            replace_base_dinamica(updated.drop(columns="_row_id", errors="ignore"), "Edicao analitico consolidado", year=int(year))
            st.success(f"Analitico salvo. {changed_rows} linha(s) alterada(s).")
            st.rerun()
    with right:
        st.caption(f"Editando {len(editable)} linhas do recorte atual. A tabela de apresentacao acima mantem o mesmo layout.")

def save_director_signal(target_key: str, selected_signal_label: str, base: pd.DataFrame, year: int) -> bool:
    base = normalize_base_dinamica(base)
    if base.empty or not target_key:
        return False
    signal = DIRECTOR_SIGNAL_VALUES.get(norm_text(selected_signal_label), normalize_director_signal(selected_signal_label))
    base["_key"] = base["unidade_padrao"].apply(norm_text) + "||" + base["operadora_padrao"].apply(norm_text)
    mask = base["_key"] == target_key
    if not mask.any():
        return False
    current = base.loc[mask, "sinal_diretoria"].fillna("").astype(str).apply(normalize_director_signal)
    changed = not current.eq(signal).all()
    if not changed:
        return False
    base.loc[mask, "sinal_diretoria"] = signal
    base.loc[mask, "alerta_diretoria"] = int(signal == "vermelho")
    replace_base_dinamica(base.drop(columns="_key", errors="ignore"), "Semaforo diretoria analitico", year=int(year))
    return changed

def persist_consolidado_inline_action():
    component_state = st.session_state.get(CONSOLIDADO_INLINE_COMPONENT_KEY)
    action = getattr(component_state, "action", None) if component_state is not None else None
    if not isinstance(action, dict):
        return

    unidade = str(action.get("unidade", "") or "").strip()
    operadora = str(action.get("operadora", "") or "").strip()
    action_type = str(action.get("type", "") or "").strip().lower()
    if not unidade or not operadora:
        return

    updated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        if action_type == "signal":
            signal = normalize_director_signal(action.get("value", ""))
            _db_execute_sql(
                """
                UPDATE base_dinamica
                SET sinal_diretoria = ?, alerta_diretoria = ?, atualizado_em = ?
                WHERE unidade_padrao = ? AND operadora_padrao = ?
                """,
                (signal, int(signal == "vermelho"), updated_at, unidade, operadora),
            )
        elif action_type == "observation":
            observation = str(action.get("value", "") or "").strip()[:10000]
            # Tenta atualizar usando o nome real da coluna no DB
            # A coluna pode ser 'observacao' (schema legado) ou 'observacao_fiscal' (schema atual)
            db_cols = _db_table_columns("base_dinamica")
            obs_col_name = "observacao_fiscal" if "observacao_fiscal" in db_cols else "observacao"
            _db_execute_sql(
                f"""
                UPDATE base_dinamica
                SET {obs_col_name} = ?, atualizado_em = ?
                WHERE unidade_padrao = ? AND operadora_padrao = ?
                """,
                (observation, updated_at, unidade, operadora),
            )
        elif action_type == "value_edit":
            col_key = str(action.get("column", ""))
            value = action.get("value", "")
            if col_key:
                numeric_val = float(str(value).replace("R$", "").replace(".", "").replace(",", ".").strip() or 0)
                # Atualiza na base_dinamica (opcional, para exibir imediatamente)
                _db_execute_sql(
                    f"UPDATE base_dinamica SET {col_key} = ? WHERE unidade_padrao = ? AND operadora_padrao = ?",
                    (numeric_val, unidade, operadora)
                )
                
                # Atualiza diretamente a tabela de faturamento se for faturamento
                if col_key.startswith("fat_"):
                    month = int(col_key.split("_")[1])
                    fat_df = read_table("faturamento")
                    fat_mask = (fat_df["unidade_padrao"].apply(norm_text) == norm_text(unidade)) & \
                               (fat_df["operadora_padrao"].apply(norm_text) == norm_text(operadora)) & \
                               (fat_df["mes_faturamento"] == month)
                    if fat_mask.any():
                        fat_df.loc[fat_mask, "valor_faturado"] = numeric_val
                    else:
                        new_fat = pd.DataFrame([{
                            "nf": f"INLINE-FAT-{month:02d}", "unidade_original": unidade, "unidade_padrao": unidade,
                            "operadora_original": operadora, "operadora_padrao": operadora, "paciente": "",
                            "valor_faturado": numeric_val, "mes_faturamento": month, "ano_faturamento": 2026,
                            "origem_arquivo": "EDICAO_INLINE", "fonte": "MANUAL"
                        }])
                        fat_df = pd.concat([fat_df, new_fat], ignore_index=True)
                    write_table("faturamento", fat_df)
                    
                elif col_key.startswith("rec_bruto_") or col_key.startswith("rec_liquido_"):
                    month = int(col_key.split("_")[-1])
                    is_bruto = "bruto" in col_key
                    cont_df = read_table("contabilidade")
                    cont_mask = (cont_df["unidade_padrao"].apply(norm_text) == norm_text(unidade)) & \
                                (cont_df["operadora_padrao"].apply(norm_text) == norm_text(operadora)) & \
                                (cont_df["mes_recebimento"] == month)
                    if cont_mask.any():
                        cont_df.loc[cont_mask, "valor_bruto" if is_bruto else "valor_liquido"] = numeric_val
                    else:
                        new_cont = pd.DataFrame([{
                            "nf": f"INLINE-REC-{month:02d}", "unidade_original": unidade, "unidade_padrao": unidade,
                            "operadora_original": operadora, "operadora_padrao": operadora,
                            "valor_bruto": numeric_val if is_bruto else 0,
                            "valor_liquido": numeric_val if not is_bruto else 0,
                            "data_pago": pd.NaT, "mes_recebimento": month, "ano_recebimento": 2026,
                            "observacao_original": "", "observacao_fiscal": "",
                            "origem_arquivo": "EDICAO_INLINE", "fonte": "MANUAL"
                        }])
                        cont_df = pd.concat([cont_df, new_cont], ignore_index=True)
                    write_table("contabilidade", cont_df)
        else:
            return
        clear_data_caches()
    except Exception as exc:
        st.session_state["consolidado_inline_error"] = f"Nao foi possivel salvar a linha: {exc}"

def consume_director_signal_action(base: pd.DataFrame, year: int) -> bool:
    target_key = unquote(get_query_param(DIRECTOR_SIGNAL_QUERY_KEY)).strip()
    if not target_key:
        return False
    signal_raw = unquote(get_query_param(DIRECTOR_SIGNAL_QUERY_VALUE)).strip() or "limpar"
    signal = normalize_director_signal(signal_raw)
    if target_key and base is not None and not base.empty:
        changed = save_director_signal(target_key, signal, base, int(year))
        st.session_state["director_signal_notice"] = "Semaforo atualizado." if changed else "Sem alteracao no semaforo."
    else:
        st.session_state["director_signal_notice"] = "Nao foi possivel atualizar o semaforo desta linha."
    clear_director_signal_query_params()
    st.rerun()
    return True

def render_inline_signal_editor(filtered: pd.DataFrame, base: pd.DataFrame, year: int):
    base = normalize_base_dinamica(base)
    if filtered.empty or base.empty:
        return

    options = filtered.copy().reset_index(drop=True)
    options["_key"] = options["unidade_padrao"].apply(norm_text) + "||" + options["operadora_padrao"].apply(norm_text)
    options["_label"] = options.apply(
        lambda row: f"{short_label(row.get('unidade_padrao', ''), 28)} | {short_label(row.get('operadora_padrao', ''), 28)}",
        axis=1,
    )
    key_to_label = dict(zip(options["_key"], options["_label"]))
    key_to_signal = dict(zip(options["_key"], options.get("sinal_diretoria", pd.Series([""] * len(options))).apply(normalize_director_signal)))
    keys = list(key_to_label.keys())
    if not keys:
        return

    st.markdown('<div class="signal-editor-title">Semaforo diretoria</div>', unsafe_allow_html=True)
    line_col, color_col, action_col = st.columns([2.4, 1.6, 0.8])
    with line_col:
        selected_key = st.selectbox(
            "Linha",
            keys,
            format_func=lambda key: key_to_label.get(key, key),
            label_visibility="collapsed",
            key="inline_signal_target",
        )
    current_signal = key_to_signal.get(selected_key, "")
    current_label = DIRECTOR_SIGNAL_LABELS.get(current_signal, "Sem marcador")
    with color_col:
        selected_signal = st.radio(
            "Cor",
            DIRECTOR_SIGNAL_OPTIONS,
            index=DIRECTOR_SIGNAL_OPTIONS.index(current_label) if current_label in DIRECTOR_SIGNAL_OPTIONS else 0,
            horizontal=True,
            label_visibility="collapsed",
            key=f"inline_signal_choice_{hashlib.md5(selected_key.encode('utf-8')).hexdigest()}",
        )
    with action_col:
        if st.button("Aplicar", type="primary", use_container_width=True, key="inline_signal_save"):
            changed = save_director_signal(selected_key, selected_signal, base, int(year))
            st.success("Semaforo atualizado." if changed else "Sem alteracao no semaforo.")
            st.rerun()

def render_consolidado_analitico(consolidado: pd.DataFrame, fat_months: list[int], rec_months: list[int], base_dinamica: pd.DataFrame | None = None, year: int = 2026):
    render_page_header("Consolidado", "Consulta analítica de faturamento e recebimentos por unidade, operadora e mês.")
    
    col_t1, col_t2 = st.columns([7, 3])
    with col_t2:
        edit_mode = st.toggle("✏️ Ativar Modo de Edição (Excel)", key="consolidado_edit_mode")
        
    if edit_mode:
        st.info("Você está no modo de edição direta! Altere, exclua ou inclua valores na base bruta. As mudanças refletirão no dashboard e nas planilhas.")
        bd = base_dinamica if base_dinamica is not None else read_base_dinamica(int(year))
        render_base_dinamica_editor(bd, int(year))
        return
        
    dash = prepare_dashboard_consolidado(consolidado)
    if dash.empty:
        st.warning("Ainda não há consolidado disponível para os parâmetros selecionados.")
        return

    st.markdown('<div class="filter-band-title">Filtros do consolidado</div>', unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns([1, 1, 1.2, 0.8, 0.8])
    with f1:
        selected_unit = st.selectbox("Unidade", ["Todas Unidades"] + sorted(dash["unidade_padrao"].dropna().unique().tolist()))
    with f2:
        selected_operator = st.selectbox("Operadora", ["Todas Operadoras"] + sorted(dash["operadora_padrao"].dropna().unique().tolist()))
    with f3:
        selected_status = st.multiselect("Status", sorted(dash["status"].dropna().unique().tolist()), placeholder="Todos")
    with f4:
        only_director_alerts = st.checkbox("Somente vermelhos", key="consolidado_only_director_alerts")
    with f5:
        sort_order = st.selectbox("Ordem (A-Z)", ["Padrão", "A-Z", "Z-A"])

    scoped = dash.copy()
    if selected_unit != "Todas Unidades":
        scoped = scoped[scoped["unidade_padrao"] == selected_unit]
    if selected_operator != "Todas Operadoras":
        scoped = scoped[scoped["operadora_padrao"] == selected_operator]
    if selected_status:
        scoped = scoped[scoped["status"].isin(selected_status)]
    filtered = scoped.copy()
    if only_director_alerts:
        filtered = filtered[filtered["alerta_diretoria"].apply(as_bool_flag)]

    if filtered.empty:
        st.info("Nenhum registro encontrado para os filtros selecionados.")
        return

    total_fat = filtered["faturado"].sum() if "faturado" in filtered else 0
    total_rec = filtered["total_recebido_bruto"].sum() if "total_recebido_bruto" in filtered else 0
    total_dif = filtered["diferenca_pendente"].sum() if "diferenca_pendente" in filtered else 0
    obs_count = int(filtered["observacoes_consolidadas"].fillna("").astype(str).str.strip().ne("").sum()) if "observacoes_consolidadas" in filtered else 0
    alert_count = int(filtered["alerta_diretoria"].apply(as_bool_flag).sum()) if "alerta_diretoria" in filtered else 0

    render_kpi_row("consolidado", [
        {"key": "faturamento", "label": "Faturamento", "value": fmt_money(total_fat), "note": "Competência selecionada"},
        {"key": "recebido_bruto", "label": "Recebido bruto", "value": fmt_money(total_rec), "note": "Total recebido no recorte"},
        {"key": "diferenca_pendente", "label": "Diferença pendente", "value": fmt_money(total_dif), "note": "Faturamento - recebido", "alert": total_dif > 0},
        {"key": "observacoes", "label": "Observações", "value": str(obs_count), "note": "Registros com nota fiscal/manual"},
    ])

    
    # Apply sort_order before rendering the sheet table
    work = filtered.copy()
    if sort_order == "A-Z":
        work = work.sort_values(["unidade_padrao", "operadora_padrao"], ascending=[True, True])
    elif sort_order == "Z-A":
        work = work.sort_values(["unidade_padrao", "operadora_padrao"], ascending=[False, True])
    else:
        if "ordem_base_dinamica" not in work:
            work["ordem_base_dinamica"] = range(1, len(work) + 1)
        work["ordem_base_dinamica"] = pd.to_numeric(work["ordem_base_dinamica"], errors="coerce").fillna(999999)
        work = work.sort_values(["ordem_base_dinamica", "operadora_padrao"], ascending=[True, True])
    
    render_consolidado_tabs(dash, work, fat_months, rec_months, int(year))

def render_lancamentos_manuais_tab():
    st.subheader("Ajustes e Lançamentos Manuais")
    st.caption("Adicione valores avulsos de faturamento ou recebimento que não constam nas planilhas originais. Esses valores serão automaticamente somados aos relatórios consolidados.")
    
    ensure_lancamentos_manuais_table()
    df_manuais = read_table("lancamentos_manuais")
    if df_manuais.empty:
        df_manuais = pd.DataFrame(columns=[
            "id", "unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia", 
            "tipo_lancamento", "valor", "motivo", "atualizado_por", "atualizado_em"
        ])
    
    config = {
        "id": st.column_config.TextColumn("ID", disabled=True),
        "unidade_padrao": st.column_config.TextColumn("Unidade (Exata)", required=True),
        "operadora_padrao": st.column_config.TextColumn("Operadora (Exata)", required=True),
        "mes_referencia": st.column_config.NumberColumn("Mês", min_value=1, max_value=12, step=1, required=True),
        "ano_referencia": st.column_config.NumberColumn("Ano", min_value=2020, max_value=2100, step=1, required=True),
        "tipo_lancamento": st.column_config.SelectboxColumn("Tipo", options=["Faturamento Extra", "Recebimento Extra"], required=True),
        "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
        "motivo": st.column_config.TextColumn("Motivo/Observação", required=False),
        "atualizado_por": st.column_config.TextColumn("Atualizado Por", disabled=True),
        "atualizado_em": st.column_config.TextColumn("Atualizado Em", disabled=True)
    }
    
    edited_df = st.data_editor(
        df_manuais,
        column_config=config,
        num_rows="dynamic",
        key="editor_manuais",
        use_container_width=True
    )
    
    if st.button("Salvar Lançamentos", type="primary"):
        import uuid
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        for idx, row in edited_df.iterrows():
            if pd.isna(row["id"]) or not str(row["id"]).strip():
                edited_df.at[idx, "id"] = f"MANUAL-{uuid.uuid4().hex[:8]}"
            edited_df.at[idx, "atualizado_em"] = now_str
            edited_df.at[idx, "atualizado_por"] = "admin"
            
        write_table("lancamentos_manuais", edited_df)
        st.success("Lançamentos salvos com sucesso! Eles já estão refletidos no consolidado.")
        clear_data_caches()
        st.rerun()

@st.fragment
def render_consolidado_tabs(
    dash: pd.DataFrame,
    filtered: pd.DataFrame,
    fat_months: list[int],
    rec_months: list[int],
    year: int,
):
    analitico_tab, diferenca_tab, acerto_tab, manuais_tab = st.tabs([
        "Analitico",
        "Consolidado da diferenca",
        "Acerto de contas",
        "Lançamentos Manuais",
    ])
    with analitico_tab:
        colA, colB = st.columns([8, 2])
        with colA:
            st.markdown('<div class="section-title">Consolidado por Unidade e Operadora</div>', unsafe_allow_html=True)
        with colB:
            # Exportação bem formatada usando o layout da tela
            payload = build_consolidado_inline_payload(filtered, fat_months, rec_months)
            excel_bytes = generate_consolidado_inline_excel(payload)

            st.download_button(
                "📥 Extrair para Excel",
                data=excel_bytes,
                file_name=f"Consolidado_Analitico_{year}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        render_consolidado_inline_table(filtered, fat_months, rec_months)
        st.caption(
            f"Mostrando {len(filtered)} linhas analiticas, agrupadas por "
            f"{filtered['unidade_padrao'].nunique()} unidades. Ultima sincronizacao: "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
    with diferenca_tab:
        render_diferenca_unidade_tab(filtered)
    with acerto_tab:
        render_acerto_contas_tab(dash, fat_months, int(year))
    with manuais_tab:
        render_lancamentos_manuais_tab()



def build_comentarios_grid(consolidado: pd.DataFrame, comentarios: pd.DataFrame, mes_referencia: int, ano_referencia: int) -> pd.DataFrame:
    if consolidado.empty:
        return pd.DataFrame(columns=[
            "unidade_padrao", "operadora_padrao", "mes_ano", "observacao_fiscal",
            "comentario_manual", "status_comentario", "atualizado_por", "atualizado_em",
        ])

    base = consolidado[["unidade_padrao", "operadora_padrao", "observacao_fiscal", "diferenca_pendente", "perc_recebido_total"]].copy()
    base["mes_referencia"] = int(mes_referencia)
    base["ano_referencia"] = int(ano_referencia)

    if comentarios.empty:
        comentarios = pd.DataFrame(columns=[
            "unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia",
            "comentario_manual", "atualizado_por", "atualizado_em",
        ])

    comments_ref = comentarios[
        (pd.to_numeric(comentarios["mes_referencia"], errors="coerce") == int(mes_referencia))
        & (pd.to_numeric(comentarios["ano_referencia"], errors="coerce") == int(ano_referencia))
    ].copy()

    merged = base.merge(
        comments_ref,
        on=["unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia"],
        how="left",
    )
    merged["observacao_fiscal"] = merged["observacao_fiscal"].fillna("").astype(str)
    merged["comentario_manual"] = merged["comentario_manual"].fillna("").astype(str)
    merged["atualizado_por"] = merged["atualizado_por"].fillna("")
    merged["atualizado_em"] = merged["atualizado_em"].fillna("")
    merged["mes_ano"] = f"{MONTHS.get(int(mes_referencia), mes_referencia)}/{int(ano_referencia)}"
    merged["status_comentario"] = merged.apply(
        lambda row: "Com comentário" if row["comentario_manual"].strip()
        else ("Fiscal automático" if row["observacao_fiscal"].strip() else "Pendente"),
        axis=1,
    )
    merged = merged.sort_values(["status_comentario", "diferenca_pendente"], ascending=[False, False])
    return merged[[
        "unidade_padrao", "operadora_padrao", "mes_ano", "observacao_fiscal",
        "comentario_manual", "status_comentario", "diferenca_pendente",
        "perc_recebido_total", "atualizado_por", "atualizado_em",
    ]].reset_index(drop=True)

def save_comentarios_grid(edited: pd.DataFrame, comentarios: pd.DataFrame, mes_referencia: int, ano_referencia: int, usuario: str):
    ensure_comentarios_table()
    required = ["unidade_padrao", "operadora_padrao", "comentario_manual"]
    for col in required:
        if col not in edited:
            edited[col] = ""

    edited_save = edited[required].copy()
    edited_save["comentario_manual"] = edited_save["comentario_manual"].fillna("").astype(str).str.strip()
    edited_save["mes_referencia"] = int(mes_referencia)
    edited_save["ano_referencia"] = int(ano_referencia)
    edited_save["atualizado_por"] = usuario.strip() or "sistema"
    edited_save["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    if comentarios.empty:
        comentarios = pd.DataFrame(columns=[
            "unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia",
            "comentario_manual", "atualizado_por", "atualizado_em",
        ])

    key_cols = ["unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia"]
    edited_keys = set(
        tuple(row[col] for col in key_cols)
        for _, row in edited_save.iterrows()
    )

    keep_rows = []
    for _, row in comentarios.iterrows():
        key = (
            row.get("unidade_padrao", ""),
            row.get("operadora_padrao", ""),
            int(row.get("mes_referencia", 0) or 0),
            int(row.get("ano_referencia", 0) or 0),
        )
        if key not in edited_keys:
            keep_rows.append(row.to_dict())

    new_rows = edited_save[edited_save["comentario_manual"] != ""][
        ["unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia", "comentario_manual", "atualizado_por", "atualizado_em"]
    ]
    final = pd.concat([pd.DataFrame(keep_rows), new_rows], ignore_index=True)
    if final.empty:
        final = pd.DataFrame(columns=[
            "unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia",
            "comentario_manual", "atualizado_por", "atualizado_em",
        ])
    write_table("comentarios_manuais", final)

def render_view_preferences(consolidado: pd.DataFrame, fat_months: list[int], rec_months: list[int]):
    st.markdown('<div class="section-title">Preferências de visualização</div>', unsafe_allow_html=True)
    st.caption("Configure cards e colunas fora das telas de apresentação. As escolhas ficam salvas no banco e passam a valer nas telas principais após salvar.")

    dash = prepare_dashboard_consolidado(consolidado) if consolidado is not None and not consolidado.empty else pd.DataFrame()
    dashboard_tab, consolidado_tab = st.tabs(["Dashboard Executivo", "Consolidado"])

    with dashboard_tab:
        render_kpi_settings(
            "dashboard",
            "Cards do topo",
            [
                ("total_faturado", "Total Faturado"),
                ("recebido_bruto", "Recebido Bruto"),
                ("recebido_liquido", "Recebido Líquido"),
                ("diferenca_pendente", "Diferença Pendente"),
                ("alertas_diretoria", "Alertas Vermelhos"),
                ("perc_recebido", "% Recebido"),
            ],
        )
        if dash.empty:
            st.info("Carregue dados para configurar as colunas detalhadas do Dashboard.")
        else:
            table_cols, labels, _ = dashboard_detail_column_spec(dash)
            render_column_settings(
                "dashboard_detalhado",
                "Colunas da tabela Top Pendências Detalhadas",
                table_cols,
                labels,
                locked={"unidade_padrao", "operadora_padrao"},
            )

    with consolidado_tab:
        render_kpi_settings(
            "consolidado",
            "Cards do topo",
            [
                ("faturamento", "Faturamento"),
                ("recebido_bruto", "Recebido bruto"),
                ("diferenca_pendente", "Diferença pendente"),
                ("observacoes", "Observações"),
            ],
        )
        if dash.empty:
            st.info("Carregue dados para configurar as colunas do Consolidado.")
        else:
            table_cols, labels, _, _ = consolidado_pivot_column_spec(dash, fat_months, rec_months)
            render_column_settings(
                "consolidado",
                "Colunas da tabela Consolidado por Unidade e Operadora",
                table_cols,
                labels,
                locked={"unidade_padrao", "operadora_padrao"},
            )

def render_comentarios_financeiros(consolidado: pd.DataFrame, mes_referencia: int, ano_referencia: int):
    ensure_comentarios_table()
    comentarios = read_table("comentarios_manuais")
    grid = build_comentarios_grid(consolidado, comentarios, mes_referencia, ano_referencia)

    if grid.empty:
        st.warning("Ainda não há consolidado disponível para gerar comentários com os filtros atuais.")
        return

    st.markdown('<div class="comment-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Filtros</div>', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([1, 1, 1, 1])
    with f1:
        only_missing = st.checkbox("Apenas sem comentário")
    with f2:
        only_fiscal = st.checkbox("Com observação fiscal")
    with f3:
        selected_unit = st.selectbox("Unidade", ["Todas"] + sorted(grid["unidade_padrao"].unique().tolist()))
    with f4:
        selected_operator = st.selectbox("Operadora", ["Todas"] + sorted(grid["operadora_padrao"].unique().tolist()))

    user = st.text_input("Usuário responsável", value="sistema")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = grid.copy()
    if only_missing:
        filtered = filtered[filtered["comentario_manual"].fillna("").str.strip() == ""]
    if only_fiscal:
        filtered = filtered[filtered["observacao_fiscal"].fillna("").str.strip() != ""]
    if selected_unit != "Todas":
        filtered = filtered[filtered["unidade_padrao"] == selected_unit]
    if selected_operator != "Todas":
        filtered = filtered[filtered["operadora_padrao"] == selected_operator]

    if filtered.empty:
        st.info("Nenhum registro encontrado para os filtros selecionados.")
        return

    h1, h2 = st.columns([3, 1])
    with h1:
        st.markdown(f'<div class="section-title">Registros de Competência <span class="field-chip">{len(filtered)} itens encontrados</span></div>', unsafe_allow_html=True)
    with h2:
        st.write("")

    editable = filtered.copy()
    editable["perc_recebido_total"] = editable["perc_recebido_total"] * 100
    edited = st.data_editor(
        editable,
        width="stretch",
        hide_index=True,
        key=f"comentarios_editor_{mes_referencia}_{ano_referencia}",
        disabled=[
            "unidade_padrao", "operadora_padrao", "mes_ano", "observacao_fiscal",
            "status_comentario", "diferenca_pendente", "perc_recebido_total",
            "atualizado_por", "atualizado_em",
        ],
        column_order=[
            "unidade_padrao", "operadora_padrao", "mes_ano", "observacao_fiscal",
            "comentario_manual", "status_comentario", "diferenca_pendente",
            "perc_recebido_total", "atualizado_por", "atualizado_em",
        ],
        column_config={
            "unidade_padrao": st.column_config.TextColumn("Unidade"),
            "operadora_padrao": st.column_config.TextColumn("Operadora"),
            "mes_ano": st.column_config.TextColumn("Mês/Ano"),
            "observacao_fiscal": st.column_config.TextColumn("Observação Fiscal (Auto)"),
            "comentario_manual": st.column_config.TextColumn("Comentário Manual", width="large"),
            "status_comentario": st.column_config.TextColumn("Status"),
            "diferenca_pendente": st.column_config.NumberColumn("Dif. pendente", format="R$ %.2f"),
            "perc_recebido_total": st.column_config.NumberColumn("% recebido", format="%.1f%%"),
            "atualizado_por": st.column_config.TextColumn("Atualizado por"),
            "atualizado_em": st.column_config.TextColumn("Atualizado em"),
        },
    )

    left, right = st.columns([1, 4])
    with left:
        if st.button("Salvar alterações", type="primary", key="salvar_comentarios"):
            edited_to_save = edited.copy()
            save_comentarios_grid(edited_to_save, comentarios, mes_referencia, ano_referencia, user)
            st.success("Comentários salvos.")
            st.rerun()
    with right:
        st.caption(f"Mostrando {len(filtered)} de {len(grid)} registros.")

def render_base_dinamica_editor(base: pd.DataFrame, year: int):
    st.markdown('<div class="section-title">Base dinâmica importada</div>', unsafe_allow_html=True)
    st.caption("Edite a base que alimenta o consolidado. Ao salvar, os totais são recalculados pelo sistema.")
    base = normalize_base_dinamica(base)
    if base.empty:
        st.info("Nenhuma base DINAMICA importada ainda.")
        return

    working = base.copy().reset_index(drop=True)
    working["_row_id"] = range(len(working))
    query = st.text_input(
        "Buscar na base dinâmica",
        placeholder="Buscar unidade, operadora ou observação...",
        key="base_dinamica_search",
    )
    filtered = working.copy()
    if query:
        needle = norm_text(query)
        mask = pd.Series(False, index=filtered.index)
        for col in ["unidade_original", "unidade_padrao", "operadora_original", "operadora_padrao", "observacao"]:
            mask = mask | filtered[col].fillna("").astype(str).apply(norm_text).str.contains(needle, regex=False)
        filtered = filtered[mask].copy()

    dynamic_faturado = [c for c in filtered.columns if str(c).startswith("faturado_")]
    dynamic_rec_bruto = [c for c in filtered.columns if str(c).startswith("rec_bruto_")]
    dynamic_rec_liquido = [c for c in filtered.columns if str(c).startswith("rec_liquido_")]
    
    dynamic_cols = []
    for fat in dynamic_faturado:
        dynamic_cols.append(fat)
    for rb in dynamic_rec_bruto:
        dynamic_cols.append(rb)
    for rl in dynamic_rec_liquido:
        dynamic_cols.append(rl)
    
    col_order = [
        "_row_id",
        "linha_origem",
        "unidade_original",
        "unidade_padrao",
        "operadora_original",
        "operadora_padrao",
        "alerta_diretoria",
    ] + dynamic_cols + [
        "observacao",
        "origem_arquivo",
        "atualizado_em",
    ]
    
    col_config = {
        "_row_id": st.column_config.NumberColumn("ID", format="%d"),
        "linha_origem": st.column_config.NumberColumn("Linha origem", format="%d"),
        "unidade_original": st.column_config.TextColumn("Unidade origem", required=True),
        "unidade_padrao": st.column_config.TextColumn("Unidade padrão", required=True),
        "operadora_original": st.column_config.TextColumn("Operadora origem", required=True),
        "alerta_diretoria": st.column_config.CheckboxColumn("Vermelho diretoria"),
        "operadora_padrao": st.column_config.TextColumn("Operadora padrão", required=True),
        "observacao": st.column_config.TextColumn("Observação", width="large"),
        "origem_arquivo": st.column_config.TextColumn("Origem"),
        "atualizado_em": st.column_config.TextColumn("Atualizado em"),
    }
    
    for c in dynamic_faturado:
        parts = c.split("_", 1)
        name = parts[1].capitalize() if len(parts) > 1 else c
        col_config[c] = st.column_config.NumberColumn(f"Faturado {name}", format="R$ %.2f")
        
    for c in dynamic_rec_bruto:
        parts = c.split("_", 2)
        name = parts[2].capitalize() if len(parts) > 2 else c
        col_config[c] = st.column_config.NumberColumn(f"Rec. Bruto {name}", format="R$ %.2f")
        
    for c in dynamic_rec_liquido:
        parts = c.split("_", 2)
        name = parts[2].capitalize() if len(parts) > 2 else c
        col_config[c] = st.column_config.NumberColumn(f"Rec. Líquido {name}", format="R$ %.2f")

    edited = st.data_editor(
        filtered,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="base_dinamica_editor",
        disabled=["_row_id", "origem_arquivo", "atualizado_em"],
        column_order=col_order,
        column_config=col_config,
    )

    left, right = st.columns([1, 4])
    with left:
        if st.button("Salvar base", type="primary", key="save_base_dinamica"):
            edited = edited.copy()
            if "_row_id" not in edited:
                edited["_row_id"] = pd.NA
            original_ids = set(filtered["_row_id"].dropna().astype(int).tolist())
            edited_existing_ids = set(pd.to_numeric(edited["_row_id"], errors="coerce").dropna().astype(int).tolist())
            deleted_ids = original_ids - edited_existing_ids
            keep = working[~working["_row_id"].isin(original_ids | deleted_ids)].copy()
            updated = edited.drop(columns=["_row_id"], errors="ignore").copy()
            next_line = int(pd.to_numeric(working["linha_origem"], errors="coerce").fillna(0).max()) + 1
            if "linha_origem" in updated:
                missing_line = pd.to_numeric(updated["linha_origem"], errors="coerce").fillna(0) <= 0
                for idx in updated[missing_line].index:
                    updated.loc[idx, "linha_origem"] = next_line
                    next_line += 1
            final = pd.concat([keep.drop(columns=["_row_id"], errors="ignore"), updated], ignore_index=True)
            replace_base_dinamica(final, "Edição manual base_dinamica", year=int(year))
            st.success("Base dinâmica salva e totais recalculados.")
            st.rerun()
    with right:
        st.caption(f"Mostrando {len(filtered)} de {len(base)} linhas. Linhas removidas no editor também serão removidas da base ao salvar.")

def render_export_cards(selected_report: str):
    rows = [REPORT_TYPES[:2], REPORT_TYPES[2:4], REPORT_TYPES[4:]]
    for row in rows:
        cols = st.columns(len(row))
        for col, item in zip(cols, row):
            active = " export-card-active" if item["label"] == selected_report else ""
            with col:
                st.markdown(
                    f"""
                    <div class="export-card{active}">
                        <div class="kpi-label">{item["short"]}</div>
                        <div class="export-card-title">{item["label"]}</div>
                        <div class="export-card-text">{item["description"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

def save_export_history(edited: pd.DataFrame, history: pd.DataFrame):
    ensure_exportacoes_table()
    if history is None or history.empty:
        history = pd.DataFrame(columns=[
            "exportacao_id", "data_hora", "tipo_relatorio", "formato", "nome_arquivo",
            "periodo", "qtd_linhas", "status", "usuario", "detalhes", "observacao_manual",
        ])
    required = [
        "exportacao_id", "data_hora", "tipo_relatorio", "formato", "nome_arquivo",
        "periodo", "qtd_linhas", "status", "usuario", "detalhes", "observacao_manual",
    ]
    for col in required:
        if col not in history:
            history[col] = ""
        if col not in edited:
            edited[col] = ""

    edited_save = edited[required].copy()
    edited_ids = set(edited_save["exportacao_id"].fillna("").astype(str))
    keep = history[~history["exportacao_id"].fillna("").astype(str).isin(edited_ids)][required].copy()
    final = pd.concat([keep, edited_save], ignore_index=True)
    write_table("exportacoes", final)

def render_export_history():
    ensure_exportacoes_table()
    history = read_table("exportacoes")
    st.subheader("Histórico de exportações recentes")
    if history.empty:
        st.info("Nenhuma exportação registrada ainda. O histórico será alimentado quando um relatório for baixado.")
        return

    query = st.text_input(
        "Buscar exportação",
        placeholder="Buscar por relatório, arquivo, formato, período, status ou usuário...",
        key="export_history_search",
    )
    filtered = history.copy()
    if query:
        needle = norm_text(query)
        mask = pd.Series(False, index=filtered.index)
        for col in ["tipo_relatorio", "formato", "nome_arquivo", "periodo", "status", "usuario", "detalhes"]:
            if col in filtered:
                mask = mask | filtered[col].fillna("").astype(str).apply(norm_text).str.contains(needle, regex=False)
        filtered = filtered[mask]

    if not filtered.empty:
        filtered = filtered.iloc[::-1].reset_index(drop=True)

    edited = st.data_editor(
        filtered,
        width="stretch",
        hide_index=True,
        key="export_history_editor",
        disabled=[
            "exportacao_id", "data_hora", "tipo_relatorio", "formato",
            "nome_arquivo", "periodo", "qtd_linhas",
        ],
        column_order=[
            "exportacao_id",
            "data_hora",
            "tipo_relatorio",
            "formato",
            "nome_arquivo",
            "periodo",
            "qtd_linhas",
            "status",
            "usuario",
            "detalhes",
            "observacao_manual",
        ],
        column_config={
            "exportacao_id": st.column_config.TextColumn("ID"),
            "data_hora": st.column_config.TextColumn("Data/hora"),
            "tipo_relatorio": st.column_config.TextColumn("Tipo de relatório"),
            "formato": st.column_config.TextColumn("Formato"),
            "nome_arquivo": st.column_config.TextColumn("Nome do arquivo"),
            "periodo": st.column_config.TextColumn("Período"),
            "qtd_linhas": st.column_config.NumberColumn("Qtd. linhas", format="%d"),
            "status": st.column_config.SelectboxColumn("Status", options=["Pronto", "Falha", "Reprocessar", "Arquivado"]),
            "usuario": st.column_config.TextColumn("Usuário"),
            "detalhes": st.column_config.TextColumn("Detalhes"),
            "observacao_manual": st.column_config.TextColumn("Observação manual", width="large"),
        },
    )
    if st.button("Salvar histórico de exportações", type="primary", key="salvar_export_history"):
        save_export_history(edited, history)
        st.success("Histórico de exportações atualizado.")
        st.rerun()
    st.caption(f"Mostrando {len(filtered)} de {len(history)} registros.")

def render_exportacoes(
    fat: pd.DataFrame,
    cont: pd.DataFrame,
    fat_months: list[int],
    rec_months: list[int],
    year: int,
    depara: pd.DataFrame,
    depara_operadoras: pd.DataFrame,
):
    ensure_exportacoes_table()
    render_page_header(
        "Central de Relatórios",
        "Selecione o tipo de documento desejado, ajuste as configurações e gere relatórios consolidados para análise executiva e auditoria operacional.",
    )

    if not fat_months or not rec_months:
        st.info("Selecione pelo menos um mês de faturamento e um mês de recebimento na barra lateral para gerar relatórios consolidados.")

    consolidado = build_consolidado(fat, cont, fat_months, rec_months, year=int(year)) if fat_months and rec_months and (not fat.empty or not cont.empty) else pd.DataFrame()
    inconsistencias = merge_inconsistencias_manuais(
        build_inconsistencias(fat, cont, depara, depara_operadoras),
        read_table("inconsistencias_manuais"),
    )
    comentarios_export = build_comentarios_export(fat, cont, fat_months, rec_months, int(year)) if fat_months and rec_months else pd.DataFrame()
    periodo = report_period_label(fat_months, rec_months, int(year))

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Opções de exportação")
        report_labels = [item["label"] for item in REPORT_TYPES]
        report_type = st.radio(
            "Tipo de documento",
            report_labels,
            horizontal=True,
            label_visibility="collapsed",
            key="export_report_type",
        )
        render_export_cards(report_type)
        st.divider()
        render_export_history()

    with right:
        st.markdown('<div class="export-panel">', unsafe_allow_html=True)
        st.subheader("Configurações do arquivo")
        report_key = sanitize_file_stem(report_type)
        file_stem = st.text_input(
            "Nome do arquivo",
            value=default_export_filename(report_type),
            key=f"export_filename_{report_key}",
        )
        output_format = st.radio(
            "Formato de saída",
            ["Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"],
            horizontal=True,
            key=f"export_format_{report_key}",
        )
        st.caption("PDF está previsto para uma próxima etapa. Excel preserva múltiplas abas; CSV exporta a base principal.")

        base_report = report_type.startswith("Base de")
        include_dashboard = st.checkbox(
            "Incluir Dashboard",
            value=report_type == "Relatório Executivo Excel",
            disabled=base_report,
            key=f"export_dashboard_{report_key}",
        )
        include_bases = st.checkbox(
            "Incluir Bases Detalhadas",
            value=report_type == "Relatório Executivo Excel",
            disabled=base_report,
            key=f"export_bases_{report_key}",
        )
        include_comments = st.checkbox(
            "Incluir Comentários",
            value=False,
            disabled=base_report,
            key=f"export_comments_{report_key}",
        )
        include_inconsistencies = st.checkbox(
            "Histórico de Inconsistências",
            value=report_type in ["Relatório Executivo Excel", "Relatório de Inconsistências"],
            disabled=base_report or report_type == "Relatório de Inconsistências",
            key=f"export_inconsistencies_{report_key}",
        )

        safe_stem = sanitize_file_stem(file_stem)
        user = st.text_input("Usuário responsável", value="sistema", key=f"export_user_{report_key}")

        sheets = build_report_sheets(
            report_type,
            consolidado,
            fat,
            cont,
            inconsistencias,
            comentarios_export,
            fat_months,
            rec_months,
            int(year),
            include_dashboard,
            include_bases,
            include_comments,
            include_inconsistencies,
        )
        st.markdown("**Conteúdo preparado**")
        st.caption(", ".join(sheets.keys()))

        if output_format == "PDF (.pdf)":
            st.warning("Exportação em PDF ainda não está implementada neste projeto. Use Excel para o relatório executivo completo.")
            st.button("Gerar relatório", disabled=True, use_container_width=True)
        elif output_format == "Excel (.xlsx)":
            file_name = f"{safe_stem}.xlsx"
            data = build_export_excel_bytes(sheets, report_type)
            row_count = export_rows_count(sheets)
            details = f"Abas: {', '.join(sheets.keys())}"
            st.download_button(
                "Gerar e baixar relatório",
                data=data,
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
                on_click=register_exportacao,
                args=(report_type, "Excel", file_name, periodo, row_count, "Pronto", details, user),
                key=f"download_excel_{report_key}",
            )
        else:
            csv_df = select_csv_export_frame(
                report_type,
                consolidado,
                fat,
                cont,
                inconsistencias,
                comentarios_export,
                fat_months,
                rec_months,
                int(year),
            )
            file_name = f"{safe_stem}.csv"
            data = df_to_csv_bytes(csv_df)
            details = "CSV da base principal do relatório selecionado."
            st.download_button(
                "Gerar e baixar relatório",
                data=data,
                file_name=file_name,
                mime="text/csv",
                type="primary",
                use_container_width=True,
                on_click=register_exportacao,
                args=(report_type, "CSV", file_name, periodo, len(csv_df), "Pronto", details, user),
                key=f"download_csv_{report_key}",
            )
        st.caption("O histórico é atualizado quando o arquivo é baixado.")
        st.markdown("</div>", unsafe_allow_html=True)

init_db_if_needed()
_db_auto_migrate()  # No primeiro deploy cloud, migra SQLite → PostgreSQL
_db_sync_cloud_seed()  # Atualiza base operacional no PostgreSQL quando o SQLite embarcado tiver versao mais nova
ensure_base_dinamica_table()
ensure_importacoes_table()
ensure_exportacoes_table()
ensure_inconsistencias_table()

current_page = render_sidebar_nav()
year, fat_months, rec_months = render_global_parameters()

depara_legado = read_table("de_para_unidades")
depara_ops_legado = read_table("de_para_operadoras")

depara_fat = read_table("de_para_unidades_fat")
if depara_fat.empty:
    depara_fat = depara_legado.copy() if not depara_legado.empty else DEFAULT_DEPARA.copy()
    write_table("de_para_unidades_fat", depara_fat)

depara_cont = read_table("de_para_unidades_cont")
if depara_cont.empty:
    depara_cont = depara_legado.copy() if not depara_legado.empty else DEFAULT_DEPARA.copy()
    write_table("de_para_unidades_cont", depara_cont)

depara_ops_fat = read_table("de_para_operadoras_fat")
if depara_ops_fat.empty:
    depara_ops_fat = depara_ops_legado.copy() if not depara_ops_legado.empty else DEFAULT_OPERADORA_DEPARA.copy()
    write_table("de_para_operadoras_fat", depara_ops_fat)

depara_ops_cont = read_table("de_para_operadoras_cont")
if depara_ops_cont.empty:
    depara_ops_cont = depara_ops_legado.copy() if not depara_ops_legado.empty else DEFAULT_OPERADORA_DEPARA.copy()
    write_table("de_para_operadoras_cont", depara_ops_cont)

# Aliases de compatibilidade para partes da UI que nao precisaram dividir
depara = depara_fat
depara_operadoras = depara_ops_fat

fat, cont, base_dinamica = load_operational_tables(int(year))
hist = read_table("consolidado_historico")
seed_importacoes_from_current_base(fat, cont)

consolidado_atual = build_consolidado(fat, cont, fat_months, rec_months, year=int(year)) if fat_months and rec_months and (not fat.empty or not cont.empty) else pd.DataFrame()
consolidado_atual = merge_base_dinamica_observations(consolidado_atual, base_dinamica)
consolidado_atual = merge_manual_comments(consolidado_atual, int(year), fat_months)
inconsistencias_atual = merge_inconsistencias_manuais(
    build_inconsistencias(fat, cont, depara, depara_operadoras),
    read_table("inconsistencias_manuais"),
)
excel_pages = {"Dashboard Executivo", "Consolidado"}
top_excel = (
    df_to_excel_bytes(consolidado_atual, fat, cont, inconsistencias_atual)
    if current_page in excel_pages and not consolidado_atual.empty
    else None
)

render_topbar(current_page, top_excel)

if current_page == "Importações":
    render_page_header(
        "Importações",
        "Faça o upload dos arquivos de faturamento e recebimentos para conciliação.",
    )
    render_dynamic_base_import_panel(int(year))
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        render_import_panel(
            title="Faturamento IW",
            subtitle="Formatos aceitos: .xlsx e .csv",
            fields=["UNIDADE", "CONVENIO", "CONVENIO CONSOLIDADO", "Valor a Cobrar", "COMPETENCIA FAT", "ID Doc", "Nome do Paciente"],
            uploader_label="Upload de faturamento IW",
            uploader_key="fat_upload",
            button_label="Processar faturamento",
            tipo="Faturamento IW",
            year=int(year),
            depara=depara,
            depara_operadoras=depara_operadoras,
        )
    with col2:
        render_import_panel(
            title="Contabilidade / Recebimentos",
            subtitle="Formatos aceitos: .xlsx e .csv",
            fields=["Nº NF", "UNIDADE", "OPERADORA", "VALOR BRUTO", "VALOR LÍQUIDO", "DTA DE PAGO", "MÊS DE RECEBIMENTO", "OBSERVAÇÕES"],
            uploader_label="Upload de contabilidade/recebimentos",
            uploader_key="cont_upload",
            button_label="Processar contabilidade",
            tipo="Contabilidade/Recebimentos",
            year=int(year),
            depara=depara,
            depara_operadoras=depara_operadoras,
        )

    st.warning("Março está disponível inicialmente como histórico consolidado do modelo antigo. Para rastreabilidade completa, importe o faturamento bruto e a contabilidade bruta de março quando tiver os arquivos.")
    st.divider()
    render_import_history()

elif current_page == "DE/PARA":
    render_page_header(
        "Governança DE/PARA",
        "Gerencie o mapeamento entre nomenclaturas de origem e padrões do sistema.",
    )
    depara_units_fat_tab, depara_ops_fat_tab, depara_units_cont_tab, depara_ops_cont_tab = st.tabs([
        "Unidades (Fat.)", 
        "Operadoras (Fat.)",
        "Unidades (Rec.)",
        "Operadoras (Rec.)"
    ])

    with depara_units_fat_tab:
        render_depara_manager(
            title="DE/PARA de Unidades (Faturamento)",
            description="Controle os nomes de filiais/unidades vindos do faturamento.",
            mapping=depara_fat,
            source_values=source_values_for_depara(fat, "unidade_original"),
            table_name="de_para_unidades_fat",
            key_prefix="depara_unidades_fat",
            search_placeholder="Buscar unidade...",
        )
    with depara_ops_fat_tab:
        render_depara_operadoras_manager(
            title="DE/PARA de Operadoras (Faturamento)",
            description="Padronize convênios vindos do faturamento vinculados a cada Unidade.",
            mapping=depara_ops_fat,
            source_values=source_values_for_depara_operadoras(fat),
            table_name="de_para_operadoras_fat",
            key_prefix="depara_ops_fat",
        )
    with depara_gaps_tab:
        render_gap_manager()
    with depara_units_cont_tab:
        render_depara_manager(
            title="DE/PARA de Unidades (Recebimento)",
            description="Controle os nomes de filiais/unidades vindos da contabilidade.",
            mapping=depara_cont,
            source_values=source_values_for_depara(cont, "unidade_original"),
            table_name="de_para_unidades_cont",
            key_prefix="depara_unidades_cont",
            search_placeholder="Buscar unidade...",
        )
    with depara_ops_cont_tab:
        render_depara_operadoras_manager(
            title="DE/PARA de Operadoras (Recebimento)",
            description="Padronize convênios vindos da contabilidade vinculados a cada Unidade.",
            mapping=depara_ops_cont,
            source_values=source_values_for_depara_operadoras(cont),
            table_name="de_para_operadoras_cont",
            key_prefix="depara_ops_cont",
        )

elif current_page == "Dashboard Executivo":
    if not fat_months or not rec_months:
        st.info("Selecione pelo menos um mês de faturamento e um mês de recebimento.")
    else:
        render_dashboard_executivo(consolidado_atual, rec_months, fat, cont, depara, depara_operadoras)

elif current_page == "Consolidado":
    render_consolidado_analitico(consolidado_atual, fat_months, rec_months, base_dinamica, int(year))

elif current_page == "Comentários":
    if not fat_months or not rec_months:
        st.info("Selecione pelo menos um mês de faturamento e um mês de recebimento para gerenciar comentários.")
    else:
        render_page_header(
            "Gestão de Comentários",
            "Gerencie justificativas para divergências de faturamento. Comentários fiscais ficam separados dos apontamentos manuais.",
        )
        comment_month = st.selectbox(
            "Mês de referência do comentário",
            options=fat_months,
            format_func=lambda x: MONTHS[x],
        )
        consolidado_comentarios = build_consolidado(fat, cont, [int(comment_month)], rec_months, year=int(year)) if not fat.empty or not cont.empty else pd.DataFrame()
        render_comentarios_financeiros(consolidado_comentarios, int(comment_month), int(year))

elif current_page == "Inconsistências":
    render_inconsistencias(inconsistencias_atual)

elif current_page == "Exportações":
    render_exportacoes(fat, cont, fat_months, rec_months, int(year), depara, depara_operadoras)

else:
    render_page_header("Configurações", "Contexto técnico e pontos de manutenção do projeto.")
    render_view_preferences(consolidado_atual, fat_months, rec_months)
    st.divider()
    render_base_dinamica_editor(base_dinamica, int(year))
    st.divider()
    with st.expander("Bases carregadas e histórico antigo", expanded=False):
        st.subheader("Faturamento carregado")
        st.dataframe(fat, width="stretch", hide_index=True)
        st.subheader("Contabilidade carregada")
        st.dataframe(cont, width="stretch", hide_index=True)
        st.subheader("Histórico consolidado importado dos relatórios antigos")
        st.dataframe(hist, width="stretch", hide_index=True)
    st.divider()
    st.markdown("""
Este projeto já vem com:

- `data/raw/`: arquivos reais enviados pelo Jackson;
- `data/app.db`: base SQLite inicial;
- `src/etl.py`: funções de limpeza, padronização, DE/PARA de unidades/operadoras e consolidação;
- `scripts/seed_database.py`: recria a base inicial;
- `docs/CODEX_CONTEXT.md`: prompt técnico para orientar o Codex.

Ponto importante: quando a `base_dinamica` estiver carregada, ela passa a ser a fonte principal do sistema. Os totais da planilha não são usados; o app recalcula faturamento, recebimentos, diferenças e percentuais.
""")

