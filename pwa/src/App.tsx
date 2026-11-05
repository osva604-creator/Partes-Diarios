import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { ChevronDown, Cloud, Leaf, LogOut, Plus, RefreshCw, Save, Sprout, Users } from 'lucide-react'
import { hasSupabaseConfig, supabase } from './lib/supabase'

type Farm = { id: string; name: string }
type Lot = { id: string; farm_id: string; lot_code: string; lot_name: string; crop: string; variety: string; net_area: number | null; gross_area: number | null; furrows: number | null; planting_year: number | null; selectable: boolean; agronomic_data_available: boolean; totvs_location_id: string; suggested_cost_center_id: string; suggested_cost_center_name: string }
type Operation = { operation_code: string; name: string; unit: string; task_type: string; machine_groups: string[]; default_target: number | null; allows_inputs: boolean }
type CostCenter = { cost_center_id: string; name: string }
type OperationGroup = { group_code: string; name: string }
type InputCatalogItem = { input_code: string; description: string; unit: string }
type Person = { employee_code: string; full_name: string }
type Machine = { machine_code: string; operational_group: string; brand: string; model: string }
type Front = { id: string; name: string; created_by: string; active: boolean }
type FrontTaskMember = { operation_code: string; personnel_code: string; machine_code: string | null }
type AllocationDraft = { attendance: string; quantity: string; replacement_code: string; person_hours: string; machine_start_time: string; machine_end_time: string }
type Catalogs = { farms: Farm[]; lots: Lot[]; operations: Operation[]; personnel: Person[]; machines: Machine[]; fronts: Front[]; costCenters: CostCenter[]; groups: OperationGroup[]; inputs: InputCatalogItem[]; centerGroups: { cost_center_id: string; group_code: string }[]; groupOperations: { group_code: string; operation_code: string }[]; operationInputs: { operation_code: string; input_code: string }[] }
type Notice = { kind: 'error' | 'success'; text: string }
type ReportRow = Record<string, any>

const emptyCatalogs: Catalogs = { farms: [], lots: [], operations: [], personnel: [], machines: [], fronts: [], costCenters: [], groups: [], inputs: [], centerGroups: [], groupOperations: [], operationInputs: [] }
const today = () => {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Ocurrió un error inesperado.'
}

function allocationsInvalidReplacement(details: AllocationDraft[], personnel: Person[]) {
  const activeCodes = new Set(personnel.map((person) => person.employee_code))
  return details.some((detail) => detail.replacement_code.trim() && !activeCodes.has(detail.replacement_code.trim()))
}

function inputDoseUnit(unit: string) {
  return unit.toUpperCase() === 'TN' ? 'Kg' : unit || 'unidad'
}

function calculateInputTotal(basisQuantity: number, dose: number, unit: string) {
  return basisQuantity * dose / (unit.toUpperCase() === 'TN' ? 1000 : 1)
}

function calculateActualInputDose(quantity: number, basisQuantity: number, unit: string) {
  return quantity * (unit.toUpperCase() === 'TN' ? 1000 : 1) / basisQuantity
}

function formatInputAmount(value: number) {
  return new Intl.NumberFormat('es-AR', { maximumFractionDigits: 3 }).format(value)
}

function normalizedMachineGroup(group: string) {
  const normalized = group.trim().toLocaleUpperCase()
  return normalized === 'COSECHADORAS' ? 'MAQUINAS COSECHADORAS' : normalized
}

function machinesForOperation(operation: Operation | undefined, machines: Machine[]) {
  if (!operation || operation.task_type === 'Manual') return []
  if (operation.machine_groups.length === 0) return machines
  const allowedGroups = new Set(operation.machine_groups.map(normalizedMachineGroup))
  return machines.filter((machine) => allowedGroups.has(normalizedMachineGroup(machine.operational_group)))
}

function isMachineCompatible(operation: Operation, machine: Machine) {
  if (operation.task_type === 'Manual') return false
  if (operation.machine_groups.length === 0) return true
  const allowedGroups = new Set(operation.machine_groups.map(normalizedMachineGroup))
  return allowedGroups.has(normalizedMachineGroup(machine.operational_group))
}

