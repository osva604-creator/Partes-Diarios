from datetime import date
from pathlib import Path
from contextlib import closing
import base64
import csv
from html import escape
import re
import sqlite3
from urllib.parse import quote

import pandas as pd
import streamlit as st

from app_core import (
    filter_machines_for_operation,
    load_all_sources,
    normalize,
    operation_machine_groups,
    redistribute_rows,
)
from quick_entry import interpret_part_text, convert_input_quantity
import app_store
from app_store import (
    add_front_member,
    close_cycle,
    create_front,
    delete_partials,
    get_or_create_manual_front,
    initialize,
    list_cycles,
    list_front_members,
    list_fronts,
    list_partials,
    list_all_partials,
    remove_front_member,
    get_user_default_person_hours,
    get_user_whatsapp_preferences,
    get_report_document,
    mark_report_reviewed,
    mark_report_sent,
    save_report_corrections,
    save_user_default_person_hours,
    save_user_whatsapp_preferences,
)
import pdf_report


_DAILY_GRID_COMPONENT = st.components.v2.component(
    "daily_part_grid",
    html="<div id='daily-grid'></div>",
    css=r"""
*{box-sizing:border-box} .grid-shell{color:var(--st-text-color,#25312a);font:14px var(--st-font,Arial,sans-serif);border:1px solid var(--st-dataframe-border-color,#e0e3d9);border-radius:10px;background:var(--st-secondary-background-color,#fff);overflow:hidden}
.grid-scroll{height:434px;overflow:auto;scrollbar-width:thin;scrollbar-color:#c5ccbd transparent}table{width:100%;min-width:1380px;border-collapse:separate;border-spacing:0;table-layout:fixed}th{position:sticky;top:0;z-index:2;background:var(--st-dataframe-header-background-color,#eef0e8);color:var(--st-dataframe-header-text-color,#334438);font-weight:600;font-size:12px;height:34px;text-align:left;border-bottom:1px solid var(--st-border-color,#dadcd2)}td{height:32px;border-bottom:1px solid color-mix(in srgb,var(--st-border-color,#dadcd2) 65%,transparent);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}th,td{padding:0 11px}tbody tr:hover,tbody tr:focus-within{background:color-mix(in srgb,var(--st-primary-color,#526747) 7%,var(--st-secondary-background-color,#fff))}tbody tr.selected{background:color-mix(in srgb,var(--st-primary-color,#526747) 12%,var(--st-secondary-background-color,#fff))}.check-cell{position:sticky;left:0;z-index:1;width:68px;text-align:center;background:var(--st-secondary-background-color,#fff);padding:0 8px}th.check-cell{z-index:3;background:var(--st-dataframe-header-background-color,#eef0e8)}tr.selected .check-cell{background:color-mix(in srgb,var(--st-primary-color,#526747) 12%,var(--st-secondary-background-color,#fff))}input[type=checkbox]{width:15px;height:15px;accent-color:var(--st-primary-color,#526747);cursor:pointer;vertical-align:middle}.sort-button{border:0;background:none;font:inherit;color:inherit;cursor:pointer;width:100%;text-align:left;white-space:nowrap;padding:7px 0}.sort-button:focus-visible,.detail-button:focus-visible,.csv-button:focus-visible{outline:2px solid var(--st-primary-color,#526747);outline-offset:2px;border-radius:4px}.sort-indicator{margin-left:6px;font-size:11px;opacity:.5}.numeric{text-align:right;font-variant-numeric:tabular-nums}.detail-button{border:0;background:none;display:inline-flex;align-items:center;gap:7px;max-width:100%;font:inherit;color:var(--st-link-color,#3d5b43);padding:0;cursor:pointer;white-space:nowrap;vertical-align:middle}.detail-button span{overflow:hidden;text-overflow:ellipsis;text-decoration:underline;text-underline-offset:3px}.detail-button svg{flex:none;width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.status{display:inline-block;border-radius:6px;padding:3px 9px;font-size:12px;line-height:1.1}.status.open,.status.draft{background:var(--st-orange-background-color,#faedd9);color:var(--st-orange-text-color,#865b2a)}.status.reviewed{background:#e7f0df;color:#44613d}.status.closed{background:var(--st-green-background-color,#dcebd7);color:var(--st-green-text-color,#2f5638);font-weight:600}.status.sent{background:#dcecff;color:#174b85;font-weight:600}.progress{display:flex;align-items:center;gap:7px}.progress-track{flex:1;height:7px;background:color-mix(in srgb,var(--st-border-color,#dadcd2) 65%,transparent);border-radius:99px;overflow:hidden}.progress-fill{height:100%;background:var(--st-primary-color,#526747);border-radius:99px}.progress small{min-width:32px;text-align:right;font-size:11px}.grid-footer{height:34px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 12px;color:color-mix(in srgb,var(--st-text-color,#25312a) 75%,transparent);font-size:12px;background:var(--st-secondary-background-color,#fff)}.csv-button{border:0;background:none;color:inherit;font:inherit;cursor:pointer;display:flex;gap:5px;align-items:center;padding:4px}.csv-button svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.7}.grid-popover{position:fixed;inset:auto;margin:0;z-index:10000;max-width:min(420px,calc(100vw - 24px));width:max-content;min-width:210px;max-height:min(340px,calc(100vh - 24px));overflow:auto;background:var(--st-secondary-background-color,#fff);color:var(--st-text-color,#25312a);border:1px solid var(--st-border-color,#dadcd2);border-radius:9px;box-shadow:0 7px 22px rgba(24,44,30,.18);padding:11px 13px;font:13px/1.6 var(--st-font,Arial,sans-serif)}.grid-popover:not(:popover-open){display:none}.grid-popover.fallback-open{display:block}.grid-popover strong{display:block;font-size:12px;margin-bottom:5px;font-weight:600}.grid-popover ul{list-style:none;padding:0;margin:0}.grid-popover li{padding:3px 0;white-space:normal;overflow-wrap:anywhere}.grid-empty{text-align:center;padding:45px 16px;color:color-mix(in srgb,var(--st-text-color,#25312a) 70%,transparent)}
""",
    js=r"""
const instances = new WeakMap();
export default function(component){
  const {parentElement,data,setStateValue}=component;
  const root=parentElement.querySelector('#daily-grid');
  if(!root)return;
  const doc=root.ownerDocument;
  const win=doc.defaultView;
  const previous=instances.get(root)||{sort:null,direction:1,left:0,top:0};
  const records=Array.isArray(data.rows)?data.rows:[];
  const columns=Array.isArray(data.columns)?data.columns:[];
  const selected=new Set((data.selected_ids||[]).map(Number).filter(id=>records.some(r=>Number(r._part_id)===id)));
  const peopleIcon='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/></svg>';
  const downloadIcon='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>';
  root.replaceChildren();
  const shell=doc.createElement('div');shell.className='grid-shell';root.append(shell);
  const scroll=doc.createElement('div');scroll.className='grid-scroll';scroll.tabIndex=0;scroll.setAttribute('aria-label','Parte diario: tabla desplazable de doce filas visibles');shell.append(scroll);
  const table=doc.createElement('table');table.setAttribute('aria-label','Parte diario');scroll.append(table);
  const head=doc.createElement('thead');table.append(head);
  const headRow=doc.createElement('tr');head.append(headRow);
  const body=doc.createElement('tbody');table.append(body);
  const footer=doc.createElement('div');footer.className='grid-footer';shell.append(footer);
  const count=doc.createElement('span');footer.append(count);
  const csv=doc.createElement('button');csv.type='button';csv.className='csv-button';csv.innerHTML=downloadIcon;const csvText=doc.createElement('span');csvText.textContent='Descargar CSV';csv.append(csvText);footer.append(csv);
  const pop=doc.createElement('div');pop.className='grid-popover';pop.setAttribute('popover','manual');pop.setAttribute('role','dialog');pop.setAttribute('aria-label','Detalle del registro');root.append(pop);
  let anchor=null,pinned=false,closeTimer=null;
  function closePopup(){clearTimeout(closeTimer);if(anchor)anchor.setAttribute('aria-expanded','false');try{pop.hidePopover();}catch(e){}pop.classList.remove('fallback-open');anchor=null;pinned=false;}
  function openPopup(button,items,title,pin=false){clearTimeout(closeTimer);if(anchor&&anchor!==button)anchor.setAttribute('aria-expanded','false');anchor=button;pinned=pin;pop.replaceChildren();const h=doc.createElement('strong');h.textContent=title;pop.append(h);const list=doc.createElement('ul');for(const line of items){const li=doc.createElement('li');li.textContent=String(line);list.append(li);}pop.append(list);button.setAttribute('aria-expanded','true');try{pop.showPopover();}catch(e){pop.classList.add('fallback-open');}const rect=button.getBoundingClientRect();const width=pop.offsetWidth||300;const height=pop.offsetHeight||120;pop.style.left=Math.max(8,Math.min(rect.left,win.innerWidth-width-8))+'px';const below=rect.bottom+7;pop.style.top=Math.max(8,below+height<win.innerHeight-8?below:rect.top-height-7)+'px';}
  function laterClose(){if(!pinned)closeTimer=setTimeout(closePopup,180);}
  pop.addEventListener('mouseenter',()=>clearTimeout(closeTimer));pop.addEventListener('mouseleave',laterClose);
  function detailButton(label,items,title,icon=false){const b=doc.createElement('button');b.type='button';b.className='detail-button';b.setAttribute('aria-haspopup','dialog');b.setAttribute('aria-expanded','false');b.setAttribute('aria-label',label+': ver '+title.toLowerCase());if(icon)b.innerHTML=peopleIcon;const s=doc.createElement('span');s.textContent=label;b.append(s);b.addEventListener('click',e=>{e.stopPropagation();openPopup(b,items,title,true);});b.addEventListener('dblclick',e=>{e.preventDefault();e.stopPropagation();openPopup(b,items,title,true);});return b;}
  const widths={'Seleccionar':68,'Estado':155,'Aviso':60,'ID parte':112,'Fecha':106,'Finca':120,'Lote':78,'Tarea':220,'Ciclo':64,'Unidad':65,'Cantidad parte':108,'Objetivo':100,'Restante':100,'Avance':130,'Insumo':185,'Unidad insumo':90,'Cantidad insumo':115,'Dosis':90,'Frente':115,'Personal y vehículo':215,'Observaciones':230};
  const numeric=new Set(['Cantidad parte','Objetivo','Restante','Cantidad insumo','Dosis','Ciclo']);
  const fmt=new Intl.NumberFormat('es-AR',{maximumFractionDigits:1});
  const nfDose=new Intl.NumberFormat('es-AR',{maximumFractionDigits:3});
  function plain(value){return value==null?'':Array.isArray(value)?value.join(', '):String(value);}
  function dateText(value){const t=plain(value);return /^\d{4}-\d{2}-\d{2}$/.test(t)?t.slice(8,10)+'/'+t.slice(5,7)+'/'+t.slice(0,4):t;}
  function footerText(){const start=records.length?Math.min(records.length,Math.floor(scroll.scrollTop/32)+1):0;const end=Math.min(records.length,start+11);count.textContent='Mostrando '+start+'–'+end+' de '+records.length+' registros'+(selected.size?' · '+selected.size+' seleccionado(s)':'');}
  let selectAll;
  function syncChecks(){for(const input of body.querySelectorAll('input[type="checkbox"]')){input.checked=selected.has(Number(input.dataset.id));input.closest('tr').classList.toggle('selected',input.checked);}if(selectAll){selectAll.checked=records.length>0&&selected.size===records.length;selectAll.indeterminate=selected.size>0&&selected.size<records.length;selectAll.disabled=!records.length;}footerText();}
  function emit(){syncChecks();setStateValue('selected_ids',Array.from(selected).sort((a,b)=>a-b));}
  for(const column of columns){const th=doc.createElement('th');th.style.width=(widths[column]||120)+'px';if(column==='Seleccionar'){th.className='check-cell';selectAll=doc.createElement('input');selectAll.type='checkbox';selectAll.setAttribute('aria-label','Seleccionar todos los registros filtrados');selectAll.addEventListener('change',()=>{selected.clear();if(selectAll.checked)for(const r of records)selected.add(Number(r._part_id));emit();});th.append(selectAll);}else{const b=doc.createElement('button');b.type='button';b.className='sort-button';b.textContent=column;const indicator=doc.createElement('span');indicator.className='sort-indicator';indicator.textContent=previous.sort===column?(previous.direction===1?'↑':'↓'):'↕';b.append(indicator);b.setAttribute('aria-label','Ordenar por '+column);b.addEventListener('click',()=>{previous.direction=previous.sort===column?-previous.direction:1;previous.sort=column;closePopup();renderRows();for(const h of headRow.querySelectorAll('th')){const x=h.querySelector('.sort-indicator');if(x)x.textContent=h===th?(previous.direction===1?'↑':'↓'):'↕';} });th.append(b);}headRow.append(th);}
  function renderRows(){body.replaceChildren();let rows=records.slice();if(previous.sort){const c=previous.sort;rows.sort((a,b)=>{const va=a[c],vb=b[c];if(typeof va==='number'&&typeof vb==='number')return (va-vb)*previous.direction;return plain(va).localeCompare(plain(vb),'es',{numeric:true,sensitivity:'base'})*previous.direction;});}for(const record of rows){const tr=doc.createElement('tr');tr.dataset.partId=String(record._part_id);for(const c of columns){const td=doc.createElement('td');const value=record[c];if(c==='Seleccionar'){td.className='check-cell';const box=doc.createElement('input');box.type='checkbox';box.dataset.id=String(record._part_id);box.setAttribute('aria-label','Seleccionar '+plain(record['ID parte'])+' · '+dateText(record.Fecha)+' · '+plain(record.Tarea));box.addEventListener('change',()=>{if(box.checked)selected.add(Number(record._part_id));else selected.delete(Number(record._part_id));emit();});td.append(box);}else if(c==='Personal y vehículo'){const info=record._staff;td.append(info&&info.lines.length?detailButton(info.summary,info.lines,'Personal y vehículo',true):doc.createTextNode('—'));}else if(c==='Insumo'&&record._inputs&&record._inputs.lines.length){td.append(detailButton(record._inputs.summary,record._inputs.lines,'Insumos del parte'));}else if(c==='Aviso'&&value){td.append(detailButton('⚠',[plain(value)],'Aviso del objetivo'));}else if(c==='Estado'){const status=plain(value);const badge=doc.createElement('span');badge.className='status '+(status==='Enviado'?'sent':status==='Pendiente de envío'?'closed':'open');badge.textContent=status;td.append(badge);}else if(c==='Avance'&&value!=null){const p=doc.createElement('div');p.className='progress';const track=doc.createElement('div');track.className='progress-track';const fill=doc.createElement('div');fill.className='progress-fill';fill.style.width=Math.max(0,Math.min(100,Number(value)*100))+'%';track.append(fill);const label=doc.createElement('small');label.textContent=Math.round(Number(value)*100)+'%';p.append(track,label);td.append(p);}else if(c==='Fecha'){td.textContent=dateText(value);}else if(numeric.has(c)&&value!=null&&typeof value==='number'){td.className='numeric';td.textContent=(c==='Dosis'?nfDose:fmt).format(value);}else{td.textContent=value==null?'—':plain(value);}if(!td.querySelector('button'))td.title=td.textContent;tr.append(td);}body.append(tr);}if(!rows.length){const tr=doc.createElement('tr');const td=doc.createElement('td');td.colSpan=columns.length;td.className='grid-empty';td.textContent='No hay partes que coincidan con la búsqueda.';tr.append(td);body.append(tr);}syncChecks();}
  scroll.addEventListener('scroll',()=>{previous.left=scroll.scrollLeft;previous.top=scroll.scrollTop;closePopup();footerText();});
  function outside(e){const path=e.composedPath();if(anchor&&!path.includes(anchor)&&!path.includes(pop))closePopup();}
  function keydown(e){if(e.key==='Escape'&&anchor){closePopup();}}
  doc.addEventListener('pointerdown',outside);doc.addEventListener('keydown',keydown);
  csv.addEventListener('click',()=>{const cols=columns.filter(c=>c!=='Seleccionar');function escape(value){let text=plain(value);if(/^[=+@-]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';}const content='\ufeff'+[cols.map(escape).join(';'),...records.map(r=>cols.map(c=>escape(r[c])).join(';'))].join('\r\n');const url=URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8;'}));const a=doc.createElement('a');a.href=url;a.download='parte_diario.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),500);});
  renderRows();scroll.scrollLeft=previous.left;scroll.scrollTop=previous.top;footerText();instances.set(root,previous);
  return ()=>{clearTimeout(closeTimer);closePopup();doc.removeEventListener('pointerdown',outside);doc.removeEventListener('keydown',keydown);};
}
""",
)

_WHATSAPP_SEND_COMPONENT = st.components.v2.component(
    "whatsapp_send_button",
    html="<button id='send-whatsapp' type='button'>Enviar PDF por WhatsApp</button>",
    css=r"""
#send-whatsapp{width:100%;min-height:40px;border:0;border-radius:8px;padding:9px 16px;
background:#1f6f43;color:white;font:600 14px var(--st-font,Arial,sans-serif);cursor:pointer}
#send-whatsapp:hover{background:#185b36}#send-whatsapp:focus-visible{outline:3px solid #8dc6a4;outline-offset:2px}
""",
    js=r"""
export default function(component){
  const {parentElement,data,setStateValue}=component;
  const button=parentElement.querySelector('#send-whatsapp');
  if(!button)return;
  button.textContent=data.label||'Enviar PDF por WhatsApp';
  button.onclick=async()=>{
    button.disabled=true;
    try{
      const raw=atob(data.pdf_b64||'');
      const bytes=new Uint8Array(raw.length);
      for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
      const file=new File([bytes],data.filename,{type:'application/pdf'});
      if(navigator.canShare&&navigator.canShare({files:[file]})){
        await navigator.share({files:[file],text:data.message||''});
      }else{
        const objectUrl=URL.createObjectURL(file);
        const download=parentElement.ownerDocument.createElement('a');
        download.href=objectUrl;download.download=data.filename;download.click();
        setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);
        window.open(data.url,'_blank','noopener,noreferrer');
      }
      setStateValue('sent_token',data.token);
      button.textContent='Envío preparado';
    }catch(error){
      button.disabled=false;
      button.textContent='Reintentar envío por WhatsApp';
    }
  };
}
""",
)


def whatsapp_send_button(url, token, pdf_data, filename, message, *, key, label="Enviar PDF por WhatsApp"):
    result = _WHATSAPP_SEND_COMPONENT(
        data={
            "url": url, "token": token, "label": label,
            "pdf_b64": base64.b64encode(pdf_data).decode("ascii"),
            "filename": filename, "message": message,
        },
        key=key, width="stretch", height="content", default={"sent_token": ""},
        on_sent_token_change=lambda: None,
    )
    return str(getattr(result, "sent_token", "") or "") == str(token)


# Compact daily table: independent presentation and selection state.
def daily_list_lines(value):
    return [re.sub(r"^\s*-\s*", "", line).strip() for line in str(value or "").splitlines() if line.strip()]


def staff_cell_info(value):
    lines = daily_list_lines(value)
    vehicles = []
    for line in lines:
        if " — " in line:
            vehicle = line.split(" — ", 1)[1].split(" (", 1)[0].strip()
            if vehicle and vehicle not in vehicles:
                vehicles.append(vehicle)
    summary = f"{len(lines)} pers."
    if vehicles:
        summary += " · Eq. " + ", ".join(vehicles)
    return {"summary": summary, "lines": lines}


def filter_daily_frame(frame, query):
    terms = normalize(query).split()
    if not terms or frame.empty:
        return frame.copy()
    columns = [column for column in frame.columns if not column.startswith("_") and column != "Seleccionar"]
    haystacks = frame[columns].apply(
        lambda row: normalize(" ".join(str(value) for value in row if value is not None and str(value) not in {"nan", "NaT", "<NA>"})),
        axis=1,
    )
    return frame.loc[haystacks.map(lambda value: all(term in value for term in terms))].copy()


def daily_metrics_markdown(cycles):
    opened = sum(cycle["status"] == "Abierto" for cycle in cycles)
    closed = sum(cycle["status"] == "Cerrado" for cycle in cycles)
    values = [min(100.0, 100 * float(cycle["accumulated"]) / float(cycle["target_quantity"]))
              for cycle in cycles if cycle["allocation_mode"] == "Total a repartir" and float(cycle["target_quantity"]) > 0]
    progress = sum(values) / len(values) if values else 0.0
    return (
        f"Trabajos :green[**{len(cycles)}**]　·　Abiertos :orange[**{opened}**]　·　"
        f"Cerrados :green[**{closed}**]　·　Avance :green[**{progress:,.0f}%**]"
    )


