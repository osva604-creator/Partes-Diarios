"""Interpret text (including future speech transcripts) into a reviewable draft.

This module never writes data or confirms a part: the UI must review and save it.
"""
from datetime import date, timedelta
import re

from app_core import find_candidates, normalize


NUMBER_WORDS = {
    "CERO": 0, "UN": 1, "UNO": 1, "UNA": 1, "DOS": 2, "TRES": 3,
    "CUATRO": 4, "CINCO": 5, "SEIS": 6, "SIETE": 7, "OCHO": 8, "NUEVE": 9,
    "DIEZ": 10, "ONCE": 11, "DOCE": 12, "TRECE": 13, "CATORCE": 14,
    "QUINCE": 15, "DIECISEIS": 16, "DIECISIETE": 17, "DIECIOCHO": 18,
    "DIECINUEVE": 19, "VEINTE": 20, "VEINTIUNO": 21, "VEINTIDOS": 22,
    "VEINTITRES": 23, "VEINTICUATRO": 24, "VEINTICINCO": 25, "VEINTISEIS": 26,
    "VEINTISIETE": 27, "VEINTIOCHO": 28, "VEINTINUEVE": 29, "TREINTA": 30,
    "CUARENTA": 40, "CINCUENTA": 50, "SESENTA": 60, "SETENTA": 70,
    "OCHENTA": 80, "NOVENTA": 90, "CIEN": 100, "CIENTO": 100,
    "DOSCIENTOS": 200, "TRESCIENTOS": 300, "CUATROCIENTOS": 400,
    "QUINIENTOS": 500, "SEISCIENTOS": 600, "SETECIENTOS": 700,
    "OCHOCIENTOS": 800, "NOVECIENTOS": 900,
}
WORD_NUMBER = r"(?:\b(?:" + "|".join(NUMBER_WORDS) + r"|MIL|Y)\b\s*){1,8}"
NUMERIC_NUMBER = r"\d+(?:[.,]\d+)*"
NUMBER = rf"(?:{NUMERIC_NUMBER}|{WORD_NUMBER})"
WORK_UNITS = {
    "HA": "HA", "HECTAREA": "HA", "HECTAREAS": "HA",
    "SC": "SC", "SURCO": "SC", "SURCOS": "SC",
    "H": "HS", "HS": "HS", "HORA": "HS", "HORAS": "HS",
    "TN": "TN", "TONELADA": "TN", "TONELADAS": "TN",
    "JN": "JN", "JORNAL": "JN", "JORNALES": "JN",
}
INPUT_UNITS = {
    "L": "L", "LT": "L", "LTS": "L", "LITRO": "L", "LITROS": "L",
    "KG": "KG", "KGS": "KG", "KILO": "KG", "KILOS": "KG",
    "KILOGRAMO": "KG", "KILOGRAMOS": "KG", "GR": "GR", "G": "GR",
    "GRAMO": "GR", "GRAMOS": "GR", "TN": "TN", "TONELADA": "TN",
    "TONELADAS": "TN", "UN": "UN", "UNIDAD": "UN", "UNIDADES": "UN",
}


def number_value(value):
    value = value.strip()
    if re.fullmatch(NUMERIC_NUMBER, value):
        if "," in value and "." in value:
            value = value.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value):
            value = value.replace(".", "")
        else:
            value = value.replace(",", ".")
        return float(value)
    total = current = 0
    for token in normalize(value).split():
        if token == "MIL":
            total += (current or 1) * 1000
            current = 0
        elif token != "Y":
            current += NUMBER_WORDS[token]
    return float(total + current)


def _confident(matches):
    if not matches:
        return None
    if len(matches) > 1 and matches[0].score - matches[1].score < 3:
        return None
    return matches[0].key


def _code(prompt, hints):
    match = re.search(rf"\b(?:{hints})\s*[:#-]?\s*(\d+)\b", prompt)
    return match.group(1) if match else None