function MachinePicker({
  machines,
  value,
  onChange,
  label,
  disabled = false,
}: {
  machines: Machine[]
  value: string
  onChange: (machineCode: string) => void
  label: string
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const selectedMachine = machines.find((machine) => machine.machine_code === value)
  const searchTerm = search.trim().toLocaleLowerCase()
  const visibleMachines = searchTerm
    ? machines.filter((machine) => `${machine.machine_code} ${machine.brand} ${machine.model} ${machine.operational_group}`.toLocaleLowerCase().includes(searchTerm))
    : machines

  return <div className="machine-picker" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
  }}>
    <button className="machine-picker-trigger" type="button" aria-label={label} aria-haspopup="listbox" aria-expanded={open} disabled={disabled} onClick={() => setOpen((current) => !current)}>
      <span>{selectedMachine ? `${selectedMachine.machine_code} · ${[selectedMachine.brand, selectedMachine.model].filter(Boolean).join(' ')}` : 'Sin maquinaria'}</span>
      <ChevronDown size={16} aria-hidden="true" />
    </button>
    {open && <div className="machine-picker-menu">
      <label className="machine-picker-search">Buscar por código, marca o modelo<input autoFocus type="search" value={search} onKeyDown={(event) => { if (event.key === 'Enter') event.preventDefault() }} onChange={(event) => setSearch(event.target.value)} placeholder="Ej.: 10101124 o John Deere" /></label>
      <div className="machine-picker-options" role="listbox" aria-label="Maquinaria compatible con la tarea">
        <button type="button" role="option" aria-selected={!value} className={!value ? 'selected' : ''} onClick={() => { onChange(''); setOpen(false); setSearch('') }}>Sin maquinaria</button>
        {visibleMachines.map((machine) => <button type="button" role="option" aria-selected={value === machine.machine_code} className={value === machine.machine_code ? 'selected' : ''} key={machine.machine_code} onClick={() => { onChange(machine.machine_code); setOpen(false); setSearch('') }}>
          <span>{machine.machine_code} · {[machine.brand, machine.model].filter(Boolean).join(' ')}</span>
          <small>{machine.operational_group}</small>
        </button>)}
        {visibleMachines.length === 0 && <p className="machine-picker-empty">No hay máquinas compatibles con esa búsqueda.</p>}
      </div>
      <small className="machine-picker-count">{visibleMachines.length} de {machines.length} máquinas compatibles</small>
    </div>}
  </div>
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [sessionReady, setSessionReady] = useState(false)
  const [catalogs, setCatalogs] = useState<Catalogs>(emptyCatalogs)
  const [members, setMembers] = useState<FrontTaskMember[]>([])
  const [memberMachines, setMemberMachines] = useState<Record<string, string>>({})
  const [allocationDrafts, setAllocationDrafts] = useState<Record<string, AllocationDraft>>({})
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
  const [chosenCostCenter, setChosenCostCenter] = useState('')
  const [groupCode, setGroupCode] = useState('')
  const [inputLines, setInputLines] = useState<{ input_code: string; dose: string; quantity: string; unit: string }[]>([])
  const [draftTasks, setDraftTasks] = useState<Record<string, unknown>[]>([])
  const [exchangePreview, setExchangePreview] = useState<{ report_date: string; service_order: string; tasks: Record<string, unknown>[]; labels: string[] } | null>(null)
  const [draftIdempotencyKey, setDraftIdempotencyKey] = useState('')
  const [draftFingerprint, setDraftFingerprint] = useState('')
  const [section, setSection] = useState<'report' | 'fronts' | 'reports'>('report')
  const [reports, setReports] = useState<ReportRow[]>([])
  const [reportSearch, setReportSearch] = useState('')
  const [reportFrom, setReportFrom] = useState('')
  const [reportTo, setReportTo] = useState('')
  const [selectedReport, setSelectedReport] = useState<ReportRow | null>(null)
  const [correctionDraft, setCorrectionDraft] = useState<ReportRow | null>(null)
  const [cycleTotals, setCycleTotals] = useState<Record<string, number>>({})
  const [sentTo, setSentTo] = useState('')
  const [sentVia, setSentVia] = useState('WhatsApp')
  const [manageFrontId, setManageFrontId] = useState('')
  const [manageFrontName, setManageFrontName] = useState('')
  const [newFrontName, setNewFrontName] = useState('')
  const [manageOperationCode, setManageOperationCode] = useState('')
  const [frontPeopleSearch, setFrontPeopleSearch] = useState('')
  const [openCycle, setOpenCycle] = useState<{ allocation_mode: string; target_quantity: number; target_available: boolean; unit: string } | null>(null)

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
      const [farms, lots, operations, personnel, machines, fronts, costCenters, groups, inputs, centerGroups, groupOperations, operationInputs] = await Promise.all([
        supabase.from('farms').select('id,name').eq('active', true).order('name'),
        supabase.from('lots').select('id,farm_id,lot_code,lot_name,crop,variety,net_area,gross_area,furrows,planting_year,selectable,agronomic_data_available,totvs_location_id,suggested_cost_center_id,suggested_cost_center_name').eq('active', true).order('lot_code'),
        supabase.from('operations').select('operation_code,name,unit,task_type,machine_groups,default_target,allows_inputs').eq('active', true).order('operation_code'),
        supabase.from('personnel').select('employee_code,full_name').eq('active', true).order('full_name'),
        supabase.from('machines').select('machine_code,operational_group,brand,model').eq('active', true).order('machine_code'),
        supabase.from('fronts').select('id,name,created_by,active').eq('active', true).order('name'),
        supabase.from('cost_centers').select('cost_center_id,name').eq('active', true).order('cost_center_id'),
        supabase.from('operation_groups').select('group_code,name').eq('active', true).order('group_code'),
        supabase.from('inputs').select('input_code,description,unit').eq('active', true).order('description'),
        supabase.from('cost_center_operation_groups').select('cost_center_id,group_code'),
        supabase.from('operation_group_operations').select('group_code,operation_code'),
        supabase.from('operation_inputs').select('operation_code,input_code'),
      ])
      const result = [farms, lots, operations, personnel, machines, fronts, costCenters, groups, inputs, centerGroups, groupOperations, operationInputs]
      const failed = result.find((item) => item.error)
      if (failed?.error) throw failed.error
      // operation_machines expands group rules into ~29k rows; its REST response is capped, so it cannot safely drive client filtering.
      // The full rules live on operations.machine_groups and the machine catalog is small enough to load completely.
      setCatalogs({ farms: farms.data ?? [], lots: lots.data ?? [], operations: operations.data ?? [], personnel: personnel.data ?? [], machines: machines.data ?? [], fronts: fronts.data ?? [], costCenters: costCenters.data ?? [], groups: groups.data ?? [], inputs: inputs.data ?? [], centerGroups: centerGroups.data ?? [], groupOperations: groupOperations.data ?? [], operationInputs: operationInputs.data ?? [] })
    } catch (error) {
      setNotice({ kind: 'error', text: `No se pudieron cargar los datos: ${errorText(error)}` })
    } finally { setLoading(false) }
  }, [session])

  useEffect(() => { void loadCatalogs() }, [loadCatalogs])

  const loadReports = useCallback(async () => {
    if (!supabase || !session) return
    setLoading(true)
    const { data, error } = await supabase.from('daily_reports').select('id,report_code,report_sequence,report_date,service_order,document_status,pdf_version,created_by,created_at,reviewed_at,sent_at,report_tasks(id,line_no,quantity,crop,notes,cost_center_context,catalog_snapshot,lot_id,operation_code,work_cycle_id,front_id,lots(id,farm_id,lot_code,lot_name,crop,variety),operations(operation_code,name,unit,task_type,machine_groups),work_cycles(cycle_no,target_quantity,target_available,unit,allocation_mode,status),allocations(id,personnel_code,machine_code,attendance,quantity,replacement_code,front_id,person_hours,machine_start_time,machine_end_time,personnel:personnel!allocations_personnel_code_fkey(employee_code,full_name),machines(machine_code,brand,model,operational_group)),part_inputs(id,input_code,dose,quantity,unit,inputs(input_code,description)))').order('report_date', { ascending: false }).limit(500)
    if (error) setNotice({ kind: 'error', text: `No se pudieron cargar los partes permitidos por tu cuenta: ${error.message}` })
    else {
      const next = data ?? []
      setReports(next)
      setSelectedReport((current) => current ? next.find((report) => report.id === current.id) ?? current : current)
    }
    setLoading(false)
  }, [session])

  useEffect(() => { if (section === 'reports') void loadReports() }, [section, loadReports])

  useEffect(() => {
    const cycleIds = [...new Set((selectedReport?.report_tasks ?? []).map((task: ReportRow) => task.work_cycle_id).filter(Boolean))]
    if (!supabase || cycleIds.length === 0) { setCycleTotals({}); return }
    let cancelled = false
    supabase.from('report_tasks').select('work_cycle_id,quantity').in('work_cycle_id', cycleIds).then(({ data, error }) => {
      if (cancelled) return
      if (error) { setNotice({ kind: 'error', text: `No se pudo calcular el acumulado visible: ${error.message}` }); return }
      const totals: Record<string, number> = {}
      for (const row of data ?? []) totals[row.work_cycle_id] = (totals[row.work_cycle_id] ?? 0) + Number(row.quantity)
      setCycleTotals(totals)
    })
    return () => { cancelled = true }
  }, [selectedReport])

  useEffect(() => {
    if (!supabase || !session) { setAppRole(''); return }
    supabase.from('profiles').select('role').eq('user_id', session.user.id).maybeSingle()
      .then(({ data }) => setAppRole(data?.role ?? ''))
  }, [session])

  const visibleLots = useMemo(() => catalogs.lots.filter((lot) => lot.selectable && (!farmId || lot.farm_id === farmId)), [catalogs.lots, farmId])
  const selectedOperation = catalogs.operations.find((operation) => operation.operation_code === operationCode)
  const selectedFront = catalogs.fronts.find((front) => front.id === frontId)
  const selectedLot = catalogs.lots.find((lot) => lot.id === lotId)
  const effectiveCostCenter = chosenCostCenter || selectedLot?.suggested_cost_center_id || ''
  const permittedGroups = effectiveCostCenter ? catalogs.centerGroups.filter((row) => row.cost_center_id === effectiveCostCenter).map((row) => row.group_code) : []
  const visibleOperationGroups = catalogs.groups.filter((group) => permittedGroups.includes(group.group_code))
  const allowedOperations = catalogs.operations.filter((operation) => {
    if (!effectiveCostCenter || catalogs.groups.length === 0) return true
    const groupsForOperation = catalogs.groupOperations.filter((row) => row.operation_code === operation.operation_code).map((row) => row.group_code)
    return Boolean(groupCode) && groupsForOperation.includes(groupCode) && permittedGroups.includes(groupCode)
  })
  const currentUnit = openCycle?.unit ?? selectedOperation?.unit ?? ''
  const completedWorkQuantity = allocationMode === 'Total a repartir'
    ? Number(quantity || 0)
    : selectedPeople.reduce((total, personCode) => {
      const detail = allocationDrafts[personCode]
      const amount = Number(detail?.quantity)
      return total + (detail?.attendance !== 'Ausente' && Number.isFinite(amount) ? amount : 0)
    }, 0)
  const eligiblePeople = catalogs.personnel.filter((person) => members.some((member) => member.personnel_code === person.employee_code))
  const selectedManageMembers = frontTaskMembers.filter((member) => member.operation_code === manageOperationCode)
  const manageOperation = catalogs.operations.find((operation) => operation.operation_code === manageOperationCode)
  const manageMachines = machinesForOperation(manageOperation, catalogs.machines)
  const matchingManagePeople = catalogs.personnel.filter((person) => `${person.full_name} ${person.employee_code}`.toLocaleLowerCase().includes(frontPeopleSearch.trim().toLocaleLowerCase()))
  const manageableFronts = catalogs.fronts.filter((front) => appRole === 'administrador' || front.created_by === session?.user.id)
  const manageFront = manageableFronts.find((front) => front.id === manageFrontId)
  const eligibleMachines = machinesForOperation(selectedOperation, catalogs.machines)
  const filteredReports = useMemo(() => reports.filter((report) => {
    if (reportFrom && report.report_date < reportFrom) return false
    if (reportTo && report.report_date > reportTo) return false
    const query = reportSearch.trim().toLocaleLowerCase()
    if (!query) return true
    const tasks = report.report_tasks ?? []
    const haystack = [report.report_code, report.service_order, report.created_by, ...tasks.flatMap((task: ReportRow) => [task.lots?.lot_code, task.lots?.lot_name, catalogs.farms.find((farm) => farm.id === task.lots?.farm_id)?.name, task.operations?.name, ...(task.allocations ?? []).map((allocation: ReportRow) => allocation.personnel?.full_name), ...(task.part_inputs ?? []).map((input: ReportRow) => input.inputs?.description)])].filter(Boolean).join(' ').toLocaleLowerCase()
    return haystack.includes(query)
  }), [reports, reportFrom, reportTo, reportSearch, catalogs.farms])

  useEffect(() => {
    if (!supabase || !frontId || !operationCode) { setMembers([]); setSelectedPeople([]); setMemberMachines({}); setAllocationDrafts({}); return }
    let cancelled = false
    supabase.from('front_task_members').select('operation_code,personnel_code,machine_code').eq('front_id', frontId).eq('operation_code', operationCode).then(({ data, error }) => {
      if (cancelled) return
      if (error) { setNotice({ kind: 'error', text: `No se pudieron cargar los integrantes: ${error.message}` }); return }
      const rows = data ?? []
      setMembers(rows)
      setSelectedPeople(rows.map((member) => member.personnel_code))
      setMemberMachines(Object.fromEntries(rows.map((member) => [member.personnel_code, member.machine_code ?? ''])))
      setAllocationDrafts(Object.fromEntries(rows.map((member) => [member.personnel_code, { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: '12', machine_start_time: '', machine_end_time: '' }])))
    })
    return () => { cancelled = true }
  }, [frontId, operationCode])

  useEffect(() => {
    if (!supabase || !lotId || !operationCode) { setOpenCycle(null); setTargetQuantity(''); return }
    let cancelled = false
    const lot = catalogs.lots.find((item) => item.id === lotId)
    const operation = catalogs.operations.find((item) => item.operation_code === operationCode)
    supabase.from('work_cycles').select('allocation_mode,target_quantity,target_available,unit,cycle_no').eq('lot_id', lotId).eq('operation_code', operationCode).eq('status', 'Abierto').order('cycle_no', { ascending: false }).limit(1).maybeSingle()
      .then(({ data, error }) => {
        if (cancelled) return
        if (error) { setNotice({ kind: 'error', text: `No se pudo consultar el avance existente: ${error.message}` }); return }
        if (data) {
          setOpenCycle(data)
          setAllocationMode(data.allocation_mode)
          setTargetQuantity(data.target_available ? String(data.target_quantity) : '')
        } else {
          setOpenCycle(null)
          const unit = operation?.unit.trim().toLocaleUpperCase() ?? ''
          const mode = ['SC', 'HA', 'TN'].includes(unit) ? 'Total a repartir' : 'Cantidad individual'
          setAllocationMode(mode)
          const inventoryTarget = unit === 'SC' ? lot?.furrows : unit === 'HA' ? (lot?.net_area ?? lot?.gross_area) : null
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
    setFarmId(''); setLotId(''); setOperationCode(''); setFrontId(''); setQuantity(''); setTargetQuantity(''); setSelectedPeople([]); setMemberMachines({}); setAllocationDrafts({}); setInputLines([]); setSavedReport(null); setDraftTasks([]); setDraftIdempotencyKey(''); setDraftFingerprint('')
  }, [session?.user.id])

  useEffect(() => { setChosenCostCenter(''); setGroupCode('') }, [lotId])

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
    const amount = allocationMode === 'Total a repartir' ? Number(quantity) : 0
    const people = selectedPeople
    if ((allocationMode === 'Total a repartir' && (!Number.isFinite(amount) || amount <= 0)) || people.length === 0) {
      setNotice({ kind: 'error', text: 'Ingresá una cantidad válida y seleccioná al menos una persona.' }); return
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
    if (inputLines.length && !selectedOperation.allows_inputs) {
      setNotice({ kind: 'error', text: 'La tarea elegida no admite insumos.' }); return
    }
    if (new Set(inputLines.map((line) => line.input_code)).size !== inputLines.length) {
      setNotice({ kind: 'error', text: 'No repitas un insumo en la misma tarea.' }); return
    }
    const compatibleInputCodes = catalogs.operationInputs.filter((row) => row.operation_code === operationCode).map((row) => row.input_code)
    if (compatibleInputCodes.length && inputLines.some((line) => !compatibleInputCodes.includes(line.input_code))) {
      setNotice({ kind: 'error', text: 'Hay un insumo que no corresponde a esta tarea.' }); return
    }
    if (inputLines.some((line) => !line.dose.trim() || !line.quantity.trim() || !line.unit.trim() || !Number.isFinite(Number(line.dose)) || Number(line.dose) < 0 || !Number.isFinite(Number(line.quantity)) || Number(line.quantity) < 0)) {
      setNotice({ kind: 'error', text: 'Revisá la dosis y el consumo de los insumos.' }); return
    }
    const details = people.map((personCode) => allocationDrafts[personCode] ?? { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: '12', machine_start_time: '', machine_end_time: '' })
    const fixedTotal = details.reduce((total, detail) => total + (detail.attendance === 'Cantidad fija' ? Number(detail.quantity || 0) : 0), 0)
    const absentCount = details.filter((detail) => detail.attendance === 'Ausente').length
    const dynamicCount = details.filter((detail) => detail.attendance === 'Presente').length
    const remainderToShare = allocationMode === 'Total a repartir' ? amount - fixedTotal : 0
    if (allocationMode === 'Total a repartir' && (fixedTotal > amount || (dynamicCount === 0 && Math.abs(fixedTotal - amount) > 0.001))) {
      setNotice({ kind: 'error', text: 'Las cantidades fijas deben caber dentro del total; sin personas presentes, deben cubrirlo completo.' }); return
    }
    if (allocationMode === 'Cantidad individual' && details.some((detail) => detail.attendance !== 'Ausente' && (!detail.quantity.trim() || Number(detail.quantity) < 0))) {
      setNotice({ kind: 'error', text: 'Ingresá una cantidad individual válida para cada persona presente o fija.' }); return
    }
    if (details.some((detail) => detail.attendance === 'Cantidad fija' && (!detail.quantity.trim() || Number(detail.quantity) < 0))) {
      setNotice({ kind: 'error', text: 'Ingresá la cantidad de cada persona con cantidad fija.' }); return
    }
    if (integerAllocation && details.some((detail) => detail.attendance === 'Cantidad fija' && !Number.isInteger(Number(detail.quantity)))) {
      setNotice({ kind: 'error', text: 'Las cantidades fijas en surcos deben ser enteras.' }); return
    }
    if (details.some((detail) => !Number.isFinite(Number(detail.person_hours)) || Number(detail.person_hours) < 0)) {
      setNotice({ kind: 'error', text: 'Las horas por persona deben ser un número válido.' }); return
    }
    if (allocationsInvalidReplacement(details, catalogs.personnel)) {
      setNotice({ kind: 'error', text: 'Elegí una persona activa como reemplazo o dejá el campo vacío.' }); return
    }
    if (details.some((detail) => Boolean(detail.machine_start_time) !== Boolean(detail.machine_end_time) || (detail.machine_start_time && (!Number.isInteger(Number(detail.machine_start_time)) || !Number.isInteger(Number(detail.machine_end_time)) || Number(detail.machine_end_time) < Number(detail.machine_start_time))))) {
      setNotice({ kind: 'error', text: 'Las lecturas de máquina deben ser enteras, estar completas y terminar después del inicio.' }); return
    }
    const dynamicAmount = dynamicCount > 0 ? remainderToShare / dynamicCount : 0
    const baseDynamic = integerAllocation ? Math.floor(dynamicAmount) : Math.floor(dynamicAmount * 10000) / 10000
    const shareRemainder = integerAllocation ? Math.round(remainderToShare - baseDynamic * dynamicCount) : Math.round((remainderToShare - baseDynamic * dynamicCount) * 10000) / 10000
    const allocations = people.map((personCode, index) => {
      const detail = details[index]
      const assignedMachine = selectedOperation.task_type === 'Manual' ? '' : memberMachines[personCode] ?? ''
      const dynamicIndex = details.slice(0, index).filter((item) => item.attendance === 'Presente').length
      const assignedQuantity = detail.attendance === 'Ausente' ? 0
        : detail.attendance === 'Cantidad fija' || allocationMode === 'Cantidad individual' ? Number(detail.quantity)
          : baseDynamic + (dynamicIndex < Math.round(shareRemainder * (integerAllocation ? 1 : 10000)) ? (integerAllocation ? 1 : 0.0001) : 0)
      return {
        personnel_code: personCode,
        machine_code: assignedMachine,
        attendance: detail.attendance,
        quantity: assignedQuantity,
        replacement_code: detail.replacement_code,
        front_id: frontId,
        person_hours: Number(detail.person_hours),
        machine_start_time: assignedMachine && detail.machine_start_time ? Number(detail.machine_start_time) : null,
        machine_end_time: assignedMachine && detail.machine_end_time ? Number(detail.machine_end_time) : null,
      }
    })
    const taskQuantity = allocations.reduce((total, allocation) => total + allocation.quantity, 0)
    if (taskQuantity <= 0) {
      setNotice({ kind: 'error', text: 'La suma de cantidades de las personas debe ser mayor que cero.' }); return
    }
    if (integerAllocation && allocations.some((allocation) => !Number.isInteger(allocation.quantity))) {
      setNotice({ kind: 'error', text: 'La distribución en surcos debe usar cantidades enteras.' }); return
    }
    if (allocationMode === 'Total a repartir' && Math.abs(taskQuantity - amount) > 0.001) {
      setNotice({ kind: 'error', text: 'La suma de cantidades asignadas no coincide con el trabajo.' }); return
    }
    if (allocationMode === 'Total a repartir' && absentCount === people.length) {
      setNotice({ kind: 'error', text: 'No se puede distribuir un total entre personas ausentes.' }); return
    }
    if (selectedOperation.machine_groups.length && !people.some((personCode, index) => details[index].attendance !== 'Ausente' && memberMachines[personCode])) {
      setNotice({ kind: 'error', text: 'Asigná al menos una máquina compatible a las personas que la necesitan.' }); return
    }
    if (draftTasks.some((task) => task.lot_id === lotId && task.operation_code === operationCode)) {
      setNotice({ kind: 'error', text: 'Ese lote y tarea ya están incluidos en este parte.' }); return
    }
    const suggestedCenter = selectedLot.suggested_cost_center_id || ''
    const selectedCenter = effectiveCostCenter
    const selectedCenterName = catalogs.costCenters.find((center) => center.cost_center_id === selectedCenter)?.name ?? selectedLot.suggested_cost_center_name ?? ''
    const payload: Record<string, unknown> = {
      lot_id: lotId,
      operation_code: operationCode,
      front_id: frontId,
      quantity: taskQuantity,
      target_quantity: allocationMode === 'Total a repartir' ? (targetQuantity.trim() ? Number(targetQuantity) : 0) : 0,
      target_available: allocationMode === 'Total a repartir' && (openCycle?.target_available ?? Boolean(targetQuantity.trim())),
      unit: openCycle?.unit ?? selectedOperation.unit,
      allocation_mode: allocationMode,
      crop: selectedLot.crop,
      notes: notes.trim(),
      allocations,
      inputs: inputLines.map((line) => ({ input_code: line.input_code, dose: Number(line.dose), quantity: Number(line.quantity), unit: line.unit })),
      cost_center_context: {
        suggested: { id: suggestedCenter, name: selectedLot.suggested_cost_center_name || '' },
        selected: { id: selectedCenter, name: selectedCenterName },
        source: suggestedCenter ? 'totvs_location' : 'manual',
        changed: Boolean(suggestedCenter && selectedCenter !== suggestedCenter),
      },
    }
    setDraftTasks((current) => [...current, payload])
    setQuantity(''); setNotes(''); setInputLines([]); setNotice({ kind: 'success', text: `Tarea agregada al borrador (${draftTasks.length + 1}).` })
    return
  }

  async function submitDraft() {
    if (!supabase || draftTasks.length === 0) return
    setLoading(true); setNotice(null); setSavedReport(null)
    const fingerprint = JSON.stringify({ reportDate, serviceOrder: serviceOrder.trim(), tasks: draftTasks })
    const idempotencyKey = draftIdempotencyKey && draftFingerprint === fingerprint ? draftIdempotencyKey : crypto.randomUUID()
    setDraftIdempotencyKey(idempotencyKey); setDraftFingerprint(fingerprint)
    const { data, error } = await supabase.rpc('create_daily_report', {
      p_idempotency_key: idempotencyKey,
      p_report_date: reportDate,
      p_service_order: serviceOrder.trim(),
      p_tasks: draftTasks,
    })
    if (error) setNotice({ kind: 'error', text: `No se pudo guardar el parte: ${error.message}` })
    else {
      const report = Array.isArray(data) ? data[0] : data
      setSavedReport(report)
      setNotice({ kind: 'success', text: `Parte ${report?.report_code ?? ''} guardado correctamente.` })
      setDraftTasks([]); setDraftIdempotencyKey(''); setDraftFingerprint(''); setQuantity(''); setNotes('')
    }
    setLoading(false)
  }

  function discardDraft() {
    if (!draftTasks.length || window.confirm('¿Descartar todas las tareas de este borrador?')) {
      setDraftTasks([]); setDraftIdempotencyKey(''); setDraftFingerprint(''); setNotice({ kind: 'success', text: 'Borrador descartado.' })
    }
  }

  async function previewExchangeFile(file?: File) {
    if (!file) return
    setExchangePreview(null)
    try {
      if (draftTasks.length) throw new Error('Guardá o descartá el borrador actual antes de importar un JSON.')
      if (file.size > 5 * 1024 * 1024) throw new Error('El JSON supera el límite de 5 MB.')
      const source = JSON.parse(await file.text())
      if (source.schema !== 'asistente-parte-diario' || source.schema_version !== 1 || !Array.isArray(source.tasks) || source.tasks.length < 1 || source.tasks.length > 1000) throw new Error('El archivo no coincide con el esquema asistente-parte-diario v1 o no tiene tareas válidas.')
      if (!catalogs.lots.length || !catalogs.operations.length || !catalogs.personnel.length) throw new Error('Esperá a que carguen los catálogos antes de importar.')
      const labels: string[] = []
      const tasks = source.tasks.map((entry: ReportRow, index: number) => {
        const part = entry?.part
        const lot = catalogs.lots.find((item) => item.id === part?.lot_key && item.selectable)
        const operation = catalogs.operations.find((item) => item.operation_code === part?.operation_key)
        if (!lot || !operation) throw new Error(`La tarea ${index + 1}: lote u operación inexistente/inactiva para una nueva carga.`)
        if (!Array.isArray(entry.allocations) || entry.allocations.length === 0 || !Array.isArray(entry.inputs ?? [])) throw new Error(`La tarea ${index + 1}: faltan personas o la lista de insumos no es válida.`)
        const allocations = entry.allocations.map((row: ReportRow) => {
          const person = catalogs.personnel.find((item) => item.employee_code === row.personnel_key)
          const machine = row.machine_key ? catalogs.machines.find((item) => item.machine_code === row.machine_key) : null
          if (!person || (row.machine_key && !machine)) throw new Error(`La tarea ${index + 1}: hay una persona o máquina que no está activa.`)
          if (machine && operation.task_type === 'Manual') throw new Error(`La tarea ${index + 1}: una tarea manual no puede tener máquina.`)
          const compatible = machine ? isMachineCompatible(operation, machine) : !row.machine_key
          if (machine && !compatible) throw new Error(`La tarea ${index + 1}: la máquina no es compatible con la operación.`)
          const amount = Number(row.quantity ?? 0)
          const attendance = row.attendance ?? 'Presente'
          const personHours = Number(row.person_hours ?? 12)
          const replacement = row.replacement_key ? catalogs.personnel.find((item) => item.employee_code === row.replacement_key) : null
          const start = row.machine_start_time == null ? null : Number(row.machine_start_time)
          const end = row.machine_end_time == null ? null : Number(row.machine_end_time)
          if (!Number.isFinite(amount) || amount < 0 || !['Presente', 'Ausente', 'Cantidad fija'].includes(attendance) || (attendance === 'Ausente' && amount !== 0)) throw new Error(`La tarea ${index + 1}: una cantidad o asistencia no es válida.`)
          if (!Number.isFinite(personHours) || personHours < 0 || personHours > 48 || (row.replacement_key && !replacement)) throw new Error(`La tarea ${index + 1}: las horas o el reemplazo no son válidos.`)
          if ((start != null && (!Number.isInteger(start) || start < 0)) || (end != null && (!Number.isInteger(end) || end < 0)) || ((start == null) !== (end == null)) || (start != null && end != null && end < start)) throw new Error(`La tarea ${index + 1}: las lecturas de máquina no son válidas.`)
          return { personnel_code: person.employee_code, machine_code: row.machine_key ?? '', attendance, quantity: amount, replacement_code: row.replacement_key ?? '', front_id: frontId, person_hours: personHours, machine_start_time: start, machine_end_time: end }
        })
        if (new Set(allocations.map((row: ReportRow) => row.personnel_code)).size !== allocations.length) throw new Error(`La tarea ${index + 1}: hay personas repetidas.`)
        if (operation.machine_groups.length && !allocations.some((row: ReportRow) => row.machine_code && row.attendance !== 'Ausente')) throw new Error(`La tarea ${index + 1}: la operación requiere una máquina.`)
        const inputs = (entry.inputs ?? []).map((row: ReportRow) => {
          const input = catalogs.inputs.find((item) => item.input_code === row.input_key)
          if (!input || !operation.allows_inputs) throw new Error(`La tarea ${index + 1}: contiene un insumo no disponible para esa operación.`)
          const dose = Number(row.dose ?? 0); const amount = Number(row.quantity ?? 0)
          if (!Number.isFinite(dose) || dose < 0 || !Number.isFinite(amount) || amount < 0) throw new Error(`La tarea ${index + 1}: la dosis o el consumo del insumo no son válidos.`)
          return { input_code: input.input_code, dose, quantity: amount, unit: row.unit ?? input.unit }
        })
        const quantity = Number(part.quantity)
        const total = allocations.reduce((sum: number, row: ReportRow) => sum + row.quantity, 0)
        if (!Number.isFinite(quantity) || quantity <= 0 || Math.abs(total - quantity) > 0.001) throw new Error(`La tarea ${index + 1}: la cantidad no coincide con la suma asignada.`)
        const unit = String(part.unit || operation.unit)
        if (unit.toUpperCase() === 'SC' && (!Number.isInteger(quantity) || allocations.some((row: ReportRow) => !Number.isInteger(row.quantity)))) throw new Error(`La tarea ${index + 1}: las cantidades en surcos deben ser enteras.`)
        labels.push(`${lot.lot_code} · ${operation.name} · ${quantity} ${unit}`)
        const target = part.target_quantity == null ? 0 : Number(part.target_quantity)
        const allocationMode = part.allocation_mode || (['SC', 'HA', 'TN'].includes(unit.toUpperCase()) ? 'Total a repartir' : 'Cantidad individual')
        if (!Number.isFinite(target) || target < 0 || !['Total a repartir', 'Cantidad individual'].includes(allocationMode)) throw new Error(`La tarea ${index + 1}: el objetivo o modo de distribución no es válido.`)
        return {
          lot_id: lot.id, operation_code: operation.operation_code, front_id: frontId, quantity,
          target_quantity: target, target_available: part.target_quantity != null,
          unit, allocation_mode: allocationMode,
          crop: part.crop ?? lot.crop, notes: part.notes ?? '', allocations, inputs,
          cost_center_context: part.cost_center_context ?? {},
        }
      })
      const unique = new Set<string>()
      for (const task of tasks) {
        const key = `${task.lot_id}:${task.operation_code}`
        if (unique.has(key)) throw new Error('El archivo repite una combinación de lote y operación.')
        unique.add(key)
      }
      const reportDate = String(source.report?.report_date ?? today())
      const parsedDate = new Date(`${reportDate}T00:00:00`)
      if (!/^\d{4}-\d{2}-\d{2}$/.test(reportDate) || Number.isNaN(parsedDate.getTime()) || parsedDate.toISOString().slice(0, 10) !== reportDate) throw new Error('La fecha del archivo no es válida.')
      setExchangePreview({ report_date: reportDate, service_order: String(source.report?.service_order ?? ''), tasks, labels })
    } catch (error) { setNotice({ kind: 'error', text: `No se pudo preparar la importación: ${errorText(error)}` }) }
  }

  function acceptExchangePreview() {
    if (!exchangePreview || !frontId) { setNotice({ kind: 'error', text: 'Elegí primero un frente para asociarlo a las tareas importadas.' }); return }
    const tasks = exchangePreview.tasks.map((task) => ({ ...task, front_id: frontId, allocations: (task.allocations as ReportRow[]).map((row) => ({ ...row, front_id: frontId })) }))
    setReportDate(exchangePreview.report_date); setServiceOrder(exchangePreview.service_order); setDraftTasks(tasks)
    setDraftIdempotencyKey(''); setDraftFingerprint(''); setExchangePreview(null)
    setNotice({ kind: 'success', text: 'Vista previa aceptada: el contenido quedó en el borrador local. Todavía falta guardar el parte.' })
  }

  function buildReportExchange(report: ReportRow) {
    const installationId = localStorage.getItem('parte-diario-installation-id') || crypto.randomUUID()
    localStorage.setItem('parte-diario-installation-id', installationId)
    const payload = {
      schema: 'asistente-parte-diario', schema_version: 1, source_id: installationId,
        report: { report_code: report.report_code, created_by: report.created_by, report_date: report.report_date, service_order: report.service_order, document_status: report.document_status },
      tasks: (report.report_tasks ?? []).map((task: ReportRow) => ({
        part: { lot_key: task.lot_id, operation_key: task.operation_code, unit: task.work_cycles?.unit ?? task.operations?.unit ?? '', allocation_mode: task.work_cycles?.allocation_mode ?? 'Total a repartir', quantity: Number(task.quantity), crop: task.crop ?? '', notes: task.notes ?? '', target_quantity: task.work_cycles?.target_available === false ? null : task.work_cycles?.target_quantity ?? null, cycle_no: task.work_cycles?.cycle_no ?? null, cost_center_context: task.cost_center_context ?? {} },
        allocations: (task.allocations ?? []).map((allocation: ReportRow) => ({ personnel_key: allocation.personnel_code, machine_key: allocation.machine_code, attendance: allocation.attendance, quantity: Number(allocation.quantity), replacement_key: allocation.replacement_code, person_hours: Number(allocation.person_hours), machine_start_time: allocation.machine_start_time, machine_end_time: allocation.machine_end_time })),
        inputs: (task.part_inputs ?? []).map((input: ReportRow) => ({ input_key: input.input_code, dose: Number(input.dose), quantity: Number(input.quantity), unit: input.unit })),
        catalogs: { lot: task.lots ?? {}, operation: task.operations ?? {}, people: Object.fromEntries((task.allocations ?? []).map((row: ReportRow) => [row.personnel_code, row.personnel ?? {}])), machines: Object.fromEntries((task.allocations ?? []).filter((row: ReportRow) => row.machine_code).map((row: ReportRow) => [row.machine_code, row.machines ?? {}])), inputs: Object.fromEntries((task.part_inputs ?? []).map((row: ReportRow) => [row.input_code, row.inputs ?? {}])) },
      })),
    }
    const json = JSON.stringify(payload)
    if (new TextEncoder().encode(json).byteLength > 5 * 1024 * 1024) throw new Error('El JSON supera el límite de 5 MB.')
    if (!payload.tasks.length || payload.tasks.length > 1000) throw new Error('La cantidad de tareas no es válida para exportar.')
    return json
  }

  function downloadReportExchange(report: ReportRow) {
    let json: string
    try { json = buildReportExchange(report) } catch (error) { setNotice({ kind: 'error', text: errorText(error) }); return }
    const blob = new Blob([JSON.stringify(JSON.parse(json), null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a')
    anchor.href = url; anchor.download = `${report.report_code}.parte_diario_v1.json`; anchor.click(); URL.revokeObjectURL(url)
  }

  async function buildReportPdf(report: ReportRow) {
    if (!['Revisado', 'Enviado'].includes(report.document_status)) throw new Error('El PDF solo se genera para un parte revisado o enviado.')
    const { PDFDocument, StandardFonts, rgb } = await import('pdf-lib')
    const json = buildReportExchange(report)
    const doc = await PDFDocument.create()
    const regular = await doc.embedFont(StandardFonts.Helvetica)
    const bold = await doc.embedFont(StandardFonts.HelveticaBold)
    const pageSize: [number, number] = [595.28, 841.89]
    let page = doc.addPage(pageSize); let y = pageSize[1] - 42
    const green = rgb(0.29, 0.39, 0.20); const black = rgb(0.08, 0.08, 0.08)
    const text = (value: unknown) => String(value ?? '').replace(/[^\x00-\xFF]/g, '?')
    const wrap = (value: unknown, max = 92) => { const source = text(value); const lines: string[] = []; for (let i = 0; i < source.length; i += max) lines.push(source.slice(i, i + max)); return lines.length ? lines : [''] }
    const line = (value: unknown, size = 9, strong = false, color = black) => {
      for (const part of wrap(value)) {
        if (y < 48) { page = doc.addPage(pageSize); y = pageSize[1] - 42 }
        page.drawText(part, { x: 42, y, size, font: strong ? bold : regular, color }); y -= size + 5
      }
    }
    line(`PARTE DIARIO  ${report.report_code}`, 16, true, green)
    line(`Fecha: ${report.report_date}     Orden: ${report.service_order || '-'}     Estado: ${report.document_status}`, 9)
    for (const [index, task] of (report.report_tasks ?? []).entries()) {
      y -= 7; page.drawLine({ start: { x: 42, y }, end: { x: pageSize[0] - 42, y }, thickness: 0.7, color: black }); y -= 16
      line(`${index + 1}. ${task.lots?.lot_code ?? task.lot_id}  |  ${task.operations?.name ?? task.operation_code}`, 12, true, green)
      line(`Cantidad: ${task.quantity} ${task.work_cycles?.unit ?? task.operations?.unit ?? ''}     Ciclo: ${task.work_cycles?.cycle_no ?? '-'}     Objetivo: ${task.work_cycles?.target_available === false ? 'Sin dato' : task.work_cycles?.target_quantity ?? 'Sin dato'}`, 9)
      line(`Centro de costo sugerido: ${task.cost_center_context?.suggested?.id || '-'} ${task.cost_center_context?.suggested?.name || ''}     Elegido: ${task.cost_center_context?.selected?.id || '-'} ${task.cost_center_context?.selected?.name || ''}`, 8)
      if (task.notes) line(`Observaciones: ${task.notes}`, 9)
      line('PERSONAL Y MAQUINARIA', 9, true)
      for (const row of task.allocations ?? []) line(`${row.personnel?.full_name ?? row.personnel_code} | ${row.attendance} | ${row.quantity} | ${row.machines?.brand ?? ''} ${row.machines?.model ?? ''} | ${row.person_hours} h`, 8)
      line('INSUMOS', 9, true)
      for (const row of task.part_inputs ?? []) line(`${row.inputs?.description ?? row.input_code} | ${row.quantity} ${row.unit} | dosis ${row.dose}`, 8)
    }
    line(`Documento ${report.report_code} · generado para la versión ${report.pdf_version ?? 1}`, 7, false, green)
    await doc.attach(new TextEncoder().encode(json), 'parte_diario_v1.json', { mimeType: 'application/json', description: 'Datos estructurados del parte, esquema asistente-parte-diario v1' })
    const bytes = await doc.save()
    if (bytes.byteLength > 30 * 1024 * 1024) throw new Error('El PDF supera el límite de 30 MB.')
    return new File([bytes], `${report.report_code}.pdf`, { type: 'application/pdf' })
  }

  async function downloadReportPdf(report: ReportRow) {
    try {
      const file = await buildReportPdf(report); const url = URL.createObjectURL(file); const anchor = document.createElement('a')
      anchor.href = url; anchor.download = file.name; anchor.click(); URL.revokeObjectURL(url)
    } catch (error) { setNotice({ kind: 'error', text: `No se pudo generar el PDF: ${errorText(error)}` }) }
  }

  async function shareReportPdf(report: ReportRow) {
    try {
      const file = await buildReportPdf(report)
      if (navigator.canShare?.({ files: [file] })) await navigator.share({ files: [file], title: `Parte ${report.report_code}` })
      else { await downloadReportPdf(report); setNotice({ kind: 'success', text: 'Este dispositivo no ofrece compartir archivos; se descargó el PDF como alternativa.' }) }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') return
      setNotice({ kind: 'error', text: `No se pudo compartir el PDF: ${errorText(error)}` })
    }
  }

  async function reviewReport(report: ReportRow) {
    if (!supabase || appRole !== 'administrador') return
    if (!window.confirm(`¿Guardar una instantánea de revisión y habilitar el PDF de ${report.report_code}?`)) return
    const { error } = await supabase.rpc('review_daily_report', { p_report_id: report.id })
    if (error) setNotice({ kind: 'error', text: `No se pudo revisar el parte: ${error.message}` })
    else { setNotice({ kind: 'success', text: 'Revisión guardada. El número de versión del PDF fue actualizado.' }); await loadReports() }
  }

  async function saveReportCorrection() {
    if (!supabase || appRole !== 'administrador' || !correctionDraft) return
    const report = correctionDraft
    const tasks = (report.report_tasks ?? []).map((task: ReportRow) => ({
      task_id: task.id,
      quantity: Number(task.quantity),
      crop: task.crop ?? '',
      notes: task.notes ?? '',
      cost_center_context: task.cost_center_context ?? {},
      allocations: (task.allocations ?? []).map((row: ReportRow) => ({
        allocation_id: row.id, personnel_code: row.personnel_code, machine_code: row.machine_code ?? '',
        attendance: row.attendance, quantity: Number(row.quantity), replacement_code: row.replacement_code ?? '',
        front_id: row.front_id ?? task.front_id, person_hours: Number(row.person_hours),
        machine_start_time: row.machine_start_time, machine_end_time: row.machine_end_time,
      })),
      inputs: (task.part_inputs ?? []).map((row: ReportRow) => ({
        input_id: row.id, input_code: row.input_code, dose: Number(row.dose), quantity: Number(row.quantity), unit: row.unit,
      })),
    }))
    if (!window.confirm(`¿Guardar la corrección atómica de ${report.report_code}? Se conservará una instantánea completa y deberá revisarse de nuevo antes de generar/compartir el PDF vigente.`)) return
    setLoading(true)
    const correctionPayload = { p_report_id: report.id, p_report_date: report.report_date, p_service_order: report.service_order ?? '', p_tasks: tasks }
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(correctionPayload)))
    const fingerprint = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, '0')).join('').slice(0, 32)
    const correctionKey = `${fingerprint.slice(0, 8)}-${fingerprint.slice(8, 12)}-5${fingerprint.slice(13, 16)}-a${fingerprint.slice(17, 20)}-${fingerprint.slice(20, 32)}`
    const { error } = await supabase.rpc('correct_daily_report', {
      ...correctionPayload,
      p_correction_key: correctionKey,
    })
    setLoading(false)
    if (error) setNotice({ kind: 'error', text: `No se pudo corregir el parte: ${error.message}` })
    else { setCorrectionDraft(null); setNotice({ kind: 'success', text: 'Corrección guardada en una transacción. El PDF anterior quedó invalidado; el parte requiere una nueva revisión.' }); await loadReports() }
  }

  async function confirmReportSent(report: ReportRow) {
    if (!supabase || !window.confirm(`¿Confirmás que ${report.report_code} ya fue enviado por ${sentVia}${sentTo.trim() ? ` a ${sentTo.trim()}` : ''}? Esta acción cambia el estado documental.`)) return
    const { error } = await supabase.rpc('confirm_daily_report_sent', { p_report_id: report.id, p_sent_to: sentTo.trim(), p_sent_via: sentVia.trim() })
    if (error) setNotice({ kind: 'error', text: `No se pudo registrar el envío: ${error.message}` })
    else { setNotice({ kind: 'success', text: 'Envío confirmado y registrado.' }); setSentTo(''); await loadReports() }
  }

  function patchCorrectionTask(taskId: string, patch: ReportRow) {
    setCorrectionDraft((current) => current && ({ ...current, report_tasks: current.report_tasks.map((task: ReportRow) => task.id === taskId ? { ...task, ...patch } : task) }))
  }

  function patchCorrectionRow(taskId: string, collection: 'allocations' | 'part_inputs', rowId: string, patch: ReportRow) {
    setCorrectionDraft((current) => current && ({ ...current, report_tasks: current.report_tasks.map((task: ReportRow) => task.id === taskId ? { ...task, [collection]: task[collection].map((row: ReportRow) => row.id === rowId ? { ...row, ...patch } : row) } : task) }))
  }

  if (!hasSupabaseConfig) return <main className="setup-screen"><section className="setup-card"><div className="brand-mark"><Leaf size={22} /></div><span className="eyebrow">ASISTENTE DE CAMPO</span><h1>Configurá la conexión</h1><p>Copiá <code>.env.example</code> como <code>.env.local</code> y agregá la URL del proyecto Supabase y la clave publicable.</p><p className="muted">La clave secreta del proyecto nunca debe configurarse en esta aplicación.</p></section></main>

  if (!sessionReady) return <main className="setup-screen"><div className="loading-label"><RefreshCw className="spin" size={18} /> Verificando sesión…</div></main>

  if (!session) return <main className="setup-screen"><section className="setup-card login-card"><div className="brand-mark"><Leaf size={22} /></div><span className="eyebrow">ASISTENTE DE CAMPO</span><h1>Partes Diarios</h1><p>Iniciá sesión para consultar los catálogos y cargar un parte.</p>
    <form onSubmit={signIn} className="stack-form"><label>Correo electrónico<input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Contraseña<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label><button className="primary-button" disabled={loading}>{loading ? 'Ingresando…' : 'Iniciar sesión'}</button></form>
    {notice && <p className={`notice ${notice.kind}`} role="status">{notice.text}</p>}<p className="muted">Las cuentas se habilitan desde el proyecto Supabase.</p></section></main>

  const hasMasterCatalogs = catalogs.farms.length > 0 && catalogs.lots.length > 0 && catalogs.operations.length > 0 && catalogs.personnel.length > 0
  const hasFronts = catalogs.fronts.length > 0
  return <main className="app-shell">
    <aside className="sidebar"><a className="brand" href="#inicio"><span className="brand-mark"><Leaf size={21} /></span><span><strong>Parte diario</strong><small>Gestión de tareas agrícolas</small></span></a><nav aria-label="Secciones"><button className={`nav-link ${section === 'report' ? 'active' : ''}`} onClick={() => setSection('report')}>Cargar parte</button><button className={`nav-link ${section === 'reports' ? 'active' : ''}`} onClick={() => { setSelectedReport(null); setSection('reports') }}>Partes y avance</button><button className={`nav-link ${section === 'fronts' ? 'active' : ''}`} onClick={() => setSection('fronts')}>Frentes</button></nav><div className="sidebar-note"><Cloud size={17} /><span>Conectado a Supabase<br /><b>Sincronización en línea</b></span></div></aside>
    <section className="workspace" id="inicio"><header className="topbar"><div><span className="eyebrow">{selectedFront ? `FRENTE · ${selectedFront.name}` : 'ASISTENTE DE CAMPO'}</span><h1>{section === 'report' ? 'Cargar parte' : section === 'reports' ? 'Partes y avance' : 'Frentes'}</h1></div><div className="account-actions"><span className="user-email">{session.user.email}</span><button className="icon-button" onClick={section === 'reports' ? loadReports : loadCatalogs} title="Actualizar datos" disabled={loading}><RefreshCw size={17} /></button><button className="icon-button" onClick={signOut} title="Cerrar sesión"><LogOut size={17} /></button></div></header>
      {section === 'report' && <section className="intro-card"><div><span className="eyebrow">REGISTRO DE TRABAJO</span><h2>Una carga simple para empezar.</h2><p>Seleccioná el lote, la tarea, el frente y la cantidad. El detalle se distribuye entre las personas elegidas.</p></div><div className="intro-icon"><Sprout size={34} /></div></section>}
      {notice && <div className={`notice ${notice.kind}`} role="status">{notice.text}{savedReport && <span className="saved-code">{savedReport.report_code}</span>}</div>}
      {section === 'reports' && <section className="reports-panel"><div className="section-heading"><span>↗</span><div><h2>Partes visibles para tu cuenta</h2><p>Los resultados se consultan con tu sesión y las políticas RLS activas.</p></div></div><div className="report-filters"><label>Buscar por ID, finca, lote, tarea, insumo o usuario<input type="search" value={reportSearch} onChange={(event) => setReportSearch(event.target.value)} placeholder="Código de parte, nombre o legajo" /></label><label>Desde<input type="date" value={reportFrom} onChange={(event) => setReportFrom(event.target.value)} /></label><label>Hasta<input type="date" value={reportTo} onChange={(event) => setReportTo(event.target.value)} /></label></div>{selectedReport ? <article className="report-detail"><div className="front-editor-heading"><div><h2>{selectedReport.report_code}</h2><p>{selectedReport.report_date} · Orden {selectedReport.service_order || '—'} · {selectedReport.document_status}</p></div><button className="secondary-button" onClick={() => { setSelectedReport(null); setCorrectionDraft(null) }}>Volver a resultados</button></div>{correctionDraft && <section className="report-task-detail"><h3>Corrección de {correctionDraft.report_code}</h3><p>Se conserva el mismo conjunto de tareas, personas e insumos. El guardado es atómico y crea una instantánea previa.</p><div className="field-grid two"><label>Fecha<input type="date" value={correctionDraft.report_date} onChange={(event) => setCorrectionDraft({ ...correctionDraft, report_date: event.target.value })} /></label><label>Orden de servicio<input value={correctionDraft.service_order ?? ''} onChange={(event) => setCorrectionDraft({ ...correctionDraft, service_order: event.target.value })} /></label></div>{correctionDraft.report_tasks.map((task: ReportRow, index: number) => <section className="report-task-detail" key={task.id}><h4>{index + 1}. {task.lots?.lot_code} · {task.operations?.name}</h4><div className="field-grid two"><label>Cantidad<input type="number" min={(task.work_cycles?.unit ?? task.operations?.unit ?? '').toUpperCase() === 'SC' ? '1' : '0.001'} step={(task.work_cycles?.unit ?? task.operations?.unit ?? '').toUpperCase() === 'SC' ? '1' : '0.001'} value={task.quantity} onChange={(event) => patchCorrectionTask(task.id, { quantity: event.target.value })} /></label><label>Cultivo<input value={task.crop ?? ''} onChange={(event) => patchCorrectionTask(task.id, { crop: event.target.value })} /></label><label className="full-field">Observaciones<textarea rows={2} value={task.notes ?? ''} onChange={(event) => patchCorrectionTask(task.id, { notes: event.target.value })} /></label></div><h5>Personal y maquinaria</h5>{(task.allocations ?? []).map((row: ReportRow) => <div className="field-grid two" key={row.id}><label>Persona<select value={row.personnel_code} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { personnel_code: event.target.value })}>{catalogs.personnel.map((person) => <option key={person.employee_code} value={person.employee_code}>{person.employee_code} · {person.full_name}</option>)}</select></label><label>Estado<select value={row.attendance} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { attendance: event.target.value, quantity: event.target.value === 'Ausente' ? 0 : row.quantity })}><option>Presente</option><option>Ausente</option><option>Cantidad fija</option></select></label><label>Cantidad<input type="number" min="0" step="0.001" disabled={row.attendance === 'Ausente'} value={row.quantity} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { quantity: event.target.value })} /></label><label>Reemplazo<input list={`replacement-${row.id}`} value={row.replacement_code ?? ''} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { replacement_code: event.target.value })} /><datalist id={`replacement-${row.id}`}>{catalogs.personnel.map((person) => <option key={person.employee_code} value={person.employee_code}>{person.full_name}</option>)}</datalist></label><label>Horas<input type="number" min="0" max="48" step="0.25" value={row.person_hours} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { person_hours: event.target.value })} /></label><label>Máquina<select value={row.machine_code ?? ''} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { machine_code: event.target.value })}><option value="">Sin maquinaria</option>{catalogs.machines.map((machine) => <option key={machine.machine_code} value={machine.machine_code}>{machine.machine_code} · {machine.brand} {machine.model}</option>)}</select></label><label>Lectura inicial<input type="number" min="0" step="1" value={row.machine_start_time ?? ''} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { machine_start_time: event.target.value || null })} /></label><label>Lectura final<input type="number" min="0" step="1" value={row.machine_end_time ?? ''} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { machine_end_time: event.target.value || null })} /></label></div>)}<h5>Insumos</h5>{(task.part_inputs ?? []).map((row: ReportRow) => <div className="field-grid two" key={row.id}><label>Producto<select value={row.input_code} onChange={(event) => patchCorrectionRow(task.id, 'part_inputs', row.id, { input_code: event.target.value })}>{catalogs.inputs.map((input) => <option key={input.input_code} value={input.input_code}>{input.description}</option>)}</select></label><label>Dosis<input type="number" min="0" step="0.001" value={row.dose} onChange={(event) => patchCorrectionRow(task.id, 'part_inputs', row.id, { dose: event.target.value })} /></label><label>Consumo<input type="number" min="0" step="0.001" value={row.quantity} onChange={(event) => patchCorrectionRow(task.id, 'part_inputs', row.id, { quantity: event.target.value })} /></label><label>Unidad<input value={row.unit} onChange={(event) => patchCorrectionRow(task.id, 'part_inputs', row.id, { unit: event.target.value })} /></label></div>)}</section>)}<div className="form-actions"><button className="secondary-button" onClick={() => setCorrectionDraft(null)}>Cancelar</button><button className="primary-button" disabled={loading} onClick={() => void saveReportCorrection()}>{loading ? 'Guardando…' : 'Guardar corrección'}</button></div></section>}
      {(selectedReport.report_tasks ?? []).map((task: ReportRow, index: number) => <section className="report-task-detail" key={task.id}><h3>{index + 1}. {task.lots?.lot_code} · {task.operations?.name}</h3><p>{task.quantity} {task.work_cycles?.unit ?? task.operations?.unit} · Ciclo {task.work_cycles?.cycle_no} · Objetivo {task.work_cycles?.target_available === false ? 'Sin dato' : task.work_cycles?.target_quantity ?? 'Sin dato'} · Acumulado {cycleTotals[task.work_cycle_id] ?? 'calculando'} · Saldo {task.work_cycles?.target_available !== false && task.work_cycles?.target_quantity ? Math.max(0, Number(task.work_cycles.target_quantity) - (cycleTotals[task.work_cycle_id] ?? 0)) : 'Sin dato'}</p><p>Centro sugerido {task.cost_center_context?.suggested?.id || '—'} · elegido {task.cost_center_context?.selected?.id || '—'} {task.cost_center_context?.changed ? '· cambio manual' : ''}</p><h4>Personal y maquinaria</h4><ul>{(task.allocations ?? []).map((row: ReportRow, i: number) => <li key={`${row.personnel_code}-${i}`}>{row.personnel?.full_name} · {row.attendance} · {row.quantity} · {row.machines?.brand} {row.machines?.model} · {row.person_hours} h</li>)}</ul><h4>Insumos</h4><ul>{(task.part_inputs ?? []).map((row: ReportRow) => <li key={row.input_code}>{row.inputs?.description} · {row.quantity} {row.unit} · dosis {row.dose}</li>)}</ul></section>)}<div className="form-actions report-document-actions">{appRole === 'administrador' && !['Revisado','Enviado'].includes(selectedReport.document_status) && <button className="secondary-button" onClick={() => void reviewReport(selectedReport)}>Guardar revisión</button>}{appRole === 'administrador' && selectedReport.document_status !== 'Borrador' && !correctionDraft && <button className="secondary-button" onClick={() => setCorrectionDraft(structuredClone(selectedReport))}>Corregir parte</button>}<button className="secondary-button" disabled={!['Revisado','Enviado'].includes(selectedReport.document_status)} onClick={() => void downloadReportPdf(selectedReport)}>Descargar PDF con JSON adjunto</button><button className="secondary-button" disabled={!['Revisado','Enviado'].includes(selectedReport.document_status)} onClick={() => void shareReportPdf(selectedReport)}>Compartir PDF</button><button className="secondary-button" onClick={() => downloadReportExchange(selectedReport)}>Exportar JSON</button></div>{selectedReport.document_status === 'Revisado' && (selectedReport.created_by === session.user.id || appRole === 'administrador') && <div className="send-confirm"><label>Destinatario (opcional)<input value={sentTo} onChange={(event) => setSentTo(event.target.value)} /></label><label>Canal<select value={sentVia} onChange={(event) => setSentVia(event.target.value)}><option>WhatsApp</option><option>Correo</option><option>Otro</option></select></label><button className="primary-button" onClick={() => void confirmReportSent(selectedReport)}>Confirmar envío realizado</button><small>Confirmá solo después de compartir o enviar el PDF.</small></div>}<p className="helper-text">Preparar, descargar o compartir no registra un envío. Revisar y confirmar envío son acciones separadas.</p></article> : <>{loading ? <div className="loading-label">Cargando partes…</div> : filteredReports.length === 0 ? <p className="empty-state">No hay partes que coincidan con los filtros.</p> : <div className="report-results">{filteredReports.map((report) => <button className="report-result" key={report.id} onClick={() => setSelectedReport(report)}><strong>{report.report_code}</strong><span>{report.report_date} · {report.document_status} · {(report.report_tasks ?? []).length} tareas</span><small>{(report.report_tasks ?? []).map((task: ReportRow) => `${task.lots?.lot_code ?? task.lot_id} · ${task.operations?.name ?? task.operation_code}`).join(' / ')}</small></button>)}</div>}</>}</section>}
      {section === 'report' && !hasMasterCatalogs && !loading && <section className="empty-state"><h2>Faltan datos maestros</h2><p>La conexión funciona, pero aún faltan fincas, lotes, tareas o personal activos. Revisá los catálogos en Supabase y actualizá esta pantalla.</p><button className="secondary-button" onClick={loadCatalogs}>Actualizar catálogos</button></section>}
      {section === 'fronts' && <section className="fronts-panel">
        <div className="section-heading"><span><Users size={16} /></span><div><h2>Administración de frentes</h2><p>Creá frentes y asigná personal con su maquinaria habitual.</p></div></div>
        <form className="new-front-form" onSubmit={createFront}><label>Nuevo frente<input required maxLength={120} value={newFrontName} onChange={(event) => setNewFrontName(event.target.value)} placeholder="Nombre del frente" /></label><button className="primary-button" disabled={loading}><Plus size={15} /> Crear frente</button></form>
        {manageableFronts.length > 0 ? <label className="front-picker">Frente a administrar<select value={manageFrontId} onChange={(event) => setManageFrontId(event.target.value)}><option value="">Seleccionar frente</option>{manageableFronts.map((front) => <option key={front.id} value={front.id}>{front.name}</option>)}</select></label> : <p className="helper-text">Todavía no tenés frentes propios. Los frentes compartidos aparecen en Cargar parte.</p>}
        {manageFront && <form className="front-editor" onSubmit={saveFront}><div className="front-editor-heading"><div><h3>{manageFront.name}</h3><p>Los cambios se aplican al guardar.</p></div><button className="secondary-button danger-button" type="button" disabled={loading} onClick={deactivateFront}>Desactivar</button></div><label>Nombre del frente<input required maxLength={120} value={manageFrontName} onChange={(event) => setManageFrontName(event.target.value)} /></label><label className="front-picker">Tarea del frente<select required value={manageOperationCode} onChange={(event) => { setManageOperationCode(event.target.value); setFrontPeopleSearch('') }}><option value="">Seleccionar tarea</option>{catalogs.operations.map((operation) => <option key={operation.operation_code} value={operation.operation_code}>{operation.operation_code} · {operation.name}</option>)}</select></label><h3>Equipo para esta tarea <small>{selectedManageMembers.length} {selectedManageMembers.length === 1 ? 'integrante' : 'integrantes'} · {manageMachines.length} máquinas compatibles</small></h3>
          <label className="front-search">Buscar personal<input type="search" value={frontPeopleSearch} onChange={(event) => setFrontPeopleSearch(event.target.value)} placeholder="Nombre o legajo" /></label>
          <div className="front-person-list">{matchingManagePeople.map((person) => { const assignedMember = selectedManageMembers.find((member) => member.personnel_code === person.employee_code); const assigned = Boolean(assignedMember); return <div className="front-person-row" key={person.employee_code}><label className="person-option"><input type="checkbox" checked={assigned} onChange={(event) => setFrontTaskMembers((current) => { const remaining = current.filter((member) => !(member.operation_code === manageOperationCode && member.personnel_code === person.employee_code)); return event.target.checked ? [...remaining, { operation_code: manageOperationCode, personnel_code: person.employee_code, machine_code: null }] : remaining })} /><span>{person.full_name}<small>Legajo {person.employee_code}</small></span></label>{assigned && <MachinePicker label={`Maquinaria habitual de ${person.full_name}`} disabled={manageOperation?.task_type === 'Manual'} machines={manageMachines} value={assignedMember?.machine_code ?? ''} onChange={(machineCode) => setFrontTaskMembers((current) => current.map((member) => member.operation_code === manageOperationCode && member.personnel_code === person.employee_code ? { ...member, machine_code: machineCode || null } : member))} />}</div> })}</div>
          <div className="form-actions"><span>El equipo queda disponible al cargar un parte con este frente.</span><button className="primary-button" disabled={loading || !manageFrontName.trim()}><Save size={15} /> Guardar frente</button></div></form>}
      </section>}
      {section === 'report' && hasMasterCatalogs && !hasFronts && !loading && <section className="empty-state"><h2>Los maestros están listos; falta un frente</h2><p>No hay frentes activos disponibles. Creá uno y asignale personal para empezar a cargar partes.</p><button className="secondary-button" onClick={() => setSection('fronts')}>Administrar frentes</button></section>}
      {loading && !hasMasterCatalogs && <div className="loading-label"><RefreshCw className="spin" size={18} /> Cargando datos…</div>}
      {section === 'report' && hasMasterCatalogs && hasFronts && <form className="report-form" id="cargar" onSubmit={saveReport}>
        <section className="form-section"><div className="section-heading"><span>JSON</span><div><h2>Importar un parte</h2><p>Validá el contenido antes de incorporarlo al borrador local.</p></div></div><label>Archivo JSON<input type="file" accept="application/json,.json" disabled={draftTasks.length > 0} onChange={(event) => { void previewExchangeFile(event.currentTarget.files?.[0]); event.currentTarget.value = '' }} /></label>{draftTasks.length > 0 && <small>Guardá o descartá el borrador actual antes de importar.</small>}{exchangePreview && <div className="draft-review"><h3>Vista previa · {exchangePreview.tasks.length} tareas</h3><label>Frente que se asignará a la importación<select value={frontId} onChange={(event) => setFrontId(event.target.value)}><option value="">Seleccionar frente</option>{catalogs.fronts.map((front) => <option key={front.id} value={front.id}>{front.name}</option>)}</select></label><ul>{exchangePreview.labels.map((label, index) => <li key={`${label}-${index}`}>{label}</li>)}</ul><p>Fecha {exchangePreview.report_date} · Orden {exchangePreview.service_order || '—'}. La confirmación solo crea un borrador editable en esta pantalla.</p><div className="form-actions"><button type="button" className="secondary-button" onClick={() => setExchangePreview(null)}>Cancelar</button><button type="button" className="primary-button" disabled={!frontId} onClick={acceptExchangePreview}>Aceptar vista previa</button></div></div>}</section>
        {draftTasks.length > 0 && <section className="form-section draft-review"><div className="section-heading"><span>{draftTasks.length}</span><div><h2>Borrador del parte</h2><p>Las tareas comparten la fecha {reportDate}. Revisá el conjunto antes de guardar.</p></div><button className="secondary-button danger-button" type="button" onClick={discardDraft}>Descartar</button></div><ul>{draftTasks.map((task, index) => { const lot = catalogs.lots.find((item) => item.id === task.lot_id); const operation = catalogs.operations.find((item) => item.operation_code === task.operation_code); return <li key={`${task.lot_id}-${task.operation_code}`}><span><b>{index + 1}. {lot?.lot_code}</b> · {operation?.name} · {String(task.quantity)} {String(task.unit)}</span><button type="button" className="text-button" onClick={() => { setDraftTasks((items) => items.filter((_, itemIndex) => itemIndex !== index)); setDraftIdempotencyKey(''); setDraftFingerprint('') }}>Quitar</button></li> })}</ul><button type="button" className="primary-button" disabled={loading} onClick={() => void submitDraft()}>{loading ? 'Guardando…' : `Guardar parte completo (${draftTasks.length} tarea${draftTasks.length === 1 ? '' : 's'})`}</button></section>}
        <section className="form-section"><div className="section-heading"><span>01</span><div><h2>Datos del parte</h2><p>Fecha y número de orden, si corresponde.</p></div></div><div className="field-grid two"><label>Fecha<input type="date" required value={reportDate} disabled={draftTasks.length > 0} onChange={(e) => setReportDate(e.target.value)} /></label><label>Orden de servicio <small>Opcional</small><input value={serviceOrder} onChange={(e) => setServiceOrder(e.target.value)} placeholder="Número de orden" /></label></div></section>
        <section className="form-section"><div className="section-heading"><span>02</span><div><h2>Lote y tarea</h2><p>El avance se acumula en el ciclo abierto del lote y la operación.</p></div></div><div className="field-grid two"><label>Finca<select required value={farmId} onChange={(e) => { setFarmId(e.target.value); setLotId('') }}><option value="">Seleccionar finca</option>{catalogs.farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}</select></label><label>Lote<select required value={lotId} onChange={(e) => { setLotId(e.target.value); setChosenCostCenter('') }} disabled={!farmId}><option value="">Seleccionar lote</option>{visibleLots.map((lot) => <option key={lot.id} value={lot.id}>{lot.lot_code} · {lot.lot_name || lot.crop}</option>)}</select></label>
          {selectedLot && <><label>Centro de costo<select required={catalogs.costCenters.length > 0} value={effectiveCostCenter} onChange={(e) => { setChosenCostCenter(e.target.value); setGroupCode('') }}><option value="">Elegir centro de costo</option>{catalogs.costCenters.map((center) => <option key={center.cost_center_id} value={center.cost_center_id}>{center.cost_center_id} · {center.name}</option>)}</select>{catalogs.costCenters.length === 0 && <small>El catálogo V1.1 aún no está sincronizado; esta tarea guardará el contexto de centro vacío.</small>}<small>Centro sugerido por ubicación: {selectedLot.suggested_cost_center_id ? `${selectedLot.suggested_cost_center_id} · ${selectedLot.suggested_cost_center_name}` : 'Sin correspondencia; elegí uno manualmente.'}</small>{selectedLot.suggested_cost_center_id && effectiveCostCenter !== selectedLot.suggested_cost_center_id && <small className="helper-text">Aviso: el centro seleccionado difiere del sugerido. La elección quedará registrada en esta tarea.</small>}</label>{effectiveCostCenter && visibleOperationGroups.length > 0 && <label>Grupo de operación<select required value={groupCode} onChange={(e) => setGroupCode(e.target.value)}><option value="">Seleccionar grupo</option>{visibleOperationGroups.map((group) => <option key={group.group_code} value={group.group_code}>{group.group_code} · {group.name}</option>)}</select></label>}<div className="allocation-hint"><span>Datos agronómicos</span><strong>{selectedLot.agronomic_data_available ? 'Disponibles' : 'Incompletos'}</strong><small>{selectedLot.agronomic_data_available ? `Superficie neta: ${selectedLot.net_area ?? 'sin dato'} ha · Surcos: ${selectedLot.furrows ?? 'sin dato'}` : 'Se puede continuar; no se generan objetivos derivados.'}</small></div></>}
          <label>Tarea<select required value={operationCode} onChange={(e) => { setOperationCode(e.target.value); setQuantity(''); setSelectedPeople([]); setMemberMachines({}); setAllocationDrafts({}); setInputLines([]) }}><option value="">Seleccionar tarea</option>{allowedOperations.map((operation) => <option key={operation.operation_code} value={operation.operation_code}>{operation.operation_code} · {operation.name}</option>)}</select>{effectiveCostCenter && catalogs.groups.length > 0 && <small>Filtrada por grupos habilitados para el centro.</small>}</label>{['SC', 'HA', 'TN'].includes(currentUnit.toUpperCase()) && <label>Modo de carga<select value={allocationMode} onChange={(event) => { setAllocationMode(event.target.value); if (event.target.value === 'Cantidad individual') setQuantity('') }}><option value="Total a repartir">Ingresar un total para repartir</option><option value="Cantidad individual">Cantidad por persona (destajo)</option></select><small>Elegí si distribuís un total o cargás lo realizado por cada persona.</small></label>}{allocationMode === 'Total a repartir' && <label>Cantidad total realizada <small>{currentUnit || 'Unidad'}</small><input type="number" inputMode="decimal" min={currentUnit.toUpperCase() === 'SC' ? '1' : '0.001'} step={currentUnit.toUpperCase() === 'SC' ? '1' : '0.001'} required value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="0" /></label>}{allocationMode === 'Total a repartir' && <label>Objetivo del lote <small>{openCycle ? 'Del ciclo abierto' : 'Sugerido por datos agronómicos'}</small><input type="number" min="0" step={currentUnit.toUpperCase() === 'SC' ? '1' : '0.001'} value={targetQuantity} onChange={(e) => setTargetQuantity(e.target.value)} readOnly={Boolean(openCycle)} placeholder="Sin dato" /></label>}<div className="allocation-hint"><span>Distribución</span><strong>{allocationMode}</strong>{openCycle && <small>Parte del avance registrado de este lote y tarea.</small>}</div></div></section>
        <section className="form-section"><div className="section-heading"><span>03</span><div><h2>Frente y personal</h2><p>El personal y las máquinas se configuran por tarea dentro de cada frente.</p></div></div><div className="field-grid two"><label>Frente<select required value={frontId} onChange={(e) => setFrontId(e.target.value)}><option value="">Seleccionar frente</option>{catalogs.fronts.map((front) => <option key={front.id} value={front.id}>{front.name}</option>)}</select></label></div>
          {!operationCode && <p className="helper-text">Elegí la tarea para ver los frentes y su equipo configurado.</p>}{operationCode && !frontId && <p className="helper-text">Elegí un frente para ver el personal de esta tarea.</p>}{frontId && eligiblePeople.length === 0 && <p className="helper-text">Este frente no tiene personal configurado para la tarea elegida. Configuralo en Frentes.</p>}{eligiblePeople.length > 0 && <div className="report-member-list">{eligiblePeople.map((person) => { const assignedMachine = memberMachines[person.employee_code] ?? ''; const checked = selectedPeople.includes(person.employee_code); const detail = allocationDrafts[person.employee_code] ?? { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: '12', machine_start_time: '', machine_end_time: '' }; const updateDetail = (key: keyof AllocationDraft, value: string) => setAllocationDrafts((current) => ({ ...current, [person.employee_code]: { ...detail, [key]: value } })); return <div className="report-member-row allocation-member-row" key={person.employee_code}><label className="person-option"><input type="checkbox" checked={checked} onChange={(event) => { setSelectedPeople((current) => event.target.checked ? [...current, person.employee_code] : current.filter((code) => code !== person.employee_code)); if (event.target.checked && !Object.hasOwn(memberMachines, person.employee_code)) { const configured = members.find((member) => member.personnel_code === person.employee_code)?.machine_code ?? ''; setMemberMachines((current) => ({ ...current, [person.employee_code]: configured })) } }} /><span>{person.full_name}<small>Legajo {person.employee_code}</small></span></label>{selectedOperation?.task_type !== 'Manual' && <select aria-label={`Máquina de ${person.full_name}`} disabled={!checked} value={assignedMachine} onChange={(event) => setMemberMachines((current) => ({ ...current, [person.employee_code]: event.target.value }))}><option value="">Sin maquinaria</option>{eligibleMachines.map((machine) => <option key={machine.machine_code} value={machine.machine_code}>{machine.machine_code} · {[machine.brand, machine.model].filter(Boolean).join(' ')}</option>)}</select>}{checked && <div className="allocation-person-fields"><label>Estado<select value={detail.attendance} onChange={(event) => updateDetail('attendance', event.target.value)}><option>Presente</option><option>Ausente</option><option>Cantidad fija</option></select></label>{(allocationMode === 'Cantidad individual' || detail.attendance === 'Cantidad fija') && detail.attendance !== 'Ausente' && <label>Cantidad <small>{currentUnit || 'Unidad'}</small><input type="number" min="0" step={currentUnit.toUpperCase() === 'SC' ? '1' : '0.001'} required value={detail.quantity} onChange={(event) => updateDetail('quantity', event.target.value)} /></label>}<label>Reemplaza<input list={`personnel-${person.employee_code}`} value={detail.replacement_code} onChange={(event) => updateDetail('replacement_code', event.target.value)} placeholder="Legajo opcional" /><datalist id={`personnel-${person.employee_code}`}>{catalogs.personnel.filter((item) => item.employee_code !== person.employee_code).map((item) => <option key={item.employee_code} value={item.employee_code}>{item.full_name}</option>)}</datalist></label><label>Horas<input type="number" min="0" max="24" step="0.25" value={detail.person_hours} onChange={(event) => updateDetail('person_hours', event.target.value)} /></label>{assignedMachine && <><label>Lectura inicial<input type="number" min="0" step="1" value={detail.machine_start_time} onChange={(event) => updateDetail('machine_start_time', event.target.value)} /></label><label>Lectura final<input type="number" min="0" step="1" value={detail.machine_end_time} onChange={(event) => updateDetail('machine_end_time', event.target.value)} /></label></>}</div>}</div> })}</div>}</section>
        {selectedOperation?.allows_inputs && <section className="form-section"><div className="section-heading"><span>04</span><div><h2>Insumos</h2><p>Agregá productos, dosis y consumo para esta tarea.</p></div><button className="secondary-button" type="button" disabled={!catalogs.inputs.length} onClick={() => setInputLines((rows) => [...rows, { input_code: '', dose: '', quantity: '', unit: '' }])}>Agregar insumo</button></div>{inputLines.map((line, index) => { const operationInputCodes = catalogs.operationInputs.filter((row) => row.operation_code === operationCode).map((row) => row.input_code); const compatibleInputs = operationInputCodes.length ? catalogs.inputs.filter((input) => operationInputCodes.includes(input.input_code)) : catalogs.inputs; const basisQuantity = completedWorkQuantity; const dose = Number(line.dose); const inputQuantity = Number(line.quantity); const hasBasis = Number.isFinite(basisQuantity) && basisQuantity > 0; const hasDose = line.dose.trim() !== '' && Number.isFinite(dose) && dose >= 0; const hasQuantity = line.quantity.trim() !== '' && Number.isFinite(inputQuantity) && inputQuantity >= 0; const theoretical = hasBasis && hasDose ? calculateInputTotal(basisQuantity, dose, line.unit) : null; const actualDose = hasBasis && hasQuantity ? calculateActualInputDose(inputQuantity, basisQuantity, line.unit) : null; const doseUnit = inputDoseUnit(line.unit); return <div className="field-grid two" key={`input-${index}`} ><label>Producto<select required value={line.input_code} onChange={(event) => { const selected = catalogs.inputs.find((input) => input.input_code === event.target.value); setInputLines((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, input_code: event.target.value, unit: selected?.unit ?? '' } : row)) }}><option value="">Seleccionar insumo</option>{compatibleInputs.map((input) => <option key={input.input_code} value={input.input_code}>{input.description} · {input.input_code}</option>)}</select></label><label>Dosis ({doseUnit} / {currentUnit || 'unidad'})<input type="number" min="0" step="0.001" value={line.dose} onChange={(event) => setInputLines((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, dose: event.target.value } : row))} /></label><label>Consumo real<input type="number" min="0" step="0.001" value={line.quantity} onChange={(event) => setInputLines((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, quantity: event.target.value } : row))} /></label><label>Unidad<input value={line.unit} onChange={(event) => setInputLines((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, unit: event.target.value } : row))} /></label><div className="allocation-hint full-field"><span>Estimación del insumo</span><strong>Consumo teórico: {theoretical === null ? 'Sin objetivo o dosis' : `${formatInputAmount(theoretical)} ${line.unit || 'unidad'}`}</strong><small>{actualDose === null ? (hasBasis ? `Ingresá el consumo real para calcular la dosis aplicada en ${currentUnit || 'la unidad de tarea'}.` : 'Ingresá la cantidad realizada para hacer el cálculo.') : `Dosis real: ${formatInputAmount(actualDose)} ${doseUnit} / ${currentUnit || 'unidad'} · Base realizada: ${formatInputAmount(basisQuantity)} ${currentUnit || 'unidades'}.`}</small></div><button className="text-button" type="button" onClick={() => setInputLines((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}>Quitar insumo</button></div> })}{catalogs.inputs.length === 0 && <p className="helper-text">El catálogo de insumos todavía no está cargado en Supabase.</p>}</section>}
        <section className="form-section"><div className="section-heading"><span>05</span><div><h2>Observaciones</h2><p>Agregá una nota si hace falta.</p></div></div><label className="full-field">Notas<textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Observaciones del trabajo" /></label></section>
        <div className="form-actions"><span>{draftTasks.length ? 'La tarea se agregará al borrador compartido.' : 'Armá una o más tareas y guardá el documento completo.'}</span><button className="primary-button" disabled={loading || !selectedFront || !selectedLot || !selectedOperation}>{loading ? 'Agregando…' : 'Agregar tarea al borrador'}</button></div>
      </form>}
      <footer>Asistente de parte diario <span>·</span> Versión de trabajo</footer>
    </section>
  </main>
}
