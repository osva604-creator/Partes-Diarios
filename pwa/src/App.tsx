import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { Cloud, Leaf, LogOut, RefreshCw, Sprout } from 'lucide-react'
import { hasSupabaseConfig, supabase } from './lib/supabase'

type Farm = { id: string; name: string }
type Lot = { id: string; farm_id: string; lot_code: string; lot_name: string; crop: string }
type Operation = { operation_code: string; name: string; unit: string; task_type: string; machine_groups: string[]; default_target: number | null; allows_inputs: boolean }
type Person = { employee_code: string; full_name: string }
type Machine = { machine_code: string; operational_group: string; brand: string; model: string }
type Front = { id: string; name: string }
type FrontMember = { personnel_code: string; machine_code: string | null }
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
  const [members, setMembers] = useState<FrontMember[]>([])
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
  const [machineCode, setMachineCode] = useState('')
  const [notes, setNotes] = useState('')
  const [savedReport, setSavedReport] = useState<{ report_code: string } | null>(null)

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
        supabase.from('lots').select('id,farm_id,lot_code,lot_name,crop').eq('active', true).order('lot_code'),
        supabase.from('operations').select('operation_code,name,unit,task_type,machine_groups,default_target,allows_inputs').eq('active', true).order('operation_code'),
        supabase.from('personnel').select('employee_code,full_name').eq('active', true).order('full_name'),
        supabase.from('machines').select('machine_code,operational_group,brand,model').eq('active', true).order('machine_code'),
        supabase.from('fronts').select('id,name').eq('active', true).order('name'),
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

  const visibleLots = useMemo(() => catalogs.lots.filter((lot) => !farmId || lot.farm_id === farmId), [catalogs.lots, farmId])
  const selectedOperation = catalogs.operations.find((operation) => operation.operation_code === operationCode)
  const selectedFront = catalogs.fronts.find((front) => front.id === frontId)
  const selectedLot = catalogs.lots.find((lot) => lot.id === lotId)
  const eligiblePeople = catalogs.personnel.filter((person) => members.some((member) => member.personnel_code === person.employee_code))
  const eligibleMachines = selectedOperation?.machine_groups.length
    ? catalogs.machines.filter((machine) => selectedOperation.machine_groups.some((group) => group.trim().toLocaleUpperCase() === machine.operational_group.trim().toLocaleUpperCase()))
    : catalogs.machines

  useEffect(() => {
    if (!supabase || !frontId) { setMembers([]); setSelectedPeople([]); setMachineCode(''); return }
    let cancelled = false
    supabase.from('front_members').select('personnel_code,machine_code').eq('front_id', frontId).then(({ data, error }) => {
      if (cancelled) return
      if (error) { setNotice({ kind: 'error', text: `No se pudieron cargar los integrantes: ${error.message}` }); return }
      const rows = data ?? []
      setMembers(rows)
      setSelectedPeople(rows.map((member) => member.personnel_code))
      setMachineCode(rows.find((member) => member.machine_code)?.machine_code ?? '')
    })
    return () => { cancelled = true }
  }, [frontId])

  useEffect(() => {
    setFarmId(''); setLotId(''); setOperationCode(''); setFrontId(''); setQuantity(''); setTargetQuantity(''); setSelectedPeople([]); setMachineCode(''); setSavedReport(null)
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

  async function saveReport(event: FormEvent) {
    event.preventDefault()
    if (!supabase || !selectedOperation || !selectedLot || !selectedFront) return
    const amount = Number(quantity)
    const people = selectedPeople
    if (!Number.isFinite(amount) || amount <= 0 || people.length === 0) {
      setNotice({ kind: 'error', text: 'Ingresá una cantidad mayor a cero y seleccioná al menos una persona.' }); return
    }
    if (selectedOperation.task_type === 'Manual' && machineCode) {
      setNotice({ kind: 'error', text: 'La tarea seleccionada es manual y no admite maquinaria.' }); return
    }
    const perPerson = Math.floor((amount / people.length) * 1000) / 1000
    const allocations = people.map((personCode, index) => ({
      personnel_code: personCode,
      machine_code: selectedOperation.task_type === 'Manual' ? '' : machineCode,
      attendance: 'Presente',
      quantity: index === people.length - 1 ? Math.round((amount - perPerson * (people.length - 1)) * 1000) / 1000 : perPerson,
      front_id: frontId,
      person_hours: 12,
    }))
    const payload = {
      lot_id: lotId,
      operation_code: operationCode,
      front_id: frontId,
      quantity: amount,
      target_quantity: Number(targetQuantity) || amount,
      unit: selectedOperation.unit,
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
    <aside className="sidebar"><a className="brand" href="#inicio"><span className="brand-mark"><Leaf size={21} /></span><span><strong>Parte diario</strong><small>Gestión de tareas agrícolas</small></span></a><nav aria-label="Secciones"><a className="nav-link" href="#inicio">Inicio</a><a className="nav-link active" href="#cargar">Cargar parte</a></nav><div className="sidebar-note"><Cloud size={17} /><span>Conectado a Supabase<br /><b>Sincronización en línea</b></span></div></aside>
    <section className="workspace" id="inicio"><header className="topbar"><div><span className="eyebrow">{selectedFront ? `FRENTE · ${selectedFront.name}` : 'ASISTENTE DE CAMPO'}</span><h1>Cargar parte</h1></div><div className="account-actions"><span className="user-email">{session.user.email}</span><button className="icon-button" onClick={loadCatalogs} title="Actualizar catálogos" disabled={loading}><RefreshCw size={17} /></button><button className="icon-button" onClick={signOut} title="Cerrar sesión"><LogOut size={17} /></button></div></header>
      <section className="intro-card"><div><span className="eyebrow">REGISTRO DE TRABAJO</span><h2>Una carga simple para empezar.</h2><p>Seleccioná el lote, la tarea, el frente y la cantidad. El detalle se distribuye entre las personas elegidas.</p></div><div className="intro-icon"><Sprout size={34} /></div></section>
      {notice && <div className={`notice ${notice.kind}`} role="status">{notice.text}{savedReport && <span className="saved-code">{savedReport.report_code}</span>}</div>}
      {!hasMasterCatalogs && !loading && <section className="empty-state"><h2>Faltan datos maestros</h2><p>La conexión funciona, pero aún faltan fincas, lotes, tareas o personal activos. Revisá los catálogos en Supabase y actualizá esta pantalla.</p><button className="secondary-button" onClick={loadCatalogs}>Actualizar catálogos</button></section>}
      {hasMasterCatalogs && !hasFronts && !loading && <section className="empty-state"><h2>Los maestros están listos; falta un frente</h2><p>No hay frentes configurados en Supabase. Creá un frente y asignale personal antes de cargar partes. La administración de frentes todavía no está incluida en esta PWA.</p><button className="secondary-button" onClick={loadCatalogs}>Actualizar datos</button></section>}
      {loading && !hasMasterCatalogs && <div className="loading-label"><RefreshCw className="spin" size={18} /> Cargando datos…</div>}
      {hasMasterCatalogs && hasFronts && <form className="report-form" id="cargar" onSubmit={saveReport}>
        <section className="form-section"><div className="section-heading"><span>01</span><div><h2>Datos del parte</h2><p>Fecha y número de orden, si corresponde.</p></div></div><div className="field-grid two"><label>Fecha<input type="date" required value={reportDate} onChange={(e) => setReportDate(e.target.value)} /></label><label>Orden de servicio <small>Opcional</small><input value={serviceOrder} onChange={(e) => setServiceOrder(e.target.value)} placeholder="Número de orden" /></label></div></section>
        <section className="form-section"><div className="section-heading"><span>02</span><div><h2>Lote y tarea</h2><p>El avance se acumula en el ciclo abierto del lote y la operación.</p></div></div><div className="field-grid two"><label>Finca<select required value={farmId} onChange={(e) => { setFarmId(e.target.value); setLotId('') }}><option value="">Seleccionar finca</option>{catalogs.farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}</select></label><label>Lote<select required value={lotId} onChange={(e) => setLotId(e.target.value)} disabled={!farmId}><option value="">Seleccionar lote</option>{visibleLots.map((lot) => <option key={lot.id} value={lot.id}>{lot.lot_code} · {lot.lot_name || lot.crop}</option>)}</select></label><label>Tarea<select required value={operationCode} onChange={(e) => { const op = catalogs.operations.find((item) => item.operation_code === e.target.value); setOperationCode(e.target.value); setMachineCode(''); setTargetQuantity(op?.default_target ? String(op.default_target) : '') }}><option value="">Seleccionar tarea</option>{catalogs.operations.map((operation) => <option key={operation.operation_code} value={operation.operation_code}>{operation.operation_code} · {operation.name}</option>)}</select></label><label>Cantidad realizada <small>{selectedOperation?.unit || 'Unidad'}</small><input type="number" inputMode="decimal" min="0.001" step="0.001" required value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="0" /></label><label>Objetivo del lote <small>Opcional</small><input type="number" min="0" step="0.001" value={targetQuantity} onChange={(e) => setTargetQuantity(e.target.value)} placeholder={quantity || 'Sin objetivo'} /></label><label>Modo de distribución<select value={allocationMode} onChange={(e) => setAllocationMode(e.target.value)}><option>Total a repartir</option><option>Cantidad individual</option></select></label></div></section>
        <section className="form-section"><div className="section-heading"><span>03</span><div><h2>Frente y personal</h2><p>El total se reparte en partes iguales entre las personas seleccionadas.</p></div></div><div className="field-grid two"><label>Frente<select required value={frontId} onChange={(e) => setFrontId(e.target.value)}><option value="">Seleccionar frente</option>{catalogs.fronts.map((front) => <option key={front.id} value={front.id}>{front.name}</option>)}</select></label>{selectedOperation?.task_type !== 'Manual' && <label>Maquinaria <small>Opcional</small><select value={machineCode} onChange={(e) => setMachineCode(e.target.value)}><option value="">Sin maquinaria</option>{eligibleMachines.map((machine) => <option key={machine.machine_code} value={machine.machine_code}>{machine.machine_code} · {[machine.brand, machine.model].filter(Boolean).join(' ')}</option>)}</select></label>}</div>
          {!frontId && <p className="helper-text">Elegí un frente para ver su personal.</p>}{frontId && eligiblePeople.length === 0 && <p className="helper-text">Este frente todavía no tiene personal asignado.</p>}{eligiblePeople.length > 0 && <div className="people-list">{eligiblePeople.map((person) => <label className="person-option" key={person.employee_code}><input type="checkbox" checked={selectedPeople.includes(person.employee_code)} onChange={(e) => setSelectedPeople((current) => e.target.checked ? [...current, person.employee_code] : current.filter((code) => code !== person.employee_code))} /><span>{person.full_name}<small>Legajo {person.employee_code}</small></span></label>)}</div>}</section>
        <section className="form-section"><div className="section-heading"><span>04</span><div><h2>Observaciones</h2><p>Agregá una nota si hace falta.</p></div></div><label className="full-field">Notas<textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Observaciones del trabajo" /></label></section>
        <div className="form-actions"><span>Se guardará un borrador en Supabase.</span><button className="primary-button" disabled={loading || !selectedFront || !selectedLot || !selectedOperation}>{loading ? 'Guardando…' : 'Guardar parte'}</button></div>
      </form>}
      <footer>Asistente de parte diario <span>·</span> Versión de trabajo</footer>
    </section>
  </main>
}