def render_daily_grid(frame, *, key):
    import json
    columns = [column for column in frame.columns if not column.startswith("_")]
    records = json.loads(frame.to_json(orient="records", date_format="iso"))
    for record in records:
        record["_staff"] = staff_cell_info(record.get("Personal y vehículo"))
        inputs = daily_list_lines(record.get("Insumo"))
        if inputs == ["Sin insumo"]:
            inputs = []
        record["_inputs"] = {
            "summary": f"{len(inputs)} insumos" if len(inputs) > 1 else (inputs[0].split(" — ", 1)[0] if inputs else "—"),
            "lines": inputs,
        }
    allowed = {int(record["_part_id"]) for record in records}
    component_state = st.session_state.get(key, {})
    current_ids = component_state.get("selected_ids", [])
    current_ids = [int(value) for value in current_ids if str(value).isdigit() and int(value) in allowed]
    result = _DAILY_GRID_COMPONENT(
        data={"rows": records, "columns": columns, "selected_ids": current_ids},
        key=key, width="stretch", height="content", default={"selected_ids": current_ids},
        on_selected_ids_change=lambda: None,
    )
    selected = {int(value) for value in (getattr(result, "selected_ids", None) or [])
                if str(value).isdigit() and int(value) in allowed}
    edited = frame.copy()
    edited["Seleccionar"] = edited["_part_id"].isin(selected)
    return edited

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "datos_fuente"
DATABASE = ROOT / "datos_app" / "asistente.db"


def get_user_front_preference(path, user_code):
    with closing(sqlite3.connect(path)) as database:
        row = database.execute(
            "SELECT front_id FROM local_user_preferences WHERE user_code = ?",
            (str(user_code).strip().lower(),),
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None


def save_user_front_preference(path, user_code, front_id):
    with closing(sqlite3.connect(path)) as database, database:
        database.execute(
            """INSERT INTO local_user_preferences(user_code, front_id, updated_at)
               VALUES (?, ?, datetime('now', 'localtime'))
               ON CONFLICT(user_code) DO UPDATE SET
                   front_id = excluded.front_id,
                   updated_at = excluded.updated_at""",
            (str(user_code).strip().lower(), front_id),
        )


def ensure_multi_task_schema(path):
    with closing(sqlite3.connect(path)) as database, database:
        database.execute("PRAGMA foreign_keys = ON")
        database.executescript(
            """
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
            """
        )
        partial_columns = {row[1] for row in database.execute("PRAGMA table_info(partial_parts)")}
        for column, definition in {
            "report_id": "INTEGER REFERENCES daily_reports(id)",
            "report_code": "TEXT",
            "line_no": "INTEGER",
        }.items():
            if column not in partial_columns:
                database.execute(f"ALTER TABLE partial_parts ADD COLUMN {column} {definition}")
        report_columns = {row[1] for row in database.execute("PRAGMA table_info(daily_reports)")}
        if "service_order" not in report_columns:
            database.execute("ALTER TABLE daily_reports ADD COLUMN service_order TEXT NOT NULL DEFAULT ''")


def add_front_task_member_local(path, front_id, operation_key, personnel_key, machine_key):
    with closing(sqlite3.connect(path)) as database, database:
        database.execute(
            """INSERT INTO front_task_members(front_id, operation_key, personnel_key, machine_key)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(front_id, operation_key, personnel_key)
               DO UPDATE SET machine_key = excluded.machine_key""",
            (int(front_id), str(operation_key), str(personnel_key), machine_key or None),
        )


def list_front_task_members_local(path, front_id, operation_key=None):
    sql = "SELECT * FROM front_task_members WHERE front_id = ?"
    parameters = [int(front_id)]
    if operation_key is not None:
        sql += " AND operation_key = ?"
        parameters.append(str(operation_key))
    sql += " ORDER BY operation_key, id"
    with closing(sqlite3.connect(path)) as database:
        database.row_factory = sqlite3.Row
        return [dict(row) for row in database.execute(sql, parameters)]


def remove_front_task_member_local(path, member_id):
    with closing(sqlite3.connect(path)) as database, database:
        database.execute("DELETE FROM front_task_members WHERE id = ?", (int(member_id),))


def archive_front_local(path, front_id):
    with closing(sqlite3.connect(path)) as database, database:
        front = database.execute(
            "SELECT name FROM fronts WHERE id = ? AND active = 1", (int(front_id),)
        ).fetchone()
        if front is None:
            raise ValueError("El frente ya no está activo.")
        if front[0] == "__MANUAL__":
            raise ValueError("El frente interno de carga manual no se puede eliminar.")
        database.execute(
            "UPDATE local_user_preferences SET front_id = NULL WHERE front_id = ?",
            (int(front_id),),
        )
        database.execute("UPDATE fronts SET active = 0 WHERE id = ?", (int(front_id),))
        return front[0]


def delete_complete_reports(path, part_ids):
    identifiers = [int(part_id) for part_id in part_ids]
    if not identifiers:
        return 0
    placeholders = ",".join("?" for _ in identifiers)
    with closing(sqlite3.connect(path)) as database, database:
        database.execute("PRAGMA foreign_keys = ON")
        rows = database.execute(
            f"SELECT id, report_id FROM partial_parts WHERE id IN ({placeholders})", identifiers
        ).fetchall()
        report_ids = sorted({int(row[1]) for row in rows if row[1] is not None})
        legacy_ids = [int(row[0]) for row in rows if row[1] is None]
        deleted = 0
        for report_id in report_ids:
            report = database.execute("SELECT report_code, document_status, sent_at FROM daily_reports WHERE id = ?", (report_id,)).fetchone()
            revision_table = database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='report_revisions'").fetchone()
            prior_sent = revision_table and database.execute("SELECT 1 FROM report_revisions WHERE report_code = ? AND was_sent = 1 LIMIT 1", (report[0],)).fetchone()
            if report[1] == "Enviado" or report[2] or prior_sent:
                raise ValueError("Un parte enviado no puede eliminarse. Podés corregirlo conservando su historial.")
        if report_ids:
            report_placeholders = ",".join("?" for _ in report_ids)
            deleted += database.execute(
                f"DELETE FROM partial_parts WHERE report_id IN ({report_placeholders})", report_ids
            ).rowcount
            database.execute(
                f"DELETE FROM daily_reports WHERE id IN ({report_placeholders})", report_ids
            )
        if legacy_ids:
            legacy_placeholders = ",".join("?" for _ in legacy_ids)
            deleted += database.execute(
                f"DELETE FROM partial_parts WHERE id IN ({legacy_placeholders})", legacy_ids
            ).rowcount
        return int(deleted)


def close_reports_for_parts(path, part_ids):
    identifiers = sorted({int(part_id) for part_id in part_ids})
    if not identifiers:
        return 0, []
    placeholders = ",".join("?" for _ in identifiers)
    with closing(sqlite3.connect(path)) as database, database:
        database.row_factory = sqlite3.Row
        selected = database.execute(
            f"SELECT id, report_id, report_code FROM partial_parts WHERE id IN ({placeholders})",
            identifiers,
        ).fetchall()
        report_ids = sorted({int(row["report_id"]) for row in selected if row["report_id"] is not None})
        target_parts = {int(row["id"]) for row in selected if row["report_id"] is None}
        if report_ids:
            report_placeholders = ",".join("?" for _ in report_ids)
            target_parts.update(
                int(row[0]) for row in database.execute(
                    f"SELECT id FROM partial_parts WHERE report_id IN ({report_placeholders})", report_ids
                )
            )
        if not target_parts:
            return 0, []
        target_placeholders = ",".join("?" for _ in target_parts)
        cycle_ids = sorted({
            int(row[0]) for row in database.execute(
                f"SELECT cycle_id FROM partial_parts WHERE id IN ({target_placeholders})",
                sorted(target_parts),
            )
        })
        closed = 0
        if cycle_ids:
            cycle_placeholders = ",".join("?" for _ in cycle_ids)
            closed = database.execute(
                f"UPDATE work_cycles SET status = 'Cerrado', closed_on = ? "
                f"WHERE id IN ({cycle_placeholders}) AND status = 'Abierto'",
                [date.today().isoformat(), *cycle_ids],
            ).rowcount
        report_codes = sorted({
            row["report_code"] or f"parte {int(row['id'])}" for row in selected
        })
        return int(closed), report_codes


def ensure_report_crop_schema(path):
    """Keep the crop migration available even if an imported initializer is cached."""
    with closing(sqlite3.connect(path, timeout=30)) as database, database:
        database.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in database.execute("PRAGMA table_info(partial_parts)")}
        if "crop" not in columns:
            database.execute("ALTER TABLE partial_parts ADD COLUMN crop TEXT")


def create_multi_task_report(lines, report_date, created_by, service_order=""):
    if not lines:
        raise ValueError("Agregá al menos una tarea al parte.")
    for line in lines:
        validate_manual_vehicles(line["operation_key"], line["allocations"])
    user = re.sub(r"[^a-z0-9]", "", normalize(created_by).lower()) or "usuario"
    with closing(sqlite3.connect(DATABASE)) as database, database:
        database.execute("PRAGMA foreign_keys = ON")
        database.execute("BEGIN IMMEDIATE")
        sequence_row = database.execute(
            "SELECT last_sequence FROM part_sequences WHERE user_code = ?", (user,)
        ).fetchone()
        sequence = int(sequence_row[0] if sequence_row else 0) + 1
        report_code = f"{user}{sequence:04d}"
        database.execute(
            """INSERT INTO part_sequences(user_code, last_sequence) VALUES (?, ?)
               ON CONFLICT(user_code) DO UPDATE SET last_sequence = excluded.last_sequence""",
            (user, sequence),
        )
        report_cursor = database.execute(
            """INSERT INTO daily_reports(
                   report_code, report_date, created_by, report_sequence, created_at, service_order
               ) VALUES (?, ?, ?, ?, datetime('now', 'localtime'), ?)""",
            (report_code, report_date, user, sequence, str(service_order or "").strip()),
        )
        report_id = int(report_cursor.lastrowid)
        for line_no, line in enumerate(lines, start=1):
            cycle_row = database.execute(
                """SELECT id FROM work_cycles
                   WHERE lot_key = ? AND operation_key = ? AND status = 'Abierto'
                   ORDER BY id DESC LIMIT 1""",
                (line["lot_key"], line["operation_key"]),
            ).fetchone()
            if cycle_row:
                cycle_id = int(cycle_row[0])
            else:
                cycle_no = database.execute(
                    "SELECT COALESCE(MAX(cycle_no), 0) + 1 FROM work_cycles WHERE lot_key = ? AND operation_key = ?",
                    (line["lot_key"], line["operation_key"]),
                ).fetchone()[0]
                cycle_cursor = database.execute(
                    """INSERT INTO work_cycles(lot_key, operation_key, cycle_no, target_quantity, unit,
                       allocation_mode, started_on, input_key, input_dose, input_unit)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        line["lot_key"], line["operation_key"], cycle_no,
                        float(line["target_quantity"]), line["unit"], line["allocation_mode"],
                        report_date, line.get("input_key"), float(line.get("input_dose") or 0),
                        line.get("input_unit") or "",
                    ),
                )
                cycle_id = int(cycle_cursor.lastrowid)
            line_code = f"{report_code}-{line_no:02d}"
            part_cursor = database.execute(
                """INSERT INTO partial_parts(
                       cycle_id, front_id, part_date, quantity, notes, created_at,
                       input_key, input_dose, input_quantity, input_unit,
                       created_by, part_sequence, part_code, report_id, report_code, line_no
                   ) VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cycle_id, int(line["front_id"]), report_date, float(line["quantity"]),
                    line.get("notes") or "", line.get("input_key"), float(line.get("input_dose") or 0),
                    float(line.get("input_quantity") or 0), line.get("input_unit") or "",
                    user, sequence, line_code, report_id, report_code, line_no,
                ),
            )
            part_id = int(part_cursor.lastrowid)
            database.execute("UPDATE partial_parts SET crop=? WHERE id=?", (line.get("crop"), part_id))
            database.executemany(
                "INSERT INTO partial_inputs(part_id, input_key, dose, quantity, unit) VALUES (?, ?, ?, ?, ?)",
                [
                    (part_id, item["input_key"], float(item["dose"]), float(item["quantity"]), item["unit"])
                    for item in line.get("inputs", []) if item.get("input_key")
                ],
            )
            database.executemany(
                """INSERT INTO partial_allocations(
                       part_id, personnel_key, machine_key, attendance, quantity, replacement_key, front_id,
                       machine_start_time, machine_end_time, person_hours
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        part_id, item["personnel_key"], item.get("machine_key"), item["attendance"],
                        float(item["quantity"]), None, item.get("front_id") or int(line["front_id"]),
                        item.get("machine_start_time"), item.get("machine_end_time"),
                        float(item.get("person_hours", 12) or 0),
                    )
                    for item in line["allocations"]
                ],
            )
        return report_code

st.set_page_config(page_title="Asistente de parte diario", page_icon=":material/agriculture:", layout="wide")
# Viewer toolbar preserves theme settings and hides developer deployment controls.
st.set_option("client.toolbarMode", "viewer")

# Keep the header controls available while reclaiming the surrounding whitespace.
st.html("""
<style>
[data-testid="stHeader"] {height: 3rem;}
[data-testid="stMainBlockContainer"] {
    padding: 3.5rem 1.15rem 1rem;
    max-width: none;
}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {gap: .65rem;}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-top: 1.2rem;}
[data-testid="stSidebar"] [role="radiogroup"] label {
    border-radius: 9px;
    padding: .38rem .55rem;
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background: color-mix(in srgb, var(--st-primary-color) 22%, transparent);
}
[data-testid="stDialog"] [role="dialog"] {
    border-radius: 18px;
    border: 1px solid var(--st-border-color);
    box-shadow: 0 18px 55px rgba(23,55,42,.2);
}
.st-key-input_catalog_result,
[class*="st-key-part_input_card_"] {
    background: color-mix(in srgb, var(--st-secondary-background-color) 88%, white);
}
[class*="st-key-part_input_card_"] {
    box-shadow: 0 2px 10px rgba(31,55,41,.055);
}
[data-testid="stMainBlockContainer"] h1,
[data-testid="stMainBlockContainer"] h2,
[data-testid="stMainBlockContainer"] h3 {
    padding-top: .15rem;
    padding-bottom: .3rem;
    line-height: 1.3;
    overflow: visible;
}
.st-key-summary_metrics [data-testid="stMetric"] {padding: .25rem .5rem; min-height: 0;}
.st-key-summary_metrics [data-testid="stMetricValue"] {font-size: 1.25rem; line-height: 1.25;}
.st-key-summary_metrics [data-testid="stMetricLabel"],
.st-key-summary_metrics [data-testid="stMetricLabel"] p {font-size: .8rem; min-height: 0;}
@media (max-width: 900px) {
    [data-testid="stMainBlockContainer"] {padding: 3.25rem .65rem .85rem;}
    [data-testid="stMainBlockContainer"] h2 {font-size: 1.45rem;}
    [data-testid="stMainBlockContainer"] h3 {font-size: 1.2rem;}
    [data-testid="stHorizontalBlock"] {flex-wrap: wrap; gap: .5rem;}
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        min-width: min(100%, 16rem);
        flex: 1 1 16rem;
    }
    [data-testid="stMetricValue"] {font-size: 1.35rem;}
    .stButton button, [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"] {min-height: 2.8rem;}
    [data-testid="stDataFrame"] {max-width: calc(100vw - 1.1rem); overflow-x: auto;}
}
</style>
""")


def create_partial_with_input(
    cycle_id, front_id, part_date, quantity, notes, allocations,
    input_key=None, input_dose=0, input_quantity=0, input_unit="", created_by="pyni", new_cycle=None,
    part_inputs=None, crop=None,
):
    with closing(sqlite3.connect(DATABASE)) as database, database:
        database.execute("PRAGMA foreign_keys = ON")
        database.execute("BEGIN IMMEDIATE")
        validation_operation_key = new_cycle["operation_key"] if new_cycle else database.execute(
            "SELECT operation_key FROM work_cycles WHERE id = ?", (cycle_id,)
        ).fetchone()[0]
        validate_manual_vehicles(validation_operation_key, allocations)
        if new_cycle:
            existing = database.execute(
                "SELECT id FROM work_cycles WHERE lot_key = ? AND operation_key = ? AND status = 'Abierto' ORDER BY id DESC LIMIT 1",
                (new_cycle["lot_key"], new_cycle["operation_key"]),
            ).fetchone()
            if existing:
                cycle_id = int(existing[0])
            else:
                cycle_no = database.execute(
                    "SELECT COALESCE(MAX(cycle_no), 0) + 1 FROM work_cycles WHERE lot_key = ? AND operation_key = ?",
                    (new_cycle["lot_key"], new_cycle["operation_key"]),
                ).fetchone()[0]
                cursor = database.execute(
                    """INSERT INTO work_cycles(lot_key, operation_key, cycle_no, target_quantity, unit,
                       allocation_mode, started_on, input_key, input_dose, input_unit)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_cycle["lot_key"], new_cycle["operation_key"], cycle_no,
                     new_cycle["target_quantity"], new_cycle["unit"], new_cycle["allocation_mode"],
                     new_cycle["started_on"], input_key, input_dose, input_unit),
                )
                cycle_id = int(cursor.lastrowid)
        current = database.execute(
            """SELECT c.status, c.allocation_mode, c.target_quantity, COALESCE(SUM(p.quantity), 0)
               FROM work_cycles c LEFT JOIN partial_parts p ON p.cycle_id = c.id
               WHERE c.id = ? GROUP BY c.id""", (cycle_id,),
        ).fetchone()
        if not current or current[0] != "Abierto":
            raise ValueError("El trabajo ya no está abierto. Actualizá la página antes de guardar.")
        if quantity <= 0 or not allocations:
            raise ValueError("El parte debe tener una cantidad mayor que cero y al menos una persona.")
        user = re.sub(r"[^a-z0-9]", "", normalize(created_by).lower()) or "usuario"
        sequence_row = database.execute(
            "SELECT last_sequence FROM part_sequences WHERE user_code = ?", (user,)
        ).fetchone()
        part_sequence = int(sequence_row[0] if sequence_row else 0) + 1
        database.execute(
            """INSERT INTO part_sequences(user_code, last_sequence) VALUES (?, ?)
               ON CONFLICT(user_code) DO UPDATE SET last_sequence = excluded.last_sequence""",
            (user, part_sequence),
        )
        part_code = f"{user}{part_sequence:04d}"
        cursor = database.execute(
            """INSERT INTO partial_parts(
                   cycle_id, front_id, part_date, quantity, notes, created_at,
                   input_key, input_dose, input_quantity, input_unit,
                   created_by, part_sequence, part_code
               ) VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'), ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(cycle_id), int(front_id), part_date, float(quantity), notes,
                input_key, float(input_dose), float(input_quantity), input_unit,
                user, part_sequence, part_code,
            ),
        )
        part_id = int(cursor.lastrowid)
        database.execute("UPDATE partial_parts SET crop=? WHERE id=?", (crop, part_id))
        inputs_to_save = part_inputs if part_inputs is not None else (
            [{"input_key": input_key, "dose": input_dose, "quantity": input_quantity, "unit": input_unit}]
            if input_key else []
        )
        database.executemany(
            "INSERT INTO partial_inputs(part_id, input_key, dose, quantity, unit) VALUES (?, ?, ?, ?, ?)",
            [
                (part_id, item["input_key"], float(item["dose"]), float(item["quantity"]), item["unit"])
                for item in inputs_to_save if item.get("input_key")
            ],
        )
        database.executemany(
            """INSERT INTO partial_allocations(
                   part_id, personnel_key, machine_key, attendance, quantity, replacement_key, front_id,
                   machine_start_time, machine_end_time, person_hours
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    part_id, item["personnel_key"], item.get("machine_key"),
                    item["attendance"], float(item["quantity"]), item.get("replacement_key") or None,
                    item.get("front_id") or int(front_id),
                    item.get("machine_start_time") or None,
                    item.get("machine_end_time") or None,
                    float(item.get("person_hours", 12) or 0),
                )
                for item in allocations
            ],
        )
        return part_id, part_code


def dose_unit(input_unit):
    return "KGS" if input_unit.upper() == "TN" else input_unit


def calculate_input_total(work_quantity, dose, input_unit):
    total = float(work_quantity) * float(dose)
    return total / 1000 if input_unit.upper() == "TN" else total


