import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Adicionar funções
new_funcs = """
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
    f1, f2, f3 = st.columns([2, 1, 1])
    search = f1.text_input("Buscar", placeholder="Buscar operadora...", label_visibility="collapsed", key=f"{key_prefix}_search")
    
    opts_unidade = ["Todas"] + sorted(grid["unidade_origem"].unique().tolist())
    filter_unit = f2.selectbox("Filtrar Unidade", opts_unidade, key=f"{key_prefix}_funit", label_visibility="collapsed")
    
    filter_status = f3.selectbox("Status", ["Todos", "Pendente", "Mapeado"], key=f"{key_prefix}_fstatus", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = grid.copy()
    if search:
        q = search.lower()
        filtered = filtered[
            filtered["sigla_origem"].str.lower().str.contains(q, na=False) |
            filtered["nome_padrao"].str.lower().str.contains(q, na=False) |
            filtered["unidade_origem"].str.lower().str.contains(q, na=False)
        ]
    if filter_unit != "Todas":
        filtered = filtered[filtered["unidade_origem"] == filter_unit]
    if filter_status != "Todos":
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
"""

# Inserindo funções logo após render_depara_manager
code = code.replace("def render_depara_manager(", new_funcs + "\n\ndef render_depara_manager(")


# 2. Modificar UI das abas
old_ops_fat = """    with depara_ops_fat_tab:
        render_depara_manager(
            title="DE/PARA de Operadoras (Faturamento)",
            description="Padronize convênios vindos do faturamento.",
            mapping=depara_ops_fat,
            source_values=source_values_for_depara(fat, "operadora_original"),
            table_name="de_para_operadoras_fat",
            key_prefix="depara_ops_fat",
            search_placeholder="Buscar operadora...",
        )"""
new_ops_fat = """    with depara_ops_fat_tab:
        render_depara_operadoras_manager(
            title="DE/PARA de Operadoras (Faturamento)",
            description="Padronize convênios vindos do faturamento vinculados a cada Unidade.",
            mapping=depara_ops_fat,
            source_values=source_values_for_depara_operadoras(fat),
            table_name="de_para_operadoras_fat",
            key_prefix="depara_ops_fat",
        )"""

old_ops_cont = """    with depara_ops_cont_tab:
        render_depara_manager(
            title="DE/PARA de Operadoras (Recebimento)",
            description="Padronize convênios vindos da contabilidade.",
            mapping=depara_ops_cont,
            source_values=source_values_for_depara(cont, "operadora_original"),
            table_name="de_para_operadoras_cont",
            key_prefix="depara_ops_cont",
            search_placeholder="Buscar operadora...",
        )"""
new_ops_cont = """    with depara_ops_cont_tab:
        render_depara_operadoras_manager(
            title="DE/PARA de Operadoras (Recebimento)",
            description="Padronize convênios vindos da contabilidade vinculados a cada Unidade.",
            mapping=depara_ops_cont,
            source_values=source_values_for_depara_operadoras(cont),
            table_name="de_para_operadoras_cont",
            key_prefix="depara_ops_cont",
        )"""

code = code.replace(old_ops_fat, new_ops_fat)
code = code.replace(old_ops_cont, new_ops_cont)

# 3. Adicionar Filtros ao DE/PARA de Unidades também! (O usuário pediu no DE/PARA de unidades)
# Substituindo a search box simples na render_depara_manager
old_toolbar = """    st.markdown('<div class="depara-toolbar">', unsafe_allow_html=True)
    search = st.text_input("Buscar", placeholder=search_placeholder, label_visibility="collapsed", key=f"{key_prefix}_search")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = filter_depara_grid(grid, search)"""

new_toolbar = """    st.markdown('<div class="depara-toolbar">', unsafe_allow_html=True)
    f1, f2 = st.columns([3, 1])
    search = f1.text_input("Buscar", placeholder=search_placeholder, label_visibility="collapsed", key=f"{key_prefix}_search")
    filter_status = f2.selectbox("Status", ["Todos", "Pendente", "Mapeado"], key=f"{key_prefix}_fstatus", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = filter_depara_grid(grid, search)
    if filter_status != "Todos":
        filtered = filtered[filtered["status"] == filter_status]"""

code = code.replace(old_toolbar, new_toolbar)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)

print("SUCESSO UI")
