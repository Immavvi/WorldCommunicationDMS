import { apiRequest } from "./client";

export type LoaImportLine = {
  id: string; line_number: number; product_id?: string;
  candidate_key?: string; source_order?: number; group_id?: string;
  description?: string; description_raw?: string; description_normalized?: string;
  hsn_text?: string; hsn_code_id?: string; unit_text?: string; uom_raw?: string; uom_normalized?: string;
  unit_id?: string; quantity?: string; rate?: string; amount?: string;
  oem_make?: string; model_number?: string; tax_text?: string; remarks?: string;
  source_page?: number; source_page_start?: number; source_page_end?: number;
  source_serial?: string; source_raw_text?: string; extraction_method?: string;
  extraction_confidence?: string; extraction_issues?: string[];
  extraction_outcome: "EXTRACTED" | "NEEDS_REVIEW" | "REJECTED_WITH_REASON" | "EXPLICITLY_IGNORED_BY_OWNER";
  extraction_issue?: string;
};
export type LoaImportGroup = { id:string; sequence:number; source_key:string; title_raw:string; title_normalized:string; source_kind:string; source_page_start?:number; source_page_end?:number; source_total?:string; extracted_total?:string; difference?:string; reconciliation_status:string };
export type LoaImportSchedule = { id:string; sequence:number; source_key:string; title_raw:string; title_normalized:string; source_page_start?:number; source_page_end?:number; source_total?:string; extracted_total?:string; difference?:string; reconciliation_status:string; groups:LoaImportGroup[] };
export type LoaImport = {
  id: string; original_filename: string; mime_type: string; extension: string;
  size_bytes: number; uploaded_by_user_id: string; uploaded_at: string; status: string;
  extraction_method?: string; extraction_error?: string; extraction_warnings: string[];
  project_id?: string; railway_zone_id?: string; railway_division_id?: string;
  authority_id?: string; issuing_party_id?: string; loa_id?: string;
  extracted_zone_text?: string; extracted_division_text?: string; authority_text?: string;
  loa_number?: string; tender_reference?: string; loa_date?: string;
  completion_period?: string; completion_date?: string; work_description?: string;
  contract_value?: string; duplicate_candidates: Array<{id:string;loa_number:string;project_id:string}>;
  project_candidates: Array<{id:string;code:string;name:string;reason:string}>;
  authority_candidates: Array<{text:string;role:string;source:string;master_id?:string;master_status?:"MATCHED"|"NOT_CONFIGURED"|"AMBIGUOUS";master_detail?:string}>;
  boq_reconciliation: Record<string, unknown>;
  boq_readiness_issues: Array<{scope:string;line_number?:number;field:string;message:string}>;
  completion_date_provenance?: "SOURCE_EXTRACTED" | "DERIVED" | "OWNER_CORRECTED" | "WAITING_FOR_LOA_DATE";
  loa_date_provenance?: "SOURCE_EXTRACTED" | "OWNER_CORRECTED";
  loa_date_source?: string;
  lines: LoaImportLine[];
  schedules?: LoaImportSchedule[];
};

export function uploadRailwayLoa(token: string, file: File): Promise<LoaImport> {
  const body = new FormData(); body.append("file", file);
  return apiRequest<LoaImport>("/railway-loa-imports", { method: "POST", token, body });
}
export const listLoaImports = (token: string) => apiRequest<LoaImport[]>("/railway-loa-imports", { token });
export const getLoaImport = (token: string, id: string) => apiRequest<LoaImport>(`/railway-loa-imports/${id}`, { token });
export const saveLoaImportReview = (token: string, id: string, data: Record<string, unknown>) => apiRequest<LoaImport>(`/railway-loa-imports/${id}`, { method: "PATCH", token, body: JSON.stringify(data) });
export const retryLoaImport = (token: string, id: string) => apiRequest<LoaImport>(`/railway-loa-imports/${id}/retry`, { method: "POST", token });
export const resolveLoaImportMasters = (token: string, id: string) => apiRequest<LoaImport>(`/railway-loa-imports/${id}/resolve-masters`, { method: "POST", token });
export const mapRailwayCustomer = (token: string, id: string, customerPartyId: string) => apiRequest<LoaImport>(`/railway-loa-imports/${id}/customer-mapping`, { method: "POST", token, body: JSON.stringify({ customer_party_id: customerPartyId }) });
export const approveLoaImport = (token: string, id: string, data: Record<string, unknown> = {}) => apiRequest<LoaImport>(`/railway-loa-imports/${id}/approve`, { method: "POST", token, body: JSON.stringify(data) });
export const cancelLoaImport = (token: string, id: string) => apiRequest<LoaImport>(`/railway-loa-imports/${id}/cancel`, { method: "POST", token });

export async function openOriginalLoa(token: string, id: string, filename: string): Promise<void> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? "/api/v1"}/railway-loa-imports/${id}/original`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error("Unable to open original LOA.");
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a"); anchor.href = url; anchor.target = "_blank"; anchor.download = filename.endsWith(".xlsx") ? filename : ""; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}
