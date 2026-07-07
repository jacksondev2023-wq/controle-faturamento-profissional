import streamlit as st


COMPONENT_HTML = """
<div class="consolidado-table-host"></div>
"""


COMPONENT_CSS = r"""
:host {
    display: block;
    width: 100%;
    color: #11131A;
    font-family: var(--st-font, "Inter", Arial, sans-serif);
}

* {
    box-sizing: border-box;
}

.table-wrap {
    width: 100%;
    overflow-x: auto;
    border: 1px solid #BFC5D2;
    border-radius: 7px;
    background: #FFFFFF;
}

table {
    width: 100%;
    min-width: 1180px;
    table-layout: fixed;
    border-collapse: collapse;
}

th,
td {
    padding: 4px 6px;
    border-right: 1px solid #E3E6ED;
    font-size: 0.86rem;
    line-height: 1.2;
    vertical-align: middle;
}

th {
    height: 32px;
    background: #00245D;
    color: #FFFFFF;
    font-weight: 800;
    text-align: center;
    text-transform: uppercase;
}

th:first-child,
td:first-child {
    width: 255px;
}

th.money-col,
td.money-col {
    width: 134px;
}

th.fat-col {
    background: #FFC000;
    color: #000000;
}

th.obs-col {
    width: 390px;
    background: #244392;
    color: #FFFFFF;
}

td.num {
    text-align: right;
    white-space: nowrap;
}

td.obs-col {
    width: 390px;
    padding: 0;
    background: #FFF2CC;
    color: #000000;
    vertical-align: top;
}

td.fat-month-4 {
    background: #D9D9D9;
}

tr.unit-row td {
    background: #DDEBF7;
    color: #001945;
    border-top: 2px solid #2F75B5;
    border-bottom: 1px solid #2F75B5;
    font-weight: 900;
}

tr.detail-row td {
    border-bottom: 1px solid #2FA8E1;
}

tr.detail-row td:first-child {
    color: #001945;
    font-weight: 500;
}

tr.signal-verde td {
    background: #F0FFF5;
}

tr.signal-amarelo td {
    background: #FFF8E1;
}

tr.signal-vermelho td {
    background: #FFF1F1;
}

tr.signal-verde td:first-child {
    background: #00A651;
    color: #FFFFFF;
    font-weight: 900;
}

tr.signal-amarelo td:first-child {
    background: #FFC000;
    color: #11131A;
    font-weight: 900;
}

tr.signal-vermelho td:first-child {
    background: #FF0000;
    color: #FFFFFF;
    font-weight: 900;
}

tr.unit-signal-verde td:first-child {
    box-shadow: inset 5px 0 0 #00A651;
}

tr.unit-signal-amarelo td:first-child {
    box-shadow: inset 5px 0 0 #FFC000;
}

tr.unit-signal-vermelho td:first-child {
    box-shadow: inset 5px 0 0 #FF0000;
}

.line-cell {
    min-height: 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}

.line-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.signal-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex: 0 0 auto;
}

.signal-dot {
    width: 13px;
    height: 13px;
    display: inline-block;
    padding: 0;
    border-radius: 999px;
    border: 1px solid #8A91A1;
    background: #FFFFFF;
    cursor: pointer;
    opacity: 0.58;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.65);
}

.signal-dot:hover,
.signal-dot:focus-visible {
    opacity: 1;
    transform: scale(1.08);
}

.signal-dot.active {
    opacity: 1;
    outline: 2px solid #001F4E;
    outline-offset: 1px;
}

.signal-dot.none {
    background: #FFFFFF;
}

.signal-dot.verde {
    background: #00A651;
    border-color: #007F3E;
}

.signal-dot.amarelo {
    background: #FFC000;
    border-color: #B98900;
}

.signal-dot.vermelho {
    background: #FF0000;
    border-color: #B00000;
}

.observation-wrap {
    min-height: 100%;
}

.observation-editor {
    width: 100%;
    min-height: 30px;
    padding: 6px 8px;
    color: #000000;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    cursor: text;
    outline: none;
}

.observation-editor:hover {
    box-shadow: inset 0 0 0 1px #C79B17;
}

.observation-editor:focus {
    background: #FFFFFF;
    box-shadow: inset 0 0 0 2px #002E7A;
}

.manual-note {
    padding: 5px 8px 7px;
    border-top: 1px dashed #D6B653;
    color: #5F4A00;
    font-size: 0.76rem;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
"""


