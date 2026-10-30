from __future__ import annotations

import re
import csv
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz


COMMON_WORDS = {
    "CON",
    "DEL",
    "FINCA",
    "HACIENDO",
    "LOTE",
    "MANUAL",
    "PARA",
    "POR",
    "TAREA",
    "TRABAJANDO",
    "TRABAJO",
}


@dataclass(frozen=True)
class Match:
    key: str
    label: str
    score: float
    metadata: dict[str, object]
    evidence: int = 0


def normalize(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).strip().upper()
    return re.sub(r"\s+", " ", text)


def score_query(query: str, candidate: str) -> float:
    query_n = normalize(query)
    candidate_n = normalize(candidate)
    if not query_n or not candidate_n:
        return 0.0
    if query_n == candidate_n:
        return 100.0
    if query_n in candidate_n:
        return 96.0
    if len(candidate_n) >= 4 and f" {candidate_n} " in f" {query_n} ":
        return 96.0
    query_tokens = query_n.split()
    candidate_tokens = candidate_n.split()
    if all(any(token in value for value in candidate_tokens) for token in query_tokens):
        return 93.0
    significant_overlap = {
        token
        for token in candidate_tokens
        if len(token) >= 4 and token not in COMMON_WORDS and token in query_tokens
    }
    if significant_overlap:
        return min(99.0, 90.0 + len(significant_overlap) * 3.0)
    if len(query_tokens) > 4:
        return 0.0
    return max(
        float(fuzz.WRatio(query_n, candidate_n)),
        float(fuzz.token_set_ratio(query_n, candidate_n)),
    )


def rank_matches(
    query: str,
    records: list[dict[str, object]],
    *,
    key_field: str,
    label_fields: list[str],
    aliases: list[str] | None = None,
    search_fields: list[str] | None = None,
    code_fields: list[str] | None = None,
    code_hints: list[str] | None = None,
    limit: int = 5,
    minimum: float = 55.0,
) -> list[Match]:
    ranked: list[Match] = []
    seen: set[tuple[str, str]] = set()
    aliases = aliases or []
    code_fields = code_fields or []
    query_tokens = normalize(query).split()
    hinted_codes: set[str] = set()
    hints = {normalize(hint) for hint in (code_hints or [])}
    for position, token in enumerate(query_tokens):
        if token not in hints:
            continue
        hinted_codes.update(
            value
            for value in query_tokens[position + 1 : position + 4]
            if any(character.isdigit() for character in value)
        )
    for record in records:
        fields = search_fields or [*label_fields, *aliases]
        values = [record.get(field, "") for field in fields]
        scores = [score_query(query, value) for value in values]
        for field in code_fields:
            code = normalize(record.get(field, ""))
            if not code:
                continue
            if code in hinted_codes:
                scores.append(98.0)
            elif len(code) >= 3 and code in query_tokens:
                scores.append(97.0)
        score = max(scores, default=0.0)
        strong_fields = sum(item >= 90 for item in scores)
        if strong_fields > 1:
            score = min(100.0, score + (strong_fields - 1) * 2.0)
        if score < minimum:
            continue
        label = " · ".join(str(record.get(field, "")) for field in label_fields if record.get(field) not in (None, ""))
        identity = (str(record.get(key_field, "")), label)
        if identity in seen:
            continue
        seen.add(identity)
        ranked.append(
            Match(
                key=str(record.get(key_field, "")),
                label=label,
                score=round(score, 1),
                metadata=record,
                evidence=strong_fields,
            )
        )
    ranked.sort(key=lambda item: (-item.score, -item.evidence, item.label))
    return ranked[:limit]


def _clean_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def equal_distribution(total: float, count: int, *, integers: bool) -> list[float]:
    if count <= 0:
        return []
    if integers:
        total_int = int(round(total))
        base, remainder = divmod(total_int, count)
        return [float(base + (1 if index < remainder else 0)) for index in range(count)]
    base = round(float(total) / count, 4)
    result = [base] * count
    result[-1] = round(float(total) - sum(result[:-1]), 4)
    return result


def redistribute_rows(rows: list[dict], total: float, *, integers: bool) -> list[dict]:
    result = [dict(row) for row in rows]
    receivers = []
    fixed_total = 0.0
    for index, row in enumerate(result):
        attendance = str(row.get("Estado", "Presente"))
        if attendance == "Ausente":
            row["Cantidad"] = 0.0
        elif attendance == "Cantidad fija":
            fixed_total += float(row.get("Cantidad", 0) or 0)
        else:
            receivers.append(index)
    available = float(total) - fixed_total
    if available < 0:
        raise ValueError("Las cantidades fijas superan la cantidad parcial.")
    distributed = equal_distribution(available, len(receivers), integers=integers)
    for index, amount in zip(receivers, distributed):
        result[index]["Cantidad"] = amount
    return result


