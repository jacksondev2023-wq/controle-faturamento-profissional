import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. source_values_for_depara
old_source_values = """def source_values_for_depara(fat: pd.DataFrame, cont: pd.DataFrame, column: str) -> set[str]:
    v_fat = set(fat[column].astype(str).unique()) if column in fat and not fat.empty else set()
    v_cont = set(cont[column].astype(str).unique()) if column in cont and not cont.empty else set()
    return {norm_text(v) for v in v_fat.union(v_cont) if str(v).strip() and str(v).lower() != "nan"}"""

new_source_values = """def source_values_for_depara(df: pd.DataFrame, column: str) -> set[str]:
    v = set(df[column].astype(str).unique()) if column in df and not df.empty else set()
    return {norm_text(val) for val in v if str(val).strip() and str(val).lower() != "nan"}"""

code = code.replace(old_source_values, new_source_values)

# 2. Inicialização
old_init = """depara = read_table("de_para_unidades")
if depara.empty:
    depara = DEFAULT_DEPARA.copy()
    write_table("de_para_unidades", depara)
depara_operadoras = read_table("de_para_operadoras")
if depara_operadoras.empty:
    depara_operadoras = DEFAULT_OPERADORA_DEPARA.copy()
    write_table("de_para_operadoras", depara_operadoras)"""

new_init = """depara_legado = read_table("de_para_unidades")
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
depara_operadoras = depara_ops_fat"""

code = code.replace(old_init, new_init)

# 3. Import Panels
old_import_fat = """        render_import_panel(
            title="Faturamento",
            subtitle="Formatos aceitos: .xlsx, .xls",
            file_key="file_fat",
            tipo="Faturamento IW",
            year=int(year),
            depara=depara,
            depara_operadoras=depara_operadoras,
        )"""
new_import_fat = """        render_import_panel(
            title="Faturamento",
            subtitle="Formatos aceitos: .xlsx, .xls",
            file_key="file_fat",
            tipo="Faturamento IW",
            year=int(year),
            depara=depara_fat,
            depara_operadoras=depara_ops_fat,
        )"""

old_import_cont = """        render_import_panel(
            title="Contabilidade / Recebimentos",
            subtitle="Formatos aceitos: .xlsx, .xls",
            file_key="file_cont",
            tipo="Contabilidade/Recebimentos",
            year=int(year),
            depara=depara,
            depara_operadoras=depara_operadoras,
        )"""
new_import_cont = """        render_import_panel(
            title="Contabilidade / Recebimentos",
            subtitle="Formatos aceitos: .xlsx, .xls",
            file_key="file_cont",
            tipo="Contabilidade/Recebimentos",
            year=int(year),
            depara=depara_cont,
            depara_operadoras=depara_ops_cont,
        )"""

code = code.replace(old_import_fat, new_import_fat)
code = code.replace(old_import_cont, new_import_cont)

ui_regex = r"depara_units_tab, depara_ops_tab = st\.tabs\(\[\"DE/PARA de Unidades\", \"DE/PARA de Operadoras\"\]\).*?Buscar operadora.*?,\n\s*\)"

new_ui = """    depara_units_fat_tab, depara_ops_fat_tab, depara_units_cont_tab, depara_ops_cont_tab = st.tabs([
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
        render_depara_manager(
            title="DE/PARA de Operadoras (Faturamento)",
            description="Padronize convênios vindos do faturamento.",
            mapping=depara_ops_fat,
            source_values=source_values_for_depara(fat, "operadora_original"),
            table_name="de_para_operadoras_fat",
            key_prefix="depara_ops_fat",
            search_placeholder="Buscar operadora...",
        )
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
        render_depara_manager(
            title="DE/PARA de Operadoras (Recebimento)",
            description="Padronize convênios vindos da contabilidade.",
            mapping=depara_ops_cont,
            source_values=source_values_for_depara(cont, "operadora_original"),
            table_name="de_para_operadoras_cont",
            key_prefix="depara_ops_cont",
            search_placeholder="Buscar operadora...",
        )"""

code = re.sub(ui_regex, new_ui, code, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)

print("SUCESSO")
