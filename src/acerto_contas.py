from __future__ import annotations

import re
import unicodedata

import pandas as pd

from src.etl import MONTHS, norm_text


DEFAULT_FISCAL_UNIT_ALIASES = {
    "RESIDENCIAL JOAO PESSOA": "HOSPITAL RESIDENCIAL - JP",
    "RESIDENCIAL JP": "HOSPITAL RESIDENCIAL - JP",
    "HM JP": "HOSPITAL RESIDENCIAL - JP",
    "RESIDENCIAL CG": "HOSPITAL RESIDENCIAL - CG",
    "LIFE HOME PE": "LIFE HOME CARE - PE",
    "LIFE PE": "LIFE HOME CARE - PE",
    "MILAGRES FORTALEZA": "MILAGRES HOME CARE - CE",
    "MILAGRES PARAIBA": "MILAGRES HOME CARE - JP",
    "MILAGRES MANAUS": "MILAGRES HOME CARE - AM",
    "NATAL HOME": "NATAL HOME CARE",
    "SAUDE BAHIA": "SAUDE BAHIA",
}


def _alias_key(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").upper())
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def _canonical_unit(target: str, known_units: dict[str, str]) -> str:
    target_key = _alias_key(target)
    if target_key in known_units:
        return known_units[target_key]
    for known_key, known_value in known_units.items():
        if target_key and (target_key in known_key or known_key in target_key):
            return known_value
    return target


def build_fiscal_unit_aliases(
    units: pd.Series,
    unit_mapping: pd.DataFrame | None = None,
) -> dict[str, str]:
    known_units = {
        _alias_key(unit): str(unit).strip()
        for unit in units.dropna().astype(str)
        if str(unit).strip()
    }
    aliases = dict(known_units)

    for alias, target in DEFAULT_FISCAL_UNIT_ALIASES.items():
        aliases[_alias_key(alias)] = _canonical_unit(target, known_units)

    if unit_mapping is not None and not unit_mapping.empty:
        mapping = unit_mapping.copy()
        for col in ["sigla_origem", "nome_padrao"]:
            if col not in mapping:
                mapping[col] = ""
        for _, row in mapping.iterrows():
            alias = _alias_key(row.get("sigla_origem", ""))
            target = _canonical_unit(str(row.get("nome_padrao", "") or ""), known_units)
            if alias and target:
                aliases[alias] = target
    return aliases


def resolve_fiscal_unit(observation: str, aliases: dict[str, str]) -> str:
    normalized = _alias_key(observation)
    matches = [
        (len(alias), target)
        for alias, target in aliases.items()
        if len(alias) >= 5 and alias in normalized
    ]
    return max(matches, default=(0, ""))[1]


def infer_settlement_direction(
    current_unit: str,
    observation: str,
    aliases: dict[str, str],
) -> tuple[str, str, str, str]:
    normalized = norm_text(observation)
    target_unit = resolve_fiscal_unit(observation, aliases)

    if "FATURADO NA FILIAL DE ATENDIMENTO" in normalized or "FATURADO NA FILIAL" in normalized:
        return current_unit, target_unit, "Faturado em outra filial", target_unit

    if "FILIAL FISCAL" in normalized:
        return target_unit, current_unit, "Recebido em filial fiscal diferente", target_unit

    if "ACERTO DE CONTAS" in normalized:
        return "", current_unit, "Acerto informado sem filial fiscal", ""

    return "", "", "", ""


def build_automatic_settlements(
    consolidado: pd.DataFrame,
    fat_months: list[int],
    year: int,
    unit_mapping: pd.DataFrame | None = None,
) -> pd.DataFrame:
    columns = [
        "competencia",
        "mes",
        "ano",
        "filial_fiscal_pagadora",
        "filial_faturadora_recebedora",
        "operadora",
        "valor_acerto",
        "status",
        "regra",
        "observacao_origem",
    ]
    if consolidado is None or consolidado.empty:
        return pd.DataFrame(columns=columns)

    work = consolidado.copy()
    aliases = build_fiscal_unit_aliases(work["unidade_padrao"], unit_mapping)
    observation_col = (
        "observacao_fiscal"
        if "observacao_fiscal" in work
        else "observacoes_consolidadas"
    )
    if observation_col not in work:
        return pd.DataFrame(columns=columns)

    rows = []
    for _, row in work.iterrows():
        observation = str(row.get(observation_col, "") or "").strip()
        normalized = norm_text(observation)
        if not observation or not any(
            marker in normalized
            for marker in ["FILIAL FISCAL", "FATURADO NA FILIAL", "ACERTO DE CONTAS"]
        ):
            continue

        current_unit = str(row.get("unidade_padrao", "") or "").strip()
        payer, receiver, rule, resolved_target = infer_settlement_direction(
            current_unit,
            observation,
            aliases,
        )

        for month in fat_months:
            value = pd.to_numeric(
                pd.Series([row.get(f"fat_{int(month)}", 0)]),
                errors="coerce",
            ).fillna(0).iloc[0]
            value = float(value)

            if not resolved_target:
                status = "Filial fiscal não identificada"
            elif not payer or not receiver or payer == receiver:
                status = "Relação de filiais inválida"
            elif abs(value) < 0.005:
                status = "Sem faturamento na competência"
            else:
                status = "Pronto"

            rows.append({
                "competencia": f"{MONTHS.get(int(month), month)}/{int(year)}",
                "mes": int(month),
                "ano": int(year),
                "filial_fiscal_pagadora": payer,
                "filial_faturadora_recebedora": receiver,
                "operadora": str(row.get("operadora_padrao", "") or "").strip(),
                "valor_acerto": value,
                "status": status,
                "regra": rule,
                "observacao_origem": observation,
            })

    result = pd.DataFrame(rows, columns=columns)
    if result.empty:
        return result

    ready = result[result["status"] == "Pronto"].copy()
    pending = result[result["status"] != "Pronto"].copy()
    if not ready.empty:
        ready = (
            ready.groupby(
                [
                    "competencia",
                    "mes",
                    "ano",
                    "filial_fiscal_pagadora",
                    "filial_faturadora_recebedora",
                    "operadora",
                    "status",
                    "regra",
                ],
                as_index=False,
                dropna=False,
            )
            .agg(
                valor_acerto=("valor_acerto", "sum"),
                observacao_origem=(
                    "observacao_origem",
                    lambda values: " | ".join(dict.fromkeys(str(value) for value in values if str(value).strip())),
                ),
            )
        )
    result = pd.concat([ready, pending], ignore_index=True)
    return result.sort_values(
        [
            "status",
            "mes",
            "filial_fiscal_pagadora",
            "filial_faturadora_recebedora",
            "operadora",
        ],
        kind="stable",
    ).reset_index(drop=True)


def build_branch_net_summary(settlements: pd.DataFrame) -> pd.DataFrame:
    columns = ["filial", "total_a_pagar", "total_a_receber", "saldo_liquido"]
    if settlements is None or settlements.empty:
        return pd.DataFrame(columns=columns)

    ready = settlements[settlements["status"] == "Pronto"].copy()
    if ready.empty:
        return pd.DataFrame(columns=columns)

    outgoing = (
        ready.groupby("filial_fiscal_pagadora", as_index=False)["valor_acerto"]
        .sum()
        .rename(columns={
            "filial_fiscal_pagadora": "filial",
            "valor_acerto": "total_a_pagar",
        })
    )
    incoming = (
        ready.groupby("filial_faturadora_recebedora", as_index=False)["valor_acerto"]
        .sum()
        .rename(columns={
            "filial_faturadora_recebedora": "filial",
            "valor_acerto": "total_a_receber",
        })
    )
    summary = outgoing.merge(incoming, on="filial", how="outer").fillna(0)
    summary["saldo_liquido"] = summary["total_a_receber"] - summary["total_a_pagar"]
    return summary.sort_values("saldo_liquido", ascending=False).reset_index(drop=True)


def format_settlements_for_copy(settlements: pd.DataFrame) -> str:
    if settlements is None or settlements.empty:
        return "Nenhum acerto automático identificado."

    ready = settlements[settlements["status"] == "Pronto"].copy()
    if ready.empty:
        return "Nenhum acerto pronto para envio."

    def money(value) -> str:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    lines = ["ACERTO DE CONTAS"]
    grouped = ready.groupby(
        ["competencia", "filial_fiscal_pagadora", "filial_faturadora_recebedora"],
        sort=False,
        dropna=False,
    )
    for (competencia, payer, receiver), group in grouped:
        lines.extend([
            "",
            (
                f"{competencia} | Filial fiscal {payer} deve repassar para a filial "
                f"de atendimento/faturamento {receiver}"
            ),
        ])
        for _, row in group.sort_values("operadora").iterrows():
            lines.append(f"- {row['operadora']}: {money(row['valor_acerto'])}")
        lines.append(f"Total: {money(group['valor_acerto'].sum())}")
    return "\n".join(lines)