def _read_txt_table(
    path: Path,
    *,
    expected_columns: list[str],
    overflow_column: int | None = None,
) -> pd.DataFrame:
    """Read the ANSI CSV exports, repairing unquoted commas in text fields."""
    rows: list[list[str]] = []
    with path.open("r", encoding="cp1252", newline="") as source:
        reader = csv.reader(source)
        header = next(reader, None)
        if header is None:
            return pd.DataFrame(columns=expected_columns)
        if header != expected_columns:
            raise ValueError(
                f"Columnas inesperadas en {path.name}. "
                f"Esperadas: {expected_columns}. Encontradas: {header}."
            )
        width = len(expected_columns)
        for line_number, row in enumerate(reader, start=2):
            if len(row) > width and overflow_column is not None:
                trailing = width - overflow_column - 1
                tail = row[-trailing:] if trailing else []
                row = [*row[:overflow_column], ",".join(row[overflow_column : len(row) - trailing]), *tail]
            if len(row) != width:
                raise ValueError(
                    f"Fila {line_number} inválida en {path.name}: "
                    f"se esperaban {width} campos y se encontraron {len(row)}."
                )
            rows.append(row)
    return pd.DataFrame(rows, columns=expected_columns, dtype="string")


def load_personal(path: Path) -> list[dict[str, object]]:
    frame = _read_txt_table(
        path,
        expected_columns=["LEGAJO", "EMPLEADO", "FECHA ALTA", "ID_CC", "CENTRO COSTO"],
    )
    return _clean_records(frame)


def load_maquinaria(path: Path) -> list[dict[str, object]]:
    frame = _read_txt_table(
        path,
        expected_columns=[
            "ID_Equipo",
            "Equipo",
            "Grupo Operativo",
            "Fecha_Aquisición",
            "Marca",
            "Modelo",
            "Patente",
        ],
        overflow_column=5,
    )
    frame["ULTIMOS_4"] = frame["Equipo"].fillna("").str[-4:]
    return _clean_records(frame)


def load_operaciones(path: Path) -> list[dict[str, object]]:
    base_columns = [
        "ID_Operacion",
        "Operación",
        "Unidad_Medida",
        "Tipo_Tarea",
        "Descripcion_Unidad_Medida",
        "Grupo_Op_Maq",
    ]
    with path.open("r", encoding="cp1252", newline="") as source:
        frame = pd.read_csv(source, sep=";", dtype="string", keep_default_na=False)
    frame.columns = [str(column).lstrip("\ufeff") for column in frame.columns]
    valid_columns = (base_columns, [*base_columns, "Insumos"])
    if list(frame.columns) not in valid_columns:
        raise ValueError(
            f"Columnas inesperadas en {path.name}. "
            f"Esperadas: {valid_columns[-1]}. Encontradas: {list(frame.columns)}."
        )
    if "Insumos" not in frame.columns:
        frame["Insumos"] = ""
    return _clean_records(frame)


def load_lotes(path: Path) -> list[dict[str, object]]:
    frame = _read_txt_table(
        path,
        expected_columns=[
            "ID_UNICO",
            "ID_Finca",
            "FINCA",
            "CULTIVO",
            "ID_Lote",
            "LOTE",
            "VARIEDAD",
            "AREA B",
            "AREA N",
            "SURCOS",
            "Año Plantacion",
            "Dist Plantacion",
        ],
        overflow_column=6,
    )
    return _clean_records(frame)


