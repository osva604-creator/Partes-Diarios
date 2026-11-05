"""Validate V1.1 master catalogs and build an idempotent SQL import plan.

This tool never opens Personal.csv and writes the generated SQL under the
ignored supabase/.temp directory. It prints counts only, never catalog rows.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import unicodedata
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


DEFAULT_ZIP = Path(r"C:\Users\dmoya\Documents\GitHub\Asistente Parte Diario\asistente parte diario V1.1\Asistente Parte Diario.zip")
DEFAULT_BACKUP = Path("supabase/.temp/pwa_v11_catalog_backup_20261105.json")
DEFAULT_OUTPUT = Path("supabase/.temp/pwa_v11_catalog_import.sql")
SOURCE_PREFIX = "Asistente Parte Diario/datos_fuente/base_datos/"


def canonical(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def normalized_id(value: object) -> str:
    text = str(value or "").strip()
    return str(int(text)) if text.isdigit() else text


def source_value(row: dict[str, str], *names: str) -> str:
    values = {canonical(key): (value or "").strip() for key, value in row.items() if key}
    for name in names:
        value = values.get(canonical(name), "")
        if value:
            return value
    return ""


def read_csv(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    path = SOURCE_PREFIX + name
    try:
        raw = archive.read(path)
    except KeyError as exc:
        raise ValueError(f"Falta el archivo fuente requerido: {name}") from exc
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(encoding), newline=""), delimiter=";"))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo decodificar {name}")


def unique_by(rows: list[dict[str, str]], key_fields: tuple[str, ...], label: str) -> dict[tuple[str, ...], dict[str, str]]:
    found: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(source_value(row, field) for field in key_fields)
        if any(not part for part in key):
            raise ValueError(f"Hay claves vacías en {label}")
        if key in found and found[key] != row:
            raise ValueError(f"Hay claves duplicadas con contenido distinto en {label}")
        found[key] = row
    return found


def number(value: str, field: str, integer: bool = False) -> int | str | None:
    value = (value or "").strip().replace(" ", "")
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    else:
        value = value.replace(",", ".")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"No se pudo convertir un campo numerico ({field})") from exc
    if integer:
        if parsed != parsed.to_integral_value():
            raise ValueError(f"Se esperaba un entero en {field}")
        return int(parsed)
    return format(parsed, "f")


def date_value(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value[:10], fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Hay una fecha de maquinaria en un formato no reconocido")


def jsonb(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def sql_literal_json(value: Any) -> str:
    encoded = jsonb(value)
    delimiter = "$pwa_v11$"
    while delimiter in encoded:
        delimiter = "$pwa_v11_x$" if delimiter == "$pwa_v11$" else delimiter + "x"
    return f"{delimiter}{encoded}{delimiter}::jsonb"


def build_plan(zip_path: Path, backup_path: Path) -> tuple[dict[str, Any], dict[str, int]]:
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    with zipfile.ZipFile(zip_path) as archive:
        centers_src = read_csv(archive, "CentroCosto.csv")
        locations_src = read_csv(archive, "CentroCosto_Finca_Lote.csv")
        center_groups_src = read_csv(archive, "CentroCosto_GrupoOperacion.csv")
        group_operations_src = read_csv(archive, "GrupoOperacion_Operacion.csv")
        operations_src = read_csv(archive, "Operacion.csv")
        advance_src = read_csv(archive, "Operacion_AvanceDosis.csv")
        operation_machines_src = read_csv(archive, "Operacion_Maquinaria.csv")
        operation_inputs_src = read_csv(archive, "Operacion_Insumos.csv")
        machines_src = read_csv(archive, "Maquinaria.csv")
        inputs_src = read_csv(archive, "Insumos.csv")
        inventory_src = read_csv(archive, "Inventario_2026.csv")

    centers_by_id = unique_by(centers_src, ("ID_Centro_costo",), "CentroCosto.csv")
    locations_by_id = unique_by(locations_src, ("ID_Unico_APD",), "CentroCosto_Finca_Lote.csv")
    inventory_by_id = unique_by(inventory_src, ("ID_UNICO",), "Inventario_2026.csv")
    operations_by_id = unique_by(operations_src, ("ID_Operacion",), "Operacion.csv")
    machines_by_code = unique_by(machines_src, ("Equipo",), "Maquinaria.csv/Equipo")
    inputs_by_id = unique_by(inputs_src, ("ID",), "Insumos.csv")
    unique_by(operation_machines_src, ("ID_Operacion",), "Operacion_Maquinaria.csv")
    unique_by(advance_src, ("ID_Operacion",), "Operacion_AvanceDosis.csv")

    center_codes = {key[0] for key in centers_by_id}
    operation_codes = {key[0] for key in operations_by_id}
    input_codes = {key[0] for key in inputs_by_id}
    center_group_pairs = {
        (source_value(row, "ID_Centro_costo"), source_value(row, "ID_Grupo_operacion"))
        for row in center_groups_src
    }
    group_operation_pairs = {
        (source_value(row, "ID_Grupo_operacion"), source_value(row, "ID_Operacion"))
        for row in group_operations_src
    }
    if len(center_group_pairs) != len(center_groups_src) or len(group_operation_pairs) != len(group_operations_src):
        raise ValueError("Hay relaciones centro/grupo u operacion/grupo duplicadas")
    if any(center not in center_codes for center, _ in center_group_pairs):
        raise ValueError("Centro faltante en CentroCosto_GrupoOperacion.csv")
    if any(operation not in operation_codes for _, operation in group_operation_pairs):
        raise ValueError("Operacion faltante en GrupoOperacion_Operacion.csv")

    group_names: dict[str, str] = {}
    for row in center_groups_src + group_operations_src:
        code = source_value(row, "ID_Grupo_operacion")
        name = source_value(row, "Grupo_operacion")
        if not code or not name or (code in group_names and group_names[code] != name):
            raise ValueError("Codigo de grupo vacio o nombre contradictorio")
        group_names[code] = name
    if any(group not in group_names for _, group in center_group_pairs):
        raise ValueError("Grupo faltante en CentroCosto_GrupoOperacion.csv")
    if any(group not in group_names for group, _ in group_operation_pairs):
        raise ValueError("Grupo faltante en GrupoOperacion_Operacion.csv")

    center_code_by_normalized = {normalized_id(code): code for code in center_codes}
    if len(center_code_by_normalized) != len(center_codes):
        raise ValueError("Dos centros colisionan al normalizar sus IDs")
    if any(normalized_id(source_value(row, "ID_CentroCosto_TTS")) not in center_code_by_normalized for row in locations_src):
        raise ValueError("Hay ubicaciones con un centro sugerido ausente")

    operations_machinery = unique_by(operation_machines_src, ("ID_Operacion",), "Operacion_Maquinaria.csv")
    advance_by_operation = unique_by(advance_src, ("ID_Operacion",), "Operacion_AvanceDosis.csv")
    input_flags: dict[str, str] = {}
    for row in operation_inputs_src:
        code = source_value(row, "ID_Operacion")
        if not code:
            raise ValueError("Operacion_Insumos.csv tiene una clave vacia")
        old = input_flags.get(code)
        flag = source_value(row, "Insumos").strip().upper()
        if flag not in {"", "SI", "S", "NO", "1", "TRUE"}:
            raise ValueError("Indicador de insumos con valor desconocido")
        if old is not None and old != flag:
            raise ValueError("Operacion_Insumos.csv tiene indicadores contradictorios")
        input_flags[code] = flag

    # V1.1 filters machine groups by normalized substring containment.
    machine_groups = sorted({source_value(row, "Grupo Operativo") for row in machines_src if source_value(row, "Grupo Operativo")})
    machine_group_codes = {canonical(group): group for group in machine_groups}
    operation_group_raw: dict[str, list[str]] = {}
    group_machine_pairs: set[tuple[str, str]] = set()
    operation_task_type: dict[str, str] = {}
    for code, row in operations_by_id.items():
        operation_task_type[code[0]] = source_value(row, "Tipo_Operacion")
    for code, row in operations_machinery.items():
        operation = code[0]
        groups = list(dict.fromkeys(part.strip() for part in source_value(row, "Grupo_Op_Maq").split(",") if part.strip()))
        operation_group_raw[operation] = groups
        task_type = operation_task_type.get(operation, "")
        if task_type not in {"Manual", "Mecanizada"}:
            raise ValueError("Tipo de operacion no reconocido")
        if task_type == "Manual":
            continue
        for group in groups:
            group_key = canonical(group)
            matched = [
                source_value(machine, "Equipo")
                for machine in machines_src
                if group_key in canonical(source_value(machine, "Grupo Operativo"))
                or canonical(source_value(machine, "Grupo Operativo")) in group_key
            ]
            if not matched:
                raise ValueError("Grupo de maquinaria sin equipos compatibles")
            group_machine_pairs.update((operation, machine_code) for machine_code in matched)
    if set(operation_group_raw) != operation_codes:
        raise ValueError("Operacion_Maquinaria.csv no cubre el catalogo completo de operaciones")

    existing_farms = {normalized_id(row["id"]): row["id"] for row in backup["farms"]}
    existing_lots = {normalized_id(row["id"]): row["id"] for row in backup["lots"]}
    location_ids_normalized = {normalized_id(key[0]) for key in locations_by_id}
    inventory_ids_normalized = {normalized_id(key[0]) for key in inventory_by_id}
    farm_name_by_id: dict[str, set[str]] = {}
    for row in locations_src:
        farm_key = normalized_id(source_value(row, "ID_Finca_APD"))
        farm_name_by_id.setdefault(farm_key, set()).add(source_value(row, "Finca_TTS"))
    new_farms = []
    source_farm_id: dict[str, str] = {}
    for row in locations_src:
        farm_source_id = source_value(row, "ID_Finca_APD")
        farm_key = normalized_id(farm_source_id)
        if farm_key in existing_farms:
            source_farm_id[farm_key] = existing_farms[farm_key]
        else:
            names = {name for name in farm_name_by_id.get(farm_key, set()) if name}
            if len(names) != 1:
                raise ValueError("Finca nueva sin nombre unico en el catalogo de ubicaciones")
            source_farm_id[farm_key] = farm_source_id
    for farm_key, farm_id in source_farm_id.items():
        if farm_key not in existing_farms:
            new_farms.append({
                "id": farm_id,
                "name": next(name for name in farm_name_by_id[farm_key] if name),
                "source_data": {"source_file": "CentroCosto_Finca_Lote.csv", "ID_Finca_APD": farm_id},
            })
    new_farms = list({row["id"]: row for row in new_farms}.values())

    inv_by_normalized = {normalized_id(key[0]): row for key, row in inventory_by_id.items()}
    lots_payload = []
    for source_id, loc in ((key[0], row) for key, row in locations_by_id.items()):
        loc_fields = {canonical(k): (v or "").strip() for k, v in loc.items() if k}
        inventory = inv_by_normalized.get(normalized_id(source_id))
        inv_fields = {canonical(k): (v or "").strip() for k, v in inventory.items() if k} if inventory else {}
        farm_key = normalized_id(source_value(loc, "ID_Finca_APD"))
        suggested_cc_source = source_value(loc, "ID_CentroCosto_TTS")
        lot_id = existing_lots.get(normalized_id(source_id), source_id)
        lots_payload.append({
            "id": lot_id,
            "farm_id": source_farm_id[farm_key],
            "lot_code": source_value(loc, "ID_Lote_APD"),
            "lot_name": source_value(loc, "Lote_TTS"),
            "crop": inv_fields.get(canonical("CULTIVO"), ""),
            "variety": inv_fields.get(canonical("VARIEDAD"), ""),
            "gross_area": number(inv_fields.get(canonical("AREA B"), ""), "AREA B"),
            "net_area": number(inv_fields.get(canonical("AREA N"), ""), "AREA N"),
            "furrows": number(inv_fields.get(canonical("SURCOS"), ""), "SURCOS", integer=True),
            "planting_year": number(inv_fields.get(canonical("Año Plantacion"), inv_fields.get("anoplantacion", "")), "Año Plantacion", integer=True),
            "planting_distance": number(inv_fields.get(canonical("Dist Plantacion"), ""), "Dist Plantacion"),
            "active": True,
            "selectable": True,
            "agronomic_data_available": inventory is not None,
            "totvs_location_id": source_value(loc, "ID_Unico_APD"),
            "suggested_cost_center_id": center_code_by_normalized[normalized_id(suggested_cc_source)],
            "suggested_cost_center_name": source_value(loc, "CentroCosto_TTS"),
            "source_data": {"source_file": "CentroCosto_Finca_Lote.csv", "location": loc, "inventory": inventory},
        })
    if len({row["id"] for row in lots_payload}) != len(lots_payload):
        raise ValueError("Dos ubicaciones producirian el mismo ID interno")
    if len({(row["farm_id"], row["lot_code"]) for row in lots_payload}) != len(lots_payload):
        raise ValueError("Hay claves finca/lote duplicadas en el catalogo TOTVS")
    existing_lot_pairs = {(row["farm_id"], str(row["lot_code"])): row["id"] for row in backup["lots"]}
    if any(
        (row["farm_id"], row["lot_code"]) in existing_lot_pairs
        and existing_lot_pairs[(row["farm_id"], row["lot_code"])] != row["id"]
        for row in lots_payload
    ):
        raise ValueError("El catalogo TOTVS colisiona con una clave finca/lote historica")
    historical_ids = [row["id"] for row in backup["lots"] if normalized_id(row["id"]) not in location_ids_normalized]
    if len(historical_ids) != 5:
        raise ValueError("La cantidad de lotes historicos fuera de ubicaciones TOTVS no coincide con el respaldo")

    farms_payload = new_farms
    centers_payload = [
        {"cost_center_id": source_value(row, "ID_Centro_costo"), "name": source_value(row, "Centro_costo"), "source_data": row}
        for row in centers_src
    ]
    groups_payload = []
    for code, name in sorted(group_names.items()):
        groups_payload.append({
            "group_code": code,
            "name": name,
            "source_data": {
                "source_files": ["CentroCosto_GrupoOperacion.csv", "GrupoOperacion_Operacion.csv"],
                "group_code": code,
                "name": name,
            },
        })

    advances = {key[0]: row for key, row in advance_by_operation.items()}
    machinery = {key[0]: row for key, row in operations_machinery.items()}
    operations_payload = []
    for (code,), row in operations_by_id.items():
        task_type = source_value(row, "Tipo_Operacion")
        groups = operation_group_raw[code] if task_type != "Manual" else []
        flag = input_flags.get(code, "")
        advance_row = advances.get(code) or {}
        machinery_row = machinery.get(code) or {}
        operations_payload.append({
            "operation_code": code,
            "name": source_value(row, "Operación"),
            "unit": source_value(row, "ID_Unidad_medida"),
            "unit_description": source_value(row, "Unidad_medida"),
            "task_type": task_type,
            "machine_groups": groups,
            "allows_inputs": flag in {"SI", "S", "1", "TRUE"},
            "source_data": {
                "source_files": ["Operacion.csv", "Operacion_AvanceDosis.csv", "Operacion_Maquinaria.csv", "Operacion_Insumos.csv"],
                "Operacion": {
                    "ID_Operacion": code,
                    "Operación": source_value(row, "Operación"),
                    "ID_Unidad_medida": source_value(row, "ID_Unidad_medida"),
                    "Unidad_medida": source_value(row, "Unidad_medida"),
                    "Tipo_Operacion": task_type,
                },
                "Unidad_avance": source_value(advance_row, "Unidad_avance"),
                "Grupo_Op_Maq": source_value(machinery_row, "Grupo_Op_Maq"),
                "Insumos": flag,
            },
        })

    machines_payload = []
    for (code,), row in machines_by_code.items():
        machines_payload.append({
            "machine_code": code,
            "equipment_code": source_value(row, "ID_Equipo"),
            "operational_group": source_value(row, "Grupo Operativo"),
            "acquisition_date": date_value(source_value(row, "Fecha_Aquisición")),
            "brand": source_value(row, "Marca"),
            "model": source_value(row, "Modelo"),
            "plate": source_value(row, "Patente"),
            "source_data": {"source_file": "Maquinaria.csv", "source_row": row},
        })
    inputs_payload = [
        {"input_code": code[0], "description": source_value(row, "Insumo"), "unit": source_value(row, "Unidad Medida"), "source_data": {"source_file": "Insumos.csv", "source_row": row}}
        for code, row in inputs_by_id.items()
    ]

    source_ops = {row["operation_code"] for row in operations_payload}
    source_machines = {row["machine_code"] for row in machines_payload}
    source_inputs = {row["input_code"] for row in inputs_payload}
    existing_operations = {row["operation_code"] for row in backup["operations"]}
    existing_machines = {row["machine_code"] for row in backup["machines"]}
    existing_inputs = {row["input_code"] for row in backup["inputs"]}
    existing_farm_ids = {row["id"] for row in backup["farms"]}
    existing_lot_ids = {row["id"] for row in backup["lots"]}

    # Check that operation flags have no conflicting duplicate and that every
    # referenced catalog key exists before serializing any SQL.
    if any(code not in input_codes for code in source_inputs):
        raise ValueError("Insumo ausente en el catalogo fuente")
    if len(set(center_codes)) != len(centers_src):
        raise ValueError("Centros duplicados")
    if len(set(operations_payload[i]["operation_code"] for i in range(len(operations_payload)))) != len(operations_payload):
        raise ValueError("Operaciones duplicadas")

    plan: dict[str, Any] = {
        "farms": farms_payload,
        "cost_centers": centers_payload,
        "operation_groups": groups_payload,
        "lots": lots_payload,
        "operations": operations_payload,
        "machines": machines_payload,
        "inputs": inputs_payload,
        "center_groups": [{"cost_center_id": a, "group_code": b} for a, b in sorted(center_group_pairs)],
        "group_operations": [{"group_code": a, "operation_code": b} for a, b in sorted(group_operation_pairs)],
        "historical_lot_ids": historical_ids,
        "stale_operation_codes": sorted(existing_operations - source_ops),
        "stale_machine_codes": sorted(existing_machines - source_machines),
        "operation_machine_pair_count": len(group_machine_pairs),
    }
    summary = {
        "source_farms_to_add": len(farms_payload),
        "source_cost_centers": len(centers_payload),
        "source_operation_groups": len(groups_payload),
        "source_locations": len(lots_payload),
        "existing_lots_to_update": len({row["id"] for row in lots_payload} & existing_lot_ids),
        "new_lots_to_add": len({row["id"] for row in lots_payload} - existing_lot_ids),
        "historical_lots_to_keep_unselectable": len(historical_ids),
        "agronomic_data_available": sum(bool(row["agronomic_data_available"]) for row in lots_payload),
        "agronomic_data_missing": sum(not row["agronomic_data_available"] for row in lots_payload),
        "source_operations": len(operations_payload),
        "existing_operations_to_update": len(source_ops & existing_operations),
        "new_operations_to_add": len(source_ops - existing_operations),
        "existing_operations_to_deactivate": len(plan["stale_operation_codes"]),
        "source_machines": len(machines_payload),
        "existing_machines_to_update": len(source_machines & existing_machines),
        "new_machines_to_add": len(source_machines - existing_machines),
        "existing_machines_to_deactivate": len(plan["stale_machine_codes"]),
        "source_inputs": len(inputs_payload),
        "existing_inputs_to_update": len(source_inputs & existing_inputs),
        "new_inputs_to_add": len(source_inputs - existing_inputs),
        "center_group_relations": len(center_group_pairs),
        "group_operation_relations": len(group_operation_pairs),
        "operation_machine_relations": len(group_machine_pairs),
        "operation_input_relations": 0,
    }
    return plan, summary


def recordset(payload: str, key: str, columns: str) -> str:
    return f"jsonb_to_recordset((select data->'{key}' from pwa_v11_import_payload)) as x({columns})"


def build_sql(plan: dict[str, Any]) -> str:
    payload = sql_literal_json(plan)
    sql = [
        "begin;",
        "create temporary table pwa_v11_import_payload(data jsonb not null) on commit drop;",
        f"insert into pwa_v11_import_payload(data) values ({payload});",
        """