COMPONENT_JS = r"""
export default function(component) {
    const { data, parentElement, setTriggerValue } = component;
    const host = parentElement.querySelector(".consolidado-table-host");
    if (!host) return;

    host.replaceChildren();

    const wrapper = document.createElement("div");
    wrapper.className = "table-wrap";
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");

    const columns = Array.isArray(data?.columns) ? data.columns : [];
    const rows = Array.isArray(data?.rows) ? data.rows : [];

    function applyColumnClasses(element, column) {
        if (column.kind === "money") element.classList.add("money-col");
        if (column.kind === "fat") element.classList.add("money-col", "fat-col");
        if (column.kind === "observation") element.classList.add("obs-col");
        if (column.month === 4 && column.kind === "fat") element.classList.add("fat-month-4");
    }

    columns.forEach((column) => {
        const th = document.createElement("th");
        th.textContent = column.label || "";
        applyColumnClasses(th, column);
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    function setRowSignal(tr, signal) {
        ["verde", "amarelo", "vermelho"].forEach((value) => {
            tr.classList.remove(`signal-${value}`);
        });
        if (signal) tr.classList.add(`signal-${signal}`);
    }

    function sendAction(action) {
        setTriggerValue("action", {
            ...action,
            nonce: `${Date.now()}-${Math.random()}`,
        });
    }

    rows.forEach((row) => {
        const tr = document.createElement("tr");
        const isDetail = row.type === "detail";
        tr.classList.add(isDetail ? "detail-row" : "unit-row");

        if (isDetail) {
            setRowSignal(tr, row.signal || "");
        } else if (row.signal) {
            tr.classList.add(`unit-signal-${row.signal}`);
        }

        columns.forEach((column) => {
            const td = document.createElement("td");
            applyColumnClasses(td, column);

            if (column.kind === "money") td.classList.add("num");
            if (column.kind === "fat") td.classList.add("num");

            if (column.key === "linha_label") {
                const lineCell = document.createElement("div");
                lineCell.className = "line-cell";

                const label = document.createElement("span");
                label.className = "line-label";
                label.textContent = row.label || "";
                label.title = row.label || "";
                lineCell.appendChild(label);

                if (isDetail) {
                    const actions = document.createElement("span");
                    actions.className = "signal-actions";
                    [
                        { value: "", className: "none", label: "Sem marcador" },
                        { value: "verde", className: "verde", label: "Verde" },
                        { value: "amarelo", className: "amarelo", label: "Amarelo" },
                        { value: "vermelho", className: "vermelho", label: "Vermelho" },
                    ].forEach((option) => {
                        const button = document.createElement("button");
                        button.type = "button";
                        button.className = `signal-dot ${option.className}`;
                        if ((row.signal || "") === option.value) button.classList.add("active");
                        button.title = option.label;
                        button.setAttribute("aria-label", option.label);
                        button.onclick = (event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            row.signal = option.value;
                            setRowSignal(tr, option.value);
                            actions.querySelectorAll(".signal-dot").forEach((dot) => dot.classList.remove("active"));
                            button.classList.add("active");
                            sendAction({
                                type: "signal",
                                unidade: row.unidade,
                                operadora: row.operadora,
                                value: option.value,
                            });
                        };
                        actions.appendChild(button);
                    });
                    lineCell.appendChild(actions);
                }

                td.appendChild(lineCell);
            } else if (column.kind === "observation" && isDetail) {
                const observationWrap = document.createElement("div");
                observationWrap.className = "observation-wrap";

                const editor = document.createElement("div");
                editor.className = "observation-editor";
                editor.contentEditable = "true";
                editor.spellcheck = true;
                editor.setAttribute("role", "textbox");
                editor.setAttribute("aria-label", "Observacao");
                editor.textContent = row.observation || "";
                editor.dataset.original = row.observation || "";

                editor.addEventListener("keydown", (event) => {
                    if (event.key === "Escape") {
                        editor.textContent = editor.dataset.original || "";
                        editor.blur();
                    } else if (event.key === "Enter" && event.ctrlKey) {
                        event.preventDefault();
                        editor.blur();
                    }
                });

                editor.addEventListener("blur", () => {
                    const nextValue = editor.innerText.replace(/\u00a0/g, " ").trim();
                    const previousValue = editor.dataset.original || "";
                    if (nextValue === previousValue) return;
                    editor.dataset.original = nextValue;
                    sendAction({
                        type: "observation",
                        unidade: row.unidade,
                        operadora: row.operadora,
                        value: nextValue,
                    });
                });

                observationWrap.appendChild(editor);

                if (row.manualComment) {
                    const manual = document.createElement("div");
                    manual.className = "manual-note";
                    manual.textContent = `Manual: ${row.manualComment}`;
                    observationWrap.appendChild(manual);
                }

                td.appendChild(observationWrap);
            } else if ((column.kind === "money" || column.kind === "fat") && isDetail) {
                const rawValue = row.values?.[column.key] || "";
                const display = document.createElement("span");
                display.className = "editable-value";
                display.textContent = rawValue;
                display.title = "Clique para editar";
                display.style.cursor = "pointer";
                display.style.display = "block";
                display.style.width = "100%";

                display.addEventListener("click", () => {
                    const input = document.createElement("input");
                    input.type = "text";
                    input.className = "inline-edit-input";
                    input.value = rawValue.replace(/R\$\s?/g, "").replace(/\./g, "").replace(",", ".");
                    input.style.width = "100%";
                    input.style.border = "2px solid #002E7A";
                    input.style.borderRadius = "3px";
                    input.style.padding = "2px 4px";
                    input.style.fontSize = "0.86rem";
                    input.style.textAlign = "right";
                    input.style.outline = "none";
                    input.style.background = "#FFFFFF";

                    td.replaceChildren(input);
                    input.focus();
                    input.select();

                    function commitEdit() {
                        const newVal = input.value.trim();
                        const numVal = parseFloat(newVal.replace(/R\$\s?/g, "").replace(/\./g, "").replace(",", ".") || "0");
                        const formatted = isNaN(numVal) || Math.abs(numVal) < 0.005
                            ? ""
                            : "R$ " + numVal.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                        display.textContent = formatted;
                        td.replaceChildren(display);
                        sendAction({
                            type: "value_edit",
                            unidade: row.unidade,
                            operadora: row.operadora,
                            column: column.key,
                            value: String(numVal),
                        });
                    }

                    input.addEventListener("blur", commitEdit);
                    input.addEventListener("keydown", (e) => {
                        if (e.key === "Enter") { e.preventDefault(); input.blur(); }
                        if (e.key === "Escape") { td.replaceChildren(display); }
                    });
                });

                td.appendChild(display);
            } else {
                td.textContent = row.values?.[column.key] || "";
            }

            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrapper.appendChild(table);
    host.appendChild(wrapper);
}
"""


consolidado_inline_table = st.components.v2.component(
    "consolidado_inline_table",
    html=COMPONENT_HTML,
    css=COMPONENT_CSS,
    js=COMPONENT_JS,
)
