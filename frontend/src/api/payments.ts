import { apiRequest } from "./client";

export type Allocation = { id: string; tax_invoice_id: string; allocated_amount: string; invoice_number_snapshot: string };
export type Payment = { id: string; receipt_number: string; receipt_date: string; customer_party_id: string; organization_id: string; payment_mode: string; transaction_reference: string | null; amount_received: string; status: string; customer_snapshot: Record<string, string>; allocations: Allocation[]; allocated_amount: string; unallocated_amount: string };
export type Receivable = { tax_invoice_id: string; invoice_number: string; customer_name: string; project_name: string | null; loa_number: string | null; due_date: string | null; invoice_total: string; received_amount: string; outstanding_amount: string; payment_status: string; days_overdue: number };
export type EligibleInvoice = { tax_invoice_id: string; invoice_number: string; outstanding_amount: string; project_name: string | null };

export const listPayments = (token: string) => apiRequest<Payment[]>("/payments", { token });
export const listReceivables = (token: string, query = "") => apiRequest<Receivable[]>(`/receivables${query ? `?${query}` : ""}`, { token });
export const eligibleInvoices = (token: string, id: string) => apiRequest<EligibleInvoice[]>(`/payments/${id}/eligible-invoices`, { token });
export const createPayment = (token: string, body: unknown) => apiRequest<Payment>("/payments", { method: "POST", token, body: JSON.stringify(body) });
export const allocatePayment = (token: string, id: string, body: unknown) => apiRequest<Payment>(`/payments/${id}/allocations`, { method: "POST", token, body: JSON.stringify(body) });
export const paymentAction = (token: string, id: string, action: string, reason: string) => apiRequest<Payment>(`/payments/${id}/actions`, { method: "POST", token, body: JSON.stringify({ action, reason }) });
