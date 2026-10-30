from __future__ import annotations

from io import BytesIO
import sqlite3
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


GREEN = colors.HexColor("#526747")
LIGHT_GREEN = colors.HexColor("#E9EEE5")
PALE_GREEN = colors.HexColor("#F4F6F1")
GRID = colors.HexColor("#AEB8AA")
TEXT = colors.HexColor("#26322A")
MUTED = colors.HexColor("#687168")


def _value(record, *names, default=""):
    if not record:
        return default
    lowered = {str(key).lower(): value for key, value in record.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return default


def _fmt_number(value):
    number = float(value or 0)
    return f"{number:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _vehicle_unit(machine):
    explicit = str(_value(machine, "UNIDAD", "UNIDAD_MEDIDA", "U.MED", default="")).strip()
    if explicit:
        return explicit.upper()
    group = str(_value(machine, "Grupo Operativo", "GRUPO_OPERATIVO", default="")).upper()
    return "KM" if any(word in group for word in ("CAMIONETA", "CAMION", "UTILITARIO", "VEHICULO")) else "HS"


def _operation_name(operation, fallback):
    direct = _value(operation, "Operacion", "DESCRIPCION", "TAREA", default="")
    if direct:
        return str(direct)
    for key, value in (operation or {}).items():
        if str(key).lower().startswith("operaci") and value not in (None, ""):
            return str(value)
    return str(fallback)


def _task_uses_person_hours(unit):
    normalized = str(unit or "").strip().upper().replace(".", "")
    return normalized not in {
        "JN", "JORNAL", "JORNALES", "HS", "H", "HR", "HRS", "HORA", "HORAS",
    }


def _load_report(database_path: Path, report_code: str):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        report = connection.execute(
            "SELECT * FROM daily_reports WHERE report_code = ?", (report_code,)
        ).fetchone()
        parts = connection.execute(
            """SELECT p.*, c.lot_key, c.operation_key, c.unit, f.name AS front_name
               FROM partial_parts p
               JOIN work_cycles c ON c.id = p.cycle_id
               LEFT JOIN fronts f ON f.id = p.front_id
               WHERE p.report_code = ? OR p.part_code = ?
               ORDER BY COALESCE(p.line_no, p.id), p.id""",
            (report_code, report_code),
        ).fetchall()
        if not parts:
            raise ValueError(f"No se encontró el parte {report_code}.")
        result = []
        for part in parts:
            allocations = connection.execute(
                "SELECT * FROM partial_allocations WHERE part_id = ? ORDER BY id", (part["id"],)
            ).fetchall()
            inputs = connection.execute(
                "SELECT * FROM partial_inputs WHERE part_id = ? ORDER BY id", (part["id"],)
            ).fetchall()
            result.append((dict(part), [dict(row) for row in allocations], [dict(row) for row in inputs]))
        return dict(report) if report else {}, result
    finally:
        connection.close()


def build_daily_report_pdf(
    database_path,
    report_code,
    *,
    people_by_key,
    machines_by_key,
    lots_by_key,
    operations_by_key,
    inputs_by_key,
):
    """Return a compact, printable A4-landscape daily report as PDF bytes."""
    report, parts = _load_report(Path(database_path), str(report_code))
    buffer = BytesIO()
    page_size = landscape(A4)
    document = BaseDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=7 * mm,
        rightMargin=7 * mm,
        topMargin=18 * mm,
        bottomMargin=9 * mm,
        title=f"Parte diario {report_code}",
        author="Asistente Parte Diario",
    )
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )

    def draw_header(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(GREEN)
        canvas.rect(0, page_size[1] - 14 * mm, page_size[0], 14 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(8 * mm, page_size[1] - 8.8 * mm, "PARTE DIARIO")
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawRightString(page_size[0] - 8 * mm, page_size[1] - 7 * mm, f"ID {report_code}")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            page_size[0] - 8 * mm,
            page_size[1] - 11 * mm,
            f"Fecha {report.get('report_date', parts[0][0]['part_date'])}  |  Página {doc.page}",
        )
        canvas.setStrokeColor(GRID)
        canvas.line(7 * mm, 7 * mm, page_size[0] - 7 * mm, 7 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(7 * mm, 4.2 * mm, "Generado por Asistente Parte Diario")
        canvas.restoreState()

    document.addPageTemplates(PageTemplate(id="daily", frames=[frame], onPage=draw_header))
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "compact", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2,
        leading=8.4, textColor=TEXT, spaceAfter=0,
    )
    small = ParagraphStyle("small", parent=normal, fontSize=6.7, leading=7.8)
    section = ParagraphStyle(
        "section", parent=normal, fontName="Helvetica-Bold", fontSize=7.8,
        leading=9, textColor=colors.white, alignment=TA_LEFT,
    )
    header_cell = ParagraphStyle(
        "header_cell", parent=small, fontName="Helvetica-Bold", textColor=colors.white,
        alignment=TA_LEFT,
    )
    center = ParagraphStyle("center", parent=small, alignment=TA_LEFT)

    front_names = sorted({part.get("front_name") or "Manual" for part, _, _ in parts})
    locations = []
    for part, _, _ in parts:
        lot = lots_by_key.get(part["lot_key"], {})
        location = (
            f"{_value(lot, 'FINCA', default='-')} "
            f"{_value(lot, 'ID_Lote', 'LOTE', default=part['lot_key'])}"
        )
        if location not in locations:
            locations.append(location)
    metadata = [
        ["Frente", ", ".join("Manual" if name == "__MANUAL__" else name for name in front_names), "Ubicaciones", "; ".join(locations)],
    ]
    metadata_table = Table(
        metadata, colWidths=[20 * mm, 102 * mm, 24 * mm, 136 * mm],
        rowHeights=8 * mm, hAlign="LEFT",
    )
    metadata_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREEN),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT_GREEN),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
        ("GRID", (0, 0), (-1, -1), .35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story = [metadata_table, Spacer(1, 2.5 * mm)]

    for task_number, (part, allocations, inputs) in enumerate(parts, start=1):
        lot = lots_by_key.get(part["lot_key"], {})
        operation = operations_by_key.get(part["operation_key"], {})
        operation_code = str(_value(operation, "ID_Operacion", "ID_OPERACION", default=part["operation_key"]))
        operation_name = _operation_name(operation, operation_code)
        farm = str(_value(lot, "FINCA", default="-"))
        lot_id = str(_value(lot, "ID_Lote", "LOTE", default=part["lot_key"]))
        crop = str(part.get("crop") or _value(lot, "CULTIVO", default="-"))
        person_hours_enabled = _task_uses_person_hours(part["unit"])
        band_text = (
            f"T{task_number}  |  {operation_code} - {operation_name}  |  "
            f"{farm} / lote {lot_id}  |  {_fmt_number(part['quantity'])} {part['unit']}"
        )
        box_label = ParagraphStyle(
            f"box_label_{task_number}", parent=small, fontName="Helvetica-Bold",
            fontSize=6.5, leading=7.2, textColor=TEXT, alignment=TA_LEFT,
        )
        band = Table(
            [[
                Paragraph("OS", box_label), "",
                Paragraph("CULTIVO", box_label), Paragraph(crop, small),
                Paragraph(band_text, section),
            ]],
            colWidths=[9 * mm, 18 * mm, 15 * mm, 30 * mm, 210 * mm],
            rowHeights=7 * mm,
            hAlign="LEFT",
        )
        band.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), LIGHT_GREEN),
            ("BACKGROUND", (2, 0), (2, 0), LIGHT_GREEN),
            ("BACKGROUND", (1, 0), (1, 0), colors.white),
            ("BACKGROUND", (3, 0), (3, 0), colors.white),
            ("BACKGROUND", (4, 0), (4, 0), GREEN),
            ("BOX", (0, 0), (3, 0), .45, GRID),
            ("INNERGRID", (0, 0), (3, 0), .35, GRID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (3, 0), 3),
            ("LEFTPADDING", (4, 0), (4, 0), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        rows = [
            [
                Paragraph("PERSONAL", header_cell), "", "", "", "",
                Paragraph("VEHÍCULO / MÁQUINA", header_cell), "", "", "", "", "",
            ],
            [
                Paragraph("Legajo", header_cell), Paragraph("Apellido y nombre", header_cell),
                Paragraph("Hs persona", header_cell), Paragraph("Cant. tarea", header_cell),
                Paragraph("U.M.", header_cell), Paragraph("ID vehículo", header_cell),
                Paragraph("Marca", header_cell), Paragraph("U.M. veh.", header_cell),
                Paragraph("H/Km inicio", header_cell), Paragraph("H/Km fin", header_cell),
                Paragraph("Dif.", header_cell),
            ],
        ]
        for allocation in allocations:
            person = people_by_key.get(str(allocation["personnel_key"]), {})
            machine_key = str(allocation.get("machine_key") or "")
            machine = machines_by_key.get(machine_key, {})
            start = allocation.get("machine_start_time")
            end = allocation.get("machine_end_time")
            difference = int(end) - int(start) if start is not None and end is not None else ""
            rows.append([
                Paragraph(str(allocation["personnel_key"]), small),
                Paragraph(str(_value(person, "EMPLEADO", "APELLIDO Y NOMBRE", default=allocation["personnel_key"])), small),
                Paragraph(
                    _fmt_number(allocation.get("person_hours", 12)) if person_hours_enabled else "-",
                    center,
                ),
                Paragraph(_fmt_number(allocation.get("quantity", 0)), center),
                Paragraph(str(part["unit"]), center),
                Paragraph(
                    str(_value(machine, "ID_Equipo", "ID EQUIPO", default=machine_key)) if machine_key else "-",
                    center,
                ),
                Paragraph(str(_value(machine, "Marca", "MARCA", default="-")) if machine_key else "-", small),
                Paragraph(_vehicle_unit(machine) if machine_key else "-", center),
                Paragraph(str(start) if start is not None else "-", center),
                Paragraph(str(end) if end is not None else "-", center),
                Paragraph(str(difference) if difference != "" else "-", center),
            ])
        staff_table = Table(
            rows,
            colWidths=[18 * mm, 62 * mm, 18 * mm, 22 * mm, 13 * mm, 24 * mm, 45 * mm, 18 * mm, 24 * mm, 24 * mm, 14 * mm],
            repeatRows=2,
            hAlign="LEFT",
        )
        staff_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#71816A")),
            ("SPAN", (0, 0), (4, 0)),
            ("SPAN", (5, 0), (10, 0)),
            ("LINEBEFORE", (5, 0), (5, -1), .8, GREEN),
            ("ROWBACKGROUNDS", (0, 2), (-1, -1), [colors.white, PALE_GREEN]),
            ("GRID", (0, 0), (-1, -1), .3, GRID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        task_block = [band, staff_table]
        if inputs:
            input_title_style = ParagraphStyle(
                f"input_title_{task_number}", parent=normal, fontName="Helvetica-Bold",
                fontSize=7.2, leading=8.2, textColor=TEXT,
            )
            input_band = Table(
                [[Paragraph(f"Insumos de T{task_number}", input_title_style)]],
                colWidths=[170 * mm], rowHeights=5.5 * mm, hAlign="LEFT",
            )
            input_band.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN),
                ("BOX", (0, 0), (-1, -1), .35, GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))
            input_rows = [[
                Paragraph("Producto", header_cell), Paragraph("Dosis", header_cell),
                Paragraph("Cantidad", header_cell), Paragraph("U.M.", header_cell),
            ]]
            for item in inputs:
                product = inputs_by_key.get(str(item["input_key"]), {})
                input_rows.append([
                    Paragraph(str(_value(product, "DESCRIPCION", "INSUMO", "NOMBRE", default=item["input_key"])), small),
                    Paragraph(_fmt_number(item.get("dose", 0)), center),
                    Paragraph(_fmt_number(item.get("quantity", 0)), center),
                    Paragraph(str(item.get("unit") or "-"), center),
                ])
            input_table = Table(
                input_rows,
                colWidths=[105 * mm, 24 * mm, 27 * mm, 14 * mm],
                repeatRows=1,
                hAlign="LEFT",
            )
            input_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#71816A")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GREEN]),
                ("GRID", (0, 0), (-1, -1), .3, GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ]))
            task_block.extend([input_band, input_table])
        task_block.append(Spacer(1, 2.3 * mm))
        story.append(KeepTogether(task_block))

    story.extend([
        Spacer(1, 3 * mm),
        Table(
            [[Paragraph("Observaciones", normal), "", Paragraph("Firma responsable", normal), ""]],
            colWidths=[24 * mm, 141 * mm, 30 * mm, 87 * mm],
            rowHeights=9 * mm,
            style=TableStyle([
                ("LINEBELOW", (1, 0), (1, 0), .4, GRID),
                ("LINEBELOW", (3, 0), (3, 0), .4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ]),
        ),
    ])
    document.build(story)
    return buffer.getvalue()

