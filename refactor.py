import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace f1, f2, f3, f4 columns block
old_filters = '''    f1, f2, f3, f4 = st.columns([1, 1, 1.4, 0.9])
    with f1:
        selected_unit = st.selectbox("Unidade", ["Todas Unidades"] + sorted(dash["unidade_padrao"].dropna().unique().tolist()))
    with f2:
        selected_operator = st.selectbox("Operadora", ["Todas Operadoras"] + sorted(dash["operadora_padrao"].dropna().unique().tolist()))
    with f3:
        selected_status = st.multiselect("Status", sorted(dash["status"].dropna().unique().tolist()), placeholder="Todos")
    with f4:
        only_director_alerts = st.checkbox("Somente vermelhos", key="consolidado_only_director_alerts")'''

new_filters = '''    f1, f2, f3, f4, f5 = st.columns([1, 1, 1.2, 0.8, 0.8])
    with f1:
        selected_unit = st.selectbox("Unidade", ["Todas Unidades"] + sorted(dash["unidade_padrao"].dropna().unique().tolist()))
    with f2:
        selected_operator = st.selectbox("Operadora", ["Todas Operadoras"] + sorted(dash["operadora_padrao"].dropna().unique().tolist()))
    with f3:
        selected_status = st.multiselect("Status", sorted(dash["status"].dropna().unique().tolist()), placeholder="Todos")
    with f4:
        only_director_alerts = st.checkbox("Somente vermelhos", key="consolidado_only_director_alerts")
    with f5:
        sort_order = st.selectbox("Ordem (A-Z)", ["Padrão", "A-Z", "Z-A"])'''

content = content.replace(old_filters, new_filters)

# 2. Replace the render call
old_render = '''    st.markdown('<div class="section-title">Consolidado por Unidade e Operadora</div>', unsafe_allow_html=True)
    render_consolidado_sheet_table(filtered, fat_months, rec_months)
    st.caption(f"Mostrando {len(filtered)} linhas analíticas, agrupadas por {filtered['unidade_padrao'].nunique()} unidades. Última sincronização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")'''

new_render = '''    st.markdown('<div class="section-title">Consolidado por Unidade e Operadora</div>', unsafe_allow_html=True)
    render_consolidado_editable_table(filtered, fat_months, rec_months, sort_order, int(year))
    st.caption(f"Mostrando {len(filtered)} linhas analíticas, agrupadas por {filtered['unidade_padrao'].nunique()} unidades. Última sincronização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")'''

content = content.replace(old_render, new_render)

# 3. Add render_consolidado_editable_table
new_func = '''
def render_consolidado_editable_table(filtered: pd.DataFrame, fat_months: list[int], rec_months: list[int], sort_order: str, year: int):
    fat_cols = [f"fat_{month}" for month in fat_months if f"fat_{month}" in filtered]
    rec_cols = [f"rec_bruto_{month}" for month in rec_months if f"rec_bruto_{month}" in filtered]
    
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
        
    edit_df = work[["unidade_padrao", "operadora_padrao"] + fat_cols + rec_cols + ["observacoes_consolidadas"]].copy()
    edit_df = edit_df.reset_index(drop=True)
    
    col_config = {
        "unidade_padrao": st.column_config.TextColumn("Unidade", disabled=True, width="medium"),
        "operadora_padrao": st.column_config.TextColumn("Operadora", disabled=True, width="medium"),
        "observacoes_consolidadas": st.column_config.TextColumn("Observações", disabled=True, width="large")
    }
    for m in fat_months:
        c = f"fat_{m}"
        col_config[c] = st.column_config.NumberColumn(f"Fat {MONTHS.get(m, m)}", format="R$ %.2f")
    for m in rec_months:
        c = f"rec_bruto_{m}"
        col_config[c] = st.column_config.NumberColumn(f"Rec {MONTHS.get(m, m)}", format="R$ %.2f")
        
    edited = st.data_editor(
        edit_df,
        hide_index=True,
        column_config=col_config,
        use_container_width=True,
        key="consolidado_editor"
    )
    
    import time
    changed = False
    for col in fat_cols + rec_cols:
        edited_col = pd.to_numeric(edited[col], errors='coerce').fillna(0)
        orig_col = pd.to_numeric(edit_df[col], errors='coerce').fillna(0)
        diff = edited_col - orig_col
        changed_mask = diff.abs() > 0.01
        
        if changed_mask.any():
            ensure_lancamentos_manuais_table()
            lanc = read_table("lancamentos_manuais")
            new_rows = []
            
            for idx in diff[changed_mask].index:
                val_diff = diff.loc[idx]
                unidade = edit_df.loc[idx, "unidade_padrao"]
                operadora = edit_df.loc[idx, "operadora_padrao"]
                
                tipo = "Faturamento Extra" if col.startswith("fat_") else "Recebimento Extra"
                mes = int(col.split("_")[1]) if col.startswith("fat_") else int(col.split("_")[2])
                
                new_id = int(lanc["id"].max() + 1) if not lanc.empty and "id" in lanc else 1
                if new_rows:
                    new_id = max(new_id, new_rows[-1]["id"] + 1)
                    
                new_rows.append({
                    "id": new_id,
                    "unidade_padrao": unidade,
                    "operadora_padrao": operadora,
                    "mes_referencia": mes,
                    "ano_referencia": year,
                    "tipo_lancamento": tipo,
                    "valor": float(val_diff),
                    "motivo": "Edição direta Consolidado",
                    "atualizado_por": "sistema",
                    "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            
            if new_rows:
                append_table("lancamentos_manuais", pd.DataFrame(new_rows))
                changed = True
                
    if changed:
        if "consolidado_editor" in st.session_state:
            del st.session_state["consolidado_editor"]
        st.toast("✅ Valores atualizados! Recalculando dashboard...")
        time.sleep(0.5)
        st.rerun()
'''

content += new_func

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("done")
