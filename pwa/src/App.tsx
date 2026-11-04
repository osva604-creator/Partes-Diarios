import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { Cloud, Leaf, LogOut, Plus, RefreshCw, Save, Sprout, Users } from 'lucide-react'
import { hasSupabaseConfig, supabase } from './lib/supabase'

type Farm = { id: string; name: string }
type Lot = { id: string; farm_id: string; lot_code: string; lot_name: string; crop: string; net_area: number | null; gross_area: number | null; furrows: number | null }
type Operation = { operation_code: string; name: string; unit: string; task_type: string; machine_groups: string[]; default_target: number | null; allows_inputs: boolean }
type Person = { employee_code: string; full_name: string }
type Machine = { machine_code: string; operational_group: string; brand: string; model: string }
type Front = { id: string; name: string; created_by: string; active: boolean }
type FrontTaskMember = { operation_code: string; personnel_code: string; machine_code: string | null }
type Catalogs = { farms: Farm[]; lots: Lot[]; operations: Operation[]; personnel: Person[]; machines: Machine[]; fronts: Front[] }
type Notice = { kind: 'error' | 'success'; text: string }

const emptyCatalogs: Catalogs = { farms: [], lots: [], operations: [], personnel: [], machines: [], fronts: [] }
const today = () => {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Ocurrió un error inesperado.'
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [sessionReady, setSessionReady] = useState(false)
  const [catalogs, setCatalogs] = useState<Catalogs>(emptyCatalogs)
  const [members, setMembers] = useState<FrontTaskMember[]>([])
  const [memberMachines, setMemberMachines] = useState<Record<string, string>>({})
  const [frontTaskMembers, setFrontTaskMembers] = useState<FrontTaskMember[]>([])
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [reportDate, setReportDate] = useState(today)
  const [serviceOrder, setServiceOrder] = useState('')
  const [farmId, setFarmId] = useState('')
  const [lotId, setLotId] = useState('')
  const [operationCode, setOperationCode] = useState('')
  const [frontId, setFrontId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [targetQuantity, setTargetQuantity] = useState('')
  const [allocationMode, setAllocationMode] = useState('Total a repartir')
  const [selectedPeople, setSelectedPeople] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [savedReport, setSavedReport] = useState<{ report_code: string } | null>(null)
  const [appRole, setAppRole] = useState('')
  const [section, setSection] = useState<'report' | 'fronts'>('report')
  const [manageFrontId, setManageFrontId] = useState('')
  const [manageFrontName, setManageFrontName] = useState('')
  const [newFrontName, setNewFrontName] = useState('')
  const [manageOperationCode, setManageOperationCode] = useState('')
  const [frontPeopleSearch, setFrontPeopleSearch] = useState('')
  const [openCycle, setOpenCycle] = useState<{ allocation_mode: string; target_quantity: number; unit: string } | null>(null)

  useEffect(() => {
    if (!supabase) { setSessionReady(true); return }
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setSessionReady(true) })
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession))
    return () => listener.subscription.unsubscribe()
  }, [])

  const loadCatalogs = useCallback(async () => {
    if (!supabase || !session) return
    setLoading(true)
    setNotice(null)
    try {
      const [farms, lots, operations, personnel, machines, fronts] = await Promise.all([
        supabase.from('farms').select('id,name').eq('active', true).order('name'),
        supabase.from('lots').select('id,farm_id,lot_code,lot_name,crop,net_area,gross_area,furrows').eq('active', true).order('lot_code'),
        supabase.from('operations').select('operation_code,name,unit,task_type,machine_groups,default_target,allows_inputs').eq('active', true).order('operation_code'),
        supabase.from('personnel').select('employee_code,full_name').eq('active', true).order('full_name'),
        supabase.from('machines').select('machine_code,operational_group,brand,model').eq('active', true).order('machine_code'),
        supabase.from('fronts').select('id,name,created_by,active').eq('active', true).order('name'),
      ])
      const result = [farms, lots, operations, personnel, machines, fronts]
      const failed = result.find((item) => item.error)
      if (failed?.error) throw failed.error
      setCatalogs({ farms: farms.data ?? [], lots: lots.data ?? [], operations: operations.data ?? [], personnel: personnel.data ?? [], machines: machines.data ?? [], fronts: fronts.data ?? [] })
    } catch (error) {
      setNotice({ kind: 'error', text: `No se pudieron cargar los datos: ${errorText(error)}` })
    } finally { setLoading(false) }
  }, [session])

  useEffect(() => { void loadCatalogs() }, [loadCatalogs])

  useEffect(() => {
    if (!supabase || !session) { setAppRole(''); return }
    supabase.from('profiles').select('role').eq('user_id', session.user.id).maybeSingle()
      .then(({ data }) => setAppRole(data?.role ?? ''))
  }, [session])

  const visibleLots = useMemo(() => catalogs.lots.filter((lot) => !farmId || lot.farm_id === farmId), [catalogs.lots, farmId])
  const selectedOperation = catalogs.operations.find((operation) => operation.operation_code === operationCode)
  const selectedFront = catalogs.fronts.find((front) => front.id === frontId)
  const selectedLot = catalogs.lots.find((lot) => lot.id === lotId)
  const currentUnit = openCycle?.unit ?? selectedOperation?.unit ?? ''
  const eligiblePeople = catalogs.personnel.filter((person) => members.some((member) => member.personnel_code === person.employee_code))
  const selectedManageMembers = frontTaskMembers.filter((member) => member.operation_code === manageOperationCode)
  const manageOperation = catalogs.operations.find((operation) => operation.operation_code === manageOperationCode)
  const manageMachines = manageOperation?.machine_groups.length
    ? catalogs.machines.filter((machine) => manageOperation.machine_groups.some((group) => group.trim().toLocaleUpperCase() === machine.operational_group.trim().toLocaleUpperCase()))
    : catalogs.machines
  const matchingManagePeople = catalogs.personnel.filter((person) => `${person.full_name} ${person.employee_code}`.toLocaleLowerCase().includes(frontPeopleSearch.trim().toLocaleLowerCase()))
  const manageableFronts = catalogs.fronts.filter((front) => appRole === 'administrador' || front.created_by === session?.user.id)
  const manageFront = manageableFronts.find((front) => front.id === manageFrontId)
  const eligibleMachines = selectedOperation?.machine_groups.length
    ? catalogs.machines.filter((machine) => selectedOperation.machine_groups.some((group) => group.trim().toLocaleUpperCase() === machine.operational_group.trim().toLocaleUpperCase()))
    : catalogs.machines

  useEffect(() => {
    if (!supabase || !frontId || !operationCode) { setMembers([]); setSelectedPeople([]); setMemberMachines({}); return }
    let cancelled = false
    supabase.from('front_task_members').select('operation_code,personnel_code,machine_code').eq('front_id', frontId).eq('operation_code', operationCode).then(({ data, error }) => {
      if (cancelled) return
      if (error) { setNotice({ kind: 'error', text: `No se pudieron cargar los integrantes: ${error.message}` }); return }
      const rows = data ?? []
      setMembers(rows)
      setSelectedPeople(rows.map((member) => member.personnel_code))
      setMemberMachines(Object.fromEntries(rows.map((member) => [member.personnel_code, member.machine_code ?? ''])))
    })
    return () => { cancelled = true }
  }, [frontId, operationCode])

  useEffect(() => {
    if (!supabase || !lotId || !operationCode) { setOpenCycle(null); setTargetQuantity(''); return }
    let cancelled = false
    const lot = catalogs.lots.find((item) => item.id === lotId)
    const operation = catalogs.operations.find((item) => item.operation_code === operationCode)
    supabase.from('work_cycles').select('allocation_mode,target_quantity,unit,cycle_no').eq('lot_id', lotId).eq('operation_code', operationCode).eq('status', 'Abierto').order('cycle_no', { ascending: false }).limit(1).maybeSingle()
      .then(({ data, error }) => {
        if (cancelled) return
        if (error) { setNotice({ kind: 'error', text: `No se pudo consultar el avance existente: ${error.message}` }); return }
        if (data) {
          setOpenCycle(data)
          setAllocationMode(data.allocation_mode)
          setTargetQuantity(String(data.target_quantity || ''))
        } else {
          setOpenCycle(null)
          const unit = operation?.unit.trim().toLocaleUpperCase() ?? ''
          const mode = ['SC', 'HA', 'TN'].includes(unit) ? 'Total a repartir' : 'Cantidad individual'
          setAllocationMode(mode)
          const inventoryTarget = unit === 'SC' ? lot?.furrows : unit === 'HA' ? (lot?.net_area || lot?.gross_area) : operation?.default_target
          setTargetQuantity(mode === 'Total a repartir' && inventoryTarget ? String(inventoryTarget) : '')
        }
      })
    return () => { cancelled = true }
  }, [lotId, operationCode, catalogs.lots, catalogs.operations])

  useEffect(() => {
    if (!supabase || !manageFront) { setManageFrontName(''); setFrontTaskMembers([]); return }
    let cancelled = false
    Promise.all([
      supabase.from('front_task_members').select('operation_code,personnel_code,machine_code').eq('front_id', manageFront.id),
    ]).then(([result]) => {
      if (cancelled) return
      if (result.error) { setNotice({ kind: 'error', text: `No se pudieron cargar los integrantes: ${result.error.message}` }); return }
      setManageFrontName(manageFront.name)
      setFrontTaskMembers(result.data ?? [])
      setManageOperationCode((current) => current || catalogs.operations[0]?.operation_code || '')
    })
    return () => { cancelled = true }
  }, [manageFrontId, manageFront?.name, catalogs.operations])

  useEffect(() => {
    setFarmId(''); setLotId(''); setOperationCode(''); setFrontId(''); setQuantity(''); setTargetQuantity(''); setSelectedPeople([]); setMemberMachines({}); setSavedReport(null)
  }, [session?.user.id])

  async function signIn(event: FormEvent) {
    event.preventDefault()
    if (!supabase) return
    setLoading(true); setNotice(null)
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password })
    if (error) setNotice({ kind: 'error', text: error.message })
    setLoading(false)
  }

  async function signOut() {
    if (!supabase) return
    await supabase.auth.signOut()
    setCatalogs(emptyCatalogs); setNotice(null)
  }

  async function createFront(event: FormEvent) {
    event.preventDefault()
    if (!supabase || !session || !newFrontName.trim()) return
    setLoading(true); setNotice(null)
    const { data, error } = await supabase.from('fronts').insert({ name: newFrontName.trim(), created_by: session.user.id }).select('id').single()
    if (error) setNotice({ kind: 'error', text: `No se pudo crear el frente: ${error.message}` })
    else {
      setNewFrontName(''); setManageFrontId(data.id); setSection('fronts')
      await loadCatalogs()
      setNotice({ kind: 'success', text: 'Frente creado. Ahora podés asignarle personal y maquinaria.' })
    }
    setLoading(false)
  }

  async function saveFront(event: FormEvent) {
    event.preventDefault()
    if (!supabase || !manageFront) return
    setLoading(true); setNotice(null)
    const { error } = await supabase.rpc('replace_front_task_members', {
      p_front_id: manageFront.id,
      p_front_name: manageFrontName.trim(),
      p_members: frontTaskMembers,
    })
    if (error) setNotice({ kind: 'error', text: `No se pudo guardar el frente y sus equipos: ${error.message}` })
    await loadCatalogs()
    if (!error) setNotice({ kind: 'success', text: 'Frente y equipos por tarea guardados.' })
    setLoading(false)
  }

  async function deactivateFront() {
    if (!supabase || !manageFront || !window.confirm(`¿Desactivar el frente “${manageFront.name}”?`)) return
    setLoading(true); setNotice(null)
    const { error } = await supabase.from('fronts').update({ active: false }).eq('id', manageFront.id)
    if (error) setNotice({ kind: 'error', text: `No se pudo desactivar el frente: ${error.message}` })
    else setManageFrontId('')
    await loadCatalogs()
    if (!error) setNotice({ kind: 'success', text: 'Frente desactivado.' })
    setLoading(false)
  }

  async function saveReport(event: FormEvent) {
    event.preventDefault()
    if (!supabase || !selectedOperation || !selectedLot || !selectedFront) return
    const amount = Number(quantity)
    const people = selectedPeople
    if (!Number.isFinite(amount) || amount <= 0 || people.length === 0) {
      setNotice({ kind: 'error', text: 'Ingresá una cantidad mayor a cero y seleccioná al menos una persona.' }); return
    }
    const unit = (openCycle?.unit ?? selectedOperation.unit).trim().toLocaleUpperCase()
    const integerAllocation = unit === 'SC'
    if (integerAllocation && !Number.isInteger(amount)) {
      setNotice({ kind: 'error', text: 'La cantidad en surcos debe ser un número entero.' }); return
    }
    if (selectedOperation.task_type === 'Manual' && people.some((personCode) => memberMachines[personCode])) {
      setNotice({ kind: 'error', text: 'La tarea seleccionada es manual y no admite maquinaria.' }); return
    }
    if (people.some((personCode) => memberMachines[personCode] && !eligibleMachines.some((machine) => machine.machine_code === memberMachines[personCode]))) {
      setNotice({ kind: 'error', text: 'Hay una máquina que no corresponde al grupo permitido para esta tarea.' }); return
    }
    const perPerson = integerAllocation ? Math.floor(amount / people.length) : Math.round((amount / people.length) * 10000) / 10000
    const integerRemainder = integerAllocation ? Math.round(amount) - perPerson * people.length : 0
    const remaining = Math.round((amount - perPerson * (people.length - 1)) * 10000) / 10000
    const taskQuantity = allocationMode === 'Total a repartir' ? amount : amount * people.length
    const allocations = people.map((personCode, index) => {
      const assignedMachine = memberMachines[personCode] ?? ''
      return {
      personnel_code: personCode,
      machine_code: selectedOperation.task_type === 'Manual' ? '' : assignedMachine,
      attendance: 'Presente',
      quantity: allocationMode === 'Cantidad individual' ? amount : integerAllocation ? perPerson + (index < integerRemainder ? 1 : 0) : index === people.length - 1 ? remaining : perPerson,
      front_id: frontId,
      person_hours: 12,
    }})
    if (selectedOperation.machine_groups.length && !people.some((personCode) => memberMachines[personCode])) {
      setNotice({ kind: 'error', text: 'Asigná al menos una máquina compatible a las personas que la necesitan.' }); return
    }
    const payload = {
      lot_id: lotId,
      operation_code: operationCode,
      front_id: frontId,
      quantity: taskQuantity,
      target_quantity: allocationMode === 'Total a repartir' ? Number(targetQuantity) || taskQuantity : 0,
      unit: openCycle?.unit ?? selectedOperation.unit,
      allocation_mode: allocationMode,
      crop: selectedLot.crop,
      notes: notes.trim(),
      allocations,
      inputs: [],
    }
    setLoading(true); setNotice(null); setSavedReport(null)
    const { data, error } = await supabase.rpc('create_daily_report', {
      p_idempotency_key: crypto.randomUUID(),
      p_report_date: reportDate,
      p_service_order: serviceOrder.trim(),
      p_tasks: [payload],
    })
    if (error) setNotice({ kind: 'error', text: `No se pudo guardar el parte: ${error.message}` })
    else {
      const report = Array.isArray(data) ? data[0] : data
      setSavedReport(report)
      setNotice({ kind: 'success', text: `Parte ${report?.report_code ?? ''} guardado correctamente.` })
      setQuantity(''); setNotes('')
    }
    setLoading(false)
  }

  if (!hasSupabaseConfig) return <main className="setup-screen"><section className="setup-card"><div className="brand-mark"><Leaf size={22} /></div><span className="eyebrow">ASISTENTE DE CAMPO</span><h1>Configurá la conexión</h1><p>Copiá <code>.env.example</code> como <code>.env.local</code> y agregá la URL del proyecto Supabase y la clave publicable.</p><p className="muted">La clave secreta del proyecto nunca debe configurarse en esta aplicación.</p></section></main>

  if (!sessionReady) return <main className="setup-screen"><div className="loading-label"><RefreshCw className="spin" size={18} /> Verificando sesión…</div></main>

  if (!session) return <main className="setup-screen"><section className="setup-card login-card"><div className="brand-mark"><Leaf size={22} /></div><span className="eyebrow">ASISTENTE DE CAMPO</span><h1>Partes Diarios</h1><p>Iniciá sesión para consultar los catálogos y cargar un parte.</p>
    <form onSubmit={signIn} className="stack-form"><label>Correo electrónico<input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Contraseña<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label><button className="primary-button" disabled={loading}>{loading ? 'Ingresando…' : 'Iniciar sesión'}</button></form>
    {notice && <p className={`notice ${notice.kind}`} role="status">{notice.text}</p>}<p className="muted">Las cuentas se habilitan desde el proyecto Supabase.</p></section></main>

  const hasMasterCatalogs = catalogs.farms.length > 0 && catalogs.lots.length > 0 && catalogs.operations.length > 0 && catalogs.personnel.length > 0
  const hasFronts = catalogs.fronts.length > 0
  return <main className="app-shell">
    <aside className="sidebar"><a className="brand" href="#inicio"><span className="brand-mark"><Leaf size={21} /></span><span><strong>Parte diario</strong><small>Gestión de tareas agrícolas</small></span></a><nav aria-label="Secciones"><button className={`nav-link ${section === 'report' ? 'active' : ''}`} onClick={() => setSection('report')}>Cargar parte</button><button className={`nav-link ${section === 'fronts' ? 'active' : ''}`} onClick={() => setSection('fronts')}>Frentes</button></nav><div className="sidebar-note"><Cloud size={17} /><span>Conectado a Supabase<br /><b>Sincronización en línea</b></span></div></aside>
    <section className="workspace" id="inicio"><header className="topbar"><div><span className="eyebrow">{selectedFront ? `FRENTE · ${selectedFront.name}` : 'ASISTENTE DE CAMPO'}</span><h1>{section === 'report' ? 'Cargar parte' : 'Frentes'}</h1></div><div className="account-actions"><span className="user-email">{session.user.email}</span><button className="icon-button" onClick={loadCatalogs} title="Actualizar catálogos" disabled={loading}><RefreshCw size={17} /></button><button className="icon-button" onClick={signOut} title="Cerrar sesión"><LogOut size={17} /></button></div></header>
      {section === 'report' && <section className="intro-card"><div><span className="eyebrow">REGISTRO DE TRABAJO</span><h2>Una carga simple para empezar.</h2><p>Seleccioná el lote, la tarea, el frente y la cantidad. El detalle se distribuye entre las personas elegidas.</p></div><div className="intro-icon"><Sprout size={34} /></div></section>}
      {notice && <div className={`notice ${notice.kind}`} role="status">{notice.text}{savedReport && <span className="saved-code">{savedReport.report_code}</span>}</div>}
      {section === 'report' && !hasMasterCatalogs && !loading && <section className="empty-state"><h2>Faltan datos maestros</h2><p>La conexión funciona, pero aún faltan fincas, lotes, tareas o personal activos. Revisá los catálogos en Supabase y actualizá esta pantalla.</p><button className="secondary-button" onClick={loadCatalogs}>Actualizar catálogos</button></section>}
      {section === 'fronts' && <section className="fronts-panel">
        <div className="section-heading"><span><Users size={16} /></span><div><h2>Administración de frentes</h2><p>Creá frentes y asigná personal con su maquinaria habitual.</p></div></div>
        <form className="new-front-form" onSubmit={createFront}><label>Nuevo frente<input required maxLength={120} value={newFrontName} onChange={(event) => setNewFrontName(event.target.value)} placeholder="Nombre del frente" /></label><button className="primary-button" disabled={loading}><Plus size={15} /> Crear frente</button></form>
        {manageableFronts.length > 0 ? <label className="front-picker">Frente a administrar<select value={manageFrontId} onChange={(event) => setManageFrontId(event.target.value)}><option value="">Seleccionar frente</option>{manageableFronts.map((front) => <option key={front.id} value={front.id}>{front.name}</option>)}</select></label> : <p className="helper-text">Todavía no tenés frentes propios. Los frentes compartidos aparecen en Cargar parte.</p>}
        {manageFront && <form className="front-editor" onSubmit={saveFront}><div className="front-editor-heading"><div><h3>{manageFront.name}</h3><p>Los cambios se aplican al guardar.</p></div><button className="secondary-button danger-button" type="button" disabled={loading} onClick={deactivateFront}>Desactivar</button></div><label>Nombre del frente<input required maxLength={120} value={manageFrontName} onChange={(event) => setManageFrontName(event.target.value)} /></label><label className="front-picker">Tarea del frente<select required value={manageOperationCode} onChange={(event) => { setManageOperationCode(event.target.value); setFrontPeopleSearch('') }}><option value="">Seleccionar tarea</option>{catalogs.operations.map((operation) => <option key={operation.operation_code} value={operation.operation_code}>{operation.operation_code} · {operation.name}</option>)}</select></label><h3>Equipo para esta tarea <small>{selectedManageMembers.length} integrantes</small></h3>
          <label className="front-search">Buscar personal<input type="search" value={frontPeopleSearch} onChange={(event) => setFrontPeopleSearch(event.target.value)} placeholder="Nombre o legajo" /></label>
          <div className="front-person-list">{matchingManagePeople.map((person) => { const assignedMember = selectedManageMembers.find((member) => member.personnel_code === person.employee_code); const assigned = Boolean(assignedMember); return <div className="front-person-row" key={person.employee_code}><label className="person-option"><input type="checkbox" checked={assigned} onChange={(event) => setFrontTaskMembers((current) => { const remaining = current.filter((member) => !(member.operation_code === manageOperationCode && member.personnel_code === person.employee_code)); return event.target.checked ? [...remaining, { operation_code: manageOperationCode, personnel_code: person.employee_code, machine_code: null }] : remaining })} /><span>{person.full_name}<small>Legajo {person.employee_code}</small></span></label>{assigned && <select aria-label={`Maquinaria habitual de ${person.full_name}`} disabled={manageOperation?.task_type === 'Manual'} value={assignedMember?.machine_code ?? ''} onChange={(event) => setFrontTaskMembers((current) => current.map((member) => member.operation_code === manageOperationCode && member.personnel_code === person.employee_code ? { ...member, machine_code: event.target.value || null } : member))}><option value="">Sin maquinaria</option>{manageMachines.map((machine) => <option key={machine.machine_code} value={machine.machine_code}>{machine.machine_code} · {[machine.brand, machine.model].filter(Boolean).join(' ')}</option>)}</select>}</div> })}</div>
          <div className="form-actions"><span>El equipo queda disponible al cargar un parte con este frente.</span><button className="primary-button" disabled={loading || !manageFrontName.trim()}><Save size={15} /> Guardar frente</button></div></form>}
      </section>}
      {section === 'report' && hasMasterCatalogs && !hasFronts && !loading && <section className="empty-state"><h2>Los maestros están listos; falta un frente</h2><p>No hay frentes activos disponibles. Creá uno y asignale personal para empezar a cargar partes.</p><button className="secondary-button" onClick={() => setSection('fronts')}>Administrar frentes</button></section>}
      {loading && !hasMasterCatalogs && <div className="loading-label"><RefreshCw className="spin" size={18} /> Cargando datos…</div>}
      {section === 'report' && hasMasterCatalogs && hasFronts && <form className="report-form" id="cargar" onSubmit={saveReport}>
        <section className="form-section"><div className="section-heading"><span>01</span><div><h2>Datos del parte</h2><p>Fecha y número de orden, si corresponde.</p></div></div><div className="field-grid two"><label>Fecha<input type="date" required value={reportDate} onChange={(e) => setReportDate(e.target.value)} /></label><label>Orden de servicio <small>Opcional</small><input value={serviceOrder} onChange={(e) => setServiceOrder(e.target.value)} placeholder="Número de orden" /></label></div></section>
        <section className="form-section"><div className="section-heading"><span>02</span><div><h2>Lote y tarea</h2><p>El avance se acumula en el ciclo abierto del lote y la operación.</p></div></div><div className="field-grid two"><label>Finca<select required value={farmId} onChange={(e) => { setFarmId(e.target.value); setLotId('') }}><option value="">Seleccionar finca</option>{catalogs.farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}</select></label><label>Lote<select required value={lotId} onChange={(e) => setLotId(e.target.value)} disabled={!farmId}><option value="">Seleccionar lote</option>{visibleLots.map((lot) => <option key={lot.id} value={lot.id}>{lot.lot_code} · {lot.lot_name || lot.crop}</option>)}</select></label><label>Tarea<select required value={operationCode} onChange={(e) => { setOperationCode(e.target.value); setQuantity(''); setSelectedPeople([]); setMemberMachines({}) }}><option value="">Seleccionar tarea</option>{catalogs.operations.map((operation) => <option key={operation.operation_code} value={operation.operation_code}>{operation.operation_code} · {operation.name}</option>)}</select></label><label>{allocationMode === 'Total a repartir' ? 'Cantidad total realizada' : 'Cantidad realizada por persona'} <small>{currentUnit || 'Unidad'}</small><input type="number" inputMode="decimal" min="0.001" step={currentUnit.toUpperCase() === 'SC' ? '1' : '0.001'} required value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="0" /></label>{allocationMode === 'Total a repartir' && <label>Objetivo del lote <small>{openCycle ? 'Del ciclo abierto' : 'Sugerido por el lote'}</small><input type="number" min="0" step="0.001" value={targetQuantity} onChange={(e) => setTargetQuantity(e.target.value)} readOnly={Boolean(openCycle)} placeholder="Se usa la cantidad del parte" /></label>}<div className="allocation-hint"><span>Distribución</span><strong>{allocationMode}</strong>{openCycle && <small>Parte del avance registrado de este lote y tarea.</small>}</div></div></section>
        <section className="form-section"><div className="section-heading"><span>03</span><div><h2>Frente y personal</h2><p>El personal y las máquinas se configuran por tarea dentro de cada frente.</p></div></div><div className="field-grid two"><label>Frente<select required value={frontId} onChange={(e) => setFrontId(e.target.value)}><option value="">Seleccionar frente</option>{catalogs.fronts.map((front) => <option key={front.id} value={front.id}>{front.name}</option>)}</select></label></div>
          {!operationCode && <p className="helper-text">Elegí la tarea para ver los frentes y su equipo configurado.</p>}{operationCode && !frontId && <p className="helper-text">Elegí un frente para ver el personal de esta tarea.</p>}{frontId && eligiblePeople.length === 0 && <p className="helper-text">Este frente no tiene personal configurado para la tarea elegida. Configuralo en Frentes.</p>}{eligiblePeople.length > 0 && <div className="report-member-list">{eligiblePeople.map((person) => { const assignedMachine = memberMachines[person.employee_code] ?? ''; const checked = selectedPeople.includes(person.employee_code); return <div className="report-member-row" key={person.employee_code}><label className="person-option"><input type="checkbox" checked={checked} onChange={(event) => { setSelectedPeople((current) => event.target.checked ? [...current, person.employee_code] : current.filter((code) => code !== person.employee_code)); if (event.target.checked && !Object.hasOwn(memberMachines, person.employee_code)) { const configured = members.find((member) => member.personnel_code === person.employee_code)?.machine_code ?? ''; setMemberMachines((current) => ({ ...current, [person.employee_code]: configured })) } }} /><span>{person.full_name}<small>Legajo {person.employee_code}</small></span></label>{selectedOperation?.task_type !== 'Manual' && <select aria-label={`Máquina de ${person.full_name}`} disabled={!checked} value={assignedMachine} onChange={(event) => setMemberMachines((current) => ({ ...current, [person.employee_code]: event.target.value }))}><option value="">Sin maquinaria</option>{eligibleMachines.map((machine) => <option key={machine.machine_code} value={machine.machine_code}>{machine.machine_code} · {[machine.brand, machine.model].filter(Boolean).join(' ')}</option>)}</select>}</div> })}</div>}</section>
        <section className="form-section"><div className="section-heading"><span>04</span><div><h2>Observaciones</h2><p>Agregá una nota si hace falta.</p></div></div><label className="full-field">Notas<textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Observaciones del trabajo" /></label></section>
        <div className="form-actions"><span>Se guardará un borrador en Supabase.</span><button className="primary-button" disabled={loading || !selectedFront || !selectedLot || !selectedOperation}>{loading ? 'Guardando…' : 'Guardar parte'}</button></div>
      </form>}
      <footer>Asistente de parte diario <span>·</span> Versión de trabajo</footer>
    </section>
  </main>
}
