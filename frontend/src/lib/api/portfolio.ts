import { api } from './client'

export interface MfImportBatchOut {
  id: string
  user_id: number
  statement_date: string | null
  investor_name: string | null
  pan: string | null
  source_filename: string
  total_holdings: number
  total_value: string
  created_at: string
}

export interface MfHoldingOut {
  id: string
  batch_id: string
  user_id: number
  amc_name: string
  scheme_name: string
  folio_number: string
  isin: string | null
  units: string
  nav: string
  current_value: string
  as_of_date: string | null
  created_at: string
}

export interface MfImportBatchDetail extends MfImportBatchOut {
  holdings: MfHoldingOut[]
}

export interface ManualAssetOut {
  id: string
  user_id: number
  asset_type: string
  name: string
  institution: string | null
  current_value: string
  purchase_value: string | null
  purchase_date: string | null
  maturity_date: string | null
  units: string | null
  unit_price: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ManualAssetCreate {
  asset_type: string
  name: string
  institution?: string
  current_value: string
  purchase_value?: string
  purchase_date?: string
  maturity_date?: string
  units?: string
  unit_price?: string
  notes?: string
}

export interface ManualAssetUpdate {
  asset_type?: string
  name?: string
  institution?: string
  current_value?: string
  purchase_value?: string
  purchase_date?: string
  maturity_date?: string
  units?: string
  unit_price?: string
  notes?: string
}

export interface AssetBreakdownItem {
  asset_type: string
  label: string
  total_value: string
  count: number
}

export interface EquitySummary {
  current_value: string
  cost_basis: string
  unrealized_pnl: string
  position_count: number
}

export interface MfSummary {
  current_value: string
  holding_count: number
  last_imported: string | null
}

export interface ManualSummary {
  current_value: string
  count: number
  breakdown: AssetBreakdownItem[]
}

export interface NetWorthOut {
  equity: EquitySummary
  mutual_funds: MfSummary
  manual_assets: ManualSummary
  total_net_worth: string
  as_of: string
}

// ── CAS upload ─────────────────────────────────────────────────────────────────

export function uploadCas(file: File): Promise<MfImportBatchOut> {
  const form = new FormData()
  form.append('file', file)
  return api.postForm<MfImportBatchOut>('/portfolio/cas/upload', form)
}

export function listBatches(): Promise<MfImportBatchOut[]> {
  return api.get<MfImportBatchOut[]>('/portfolio/cas/batches')
}

export function getBatch(batchId: string): Promise<MfImportBatchDetail> {
  return api.get<MfImportBatchDetail>(`/portfolio/cas/batches/${batchId}`)
}

export function deleteBatch(batchId: string): Promise<void> {
  return api.delete<void>(`/portfolio/cas/batches/${batchId}`)
}

// ── Manual assets ──────────────────────────────────────────────────────────────

export function createAsset(payload: ManualAssetCreate): Promise<ManualAssetOut> {
  return api.post<ManualAssetOut>('/portfolio/assets', payload)
}

export function listAssets(assetType?: string): Promise<ManualAssetOut[]> {
  const qs = assetType ? `?asset_type=${assetType}` : ''
  return api.get<ManualAssetOut[]>(`/portfolio/assets${qs}`)
}

export function updateAsset(id: string, payload: ManualAssetUpdate): Promise<ManualAssetOut> {
  return api.put<ManualAssetOut>(`/portfolio/assets/${id}`, payload)
}

export function deleteAsset(id: string): Promise<void> {
  return api.delete<void>(`/portfolio/assets/${id}`)
}

// ── Net worth ──────────────────────────────────────────────────────────────────

export function getNetWorth(): Promise<NetWorthOut> {
  return api.get<NetWorthOut>('/portfolio/net-worth')
}