def _vehicle(prompt, machines):
    code = _code(prompt, r"MAQUINA|MAQUINARIA|EQUIPO|VEHICULO|TRACTOR")
    if not code:
        return None
    options = [str(row["Equipo"]) for row in machines
               if code in {str(row.get("Equipo", "")), str(row.get("ID_Equipo", "")), str(row.get("ULTIMOS_4", ""))}]
    return options[0] if len(set(options)) == 1 else None


def interpret_part_text(prompt, masters, fronts=(), today=None):
    today = today or date.today()
    normalized = normalize(prompt)
    # Preserve decimal separators, dates and unit expressions while folding accents.
    import unicodedata
    raw = "".join(c for c in unicodedata.normalize("NFKD", prompt.upper())
                  if not unicodedata.combining(c))
    candidates = find_candidates(prompt, masters)
    suggestions = {category: _confident(matches) for category, matches in candidates.items()}
    notices = []
    part_date = today
    date_match = re.search(r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{1,2}\.\d{1,2}\.\d{4})\b", raw)
    if date_match:
        try:
            bits = re.split(r"[/.-]", date_match.group(1))
            if len(bits[0]) == 4:
                year, month, day = map(int, bits)
            else:
                day, month = map(int, bits[:2])
                year = int(bits[2]) if len(bits) == 3 else today.year
                if year < 100:
                    year += 2000
            part_date = date(year, month, day)
        except ValueError:
            notices.append("La fecha del texto no es válida; corregila antes de confirmar.")
    elif "ANTEAYER" in normalized.split():
        part_date = today - timedelta(days=2)
    elif "AYER" in normalized.split():
        part_date = today - timedelta(days=1)

    # A named farm disambiguates lot codes that are repeated across farms.
    farm_names = {str(row.get("FINCA", "")) for row in masters["lotes"]
                  if row.get("FINCA") and f" {normalize(row['FINCA'])} " in f" {normalized} "}
    lot_code = _code(normalized, "LOTE")
    if farm_names or lot_code:
        lots = [row for row in masters["lotes"]
                if (not farm_names or str(row.get("FINCA", "")) in farm_names)
                and (not lot_code or str(row.get("ID_Lote", "")).lstrip("0") == lot_code.lstrip("0")
                     or str(row.get("ID_UNICO", "")) == lot_code)]
        lot_keys = {str(row["ID_UNICO"]) for row in lots}
        suggestions["Fincas y lotes"] = next(iter(lot_keys)) if len(lot_keys) == 1 else None
    for category, hints, records, key in [
        ("Operaciones", "TAREA|OPERACION", masters["operaciones"], "ID_Operacion"),
        ("Insumos", "INSUMO|PRODUCTO", masters["insumos"], "CODIGO"),
    ]:
        code = _code(normalized, hints)
        if code:
            matches = [row for row in records if str(row.get(key, "")) == code]
            keys = {str(row[key]) for row in matches}
            suggestions[category] = next(iter(keys)) if len(keys) == 1 else None

    personnel = []
    explicit_people = list(re.finditer(r"\bLEGAJOS?\s*[:#-]?\s*((?:\d+\s*(?:(?:,|Y|E)\s*)?)+)", raw))
    valid_people = {str(row["LEGAJO"]) for row in masters["personal"]}
    vehicle_by_person = {}
    for index, match in enumerate(explicit_people):
        keys = re.findall(r"\d+", match.group(1))
        next_start = explicit_people[index + 1].start() if index + 1 < len(explicit_people) else len(raw)
        vehicle = _vehicle(normalize(raw[match.end():next_start]), masters["maquinaria"])
        for key in keys:
            if key in valid_people:
                personnel.append(key)
                if vehicle:
                    vehicle_by_person[key] = vehicle
            else:
                notices.append(f"El legajo {key} no existe en los datos de personal.")
    if not explicit_people:
        for segment in re.split(r";|\n|\s+y\s+", prompt, flags=re.IGNORECASE):
            matches = find_candidates(segment, masters)["Personal"]
            key = _confident(matches)
            if key:
                personnel.append(key)
                vehicle = _vehicle(normalize(segment), masters["maquinaria"])
                if vehicle:
                    vehicle_by_person[key] = vehicle
        if not personnel and suggestions.get("Personal"):
            personnel.append(suggestions["Personal"])
    personnel = list(dict.fromkeys(personnel))
    common_vehicle = _vehicle(normalized, masters["maquinaria"]) or suggestions.get("Maquinaria")
    if len(personnel) == 1 and common_vehicle:
        vehicle_by_person.setdefault(personnel[0], common_vehicle)
    if len(personnel) > 1 and vehicle_by_person:
        # Per-person associations take precedence; never give another worker's
        # vehicle to a person whose segment did not mention one.
        common_vehicle = None

    front_ids = [int(front["id"]) for front in fronts
                 if f" {normalize(front['name'])} " in f" {normalized} "
                 or f" FRENTE {normalize(front['name']).removeprefix('FRENTE ').strip()} " in f" {normalized} "]
    work_unit_pattern = "|".join(sorted(WORK_UNITS, key=len, reverse=True))
    quantity = 0.0
    quantity_unit = ""
    for match in re.finditer(rf"(?<![\w/-])({NUMBER})\s*({work_unit_pattern})\b", raw):
        prefix = raw[max(0, match.start()-25):match.start()]
        if re.search(r"-\s*$", prefix):
            continue
        if re.search(r"\b(?:DOSIS|CONSUMO|INSUMO|PRODUCTO|OBJETIVO)\s*[:=]?\s*$", prefix):
            continue
        quantity, quantity_unit = number_value(match.group(1)), WORK_UNITS[match.group(2)]
        break
    if not quantity:
        explicit_quantity = re.search(rf"\bCANTIDAD\s*[:=]?\s*({NUMBER})(?=\W|$)", raw)
        if explicit_quantity:
            quantity = number_value(explicit_quantity.group(1))
    dose_match = re.search(rf"\bDOSIS(?:\s+DE)?\s*[:=]?\s*({NUMBER})", raw)
    dose = number_value(dose_match.group(1)) if dose_match else 0.0
    input_pattern = "|".join(sorted(INPUT_UNITS, key=len, reverse=True))
    consumption_match = re.search(rf"\b(?:CONSUMO|CANTIDAD\s+(?:DE\s+)?INSUMO)(?:\s+DE)?\s*[:=]?\s*({NUMBER})\s*({input_pattern})\b", raw)
    consumption = number_value(consumption_match.group(1)) if consumption_match else None
    consumption_unit = INPUT_UNITS[consumption_match.group(2)] if consumption_match else ""
    notes_match = re.search(r"\bOBSERVACIONES?\s*[:=]?\s*(.+)$", prompt, flags=re.IGNORECASE)
    return {
        "text": prompt, "suggestions": suggestions, "date": part_date.isoformat(),
        "farm": next(iter(farm_names)) if len(farm_names) == 1 else None,
        "personnel_keys": personnel, "front_ids": front_ids,
        "vehicle_by_person": vehicle_by_person, "vehicle_key": common_vehicle,
        "quantity": quantity, "quantity_unit": quantity_unit, "dose": dose,
        "input_quantity": consumption, "input_quantity_unit": consumption_unit,
        "notes": notes_match.group(1).strip() if notes_match else prompt,
        "notices": notices,
    }


def convert_input_quantity(quantity, source_unit, target_unit):
    source = INPUT_UNITS.get(normalize(source_unit), normalize(source_unit))
    target = INPUT_UNITS.get(normalize(target_unit), normalize(target_unit))
    if source == target:
        return float(quantity)
    mass = {"GR": .001, "KG": 1.0, "TN": 1000.0}
    if source in mass and target in mass:
        return float(quantity) * mass[source] / mass[target]
    raise ValueError(f"El consumo está expresado en {source}; revisalo en {target or 'la unidad del insumo'}.")
