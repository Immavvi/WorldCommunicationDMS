import { apiRequest } from "./client";

export type DispatchAvailability = {
  material_receipt_line_id: string;
  description: string;
  unit: string;
  contractual_item_id?: string;
  contract_origin?: "ORIGINAL_LOA" | "VARIATION";
  verified_accepted_quantity: string;
  allocated_dispatched_quantity: string;
  available_quantity: string;
  approved_contract_quantity?: string;
  previously_dispatched_contract_quantity: string;
  remaining_contract_quantity?: string;
};

export type ChallanLine = {
  id: string; line_number: number; description_snapshot: string; hsn_snapshot?: string;
  unit_snapshot: string; dispatched_quantity: string;
  allocations: Array<{ id: string; material_receipt_line_id: string; allocated_quantity: string }>;
};

export type SupplyChallan = {
  id: string; challan_number: string; challan_date: string; project_id: string; loa_id?: string;
  business_scope: "RAILWAY" | "NON_RAILWAY"; status: string;
  customer_snapshot: Record<string, string>; division_snapshot?: Record<string, string>;
  consignee_snapshot?: Record<string, string>; delivery_address_snapshot: Record<string, string>;
  dispatch_from_snapshot: Record<string, string>; organization_snapshot: Record<string, string>;
  vehicle_number?: string; transporter?: string; acknowledgement_reference?: string;
  receiving_authority_text?: string; acknowledged_date?: string; lines: ChallanLine[];
};

export const listChallans = (token: string) => apiRequest<SupplyChallan[]>("/supply-challans", { token });
export const getChallan = (token: string, id: string) => apiRequest<SupplyChallan>(`/supply-challans/${id}`, { token });
export const createChallan = (token: string, data: Record<string, unknown>) => apiRequest<SupplyChallan>("/supply-challans", { method: "POST", token, body: JSON.stringify(data) });
export const getDispatchAvailability = (token: string, projectId: string) => apiRequest<DispatchAvailability[]>(`/dispatch-availability?project_id=${projectId}`, { token });
export const transitionChallan = (token: string, id: string, action: string, reason: string) => apiRequest<SupplyChallan>(`/supply-challans/${id}/actions`, { method: "POST", token, body: JSON.stringify({ action, reason }) });
export const acknowledgeChallan = (token: string, id: string, data: Record<string, unknown>) => apiRequest<SupplyChallan>(`/supply-challans/${id}/acknowledgement`, { method: "POST", token, body: JSON.stringify(data) });
export const updateChallanLine = (token: string, challanId: string, lineId: string, data: Record<string, unknown>) => apiRequest<SupplyChallan>(`/supply-challans/${challanId}/lines/${lineId}`, { method: "PUT", token, body: JSON.stringify(data) });
