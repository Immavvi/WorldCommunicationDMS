import { apiRequest } from "./client";

export type Project = {
  id: string; code: string; name: string; work_reference?: string; customer_party_id: string;
  business_scope: "RAILWAY" | "NON_RAILWAY"; railway_zone_id?: string;
  railway_division_id?: string; status: string; is_active: boolean;
};
export type Loa = {
  id: string; project_id: string; loa_number: string; loa_date: string; description?: string;
  original_contract_value: string; status: string; is_active: boolean;
};
export type LoaItem = {
  id: string; item_number: string; description: string; unit_id: string;
  original_approved_quantity: string; contractual_rate: string; original_line_value: string;
};
export type VariationLine = {
  id: string; loa_item_id?: string; product_id?: string; description: string; hsn_code_id?: string; unit_id: string;
  direction: "POSITIVE" | "NEGATIVE"; quantity: string; rate: string; line_value: string;
};
export type Variation = {
  id: string; reference_number: string; variation_date: string; status: string;
  remarks?: string; lines: VariationLine[];
};
export type ApprovedPosition = {
  loa_id: string; original_total: string; variation_total: string; current_approved_total: string;
  lines: Array<{ contractual_item_id: string; origin: "ORIGINAL_LOA" | "VARIATION";
    loa_item_id?: string; originating_variation_id?: string; originating_variation_reference?: string;
    item_number: string; description: string;
    original_quantity: string; positive_variation_quantity: string;
    negative_variation_quantity: string; current_approved_quantity: string;
    contractual_rate: string; original_value: string; variation_value: string;
    current_approved_value: string }>;
};

export const listProjects = (token: string) => apiRequest<Project[]>("/projects", { token });
export const createProject = (token: string, data: Record<string, unknown>) =>
  apiRequest<Project>("/projects", { method: "POST", token, body: JSON.stringify(data) });
export const listLoas = (token: string, projectId?: string) =>
  apiRequest<Loa[]>(`/loas${projectId ? `?project_id=${projectId}` : ""}`, { token });
export const createLoa = (token: string, data: Record<string, unknown>) =>
  apiRequest<Loa>("/loas", { method: "POST", token, body: JSON.stringify(data) });
export const getLoa = (token: string, id: string) => apiRequest<Loa>(`/loas/${id}`, { token });
export const listLoaItems = (token: string, id: string) =>
  apiRequest<LoaItem[]>(`/loas/${id}/items`, { token });
export const createLoaItem = (token: string, id: string, data: Record<string, unknown>) =>
  apiRequest<LoaItem>(`/loas/${id}/items`, { method: "POST", token, body: JSON.stringify(data) });
export const listVariations = (token: string, id: string) =>
  apiRequest<Variation[]>(`/loas/${id}/variations`, { token });
export const createVariation = (token: string, id: string, data: Record<string, unknown>) =>
  apiRequest<Variation>(`/loas/${id}/variations`, { method: "POST", token, body: JSON.stringify(data) });
export const transitionVariation = (token: string, id: string, action: string, reason: string) =>
  apiRequest<Variation>(`/variations/${id}/actions`, {
    method: "POST", token, body: JSON.stringify({ action, reason }),
  });
export const getApprovedPosition = (token: string, id: string) =>
  apiRequest<ApprovedPosition>(`/loas/${id}/approved-position`, { token });
