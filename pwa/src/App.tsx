import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { ArrowUp, ChevronDown, ChevronsLeft, ChevronsRight, ClipboardList, Cloud, Folder, Leaf, LogOut, Plus, RefreshCw, Save, Settings, Sprout, Users } from 'lucide-react'
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
type FrontTaskMemberRow = FrontTaskMember & { front_id: string }
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

function distributeTaskQuantity(total: number, people: string[], details: AllocationDraft[], integers: boolean) {
  const fixedTotal = details.reduce((sum, detail) => sum + (detail.attendance === 'Cantidad fija' ? Number(detail.quantity || 0) : 0), 0)
  const presentCount = details.filter((detail) => detail.attendance === 'Presente').length
  const remaining = Math.max(0, total - fixedTotal)
  const share = presentCount ? remaining / presentCount : 0
  const base = integers ? Math.floor(share) : Math.floor(share * 10000) / 10000
  const precision = integers ? 1 : 10000
  const extraShares = Math.max(0, Math.round((remaining - base * presentCount) * precision))
  let presentIndex = 0
  const result: Record<string, number> = {}
  people.forEach((personCode, index) => {
    const detail = details[index]
    if (detail.attendance === 'Ausente') result[personCode] = 0
    else if (detail.attendance === 'Cantidad fija') result[personCode] = Number(detail.quantity || 0)
    else {
      result[personCode] = base + (presentIndex < extraShares ? 1 / precision : 0)
      presentIndex += 1
    }
  })
  return result
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
  const [frontTaskCatalog, setFrontTaskCatalog] = useState<FrontTaskMemberRow[]>([])
  const [memberMachines, setMemberMachines] = useState<Record<string, string>>({})
  const [allocationDrafts, setAllocationDrafts] = useState<Record<string, AllocationDraft>>({})
  const [frontTaskMembers, setFrontTaskMembers] = useState<FrontTaskMember[]>([])
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [reportDate, setReportDate] = useState(today)
  const [farmId, setFarmId] = useState('')
  const [lotId, setLotId] = useState('')
  const [operationCode, setOperationCode] = useState('')
  const [frontId, setFrontId] = useState('')
  const [targetQuantity, setTargetQuantity] = useState('')
  const [quantity, setQuantity] = useState('')
  const [selectedPeople, setSelectedPeople] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [savedReport, setSavedReport] = useState<{ report_code: string } | null>(null)
  const [appRole, setAppRole] = useState('')
  const [chosenCostCenter, setChosenCostCenter] = useState('')
  const [groupCode, setGroupCode] = useState('')
  const [inputLines, setInputLines] = useState<{ input_code: string; dose: string; quantity: string; unit: string }[]>([])
  const [draftTasks, setDraftTasks] = useState<Record<string, unknown>[]>([])
  const [draftIdempotencyKey, setDraftIdempotencyKey] = useState('')
  const [draftFingerprint, setDraftFingerprint] = useState('')
  const [section, setSection] = useState<'reports' | 'fronts' | 'quick' | 'sent'>('reports')
  const [configOpen, setConfigOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [partsView, setPartsView] = useState<'summary' | 'new'>('summary')
  const [newPartStep, setNewPartStep] = useState(1)
  const [frontsView, setFrontsView] = useState<'create' | 'manage'>('create')
  const [manualText, setManualText] = useState('')
  const [defaultPersonHours, setDefaultPersonHours] = useState('12')
  const [whatsappNumber, setWhatsappNumber] = useState('')
  const [whatsappMessage, setWhatsappMessage] = useState('Parte diario {id} · {fecha}')
  const [reports, setReports] = useState<ReportRow[]>([])
  const [reportSearch, setReportSearch] = useState('')
  const [reportFrom, setReportFrom] = useState('')
  const [reportTo, setReportTo] = useState('')
  const [reportFarmFilter, setReportFarmFilter] = useState('Todas')
  const [reportLotFilter, setReportLotFilter] = useState('Todos')
  const [reportOperationFilter, setReportOperationFilter] = useState('Todas')
  const [reportStatusFilter, setReportStatusFilter] = useState('Todos')
  const [reportIdFilter, setReportIdFilter] = useState('')
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
  const [openCycle, setOpenCycle] = useState<{ id: string; target_quantity: number; target_available: boolean; unit: string; cycle_no: number } | null>(null)
  const [cycleAccumulated, setCycleAccumulated] = useState(0)
  const [staffMode, setStaffMode] = useState<'fronts' | 'manual'>('fronts')
  const [includedFrontTasks, setIncludedFrontTasks] = useState<string[]>([])
  const [manualPeopleCodes, setManualPeopleCodes] = useState<string[]>([])
  const [frontTaskPickerOpen, setFrontTaskPickerOpen] = useState(false)
  const [selectedDraftKeys, setSelectedDraftKeys] = useState<string[]>([])
  const [manualFrontId, setManualFrontId] = useState('')
  const [inputSearch, setInputSearch] = useState('')

  useEffect(() => {
    if (!supabase) { setSessionReady(true); return }
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setSessionReady(true) })
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession))
    return () => listener.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) return
    try {
      const saved = JSON.parse(localStorage.getItem(`parte-diario:preferences:${session.user.id}`) || '{}')
      if (saved.defaultPersonHours !== undefined) setDefaultPersonHours(String(saved.defaultPersonHours))
      if (saved.whatsappNumber !== undefined) setWhatsappNumber(String(saved.whatsappNumber))
      if (saved.whatsappMessage !== undefined) setWhatsappMessage(String(saved.whatsappMessage))
      if (saved.whatsappNumber !== undefined) setSentTo(String(saved.whatsappNumber))
    } catch { /* Ignore malformed local preferences and keep defaults. */ }
  }, [session?.user.id])

  useEffect(() => {
    if (!supabase || !frontId || staffMode !== 'fronts') { setFrontTaskCatalog([]); return }
    let cancelled = false
    supabase.from('front_task_members').select('front_id,operation_code,personnel_code,machine_code').eq('front_id', frontId)
      .then(({ data, error }) => {
        if (cancelled) return
        if (error) { setNotice({ kind: 'error', text: `No se pudieron cargar las tareas del frente: ${error.message}` }); setFrontTaskCatalog([]); return }
        const rows = (data ?? []) as FrontTaskMemberRow[]
        setFrontTaskCatalog(rows)
        setIncludedFrontTasks([...new Set(rows.map((row) => row.operation_code))])
      })
    return () => { cancelled = true }
  }, [frontId, staffMode])

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

  useEffect(() => { if (section === 'reports' || section === 'sent') void loadReports() }, [section, loadReports])

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
  const centerAllowedOperations = catalogs.operations.filter((operation) => {
    if (!effectiveCostCenter || catalogs.groups.length === 0) return true
    const groupsForOperation = catalogs.groupOperations.filter((row) => row.operation_code === operation.operation_code).map((row) => row.group_code)
    return groupsForOperation.length === 0 || groupsForOperation.some((group) => permittedGroups.includes(group))
  })
  const allowedOperations = centerAllowedOperations.filter((operation) => {
    if (!effectiveCostCenter || catalogs.groups.length === 0 || !groupCode) return !groupCode
    const groupsForOperation = catalogs.groupOperations.filter((row) => row.operation_code === operation.operation_code).map((row) => row.group_code)
    return groupsForOperation.includes(groupCode) && permittedGroups.includes(groupCode)
  })
  const configuredFrontTaskCodes = [...new Set(frontTaskCatalog.map((member) => member.operation_code))]
  const availableFrontTaskCodes = configuredFrontTaskCodes.filter((code) => centerAllowedOperations.some((operation) => operation.operation_code === code))
  const selectedFrontTaskCodes = availableFrontTaskCodes.filter((code) => includedFrontTasks.includes(code))
  const stagedFrontTaskCodes = draftTasks.filter((task) => task.front_id === frontId).map((task) => String(task.operation_code))
  const completedFrontTaskCodes = selectedFrontTaskCodes.filter((code) => stagedFrontTaskCodes.includes(code))
  const pendingFrontTaskCodes = selectedFrontTaskCodes.filter((code) => !stagedFrontTaskCodes.includes(code))
  const nextFrontTaskCode = pendingFrontTaskCodes[0] ?? ''
  const currentUnit = openCycle?.unit ?? selectedOperation?.unit ?? ''
  const usesSharedTotal = ['SC', 'HA', 'TN'].includes(currentUnit.trim().toUpperCase())
  const allocationMode = usesSharedTotal ? 'Total a repartir' : 'Cantidad individual'
  const completedWorkQuantity = usesSharedTotal
    ? Number(quantity || 0)
    : selectedPeople.reduce((total, personCode) => {
      const detail = allocationDrafts[personCode]
      const amount = Number(detail?.quantity)
      return total + (detail?.attendance !== 'Ausente' && Number.isFinite(amount) ? amount : 0)
    }, 0)
  const allocationPreview = useMemo(() => {
    if (!usesSharedTotal || !quantity.trim() || !Number.isFinite(Number(quantity))) return {}
    const details = selectedPeople.map((personCode) => allocationDrafts[personCode] ?? { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: defaultPersonHours, machine_start_time: '', machine_end_time: '' })
    return distributeTaskQuantity(Number(quantity), selectedPeople, details, currentUnit.trim().toUpperCase() === 'SC')
  }, [usesSharedTotal, quantity, selectedPeople, allocationDrafts, currentUnit])
  const eligiblePeople = catalogs.personnel.filter((person) => staffMode === 'manual' ? manualPeopleCodes.includes(person.employee_code) : members.some((member) => member.personnel_code === person.employee_code) || selectedPeople.includes(person.employee_code))
  useEffect(() => {
    if (staffMode !== 'fronts') return
    setOperationCode(nextFrontTaskCode)
    setGroupCode('')
    setQuantity('')
    setNotes('')
    setInputLines([])
  }, [staffMode, frontId, nextFrontTaskCode])
  const selectedManageMembers = frontTaskMembers.filter((member) => member.operation_code === manageOperationCode)
  const manageOperation = catalogs.operations.find((operation) => operation.operation_code === manageOperationCode)
  const manageMachines = machinesForOperation(manageOperation, catalogs.machines)
  const matchingManagePeople = catalogs.personnel.filter((person) => `${person.full_name} ${person.employee_code}`.toLocaleLowerCase().includes(frontPeopleSearch.trim().toLocaleLowerCase()))
  const frequentInputCodes = useMemo(() => {
    const uses = new Map<string, number>()
    for (const report of reports) for (const task of report.report_tasks ?? []) for (const input of task.part_inputs ?? []) uses.set(input.input_code, (uses.get(input.input_code) ?? 0) + 1)
    const ranked = [...uses.entries()].filter(([code]) => catalogs.inputs.some((item) => item.input_code === code)).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([code]) => code)
    const fallback = [...catalogs.inputs].sort((a, b) => a.description.localeCompare(b.description)).map((item) => item.input_code)
    return [...ranked, ...fallback.filter((code) => !ranked.includes(code))].slice(0, 4)
  }, [reports, catalogs.inputs])
  const visibleFronts = catalogs.fronts.filter((front) => front.id !== manualFrontId && front.name !== 'Carga manual')
  const manageableFronts = visibleFronts.filter((front) => appRole === 'administrador' || front.created_by === session?.user.id)
  const manageFront = manageableFronts.find((front) => front.id === manageFrontId)
  const eligibleMachines = machinesForOperation(selectedOperation, catalogs.machines)
  const filteredReports = useMemo(() => reports.filter((report) => {
    if (section === 'sent' && report.document_status !== 'Enviado') return false
    if (section === 'reports' && report.document_status === 'Enviado') return false
    if (reportFrom && report.report_date < reportFrom) return false
    if (reportTo && report.report_date > reportTo) return false
    if (reportStatusFilter !== 'Todos' && report.document_status !== reportStatusFilter) return false
    const tasks = report.report_tasks ?? []
    const farmNames = tasks.map((task: ReportRow) => catalogs.farms.find((farm) => farm.id === task.lots?.farm_id)?.name).filter(Boolean)
    const lotCodes = tasks.map((task: ReportRow) => task.lots?.lot_code).filter(Boolean)
    const operationNames = tasks.map((task: ReportRow) => task.operations?.name).filter(Boolean)
    if (reportFarmFilter !== 'Todas' && !farmNames.includes(reportFarmFilter)) return false
    if (reportLotFilter !== 'Todos' && !lotCodes.includes(reportLotFilter)) return false
    if (reportOperationFilter !== 'Todas' && !operationNames.includes(reportOperationFilter)) return false
    if (reportIdFilter.trim() && !String(report.report_code).toLocaleLowerCase().includes(reportIdFilter.trim().toLocaleLowerCase())) return false
    const query = reportSearch.trim().toLocaleLowerCase()
    if (!query) return true
    const haystack = [report.report_code, report.service_order, report.created_by, ...tasks.flatMap((task: ReportRow) => [task.lots?.lot_code, task.lots?.lot_name, catalogs.farms.find((farm) => farm.id === task.lots?.farm_id)?.name, task.operations?.name, ...(task.allocations ?? []).map((allocation: ReportRow) => allocation.personnel?.full_name), ...(task.part_inputs ?? []).map((input: ReportRow) => input.inputs?.description)])].filter(Boolean).join(' ').toLocaleLowerCase()
    return haystack.includes(query)
  }), [reports, reportFrom, reportTo, reportSearch, catalogs.farms, section, reportFarmFilter, reportLotFilter, reportOperationFilter, reportStatusFilter, reportIdFilter])
  const reportFarmOptions = [...new Set(reports.flatMap((report) => (report.report_tasks ?? []).map((task: ReportRow) => catalogs.farms.find((farm) => farm.id === task.lots?.farm_id)?.name).filter(Boolean)))].sort()
  const reportLotOptions = [...new Set(reports.flatMap((report) => (report.report_tasks ?? []).map((task: ReportRow) => task.lots?.lot_code).filter(Boolean)))].sort()
  const reportOperationOptions = [...new Set(reports.flatMap((report) => (report.report_tasks ?? []).map((task: ReportRow) => task.operations?.name).filter(Boolean)))].sort()

  function savePreferences() {
    if (!session) return
    try {
      localStorage.setItem(`parte-diario:preferences:${session.user.id}`, JSON.stringify({ defaultPersonHours, whatsappNumber, whatsappMessage }))
      setSentTo(whatsappNumber)
      setNotice({ kind: 'success', text: 'Configuración guardada en este dispositivo.' })
    } catch {
      setNotice({ kind: 'error', text: 'No se pudo guardar la configuración en este dispositivo.' })
    }
  }

  async function ensureManualFront() {
    if (!supabase || !session) throw new Error('Iniciá sesión para continuar.')
    if (manualFrontId) return manualFrontId
    const existing = catalogs.fronts.find((front) => front.name === 'Carga manual')
    if (existing) { setManualFrontId(existing.id); setFrontId(existing.id); return existing.id }
    const { data, error } = await supabase.from('fronts').insert({ name: 'Carga manual', created_by: session.user.id }).select('id,name,created_by,active').single()
    if (error) throw new Error(`No se pudo preparar la carga manual: ${error.message}`)
    setManualFrontId(data.id)
    setFrontId(data.id)
    setCatalogs((current) => ({ ...current, fronts: [...current.fronts, data as Front] }))
    return data.id as string
  }

  async function continueToStaffStep() {
    setNotice(null)
    if (!selectedOperation || !selectedLot || !quantity.trim() || !Number.isFinite(Number(quantity)) || Number(quantity) <= 0) return
    if (staffMode === 'manual') {
      try { await ensureManualFront() }
      catch (error) { setNotice({ kind: 'error', text: errorText(error) }); return }
    }
    setAllocationDrafts((current) => Object.fromEntries(selectedPeople.map((code) => [code, { ...(current[code] ?? { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: defaultPersonHours, machine_start_time: '', machine_end_time: '' }), quantity: current[code]?.quantity || quantity } ])))
    setNewPartStep(3)
  }

  function prepareManualEntry(event: FormEvent) {
    event.preventDefault()
    const raw = manualText.trim()
    if (!raw) { setNotice({ kind: 'error', text: 'Escribí el parte antes de prepararlo.' }); return }
    const normalized = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().trim()
    const text = normalized(raw)
    const unique = <T,>(items: T[]) => items.length === 1 ? items[0] : undefined
    const matchedFarms = catalogs.farms.filter((farm) => text.includes(normalized(farm.name)))
    const farm = unique(matchedFarms)
    const lotCode = raw.match(/\blote\s*(?:n(?:ro|úm(?:ero)?)?\.?\s*)?[:#-]?\s*(\d{1,6})/i)?.[1]
    const matchedLots = catalogs.lots.filter((lot) => {
      const farmMatches = !farm || lot.farm_id === farm.id
      const codeMatches = lotCode ? lot.lot_code.replace(/^0+/, '') === lotCode.replace(/^0+/, '') : false
      const nameMatches = text.includes(normalized(lot.lot_name)) && lot.lot_name.trim().length > 2
      return lot.selectable && farmMatches && (codeMatches || nameMatches)
    })
    const lot = unique(matchedLots)
    const operationCodeFromText = raw.match(/\b(?:tarea|operaci[oó]n)\s*[:#-]?\s*(\d{2,})/i)?.[1]
    const matchedOperations = catalogs.operations.filter((operation) => operationCodeFromText
      ? operation.operation_code === operationCodeFromText
      : text.includes(normalized(operation.name)) && operation.name.trim().length > 3)
    const operation = unique(matchedOperations)
    const front = unique(catalogs.fronts.filter((item) => text.includes(normalized(item.name))))
    const peopleFromCodes = [...raw.matchAll(/\blegajo\s*[:#-]?\s*(\d+)/gi)].map((match) => match[1])
    const matchedPeople = peopleFromCodes.length
      ? catalogs.personnel.filter((person) => peopleFromCodes.includes(person.employee_code))
      : catalogs.personnel.filter((person) => text.includes(normalized(person.full_name)) && person.full_name.trim().length > 4)
    const amountText = raw.match(/\b(?:cantidad(?:\s+total)?|hizo|realiz[oó])\s*[:=]?\s*(\d+(?:[.,]\d+)?)/i)?.[1]
      ?? raw.match(/\b(\d+(?:[.,]\d+)?)\s*(?:ha|hect[aá]reas?|sc|surcos?|tn|toneladas?|hs|horas?)\b/i)?.[1]
    const amount = amountText ? Number(amountText.replace(',', '.')) : undefined
    const dateText = raw.match(/\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b/)?.[1]
    let parsedDate = today()
    if (/\banteayer\b/i.test(text)) { const date = new Date(`${today()}T12:00:00`); date.setDate(date.getDate() - 2); parsedDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
    else if (/\bayer\b/i.test(text)) { const date = new Date(`${today()}T12:00:00`); date.setDate(date.getDate() - 1); parsedDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
    else if (dateText) {
      const parts = dateText.split(/[/-]/)
      const [year, month, day] = parts[0].length === 4 ? parts : [parts[2] || String(new Date().getFullYear()), parts[1], parts[0]]
      parsedDate = `${year.length === 2 ? `20${year}` : year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    }
    setReportDate(parsedDate); setFarmId(farm?.id ?? ''); setLotId(lot?.id ?? ''); setOperationCode(operation?.operation_code ?? '')
    setFrontId(front?.id ?? ''); setSelectedPeople(matchedPeople.map((person) => person.employee_code))
    setQuantity(amount && Number.isFinite(amount) ? String(amount) : ''); setNotes(raw); setInputLines([])
    setMemberMachines({}); setAllocationDrafts(Object.fromEntries(matchedPeople.map((person) => [person.employee_code, { attendance: 'Presente', quantity: amount ? String(amount / Math.max(matchedPeople.length, 1)) : '', replacement_code: '', person_hours: defaultPersonHours, machine_start_time: '', machine_end_time: '' }])))
    setPartsView('new'); setNewPartStep(1); setSection('reports')
    const resolved = [farm, lot, operation].filter(Boolean).length
    setNotice({ kind: 'success', text: resolved ? `Preparé un borrador con ${resolved} coincidencia${resolved === 1 ? '' : 's'}. Revisá los campos y completá lo que falte.` : 'Preparé el formulario. Completá la finca, el lote y la tarea que no pude identificar con seguridad.' })
  }

  useEffect(() => {
    if (staffMode === 'manual') { setMembers([]); setSelectedPeople(manualPeopleCodes); setMemberMachines({}); setAllocationDrafts({}); return }
    if (!supabase || !frontId || !operationCode) { setMembers([]); setSelectedPeople([]); setMemberMachines({}); setAllocationDrafts({}); return }
    let cancelled = false
    supabase.from('front_task_members').select('operation_code,personnel_code,machine_code').eq('front_id', frontId).eq('operation_code', operationCode).then(({ data, error }) => {
      if (cancelled) return
      if (error) { setNotice({ kind: 'error', text: `No se pudieron cargar los integrantes: ${error.message}` }); return }
      const rows = data ?? []
      setMembers(rows)
      setSelectedPeople(rows.map((member) => member.personnel_code))
      setMemberMachines(Object.fromEntries(rows.map((member) => [member.personnel_code, member.machine_code ?? ''])))
      setAllocationDrafts(Object.fromEntries(rows.map((member) => [member.personnel_code, { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: defaultPersonHours, machine_start_time: '', machine_end_time: '' }])))
    })
    return () => { cancelled = true }
  }, [frontId, operationCode, defaultPersonHours, staffMode, manualPeopleCodes])

  useEffect(() => {
    if (!supabase || !lotId || !operationCode) { setOpenCycle(null); setCycleAccumulated(0); setTargetQuantity(''); return }
    const client = supabase
    let cancelled = false
    const lot = catalogs.lots.find((item) => item.id === lotId)
    const operation = catalogs.operations.find((item) => item.operation_code === operationCode)
    client.from('work_cycles').select('id,target_quantity,target_available,unit,cycle_no').eq('lot_id', lotId).eq('operation_code', operationCode).eq('status', 'Abierto').order('cycle_no', { ascending: false }).limit(1).maybeSingle()
      .then(({ data, error }) => {
        if (cancelled) return
        if (error) { setNotice({ kind: 'error', text: `No se pudo consultar el avance existente: ${error.message}` }); return }
        if (data) {
          setOpenCycle(data)
          setTargetQuantity(data.target_available ? String(data.target_quantity) : '')
          client.from('report_tasks').select('quantity').eq('work_cycle_id', data.id).then(({ data: rows, error: totalsError }) => {
            if (cancelled) return
            if (totalsError) { setNotice({ kind: 'error', text: `No se pudo calcular el avance acumulado: ${totalsError.message}` }); return }
            setCycleAccumulated((rows ?? []).reduce((total, row) => total + Number(row.quantity), 0))
          })
        } else {
          setOpenCycle(null)
          setCycleAccumulated(0)
          const unit = operation?.unit.trim().toLocaleUpperCase() ?? ''
          const inventoryTarget = unit === 'SC' ? lot?.furrows : unit === 'HA' ? (lot?.net_area ?? lot?.gross_area) : null
          setTargetQuantity(inventoryTarget ? String(inventoryTarget) : '')
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
      setFarmId(''); setLotId(''); setOperationCode(''); setFrontId(''); setTargetQuantity(''); setQuantity(''); setSelectedPeople([]); setMemberMachines({}); setAllocationDrafts({}); setInputLines([]); setSavedReport(null); setDraftTasks([]); setDraftIdempotencyKey(''); setDraftFingerprint(''); setPartsView('summary'); setNewPartStep(1)
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
      setNewFrontName(''); setManageFrontId(data.id); setSection('fronts'); setFrontsView('manage')
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
    const people = selectedPeople
    if (people.length === 0) {
      setNotice({ kind: 'error', text: 'Seleccioná al menos una persona.' }); return
    }
    const totalAmount = Number(quantity)
    if (usesSharedTotal && (!quantity.trim() || !Number.isFinite(totalAmount) || totalAmount <= 0)) {
      setNotice({ kind: 'error', text: `Ingresá la cantidad total realizada en ${currentUnit}.` }); return
    }
    const unit = (openCycle?.unit ?? selectedOperation.unit).trim().toLocaleUpperCase()
    const integerAllocation = unit === 'SC'
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
    const details = people.map((personCode) => allocationDrafts[personCode] ?? { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: defaultPersonHours, machine_start_time: '', machine_end_time: '' })
    if (details.some((detail) => detail.attendance === 'Cantidad fija' && (!detail.quantity.trim() || !Number.isFinite(Number(detail.quantity)) || Number(detail.quantity) < 0))) {
      setNotice({ kind: 'error', text: 'Ingresá una cantidad válida para cada persona con cantidad fija.' }); return
    }
    if (usesSharedTotal) {
      const fixedTotal = details.reduce((sum, detail) => sum + (detail.attendance === 'Cantidad fija' ? Number(detail.quantity) : 0), 0)
      const presentCount = details.filter((detail) => detail.attendance === 'Presente').length
      if (fixedTotal > totalAmount + 0.001) {
        setNotice({ kind: 'error', text: 'Las cantidades fijas superan el total realizado.' }); return
      }
      if (presentCount === 0 && Math.abs(fixedTotal - totalAmount) > 0.001) {
        setNotice({ kind: 'error', text: 'Sin personas presentes, las cantidades fijas deben cubrir el total realizado.' }); return
      }
      if (integerAllocation && details.some((detail) => detail.attendance === 'Cantidad fija' && !Number.isInteger(Number(detail.quantity)))) {
        setNotice({ kind: 'error', text: 'Las cantidades fijas en surcos deben ser enteras.' }); return
      }
    } else if (details.some((detail) => detail.attendance !== 'Ausente' && (!detail.quantity.trim() || !Number.isFinite(Number(detail.quantity)) || Number(detail.quantity) < 0))) {
      setNotice({ kind: 'error', text: 'Ingresá una cantidad válida para cada persona presente.' }); return
    }
    if (!usesSharedTotal && integerAllocation && details.some((detail) => detail.attendance !== 'Ausente' && !Number.isInteger(Number(detail.quantity)))) {
      setNotice({ kind: 'error', text: 'Las cantidades por persona en surcos deben ser enteras.' }); return
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
    const distributedQuantities = usesSharedTotal ? distributeTaskQuantity(totalAmount, people, details, integerAllocation) : null
    const allocations = people.map((personCode, index) => {
      const detail = details[index]
      const assignedMachine = selectedOperation.task_type === 'Manual' ? '' : memberMachines[personCode] ?? ''
      const assignedQuantity = usesSharedTotal ? distributedQuantities?.[personCode] ?? 0 : detail.attendance === 'Ausente' ? 0 : Number(detail.quantity)
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
      target_quantity: targetQuantity.trim() ? Number(targetQuantity) : 0,
      target_available: openCycle?.target_available ?? Boolean(targetQuantity.trim()),
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
    const nextQueuedTask = staffMode === 'fronts' ? pendingFrontTaskCodes.find((code) => code !== operationCode) : undefined
    if (nextQueuedTask) {
      setOperationCode(nextQueuedTask)
      setNewPartStep(2)
      setNotice({ kind: 'success', text: `Tarea ${operationCode} agregada. El sistema continúa con la siguiente tarea del frente.` })
    } else {
      setNewPartStep(4)
      setNotice({ kind: 'success', text: `Tarea agregada al borrador (${draftTasks.length + 1}). Revisá el parte completo antes de guardarlo.` })
    }
    setQuantity(''); setNotes(''); setInputLines([])
    return
  }

  async function submitDraft() {
    if (!supabase || draftTasks.length === 0) return
    setLoading(true); setNotice(null); setSavedReport(null)
    const fingerprint = JSON.stringify({ reportDate, tasks: draftTasks })
    const idempotencyKey = draftIdempotencyKey && draftFingerprint === fingerprint ? draftIdempotencyKey : crypto.randomUUID()
    setDraftIdempotencyKey(idempotencyKey); setDraftFingerprint(fingerprint)
    const { data, error } = await supabase.rpc('create_daily_report', {
      p_idempotency_key: idempotencyKey,
      p_report_date: reportDate,
      p_service_order: '',
      p_tasks: draftTasks,
    })
    if (error) setNotice({ kind: 'error', text: `No se pudo guardar el parte: ${error.message}` })
    else {
      const report = Array.isArray(data) ? data[0] : data
      setSavedReport(report)
      setNotice({ kind: 'success', text: `Parte ${report?.report_code ?? ''} guardado correctamente.` })
      setDraftTasks([]); setDraftIdempotencyKey(''); setDraftFingerprint(''); setQuantity(''); setNotes(''); setNewPartStep(1); setPartsView('summary')
    }
    setLoading(false)
  }

  function discardDraft() {
    if (!draftTasks.length || window.confirm('¿Descartar todas las tareas de este borrador?')) {
      setDraftTasks([]); setSelectedDraftKeys([]); setDraftIdempotencyKey(''); setDraftFingerprint('')
      setFrontId(''); setOperationCode(''); setGroupCode(''); setManualPeopleCodes([])
      setStaffMode('fronts'); setNewPartStep(1)
      setNotice({ kind: 'success', text: 'Borrador descartado.' })
    }
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
  return <main className="app-shell">
    <aside className={`sidebar ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <button className="sidebar-toggle" type="button" aria-label={sidebarCollapsed ? 'Expandir menú' : 'Contraer menú'} title={sidebarCollapsed ? 'Expandir menú' : 'Contraer menú'} onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}>{sidebarCollapsed ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />}</button>
      <a className="brand" href="#inicio"><span className="brand-mark"><Leaf size={21} /></span><span><strong>Parte diario</strong><small>Gestión de tareas agrícolas</small></span></a>
      <nav aria-label="Secciones">
        <button className={`nav-link ${section === 'reports' ? 'active' : ''}`} onClick={() => { setSection('reports'); setPartsView('summary'); setSelectedReport(null) }}><ClipboardList size={16} />Partes y avance</button>
        <button className={`nav-link ${section === 'fronts' ? 'active' : ''}`} onClick={() => setSection('fronts')}><Users size={16} />Frentes</button>
        <button className={`nav-link ${section === 'quick' ? 'active' : ''}`} onClick={() => { setSection('quick'); setNotice(null) }}><Sprout size={16} />Carga manual</button>
        <button className={`nav-link ${section === 'sent' ? 'active' : ''}`} onClick={() => { setSection('sent'); setSelectedReport(null) }}><Folder size={16} />Mis partes</button>
      </nav>
      <div className="sidebar-footer">
        <button className={`nav-link config-link ${configOpen ? 'active' : ''}`} aria-expanded={configOpen} onClick={() => setConfigOpen((open) => !open)}><Settings size={16} />Configuración</button>
        {configOpen && <section className="sidebar-settings" aria-label="Configuración">
          <label>Usuario activo<input value={session.user.email ?? ''} readOnly /></label>
          <label>Horas por persona<input type="number" min="0" max="48" step="0.5" value={defaultPersonHours} onChange={(event) => setDefaultPersonHours(event.target.value)} /></label>
          <label>WhatsApp destinatario<input type="tel" value={whatsappNumber} onChange={(event) => setWhatsappNumber(event.target.value)} placeholder="Ej.: 5493815551234" /></label>
          <label>Mensaje sugerido<textarea rows={3} value={whatsappMessage} onChange={(event) => setWhatsappMessage(event.target.value)} /></label>
          <small>Podés usar {'{id}'} y {'{fecha}'} en el mensaje.</small>
          <button className="primary-button" onClick={savePreferences}><Save size={15} />Guardar configuración</button>
          <div className="sidebar-config-actions"><button type="button" onClick={section === 'reports' || section === 'sent' ? loadReports : loadCatalogs} disabled={loading}><RefreshCw size={15} />Actualizar datos</button><button type="button" onClick={signOut}><LogOut size={15} />Cerrar sesión</button></div>
          <div className="sidebar-note"><Cloud size={15} /><span>Sincronización en línea</span></div>
        </section>}
      </div>
    </aside>
    <section className="workspace" id="inicio">
      <header className="topbar">
        <h1>{section === 'reports' ? 'Partes y avance' : section === 'fronts' ? 'Frentes de trabajo' : section === 'quick' ? 'Carga manual' : 'Mis partes'}</h1>
      </header>
      {section === 'reports' && <div className="view-tabs" role="tablist" aria-label="Partes y avance">
        <button className={partsView === 'summary' ? 'selected' : ''} role="tab" aria-selected={partsView === 'summary'} onClick={() => { setPartsView('summary'); setSelectedReport(null) }}>Resumen</button>
        <button className={partsView === 'new' ? 'selected' : ''} role="tab" aria-selected={partsView === 'new'} onClick={() => { setPartsView('new'); setSelectedReport(null); setNewPartStep(1) }}><Plus size={15} />Nuevo parte</button>
      </div>}
      {section === 'reports' && partsView === 'new' && <div className="page-intro"><h2><ClipboardList size={20} />Nuevo parte</h2><p>Completá un paso por vez. Podés volver a cualquier paso sin perder lo cargado.</p></div>}
      {section === 'fronts' && <div className="page-intro"><h2><Users size={20} />Frentes de trabajo</h2><p>Cada frente puede contener varias tareas, con personal y vehículos diferentes para cada una.</p></div>}
      {section === 'quick' && <div className="page-intro"><h2><Sprout size={20} />Carga manual</h2><p>Describí el parte en una frase. Revisá los datos y completá lo que falte antes de guardarlo en Partes y avance.</p></div>}
      {section === 'sent' && <div className="page-intro"><h2><Folder size={20} />Mis partes</h2><p>Consultá los partes enviados guardados en esta instalación.</p></div>}
      {notice && <div className={`notice ${notice.kind}`} role="status">{notice.text}{savedReport && <span className="saved-code">{savedReport.report_code}</span>}</div>}
      {section === 'quick' && <section className="quick-entry">
        {manualText && <div className="quick-guidance"><strong>Revisá antes de guardar</strong><p>La carga por texto solo prepara un borrador. Corregí los campos sugeridos en <b>Partes y avance · Nuevo parte</b> antes de confirmar.</p></div>}
        <form className="quick-composer" onSubmit={prepareManualEntry}><textarea aria-label="Describir parte diario" rows={2} value={manualText} onChange={(event) => setManualText(event.target.value)} placeholder="Describí fecha, finca, lote, tarea, cantidad y personal; agregá vehículo, frente o insumo si corresponde." /><button className="primary-button" type="submit" aria-label="Preparar parte"><ArrowUp size={18} /></button></form>
      </section>}
      {(section === 'reports' && partsView === 'summary' || section === 'sent') && <section className="reports-panel"><div className="section-heading"><span>↗</span><div><h2>{section === 'sent' ? 'Partes enviados' : 'Partes y avance'}</h2><p>{section === 'sent' ? 'Consultá los documentos enviados y su detalle.' : 'Consultá los partes pendientes de revisar o enviar y el avance de cada tarea.'}</p></div></div><div className="report-filters">
        <label>Fecha desde<input type="date" value={reportFrom} onChange={(event) => setReportFrom(event.target.value)} /></label>
        <label>Fecha hasta<input type="date" value={reportTo} onChange={(event) => setReportTo(event.target.value)} /></label>
        <label>Finca<select value={reportFarmFilter} onChange={(event) => { setReportFarmFilter(event.target.value); setReportLotFilter('Todos') }}><option>Todas</option>{reportFarmOptions.map((farm) => <option key={farm}>{farm}</option>)}</select></label>
        <label>Lote<select value={reportLotFilter} onChange={(event) => setReportLotFilter(event.target.value)}><option>Todos</option>{reportLotOptions.map((lot) => <option key={lot}>{lot}</option>)}</select></label>
        <label>Tarea<select value={reportOperationFilter} onChange={(event) => setReportOperationFilter(event.target.value)}><option>Todas</option>{reportOperationOptions.map((operation) => <option key={operation}>{operation}</option>)}</select></label>
        {section !== 'sent' && <label>Estado<select value={reportStatusFilter} onChange={(event) => setReportStatusFilter(event.target.value)}><option>Todos</option>{['Borrador', 'Corregido', 'Revisado'].map((status) => <option key={status}>{status}</option>)}</select></label>}
        <label className="report-search">Buscar<input type="search" value={reportSearch} onChange={(event) => setReportSearch(event.target.value)} placeholder="ID, finca, lote, tarea, personal o insumo" /></label>
        <details className="report-more"><summary>Más</summary><label>ID de parte<input value={reportIdFilter} onChange={(event) => setReportIdFilter(event.target.value)} placeholder="Ej.: parte-0001" /></label><button type="button" className="secondary-button" onClick={() => { setReportFrom(''); setReportTo(''); setReportSearch(''); setReportIdFilter(''); setReportFarmFilter('Todas'); setReportLotFilter('Todos'); setReportOperationFilter('Todas'); setReportStatusFilter('Todos') }}>Limpiar filtros</button></details>
      </div>{selectedReport ? <article className="report-detail"><div className="front-editor-heading"><div><h2>{selectedReport.report_code}</h2><p>{selectedReport.report_date} · Orden {selectedReport.service_order || '—'} · {selectedReport.document_status}</p></div><button className="secondary-button" onClick={() => { setSelectedReport(null); setCorrectionDraft(null) }}>Volver a resultados</button></div>{correctionDraft && <section className="report-task-detail"><h3>Corrección de {correctionDraft.report_code}</h3><p>Se conserva el mismo conjunto de tareas, personas e insumos. El guardado es atómico y crea una instantánea previa.</p><div className="field-grid two"><label>Fecha<input type="date" value={correctionDraft.report_date} onChange={(event) => setCorrectionDraft({ ...correctionDraft, report_date: event.target.value })} /></label><label>Orden de servicio<input value={correctionDraft.service_order ?? ''} onChange={(event) => setCorrectionDraft({ ...correctionDraft, service_order: event.target.value })} /></label></div>{correctionDraft.report_tasks.map((task: ReportRow, index: number) => <section className="report-task-detail" key={task.id}><h4>{index + 1}. {task.lots?.lot_code} · {task.operations?.name}</h4><div className="field-grid two"><label>Cantidad<input type="number" min={(task.work_cycles?.unit ?? task.operations?.unit ?? '').toUpperCase() === 'SC' ? '1' : '0.001'} step={(task.work_cycles?.unit ?? task.operations?.unit ?? '').toUpperCase() === 'SC' ? '1' : '0.001'} value={task.quantity} onChange={(event) => patchCorrectionTask(task.id, { quantity: event.target.value })} /></label><label>Cultivo<input value={task.crop ?? ''} onChange={(event) => patchCorrectionTask(task.id, { crop: event.target.value })} /></label><label className="full-field">Observaciones<textarea rows={2} value={task.notes ?? ''} onChange={(event) => patchCorrectionTask(task.id, { notes: event.target.value })} /></label></div><h5>Personal y maquinaria</h5>{(task.allocations ?? []).map((row: ReportRow) => <div className="field-grid two" key={row.id}><label>Persona<select value={row.personnel_code} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { personnel_code: event.target.value })}>{catalogs.personnel.map((person) => <option key={person.employee_code} value={person.employee_code}>{person.employee_code} · {person.full_name}</option>)}</select></label><label>Estado<select value={row.attendance} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { attendance: event.target.value, quantity: event.target.value === 'Ausente' ? 0 : row.quantity })}><option>Presente</option><option>Ausente</option><option>Cantidad fija</option></select></label><label>Cantidad<input type="number" min="0" step="0.001" disabled={row.attendance === 'Ausente'} value={row.quantity} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { quantity: event.target.value })} /></label><label>Reemplazo<input list={`replacement-${row.id}`} value={row.replacement_code ?? ''} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { replacement_code: event.target.value })} /><datalist id={`replacement-${row.id}`}>{catalogs.personnel.map((person) => <option key={person.employee_code} value={person.employee_code}>{person.full_name}</option>)}</datalist></label><label>Horas<input type="number" min="0" max="48" step="0.25" value={row.person_hours} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { person_hours: event.target.value })} /></label><label>Máquina<select value={row.machine_code ?? ''} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { machine_code: event.target.value })}><option value="">Sin maquinaria</option>{catalogs.machines.map((machine) => <option key={machine.machine_code} value={machine.machine_code}>{machine.machine_code} · {machine.brand} {machine.model}</option>)}</select></label><label>Lectura inicial<input type="number" min="0" step="1" value={row.machine_start_time ?? ''} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { machine_start_time: event.target.value || null })} /></label><label>Lectura final<input type="number" min="0" step="1" value={row.machine_end_time ?? ''} onChange={(event) => patchCorrectionRow(task.id, 'allocations', row.id, { machine_end_time: event.target.value || null })} /></label></div>)}<h5>Insumos</h5>{(task.part_inputs ?? []).map((row: ReportRow) => <div className="field-grid two" key={row.id}><label>Producto<select value={row.input_code} onChange={(event) => patchCorrectionRow(task.id, 'part_inputs', row.id, { input_code: event.target.value })}>{catalogs.inputs.map((input) => <option key={input.input_code} value={input.input_code}>{input.description}</option>)}</select></label><label>Dosis<input type="number" min="0" step="0.001" value={row.dose} onChange={(event) => patchCorrectionRow(task.id, 'part_inputs', row.id, { dose: event.target.value })} /></label><label>Consumo<input type="number" min="0" step="0.001" value={row.quantity} onChange={(event) => patchCorrectionRow(task.id, 'part_inputs', row.id, { quantity: event.target.value })} /></label><label>Unidad<input value={row.unit} onChange={(event) => patchCorrectionRow(task.id, 'part_inputs', row.id, { unit: event.target.value })} /></label></div>)}</section>)}<div className="form-actions"><button className="secondary-button" onClick={() => setCorrectionDraft(null)}>Cancelar</button><button className="primary-button" disabled={loading} onClick={() => void saveReportCorrection()}>{loading ? 'Guardando…' : 'Guardar corrección'}</button></div></section>}
      {(selectedReport.report_tasks ?? []).map((task: ReportRow, index: number) => <section className="report-task-detail" key={task.id}><h3>{index + 1}. {task.lots?.lot_code} · {task.operations?.name}</h3><p>{task.quantity} {task.work_cycles?.unit ?? task.operations?.unit} · Ciclo {task.work_cycles?.cycle_no} · Objetivo {task.work_cycles?.target_available === false ? 'Sin dato' : task.work_cycles?.target_quantity ?? 'Sin dato'} · Acumulado {cycleTotals[task.work_cycle_id] ?? 'calculando'} · Saldo {task.work_cycles?.target_available !== false && task.work_cycles?.target_quantity ? Math.max(0, Number(task.work_cycles.target_quantity) - (cycleTotals[task.work_cycle_id] ?? 0)) : 'Sin dato'}</p><p>Centro sugerido {task.cost_center_context?.suggested?.id || '—'} · elegido {task.cost_center_context?.selected?.id || '—'} {task.cost_center_context?.changed ? '· cambio manual' : ''}</p><h4>Personal y maquinaria</h4><ul>{(task.allocations ?? []).map((row: ReportRow, i: number) => <li key={`${row.personnel_code}-${i}`}>{row.personnel?.full_name} · {row.attendance} · {row.quantity} · {row.machines?.brand} {row.machines?.model} · {row.person_hours} h</li>)}</ul><h4>Insumos</h4><ul>{(task.part_inputs ?? []).map((row: ReportRow) => <li key={row.input_code}>{row.inputs?.description} · {row.quantity} {row.unit} · dosis {row.dose}</li>)}</ul></section>)}<div className="form-actions report-document-actions">{appRole === 'administrador' && !['Revisado','Enviado'].includes(selectedReport.document_status) && <button className="secondary-button" onClick={() => void reviewReport(selectedReport)}>Guardar revisión</button>}{appRole === 'administrador' && selectedReport.document_status !== 'Borrador' && !correctionDraft && <button className="secondary-button" onClick={() => setCorrectionDraft(structuredClone(selectedReport))}>Corregir parte</button>}<button className="secondary-button" disabled={!['Revisado','Enviado'].includes(selectedReport.document_status)} onClick={() => void downloadReportPdf(selectedReport)}>Descargar PDF con JSON adjunto</button><button className="secondary-button" disabled={!['Revisado','Enviado'].includes(selectedReport.document_status)} onClick={() => void shareReportPdf(selectedReport)}>Compartir PDF</button><button className="secondary-button" onClick={() => downloadReportExchange(selectedReport)}>Exportar JSON</button></div>{selectedReport.document_status === 'Revisado' && (selectedReport.created_by === session.user.id || appRole === 'administrador') && <div className="send-confirm"><label>Destinatario (opcional)<input value={sentTo} onChange={(event) => setSentTo(event.target.value)} /></label><label>Canal<select value={sentVia} onChange={(event) => setSentVia(event.target.value)}><option>WhatsApp</option><option>Correo</option><option>Otro</option></select></label><button className="primary-button" onClick={() => void confirmReportSent(selectedReport)}>Confirmar envío realizado</button><small>Confirmá solo después de compartir o enviar el PDF.</small></div>}<p className="helper-text">Preparar, descargar o compartir no registra un envío. Revisar y confirmar envío son acciones separadas.</p></article> : <>{loading ? <div className="loading-label">Cargando partes…</div> : filteredReports.length === 0 ? <p className="empty-state">{section === 'sent' ? 'Todavía no tenés partes enviados. Los partes por revisar o enviar están en Partes y avance.' : 'No hay partes que coincidan con los filtros.'}</p> : <div className="daily-table-wrap">
          <div className="table-heading"><h2>Parte diario</h2><span>{filteredReports.length} partes</span></div>
          <table className="daily-table"><thead><tr><th>Número</th><th>Fecha</th><th>Finca y lote</th><th>Tarea y cantidad</th><th>Estado</th></tr></thead><tbody>
            {filteredReports.map((report) => {
              const tasks = report.report_tasks ?? []
              const farmLots = [...new Set(tasks.map((task: ReportRow) => {
                const farm = catalogs.farms.find((item) => item.id === task.lots?.farm_id)?.name
                return [farm, task.lots?.lot_code].filter(Boolean).join(' · ')
              }))]
              return <tr key={report.id}>
                <td><button className="report-code-link" onClick={() => setSelectedReport(report)}>{report.report_code}</button></td>
                <td>{new Date(report.report_date + 'T12:00:00').toLocaleDateString('es-AR')}</td>
                <td>{farmLots.join(', ') || '—'}</td>
                <td>{tasks.map((task: ReportRow) => (task.operations?.name ?? task.operation_code) + ' · ' + formatInputAmount(Number(task.quantity)) + ' ' + (task.work_cycles?.unit ?? task.operations?.unit ?? '')).join(' / ')}</td>
                <td><span className={'status status-' + String(report.document_status).toLocaleLowerCase()}>{report.document_status}</span></td>
              </tr>
            })}
          </tbody></table>
        </div>}</>}</section>}
      {section === 'reports' && partsView === 'new' && !hasMasterCatalogs && !loading && <section className="empty-state"><h2>Faltan datos maestros</h2><p>La conexión funciona, pero aún faltan fincas, lotes, tareas o personal activos. Revisá los catálogos en Supabase y actualizá esta pantalla.</p><button className="secondary-button" onClick={loadCatalogs}>Actualizar catálogos</button></section>}
      {section === 'fronts' && <section className="fronts-panel">
        <div className="view-tabs" role="tablist" aria-label="Frentes">
          <button className={frontsView === 'create' ? 'selected' : ''} role="tab" aria-selected={frontsView === 'create'} onClick={() => setFrontsView('create')}>Crear frente</button>
          <button className={frontsView === 'manage' ? 'selected' : ''} role="tab" aria-selected={frontsView === 'manage'} onClick={() => setFrontsView('manage')}>Frentes</button>
        </div>
        {frontsView === 'create' && <section className="front-create-card"><h2>Crear un frente nuevo</h2><p>Escribí el nombre para comenzar. La configuración del equipo continúa en la sección Frentes.</p><form className="new-front-form" onSubmit={createFront}><label>Nuevo frente<input required maxLength={120} value={newFrontName} onChange={(event) => setNewFrontName(event.target.value)} placeholder="Nombre del frente" /></label><button className="primary-button" disabled={loading}><Plus size={15} /> Crear frente</button></form></section>}
{frontsView === 'manage' && <div className="front-manage-view"><h2>Frentes configurados</h2>{manageableFronts.length > 0 ? <label className="front-picker">Frente a administrar<select value={manageFrontId} onChange={(event) => setManageFrontId(event.target.value)}><option value="">Seleccionar frente</option>{manageableFronts.map((front) => <option key={front.id} value={front.id}>{front.name}</option>)}</select></label> : <p className="helper-text">Todavía no tenés frentes propios. Los frentes compartidos aparecen en Cargar parte.</p>}
        {manageFront && <form className="front-editor" onSubmit={saveFront}><div className="front-editor-heading"><div><h3>{manageFront.name}</h3><p>Los cambios se aplican al guardar.</p></div><button className="secondary-button danger-button" type="button" disabled={loading} onClick={deactivateFront}>Desactivar</button></div><label>Nombre del frente<input required maxLength={120} value={manageFrontName} onChange={(event) => setManageFrontName(event.target.value)} /></label><label className="front-picker">Tarea del frente<select required value={manageOperationCode} onChange={(event) => { setManageOperationCode(event.target.value); setFrontPeopleSearch('') }}><option value="">Seleccionar tarea</option>{catalogs.operations.map((operation) => <option key={operation.operation_code} value={operation.operation_code}>{operation.operation_code} · {operation.name}</option>)}</select></label><h3>Equipo para esta tarea <small>{selectedManageMembers.length} {selectedManageMembers.length === 1 ? 'integrante' : 'integrantes'} · {manageMachines.length} máquinas compatibles</small></h3>
          <label className="front-search">Buscar personal<input type="search" value={frontPeopleSearch} onChange={(event) => setFrontPeopleSearch(event.target.value)} placeholder="Nombre o legajo" /></label>
          <div className="front-person-list">{matchingManagePeople.map((person) => { const assignedMember = selectedManageMembers.find((member) => member.personnel_code === person.employee_code); const assigned = Boolean(assignedMember); return <div className="front-person-row" key={person.employee_code}><label className="person-option"><input type="checkbox" checked={assigned} onChange={(event) => setFrontTaskMembers((current) => { const remaining = current.filter((member) => !(member.operation_code === manageOperationCode && member.personnel_code === person.employee_code)); return event.target.checked ? [...remaining, { operation_code: manageOperationCode, personnel_code: person.employee_code, machine_code: null }] : remaining })} /><span>{person.full_name}<small>Legajo {person.employee_code}</small></span></label>{assigned && <MachinePicker label={`Maquinaria habitual de ${person.full_name}`} disabled={manageOperation?.task_type === 'Manual'} machines={manageMachines} value={assignedMember?.machine_code ?? ''} onChange={(machineCode) => setFrontTaskMembers((current) => current.map((member) => member.operation_code === manageOperationCode && member.personnel_code === person.employee_code ? { ...member, machine_code: machineCode || null } : member))} />}</div> })}</div>
          <div className="form-actions"><span>El equipo queda disponible al cargar un parte con este frente.</span><button className="primary-button" disabled={loading || !manageFrontName.trim()}><Save size={15} /> Guardar frente</button></div></form>}</div>}
      </section>}
      {loading && !hasMasterCatalogs && <div className="loading-label"><RefreshCw className="spin" size={18} /> Cargando datos…</div>}
      {section === 'reports' && partsView === 'new' && hasMasterCatalogs && <form className="report-form" id="cargar" onSubmit={saveReport}>
        <div className="part-stepper" role="tablist" aria-label="Pasos del nuevo parte">
          {['Finca y lote', 'Tarea', 'Personal y vehículos', 'Revisar y guardar'].map((label, index) => <button type="button" role="tab" aria-selected={newPartStep === index + 1} className={newPartStep === index + 1 ? 'active' : ''} key={label} onClick={() => setNewPartStep(index + 1)}><span>{index + 1}</span>{label}</button>)}
        </div>
        {newPartStep === 4 && <>
          <div className="page-intro"><h2>Paso 4 · Revisar y guardar</h2><p>Revisá las tareas agregadas antes de guardar el parte completo.</p></div>
          {draftTasks.length > 0 ? <section className="form-section draft-review">
            <h2>Tareas del parte</h2>
            <div className="daily-table-wrap staged-table-wrap"><table className="daily-table staged-table"><thead><tr><th>✓</th><th>Tarea</th><th>Cultivo</th><th>Finca</th><th>Lote</th><th>Frente</th><th>Cantidad</th><th>Unidad</th><th>Personas</th></tr></thead><tbody>
              {draftTasks.map((task) => { const key = task.front_id + ':' + task.lot_id + ':' + task.operation_code; const lot = catalogs.lots.find((item) => item.id === task.lot_id); const operation = catalogs.operations.find((item) => item.operation_code === task.operation_code); const front = catalogs.fronts.find((item) => item.id === task.front_id); const allocations = Array.isArray(task.allocations) ? task.allocations as ReportRow[] : []; return <tr key={key}><td><input type="checkbox" aria-label={'Seleccionar tarea ' + (operation?.name ?? '') + ' para quitar'} checked={selectedDraftKeys.includes(key)} onChange={(event) => setSelectedDraftKeys((current) => event.target.checked ? [...current, key] : current.filter((item) => item !== key))} /></td><td>{operation?.name ?? String(task.operation_code)}</td><td>{lot?.crop || '—'}</td><td>{catalogs.farms.find((item) => item.id === lot?.farm_id)?.name ?? '—'}</td><td>{lot?.lot_code ?? '—'}</td><td>{front?.name === 'Carga manual' ? 'Manual' : front?.name ?? '—'}</td><td>{String(task.quantity)}</td><td>{String(task.unit)}</td><td>{allocations.length}</td></tr> })}
            </tbody></table></div>
            <div className="form-actions review-actions">
              <button className="secondary-button" type="button" disabled={!selectedDraftKeys.length} onClick={() => { setDraftTasks((current) => current.filter((task) => !selectedDraftKeys.includes(task.front_id + ':' + task.lot_id + ':' + task.operation_code))); setSelectedDraftKeys([]); setDraftIdempotencyKey(''); setDraftFingerprint('') }}>Quitar tarea seleccionada</button>
              <button className="secondary-button" type="button" onClick={discardDraft}>Descartar borrador</button>
              <button className="secondary-button" type="button" onClick={() => { setNewPartStep(2); if (staffMode === 'manual') { setOperationCode(''); setGroupCode('') } }}>Agregar otra tarea</button>
              <button className="primary-button" type="button" disabled={loading} onClick={() => void submitDraft()}>{loading ? 'Guardando…' : 'Guardar parte completo'}</button>
            </div>
          </section> : <div className="notice info">Todavía no agregaste tareas. Comenzá por Finca y lote y seguí los pasos.</div>}
        </>}
        {newPartStep === 1 && <>
          <div className="page-intro"><h2>Paso 1 · Finca y lote</h2><p>Indicá dónde se realizó el trabajo. Estos datos se conservarán al avanzar.</p></div>
          <section className="form-section location-card">
            <h2>Datos del parte y ubicación de la tarea</h2>
            <p>La fecha pertenece al parte completo. La finca, el lote y el centro de costo de TOTVS corresponden solamente a la tarea que estás cargando. OS se completará a mano en el PDF.</p>
            <div className="location-fields">
              <label>Fecha<input type="date" required value={reportDate} disabled={draftTasks.length > 0} onChange={(event) => setReportDate(event.target.value)} /></label>
              <label>Finca<select required value={farmId} onChange={(event) => { setFarmId(event.target.value); setLotId(''); setChosenCostCenter('') }}><option value="">Seleccionar finca</option>{catalogs.farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}</select></label>
              <label>Lote<select required value={lotId} onChange={(event) => { setLotId(event.target.value); setChosenCostCenter('') }} disabled={!farmId}><option value="">Seleccionar lote</option>{visibleLots.map((lot) => <option key={lot.id} value={lot.id}>{lot.lot_code.padStart(4, '0')} — {lot.lot_name}</option>)}</select></label>
              <label>Centro de costo<select required={catalogs.costCenters.length > 0} value={effectiveCostCenter} onChange={(event) => { setChosenCostCenter(event.target.value); setGroupCode('') }} disabled={!selectedLot}><option value="">Seleccionar centro de costo</option>{catalogs.costCenters.map((center) => <option key={center.cost_center_id} value={center.cost_center_id}>{center.name}</option>)}</select></label>
            </div>
            {selectedLot && !selectedLot.agronomic_data_available && <p className="location-note">Sin datos de superficie, surcos y plantación para este lote. Podés cargar el parte; no se calcularán referencias que necesiten esos datos.</p>}
            {selectedLot?.suggested_cost_center_id && effectiveCostCenter !== selectedLot.suggested_cost_center_id && <p className="location-note">El centro elegido difiere del sugerido por la ubicación; el cambio quedará registrado en la tarea.</p>}
            {draftTasks.length > 0 && <small className="helper-text">La fecha queda bloqueada mientras el parte está en proceso. Podés cambiar finca, lote y centro para la siguiente tarea.</small>}
          </section>
        </>}
        {newPartStep === 2 && <>
          <div className="page-intro"><h2>Paso 2 · Tarea</h2><p>Elegí cómo cargar el parte, la tarea realizada y su cantidad.</p></div>
          <label className="staff-mode-label">¿Cómo vas a cargar el parte?</label>
          <div className="view-tabs staff-mode-tabs" role="tablist" aria-label="Modo de carga">
            <button type="button" role="tab" aria-selected={staffMode === 'fronts'} className={staffMode === 'fronts' ? 'selected' : ''} disabled={draftTasks.length > 0 && staffMode !== 'fronts'} onClick={() => { setStaffMode('fronts'); setFrontId(''); setOperationCode(''); setIncludedFrontTasks([]); setManualPeopleCodes([]); setFrontTaskPickerOpen(false) }}>Frentes</button>
            <button type="button" role="tab" aria-selected={staffMode === 'manual'} className={staffMode === 'manual' ? 'selected' : ''} disabled={draftTasks.length > 0 && staffMode !== 'manual'} onClick={() => { setStaffMode('manual'); setFrontId(''); setOperationCode(''); setGroupCode(''); setIncludedFrontTasks([]); setManualPeopleCodes([]); setSelectedPeople([]) }}>Carga manual</button>
          </div>
          {staffMode === 'fronts' && <>
            {visibleFronts.length === 0 ? <div className="notice info">No hay frentes configurados. Elegí “Carga manual” o creá un frente.</div> : <label className="front-picker">Frente<select value={frontId} disabled={draftTasks.length > 0} onChange={(event) => { setFrontId(event.target.value); setOperationCode(''); setIncludedFrontTasks([]); setFrontTaskPickerOpen(false) }}><option value="">Seleccionar frente</option>{visibleFronts.map((front) => <option key={front.id} value={front.id}>{front.name}</option>)}</select><small>Se cargarán las tareas, las personas y las máquinas configuradas para este frente.</small></label>}
            {frontId && <div className="front-picker"><span className="field-label">Tareas a incluir en este parte</span>
              <button type="button" className="front-task-multiselect" aria-expanded={frontTaskPickerOpen} onClick={() => setFrontTaskPickerOpen((open) => !open)}><span>{selectedFrontTaskCodes.length ? selectedFrontTaskCodes.map((code) => <span className="task-chip" key={code}>{catalogs.operations.find((item) => item.operation_code === code)?.name ?? code}</span>) : <span className="placeholder">Seleccionar tareas</span>}</span><ChevronDown size={16} /></button>
              {frontTaskPickerOpen && <div className="front-task-options">{availableFrontTaskCodes.map((code) => { const operation = catalogs.operations.find((item) => item.operation_code === code); return <label key={code}><input type="checkbox" checked={includedFrontTasks.includes(code)} onChange={(event) => { const included = event.target.checked; setIncludedFrontTasks((current) => included ? [...current, code] : current.filter((item) => item !== code)); if (!included) setDraftTasks((current) => current.filter((task) => !(task.front_id === frontId && task.operation_code === code))) }} /><span>{operation?.operation_code} — {operation?.name}</span></label> })}{availableFrontTaskCodes.length === 0 && <small>Este frente todavía no tiene tareas compatibles con el centro de costo elegido.</small>}</div>}
              <small>Quitá las tareas que no vas a cargar. Esto solo cambia este parte; el frente guardado no se modifica.</small>
            </div>}
            {frontId && selectedFrontTaskCodes.length > 0 && <section className="front-task-progress"><h3>Tareas incluidas en el frente</h3>
              {selectedFrontTaskCodes.map((code, index) => { const operation = catalogs.operations.find((item) => item.operation_code === code); const label = (operation?.operation_code ?? code) + ' — ' + (operation?.name ?? ''); return completedFrontTaskCodes.includes(code) ? <div className="task-progress-done" key={code}><b>✓ Tarea {index + 1} de {selectedFrontTaskCodes.length} completada</b><span>{label}</span></div> : code === nextFrontTaskCode ? <div className="task-progress-current" role="status" key={code}><b>→ TAREA ACTUAL · {index + 1} de {selectedFrontTaskCodes.length}</b><span>{label}</span></div> : <div className="task-progress-pending" key={code}>◯ <b>Pendiente · Tarea {index + 1} de {selectedFrontTaskCodes.length}</b> — {label}</div> })}
              {pendingFrontTaskCodes.length > 0 ? <div className="notice info">Ahora completá: {catalogs.operations.find((item) => item.operation_code === nextFrontTaskCode)?.name}. Después continuará automáticamente con la siguiente tarea incluida.</div> : <div className="notice success">Todas las tareas del frente están preparadas. Ya podés guardar el parte completo.</div>}
            </section>}
          </>}
        </>}
        {newPartStep === 2 && <section className="form-section task-data-card">
          <h2>Datos de la tarea</h2>
          {staffMode === 'fronts' && nextFrontTaskCode && <p className="current-task-label">Tarea {selectedFrontTaskCodes.indexOf(nextFrontTaskCode) + 1} de {selectedFrontTaskCodes.length}: <b>{selectedOperation?.operation_code} — {selectedOperation?.name}</b></p>}
          {staffMode === 'manual' && <div className="field-grid two">
            <label>Grupo de tarea<select value={groupCode} onChange={(event) => { setGroupCode(event.target.value); setOperationCode(''); setQuantity(''); setInputLines([]) }}><option value="">Seleccionar grupo de tarea</option>{visibleOperationGroups.map((group) => <option key={group.group_code} value={group.group_code}>{group.name}</option>)}</select></label>
            <label>Tarea<select value={operationCode} disabled={!groupCode} onChange={(event) => { setOperationCode(event.target.value); setQuantity(''); setSelectedPeople([]); setMemberMachines({}); setAllocationDrafts({}); setInputLines([]) }}><option value="">{groupCode ? 'Seleccionar tarea' : 'Primero seleccioná el grupo de tarea'}</option>{allowedOperations.map((operation) => <option key={operation.operation_code} value={operation.operation_code}>{operation.operation_code} · {operation.name}</option>)}</select></label>
          </div>}
          {!operationCode && staffMode === 'fronts' && <div className="notice info">Seleccioná un frente y al menos una tarea para continuar.</div>}
          {!operationCode && staffMode === 'manual' && <div className="notice info">Seleccioná el grupo y la tarea para continuar.</div>}
          {selectedOperation && <>
            <div className="task-meta"><span>Unidad: {currentUnit}</span>{selectedOperation.machine_groups.length > 0 && <b>Máquinas habilitadas: {selectedOperation.machine_groups.join(', ')}</b>}</div>
            <label className="quantity-label">{usesSharedTotal ? `Cantidad realizada en este parte (${currentUnit})` : `Cantidad por persona (${currentUnit})`}<input type="number" inputMode="decimal" min={currentUnit.toUpperCase() === 'SC' ? '1' : '0.001'} step={currentUnit.toUpperCase() === 'SC' ? '1' : '0.001'} value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="Ingresá la cantidad" /></label>
            {usesSharedTotal ? <div className="lot-progress-panel">
              <b>Avance del lote</b>{Number(targetQuantity) > 0 && <><div className="lot-progress-track"><span style={{ width: Math.min(100, Math.max(0, (cycleAccumulated + Number(quantity || 0)) / Number(targetQuantity) * 100)) + '%' }} /></div><small>{Math.round(Math.min(100, Math.max(0, (cycleAccumulated + Number(quantity || 0)) / Number(targetQuantity) * 100)))}% del objetivo</small></>}
              <div className="lot-progress-metrics"><div><small>Objetivo</small><strong>{Number(targetQuantity) > 0 ? formatInputAmount(Number(targetQuantity)) + ' ' + currentUnit : 'Sin dato'}</strong></div><div><small>Ya cargado</small><strong>{formatInputAmount(cycleAccumulated)} {currentUnit}</strong></div><div><small>Con este parte</small><strong>{formatInputAmount(Number(quantity || 0))} {currentUnit}</strong></div><div><small>Quedará pendiente</small><strong>{Number(targetQuantity) > 0 ? formatInputAmount(Math.max(0, Number(targetQuantity) - cycleAccumulated - Number(quantity || 0))) + ' ' + currentUnit : 'Sin objetivo'}</strong></div></div>
            </div> : <div className="lot-progress-panel"><b>Acumulado de la tarea</b><div className="lot-progress-metrics two"><div><small>Ya cargado</small><strong>{formatInputAmount(cycleAccumulated)} {currentUnit}</strong></div><div><small>Total al guardar</small><strong>{formatInputAmount(cycleAccumulated + completedWorkQuantity)} {currentUnit}</strong></div></div></div>}
            <label className="task-notes-label">Observaciones<input value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
          </>}
        </section>}
        {newPartStep === 3 && <section className="form-section"><h2>Personal y vehículos</h2><p>Confirmá quiénes trabajaron, sus cantidades y los datos de las máquinas.</p>
          <button className="secondary-button staff-back-button" type="button" onClick={() => setNewPartStep(2)}>Volver a tarea</button>
          {staffMode === 'fronts' && <p className="helper-text">Personal y máquinas de la tarea {operationCode} configurados en el frente {selectedFront?.name}.</p>}
          {staffMode === 'fronts' && <label className="manual-people-picker">Agregar persona<select value="" onChange={(event) => { const code = event.target.value; if (code) { setSelectedPeople((current) => current.includes(code) ? current : [...current, code]); setAllocationDrafts((current) => ({ ...current, [code]: current[code] ?? { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: defaultPersonHours, machine_start_time: '', machine_end_time: '' } })); setMemberMachines((current) => ({ ...current, [code]: current[code] ?? '' })) } }}><option value="">Seleccionar personal</option>{catalogs.personnel.filter((person) => !eligiblePeople.some((item) => item.employee_code === person.employee_code)).map((person) => <option key={person.employee_code} value={person.employee_code}>{person.full_name} — {person.employee_code}</option>)}</select></label>}
          {staffMode === 'manual' && <label className="manual-people-picker">Personas del parte<select multiple size={6} value={manualPeopleCodes} onChange={(event) => { const codes = [...event.target.selectedOptions].map((option) => option.value); setManualPeopleCodes(codes); setSelectedPeople(codes) }}>{catalogs.personnel.map((person) => <option key={person.employee_code} value={person.employee_code}>{person.full_name} — {person.employee_code}</option>)}</select><small>Seleccioná las personas para este parte. Después podrás asignar o editar su máquina.</small></label>}
          {!operationCode && <p className="helper-text">Elegí la tarea para ver los frentes y su equipo configurado.</p>}{operationCode && !frontId && <p className="helper-text">Elegí un frente para ver el personal de esta tarea.</p>}{frontId && eligiblePeople.length === 0 && <p className="helper-text">Este frente no tiene personal configurado para la tarea elegida. Configuralo en Frentes.</p>}{eligiblePeople.length > 0 && <div className="allocation-grid-wrap"><table className="allocation-grid"><thead><tr><th>Legajo / apellido y nombre</th><th>Hs persona</th><th>Cant. tarea</th><th>U.M.</th><th>ID vehículo</th><th>Marca y modelo</th><th>Medidor: inicio / fin / dif.</th><th>Estado / reemplazo</th></tr></thead><tbody>{eligiblePeople.map((person) => { const assignedMachine = memberMachines[person.employee_code] ?? ''; const machine = catalogs.machines.find((item) => item.machine_code === assignedMachine); const checked = selectedPeople.includes(person.employee_code); const detail = allocationDrafts[person.employee_code] ?? { attendance: 'Presente', quantity: '', replacement_code: '', person_hours: defaultPersonHours, machine_start_time: '', machine_end_time: '' }; const updateDetail = (key: keyof AllocationDraft, value: string) => setAllocationDrafts((current) => ({ ...current, [person.employee_code]: { ...detail, [key]: value } })); const meterDifference = detail.machine_start_time !== '' && detail.machine_end_time !== '' ? Number(detail.machine_end_time) - Number(detail.machine_start_time) : null; const quantityEnabled = checked && detail.attendance !== 'Ausente' && (!usesSharedTotal || detail.attendance === 'Cantidad fija'); return <tr key={person.employee_code} className={checked ? 'is-selected' : ''}><td data-label="Persona"><label className="allocation-person-picker"><input type="checkbox" checked={checked} aria-label={`Incluir a ${person.full_name}`} onChange={(event) => { setSelectedPeople((current) => event.target.checked ? [...current, person.employee_code] : current.filter((code) => code !== person.employee_code)); if (event.target.checked && !Object.hasOwn(memberMachines, person.employee_code)) { const configured = members.find((member) => member.personnel_code === person.employee_code)?.machine_code ?? ''; setMemberMachines((current) => ({ ...current, [person.employee_code]: configured })) } }} /><span><b>{person.employee_code}</b><strong>{person.full_name}</strong></span></label></td><td data-label="Hs persona"><input aria-label={`Horas de ${person.full_name}`} type="number" min="0" max="24" step="0.25" disabled={!checked} value={detail.person_hours} onChange={(event) => updateDetail('person_hours', event.target.value)} /></td><td data-label="Cant. tarea">{quantityEnabled ? <input aria-label={`Cantidad de tarea de ${person.full_name}`} type="number" min="0" step={currentUnit.toUpperCase() === 'SC' ? '1' : '0.001'} required value={detail.quantity} onChange={(event) => updateDetail('quantity', event.target.value)} /> : detail.attendance === 'Ausente' ? '0' : usesSharedTotal && checked && quantity.trim() ? formatInputAmount(allocationPreview[person.employee_code] ?? 0) : '—'}</td><td data-label="U.M.">{currentUnit || '—'}</td><td data-label="ID vehículo">{selectedOperation?.task_type === 'Manual' ? '—' : <select aria-label={`Vehículo de ${person.full_name}`} disabled={!checked} value={assignedMachine} onChange={(event) => setMemberMachines((current) => ({ ...current, [person.employee_code]: event.target.value }))}><option value="">Sin vehículo</option>{eligibleMachines.map((item) => <option key={item.machine_code} value={item.machine_code}>{item.machine_code}</option>)}</select>}</td><td data-label="Marca y modelo">{machine ? `${machine.brand} ${machine.model}`.trim() : '—'}</td><td data-label="Medidor"><div className="allocation-meter-fields"><label><small>Inicio</small><input aria-label={`Medidor inicial de ${person.full_name}`} type="number" min="0" step="1" disabled={!checked || !assignedMachine} value={detail.machine_start_time} onChange={(event) => updateDetail('machine_start_time', event.target.value)} /></label><label><small>Fin</small><input aria-label={`Medidor final de ${person.full_name}`} type="number" min="0" step="1" disabled={!checked || !assignedMachine} value={detail.machine_end_time} onChange={(event) => updateDetail('machine_end_time', event.target.value)} /></label><b>Dif. {meterDifference === null ? '—' : meterDifference}</b></div></td><td data-label="Estado / reemplazo"><div className="allocation-extra-fields"><select aria-label={`Estado de ${person.full_name}`} disabled={!checked} value={detail.attendance} onChange={(event) => updateDetail('attendance', event.target.value)}><option>Presente</option><option>Ausente</option><option>Cantidad fija</option></select><input aria-label={`Reemplazo de ${person.full_name}`} list={`personnel-${person.employee_code}`} disabled={!checked} value={detail.replacement_code} onChange={(event) => updateDetail('replacement_code', event.target.value)} placeholder="Legajo reemplazo" /><datalist id={`personnel-${person.employee_code}`}>{catalogs.personnel.filter((item) => item.employee_code !== person.employee_code).map((item) => <option key={item.employee_code} value={item.employee_code}>{item.full_name}</option>)}</datalist></div></td></tr> })}</tbody></table></div>}</section>}
            {newPartStep === 2 && selectedOperation?.allows_inputs && <section className="form-section input-dose-section">
              <h2>Insumos y dosis</h2>
              <label className="input-search-label">Buscar insumos<input type="search" value={inputSearch} onChange={(event) => setInputSearch(event.target.value)} placeholder="Escribí el nombre o código del insumo…" onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); const selected = catalogs.inputs.find((item) => !inputLines.some((line) => line.input_code === item.input_code) && (item.description + ' ' + item.input_code).toLocaleLowerCase().includes(inputSearch.trim().toLocaleLowerCase())); if (selected) { setInputLines((rows) => [...rows, { input_code: selected.input_code, dose: '', quantity: '', unit: selected.unit }]); setInputSearch('') } } }} /><span className="input-search-results">{inputSearch.trim() && catalogs.inputs.filter((item) => !inputLines.some((line) => line.input_code === item.input_code) && (item.description + ' ' + item.input_code).toLocaleLowerCase().includes(inputSearch.trim().toLocaleLowerCase())).slice(0, 8).map((item) => <button type="button" key={item.input_code} onClick={() => { setInputLines((rows) => [...rows, { input_code: item.input_code, dose: '', quantity: '', unit: item.unit }]); setInputSearch('') }}>{item.description} · {item.input_code} · {item.unit || '-'}</button>)}</span></label>
              <div className="frequent-inputs"><small>Productos frecuentes</small><div>{frequentInputCodes.map((code) => { const item = catalogs.inputs.find((candidate) => candidate.input_code === code); return item ? <button type="button" className="secondary-button" key={item.input_code} disabled={inputLines.some((line) => line.input_code === item.input_code)} onClick={() => setInputLines((rows) => [...rows, { input_code: item.input_code, dose: '', quantity: '', unit: item.unit }])}>♧ {item.description}</button> : null })}</div></div>
              {inputLines.map((line, index) => { const item = catalogs.inputs.find((candidate) => candidate.input_code === line.input_code); const basisQuantity = completedWorkQuantity; const actualDose = basisQuantity > 0 && Number(line.quantity) > 0 ? calculateActualInputDose(Number(line.quantity), basisQuantity, line.unit) : null; const theoretical = basisQuantity > 0 && Number(line.dose) > 0 ? calculateInputTotal(basisQuantity, Number(line.dose), line.unit) : null; const doseUnit = inputDoseUnit(line.unit); return <div className="input-dose-row" key={line.input_code + '-' + index}>
                <div><b>{item?.description ?? line.input_code}</b><small>Código {line.input_code} · Unidad {line.unit || '-'}</small></div>
                <label>Dosis teórica ({doseUnit} / {currentUnit || 'unidad'})<input type="number" min="0" step="0.001" value={line.dose} onChange={(event) => setInputLines((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, dose: event.target.value } : row))} /></label>
                <label>Consumo real<input type="number" min="0" step="0.1" value={line.quantity} onChange={(event) => setInputLines((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, quantity: event.target.value } : row))} /></label>
                <div className="dose-result"><small>Dosis real</small><b>{actualDose === null ? '—' : formatInputAmount(actualDose)}</b><small>Teórico: {theoretical === null ? '—' : formatInputAmount(theoretical)}</small></div>
                <button type="button" className="text-button" onClick={() => setInputLines((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}>Quitar</button>
              </div> })}
              {catalogs.inputs.length === 0 && <p className="helper-text">El catálogo de insumos todavía no está cargado en Supabase.</p>}
            </section>}
        {newPartStep === 1 && <div className="form-actions"><span>Fecha, finca y lote corresponden al parte y a la tarea.</span><button className="primary-button" type="button" disabled={!farmId || !lotId || !effectiveCostCenter} onClick={() => setNewPartStep(2)}>Continuar a tarea <ArrowUp size={16} /></button></div>}
        {newPartStep === 2 && <div className="form-actions"><button className="primary-button" type="button" disabled={!operationCode || !quantity.trim() || !Number.isFinite(Number(quantity)) || Number(quantity) <= 0} onClick={() => void continueToStaffStep()}>Continuar a personal y vehículos <ArrowUp size={16} /></button></div>}
        {newPartStep === 3 && <div className="form-actions"><button className="primary-button" type="submit" disabled={loading || !selectedFront || !selectedLot || !selectedOperation}>{loading ? 'Preparando…' : 'Confirmar tarea'}</button></div>}
        {newPartStep === 4 && <div className="form-actions"><span>El parte completo se guarda después de revisar todas las tareas.</span></div>}
      </form>}
      <footer>Asistente de parte diario <span>·</span> Versión de trabajo</footer>
    </section>
  </main>
}