insert into public.farms(id,name,active,source_data)
select x.id,x.name,true,x.source_data from jsonb_to_recordset((select data->'farms' from pwa_v11_import_payload)) as x(id text,name text,source_data jsonb)
on conflict(id) do update set name=excluded.name,active=true,source_data=excluded.source_data,updated_at=now();
insert into public.cost_centers(cost_center_id,name,active,source_data)
select x.cost_center_id,x.name,true,x.source_data from jsonb_to_recordset((select data->'cost_centers' from pwa_v11_import_payload)) as x(cost_center_id text,name text,source_data jsonb)
on conflict(cost_center_id) do update set name=excluded.name,active=true,source_data=excluded.source_data,updated_at=now();
insert into public.operation_groups(group_code,name,active,source_data)
select x.group_code,x.name,true,x.source_data from jsonb_to_recordset((select data->'operation_groups' from pwa_v11_import_payload)) as x(group_code text,name text,source_data jsonb)
on conflict(group_code) do update set name=excluded.name,active=true,updated_at=now();
insert into public.operations(operation_code,name,unit,unit_description,task_type,machine_groups,allows_inputs,active,source_data)
select x.operation_code,x.name,x.unit,x.unit_description,x.task_type,x.machine_groups,x.allows_inputs,true,x.source_data
from jsonb_to_recordset((select data->'operations' from pwa_v11_import_payload)) as x(operation_code text,name text,unit text,unit_description text,task_type text,machine_groups text[],allows_inputs boolean,source_data jsonb)
on conflict(operation_code) do update set name=excluded.name,unit=excluded.unit,unit_description=excluded.unit_description,task_type=excluded.task_type,machine_groups=excluded.machine_groups,allows_inputs=excluded.allows_inputs,active=true,source_data=excluded.source_data,updated_at=now();
insert into public.machines(machine_code,equipment_code,operational_group,acquisition_date,brand,model,plate,active,source_data)
select x.machine_code,x.equipment_code,x.operational_group,x.acquisition_date,x.brand,x.model,x.plate,true,x.source_data
from jsonb_to_recordset((select data->'machines' from pwa_v11_import_payload)) as x(machine_code text,equipment_code text,operational_group text,acquisition_date date,brand text,model text,plate text,source_data jsonb)
on conflict(machine_code) do update set equipment_code=excluded.equipment_code,operational_group=excluded.operational_group,acquisition_date=excluded.acquisition_date,brand=excluded.brand,model=excluded.model,plate=excluded.plate,active=true,source_data=excluded.source_data,updated_at=now();
insert into public.inputs(input_code,description,unit,active,source_data)
select x.input_code,x.description,x.unit,true,x.source_data
from jsonb_to_recordset((select data->'inputs' from pwa_v11_import_payload)) as x(input_code text,description text,unit text,source_data jsonb)
on conflict(input_code) do update set description=excluded.description,unit=excluded.unit,active=true,source_data=excluded.source_data,updated_at=now();
insert into public.lots(id,farm_id,lot_code,lot_name,crop,variety,gross_area,net_area,furrows,planting_year,planting_distance,active,selectable,agronomic_data_available,totvs_location_id,suggested_cost_center_id,suggested_cost_center_name,source_data)
select x.id,x.farm_id,x.lot_code,x.lot_name,x.crop,x.variety,x.gross_area,x.net_area,x.furrows,x.planting_year,x.planting_distance,true,x.selectable,x.agronomic_data_available,x.totvs_location_id,x.suggested_cost_center_id,x.suggested_cost_center_name,x.source_data
from jsonb_to_recordset((select data->'lots' from pwa_v11_import_payload)) as x(id text,farm_id text,lot_code text,lot_name text,crop text,variety text,gross_area numeric,net_area numeric,furrows integer,planting_year integer,planting_distance numeric,selectable boolean,agronomic_data_available boolean,totvs_location_id text,suggested_cost_center_id text,suggested_cost_center_name text,source_data jsonb)
on conflict(id) do update set farm_id=excluded.farm_id,lot_code=excluded.lot_code,lot_name=excluded.lot_name,crop=excluded.crop,variety=excluded.variety,gross_area=excluded.gross_area,net_area=excluded.net_area,furrows=excluded.furrows,planting_year=excluded.planting_year,planting_distance=excluded.planting_distance,active=true,selectable=excluded.selectable,agronomic_data_available=excluded.agronomic_data_available,totvs_location_id=excluded.totvs_location_id,suggested_cost_center_id=excluded.suggested_cost_center_id,suggested_cost_center_name=excluded.suggested_cost_center_name,source_data=excluded.source_data,updated_at=now();
insert into public.cost_center_operation_groups(cost_center_id,group_code)
select x.cost_center_id,x.group_code from jsonb_to_recordset((select data->'center_groups' from pwa_v11_import_payload)) as x(cost_center_id text,group_code text) on conflict do nothing;
insert into public.operation_group_operations(group_code,operation_code)
select x.group_code,x.operation_code from jsonb_to_recordset((select data->'group_operations' from pwa_v11_import_payload)) as x(group_code text,operation_code text) on conflict do nothing;
update public.operations set active=false,updated_at=now()
where active and not exists(select 1 from jsonb_to_recordset((select data->'operations' from pwa_v11_import_payload)) as x(operation_code text) where x.operation_code=operations.operation_code);
update public.machines set active=false,updated_at=now()
where active and not exists(select 1 from jsonb_to_recordset((select data->'machines' from pwa_v11_import_payload)) as x(machine_code text) where x.machine_code=machines.machine_code);
insert into public.operation_machines(operation_code,machine_code)
select distinct o.operation_code,m.machine_code from public.operations o
cross join lateral unnest(o.machine_groups) as g(group_name)
join public.machines m on
  position(lower(regexp_replace(trim(g.group_name),'[^A-Za-z0-9]+','','g')) in lower(regexp_replace(trim(m.operational_group),'[^A-Za-z0-9]+','','g'))) > 0
  or position(lower(regexp_replace(trim(m.operational_group),'[^A-Za-z0-9]+','','g')) in lower(regexp_replace(trim(g.group_name),'[^A-Za-z0-9]+','','g'))) > 0
where o.active and o.task_type <> 'Manual' and m.active and trim(g.group_name) <> '' and trim(m.operational_group) <> ''
on conflict do nothing;
update public.lots set selectable=false,updated_at=now()
where id in (select jsonb_array_elements_text(data->'historical_lot_ids') from pwa_v11_import_payload);
""",
        "commit;",
    ]
    return "\n".join(sql)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan, summary = build_plan(args.source_zip, args.backup)
    sql = build_sql(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sql, encoding="utf-8")
    summary["sql_bytes"] = len(sql.encode("utf-8"))
    summary["sql_file"] = str(args.output)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
