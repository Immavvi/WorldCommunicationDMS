import { apiRequest } from "./client";

export type Requirement = {
  id: string; requirement_number: string; project_id: string; loa_id?: string;
  requirement_date: string; status: string;
  lines: Array<{ id: string; description: string; required_quantity: string }>;
};
export type PurchaseOrder = {
  id: string; po_number: string; po_date: string; vendor_party_id: string; project_id: string;
  loa_id?: string; tax_mode: string; status: string; subtotal: string; taxable_amount: string;
  cgst_amount: string; sgst_amount: string; igst_amount: string; grand_total: string;
  vendor_snapshot: Record<string, string>; shipping_address_snapshot: Record<string, string>;
  lines: Array<{ id: string; line_number: number; description: string; unit_id: string;
    ordered_quantity: string; unit_rate: string; discount_percent: string; cgst_percent: string;
    sgst_percent: string; igst_percent: string; taxable_amount: string; line_total: string }>;
};
export type Commitment = { contractual_item_id: string; origin: string;
  approved_quantity: string; committed_quantity: string; remaining_quantity: string };

export const listRequirements = (token: string) =>
  apiRequest<Requirement[]>("/procurement-requirements", { token });
export const createRequirement = (token: string, data: Record<string, unknown>) =>
  apiRequest<Requirement>("/procurement-requirements", { method: "POST", token, body: JSON.stringify(data) });
export const getRequirement = (token: string, id: string) =>
  apiRequest<Requirement>(`/procurement-requirements/${id}`, { token });
export const transitionRequirement = (token: string, id: string, action: string, reason: string) =>
  apiRequest<Requirement>(`/procurement-requirements/${id}/actions`, { method: "POST", token, body: JSON.stringify({ action, reason }) });
export const listPurchaseOrders = (token: string) =>
  apiRequest<PurchaseOrder[]>("/purchase-orders", { token });
export const createPurchaseOrder = (token: string, data: Record<string, unknown>) =>
  apiRequest<PurchaseOrder>("/purchase-orders", { method: "POST", token, body: JSON.stringify(data) });
export const getPurchaseOrder = (token: string, id: string) =>
  apiRequest<PurchaseOrder>(`/purchase-orders/${id}`, { token });
export const transitionPurchaseOrder = (token: string, id: string, action: string, reason: string) =>
  apiRequest<PurchaseOrder>(`/purchase-orders/${id}/actions`, { method: "POST", token, body: JSON.stringify({ action, reason }) });
export const updatePurchaseOrderLine = (token: string, poId: string, lineId: string, data: Record<string, unknown>) =>
  apiRequest<PurchaseOrder>(`/purchase-orders/${poId}/lines/${lineId}`, { method: "PUT", token, body: JSON.stringify(data) });
export const getCommitments = (token: string, loaId: string) =>
  apiRequest<Commitment[]>(`/loas/${loaId}/procurement-commitments`, { token });