def calculate_dose_from_total(input_quantity, work_quantity, input_unit):
    if float(work_quantity) <= 0:
        return 0.0
    total_in_dose_unit = float(input_quantity) * 1000 if input_unit.upper() == "TN" else float(input_quantity)
    return total_in_dose_unit / float(work_quantity)


def format_input_total(total, input_unit):
    if input_unit.upper() == "TN":
        return f"{total:,.1f} TN ({total * 1000:,.1f} KGS)"
    return f"{total:,.1f} {input_unit}".strip()


def task_uses_person_hours(unit):
    """Hours-person is independent only when the task itself is not measured in time/jornals."""
    normalized_unit = normalize(unit).upper().replace(".", "")
    return normalized_unit not in {
        "JN", "JORNAL", "JORNALES", "HS", "H", "HR", "HRS", "HORA", "HORAS",
    }


def reset_partial_cycle_context():
    st.session_state.allocation_draft = None
    st.session_state.allocation_version += 1


def reset_new_part_context():
    reset_partial_cycle_context()


def apply_pending_allocation_edits(draft):
    """Copy edits held by the data editor into the draft before its rows change."""
    if not draft:
        return
    editor_key = f"allocation_editor_v3_{st.session_state.allocation_version}"
    editor_state = st.session_state.get(editor_key) or {}
    edited_rows = editor_state.get("edited_rows", {}) if isinstance(editor_state, dict) else {}
    for position, changes in edited_rows.items():
        row_position = int(position)
        if 0 <= row_position < len(draft.get("rows", [])):
            draft["rows"][row_position].update(changes)


def normalize_meter_row(row):
    """Merge legacy meter keys without creating duplicate editor columns."""
    result = dict(row)
    for suffix in ("inicio", "fin"):
        canonical = f"H-Km {suffix}"
        legacy = f"H/Km {suffix}"
        value = result.get(canonical)
        if value is None or pd.isna(value) or value == "":
            legacy_value = result.get(legacy)
            result[canonical] = None if legacy_value is None or pd.isna(legacy_value) or legacy_value == "" else legacy_value
        result.pop(legacy, None)
    return result


def allocation_editor_base_rows(draft):
    """Keep the editor input stable while its cell edits are being committed."""
    version = st.session_state.allocation_version
    snapshot = st.session_state.get("allocation_editor_snapshot")
    if snapshot is None or snapshot["version"] != version:
        snapshot = {"version": version, "rows": [normalize_meter_row(row) for row in draft.get("rows", [])]}
        st.session_state.allocation_editor_snapshot = snapshot
    return snapshot["rows"]


def commit_allocation_editor():
    """Persist vehicle and meter edits before the next cell triggers a rerun."""
    draft = st.session_state.allocation_draft
    if not draft:
        return
    rows = [normalize_meter_row(row) for row in draft.get("rows", [])]
    editor_state = st.session_state.get(f"allocation_editor_v3_{st.session_state.allocation_version}") or {}
    pending = editor_state.get("edited_rows", {}) if isinstance(editor_state, dict) else {}
    for position, changes in pending.items():
        index = int(position)
        if 0 <= index < len(rows):
            rows[index].update(changes)
    draft["rows"] = [normalize_meter_row(row) for row in rows]





def upgrade_allocation_editor_protocol():
    """Retire stale editor widgets once, keeping the current unsaved draft."""
    if st.session_state.get("allocation_editor_protocol") == 3:
        return
    draft = st.session_state.allocation_draft
    if draft:
        old_key = "allocation_editor_" + str(st.session_state.allocation_version)
        old_state = st.session_state.get(old_key) or {}
        changes = old_state.get("edited_rows", {}) if isinstance(old_state, dict) else {}
        rows = [normalize_meter_row(row) for row in draft.get("rows", [])]
        for position, values in changes.items():
            index = int(position)
            if 0 <= index < len(rows):
                rows[index].update(values)
        draft["rows"] = rows
    st.session_state.pop("allocation_editor_snapshot", None)
    st.session_state.allocation_version += 1
    st.session_state.allocation_editor_protocol = 3


def open_part_form():
    st.session_state.lot_view = "Carga parte"


def open_parts_summary():
    st.session_state.module_screen = "Mis partes"
    st.session_state.lot_view = "Resumen"
    clear_summary_filters()


def clear_summary_filters():
    for key in (
        "summary_part_id", "summary_farm", "summary_lot", "summary_task", "summary_input", "summary_dates", "summary_search"
    ):
        st.session_state.pop(key, None)


@st.cache_data(show_spinner=False, max_entries=2)
def load_masters(data_dir: str, source_signature=None):
    return load_all_sources(Path(data_dir))


def cell_text(value):
    return "" if pd.isna(value) else str(value).strip()


def text(record, field):
    return "" if record is None or record.get(field) is None else str(record.get(field))


def task_display_label(operation_key, operation=None):
    """One label for task selectors, cards and report tables."""
    record = operation if operation is not None else operations_by_key.get(operation_key)
    code = str(operation_key or text(record, "ID_Operacion"))
    name = text(record, "Operación")
    task_type = text(record, "Tipo_Tarea").strip()
    normalized_type = normalize(task_type).lower()
    suffix = "Mec." if normalized_type.startswith("mecan") else "Man." if normalized_type.startswith("man") else task_type
    label = " — ".join(value for value in (code, name) if value)
    return f"{label} ({suffix})" if suffix else label


def update_front_report_tasks(front_id, selection_key):
    """Remove excluded staged lines from this report, never from the saved front."""
    included = set(st.session_state.get(selection_key, []))
    st.session_state.setdefault("report_front_task_choices", {})[front_id] = list(st.session_state.get(selection_key, []))
    st.session_state.multi_part_lines = [
        line for line in st.session_state.multi_part_lines
        if line.get("front_id") != front_id or line["operation_key"] in included
    ]
    reset_partial_cycle_context()


def operation_requires_inputs(operation):
    return bool(operation and str(operation.get("Insumos") or "").strip())


def merge_operation_input_flags(operations, source_path):
    """Overlay input permissions even when app_core is still loaded in memory."""
    flags = {}
    with Path(source_path).open("r", encoding="cp1252", newline="") as source:
        for row in csv.DictReader(source, delimiter=";"):
            operation_key = str(row.get("ID_Operacion") or "").strip()
            if operation_key:
                flags[operation_key] = str(row.get("Insumos") or "").strip()
    for operation in operations:
        operation["Insumos"] = flags.get(str(operation.get("ID_Operacion") or "").strip(), "")




def index_of(options, selected):
    return options.index(selected) if selected in options else 0






required = [
    "txt/Personal.txt",
    "txt/Maquinaria.txt",
    "txt/Operaciones-Maquinaria-Insumos.csv",
    "txt/Inventario_2026.txt",
    "txt/Insumos.csv",
]
missing = [name for name in required if not (DATA_DIR / name).exists()]
if missing:
    st.error("Faltan archivos en datos_fuente: " + ", ".join(missing))
    st.stop()

initialize(DATABASE)
ensure_report_crop_schema(DATABASE)
ensure_multi_task_schema(DATABASE)
with st.spinner("Leyendo tablas maestras…"):
    source_signature = tuple(
        (name, (DATA_DIR / name).stat().st_mtime_ns, (DATA_DIR / name).stat().st_size)
        for name in required
    )
    masters = load_masters(str(DATA_DIR), source_signature)
merge_operation_input_flags(
    masters["operaciones"], DATA_DIR / "txt" / "Operaciones-Maquinaria-Insumos.csv"
)

for source_warning in masters.get("_warnings", []):
    st.warning(source_warning, icon=":material/warning:")
if masters.get("_warnings") and st.button(
    "Reintentar lectura de Insumos.csv",
    icon=":material/refresh:",
    key="retry_inputs_source",
):
    load_masters.clear()
    st.rerun()

people_by_key = {text(row, "LEGAJO"): row for row in masters["personal"]}
machines_by_key = {text(row, "Equipo"): row for row in masters["maquinaria"]}
lots_by_key = {text(row, "ID_UNICO"): row for row in masters["lotes"]}
operations_by_key = {text(row, "ID_Operacion"): row for row in masters["operaciones"]}
inputs_by_key = {text(row, "MATERIAL"): row for row in masters["insumos"]}


def validate_manual_vehicles(operation_key, allocations):
    operation = operations_by_key.get(str(operation_key), {})
    if normalize(operation.get("Tipo_Tarea")) == "MANUAL" and any(row.get("machine_key") for row in allocations):
        raise ValueError(f"La tarea {operation_key} es manual y no admite vehículos ni maquinaria.")


def operation_machines(operation):
    return {
        text(machine, "Equipo"): machine
        for machine in filter_machines_for_operation(operation, masters["maquinaria"])
    }


def machine_label(machine_key, machine_map=None):
    if not machine_key:
        return "Sin vehículo"
    machine = (machine_map or machines_by_key).get(str(machine_key))
    return (
        f"{text(machine, 'ID_Equipo')} — {text(machine, 'Grupo Operativo')} — "
        f"{text(machine, 'Marca')} {text(machine, 'Modelo')}"
    ).strip(" —")


def input_label(input_key):
    if not input_key:
        return "Sin insumo"
    record = inputs_by_key.get(str(input_key))
    return f"{text(record, 'DESCRIPCION')} — {input_key} — {text(record, 'UNIDAD')}"


def part_input_labels(part):
    summary = str(part.get("inputs_summary") or "")
    keys = [item.split(":", 1)[0].strip() for item in summary.split("|") if item.strip()]
    if not keys and part.get("input_key"):
        keys = [str(part["input_key"])]
    return {input_label(key) for key in keys} or {"Sin insumo"}


def personnel_label(personnel_key):
    record = people_by_key.get(str(personnel_key))
    return f"{text(record, 'EMPLEADO') or personnel_key} — {text(record, 'LEGAJO') or personnel_key}"


def load_report_review_bundle(report_code):
    with closing(sqlite3.connect(DATABASE)) as database:
        database.row_factory = sqlite3.Row
        report = database.execute(
            "SELECT * FROM daily_reports WHERE report_code = ?", (str(report_code),)
        ).fetchone()
        if report is None:
            raise ValueError(f"No se encontró el parte {report_code}.")
        parts = database.execute(
            """SELECT p.*, c.lot_key, c.operation_key, c.unit, c.allocation_mode,
                      f.name AS front_name
               FROM partial_parts p
               JOIN work_cycles c ON c.id = p.cycle_id
               LEFT JOIN fronts f ON f.id = p.front_id
               WHERE p.report_id = ?
               ORDER BY COALESCE(p.line_no, p.id), p.id""",
            (int(report["id"]),),
        ).fetchall()
        result = []
        for part in parts:
            allocations = database.execute(
                "SELECT * FROM partial_allocations WHERE part_id = ? ORDER BY id", (int(part["id"]),)
            ).fetchall()
            inputs = database.execute(
                "SELECT * FROM partial_inputs WHERE part_id = ? ORDER BY id", (int(part["id"]),)
            ).fetchall()
            result.append({
                "part": dict(part),
                "allocations": [dict(row) for row in allocations],
                "inputs": [dict(row) for row in inputs],
            })
        return dict(report), result


def report_pdf_filename(report_code, report_date):
    """Use the report's own date, not the download date."""
    stamp = date.fromisoformat(str(report_date)).strftime("%d%m%Y")
    return f"{report_code}_{stamp}.pdf"


def summary_report_status(document_status, work_statuses=()):
    if document_status == "Enviado":
        return "Enviado"
    if document_status == "Revisado":
        return "Pendiente de envío"
    return "En preparación"


def report_display_status(report, tasks):
    cycle_ids = sorted({int(detail["part"]["cycle_id"]) for detail in tasks})
    with closing(sqlite3.connect(DATABASE)) as database:
        statuses = [database.execute("SELECT status FROM work_cycles WHERE id = ?", (cycle_id,)).fetchone()[0]
                    for cycle_id in cycle_ids]
    return summary_report_status(report.get("document_status"), statuses)


def _editor_value(value, default=None):
    return default if value is None or (not isinstance(value, str) and pd.isna(value)) else value


def render_whatsapp_send_section(report_code):
    report = get_report_document(DATABASE, report_code)
    if not report or str(report.get("document_status") or "Borrador") not in {"Revisado", "Enviado"}:
        return
    st.divider()
    st.markdown("**2. Enviar el parte**")
    if str(report.get("document_status")) == "Enviado":
        sent_at = str(report.get("sent_at") or "").replace("T", " ")
        st.success(f"Parte enviado por WhatsApp el {sent_at or 'día registrado'}.")
        return
    try:
        pdf_generator = pdf_report
        reviewed_pdf = pdf_generator.build_daily_report_pdf(
            DATABASE, report_code,
            people_by_key=people_by_key, machines_by_key=machines_by_key,
            lots_by_key=lots_by_key, operations_by_key=operations_by_key,
            inputs_by_key=inputs_by_key,
        )
        pdf_filename = report_pdf_filename(report_code, report["report_date"])
        destination = re.sub(r"\D", "", str(whatsapp_number or ""))
        message = str(whatsapp_message or "Parte diario {id} - {fecha}")
        message = message.replace("{id}", report_code).replace("{fecha}", str(report["report_date"]))
        whatsapp_url = (
            f"https://web.whatsapp.com/send?phone={destination}&text={quote(message)}"
            if destination else "https://web.whatsapp.com/"
        )
        st.success("Datos guardados. El parte está listo para compartir por WhatsApp.")
        st.caption(
            "En celular se abre el menú para compartir el PDF. En PC se descarga el PDF y se abre "
            "WhatsApp Web usando la sesión iniciada en este navegador."
        )
        token = f"{report_code}-v{int(report.get('pdf_version') or 1)}"
        if whatsapp_send_button(
            whatsapp_url, token, reviewed_pdf, pdf_filename, message,
            key=f"review_send_{token}",
        ):
            st.session_state[f"whatsapp_prepared_{token}"] = True
        if st.session_state.get(f"whatsapp_prepared_{token}"):
            st.info("Adjuntá el PDF en WhatsApp y enviá el mensaje. Después confirmá aquí el envío.")
        if st.button(
            "Confirmar que ya envié el parte", icon=":material/check:",
            disabled=not st.session_state.get(f"whatsapp_prepared_{token}"),
            key=f"confirm_sent_{token}", width="stretch",
        ):
            if mark_report_sent(
                DATABASE, report_code, st.session_state.app_user, destination, "WhatsApp"
            ):
                st.session_state.summary_flash = f"Parte {report_code} enviado. Podés consultarlo en Mis partes."
                st.session_state.summary_delete_version += 1
                st.rerun()
    except (ValueError, sqlite3.Error) as error:
        st.error(f"No se pudo preparar el envío: {error}")


@st.dialog("Revisar y enviar", width="large")
def review_report_dialog(report_code):
    try:
        report, tasks = load_report_review_bundle(report_code)
    except (ValueError, sqlite3.Error) as error:
        st.error(str(error))
        return
    if report.get("document_status") == "Enviado":
        st.info("Este parte ya fue enviado. Consultalo o volvé a enviarlo desde Mis partes.")
        return
    st.caption(
        f"ID {report_code} · Estado: {report_display_status(report, tasks)} · "
        "Los cambios se guardan juntos y el PDF anterior deja de considerarse vigente."
    )
    if report.get("document_status") == "Enviado":
        st.warning("Al guardar una corrección se conserva la versión anterior y el parte queda pendiente de un nuevo envío.")
    st.markdown("**1. Revisar y guardar los datos**")
    with st.form(f"review_report_{report_code}"):
        header_columns = st.columns([1, 1.4])
        with header_columns[0]:
            reviewed_date = st.date_input(
                "Fecha del parte", value=date.fromisoformat(report["report_date"]), format="DD/MM/YYYY"
            )
        with header_columns[1]:
            reviewed_os = st.text_input(
                "Orden de servicio (opcional)", value=str(report.get("service_order") or "")
            )
        edited_tasks = []
        person_options = [personnel_label(key) for key in people_by_key]
        person_to_key = {personnel_label(key): key for key in people_by_key}
        input_options = [input_label(key) for key in inputs_by_key]
        input_to_key = {input_label(key): key for key in inputs_by_key}
        for position, detail in enumerate(tasks, start=1):
            part = detail["part"]
            lot = lots_by_key.get(str(part["lot_key"]), {})
            operation = operations_by_key.get(str(part["operation_key"]), {})
            task_title = task_display_label(str(part["operation_key"]), operation)
            with st.expander(f"T{position} · {task_title}", expanded=position == 1):
                st.caption(
                    f"{text(lot, 'FINCA') or '-'} · lote {text(lot, 'ID_Lote') or text(lot, 'LOTE') or part['lot_key']} · "
                    f"unidad {part['unit']} · frente {'Manual' if part.get('front_name') == '__MANUAL__' else part.get('front_name')}"
                )
                task_columns = st.columns([.8, .8, 2])
                with task_columns[0]:
                    edited_quantity = st.number_input(
                        f"Cantidad ({part['unit']})", min_value=0.0, value=float(part["quantity"]),
                        step=0.1, key=f"review_qty_{report_code}_{part['id']}",
                    )
                with task_columns[1]:
                    edited_crop = st.text_input(
                        "Cultivo", value=str(part.get("crop") or text(lot, "CULTIVO") or ""),
                        key=f"review_crop_{report_code}_{part['id']}",
                    )
                with task_columns[2]:
                    edited_notes = st.text_input(
                        "Observaciones", value=str(part.get("notes") or ""),
                        key=f"review_notes_{report_code}_{part['id']}",
                    )
                allowed_machines = operation_machines(operation)
                machine_options = ["Sin vehículo", *[machine_label(key, allowed_machines) for key in allowed_machines]]
                machine_to_key = {machine_label(key, allowed_machines): key for key in allowed_machines}
                staff_rows = []
                for row in detail["allocations"]:
                    current_machine = (
                        machine_label(row["machine_key"], allowed_machines)
                        if row.get("machine_key") in allowed_machines else "Sin vehículo"
                    )
                    staff_rows.append({
                        "Personal": personnel_label(row["personnel_key"]),
                        "Estado": row.get("attendance") or "Presente",
                        "Cantidad": float(row.get("quantity") or 0),
                        "Hs persona": float(row.get("person_hours") or 0),
                        "Vehículo / máquina": current_machine,
                        "H/Km inicio": row.get("machine_start_time"),
                        "H/Km fin": row.get("machine_end_time"),
                        "_front_id": row.get("front_id") or part["front_id"],
                    })
                st.markdown("**Personal y vehículos**")
                edited_staff = st.data_editor(
                    pd.DataFrame(staff_rows),
                    key=f"review_staff_{report_code}_{part['id']}",
                    num_rows="dynamic", hide_index=True, width="stretch",
                    column_config={
                        "Personal": st.column_config.SelectboxColumn("Personal", options=person_options, required=True),
                        "Estado": st.column_config.SelectboxColumn("Estado", options=["Presente", "Ausente", "Cantidad fija"], required=True),
                        "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.1, required=True),
                        "Hs persona": st.column_config.NumberColumn("Hs persona", min_value=0.0, step=0.5),
                        "Vehículo / máquina": st.column_config.SelectboxColumn("Vehículo / máquina", options=machine_options, disabled=not allowed_machines),
                        "H/Km inicio": st.column_config.NumberColumn("H/Km inicio", min_value=0, step=1, format="%d"),
                        "H/Km fin": st.column_config.NumberColumn("H/Km fin", min_value=0, step=1, format="%d"),
                        "_front_id": None,
                    },
                )
                input_rows = [
                    {
                        "Producto": input_label(row["input_key"]),
                        "Dosis": float(row.get("dose") or 0),
                        "Cantidad": float(row.get("quantity") or 0),
                        "Unidad": str(row.get("unit") or text(inputs_by_key.get(str(row["input_key"])), "UNIDAD")),
                    }
                    for row in detail["inputs"]
                ]
                edited_inputs = pd.DataFrame(input_rows, columns=["Producto", "Dosis", "Cantidad", "Unidad"])
                if operation_requires_inputs(operation) or input_rows:
                    st.markdown("**Insumos**")
                    edited_inputs = st.data_editor(
                        edited_inputs,
                        key=f"review_inputs_{report_code}_{part['id']}",
                        num_rows="dynamic", hide_index=True, width="stretch",
                        column_config={
                            "Producto": st.column_config.SelectboxColumn("Producto", options=input_options, required=True),
                            "Dosis": st.column_config.NumberColumn("Dosis", min_value=0.0, step=0.001, format="%.3f"),
                            "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.1),
                            "Unidad": st.column_config.TextColumn("Unidad"),
                        },
                    )
                edited_tasks.append({
                    "part": part, "quantity": edited_quantity, "crop": edited_crop, "notes": edited_notes,
                    "staff": edited_staff, "inputs": edited_inputs,
                    "person_to_key": person_to_key, "machine_to_key": machine_to_key,
                    "input_to_key": input_to_key,
                })
        submitted = st.form_submit_button(
            "Guardar y continuar al envío", icon=":material/save:", type="primary", width="stretch"
        )
    if submitted:
        try:
            payload = []
            for item in edited_tasks:
                allocations = []
                for row in item["staff"].to_dict("records"):
                    person_key = item["person_to_key"].get(str(_editor_value(row.get("Personal"), "")))
                    if not person_key:
                        raise ValueError("Seleccioná una persona válida en todas las filas.")
                    machine_key = item["machine_to_key"].get(str(_editor_value(row.get("Vehículo / máquina"), "")))
                    allocations.append({
                        "personnel_key": person_key,
                        "machine_key": machine_key,
                        "attendance": str(_editor_value(row.get("Estado"), "Presente")),
                        "quantity": float(_editor_value(row.get("Cantidad"), 0) or 0),
                        "person_hours": float(_editor_value(row.get("Hs persona"), 0) or 0),
                        "machine_start_time": _editor_value(row.get("H/Km inicio")),
                        "machine_end_time": _editor_value(row.get("H/Km fin")),
                        "front_id": int(_editor_value(row.get("_front_id"), item["part"]["front_id"])),
                    })
                inputs = []
                for row in item["inputs"].to_dict("records"):
                    input_key = item["input_to_key"].get(str(_editor_value(row.get("Producto"), "")))
                    if not input_key:
                        continue
                    inputs.append({
                        "input_key": input_key,
                        "dose": float(_editor_value(row.get("Dosis"), 0) or 0),
                        "quantity": float(_editor_value(row.get("Cantidad"), 0) or 0),
                        "unit": str(_editor_value(row.get("Unidad"), "") or text(inputs_by_key.get(input_key), "UNIDAD")),
                    })
                payload.append({
                    "id": int(item["part"]["id"]), "quantity": item["quantity"],
                    "crop": item["crop"], "notes": item["notes"],
                    "allocations": allocations, "inputs": inputs,
                })
            save_report_corrections(
                DATABASE, report_code, reviewed_date.isoformat(), reviewed_os, payload,
                st.session_state.app_user,
            )
            mark_report_reviewed(DATABASE, report_code, st.session_state.app_user)
            st.session_state.summary_flash = f"Parte {report_code} guardado. Ya podés enviarlo por WhatsApp."
            st.session_state.summary_delete_version += 1
            st.rerun(scope="fragment")
        except (ValueError, sqlite3.Error) as error:
            st.error(str(error))
    render_whatsapp_send_section(report_code)