def load_insumos(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open("r", encoding="cp1252", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        for source_row in reader:
            row = {normalize(str(key).lstrip("\ufeff")): value for key, value in source_row.items() if key}
            code = str(row.get("ID") or "").strip()
            description = str(row.get("INSUMO") or "").strip()
            if not code or not description:
                continue
            unit = str(row.get("UNIDAD MEDIDA") or row.get("UNIDAD DE MEDIDA") or row.get("UNIDAD") or "").strip().upper()
            if not unit and "UREA" in normalize(description):
                unit = "TN"
            records.append(
                {
                    "CODIGO": code,
                    "DESCRIPCION": description,
                    "UNIDAD": unit,
                    "GRUPO_CODIGO": "",
                    "GRUPO": "",
                    "MATERIAL": code,
                }
            )
    return records


def load_all_sources(data_dir: Path) -> dict[str, list[dict[str, object]]]:
    txt_dir = data_dir / "txt"
    warnings: list[str] = []
    try:
        inputs = load_insumos(txt_dir / "Insumos.csv")
    except PermissionError:
        inputs = []
        warnings.append(
            "Windows no permite leer Insumos.csv. La aplicación continuará sin catálogo de insumos; "
            "personal, tareas, lotes y maquinaria siguen disponibles."
        )
    return {
        "personal": load_personal(txt_dir / "Personal.txt"),
        "maquinaria": load_maquinaria(txt_dir / "Maquinaria.txt"),
        "operaciones": load_operaciones(
            txt_dir / "Operaciones-Maquinaria-Insumos.csv"
            if (txt_dir / "Operaciones-Maquinaria-Insumos.csv").exists()
            else txt_dir / "Operaciones-Maquinaria.csv"
        ),
        "lotes": load_lotes(txt_dir / "Inventario_2026.txt"),
        "insumos": inputs,
        "_warnings": warnings,
    }


def operation_machine_groups(operation: dict[str, object] | None) -> list[str]:
    if not operation:
        return []
    raw_groups = str(operation.get("Grupo_Op_Maq") or "")
    return [normalize(group.strip()) for group in raw_groups.split(",") if group.strip()]


def operation_requires_inputs(operation: dict[str, object] | None) -> bool:
    if not operation:
        return False
    return bool(str(operation.get("Insumos") or "").strip())


def filter_machines_for_operation(
    operation: dict[str, object] | None,
    machines: list[dict[str, object]],
) -> list[dict[str, object]]:
    if normalize((operation or {}).get("Tipo_Tarea")) == "MANUAL":
        return []
    groups = set(operation_machine_groups(operation))
    if not groups:
        return list(machines)
    filtered = []
    for machine in machines:
        machine_group = normalize(str(machine.get("Grupo Operativo") or ""))
        if any(
            required_group == machine_group
            or required_group in machine_group
            or machine_group in required_group
            for required_group in groups
        ):
            filtered.append(machine)
    return filtered


def find_candidates(text: str, masters: dict[str, list[dict[str, object]]]) -> dict[str, list[Match]]:
    return {
        "Personal": rank_matches(
            text,
            masters["personal"],
            key_field="LEGAJO",
            label_fields=["EMPLEADO", "LEGAJO"],
            search_fields=["EMPLEADO", "LEGAJO"],
            code_fields=["LEGAJO"],
            code_hints=["LEGAJO", "EMPLEADO"],
            limit=5,
            minimum=90,
        ),
        "Maquinaria": rank_matches(
            text,
            masters["maquinaria"],
            key_field="Equipo",
            label_fields=["ID_Equipo", "Grupo Operativo", "Marca", "Modelo"],
            aliases=["Equipo", "ULTIMOS_4", "Patente"],
            search_fields=[
                "ID_Equipo",
                "Grupo Operativo",
                "Marca",
                "Modelo",
                "Equipo",
                "ULTIMOS_4",
                "Patente",
            ],
            code_fields=["ID_Equipo", "Equipo", "ULTIMOS_4"],
            code_hints=["MAQUINA", "MAQUINARIA", "EQUIPO"],
            limit=5,
            minimum=90,
        ),
        "Fincas y lotes": rank_matches(
            text,
            masters["lotes"],
            key_field="ID_UNICO",
            label_fields=["FINCA", "LOTE", "CULTIVO", "VARIEDAD"],
            aliases=["ID_Finca", "ID_Lote"],
            search_fields=["FINCA", "LOTE", "ID_Finca", "ID_Lote"],
            code_fields=["ID_UNICO", "ID_Finca", "ID_Lote"],
            code_hints=["FINCA", "LOTE"],
            limit=5,
            minimum=90,
        ),
        "Operaciones": rank_matches(
            text,
            masters["operaciones"],
            key_field="ID_Operacion",
            label_fields=["Operación", "ID_Operacion", "Unidad_Medida", "Tipo_Tarea"],
            search_fields=["Operación", "ID_Operacion"],
            code_fields=["ID_Operacion"],
            code_hints=["TAREA", "OPERACION"],
            limit=5,
            minimum=90,
        ),
        "Insumos": rank_matches(
            text,
            masters["insumos"],
            key_field="CODIGO",
            label_fields=["DESCRIPCION", "CODIGO", "UNIDAD", "GRUPO"],
            aliases=["MATERIAL"],
            search_fields=["DESCRIPCION", "CODIGO", "MATERIAL"],
            code_fields=["CODIGO", "MATERIAL"],
            code_hints=["INSUMO", "PRODUCTO"],
            limit=5,
            minimum=90,
        ),
    }
