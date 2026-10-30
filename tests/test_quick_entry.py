from datetime import date

from app_core import load_all_sources
from quick_entry import interpret_part_text, convert_input_quantity


def test_text_draft_recognizes_codes_and_spoken_quantity(source_data_dir):
    masters = load_all_sources(source_data_dir)
    draft = interpret_part_text(
        "ayer legajo 4 tarea 4510 maquina 2098 lote 0501 finca luisiana veinte horas",
        masters, today=date(2026, 10, 13),
    )
    assert draft["date"] == "2026-10-12"
    assert draft["suggestions"]["Operaciones"] == "4510"
    assert draft["suggestions"]["Fincas y lotes"] == "0190501"
    assert draft["personnel_keys"] == ["4"]
    assert draft["quantity"] == 20
    assert draft["quantity_unit"] == "HS"


def test_vehicle_remains_associated_with_its_person(source_data_dir):
    masters = load_all_sources(source_data_dir)
    draft = interpret_part_text(
        "legajo 4 maquina 2098 y legajo 902688, finca luisiana lote 0501 tarea 4510 ocho horas",
        masters,
    )
    assert draft["vehicle_by_person"] == {"4": "10202098"}
    assert draft["vehicle_key"] is None


def test_invalid_date_is_reported_and_decimal_dose_is_not_a_date(source_data_dir):
    masters = load_all_sources(source_data_dir)
    draft = interpret_part_text("31/02/2026 cantidad 20", masters, today=date(2026, 10, 13))
    assert draft["notices"]
    draft = interpret_part_text("dos mil quinientos surcos dosis 2,5", masters, today=date(2026, 10, 13))
    assert draft["date"] == "2026-10-13"
    assert draft["quantity"] == 2500
    assert draft["dose"] == 2.5


def test_consumption_unit_conversion_does_not_mix_volume_and_mass():
    assert convert_input_quantity(2, "TN", "KG") == 2000
    assert convert_input_quantity(250, "GR", "KG") == .25
    try:
        convert_input_quantity(2, "L", "KG")
    except ValueError:
        pass
    else:
        raise AssertionError("Volume and mass require explicit correction")


def test_negative_quantity_is_not_silently_made_positive(source_data_dir):
    masters = load_all_sources(source_data_dir)
    draft = interpret_part_text("cantidad -20 hectareas", masters)
    assert draft["quantity"] == 0