def has_sent_revision(path, report_code):
    with closing(sqlite3.connect(path)) as database:
        exists = database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='report_revisions'").fetchone()
        return bool(exists and database.execute(
            "SELECT 1 FROM report_revisions WHERE report_code = ? AND was_sent = 1 LIMIT 1", (report_code,)
        ).fetchone())


_SENT_REPORTS_COMPONENT = st.components.v2.component(
    "sent_reports_table",
    html="<div id='sent-reports'></div>",
    css="""
#sent-reports{overflow:auto;border:1px solid var(--st-border-color,#d6dcd2);border-radius:8px;font:14px var(--st-font,Arial,sans-serif);color:var(--st-text-color,#26322a)}
#sent-reports table{width:100%;border-collapse:collapse;text-align:left;white-space:nowrap}
#sent-reports th{background:var(--st-secondary-background-color,#eef0e8);font-weight:600}
#sent-reports th,#sent-reports td{padding:10px 12px;border-bottom:1px solid var(--st-border-color,#d6dcd2)}
#sent-reports tr.selected{background:color-mix(in srgb,var(--st-primary-color,#526747) 12%,transparent)}
#sent-reports button{background:none;border:0;color:var(--st-link-color,#326596);font:600 14px var(--st-font,Arial,sans-serif);text-decoration:underline;cursor:pointer;padding:8px 0;touch-action:manipulation}
#sent-reports button:focus-visible{outline:2px solid var(--st-primary-color,#526747);outline-offset:3px}
""",
    js=r"""
export default function(component){
 const {parentElement,data,setStateValue}=component;
 const root=parentElement.querySelector('#sent-reports');
 const doc=root.ownerDocument;root.replaceChildren();
 const table=doc.createElement('table');table.setAttribute('aria-label','Partes enviados');
 const head=doc.createElement('thead');const header=doc.createElement('tr');
 for(const name of data.columns){const th=doc.createElement('th');th.textContent=name;header.append(th);}
 head.append(header);table.append(head);const body=doc.createElement('tbody');
 for(const record of data.rows){
  const tr=doc.createElement('tr');if(record['ID parte']===data.selected)tr.className='selected';
  for(const column of data.columns){const td=doc.createElement('td');
   if(column==='ID parte'){
    const button=doc.createElement('button');button.type='button';button.textContent=record[column];
    button.title='Un clic para ver el detalle';button.setAttribute('aria-label','Ver detalle del parte '+record[column]);
    let lastOpen=0;
    const open=()=>{const now=Date.now();if(now-lastOpen<500)return;lastOpen=now;setStateValue('open_event',{code:record[column],nonce:now});};
    button.addEventListener('click',open);
    button.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();open();}});
    td.append(button);
   }else td.textContent=record[column]==null?'':String(record[column]);
   tr.append(td);
  }body.append(tr);
 }table.append(body);root.append(table);
}
""",
)


def render_my_reports():
    st.title("Mis partes", anchor=False)
    st.caption("Consultá tus partes enviados, su contenido y volvé a compartirlos cuando lo necesites.")
    st.caption("Los datos se guardan en esta instalación. Enviado indica envío por WhatsApp confirmado; todavía no hay sincronización central.")
    if st.session_state.summary_flash:
        st.success(st.session_state.summary_flash)
        st.session_state.summary_flash = None
    user = re.sub(r"[^a-z0-9]", "", normalize(st.session_state.app_user).lower()) or "usuario"
    with closing(sqlite3.connect(DATABASE)) as database:
        database.row_factory = sqlite3.Row
        documents = [dict(row) for row in database.execute(
            "SELECT * FROM daily_reports WHERE created_by = ? AND document_status = 'Enviado' ORDER BY report_date DESC, id DESC", (user,)
        )]
    if not documents:
        st.info("Todavía no tenés partes enviados. Los partes por revisar o enviar están en Partes y avance.")
        return
    query = st.text_input("Buscar parte", placeholder="Número, finca, lote o tarea", key="my_reports_query").strip().casefold()
    date_filter = st.date_input("Filtrar por fechas (opcional)", value=[], format="DD/MM/YYYY", key="my_reports_dates")
    summaries = []
    for document in documents:
        report, tasks = load_report_review_bundle(document["report_code"])
        farms, lots, operations = set(), set(), []
        for detail in tasks:
            part = detail["part"]
            lot = lots_by_key.get(str(part["lot_key"]), {})
            farms.add(text(lot, "FINCA") or "-")
            lots.add(text(lot, "ID_Lote") or str(part["lot_key"]))
            operations.append(task_display_label(str(part["operation_key"])))
        status = summary_report_status(document.get("document_status"))
        row = {"ID parte": document["report_code"], "Fecha": document["report_date"],
               "Estado": status, "Finca": ", ".join(sorted(farms)), "Lote": ", ".join(sorted(lots)),
               "Tareas": " / ".join(operations), "Envío confirmado": str(document.get("sent_at") or "").replace("T", " ")}
        if query and query not in " ".join(str(value) for value in row.values()).casefold():
            continue
        report_date = date.fromisoformat(document["report_date"])
        if date_filter and (report_date < date_filter[0] or report_date > date_filter[-1]):
            continue
        summaries.append(row)
    if not summaries:
        st.info("No hay partes que coincidan con la búsqueda.")
        return
    frame = pd.DataFrame(summaries)
    frame["Estado"] = frame["Estado"].map(lambda value: {"En preparación": "🟠", "Pendiente de envío": "🟢", "Enviado": "🔵"}[value] + " " + value)
    import json
    st.caption("Hacé clic o tocá una vez el número del parte para ver su detalle.")
    codes = [row["ID parte"] for row in summaries]
    result = _SENT_REPORTS_COMPONENT(
        data={"rows": json.loads(frame.to_json(orient="records")), "columns": list(frame.columns),
              "selected": st.session_state.get("my_reports_active", "")},
        key="sent_reports_table", width="stretch", height="content", default={"open_event": {}},
        on_open_event_change=lambda: None,
    )
    event = getattr(result, "open_event", None) or {}
    if event.get("code") in codes and event.get("nonce") != st.session_state.get("my_reports_open_nonce"):
        st.session_state.my_reports_open_nonce = event["nonce"]
        st.session_state.my_reports_active = event["code"]
        preview_report_dialog(event["code"])


@st.dialog("Vista previa", width="large")
def preview_report_dialog(report_code):
    try:
        report, tasks = load_report_review_bundle(report_code)
    except (ValueError, sqlite3.Error) as error:
        st.error(str(error))
        return
    st.markdown(f"### Parte {report_code}")
    st.caption(
        f"Fecha {report['report_date']} · OS {report.get('service_order') or 'a completar'} · "
        f"{len(tasks)} tarea(s) · Estado {report_display_status(report, tasks)}"
    )
    for position, detail in enumerate(tasks, start=1):
        part = detail["part"]
        lot = lots_by_key.get(str(part["lot_key"]), {})
        operation = operations_by_key.get(str(part["operation_key"]), {})
        with st.container(border=True):
            st.markdown(f"**T{position} · {task_display_label(str(part['operation_key']), operation)}**")
            st.caption(
                f"{text(lot, 'FINCA') or '-'} · lote {text(lot, 'ID_Lote') or text(lot, 'LOTE') or part['lot_key']} · "
                f"{float(part['quantity']):,.1f} {part['unit']} · cultivo {part.get('crop') or text(lot, 'CULTIVO') or '-'}"
            )
            staff_preview = [{
                "Personal": personnel_label(row["personnel_key"]),
                "Cantidad": float(row.get("quantity") or 0),
                "Hs persona": float(row.get("person_hours") or 0),
                "Vehículo / máquina": machine_label(row.get("machine_key")),
                "Inicio": row.get("machine_start_time"), "Fin": row.get("machine_end_time"),
            } for row in detail["allocations"]]
            st.dataframe(pd.DataFrame(staff_preview), hide_index=True, width="stretch")
            if detail["inputs"]:
                st.dataframe(pd.DataFrame([{
                    "Insumo": input_label(row["input_key"]), "Dosis": float(row.get("dose") or 0),
                    "Cantidad": float(row.get("quantity") or 0), "Unidad": row.get("unit") or "",
                } for row in detail["inputs"]]), hide_index=True, width="stretch")
    if report.get("document_status") == "Enviado":
        st.divider()
        try:
            generator = pdf_report
            data = generator.build_daily_report_pdf(
                DATABASE, report_code, people_by_key=people_by_key,
                machines_by_key=machines_by_key, lots_by_key=lots_by_key,
                operations_by_key=operations_by_key, inputs_by_key=inputs_by_key,
            )
            filename = report_pdf_filename(report_code, report["report_date"])
            st.download_button("Descargar PDF", data=data, file_name=filename,
                               mime="application/pdf", key=f"detail_pdf_{report_code}")
            destination = re.sub(r"\D", "", str(whatsapp_number or ""))
            message = str(whatsapp_message or "Parte diario {id} - {fecha}").replace("{id}", report_code).replace("{fecha}", report["report_date"])
            url = f"https://web.whatsapp.com/send?phone={destination}&text={quote(message)}" if destination else "https://web.whatsapp.com/"
            st.caption("En PC se descarga el PDF para adjuntarlo en WhatsApp.")
            whatsapp_send_button(
                url, f"copy-{report_code}-{report.get('pdf_version')}", data, filename, message,
                key=f"detail_resend_{report_code}", label="Volver a enviar por WhatsApp",
            )
        except (ValueError, sqlite3.Error) as error:
            st.error(f"No se pudo preparar el PDF para reenviar: {error}")
    else:
        st.info("Para revisar los datos y enviarlo, cerrá esta vista y usá Revisar y enviar.")


st.session_state.setdefault("pending_part", None)
st.session_state.setdefault("allocation_draft", None)
st.session_state.setdefault("allocation_version", 0)
upgrade_allocation_editor_protocol()
st.session_state.setdefault("front_flash", None)
st.session_state.setdefault("summary_flash", None)
st.session_state.setdefault("part_flash", None)
st.session_state.setdefault("app_user", "pyni")
st.session_state.setdefault("summary_delete_version", 0)
st.session_state.setdefault("part_input_count", 1)
st.session_state.setdefault("written_flash", None)
st.session_state.setdefault("written_version", 0)
st.session_state.setdefault("written_editor_version", 0)
st.session_state.setdefault("written_draft", None)
st.session_state.setdefault("multi_part_lines", [])
st.session_state.setdefault("multi_part_flash", None)

with st.sidebar:
    st.subheader("Parte diario", icon=":material/eco:", anchor=False)
    st.caption("Gestión de tareas agrícolas")
    screen = st.radio(
        "Módulo",
        ["Partes y avance", "Frentes", "Carga manual", "Mis partes"],
        key="module_screen",
        label_visibility="collapsed",
        width="stretch",
        format_func=lambda value: {
            "Partes y avance": ":material/table_chart:  Partes y avance",
            "Frentes": ":material/groups:  Frentes",
            "Carga manual": ":material/edit_note:  Carga manual",
            "Mis partes": ":material/folder:  Mis partes",
        }[value],
    )
    st.divider()
    with st.expander("Configuración", icon=":material/settings:"):
        operator_code = st.text_input(
            "Código de usuario",
            key="app_user",
            width="stretch",
            help="Se usa para generar IDs de parte, por ejemplo pyni0001.",
        )
        preference_user = re.sub(r"[^a-z0-9]", "", normalize(operator_code).lower()) or "usuario"
        default_hours_key = f"default_person_hours_{preference_user}"
        if default_hours_key not in st.session_state:
            st.session_state[default_hours_key] = get_user_default_person_hours(DATABASE, preference_user)
        default_person_hours = st.number_input(
            "Horas por persona sugeridas",
            min_value=0.0,
            max_value=48.0,
            step=0.5,
            key=default_hours_key,
            help="Se completan automáticamente al crear un parte y luego pueden editarse por persona.",
        )
        whatsapp_preferences = get_user_whatsapp_preferences(DATABASE, preference_user)
        whatsapp_number_key = f"whatsapp_number_{preference_user}"
        whatsapp_message_key = f"whatsapp_message_{preference_user}"
        if whatsapp_number_key not in st.session_state:
            st.session_state[whatsapp_number_key] = whatsapp_preferences["number"]
        if whatsapp_message_key not in st.session_state:
            st.session_state[whatsapp_message_key] = whatsapp_preferences["message"]
        whatsapp_number = st.text_input(
            "WhatsApp destinatario",
            key=whatsapp_number_key,
            placeholder="Ej.: 5493815551234",
            help="Número completo con código de país y área, sin +, espacios ni guiones.",
        )
        whatsapp_message = st.text_area(
            "Mensaje sugerido",
            key=whatsapp_message_key,
            height=82,
            help="Podés usar {id} y {fecha}; se reemplazan al preparar el envío.",
        )
        if st.button("Guardar configuración", icon=":material/save:", width="stretch"):
            save_user_default_person_hours(DATABASE, preference_user, default_person_hours)
            save_user_whatsapp_preferences(
                DATABASE, preference_user, whatsapp_number, whatsapp_message,
            )
            st.success("Configuración guardada.")
        st.caption("Tema claro u oscuro: menú ⋮ de arriba a la derecha → Settings → Theme.")


if pending_review := st.session_state.pop("review_saved_report", None):
    review_report_dialog(pending_review)

if screen == "Mis partes":
    render_my_reports()
