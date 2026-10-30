from __future__ import annotations

import sqlite3
import json
import math
from datetime import datetime
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path: Path) -> None:
    with connect(path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS fronts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS front_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                front_id INTEGER NOT NULL REFERENCES fronts(id) ON DELETE CASCADE,
                personnel_key TEXT NOT NULL,
                machine_key TEXT,
                UNIQUE(front_id, personnel_key)
            );
            CREATE TABLE IF NOT EXISTS front_task_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                front_id INTEGER NOT NULL REFERENCES fronts(id) ON DELETE CASCADE,
                operation_key TEXT NOT NULL,
                personnel_key TEXT NOT NULL,
                machine_key TEXT,
                UNIQUE(front_id, operation_key, personnel_key)
            );
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_code TEXT NOT NULL UNIQUE,
                report_date TEXT NOT NULL,
                created_by TEXT NOT NULL,
                report_sequence INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                service_order TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS work_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_key TEXT NOT NULL,
                operation_key TEXT NOT NULL,
                cycle_no INTEGER NOT NULL,
                target_quantity REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL,
                allocation_mode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Abierto',
                started_on TEXT NOT NULL,
                closed_on TEXT,
                UNIQUE(lot_key, operation_key, cycle_no)
            );
            CREATE TABLE IF NOT EXISTS partial_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL REFERENCES work_cycles(id),
                front_id INTEGER NOT NULL REFERENCES fronts(id),
                part_date TEXT NOT NULL,
                quantity REAL NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS partial_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL REFERENCES partial_parts(id) ON DELETE CASCADE,
                personnel_key TEXT NOT NULL,
                machine_key TEXT,
                attendance TEXT NOT NULL,
                quantity REAL NOT NULL,
                replacement_key TEXT
            );
            CREATE TABLE IF NOT EXISTS part_sequences (
                user_code TEXT PRIMARY KEY,
                last_sequence INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS partial_inputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL REFERENCES partial_parts(id) ON DELETE CASCADE,
                input_key TEXT NOT NULL,
                dose REAL NOT NULL DEFAULT 0,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS local_user_preferences (
                user_code TEXT PRIMARY KEY,
                front_id INTEGER REFERENCES fronts(id) ON DELETE SET NULL,
                default_person_hours REAL NOT NULL DEFAULT 12,
                updated_at TEXT NOT NULL
            );
            """
        )
        cycle_columns = {row[1] for row in db.execute("PRAGMA table_info(work_cycles)")}
        for column, definition in {
            "input_key": "TEXT",
            "input_dose": "REAL NOT NULL DEFAULT 0",
            "input_unit": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if column not in cycle_columns:
                db.execute(f"ALTER TABLE work_cycles ADD COLUMN {column} {definition}")
        partial_columns = {row[1] for row in db.execute("PRAGMA table_info(partial_parts)")}
        for column, definition in {
            "input_key": "TEXT",
            "input_dose": "REAL NOT NULL DEFAULT 0",
            "input_quantity": "REAL NOT NULL DEFAULT 0",
            "input_unit": "TEXT NOT NULL DEFAULT ''",
            "created_by": "TEXT NOT NULL DEFAULT ''",
            "part_sequence": "INTEGER",
            "part_code": "TEXT",
            "report_id": "INTEGER REFERENCES daily_reports(id)",
            "report_code": "TEXT",
            "line_no": "INTEGER",
            "crop": "TEXT",
        }.items():
            if column not in partial_columns:
                db.execute(f"ALTER TABLE partial_parts ADD COLUMN {column} {definition}")
        allocation_columns = {row[1] for row in db.execute("PRAGMA table_info(partial_allocations)")}
        if "front_id" not in allocation_columns:
            db.execute("ALTER TABLE partial_allocations ADD COLUMN front_id INTEGER REFERENCES fronts(id)")
        for column in ("machine_start_time", "machine_end_time"):
            if column not in allocation_columns:
                db.execute(f"ALTER TABLE partial_allocations ADD COLUMN {column} INTEGER")
        if "person_hours" not in allocation_columns:
            db.execute("ALTER TABLE partial_allocations ADD COLUMN person_hours REAL NOT NULL DEFAULT 12")
        preference_columns = {row[1] for row in db.execute("PRAGMA table_info(local_user_preferences)")}
        if "default_person_hours" not in preference_columns:
            db.execute("ALTER TABLE local_user_preferences ADD COLUMN default_person_hours REAL NOT NULL DEFAULT 12")
        report_columns = {row[1] for row in db.execute("PRAGMA table_info(daily_reports)")}
        if "service_order" not in report_columns:
            db.execute("ALTER TABLE daily_reports ADD COLUMN service_order TEXT NOT NULL DEFAULT ''")
        report_columns = {row[1] for row in db.execute("PRAGMA table_info(daily_reports)")}
        for column, definition in {
            "document_status": "TEXT NOT NULL DEFAULT 'Borrador'",
            "reviewed_at": "TEXT",
            "reviewed_by": "TEXT",
            "sent_at": "TEXT",
            "sent_by": "TEXT",
            "sent_to": "TEXT",
            "sent_via": "TEXT",
            "pdf_version": "INTEGER NOT NULL DEFAULT 0",
            "modified_at": "TEXT",
        }.items():
            if column not in report_columns:
                db.execute(f"ALTER TABLE daily_reports ADD COLUMN {column} {definition}")
        preference_columns = {row[1] for row in db.execute("PRAGMA table_info(local_user_preferences)")}
        for column, definition in {
            "whatsapp_number": "TEXT NOT NULL DEFAULT ''",
            "whatsapp_message": "TEXT NOT NULL DEFAULT 'Parte diario {id} - {fecha}'",
        }.items():
            if column not in preference_columns:
                db.execute(f"ALTER TABLE local_user_preferences ADD COLUMN {column} {definition}")
        legacy_rows = db.execute(
            "SELECT id FROM partial_parts WHERE part_code IS NULL OR TRIM(part_code) = '' ORDER BY id"
        ).fetchall()
        legacy_sequence = int(
            db.execute(
                "SELECT COALESCE(MAX(part_sequence), 0) FROM partial_parts WHERE created_by = 'legacy'"
            ).fetchone()[0]
        )
        for row in legacy_rows:
            legacy_sequence += 1
            db.execute(
                """UPDATE partial_parts
                   SET created_by = 'legacy', part_sequence = ?, part_code = ?
                   WHERE id = ?""",
                (legacy_sequence, f"legacy{legacy_sequence:04d}", int(row[0])),
            )
        db.execute(
            """INSERT INTO part_sequences(user_code, last_sequence)
               SELECT created_by, MAX(part_sequence)
               FROM partial_parts
               WHERE created_by <> '' AND part_sequence IS NOT NULL
               GROUP BY created_by
               ON CONFLICT(user_code) DO UPDATE SET
                   last_sequence = MAX(part_sequences.last_sequence, excluded.last_sequence)"""
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_partial_parts_code ON partial_parts(part_code) WHERE part_code IS NOT NULL"
        )
        db.execute(
            """INSERT INTO partial_inputs(part_id, input_key, dose, quantity, unit)
               SELECT id, input_key, input_dose, input_quantity, input_unit
               FROM partial_parts p
               WHERE input_key IS NOT NULL AND TRIM(input_key) <> ''
                 AND NOT EXISTS (SELECT 1 FROM partial_inputs i WHERE i.part_id = p.id)"""
        )
        # Individual tasks (for example jornales) accumulate production but do not
        # have a lot target. Normalize legacy cycles that received a placeholder.
        db.execute(
            "UPDATE work_cycles SET target_quantity = 0 WHERE allocation_mode = 'Cantidad individual'"
        )


def rows(path: Path, sql: str, parameters: tuple = ()) -> list[dict]:
    with connect(path) as db:
        return [dict(row) for row in db.execute(sql, parameters).fetchall()]


def create_front(path: Path, name: str) -> int:
    with connect(path) as db:
        cursor = db.execute(
            "INSERT INTO fronts(name, created_at) VALUES (?, ?)",
            (name.strip(), datetime.now().isoformat(timespec="seconds")),
        )
        return int(cursor.lastrowid)


def list_fronts(path: Path) -> list[dict]:
    return rows(path, "SELECT * FROM fronts WHERE active = 1 ORDER BY name")


def get_user_front_preference(path: Path, user_code: str) -> int | None:
    with connect(path) as db:
        row = db.execute(
            "SELECT front_id FROM local_user_preferences WHERE user_code = ?", (user_code.strip().lower(),)
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None


def save_user_front_preference(path: Path, user_code: str, front_id: int | None) -> None:
    with connect(path) as db:
        db.execute(
            """INSERT INTO local_user_preferences(user_code, front_id, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(user_code) DO UPDATE SET front_id = excluded.front_id, updated_at = excluded.updated_at""",
            (user_code.strip().lower(), front_id, datetime.now().isoformat(timespec="seconds")),
        )


def get_user_default_person_hours(path: Path, user_code: str) -> float:
    with connect(path) as db:
        row = db.execute(
            "SELECT default_person_hours FROM local_user_preferences WHERE user_code = ?",
            (user_code.strip().lower(),),
        ).fetchone()
        return float(row[0]) if row and row[0] is not None else 12.0


def save_user_default_person_hours(path: Path, user_code: str, hours: float) -> None:
    with connect(path) as db:
        db.execute(
            """INSERT INTO local_user_preferences(user_code, front_id, default_person_hours, updated_at)
               VALUES (?, NULL, ?, ?)
               ON CONFLICT(user_code) DO UPDATE SET
                   default_person_hours = excluded.default_person_hours,
                   updated_at = excluded.updated_at""",
            (user_code.strip().lower(), float(hours), datetime.now().isoformat(timespec="seconds")),
        )


def get_user_whatsapp_preferences(path: Path, user_code: str) -> dict:
    with connect(path) as db:
        row = db.execute(
            "SELECT whatsapp_number, whatsapp_message FROM local_user_preferences WHERE user_code = ?",
            (user_code.strip().lower(),),
        ).fetchone()
        return {
            "number": str(row[0] or "") if row else "",
            "message": str(row[1] or "Parte diario {id} - {fecha}") if row else "Parte diario {id} - {fecha}",
        }


def save_user_whatsapp_preferences(path: Path, user_code: str, number: str, message: str) -> None:
    with connect(path) as db:
        db.execute(
            """INSERT INTO local_user_preferences(
                   user_code, front_id, whatsapp_number, whatsapp_message, updated_at
               ) VALUES (?, NULL, ?, ?, ?)
               ON CONFLICT(user_code) DO UPDATE SET
                   whatsapp_number = excluded.whatsapp_number,
                   whatsapp_message = excluded.whatsapp_message,
                   updated_at = excluded.updated_at""",
            (
                user_code.strip().lower(),
                str(number or "").strip(),
                str(message or "Parte diario {id} - {fecha}").strip(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def get_report_document(path: Path, report_code: str) -> dict | None:
    with connect(path) as db:
        row = db.execute(
            "SELECT * FROM daily_reports WHERE report_code = ?", (str(report_code),)
        ).fetchone()
        return dict(row) if row else None


def mark_report_reviewed(path: Path, report_code: str, user_code: str) -> int:
    with connect(path) as db:
        cursor = db.execute(
            """UPDATE daily_reports
               SET document_status = 'Revisado', reviewed_at = ?, reviewed_by = ?,
                   sent_at = NULL, sent_by = NULL, sent_to = NULL, sent_via = NULL,
                   pdf_version = COALESCE(pdf_version, 0) + 1
               WHERE report_code = ?""",
            (
                datetime.now().isoformat(timespec="seconds"),
                str(user_code or "").strip().lower(),
                str(report_code),
            ),
        )
        return int(cursor.rowcount)


def mark_report_sent(
    path: Path,
    report_code: str,
    user_code: str,
    recipient: str = "",
    channel: str = "WhatsApp",
) -> int:
    with connect(path) as db:
        cursor = db.execute(
            """UPDATE daily_reports
               SET document_status = 'Enviado', sent_at = ?, sent_by = ?, sent_to = ?, sent_via = ?
               WHERE report_code = ? AND document_status = 'Revisado'""",
            (
                datetime.now().isoformat(timespec="seconds"),
                str(user_code or "").strip().lower(),
                str(recipient or "").strip(),
                str(channel or "WhatsApp").strip(),
                str(report_code),
            ),
        )
        return int(cursor.rowcount)


def save_report_corrections(
    path: Path,
    report_code: str,
    report_date: str,
    service_order: str,
    parts: list[dict],
    user_code: str,
) -> None:
    """Save a reviewed report atomically and return it to a pending-review state."""
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        report = db.execute(
            "SELECT id, document_status FROM daily_reports WHERE report_code = ?",
            (str(report_code),),
        ).fetchone()
        if report is None:
            raise ValueError(f"No se encontró el parte {report_code}.")
        # Preserve the full previous version in the same transaction as the correction.
        db.execute("""CREATE TABLE IF NOT EXISTS report_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, report_code TEXT NOT NULL,
            saved_at TEXT NOT NULL, saved_by TEXT NOT NULL, was_sent INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL)""")
        previous_report = dict(db.execute("SELECT * FROM daily_reports WHERE id = ?", (report["id"],)).fetchone())
        previous_parts = []
        for previous_part in db.execute("SELECT * FROM partial_parts WHERE report_id = ? ORDER BY id", (report["id"],)).fetchall():
            detail = dict(previous_part)
            detail["allocations"] = [dict(row) for row in db.execute("SELECT * FROM partial_allocations WHERE part_id = ? ORDER BY id", (detail["id"],))]
            detail["inputs"] = [dict(row) for row in db.execute("SELECT * FROM partial_inputs WHERE part_id = ? ORDER BY id", (detail["id"],))]
            previous_parts.append(detail)
        db.execute("INSERT INTO report_revisions(report_code, saved_at, saved_by, was_sent, snapshot_json) VALUES (?, ?, ?, ?, ?)",
            (report_code, datetime.now().isoformat(timespec="seconds"), user_code,
             int(previous_report["document_status"] == "Enviado"),
             json.dumps({"report": previous_report, "parts": previous_parts}, ensure_ascii=False)))
        next_status = "Corregido" if str(report["document_status"]) == "Enviado" else "Borrador"
        now = datetime.now().isoformat(timespec="seconds")
        db.execute(
            """UPDATE daily_reports
               SET report_date = ?, service_order = ?, document_status = ?, modified_at = ?,
                   reviewed_at = NULL, reviewed_by = NULL,
                   sent_at = NULL, sent_by = NULL, sent_to = NULL, sent_via = NULL
               WHERE id = ?""",
            (str(report_date), str(service_order or "").strip(), next_status, now, int(report["id"])),
        )
        valid_ids = {
            int(row[0]) for row in db.execute(
                "SELECT id FROM partial_parts WHERE report_id = ?", (int(report["id"]),)
            )
        }
        submitted_ids = {int(item["id"]) for item in parts}
        if submitted_ids != valid_ids:
            raise ValueError("Las tareas del parte cambiaron mientras se editaban. Volvé a abrir la revisión.")
        for item in parts:
            part_id = int(item["id"])
            quantity = float(item.get("quantity") or 0)
            if not math.isfinite(quantity) or quantity <= 0:
                raise ValueError("La cantidad de cada tarea debe ser mayor que cero.")
            for allocation in item.get("allocations") or []:
                for field in ("quantity", "person_hours"):
                    value = float(allocation.get(field) or 0)
                    if not math.isfinite(value) or value < 0:
                        raise ValueError("Las cantidades y horas no pueden ser negativas ni inválidas.")
                if allocation.get("attendance") == "Ausente" and float(allocation.get("quantity") or 0) > 0:
                    raise ValueError("Una persona ausente no puede tener cantidad asignada.")
                start, end = allocation.get("machine_start_time"), allocation.get("machine_end_time")
                if start is not None and end is not None and float(end) < float(start):
                    raise ValueError("La lectura final del vehículo no puede ser menor que la inicial.")
            cycle = db.execute("SELECT c.allocation_mode FROM work_cycles c JOIN partial_parts p ON p.cycle_id = c.id WHERE p.id = ?", (part_id,)).fetchone()
            if cycle["allocation_mode"] == "Total a repartir" and abs(sum(float(row.get("quantity") or 0) for row in item.get("allocations") or []) - quantity) > 0.01:
                raise ValueError("La suma de las cantidades del personal debe coincidir con la cantidad de la tarea.")
            db.execute(
                """UPDATE partial_parts
                   SET part_date = ?, quantity = ?, notes = ?, crop = ?
                   WHERE id = ? AND report_id = ?""",
                (
                    str(report_date), float(item.get("quantity") or 0),
                    str(item.get("notes") or "").strip(), str(item.get("crop") or "").strip(),
                    part_id, int(report["id"]),
                ),
            )
            previous_front = db.execute(
                "SELECT front_id FROM partial_parts WHERE id = ?", (part_id,)
            ).fetchone()[0]
            allocations = list(item.get("allocations") or [])
            personnel = [str(row.get("personnel_key") or "").strip() for row in allocations]
            if not personnel or any(not value for value in personnel):
                raise ValueError("Cada tarea debe conservar al menos una persona válida.")
            if len(personnel) != len(set(personnel)):
                raise ValueError("Una persona no puede repetirse dentro de la misma tarea.")
            db.execute("DELETE FROM partial_allocations WHERE part_id = ?", (part_id,))
            db.executemany(
                """INSERT INTO partial_allocations(
                       part_id, personnel_key, machine_key, attendance, quantity, replacement_key,
                       front_id, machine_start_time, machine_end_time, person_hours
                   ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)""",
                [
                    (
                        part_id, row["personnel_key"], row.get("machine_key") or None,
                        row.get("attendance") or "Presente", float(row.get("quantity") or 0),
                        int(row.get("front_id") or previous_front),
                        int(row["machine_start_time"]) if row.get("machine_start_time") not in (None, "") else None,
                        int(row["machine_end_time"]) if row.get("machine_end_time") not in (None, "") else None,
                        float(row.get("person_hours") or 0),
                    )
                    for row in allocations
                ],
            )
            inputs = [row for row in (item.get("inputs") or []) if row.get("input_key")]
            db.execute("DELETE FROM partial_inputs WHERE part_id = ?", (part_id,))
            db.executemany(
                "INSERT INTO partial_inputs(part_id, input_key, dose, quantity, unit) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        part_id, row["input_key"], float(row.get("dose") or 0),
                        float(row.get("quantity") or 0), str(row.get("unit") or ""),
                    )
                    for row in inputs
                ],
            )
            first_input = inputs[0] if inputs else {}
            db.execute(
                """UPDATE partial_parts
                   SET input_key = ?, input_dose = ?, input_quantity = ?, input_unit = ?
                   WHERE id = ?""",
                (
                    first_input.get("input_key"), float(first_input.get("dose") or 0),
                    float(first_input.get("quantity") or 0), str(first_input.get("unit") or ""), part_id,
                ),
            )


def add_front_member(path: Path, front_id: int, personnel_key: str, machine_key: str | None) -> None:
    with connect(path) as db:
        db.execute(
            """INSERT INTO front_members(front_id, personnel_key, machine_key)
               VALUES (?, ?, ?)
               ON CONFLICT(front_id, personnel_key)
               DO UPDATE SET machine_key = excluded.machine_key""",
            (front_id, personnel_key, machine_key),
        )


def list_front_members(path: Path, front_id: int) -> list[dict]:
    return rows(path, "SELECT * FROM front_members WHERE front_id = ? ORDER BY id", (front_id,))


def remove_front_member(path: Path, member_id: int) -> None:
    with connect(path) as db:
        db.execute("DELETE FROM front_members WHERE id = ?", (member_id,))


def create_cycle(
    path: Path,
    lot_key: str,
    operation_key: str,
    target_quantity: float,
    unit: str,
    allocation_mode: str,
    started_on: str,
    input_key: str | None = None,
    input_dose: float = 0,
    input_unit: str = "",
) -> int:
    with connect(path) as db:
        cycle_no = db.execute(
            "SELECT COALESCE(MAX(cycle_no), 0) + 1 FROM work_cycles WHERE lot_key = ? AND operation_key = ?",
            (lot_key, operation_key),
        ).fetchone()[0]
        cursor = db.execute(
            """INSERT INTO work_cycles(
                   lot_key, operation_key, cycle_no, target_quantity, unit,
                   allocation_mode, started_on, input_key, input_dose, input_unit
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lot_key, operation_key, cycle_no, target_quantity, unit,
                allocation_mode, started_on, input_key, float(input_dose), input_unit,
            ),
        )
        return int(cursor.lastrowid)


