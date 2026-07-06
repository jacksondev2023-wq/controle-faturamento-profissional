import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Modificar render_depara_manager (Unidades)
old_toolbar_manager = """    st.markdown('<div class="depara-toolbar">', unsafe_allow_html=True)
    f1, f2 = st.columns([3, 1])
    search = f1.text_input("Buscar", placeholder=search_placeholder, label_visibility="collapsed", key=f"{key_prefix}_search")
    filter_status = f2.selectbox("Status", ["Todos", "Pendente", "Mapeado"], key=f"{key_prefix}_fstatus", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = filter_depara_grid(grid, search)
    if filter_status != "Todos":
        filtered = filtered[filtered["status"] == filter_status]"""

new_toolbar_manager = """    st.markdown('<div class="depara-toolbar">', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([2, 1, 1])
    search = f1.text_input("Buscar", placeholder=search_placeholder, label_visibility="collapsed", key=f"{key_prefix}_search")
    filter_em_uso = f2.selectbox("Em Uso", ["Todos (Em uso)", "Sim", "Não"], key=f"{key_prefix}_fuso", label_visibility="collapsed")
    filter_status = f3.selectbox("Status", ["Todos (Status)", "Pendente", "Mapeado"], key=f"{key_prefix}_fstatus", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = filter_depara_grid(grid, search)
    if filter_em_uso != "Todos (Em uso)":
        filtered = filtered[filtered["em_uso"] == filter_em_uso]
    if filter_status != "Todos (Status)":
        filtered = filtered[filtered["status"] == filter_status]"""

code = code.replace(old_toolbar_manager, new_toolbar_manager)

# 2. Modificar render_depara_operadoras_manager
old_toolbar_ops = """    st.markdown('<div class="depara-toolbar">', unsafe_allow_html=True)
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
        filtered = filtered[filtered["status"] == filter_status]"""

new_toolbar_ops = """    st.markdown('<div class="depara-toolbar">', unsafe_allow_html=True)
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
        filtered = filtered[filtered["status"] == filter_status]"""

code = code.replace(old_toolbar_ops, new_toolbar_ops)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)

print("SUCESSO")
