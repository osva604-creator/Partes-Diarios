from app_core import filter_machines_for_operation, load_all_sources


def test_manual_1104_disallows_all_vehicles(source_data_dir):
    masters = load_all_sources(source_data_dir)
    operation = next(row for row in masters["operaciones"] if row["ID_Operacion"] == "1104")
    assert operation["Tipo_Tarea"] == "Manual"
    assert filter_machines_for_operation(operation, masters["maquinaria"]) == []


def test_mechanized_task_keeps_tractor_filter():
    machines = [{"Grupo Operativo": "TRACTORES"}, {"Grupo Operativo": "CAMIONETAS"}]
    operation = {"Tipo_Tarea": "Mecanizada", "Grupo_Op_Maq": "TRACTORES"}
    assert filter_machines_for_operation(operation, machines) == machines[:1]


def test_manual_classification_takes_precedence_over_machine_group():
    assert filter_machines_for_operation({"Tipo_Tarea": "Manual", "Grupo_Op_Maq": "TRACTORES"}, [{"Grupo Operativo": "TRACTORES"}]) == []