def update_cycle_input(
    path: Path,
    cycle_id: int,
    input_key: str | None,
    input_dose: float,
    input_unit: str,
) -> None:
    with connect(path) as db:
        db.execute(
            "UPDATE work_cycles SET input_key = ?, input_dose = ?, input_unit = ? WHERE id = ?",
            (input_key, float(input_dose), input_unit, cycle_id),
        )


def list_cycles(path: Path, status: str | None = None) -> list[dict]:
    condition = "WHERE c.status = ?" if status else ""
    parameters = (status,) if status else ()
    return rows(
        path,
        f"""SELECT c.*, COALESCE(SUM(p.quantity), 0) AS accumulated,
                   COALESCE(SUM(p.input_quantity), 0) AS input_accumulated
            FROM work_cycles c
            LEFT JOIN partial_parts p ON p.cycle_id = c.id
            {condition}
            GROUP BY c.id
            ORDER BY c.status, c.started_on DESC, c.id DESC""",
        parameters,
    )


def create_partial(
    path: Path,
    cycle_id: int,
    front_id: int,
    part_date: str,
    quantity: float,
    notes: str,
    allocations: list[dict],
    input_key: str | None = None,
    input_dose: float = 0,
    input_quantity: float = 0,
    input_unit: str = "",
) -> int:
    with connect(path) as db:
        cursor = db.execute(
            """INSERT INTO partial_parts(
                   cycle_id, front_id, part_date, quantity, notes, created_at,
                   input_key, input_dose, input_quantity, input_unit
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cycle_id, front_id, part_date, quantity, notes,
                datetime.now().isoformat(timespec="seconds"), input_key,
                float(input_dose), float(input_quantity), input_unit,
            ),
        )
        part_id = int(cursor.lastrowid)
        db.executemany(
            """INSERT INTO partial_allocations(
                   part_id, personnel_key, machine_key, attendance, quantity, replacement_key, front_id,
                   machine_start_time, machine_end_time, person_hours
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    part_id,
                    item["personnel_key"],
                    item.get("machine_key"),
                    item["attendance"],
                    float(item["quantity"]),
                    item.get("replacement_key") or None,
                    item.get("front_id") or front_id,
                    item.get("machine_start_time") or None,
                    item.get("machine_end_time") or None,
                    float(item.get("person_hours", 12) or 0),
                )
                for item in allocations
            ],
        )
        return part_id