elif screen == "Carga manual":
    st.subheader("Carga manual", icon=":material/edit_note:", anchor=False)
    st.caption("Describí el parte en una frase. Revisá los datos y confirmá para guardarlo en Partes y avance.")
    if st.session_state.written_flash:
        st.success(st.session_state.written_flash, icon=":material/check_circle:")
        st.button("Ver en Mis partes", icon=":material/table_view:", on_click=open_parts_summary)

    pending = st.session_state.pending_part
    if pending and "personnel_keys" not in pending:
        pending = interpret_part_text(pending["text"], masters, list_fronts(DATABASE))
        st.session_state.pending_part = pending
        st.session_state.written_version += 1
        st.session_state.written_draft = None
    if pending:
        entry_key = f"quick_{st.session_state.written_version}"
        suggestions = pending["suggestions"]
        fronts = list_fronts(DATABASE)
        front_map = {row["id"]: row for row in fronts}
        for notice in pending.get("notices", []):
            st.info(notice)
        st.subheader("Revisar registro", anchor=False)
        with st.container(border=True):
            header_columns = st.columns([1, 2, 2])
            suggested_lot = lots_by_key.get(suggestions.get("Fincas y lotes"))
            farm_options = [None, *sorted({text(row, "FINCA") for row in masters["lotes"] if text(row, "FINCA")})]
            with header_columns[0]:
                part_date = st.date_input("Fecha *", value=date.fromisoformat(pending["date"]), key=f"{entry_key}_date")
            with header_columns[1]:
                farm = st.selectbox(
                    "Finca *", farm_options, index=index_of(farm_options, text(suggested_lot, "FINCA") or pending.get("farm")),
                    format_func=lambda value: value or "Seleccionar finca", key=f"{entry_key}_farm",
                )
            farm_lots = {key: row for key, row in lots_by_key.items() if text(row, "FINCA") == farm}
            lot_options = [None, *farm_lots]
            with header_columns[2]:
                lot_key = st.selectbox(
                    "Lote *", lot_options, index=index_of(lot_options, suggestions.get("Fincas y lotes")),
                    format_func=lambda key: "Seleccionar lote" if key is None else f"{text(farm_lots[key], 'ID_Lote')} — {text(farm_lots[key], 'LOTE')}",
                    key=f"{entry_key}_lot_{farm}",
                )
            crop = st.text_input("Cultivo", value=text(lots_by_key.get(lot_key), "CULTIVO"), key=f"{entry_key}_crop_{lot_key}", help="Sugerido por el inventario; podés modificarlo para este parte.")
            operation_options = [None, *operations_by_key]
            operation_key = st.selectbox(
                "Tarea *", operation_options, index=index_of(operation_options, suggestions.get("Operaciones")),
                format_func=lambda key: "Seleccionar tarea" if key is None else task_display_label(key),
                key=f"{entry_key}_operation",
            )
            operation = operations_by_key.get(operation_key)
            allowed_machines = operation_machines(operation)
            required_machine_groups = operation_machine_groups(operation)
            inputs_enabled = operation_requires_inputs(operation)
            if required_machine_groups:
                st.caption("Máquinas habilitadas para esta tarea: **" + ", ".join(required_machine_groups) + "**")
            open_cycle = next((cycle for cycle in list_cycles(DATABASE, "Abierto")
                               if cycle["lot_key"] == lot_key and cycle["operation_key"] == operation_key), None)
            unit = open_cycle["unit"] if open_cycle else text(operation, "Unidad_Medida")
            person_hours_enabled = task_uses_person_hours(unit)
            allocation_mode = open_cycle["allocation_mode"] if open_cycle else ("Total a repartir" if unit.upper() in {"SC", "HA", "TN"} else "Cantidad individual")
            quantity_label = f"Cantidad total * ({unit or 'unidad de la tarea'})" if allocation_mode == "Total a repartir" else f"Cantidad por persona * ({unit or 'unidad de la tarea'})"
            quantity = st.number_input(quantity_label, min_value=0.0, value=float(pending["quantity"]), step=1.0, key=f"{entry_key}_quantity")
            unit_confirmed = True
            if unit and pending.get("quantity_unit") and normalize(unit) != pending["quantity_unit"]:
                st.info(f"El texto indica {pending['quantity_unit']}; la tarea seleccionada utiliza {unit}. Revisá la cantidad y la tarea.")
                unit_confirmed = st.checkbox(f"La cantidad revisada está expresada en {unit}", key=f"{entry_key}_unit_confirm_{unit}")

            selected_front_ids = st.multiselect(
                "Frentes (opcional)", list(front_map), default=[key for key in pending["front_ids"] if key in front_map],
                format_func=lambda key: front_map[key]["name"], key=f"{entry_key}_fronts",
            )
            configured_members = {}
            for front_id in selected_front_ids:
                for member in list_front_members(DATABASE, front_id):
                    configured_members.setdefault(member["personnel_key"], {**member, "front_id": front_id})
            default_people = list(dict.fromkeys([*configured_members, *pending["personnel_keys"]]))
            selected_people = st.multiselect(
                "Personal *", list(people_by_key), default=[key for key in default_people if key in people_by_key],
                format_func=lambda key: f"{text(people_by_key[key], 'EMPLEADO')} — {key}",
                key=f"{entry_key}_people_{tuple(selected_front_ids)}",
                help="Podés agregar o quitar personas. Los frentes aportan sus integrantes y vehículos habituales.",
            )
            vehicle_options = [None, *allowed_machines]
            suggested_vehicle = pending.get("vehicle_key")
            if suggested_vehicle not in allowed_machines:
                suggested_vehicle = None
            common_vehicle = st.selectbox(
                "Vehículo para personal sin vehículo (opcional)", vehicle_options,
                index=index_of(vehicle_options, suggested_vehicle),
                format_func=lambda key: machine_label(key, allowed_machines),
                key=f"{entry_key}_vehicle",
                disabled=not allowed_machines,
                help="La lista se filtra según los grupos de maquinaria admitidos por la tarea.",
            )
            notes = st.text_input("Observaciones", value=pending.get("notes", ""), key=f"{entry_key}_notes")

        edited = None
        draft = None
        declared_total = 0.0
        if selected_people and quantity > 0 and operation_key:
            manual_front_id = get_or_create_manual_front(DATABASE)
            signature = [
                "machine_filter_v1", entry_key, lot_key, operation_key, unit, quantity,
                selected_people, selected_front_ids, common_vehicle, required_machine_groups,
            ]
            draft = st.session_state.written_draft
            if not draft or draft["signature"] != signature:
                amounts = redistribute_rows(
                    [{"Estado": "Presente", "Cantidad": 0.0} for _ in selected_people], quantity,
                    integers=unit.upper() == "SC",
                ) if allocation_mode == "Total a repartir" else [{"Estado": "Presente", "Cantidad": quantity} for _ in selected_people]
                rows = []
                for personnel_key, amount in zip(selected_people, amounts):
                    member = configured_members.get(personnel_key, {})
                    vehicle_key = pending["vehicle_by_person"].get(personnel_key) or member.get("machine_key") or common_vehicle
                    if vehicle_key not in allowed_machines:
                        vehicle_key = None
                    front_id = member.get("front_id") or manual_front_id
                    rows.append({
                        "Legajo": personnel_key, "Empleado": text(people_by_key[personnel_key], "EMPLEADO"),
                        "Frente": front_map[front_id]["name"] if front_id in front_map else "Manual",
                        "Estado": amount["Estado"], "Cantidad": amount["Cantidad"],
                        "ID máquina": vehicle_key or "",
                        "Reemplazo legajo": "", "_front_id": front_id,
                    })
                st.session_state.written_editor_version += 1
                draft = {"signature": signature, "rows": rows}
                st.session_state.written_draft = draft
            st.caption("Distribución del parte: revisá el personal, las cantidades y los vehículos antes de confirmar.")
            edited = st.data_editor(
                pd.DataFrame(draft["rows"]).drop(columns=["_front_id"]),
                key=f"{entry_key}_editor_{st.session_state.written_editor_version}",
                hide_index=True, width="stretch", disabled=["Legajo", "Empleado", "Frente"],
                alt="Datos revisables del personal y los vehículos del parte",
                column_config={
                    "Estado": st.column_config.SelectboxColumn(options=["Presente", "Ausente", "Cantidad fija"], required=True),
                    "Cantidad": st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
                    "ID máquina": st.column_config.SelectboxColumn(
                        "Vehículo / máquina", options=["", *sorted(allowed_machines)], disabled=not allowed_machines,
                        format_func=lambda key: machine_label(key, allowed_machines),
                        help="Sólo se muestran máquinas compatibles con la tarea seleccionada.",
                    ),
                    "Reemplazo legajo": st.column_config.SelectboxColumn(
                        "Reemplazar por", options=["", *sorted(people_by_key)],
                        format_func=lambda key: "Sin reemplazo" if not key else f"{text(people_by_key.get(key), 'EMPLEADO')} — {key}",
                        help="Elegí otra persona para reemplazar al integrante original.",
                    ),
                },
            )
            total_allocated = float(edited["Cantidad"].sum())
            declared_total = quantity if allocation_mode == "Total a repartir" else total_allocated
            st.caption(f"Total del parte: **{declared_total:,.1f} {unit}**")
            if allocation_mode == "Total a repartir" and st.button("Redistribuir saldo", icon=":material/balance:", key=f"{entry_key}_redistribute"):
                try:
                    rows = edited.to_dict("records")
                    for row, original in zip(rows, draft["rows"]):
                        if row["Estado"] == "Presente" and abs(float(row["Cantidad"]) - float(original["Cantidad"])) > .001:
                            row["Estado"] = "Cantidad fija"
                    rows = redistribute_rows(rows, quantity, integers=unit.upper() == "SC")
                    for row, original in zip(rows, draft["rows"]):
                        row["_front_id"] = original["_front_id"]
                    draft["rows"] = rows
                    st.session_state.written_editor_version += 1
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

        input_key = None
        input_unit = ""
        input_quantity = input_dose = 0.0
        if inputs_enabled:
            input_options = [None, *inputs_by_key]
            with st.expander("Insumo y dosis (opcional)", expanded=bool(suggestions.get("Insumos"))):
                input_key = st.selectbox(
                    "Insumo", input_options, index=index_of(input_options, suggestions.get("Insumos")),
                    format_func=input_label, key=f"{entry_key}_input",
                )
                if input_key:
                    catalog_unit = text(inputs_by_key[input_key], "UNIDAD")
                    unit_options = ["", *sorted({"L", "KG", "TN", "GR", "UN", "SEM", catalog_unit} - {""})]
                    input_unit = st.selectbox("Unidad del insumo *", unit_options, index=index_of(unit_options, catalog_unit), key=f"{entry_key}_input_unit_{input_key}")
                    dose = st.number_input(
                        f"Dosis ({dose_unit(input_unit) or 'unidad'}/{unit or 'unidad de la tarea'})",
                        min_value=0.0, value=float(pending["dose"]), step=.001, format="%.3f",
                        key=f"{entry_key}_dose_{input_key}_{input_unit}",
                    )
                    suggested_consumption = calculate_input_total(declared_total, dose, input_unit)
                    if pending.get("input_quantity") is not None and input_key == suggestions.get("Insumos"):
                        try:
                            suggested_consumption = convert_input_quantity(pending["input_quantity"], pending["input_quantity_unit"], input_unit)
                        except ValueError as error:
                            st.info(str(error))
                    input_quantity = st.number_input(
                        f"Cantidad insumo ({input_unit or 'unidad'}) *", min_value=0.0,
                        value=float(suggested_consumption), step=.1,
                        key=f"{entry_key}_consumption_{input_key}_{input_unit}_{declared_total}_{dose}",
                        help="Consumo real de todo el parte. Se calcula con la dosis y podés corregirlo.",
                    )
                    input_dose = calculate_dose_from_total(input_quantity, declared_total, input_unit)
                    st.caption(f"Dosis a guardar: {input_dose:,.3f} {dose_unit(input_unit)}/{unit or 'unidad'}")
        elif operation_key:
            st.caption(":material/block: Esta tarea no admite carga de insumos.")

        target = 0.0
        if lot_key and operation_key:
            lot = lots_by_key[lot_key]
            if open_cycle:
                target = float(open_cycle["target_quantity"])
                st.caption(f"Avance del lote: {float(open_cycle['accumulated']):,.1f} {unit}" + (f" de {target:,.1f} {unit}." if allocation_mode == "Total a repartir" else "."))
            elif allocation_mode == "Total a repartir":
                proposed_target = float(text(lot, "SURCOS") or 0) if unit.upper() == "SC" else (float(text(lot, "AREA N") or text(lot, "AREA B") or 0) if unit.upper() == "HA" else 0.0)
                with st.expander("Objetivo del lote (opcional)"):
                    configured_target = st.number_input(
                        f"Objetivo ({unit})", min_value=0.0, value=proposed_target, step=1.0,
                        key=f"{entry_key}_target_{lot_key}_{operation_key}",
                        help="Si dejás cero, se usa la cantidad del parte. Los siguientes partes se suman al trabajo abierto.",
                    )
                target = configured_target or declared_total
        machines_complete = bool(
            edited is not None
            and (
                not required_machine_groups
                or any(
                    row["Estado"] != "Ausente" and cell_text(row["ID máquina"])
                    for row in edited.to_dict("records")
                )
            )
        )
        ready = bool(lot_key and operation_key and selected_people and quantity > 0 and edited is not None and unit_confirmed)
        ready = ready and machines_complete
        ready = ready and (not input_key or bool(input_unit and input_quantity > 0))
        if not ready:
            st.caption("Completá los campos obligatorios (*) para confirmar el parte.")
        if required_machine_groups and edited is not None and not machines_complete:
            st.warning("Esta tarea requiere al menos una máquina compatible en el parte.")
        with st.container(horizontal=True):
            confirm_clicked = st.button("Confirmar y guardar parte", icon=":material/check_circle:", type="primary", disabled=not ready)
            if st.button("Descartar borrador", icon=":material/close:"):
                st.session_state.pending_part = None
                st.session_state.written_draft = None
                st.rerun()
        if confirm_clicked:
            try:
                if not ready:
                    raise ValueError("Completá fecha, finca, lote, tarea, cantidad y personal.")
                if allocation_mode == "Total a repartir" and abs(total_allocated - quantity) > .01:
                    raise ValueError("La distribución no coincide con la cantidad del parte. Usá Redistribuir saldo.")
                allocations = []
                for row, original in zip(edited.to_dict("records"), draft["rows"]):
                    replacement = cell_text(row["Reemplazo legajo"])
                    vehicle_key = cell_text(row["ID máquina"])
                    if replacement and replacement not in people_by_key:
                        raise ValueError(f"El legajo de reemplazo {replacement} no existe.")
                    if vehicle_key and vehicle_key not in allowed_machines:
                        raise ValueError("Una máquina seleccionada no corresponde al grupo permitido para esta tarea.")
                    if row["Estado"] == "Ausente" and float(row["Cantidad"]) > 0:
                        raise ValueError("Una persona ausente no puede tener cantidad. Redistribuí el saldo o corregí la cantidad.")
                    allocations.append({
                        "personnel_key": replacement or row["Legajo"],
                        "machine_key": vehicle_key or None,
                        "attendance": row["Estado"], "quantity": float(row["Cantidad"]),
                        "replacement_key": replacement or None, "front_id": original["_front_id"],
                        "person_hours": float(default_person_hours) if person_hours_enabled else 0.0,
                    })
                if len({row["personnel_key"] for row in allocations}) != len(allocations):
                    raise ValueError("El parte contiene una persona repetida. Revisá los reemplazos.")
                new_cycle = None if open_cycle else dict(
                    lot_key=lot_key, operation_key=operation_key, target_quantity=target,
                    unit=unit, allocation_mode=allocation_mode, started_on=part_date.isoformat(),
                )
                _, part_code = create_partial_with_input(
                    open_cycle["id"] if open_cycle else None, allocations[0]["front_id"],
                    part_date.isoformat(), declared_total, notes, allocations,
                    input_key, input_dose, input_quantity, input_unit, operator_code, new_cycle=new_cycle, crop=crop,
                )
                st.session_state.pending_part = None
                st.session_state.written_draft = None
                st.session_state.written_flash = f"Parte {part_code} guardado. Ya está disponible en Mis partes."
                st.session_state.review_saved_report = part_code
                st.rerun()
            except (ValueError, sqlite3.Error) as error:
                st.error(str(error))

    if prompt := st.chat_input("Describí fecha, finca, lote, tarea, cantidad y personal; agregá vehículo, frente o insumo si corresponde.", submit_mode="disable"):
        st.session_state.pending_part = interpret_part_text(prompt, masters, list_fronts(DATABASE))
        st.session_state.written_version += 1
        st.session_state.written_draft = None
        st.session_state.written_flash = None
        st.rerun()


elif screen == "Frentes":
    st.subheader("Frentes de trabajo", icon=":material/groups:", anchor=False)
    st.caption("Cada frente puede contener varias tareas, con personal y vehículos diferentes para cada una.")
    if st.session_state.front_flash:
        st.success(st.session_state.front_flash)
        st.session_state.front_flash = None

    with st.form("new_front", border=False):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            new_front_name = st.text_input("Nombre del frente", placeholder="Ej.: Frente 1")
            create_front_clicked = st.form_submit_button("Crear frente", icon=":material/add:")
    if create_front_clicked:
        if not new_front_name.strip():
            st.error("Ingresá un nombre para el frente.")
        else:
            try:
                create_front(DATABASE, new_front_name)
                st.session_state.front_flash = f"Frente {new_front_name.strip()} creado y guardado correctamente."
                st.rerun()
            except Exception as error:
                st.error(f"No se pudo crear el frente: {error}")

    fronts = list_fronts(DATABASE)
    if not fronts:
        st.info("Creá el primer frente para comenzar.")
    else:
        front_map = {row["id"]: row for row in fronts}
        selected_front_id = st.selectbox("Frente", list(front_map), format_func=lambda key: front_map[key]["name"])
        task_column, person_column, machine_column, action_column = st.columns(
            [1.15, 1.5, 1.0, 0.55], vertical_alignment="bottom"
        )
        with task_column:
            task_key = st.selectbox(
                "Tarea del integrante", list(operations_by_key),
                format_func=lambda key: task_display_label(key),
                key="front_member_task",
            )
        task_machine_map = operation_machines(operations_by_key[task_key])
        with person_column:
            person_index = st.selectbox(
                "Personal", range(len(masters["personal"])),
                format_func=lambda i: f"{text(masters['personal'][i], 'EMPLEADO')} — {text(masters['personal'][i], 'LEGAJO')}",
                key="front_member_person",
            )
        with machine_column:
            machine_index = st.selectbox(
                "Máquina habitual", [None, *task_machine_map],
                format_func=lambda key: "Sin máquina" if key is None else machine_label(key, task_machine_map),
                key=f"front_member_machine_{task_key}",
            )
        with action_column:
            add_clicked = st.button(
                "Agregar", icon=":material/person_add:",
                key="add_front_task_member", width="stretch",
            )
        if add_clicked:
            add_front_task_member_local(
                DATABASE, selected_front_id, task_key,
                text(masters["personal"][person_index], "LEGAJO"), machine_index,
            )
            st.session_state.front_flash = (
                f"Integrante guardado en {front_map[selected_front_id]['name']} para la tarea {task_key}."
            )
            st.rerun()

        members = list_front_task_members_local(DATABASE, selected_front_id)
        member_rows = []
        for member in members:
            person = people_by_key.get(member["personnel_key"])
            machine = machines_by_key.get(member["machine_key"])
            member_rows.append(
                {
                    "Tarea": task_display_label(member["operation_key"]),
                    "Empleado": text(person, "EMPLEADO"), "Legajo": member["personnel_key"],
                    "Grupo operativo": text(machine, "Grupo Operativo"), "ID equipo": text(machine, "ID_Equipo"),
                }
            )
        st.dataframe(
            pd.DataFrame(member_rows), hide_index=True, width="stretch",
            alt="Integrantes y máquinas guardados en el frente",
        )
        st.info(
            f"El frente {front_map[selected_front_id]['name']} tiene {len(members)} integrantes. "
            "Los cambios se guardan automáticamente."
        )
        if st.button("Confirmar frente", icon=":material/check_circle:", type="primary"):
            st.success(
                f"Frente {front_map[selected_front_id]['name']} confirmado con {len(members)} integrantes."
            )
        with st.expander("Eliminar frente"):
            st.caption(
                "El frente dejará de aparecer en las listas. Los partes históricos, si existen, se conservan."
            )
            confirm_front_deletion = st.checkbox(
                f"Confirmo que quiero eliminar el frente {front_map[selected_front_id]['name']}",
                key=f"confirm_front_deletion_{selected_front_id}",
            )
            if st.button(
                "Eliminar frente", icon=":material/delete:",
                disabled=not confirm_front_deletion,
                key=f"archive_front_{selected_front_id}",
            ):
                archived_front_name = archive_front_local(DATABASE, selected_front_id)
                st.session_state.front_flash = (
                    f"Frente {archived_front_name} eliminado. Ya no aparecerá en las listas."
                )
                st.rerun()
        if members:
            remove_id = st.selectbox(
                "Quitar integrante", [row["id"] for row in members],
                format_func=lambda key: next(
                    f"{row['operation_key']} — {text(people_by_key.get(row['personnel_key']), 'EMPLEADO')} — {row['personnel_key']}"
                    for row in members if row["id"] == key
                ),
            )
            if st.button("Quitar del frente", icon=":material/person_remove:"):
                remove_front_task_member_local(DATABASE, remove_id)
                st.session_state.front_flash = "Integrante eliminado; el frente actualizado quedó guardado."
                st.rerun()


