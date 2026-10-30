from app_core import (
    equal_distribution,
    find_candidates,
    load_all_sources,
    normalize,
    rank_matches,
    redistribute_rows,
)


def test_normalize_ignores_accents_and_case():
    assert normalize("Sánchez, José") == "SANCHEZ JOSE"


def test_partial_person_name_matches():
    records = [
        {"LEGAJO": "10", "EMPLEADO": "LOPEZ MANUEL FRANCISCO"},
        {"LEGAJO": "11", "EMPLEADO": "PEREZ JUAN"},
    ]
    matches = rank_matches(
        "manuel lopez",
        records,
        key_field="LEGAJO",
        label_fields=["EMPLEADO", "LEGAJO"],
    )
    assert matches[0].key == "10"


def test_last_four_digits_match_machine_alias():
    records = [
        {
            "Equipamiento": "10101044",
            "ID_Equipo": "1044",
            "ULTIMOS_4": "1044",
            "Grupo Operativo": "TRACTORES",
        }
    ]
    matches = rank_matches(
        "1044",
        records,
        key_field="Equipamiento",
        label_fields=["ID_Equipo", "Grupo Operativo"],
        aliases=["ULTIMOS_4"],
    )
    assert matches[0].key == "10101044"


def test_official_txt_sources_are_loaded(source_data_dir):
    masters = load_all_sources(source_data_dir)
    assert len(masters["personal"]) == 565
    assert len(masters["maquinaria"]) == 517
    assert len(masters["operaciones"]) == 1355
    assert len(masters["lotes"]) == 621
    machine = next(row for row in masters["maquinaria"] if row["ID_Equipo"] == "4339")
    assert machine["Modelo"] == "HILUX L/16 2,4D/C4X2TDDX"


def test_manual_work_does_not_invent_machine_or_input(source_data_dir):
    masters = load_all_sources(source_data_dir)
    matches = find_candidates(
        "Cajal trabajó en Los Ralos haciendo limpieza manual",
        masters,
    )
    assert matches["Personal"]
    assert matches["Fincas y lotes"]
    assert matches["Maquinaria"] == []
    assert matches["Insumos"] == []


def test_field_machine_id_is_detected(source_data_dir):
    masters = load_all_sources(source_data_dir)
    matches = find_candidates("Cajal trabajó con el 4339", masters)
    assert matches["Maquinaria"][0].metadata["ID_Equipo"] == "4339"


def test_real_written_part_prioritizes_multiple_matching_words(source_data_dir):
    masters = load_all_sources(source_data_dir)
    matches = find_candidates(
        "nuñez daniel trabajo en cosecha de directa con la maquina 2098 "
        "en el lote 0501 de luisiana",
        masters,
    )
    assert matches["Personal"][0].metadata["LEGAJO"] == "902688"
    assert matches["Maquinaria"][0].metadata["ID_Equipo"] == "2098"
    assert matches["Fincas y lotes"][0].metadata["ID_UNICO"] == "0190501"
    assert matches["Operaciones"][0].metadata["ID_Operacion"] == "4510"


def test_codes_can_replace_names_and_descriptions(source_data_dir):
    masters = load_all_sources(source_data_dir)
    matches = find_candidates(
        "legajo 4 tarea 4510 maquina 2098 lote 0501 finca luisiana",
        masters,
    )
    assert matches["Personal"][0].metadata["LEGAJO"] == "4"
    assert matches["Operaciones"][0].metadata["ID_Operacion"] == "4510"
    assert matches["Maquinaria"][0].metadata["ID_Equipo"] == "2098"
    assert matches["Fincas y lotes"][0].metadata["ID_UNICO"] == "0190501"


def test_surcos_are_distributed_without_losing_the_total():
    assert equal_distribution(3000, 10, integers=True) == [300.0] * 10
    rows = [
        {"Estado": "Cantidad fija", "Cantidad": 100.0},
        *[{"Estado": "Presente", "Cantidad": 300.0} for _ in range(9)],
    ]
    adjusted = redistribute_rows(rows, 3000, integers=True)
    assert sum(row["Cantidad"] for row in adjusted) == 3000
    assert adjusted[0]["Cantidad"] == 100