def close_cycle(path: Path, cycle_id: int) -> None:
    with connect(path) as db:
        db.execute(
            "UPDATE work_cycles SET status = 'Cerrado', closed_on = ? WHERE id = ?",
            (datetime.now().date().isoformat(), cycle_id),
        )


def list_partials(path: Path, cycle_id: int) -> list[dict]:
    return rows(
        path,
        """SELECT p.*,
                  COALESCE(
                      (SELECT GROUP_CONCAT(name, ', ') FROM (
                          SELECT DISTINCT f2.name AS name
                          FROM partial_allocations a2
                          JOIN fronts f2 ON f2.id = a2.front_id
                          WHERE a2.part_id = p.id
                          ORDER BY f2.name
                      )),
                      f.name
                  ) AS front_name,
                  (SELECT GROUP_CONCAT(input_key || ': ' || printf('%.1f', quantity) || ' ' || unit, ' | ')
                   FROM partial_inputs i WHERE i.part_id = p.id ORDER BY i.id) AS inputs_summary
           FROM partial_parts p JOIN fronts f ON f.id = p.front_id
           WHERE p.cycle_id = ? ORDER BY p.part_date, p.id""",
        (cycle_id,),
    )


def list_all_partials(path: Path) -> list[dict]:
    return rows(
        path,
        """SELECT p.*, c.lot_key, c.operation_key, c.cycle_no,
                  COALESCE(
                      (SELECT GROUP_CONCAT(name, ', ') FROM (
                          SELECT DISTINCT f2.name AS name
                          FROM partial_allocations a2
                          JOIN fronts f2 ON f2.id = a2.front_id
                          WHERE a2.part_id = p.id
                          ORDER BY f2.name
                      )),
                      f.name
                  ) AS front_name,
                  (SELECT GROUP_CONCAT(input_key || ': ' || printf('%.1f', quantity) || ' ' || unit, ' | ')
                   FROM partial_inputs i WHERE i.part_id = p.id ORDER BY i.id) AS inputs_summary
           FROM partial_parts p
           JOIN work_cycles c ON c.id = p.cycle_id
           JOIN fronts f ON f.id = p.front_id
           ORDER BY p.part_date DESC, p.id DESC""",
    )


def delete_partials(path: Path, part_ids: list[int]) -> int:
    identifiers = [int(part_id) for part_id in part_ids]
    if not identifiers:
        return 0
    placeholders = ",".join("?" for _ in identifiers)
    with connect(path) as db:
        cursor = db.execute(f"DELETE FROM partial_parts WHERE id IN ({placeholders})", tuple(identifiers))
        return int(cursor.rowcount)


def get_or_create_manual_front(path: Path) -> int:
    with connect(path) as db:
        row = db.execute("SELECT id FROM fronts WHERE name = '__MANUAL__'").fetchone()
        if row:
            return int(row[0])
        cursor = db.execute(
            "INSERT INTO fronts(name, active, created_at) VALUES ('__MANUAL__', 0, ?)",
            (datetime.now().isoformat(timespec="seconds"),),
        )
        return int(cursor.lastrowid)