else:
    st.title("Partes y avance", anchor=False)
    lot_view = st.segmented_control(
        "Vista", ["Resumen", "Carga parte"], default="Resumen", key="lot_view",
        format_func=lambda value: ":material/add_circle: Nuevo parte" if value == "Carga parte" else value,
        label_visibility="collapsed", width=300,
    ) or "Resumen"

    if lot_view == "Resumen":
        if st.session_state.summary_flash:
            st.success(st.session_state.summary_flash, icon=":material/check_circle:")
            st.session_state.summary_flash = None
        cycles = list_cycles(DATABASE)
        if not cycles:
            st.info("Todavía no hay partes. Usá “+ Nuevo parte” para registrar el primero.")
        else:
            parts_by_cycle = {}
            for part in list_all_partials(DATABASE):
                parts_by_cycle.setdefault(int(part["cycle_id"]), []).append(part)
            # Sent reports remain in the database and cumulative calculations.
            with closing(sqlite3.connect(DATABASE)) as database:
                sent_codes = {str(row[0]) for row in database.execute(
                    "SELECT report_code FROM daily_reports WHERE document_status = 'Enviado'"
                )}
            cycles = [cycle for cycle in cycles if any(
                str(part.get("report_code") or part.get("part_code") or "") not in sent_codes
                for part in parts_by_cycle.get(int(cycle["id"]), [])
            )]
            if not cycles:
                st.info("No hay partes pendientes. Los enviados están en Mis partes.")
                st.stop()
            def cycle_input_labels(detail):
                parts = parts_by_cycle.get(int(detail["cycle"]["id"]), [])
                return {label for part in parts for label in part_input_labels(part)}
            cycle_details = []
            for cycle in cycles:
                lot = lots_by_key.get(cycle["lot_key"])
                operation = operations_by_key.get(cycle["operation_key"])
                input_key = cycle.get("input_key") or ""
                cycle_details.append(
                    {
                        "cycle": cycle,
                        "farm": text(lot, "FINCA"),
                        "lot": text(lot, "ID_Lote"),
                        "task": task_display_label(text(operation, "ID_Operacion"), operation),
                        "input_key": input_key,
                        "input": input_label(input_key),
                    }
                )

            with st.container(border=False, key="summary_filters"):
                filter_columns = st.columns([2.8, 1.15, .9, 1.6, 1.35, .7], gap="small")
                with filter_columns[5]:
                    with st.popover("Más", icon=":material/tune:", width="stretch", help="ID de parte y restablecer filtros"):
                        part_id_filter = st.text_input(
                            "ID de parte", key="summary_part_id", placeholder="Ej.: pyni0001",
                            help="Podés escribir el ID completo o sólo una parte.",
                        ).strip().lower()
                        st.button("Limpiar filtros", icon=":material/filter_alt_off:", on_click=clear_summary_filters)
                if part_id_filter:
                    parts_by_cycle = {
                        cycle_id: [
                            part for part in parts
                            if part_id_filter in str(
                                part.get("report_code") or part.get("part_code") or ""
                            ).lower()
                        ]
                        for cycle_id, parts in parts_by_cycle.items()
                    }
                    cycle_details = [
                        detail for detail in cycle_details
                        if parts_by_cycle.get(int(detail["cycle"]["id"]))
                    ]
                with filter_columns[0]:
                    selected_dates = st.date_input(
                        "Fecha o período", value=(), key="summary_dates", format="DD/MM/YYYY",
                        help="Sin selección muestra todas las fechas. Elegí un día o un rango de fechas.",
                    )
                selected_dates = tuple(sorted(selected_dates or ()))
                def date_matches(part):
                    if not selected_dates:
                        return True
                    part_date = date.fromisoformat(part["part_date"])
                    start = selected_dates[0]
                    end = selected_dates[-1]
                    return start <= part_date <= end
                if selected_dates:
                    parts_by_cycle = {
                        cycle_id: [part for part in parts if date_matches(part)]
                        for cycle_id, parts in parts_by_cycle.items()
                    }
                    cycle_details = [detail for detail in cycle_details if parts_by_cycle.get(int(detail["cycle"]["id"]))]
                farms = ["Todas", *sorted({row["farm"] for row in cycle_details if row["farm"]})]
                with filter_columns[1]:
                    farm_filter = st.selectbox("Finca", farms, key="summary_farm")
                farm_rows = [row for row in cycle_details if farm_filter == "Todas" or row["farm"] == farm_filter]
                lots = ["Todos", *sorted({row["lot"] for row in farm_rows if row["lot"]})]
                with filter_columns[2]:
                    lot_filter = st.selectbox("Lote", lots, key="summary_lot")
                lot_rows = [row for row in farm_rows if lot_filter == "Todos" or row["lot"] == lot_filter]
                tasks = ["Todas", *sorted({row["task"] for row in lot_rows if row["task"]})]
                with filter_columns[3]:
                    task_filter = st.selectbox("Tarea", tasks, key="summary_task")
                task_rows = [row for row in lot_rows if task_filter == "Todas" or row["task"] == task_filter]
                inputs = ["Todos", *sorted({label for row in task_rows for label in cycle_input_labels(row)})]
                with filter_columns[4]:
                    input_filter = st.selectbox("Insumo", inputs, key="summary_input")

            filtered_details = [
                row for row in task_rows if input_filter == "Todos" or input_filter in cycle_input_labels(row)
            ]
            filtered_cycles = [row["cycle"] for row in filtered_details]
            open_count = sum(row["status"] == "Abierto" for row in filtered_cycles)
            closed_count = sum(row["status"] == "Cerrado" for row in filtered_cycles)
            completion_values = [
                min(100.0, 100 * float(row["accumulated"]) / float(row["target_quantity"]))
                for row in filtered_cycles
                if row["allocation_mode"] == "Total a repartir" and float(row["target_quantity"]) > 0
            ]
            average_completion = sum(completion_values) / len(completion_values) if completion_values else 0.0
            with st.container(key="summary_metrics"):
                metrics_slot = st.empty()
                metrics_slot.markdown(daily_metrics_markdown(filtered_cycles))

            summary_rows = []
            for detail in filtered_details:
                cycle = detail["cycle"]
                target_value = float(cycle["target_quantity"])
                loaded_value = float(cycle["accumulated"])
                has_objective = cycle["allocation_mode"] == "Total a repartir" and target_value > 0
                progress = min(1.0, loaded_value / target_value) if has_objective else None
                summary_rows.append(
                    {
                        "Trabajo": cycle["status"],
                        "Aviso": "",
                        "Finca": detail["farm"],
                        "Lote": detail["lot"],
                        "Tarea": detail["task"],
                        "Ciclo": cycle["cycle_no"],
                        "Unidad": cycle["unit"],
                        "Objetivo": target_value if has_objective else None,
                        "Cargado": loaded_value,
                        "Restante": max(0.0, target_value - loaded_value) if has_objective else None,
                        "Avance": progress,
                        "Insumo": detail["input"],
                        "Dosis": float(cycle.get("input_dose") or 0),
                    }
                )
            if not summary_rows:
                st.info("No hay partes cargados que coincidan con los filtros seleccionados.")
            else:
                with st.container(border=True, key="daily_table_toolbar"):
                    toolbar_columns = st.columns([1, 4], vertical_alignment="center")
                    with toolbar_columns[0]:
                        st.subheader("Parte diario", anchor=False)
                    with toolbar_columns[1]:
                        summary_query = st.text_input(
                            "Buscar en partes", key="summary_search", type="search", icon=":material/search:",
                            placeholder="Buscar por finca, lote, tarea, insumo o personal...",
                            label_visibility="collapsed", live=True,
                        )
                personnel_by_part = {}
                inputs_by_part = {}
                documents_by_code = {}
                with closing(sqlite3.connect(DATABASE)) as database:
                    database.row_factory = sqlite3.Row
                    documents_by_code = {
                        str(row["report_code"]): dict(row)
                        for row in database.execute("SELECT * FROM daily_reports")
                    }
                    for part_id, personnel_key, machine_key, start_time, end_time in database.execute(
                        """SELECT part_id, personnel_key, machine_key, machine_start_time, machine_end_time
                           FROM partial_allocations ORDER BY id"""
                    ):
                        person_name = text(people_by_key.get(personnel_key), "EMPLEADO") or personnel_key
                        machine = machines_by_key.get(machine_key) if machine_key else None
                        vehicle_id = (text(machine, "ID_Equipo") or machine_key) if machine_key else ""
                        personnel_by_part.setdefault(int(part_id), set()).add(
                            (person_name, vehicle_id, start_time or "", end_time or "")
                        )
                    for part_id, input_key, quantity, input_unit in database.execute(
                        "SELECT part_id, input_key, quantity, unit FROM partial_inputs ORDER BY id"
                    ):
                        input_record = inputs_by_key.get(str(input_key))
                        description = text(input_record, "DESCRIPCION") or str(input_key)
                        inputs_by_part.setdefault(int(part_id), []).append(
                            f"- {description} — {float(quantity):,.1f} {input_unit}"
                        )
                daily_rows = []
                for detail, summary in zip(filtered_details, summary_rows):
                    all_cycle_parts = parts_by_cycle.get(int(detail["cycle"]["id"]), [])
                    cumulative_by_part = {}
                    running_total = 0.0
                    for ordered_part in sorted(all_cycle_parts, key=lambda row: (row["part_date"], int(row["id"]))):
                        running_total += float(ordered_part["quantity"])
                        cumulative_by_part[int(ordered_part["id"])] = running_total
                    cycle_parts = list(all_cycle_parts)
                    if input_filter != "Todos" and cycle_parts:
                        cycle_parts = [part for part in cycle_parts if input_filter in part_input_labels(part)]
                    for part in cycle_parts:
                        part_id = int(part["id"])
                        report_code = part.get("report_code") or part.get("part_code") or f"legacy{part_id:04d}"
                        document = documents_by_code.get(str(report_code), {})
                        if document.get("document_status") == "Enviado":
                            continue
                        part_accumulated = cumulative_by_part.get(part_id, 0.0)
                        objective = float(summary["Objetivo"] or 0)
                        unit_label = "Ha" if str(summary["Unidad"]).upper() == "HA" else str(summary["Unidad"])
                        warning_detail = (
                            f"⚠\n\nLa cantidad del parte diario es {part_accumulated:,.1f} {unit_label}, "
                            f"superando el objetivo de {objective:,.1f} {unit_label}"
                            if detail["cycle"]["allocation_mode"] == "Total a repartir"
                            and objective > 0 and part_accumulated > objective + 0.01 else ""
                        )
                        daily_rows.append({
                            "Seleccionar": False if part else None,
                            "_part_id": int(part["id"]) if part else None,
                            "_cycle_id": int(detail["cycle"]["id"]) if part else None,
                            "ID parte": report_code,
                            "Estado": summary_report_status(document.get("document_status"), [summary["Trabajo"]]),
                            "Fecha": part["part_date"] if part else "",
                            **summary,
                            "Cultivo": part.get("crop") if part and part.get("crop") is not None else text(lots_by_key.get(detail["cycle"]["lot_key"]), "CULTIVO"),
                            "Aviso": warning_detail,
                            "Frente": ("Manual" if part["front_name"] == "__MANUAL__" else part["front_name"]) if part else "",
                            "Personal y vehículo": "\n".join(
                                (
                                    f"- {name} — {vehicle_id} ({start_time} a {end_time} h-km)"
                                    if vehicle_id and start_time and end_time
                                    else f"- {name} — {vehicle_id}" if vehicle_id else f"- {name}"
                                )
                                for name, vehicle_id, start_time, end_time
                                in sorted(personnel_by_part.get(int(part["id"]), set()))
                            ) if part else "",
                            "Cantidad parte": float(part["quantity"]) if part else 0.0,
                            "Insumo": "\n".join(inputs_by_part.get(part_id, [])) or "Sin insumo",
                            "Dosis": float(part.get("input_dose") or 0) if part else summary["Dosis"],
                            "Cantidad insumo": float(part.get("input_quantity") or 0) if part else 0.0,
                            "Unidad insumo": (part.get("input_unit") or text(inputs_by_key.get(part.get("input_key")), "UNIDAD")) if part else "",
                            "Observaciones": part["notes"] if part else "",
                        })
                if not daily_rows:
                    st.info("No hay partes pendientes con estos filtros. Los enviados están en Mis partes.")
                    st.stop()
                daily_frame = pd.DataFrame(daily_rows)
                daily_frame = filter_daily_frame(daily_frame, summary_query)
                searched_cycle_ids = {int(value) for value in daily_frame["_cycle_id"].dropna()}
                metrics_slot.markdown(daily_metrics_markdown([cycle for cycle in filtered_cycles if int(cycle["id"]) in searched_cycle_ids]))
                # "Ciclo" sigue existiendo internamente para relacionar partes,
                # acumulados y cierres, pero no aporta información al usuario en
                # la grilla de resumen.
                daily_frame = daily_frame.drop(
                    columns=["Cargado", "Ciclo", "Trabajo", "Estado", "Unidad insumo", "Cantidad insumo", "Dosis"],
                    errors="ignore",
                )
                column_order = list(daily_frame.columns)
                column_order.remove("Cultivo")
                column_order.insert(column_order.index("Finca"), "Cultivo")
                column_order.remove("Cantidad parte")
                column_order.insert(column_order.index("Unidad") + 1, "Cantidad parte")
                daily_frame = daily_frame[column_order]
                visible_part_ids = tuple(int(value) for value in daily_frame["_part_id"].dropna())
                edited_parts = render_daily_grid(
                    daily_frame,
                    key=f"summary_grid_v1_{st.session_state.summary_delete_version}_{tuple(int(c['id']) for c in filtered_cycles)}_{visible_part_ids}",
                )
                selected_rows = [
                    row for row in edited_parts.to_dict("records")
                    if bool(row["Seleccionar"]) and pd.notna(row["_part_id"])
                    and int(row["_part_id"]) in visible_part_ids
                ]
                selected_part_ids = sorted({int(row["_part_id"]) for row in selected_rows})
                selected_report_codes = sorted({str(row["ID parte"]) for row in selected_rows})
                selected_cycle_ids = sorted({int(row["_cycle_id"]) for row in selected_rows})
                selected_cycle_map = {int(cycle["id"]): cycle for cycle in filtered_cycles}
                selected_open_cycles = [
                    selected_cycle_map[cycle_id] for cycle_id in selected_cycle_ids
                    if cycle_id in selected_cycle_map and selected_cycle_map[cycle_id]["status"] == "Abierto"
                ]
                if len(selected_report_codes) > 1:
                    st.info("Seleccioná un solo parte para revisarlo y enviarlo.")
                selected_document = (
                    get_report_document(DATABASE, selected_report_codes[0])
                    if len(selected_report_codes) == 1 else None
                )
                selected_document_status = (
                    str(selected_document.get("document_status") or "Borrador")
                    if selected_document else ""
                )
                if selected_document is None and len(selected_report_codes) == 1:
                    st.warning("Este registro anterior no tiene cabecera documental y sólo admite las acciones históricas.")
                with st.container(horizontal=True):
                    if st.button(
                        "Revisar y enviar", icon=":material/send:",
                        disabled=selected_document is None,
                        help="Revisá los datos, guardalos y envialos desde una sola ventana.",
                    ):
                        review_report_dialog(selected_report_codes[0])
                    if st.button(
                        "Vista previa", icon=":material/preview:",
                        disabled=selected_document is None,
                        help="Consultá todos los datos del parte.",
                    ):
                        preview_report_dialog(selected_report_codes[0])
                    pdf_ready = selected_document_status in {"Revisado", "Enviado"}
                    if pdf_ready:
                        try:
                            selected_pdf_code = selected_report_codes[0]
                            pdf_generator = pdf_report
                            pdf_data = pdf_generator.build_daily_report_pdf(
                                DATABASE,
                                selected_pdf_code,
                                people_by_key=people_by_key,
                                machines_by_key=machines_by_key,
                                lots_by_key=lots_by_key,
                                operations_by_key=operations_by_key,
                                inputs_by_key=inputs_by_key,
                            )
                            st.download_button(
                                "Descargar PDF",
                                data=pdf_data,
                                file_name=report_pdf_filename(selected_pdf_code, selected_document["report_date"]),
                                mime="application/pdf",
                                icon=":material/picture_as_pdf:",
                            )
                        except (ValueError, sqlite3.Error) as error:
                            st.error(f"No se pudo preparar el PDF: {error}")
                    else:
                        st.button(
                            "Descargar PDF", icon=":material/picture_as_pdf:", disabled=True,
                            help="Primero revisá y guardá los datos desde Revisar y enviar.",
                        )
                if st.button(
                    "Eliminar partes seleccionados",
                    icon=":material/delete:",
                    disabled=not selected_part_ids or any(
                        documents_by_code.get(code, {}).get("sent_at") or
                        documents_by_code.get(code, {}).get("document_status") == "Enviado" or
                        has_sent_revision(DATABASE, code) for code in selected_report_codes
                    ),
                    help="Los partes enviados se corrigen conservando su historial; no se eliminan.",
                ):
                    try:
                        deleted = delete_complete_reports(DATABASE, selected_part_ids)
                        st.session_state.summary_flash = (
                            f"Se eliminaron {deleted} parte(s). Los acumulados y saldos se recalcularon automáticamente."
                        )
                        st.session_state.summary_delete_version += 1
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
        st.stop()

    if lot_view == "Carga parte":
        st.subheader("Nuevo parte", icon=":material/edit_note:", anchor=False)
        if st.session_state.multi_part_flash:
            st.success(st.session_state.multi_part_flash, icon=":material/check_circle:")
            st.session_state.multi_part_flash = None
        staged_lines = st.session_state.multi_part_lines
        if staged_lines:
            with st.container(border=True):
                st.subheader("Tareas del parte", icon=":material/playlist_add_check:", anchor=False)
                staged_table = st.data_editor(
                    pd.DataFrame([
                        {
                            "Seleccionar": False,
                            "Tarea": task_display_label(line["operation_key"]),
                            "Cultivo": line.get("crop") if line.get("crop") is not None else text(lots_by_key.get(line["lot_key"]), "CULTIVO"),
                            "Finca": text(lots_by_key.get(line["lot_key"]), "FINCA"),
                            "Lote": text(lots_by_key.get(line["lot_key"]), "ID_Lote"),
                            "Frente": line["front_name"],
                            "Cantidad": line["quantity"],
                            "Unidad": line["unit"],
                            "Personas": len(line["allocations"]),
                        }
                        for line in staged_lines
                    ]),
                    key=f"staged_tasks_{tuple((line['operation_key'], line['lot_key'], line['front_id']) for line in staged_lines)}",
                    hide_index=True, width="stretch",
                    disabled=["Tarea", "Cultivo", "Finca", "Lote", "Frente", "Cantidad", "Unidad", "Personas"],
                    column_config={"Seleccionar": st.column_config.CheckboxColumn("✓", width=45, help="Seleccioná las tareas que querés quitar del borrador.")},
                    alt="Tareas del parte: seleccioná las que quieras quitar",
                )
                selected_staged_positions = {
                    position for position, row in enumerate(staged_table.to_dict(orient="records"))
                    if bool(row.get("Seleccionar"))
                }
                with st.container(horizontal=True):
                    if st.button("Guardar parte completo", icon=":material/save:", type="primary"):
                        try:
                            report_code = create_multi_task_report(
                                staged_lines, staged_lines[0]["date"], operator_code,
                                "",
                            )
                            st.session_state.multi_part_lines = []
                            st.session_state["multi_part_header"] = {}
                            st.session_state.pop("part_service_order", None)
                            st.session_state.report_front_task_choices = {}
                            for choice_key in list(st.session_state):
                                if str(choice_key).startswith("report_front_tasks_"):
                                    st.session_state.pop(choice_key, None)
                            st.session_state.allocation_draft = None
                            st.session_state.part_flash = (
                                f"Parte {report_code} guardado correctamente con {len(staged_lines)} tarea(s)."
                            )
                            st.session_state.review_saved_report = report_code
                            st.rerun()
                        except (ValueError, sqlite3.Error) as error:
                            st.error(str(error))
                    if st.button(
                        "Quitar tarea seleccionada" if len(selected_staged_positions) <= 1 else "Quitar tareas seleccionadas",
                        icon=":material/remove:", disabled=not selected_staged_positions,
                    ):
                        st.session_state.multi_part_lines = [
                            line for position, line in enumerate(staged_lines) if position not in selected_staged_positions
                        ]
                        st.rerun()
                    if st.button("Descartar borrador", icon=":material/delete:"):
                        st.session_state.multi_part_lines = []
                        st.session_state.report_front_task_choices = {}
                        for choice_key in list(st.session_state):
                            if str(choice_key).startswith("report_front_tasks_"):
                                st.session_state.pop(choice_key, None)
                        st.session_state.allocation_draft = None
                        st.rerun()
        if st.session_state.part_flash:
            quantity_key_to_reset = st.session_state.pop("part_quantity_to_reset", None)
            if quantity_key_to_reset:
                st.session_state[quantity_key_to_reset] = 0.0
            st.session_state.partial_notes = ""
            st.session_state["partial_staff_mode_v2"] = "Carga manual"
            st.session_state["partial_fronts_v2"] = []
            st.session_state["partial_front_v3"] = None
            st.session_state["partial_manual_people_v2"] = []
            st.success(st.session_state.part_flash, icon=":material/check_circle:")
            st.session_state.part_flash = None
        # Shared report header survives task changes and widget cleanup.
        report_header = st.session_state.setdefault("multi_part_header", {})
        if staged_lines:
            report_header["date"] = date.fromisoformat(staged_lines[0]["date"])
        for widget_key, header_key in (
            ("partial_date", "date"), ("part_farm", "farm"), ("part_lot", "lot"),
        ):
            if widget_key not in st.session_state and header_key in report_header:
                st.session_state[widget_key] = report_header[header_key]
        with st.container(border=True):
            st.subheader("Datos del parte y ubicación de la tarea", anchor=False)
            st.caption(
                "La fecha pertenece al parte completo. La finca, el lote y el cultivo corresponden "
                "solamente a la tarea que estás cargando. OS se completará a mano en el PDF."
            )
            header_columns = st.columns([1, 2, 2, 1.7])
            with header_columns[0]:
                partial_date = st.date_input("Fecha", key="partial_date", disabled=bool(staged_lines))
            farm_options = sorted({text(lot, "FINCA") for lot in masters["lotes"] if text(lot, "FINCA")})
            if st.session_state.get("part_farm") not in farm_options:
                st.session_state.pop("part_farm", None)
            with header_columns[1]:
                selected_farm = st.selectbox(
                    "Finca", farm_options, key="part_farm", on_change=reset_new_part_context,
                )
            farm_lots = {key: lot for key, lot in lots_by_key.items() if text(lot, "FINCA") == selected_farm}
            if st.session_state.get("part_lot") not in farm_lots:
                st.session_state.pop("part_lot", None)
            with header_columns[2]:
                selected_lot_key = st.selectbox(
                    "Lote", list(farm_lots),
                    format_func=lambda key: f"{text(farm_lots[key], 'ID_Lote')} — {text(farm_lots[key], 'LOTE')}",
                    key="part_lot", on_change=reset_new_part_context,
                )
            suggested_crop = text(lots_by_key.get(selected_lot_key), "CULTIVO").strip()
            crop_options = sorted({text(lot, "CULTIVO").strip() for lot in masters["lotes"] if text(lot, "CULTIVO").strip()})
            default_crop = (
                report_header.get("crop", suggested_crop)
                if report_header.get("lot") == selected_lot_key
                else suggested_crop
            )
            default_crop = str(default_crop or "").strip()
            # Preserve an existing draft's edited crop, even if the inventory changed.
            if default_crop and default_crop not in crop_options:
                crop_options.append(default_crop)
                crop_options.sort()
            with header_columns[3]:
                crop = st.selectbox(
                    "Cultivo", crop_options,
                    index=crop_options.index(default_crop) if default_crop in crop_options else None,
                    key=f"part_crop_select_{selected_lot_key}",
                    placeholder="Seleccionar cultivo",
                    help="Cultivos disponibles en el inventario. Se sugiere el del lote seleccionado; podés elegir otro para este parte.",
                ) or ""
            report_header.update(
                date=partial_date, farm=selected_farm, lot=selected_lot_key, crop=crop,
            )
            if staged_lines:
                st.caption(
                    "Fecha fijada para este borrador. "
                    "Podés cambiar finca, lote y cultivo antes de agregar la siguiente tarea."
                )
        fronts = list_fronts(DATABASE)
        if st.session_state.get("partial_staff_mode_v2") == "Frentes configurados":
            st.session_state["partial_staff_mode_v2"] = "Frentes"
        staff_mode = st.segmented_control(
            "¿Cómo vas a cargar el parte?",
            ["Frentes", "Carga manual"],
            default="Carga manual",
            key="partial_staff_mode_v2", disabled=bool(staged_lines),
            on_change=reset_partial_cycle_context,
        ) or "Carga manual"
        front_map = {row["id"]: row for row in fronts}
        selected_front_ids = []
        selected_front_id = None
        configured_front_members = []
        configured_task_keys = []
        pending_front_task_keys = []
        if staff_mode == "Frentes":
            if not fronts:
                st.warning("No hay frentes configurados. Elegí “Carga manual” o creá un frente.")
            else:
                selected_front_id = st.selectbox(
                    "Frente",
                    list(front_map),
                    index=None,
                    placeholder="Seleccionar frente",
                    format_func=lambda key: front_map[key]["name"],
                    key="partial_front_v3", disabled=bool(staged_lines),
                    on_change=reset_partial_cycle_context,
                    help="Se cargarán las tareas, las personas y las máquinas configuradas para este frente.",
                    width="stretch",
                )
                if selected_front_id is not None:
                    selected_front_ids = [selected_front_id]
                    configured_front_members = list_front_task_members_local(DATABASE, selected_front_id)
                    configured_task_keys = list(dict.fromkeys(
                        member["operation_key"] for member in configured_front_members
                        if member["operation_key"] in operations_by_key
                    ))
                    available_front_task_keys = list(configured_task_keys)
                    if available_front_task_keys:
                        task_selection_key = f"report_front_tasks_{selected_front_id}"
                        included_front_task_keys = st.multiselect(
                            "Tareas a incluir en este parte", available_front_task_keys,
                            default=[key for key in st.session_state.get("report_front_task_choices", {}).get(selected_front_id, available_front_task_keys) if key in available_front_task_keys],
                            format_func=task_display_label,
                            key=task_selection_key,
                            on_change=update_front_report_tasks,
                            args=(selected_front_id, task_selection_key), width="stretch",
                            help="Quitá con la × las tareas que no vas a cargar. También se quitarán del borrador si ya estaban agregadas. El frente guardado no cambia.",
                        )
                        included_front_tasks = set(included_front_task_keys)
                        configured_task_keys = [key for key in available_front_task_keys if key in included_front_tasks]
                        skipped_count = len(available_front_task_keys) - len(configured_task_keys)
                        if skipped_count:
                            st.caption(f"{skipped_count} tarea(s) excluida(s) solamente de este parte.")
                    if configured_task_keys:
                        completed_task_keys = {
                            line["operation_key"] for line in staged_lines
                            if line.get("front_id") == selected_front_id
                        }
                        pending_front_task_keys = [
                            key for key in configured_task_keys if key not in completed_task_keys
                        ]
                        next_task_key = pending_front_task_keys[0] if pending_front_task_keys else None
                        st.markdown("**Tareas incluidas en el frente**")
                        for task_position, task_key in enumerate(configured_task_keys, start=1):
                            task_label = task_display_label(task_key)
                            if task_key in completed_task_keys:
                                st.success(
                                    f"Tarea {task_position} de {len(configured_task_keys)} completada: {task_label}",
                                    icon=":material/check_circle:",
                                )
                            elif task_key == next_task_key:
                                st.html(
                                    f'<div role="status" aria-label="Tarea actual" style="background:#526747;'
                                    f'color:#F6F5F0;border-radius:10px;padding:18px 20px;margin:0 0 8px;'
                                    f'box-shadow:0 2px 6px #25312a14">'
                                    f'<div style="font-weight:700;margin-bottom:8px">→ TAREA ACTUAL · {task_position} de {len(configured_task_keys)}</div>'
                                    f'<div>{escape(task_label)}</div></div>'
                                )
                            else:
                                with st.container(border=True):
                                    st.markdown(
                                        f":material/radio_button_unchecked: **Pendiente · Tarea {task_position} de "
                                        f"{len(configured_task_keys)}** — {task_label}"
                                    )
                        if pending_front_task_keys:
                            st.info(
                                f"Ahora completá: {task_display_label(next_task_key)}. "
                                "Después continuará automáticamente con la siguiente tarea incluida.",
                                icon=":material/arrow_downward:",
                            )
                        else:
                            st.success(
                                "Todas las tareas del frente están preparadas. Ya podés guardar el parte completo.",
                                icon=":material/check_circle:",
                            )
                    else:
                        st.warning("Seleccioná al menos una tarea para este parte." if available_front_task_keys else "Este frente todavía no tiene tareas con integrantes configurados.")
        with st.container(border=True):
            st.subheader("Datos de la tarea", anchor=False)
            if staff_mode == "Frentes":
                if not configured_task_keys:
                    st.info("Seleccioná un frente y al menos una tarea para continuar.")
                    st.stop()
                if not pending_front_task_keys:
                    st.stop()
                selected_operation_key = pending_front_task_keys[0]
                current_task_position = configured_task_keys.index(selected_operation_key) + 1
                st.markdown(
                    f"**Tarea {current_task_position} de {len(configured_task_keys)}:** "
                    + task_display_label(selected_operation_key)
                )
            else:
                selected_operation_key = st.selectbox(
                    "Tarea", list(operations_by_key),
                    format_func=lambda key: task_display_label(key),
                    key="part_operation", on_change=reset_partial_cycle_context,
                )
            selected_lot = lots_by_key[selected_lot_key]
            operation = operations_by_key[selected_operation_key]
            allowed_machines = operation_machines(operation)
            required_machine_groups = operation_machine_groups(operation)
            inputs_enabled = operation_requires_inputs(operation)
            open_match = next((row for row in list_cycles(DATABASE, "Abierto")
                               if row["lot_key"] == selected_lot_key
                               and row["operation_key"] == selected_operation_key), None)
            unit = text(operation, "Unidad_Medida")
            allocation_mode = "Total a repartir" if unit.upper() in {"SC", "HA", "TN"} else "Cantidad individual"
            context_key = str(open_match["id"]) if open_match else f"new_{selected_lot_key}_{selected_operation_key}"
            cycle_id = open_match["id"] if open_match else None
            cycle = open_match or {
                "unit": unit, "allocation_mode": allocation_mode,
                "target_quantity": 0.0, "accumulated": 0.0,
            }
            unit = cycle["unit"]
            person_hours_enabled = task_uses_person_hours(unit)
            allocation_mode = cycle["allocation_mode"]
            st.caption(f"Unidad: {unit} — {text(operation, 'Descripcion_Unidad_Medida')}")
            if required_machine_groups:
                st.caption("Máquinas habilitadas: **" + ", ".join(required_machine_groups) + "**")
            accumulated = float(cycle["accumulated"])
            proposed_target = 0.0
            if unit.upper() == "SC":
                proposed_target = float(text(selected_lot, "SURCOS") or 0)
            elif unit.upper() == "HA":
                proposed_target = float(text(selected_lot, "AREA N") or text(selected_lot, "AREA B") or 0)
            quantity_label = f"Cantidad total ({unit})" if allocation_mode == "Total a repartir" else f"Cantidad por persona ({unit})"
            progress_columns = st.columns([1.15, 1, 1, 1], vertical_alignment="bottom")
            with progress_columns[0]:
                partial_quantity = st.number_input(
                    quantity_label, min_value=0.0, step=1.0, key=f"part_quantity_{context_key}",
                )
            if allocation_mode == "Total a repartir":
                # Hectares and furrows come from the selected inventory lot.
                target = proposed_target if unit.upper() in {"HA", "SC"} else (float(cycle["target_quantity"]) if open_match else 0.0)
                progress_columns[1].metric(
                    "Objetivo del lote", f"{target:,.1f} {unit}" if target > 0 else "Sin dato",
                    help="Dato del inventario: área neta (o bruta si falta la neta) para hectáreas; cantidad de surcos para SC.",
                )
                progress_columns[2].metric(
                    "Registrado antes", f"{accumulated:,.1f} {unit}",
                    help="Suma de los partes ya guardados para esta tarea en este lote. No incluye este parte.",
                )
                progress_columns[3].metric(
                    "Falta después de este parte", f"{max(0.0, target - accumulated - partial_quantity):,.1f} {unit}" if target > 0 else "Sin objetivo",
                    help="Objetivo menos lo registrado antes y la cantidad de este parte. Se actualiza mientras cargás.",
                )
            else:
                target = 0.0
                progress_columns[1].metric("Registrado antes", f"{accumulated:,.1f} {unit}",
                    help="Suma de los partes ya guardados para esta tarea en este lote.")
                progress_columns[2].metric("Objetivo del lote", "No aplica")
            notes = st.text_input("Observaciones", key="partial_notes")

        remaining = max(0.0, target - accumulated)
        projected_total = accumulated + partial_quantity
        exceeds_target = (
            allocation_mode == "Total a repartir"
            and target > 0
            and projected_total > target + 0.01
        )
        if exceeds_target:
            st.warning(
                f"La cantidad del parte diario es {projected_total:,.1f} {unit}, "
                f"superando el objetivo de {target:,.1f} {unit}. Podés guardar igualmente."
            )
        new_cycle = None if open_match else {
            "lot_key": selected_lot_key, "operation_key": selected_operation_key,
            "target_quantity": target, "unit": unit, "allocation_mode": allocation_mode,
            "started_on": partial_date.isoformat(),
        }

        part_inputs = []
        if inputs_enabled:
            selected_inputs_state = f"part_selected_inputs_{context_key}"
            input_search_key = f"part_input_search_{context_key}"
            if selected_inputs_state not in st.session_state:
                initial_input = cycle.get("input_key")
                st.session_state[selected_inputs_state] = [initial_input] if initial_input in inputs_by_key else []

            def add_part_input(input_key):
                selected_inputs = list(st.session_state.get(selected_inputs_state, []))
                if input_key in inputs_by_key and input_key not in selected_inputs:
                    selected_inputs.append(input_key)
                    st.session_state[selected_inputs_state] = selected_inputs
                    st.session_state[input_search_key] = ""

            st.subheader("Insumos y dosis", icon=":material/science:", anchor=False)
            st.caption("Buscá el producto y tocá el resultado. Se agrega directamente al parte.")
            search_value = st.text_input(
                "Buscar insumo", type="search", live=True,
                placeholder="Escribí el nombre o código: urea, glifosato, 16070023...",
                icon=":material/search:", key=input_search_key,
                label_visibility="collapsed",
            )
            selected_input_keys = list(st.session_state.get(selected_inputs_state, []))
            selected_inputs = set(selected_input_keys)

            with closing(sqlite3.connect(DATABASE)) as database:
                frequent_rows = database.execute(
                    """SELECT input_key, COUNT(*) AS uses FROM partial_inputs
                       WHERE input_key IS NOT NULL AND input_key <> ''
                       GROUP BY input_key ORDER BY uses DESC, input_key LIMIT 4"""
                ).fetchall()
            frequent_keys = [str(row[0]) for row in frequent_rows if str(row[0]) in inputs_by_key]
            if len(frequent_keys) < 4:
                fallback_keys = sorted(
                    inputs_by_key,
                    key=lambda key: normalize(text(inputs_by_key[key], "DESCRIPCION")),
                )
                frequent_keys.extend(key for key in fallback_keys if key not in frequent_keys)
                frequent_keys = frequent_keys[:4]

            search_terms = normalize(search_value).split()
            if search_terms:
                catalog_results = [
                    key for key, record in inputs_by_key.items()
                    if key not in selected_inputs and all(
                        term in normalize(
                            f"{key} {text(record, 'DESCRIPCION')} {text(record, 'UNIDAD')}"
                        )
                        for term in search_terms
                    )
                ]
                catalog_results.sort(key=lambda key: normalize(text(inputs_by_key[key], "DESCRIPCION")))
                if not catalog_results:
                    st.info("No encontramos productos con ese nombre o código.")
                else:
                    st.caption("Tocá un resultado para agregarlo")
                    for result_key in catalog_results[:6]:
                        result_record = inputs_by_key[result_key]
                        description = text(result_record, "DESCRIPCION") or result_key
                        result_unit = text(result_record, "UNIDAD") or "-"
                        st.button(
                            f"{description} · {result_key} · {result_unit}",
                            icon=":material/add_circle:",
                            key=f"inline_input_result_{context_key}_{result_key}",
                            on_click=add_part_input, args=(result_key,),
                            width="stretch",
                        )
                    if len(catalog_results) > 6:
                        st.caption("Hay más coincidencias. Escribí más letras para precisar la búsqueda.")
            elif frequent_keys:
                st.caption("Productos frecuentes")
                with st.container(horizontal=True, wrap=True):
                    for frequent_key in frequent_keys:
                        frequent_record = inputs_by_key[frequent_key]
                        description = text(frequent_record, "DESCRIPCION") or frequent_key
                        st.button(
                            description,
                            icon=":material/eco:",
                            key=f"inline_frequent_input_{context_key}_{frequent_key}",
                            on_click=add_part_input, args=(frequent_key,),
                            disabled=frequent_key in selected_inputs,
                        )

            if selected_input_keys:
                st.caption("Insumos agregados")
            for input_position, selected_key in enumerate(selected_input_keys):
                selected_record = inputs_by_key.get(selected_key)
                if not selected_record:
                    continue
                selected_unit = text(selected_record, "UNIDAD")
                with st.container(border=True, key=f"part_input_card_{context_key}_{selected_key}"):
                    input_columns = st.columns([2.7, 1, 1, .62], vertical_alignment="bottom")
                    with input_columns[0]:
                        st.markdown(f"**{text(selected_record, 'DESCRIPCION') or selected_key}**")
                        st.caption(f"Código {selected_key} · Unidad {selected_unit or '-'}")
                    with input_columns[1]:
                        selected_dose = st.number_input(
                            "Dosis", min_value=0.0,
                            value=float(cycle.get("input_dose") or 0) if input_position == 0 else 0.0,
                            step=0.001, format="%.3f",
                            key=f"part_dose_{context_key}_{input_position}_{selected_key}",
                        )
                    estimated_quantity = calculate_input_total(
                        partial_quantity, selected_dose, selected_unit
                    )
                    with input_columns[2]:
                        selected_quantity = st.number_input(
                            f"Cantidad ({selected_unit or 'unidad'})", min_value=0.0,
                            value=float(estimated_quantity), step=0.1, format="%.1f",
                            key=(
                                f"part_input_quantity_{context_key}_{input_position}_"
                                f"{selected_key}_{partial_quantity}_{selected_dose}"
                            ),
                        )
                    with input_columns[3]:
                        if st.button(
                            "Quitar", icon=":material/delete:",
                            key=f"remove_input_{context_key}_{selected_key}",
                            type="tertiary",
                        ):
                            st.session_state[selected_inputs_state] = [
                                key for key in selected_input_keys if key != selected_key
                            ]
                            st.rerun()
                    part_inputs.append({
                        "input_key": selected_key,
                        "dose": calculate_dose_from_total(
                            selected_quantity, partial_quantity, selected_unit
                        ),
                        "quantity": selected_quantity,
                        "unit": selected_unit,
                    })
        else:
            st.caption(":material/block: Esta tarea no admite carga de insumos.")
        first_input = part_inputs[0] if part_inputs else {"input_key": None, "dose": 0, "quantity": 0, "unit": ""}
        selected_input_key = first_input["input_key"]
        partial_dose = first_input["dose"]
        partial_input_quantity = first_input["quantity"]
        input_unit = first_input["unit"]

        st.subheader("Personal y vehículos", icon=":material/groups:", anchor=False)
        members = []
        if staff_mode == "Frentes":
            members = [
                {**member, "_front_id": selected_front_id}
                for member in configured_front_members
                if member["operation_key"] == selected_operation_key
            ]
            selection_signature = [staff_mode, selected_front_id, selected_operation_key]
            st.caption(
                f"Personal y máquinas de la tarea {selected_operation_key} configurados en "
                f"el frente {front_map[selected_front_id]['name']}."
            )
        else:
            manual_front_id = get_or_create_manual_front(DATABASE)
            selected_personnel = st.multiselect(
                "Personas del parte",
                list(people_by_key),
                format_func=lambda key: f"{text(people_by_key.get(key), 'EMPLEADO')} — {key}",
                key="partial_manual_people_v2",
                help="Seleccioná las personas para este parte. Después podrás asignar o editar su máquina.",
                width=700,
            )
            selected_front_ids = [manual_front_id] if selected_personnel else []
            members = [
                {"personnel_key": personnel_key, "machine_key": None, "_front_id": manual_front_id}
                for personnel_key in selected_personnel
            ]
            selection_signature = [staff_mode, *selected_personnel]
        unique_members = {}
        for member in members:
            unique_members.setdefault(member["personnel_key"], member)
        if len(unique_members) < len(members):
            st.caption("Las personas que figuran en más de un frente se incluyen una sola vez.")
        members = list(unique_members.values())
        incompatible_habitual = sum(
            1 for member in members
            if member.get("machine_key") and member.get("machine_key") not in allowed_machines
        )
        if incompatible_habitual:
            st.warning(
                f"{incompatible_habitual} máquina(s) habitual(es) del frente no corresponden a esta tarea. "
                "Elegí una máquina compatible en la grilla."
            )
        # Rebuild only when the form changes; preserve edited distribution on other reruns.
        form_signature = [
            "machine_meter_v4", context_key, *selection_signature, partial_quantity, *required_machine_groups,
        ]
        previous_draft = st.session_state.allocation_draft
        if previous_draft:
            legacy_meter_keys = {"H/Km inicio", "H/Km fin"}
            editor_state = st.session_state.get(f"allocation_editor_v3_{st.session_state.allocation_version}") or {}
            pending_rows = editor_state.get("edited_rows", {}) if isinstance(editor_state, dict) else {}
            needs_meter_migration = any(
                legacy_meter_keys.intersection(row) for row in previous_draft.get("rows", [])
            ) or any(legacy_meter_keys.intersection(changes) for changes in pending_rows.values())
            if needs_meter_migration:
                quantities_before = [float(row.get("Cantidad", 0) or 0) for row in previous_draft.get("rows", [])]
                apply_pending_allocation_edits(previous_draft)
                previous_draft["rows"] = [normalize_meter_row(row) for row in previous_draft.get("rows", [])]
                for row, quantity_before in zip(previous_draft["rows"], quantities_before):
                    if row.get("Estado") == "Presente" and abs(float(row.get("Cantidad", 0) or 0) - quantity_before) > 0.001:
                        row["Estado"] = "Cantidad fija"
                st.session_state.allocation_version += 1
        preserved_rows = {}
        if previous_draft and previous_draft.get("form_signature") != form_signature:
            preserve_staff_edits = (
                previous_draft.get("context_key") == context_key
                and float(previous_draft.get("declared", 0)) == float(partial_quantity)
                and previous_draft.get("selection_signature", [None])[0] == selection_signature[0]
            )
            if preserve_staff_edits:
                previous_quantities = {
                    str(row["Legajo"]): float(row.get("Cantidad", 0) or 0)
                    for row in allocation_editor_base_rows(previous_draft)
                }
                apply_pending_allocation_edits(previous_draft)
                preserved_rows = {
                    str(row["Legajo"]): row.copy()
                    for row in previous_draft.get("rows", [])
                }
                # An explicitly edited quantity remains fixed when the staff changes.
                for personnel_key, row in preserved_rows.items():
                    if (
                        row.get("Estado") == "Presente"
                        and abs(float(row.get("Cantidad", 0) or 0) - previous_quantities[personnel_key]) > 0.001
                    ):
                        row["Estado"] = "Cantidad fija"
            st.session_state.allocation_draft = None
        if members and partial_quantity > 0 and st.session_state.allocation_draft is None:
            if preserved_rows and cycle["allocation_mode"] == "Total a repartir":
                initial = [{"Estado": "Presente", "Cantidad": 0.0} for _ in members]
            elif cycle["allocation_mode"] == "Total a repartir":
                initial = redistribute_rows(
                    [{"Estado": "Presente", "Cantidad": 0.0} for _ in members], partial_quantity,
                    integers=cycle["unit"].upper() == "SC",
                )
            else:
                initial = [{"Estado": "Presente", "Cantidad": partial_quantity} for _ in members]
            draft_rows = []
            for member, allocation in zip(members, initial):
                person = people_by_key.get(member["personnel_key"])
                machine = machines_by_key.get(member["machine_key"])
                compatible_machine_key = member["machine_key"] if member["machine_key"] in allowed_machines else ""
                preserved = preserved_rows.get(str(member["personnel_key"]))
                row = {
                        "Seleccionar": False,
                        "Frente": (
                            "Manual" if staff_mode == "Carga manual"
                            else front_map[member["_front_id"]]["name"]
                        ),
                        "Legajo": member["personnel_key"],
                        "Empleado": text(person, "EMPLEADO"),
                        "Estado": allocation["Estado"],
                        "Horas persona": float(default_person_hours) if person_hours_enabled else 0.0,
                        "Cantidad": allocation["Cantidad"],
                        "ID máquina": compatible_machine_key,
                        "H-Km inicio": None,
                        "H-Km fin": None,
                        "_machine_key": member["machine_key"] or "",
                        "_front_id": member["_front_id"],
                    }
                if preserved:
                    row.update({
                        key: value for key, value in preserved.items()
                        if key not in {"Frente", "Legajo", "Empleado", "_front_id"}
                    })
                    row.update({
                        "Seleccionar": False,
                        "Frente": "Manual" if staff_mode == "Carga manual" else front_map[member["_front_id"]]["name"],
                        "Legajo": member["personnel_key"],
                        "Empleado": text(person, "EMPLEADO"),
                        "_front_id": member["_front_id"],
                    })
                    if cell_text(row.get("ID máquina")) not in allowed_machines:
                        row["ID máquina"] = ""
                draft_rows.append(row)
            if preserved_rows and cycle["allocation_mode"] == "Total a repartir":
                try:
                    draft_rows = redistribute_rows(
                        draft_rows, partial_quantity, integers=cycle["unit"].upper() == "SC",
                    )
                except ValueError as error:
                    # Keep the rows editable so an invalid fixed quantity can be corrected.
                    st.warning(f"No se pudo repartir el saldo: {error} Revisá las cantidades fijas.")
            st.session_state.allocation_draft = {
                "cycle_id": cycle_id,
                "context_key": context_key,
                "form_signature": form_signature,
                "input_signature": part_inputs,
                "input_version": 0,
                "new_cycle": new_cycle,
                "front_ids": selected_front_ids,
                "selection_signature": selection_signature,
                "date": partial_date.isoformat(),
                "declared": partial_quantity,
                "notes": notes,
                "input_key": selected_input_key,
                "input_dose": partial_dose if selected_input_key else 0,
                "input_quantity": partial_input_quantity,
                "input_unit": input_unit,
                "inputs": part_inputs,
                "rows": draft_rows,
            }
            st.session_state.allocation_version += 1

        if not members:
            st.info("Seleccioná el personal o un frente para completar el parte.")
        elif partial_quantity <= 0:
            st.info("Ingresá la cantidad para ver la distribución y guardar el parte.")
        draft = st.session_state.allocation_draft
        if (
            draft
            and draft.get("context_key") == context_key
            and draft.get("selection_signature") == selection_signature
        ):
            draft.update(date=partial_date.isoformat(), notes=notes, new_cycle=new_cycle)
            input_signature = part_inputs
            if draft.get("input_signature") != input_signature:
                draft.update(input_key=selected_input_key, input_dose=partial_dose,
                             input_quantity=partial_input_quantity, input_unit=input_unit,
                             inputs=part_inputs,
                             input_signature=input_signature,
                             input_version=draft.get("input_version", 0) + 1)
            if not draft.get("input_key"):
                draft["input_quantity"] = 0.0
                draft["input_dose"] = 0.0
            editor_frame = pd.DataFrame(allocation_editor_base_rows(draft))
            editor_frame["ID máquina"] = editor_frame["ID máquina"].fillna("").astype(str)
            editor_columns_to_drop = ["Frente", "_machine_key", "_front_id"]
            if not person_hours_enabled:
                editor_columns_to_drop.append("Horas persona")
            edited = st.data_editor(
                editor_frame.drop(columns=editor_columns_to_drop, errors="ignore"),
                key=f"allocation_editor_v3_{st.session_state.allocation_version}",
                on_change=commit_allocation_editor,
                hide_index=True,
                width="stretch",
                disabled=["Legajo", "Empleado"] + (["ID máquina", "H-Km inicio", "H-Km fin"] if not allowed_machines else []),
                alt="Distribución de la cantidad entre integrantes del frente",
                column_config={
                    "Seleccionar": st.column_config.CheckboxColumn(
                        "✓", width=45, help="Marcá la fila para quitarla o reemplazarla."
                    ),
                    "Estado": st.column_config.SelectboxColumn(options=["Presente", "Ausente", "Cantidad fija"], required=True),
                    "Horas persona": st.column_config.NumberColumn(
                        "Horas persona", min_value=0.0, max_value=48.0, step=0.5, format="%.1f",
                        help="Total de horas trabajadas por esta persona.",
                    ),
                    "Cantidad": st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
                    "ID máquina": st.column_config.SelectboxColumn(
                        "Vehículo / máquina", options=["", *sorted(allowed_machines)], disabled=not allowed_machines,
                        format_func=lambda key: machine_label(key, allowed_machines),
                        help="Sólo se muestran máquinas compatibles con la tarea. Conserva la habitual si pertenece al grupo permitido.",
                    ),
                    "H-Km inicio": st.column_config.NumberColumn(
                        "H-Km inicio", min_value=0, step=1, format="%d",
                        help="Lectura entera inicial del horómetro o cuentakilómetros.",
                    ),
                    "H-Km fin": st.column_config.NumberColumn(
                        "H-Km fin", min_value=0, step=1, format="%d",
                        help="Lectura entera final del horómetro o cuentakilómetros.",
                    ),
                },
            )
            total_allocated = float(edited["Cantidad"].sum())
            with st.container(horizontal=True):
                st.metric("Total distribuido", f"{total_allocated:,.1f} {cycle['unit']}")
                st.metric(
                    "Insumos del parte",
                    f"{len(draft.get('inputs', []))} producto(s)" if draft.get("inputs") else "Sin insumo",
                )
            if cycle["allocation_mode"] == "Total a repartir":
                st.caption("Editá la cantidad de quien hizo menos y usá “Redistribuir saldo”; esa cantidad quedará fija.")
            selected_positions = [
                position for position, row in enumerate(edited.to_dict(orient="records"))
                if bool(row.get("Seleccionar"))
            ]

            def render_staff_dialog(action, selected_row_positions):
                replacing = action == "replace"
                action_rows = edited.to_dict(orient="records")
                current_position = selected_row_positions[0] if replacing else None
                existing_personnel = {
                    str(row["Legajo"]) for position, row in enumerate(action_rows)
                    if position != current_position
                }
                personnel_options = [key for key in people_by_key if key not in existing_personnel]
                st.caption(
                    "Elegí la persona que reemplazará a la seleccionada y su vehículo."
                    if replacing else
                    "Elegí la persona y, si corresponde, el vehículo que utilizará en este parte."
                )
                new_person_key = st.selectbox(
                    "Personal", personnel_options,
                    format_func=lambda key: f"{text(people_by_key.get(key), 'EMPLEADO')} — {key}",
                    key=f"staff_dialog_person_{st.session_state.allocation_version}_{action}",
                )
                new_machine_key = st.selectbox(
                    "Vehículo / máquina", [None, *sorted(allowed_machines)],
                    format_func=lambda key: "Sin vehículo" if key is None else machine_label(key, allowed_machines),
                    key=f"staff_dialog_machine_{st.session_state.allocation_version}_{action}",
                    disabled=not allowed_machines,
                )
                st.caption("Las lecturas H-Km se completan después en la tabla.")
                confirm_staff_action = st.button(
                    "Confirmar reemplazo" if replacing else "Agregar al parte",
                    icon=":material/check:", type="primary", width="stretch",
                    key=f"confirm_staff_dialog_{st.session_state.allocation_version}_{action}",
                    disabled=not personnel_options,
                )
                if confirm_staff_action:
                    updated_rows = []
                    for position, row in enumerate(action_rows):
                        row["Seleccionar"] = False
                        row["Frente"] = draft["rows"][position].get("Frente", "Manual")
                        row["_machine_key"] = draft["rows"][position].get("_machine_key", "")
                        row["_front_id"] = draft["rows"][position]["_front_id"]
                        updated_rows.append(row)
                    if replacing:
                        replacement_row = updated_rows[current_position]
                        replacement_row.update({
                            "Legajo": new_person_key,
                            "Empleado": text(people_by_key.get(new_person_key), "EMPLEADO"),
                            "ID máquina": new_machine_key or "",
                            "H-Km inicio": None,
                            "H-Km fin": None,
                            "Horas persona": float(default_person_hours) if person_hours_enabled else 0.0,
                            "_machine_key": new_machine_key or "",
                        })
                    else:
                        front_id_for_new_person = draft["front_ids"][0]
                        updated_rows.append({
                            "Seleccionar": False,
                            "Frente": "Manual" if staff_mode == "Carga manual" else front_map[front_id_for_new_person]["name"],
                            "Legajo": new_person_key,
                            "Empleado": text(people_by_key.get(new_person_key), "EMPLEADO"),
                            "Estado": "Presente",
                            "Horas persona": float(default_person_hours) if person_hours_enabled else 0.0,
                            "Cantidad": 0.0 if cycle["allocation_mode"] == "Total a repartir" else partial_quantity,
                            "ID máquina": new_machine_key or "",
                            "H-Km inicio": None,
                            "H-Km fin": None,
                            "_machine_key": new_machine_key or "",
                            "_front_id": front_id_for_new_person,
                        })
                        if cycle["allocation_mode"] == "Total a repartir":
                            try:
                                updated_rows = redistribute_rows(
                                    updated_rows, draft["declared"],
                                    integers=cycle["unit"].upper() == "SC",
                                )
                            except ValueError as error:
                                st.error(str(error))
                                return
                    draft["rows"] = updated_rows
                    st.session_state.allocation_version += 1
                    st.rerun()

            @st.dialog(
                "Reemplazar personal", width="medium", position="center",
                icon=":material/swap_horiz:", on_dismiss="rerun",
            )
            def replace_staff_dialog(selected_row_positions):
                render_staff_dialog("replace", selected_row_positions)

            @st.dialog(
                "Agregar personal", width="medium", position="center",
                icon=":material/person_add:", on_dismiss="rerun",
            )
            def add_staff_dialog():
                render_staff_dialog("add", [])

            with st.container(horizontal=True):
                redistribute_clicked = cycle["allocation_mode"] == "Total a repartir" and st.button(
                    "Redistribuir saldo", icon=":material/balance:"
                )
                remove_clicked = st.button(
                    "Quitar seleccionados",
                    icon=":material/person_remove:",
                    disabled=not selected_positions,
                )
                replace_clicked = st.button(
                    "Reemplazar seleccionado", icon=":material/swap_horiz:",
                    disabled=len(selected_positions) != 1,
                )
                add_person_clicked = st.button(
                    "Agregar persona y vehículo", icon=":material/person_add:",
                )
                apply_default_hours = person_hours_enabled and st.button(
                    f"Aplicar {default_person_hours:g} h a todos", icon=":material/schedule:",
                    help="Reemplaza las horas de todas las personas presentes por el valor configurado.",
                )
                save_clicked = st.button("Agregar tarea al parte", icon=":material/playlist_add:", type="primary")
            if replace_clicked:
                replace_staff_dialog(selected_positions)
            elif add_person_clicked:
                add_staff_dialog()
            if apply_default_hours:
                refreshed_rows = edited.to_dict(orient="records")
                for position, row in enumerate(refreshed_rows):
                    row["Seleccionar"] = False
                    if row.get("Estado") != "Ausente":
                        row["Horas persona"] = float(default_person_hours)
                    row["Frente"] = draft["rows"][position].get("Frente", "Manual")
                    row["_machine_key"] = draft["rows"][position].get("_machine_key", "")
                    row["_front_id"] = draft["rows"][position]["_front_id"]
                draft["rows"] = refreshed_rows
                st.session_state.allocation_version += 1
                st.rerun()
            if remove_clicked:
                retained_rows = []
                for position, row in enumerate(edited.to_dict(orient="records")):
                    if bool(row.get("Seleccionar")):
                        continue
                    row["Seleccionar"] = False
                    row["Frente"] = draft["rows"][position].get("Frente", "Manual")
                    row["_machine_key"] = draft["rows"][position]["_machine_key"]
                    row["_front_id"] = draft["rows"][position]["_front_id"]
                    retained_rows.append(row)
                if not retained_rows:
                    st.error("El parte debe conservar al menos una persona.")
                else:
                    try:
                        if cycle["allocation_mode"] == "Total a repartir":
                            visible_rows = [
                                {key: value for key, value in row.items() if not key.startswith("_")}
                                for row in retained_rows
                            ]
                            redistributed = redistribute_rows(
                                visible_rows,
                                draft["declared"],
                                integers=cycle["unit"].upper() == "SC",
                            )
                            for row, original in zip(redistributed, retained_rows):
                                row["Frente"] = original.get("Frente", "Manual")
                                row["_machine_key"] = original["_machine_key"]
                                row["_front_id"] = original["_front_id"]
                            retained_rows = redistributed
                        draft["rows"] = retained_rows
                        st.session_state.allocation_version += 1
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
            if redistribute_clicked:
                try:
                    rows_to_redistribute = edited.to_dict(orient="records")
                    for position, row in enumerate(rows_to_redistribute):
                        original_quantity = float(allocation_editor_base_rows(draft)[position].get("Cantidad", 0) or 0)
                        edited_quantity = float(row.get("Cantidad", 0) or 0)
                        if row.get("Estado") == "Presente" and abs(edited_quantity - original_quantity) > 0.001:
                            row["Estado"] = "Cantidad fija"
                    redistributed = redistribute_rows(
                        rows_to_redistribute, draft["declared"], integers=cycle["unit"].upper() == "SC"
                    )
                    for row, original in zip(redistributed, draft["rows"]):
                        row["Seleccionar"] = False
                        row["Frente"] = original.get("Frente", "Manual")
                        row["_machine_key"] = original["_machine_key"]
                        row["_front_id"] = original["_front_id"]
                    draft["rows"] = redistributed
                    st.session_state.allocation_version += 1
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
            if save_clicked:
                declared_total = draft["declared"] if cycle["allocation_mode"] == "Total a repartir" else total_allocated
                machine_keys = [cell_text(value) for value in edited["ID máquina"]]
                invalid_machines = [key for key in machine_keys if key and key not in allowed_machines]
                present_rows = [
                    row for _, row in edited.iterrows()
                    if str(row["Estado"]) != "Ausente"
                ]
                required_machine_missing = bool(
                    required_machine_groups
                    and present_rows
                    and not any(cell_text(row["ID máquina"]) for row in present_rows)
                )
                meter_error = ""
                for _, row in edited.iterrows():
                    machine_key = cell_text(row["ID máquina"])
                    start_value = row.get("H-Km inicio")
                    end_value = row.get("H-Km fin")
                    start_number = None if pd.isna(start_value) else float(start_value)
                    end_number = None if pd.isna(end_value) else float(end_value)
                    if not machine_key and (start_number is not None or end_number is not None):
                        meter_error = "Asigná una máquina antes de cargar sus lecturas H-Km."
                        break
                    if (start_number is None) != (end_number is None):
                        meter_error = "Completá tanto H-Km inicio como H-Km fin, o dejá ambos vacíos."
                        break
                    if start_number is not None and (
                        not start_number.is_integer() or not end_number.is_integer()
                    ):
                        meter_error = "Las lecturas H-Km deben ser números enteros."
                        break
                    if start_number is not None and end_number < start_number:
                        meter_error = "La lectura H-Km final no puede ser menor que la inicial."
                        break
                input_keys = [item["input_key"] for item in draft.get("inputs", [])]
                if invalid_machines:
                    st.error("Hay máquinas que no corresponden al grupo permitido para esta tarea.")
                elif required_machine_missing:
                    st.error("Esta tarea requiere al menos una máquina compatible en el parte.")
                elif meter_error:
                    st.error(meter_error)
                elif len(input_keys) != len(set(input_keys)):
                    st.error("El mismo insumo está repetido. Usá una sola fila por producto.")
                elif cycle["allocation_mode"] == "Total a repartir" and abs(total_allocated - draft["declared"]) > 0.01:
                    st.error("La distribución no coincide con la cantidad parcial. Usá “Redistribuir saldo”.")
                else:
                    allocations = []
                    for position, (_, row) in enumerate(edited.iterrows()):
                        machine_key = cell_text(row["ID máquina"])
                        machine_start = row.get("H-Km inicio")
                        machine_end = row.get("H-Km fin")
                        machine_start_value = None if pd.isna(machine_start) else int(machine_start)
                        machine_end_value = None if pd.isna(machine_end) else int(machine_end)
                        allocations.append(
                            {
                                "personnel_key": str(row["Legajo"]),
                                "machine_key": machine_key or None,
                                "attendance": str(row["Estado"]),
                                "quantity": float(row["Cantidad"]),
                                "replacement_key": None,
                                "front_id": draft["rows"][position]["_front_id"],
                                "machine_start_time": machine_start_value if machine_key else None,
                                "machine_end_time": machine_end_value if machine_key else None,
                                "person_hours": (
                                    float(row.get("Horas persona") or 0)
                                    if person_hours_enabled else 0.0
                                ),
                            }
                        )
                    front_id = draft["front_ids"][0]
                    front_name = (
                        "Manual" if staff_mode == "Carga manual"
                        else front_map[front_id]["name"]
                    )
                    line = {
                        "date": draft["date"],
                        "crop": crop,
                        "lot_key": selected_lot_key,
                        "operation_key": selected_operation_key,
                        "front_id": front_id,
                        "front_name": front_name,
                        "quantity": declared_total,
                        "target_quantity": target,
                        "unit": cycle["unit"],
                        "allocation_mode": cycle["allocation_mode"],
                        "notes": draft["notes"],
                        "input_key": draft["input_key"],
                        "input_dose": draft["input_dose"],
                        "input_quantity": draft["input_quantity"],
                        "input_unit": draft["input_unit"],
                        "inputs": draft.get("inputs", []),
                        "allocations": allocations,
                    }
                    existing_lines = st.session_state.multi_part_lines
                    if existing_lines and any(
                        existing["date"] != line["date"]
                        for existing in existing_lines
                    ):
                        st.error("Todas las tareas del mismo parte deben tener la misma fecha.")
                    elif any(
                        existing["operation_key"] == line["operation_key"]
                        and existing["lot_key"] == line["lot_key"]
                        for existing in existing_lines
                    ):
                        st.error("Esta tarea ya fue agregada para el mismo lote.")
                    else:
                        st.session_state.multi_part_lines = [*existing_lines, line]
                        st.session_state.allocation_draft = None
                        st.session_state.allocation_version += 1
                        st.session_state.multi_part_flash = (
                            f"Tarea {selected_operation_key} agregada. "
                            + (
                                "El sistema continuará con la siguiente tarea del frente."
                                if staff_mode == "Frentes"
                                else "Podés seleccionar otra tarea o guardar el parte completo."
                            )
                        )
                        st.rerun()

        partials = list_partials(DATABASE, cycle_id) if cycle_id else []
        if partials:
            history_rows = []
            for part in partials:
                history_rows.append(
                    {
                        "ID parte": part.get("report_code") or part.get("part_code") or f"legacy{int(part['id']):04d}",
                        "Fecha": part["part_date"],
                        "Frente": "Manual" if part["front_name"] == "__MANUAL__" else part["front_name"],
                        "Cantidad": part["quantity"],
                        "Insumo": part.get("inputs_summary") or input_label(part.get("input_key")),
                        "Dosis": part.get("input_dose", 0),
                        "Cantidad insumo": part.get("input_quantity", 0),
                        "Unidad insumo": part.get("input_unit", ""),
                        "Observaciones": part["notes"],
                    }
                )
            with st.expander("Partes anteriores de este lote y tarea"):
                st.dataframe(pd.DataFrame(history_rows), hide_index=True, width="stretch", alt="Historial de partes e insumos del trabajo")
        if cycle_id and st.button("Finalizar tarea en este lote", icon=":material/task_alt:"):
            if cycle["allocation_mode"] == "Total a repartir" and remaining > 0.01:
                st.warning("Todavía queda cantidad pendiente; completala antes de cerrar.")
            else:
                close_cycle(DATABASE, cycle_id)
                st.session_state.allocation_draft = None
                st.rerun()
        st.stop()

