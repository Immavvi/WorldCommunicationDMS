import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import App from "../src/App";
import { getCurrentUser } from "../src/api/auth";

vi.mock("../src/api/auth", () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
}));

vi.mock("../src/api/contracts", () => ({
  listProjects: vi.fn().mockResolvedValue([]),
  listLoas: vi.fn().mockResolvedValue([]),
  createProject: vi.fn(),
  createLoa: vi.fn(),
  getLoa: vi.fn().mockResolvedValue({
    id: "loa-1", project_id: "project-1", loa_number: "LOA/001", loa_date: "2026-08-24",
    original_contract_value: "100.00", status: "ACTIVE", is_active: true,
  }),
  listLoaItems: vi.fn().mockResolvedValue([]),
  listVariations: vi.fn().mockResolvedValue([{ id: "variation-1", reference_number: "VAR/1", variation_date: "2026-08-25", status: "DRAFT", lines: [] }]),
  getApprovedPosition: vi.fn().mockResolvedValue({ loa_id: "loa-1", lines: [], original_total: "100.00", variation_total: "0.00", current_approved_total: "100.00" }),
  createLoaItem: vi.fn(),
  createVariation: vi.fn(),
  transitionVariation: vi.fn(),
}));

vi.mock("../src/api/masterData", () => ({
  listMasterData: vi.fn().mockResolvedValue({ items: [], total: 0, offset: 0, limit: 50 }),
  listTermsVersions: vi.fn().mockResolvedValue([]),
}));

vi.mock("../src/api/procurement", () => ({
  listRequirements: vi.fn().mockResolvedValue([]),
  listPurchaseOrders: vi.fn().mockResolvedValue([]),
  createRequirement: vi.fn(), createPurchaseOrder: vi.fn(), transitionPurchaseOrder: vi.fn(),
  updatePurchaseOrderLine: vi.fn(),
  getCommitments: vi.fn().mockResolvedValue([]), transitionRequirement: vi.fn(),
  getRequirement: vi.fn().mockResolvedValue({ id: "pr-1", requirement_number: "PR-000001", status: "DRAFT", lines: [] }),
  getPurchaseOrder: vi.fn().mockResolvedValue({ id: "po-1", po_number: "PO-000001", status: "SUBMITTED", vendor_snapshot: { legal_name: "Vendor" }, shipping_address_snapshot: { address_line_1: "Warehouse" }, lines: [], grand_total: "100.00" }),
}));

vi.mock("../src/api/receiving", () => ({
  listReceipts: vi.fn().mockResolvedValue([]), getReceiptPosition: vi.fn().mockResolvedValue([]),
  createReceipt: vi.fn(), transitionReceipt: vi.fn(),
  updateReceiptLine: vi.fn(),
  getReceipt: vi.fn().mockResolvedValue({ id: "grn-1", receipt_number: "GRN-000001",
    po_number_snapshot: "PO-000001", vendor_snapshot: { legal_name: "Vendor" },
    status: "RECEIVED", lines: [] }),
}));

vi.mock("../src/api/assets", () => ({
  listAssets: vi.fn().mockResolvedValue([{
    id: "asset-1", asset_number: "AST-000001", manufacturer_serial_number: "SERIAL-1",
    product_snapshot: "Managed switch", oem_snapshot: "OEM", model_snapshot: "MODEL-1",
    status: "AVAILABLE", project_snapshot: "Railway Project", loa_snapshot: "LOA/1",
    current_site: "Station A", current_building: null, current_room: "OFC Room",
    current_rack: null, current_position: null, warranty_expiry_date: "2027-08-24",
    events: [{ id: "event-1", event_type: "REGISTER", from_status: null,
      to_status: "REGISTERED", to_location_snapshot: null, event_at: "2026-08-24T10:00:00Z",
      reason: "Receipt registration" }],
  }]),
  assetRegistrationPositions: vi.fn().mockResolvedValue([{
    material_receipt_line_id: "receipt-line-1", receipt_number: "GRN-000001",
    product_snapshot: "Managed switch", accepted_quantity: 10, already_registered: 7,
    remaining_quantity: 3,
  }]),
  registerAssets: vi.fn(),
  transitionAsset: vi.fn(),
}));

vi.mock("../src/api/attention", () => ({
  listAlerts: vi.fn().mockResolvedValue([{ id:"alert-1", alert_type:"RECEIVABLE_DUE",
    severity:"HIGH", title:"Invoice overdue", message:"Invoice INV-1 is overdue.",
    source_entity_type:"tax_invoice", source_entity_id:"inv-1", project_id:"project-1",
    loa_id:null, triggered_at:"2026-08-24T10:00:00Z", due_date:"2026-08-20",
    status:"OPEN", assigned_role:"SUPER-ADMIN", resolution_reason:null }]),
  myAttention: vi.fn().mockResolvedValue([]), alertAction: vi.fn(), evaluateAlerts: vi.fn(),
  listRules: vi.fn().mockResolvedValue([{ id:"rule-1",rule_type:"RECEIVABLE_DUE",
    is_enabled:true,warning_days:7,severity:"MEDIUM" }]), updateRule: vi.fn(),
  listNotifications: vi.fn().mockResolvedValue([{id:"note-1",title:"Invoice overdue",
    message:"Invoice INV-1 is overdue.",action_url:"/tax-invoices/inv-1",is_read:false,
    created_at:"2026-08-24T10:00:00Z"}]),
  unreadCount: vi.fn().mockResolvedValue({count:1}), markRead: vi.fn(), markAllRead: vi.fn(),
}));

vi.mock("../src/api/dispatch", () => ({
  listChallans: vi.fn().mockResolvedValue([]),
  getDispatchAvailability: vi.fn().mockResolvedValue([]),
  createChallan: vi.fn(), transitionChallan: vi.fn(), acknowledgeChallan: vi.fn(), updateChallanLine: vi.fn(),
  getChallan: vi.fn().mockResolvedValue({ id: "ch-1", challan_number: "CH-000001",
    status: "DELIVERED", customer_snapshot: { legal_name: "Railway Customer" },
    delivery_address_snapshot: { address_line_1: "Railway Store" },
    dispatch_from_snapshot: {}, organization_snapshot: {}, lines: [
      { id: "line-1", line_number: 1, description_snapshot: "Network equipment",
        unit_snapshot: "Nos", dispatched_quantity: "2.0000", allocations: [] },
    ] }),
}));

vi.mock("../src/api/billing", () => ({
  listPis: vi.fn().mockResolvedValue([]), getBillablePosition: vi.fn().mockResolvedValue([]),
  createPi: vi.fn(), transitionPi: vi.fn(), updatePiLine: vi.fn(),
  getPi: vi.fn().mockResolvedValue({ id: "pi-1", pi_number: "PI-000001", status: "SUBMITTED",
    customer_snapshot: { legal_name: "Railway Customer" }, organization_snapshot: {},
    bill_to_snapshot: {}, ship_to_snapshot: {}, bank_snapshot: {}, lines: [],
    taxable_amount: "100.00", cgst_amount: "9.00", sgst_amount: "9.00", igst_amount: "0.00",
    grand_total: "118.00", amount_in_words: "Indian Rupees One Hundred Eighteen Only" }),
}));

vi.mock("../src/api/invoicing", () => ({
  listInvoices: vi.fn().mockResolvedValue([]), getInvoiceablePosition: vi.fn().mockResolvedValue([]),
  createInvoice: vi.fn(), updateInvoiceLine: vi.fn(), transitionInvoice: vi.fn(),
  getInvoice: vi.fn().mockResolvedValue({ id: "inv-1", invoice_number: "INV-000001",
    status: "SUBMITTED", customer_snapshot: { legal_name: "Railway Customer" },
    organization_snapshot: {}, organization_gst_snapshot: {}, bill_to_snapshot: {}, ship_to_snapshot: {},
    bank_snapshot: {}, lines: [], tax_mode: "INTRA_STATE", place_of_supply_state: "West Bengal",
    place_of_supply_state_code: "19", due_date: "2026-09-26", cgst_amount: "9.00",
    sgst_amount: "9.00", igst_amount: "0.00", grand_total: "118.00",
    amount_in_words: "Indian Rupees One Hundred Eighteen Only" }),
}));

vi.mock("../src/api/payments", () => ({
  listPayments: vi.fn().mockResolvedValue([{ id: "pay-1", receipt_number: "RCT-000001",
    receipt_date: "2026-08-28", customer_party_id: "customer-1", organization_id: "org-1",
    payment_mode: "NEFT", transaction_reference: "UTR-1", amount_received: "500.00",
    status: "DRAFT", customer_snapshot: { legal_name: "Customer" }, allocations: [],
    allocated_amount: "300.00", unallocated_amount: "200.00" }]),
  listReceivables: vi.fn().mockResolvedValue([{ tax_invoice_id: "inv-1",
    invoice_number: "INV-000001", customer_name: "Customer", project_name: "Project",
    loa_number: "LOA/1", due_date: "2026-08-20", invoice_total: "1180.00",
    received_amount: "500.00", outstanding_amount: "680.00",
    payment_status: "PARTIALLY_PAID_OVERDUE", days_overdue: 4 }]),
  eligibleInvoices: vi.fn().mockResolvedValue([]), createPayment: vi.fn(),
  allocatePayment: vi.fn(), paymentAction: vi.fn(),
}));

vi.mock("../src/api/quotations", () => ({
  listQuotations: vi.fn().mockResolvedValue([]), createQuotation: vi.fn(),
  updateQuotation: vi.fn(), addQuotationLine: vi.fn(), updateQuotationLine: vi.fn(),
  deleteQuotationLine: vi.fn(), transitionQuotation: vi.fn(), createQuotationRevision: vi.fn(),
  quotationHistory: vi.fn().mockResolvedValue([
    { id: "q-1", quotation_number: "QTN-000001", revision_number: 0, status: "SUBMITTED", is_latest: true },
  ]),
  getQuotation: vi.fn().mockResolvedValue({ id: "q-1", quotation_number: "QTN-000001",
    revision_number: 0, status: "SUBMITTED", is_latest: true, subject: "Network supply",
    validity_date: "2026-09-30", customer_snapshot: { legal_name: "Railway Customer" },
    tax_mode: "INTRA_STATE", place_of_supply_state: "West Bengal", place_of_supply_state_code: "19",
    lines: [], cgst_amount: "9.00", sgst_amount: "9.00", igst_amount: "0.00",
    grand_total: "118.00", amount_in_words: "Indian Rupees One Hundred Eighteen Only" }),
}));

const mockedGetCurrentUser = vi.mocked(getCurrentUser);

beforeEach(() => {
  sessionStorage.clear();
  window.history.replaceState({}, "", "/");
  vi.clearAllMocks();
});

afterEach(cleanup);

test("redirects unauthenticated visitors to the login page", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("shows user management only to a SUPER-ADMIN and logs out", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  mockedGetCurrentUser.mockResolvedValue({
    id: "super-admin-id",
    email: "superadmin@example.com",
    is_active: true,
    roles: [{ name: "SUPER-ADMIN" }],
  });

  render(<App />);

  expect(await screen.findByRole("link", { name: "Users" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Logout" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(sessionStorage.getItem("wcdms.access-token")).toBeNull();
});

test("denies an ADMIN direct access to the users page", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/users");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id",
    email: "admin@example.com",
    is_active: true,
    roles: [{ name: "ADMIN" }],
  });

  render(<App />);

  expect(await screen.findByRole("heading", { name: "Access denied" })).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument());
});

test("shows Master Data navigation to an ADMIN", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id",
    email: "admin@example.com",
    is_active: true,
    roles: [{ name: "ADMIN" }],
  });

  render(<App />);

  expect(await screen.findByRole("link", { name: "Master Data" })).toBeInTheDocument();
});

test("shows the Project and LOA workspace to an ADMIN", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/projects");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Projects & LOAs" })).toBeInTheDocument();
});

test("presents original variations and current approved position on LOA detail", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/loas/loa-1");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "LOA/001" })).toBeInTheDocument();
  expect(screen.getByText("ORIGINAL")).toBeInTheDocument();
  expect(screen.getByText("VARIATIONS")).toBeInTheDocument();
  expect(screen.getByText("CURRENT APPROVED")).toBeInTheDocument();
  expect(screen.getByText("DRAFT")).toBeInTheDocument();
});

test("shows procurement and searchable vendor selection to an ADMIN", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/procurement");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true,
    roles: [{ name: "ADMIN" }],
  });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Procurement & Purchase Orders" })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Search vendors" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Procurement & POs" })).toBeInTheDocument();
});

test("shows SUPER-ADMIN PO approval controls", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/purchase-orders/po-1");
  mockedGetCurrentUser.mockResolvedValue({
    id: "super-id", email: "super@example.com", is_active: true,
    roles: [{ name: "SUPER-ADMIN" }],
  });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "PO-000001" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
});

test("shows readable GRN creation workflow to an ADMIN", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/receiving");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com",
    is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "GRN / Material Receipts" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Purchase order" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "PO line" })).toBeInTheDocument();
});

test("shows receipt verification only to SUPER-ADMIN", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/material-receipts/grn-1");
  mockedGetCurrentUser.mockResolvedValue({ id: "super-id", email: "super@example.com",
    is_active: true, roles: [{ name: "SUPER-ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "GRN-000001" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Verify" })).toBeInTheDocument();
});

test("shows Asset register and remaining serial registration quantity", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/assets");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com",
    is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Assets" })).toBeInTheDocument();
  expect(screen.getByText(/Accepted: 10, Registered: 7, Remaining: 3/)).toBeInTheDocument();
  expect(screen.getByText("AST-000001")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Assets" })).toBeInTheDocument();
});

test("shows payment register and role-aware finance actions", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/payments");
  mockedGetCurrentUser.mockResolvedValue({ id: "super-id", email: "super@example.com",
    is_active: true, roles: [{ name: "SUPER-ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Customer Payments" })).toBeInTheDocument();
  expect(screen.getByText("RCT-000001")).toBeInTheDocument();
  expect(screen.getByText(/unallocated ₹200.00/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Receivables" })).toBeInTheDocument();
});

test("shows Alerts inbox, severity, rules, and notification count", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/alerts");
  mockedGetCurrentUser.mockResolvedValue({ id:"super-id",email:"super@example.com",
    is_active:true,roles:[{name:"SUPER-ADMIN"}] });
  render(<App />);
  expect(await screen.findByRole("heading",{name:"Alerts"})).toBeInTheDocument();
  expect(screen.getByText(/HIGH — Invoice overdue/)).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Acknowledge"})).toBeInTheDocument();
  expect(screen.getByRole("heading",{name:"Alert Rule Settings"})).toBeInTheDocument();
  expect(await screen.findByLabelText("Unread notifications")).toHaveTextContent("1");
  expect(screen.getByRole("link",{name:"Alerts"})).toBeInTheDocument();
});

test("shows derived receivable position", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/receivables");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com",
    is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Receivables" })).toBeInTheDocument();
  expect(screen.getByText("PARTIALLY_PAID_OVERDUE (4 days)")).toBeInTheDocument();
  expect(screen.getByText("₹680.00")).toBeInTheDocument();
});

test("shows verified-material Challan workflow without commercial fields", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/dispatch");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com",
    is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Supply Challan & Dispatch" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Verified material" })).toBeInTheDocument();
  expect(screen.queryByText(/purchase rate|vendor cost|margin/i)).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Challans / Dispatch" })).toBeInTheDocument();
});

test("records acknowledgement from delivered Challan detail", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/supply-challans/ch-1");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com",
    is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "CH-000001" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Dispatched material" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Record acknowledgement" })).toBeInTheDocument();
  expect(screen.queryByText(/purchase rate|vendor cost|margin/i)).not.toBeInTheDocument();
});

test("shows PI creation from eligible dispatched material without procurement costs", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token"); window.history.replaceState({}, "", "/proforma-invoices");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Proforma Invoices" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Billable dispatch" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Proforma Invoices" })).toBeInTheDocument();
  expect(screen.queryByText(/vendor rate|purchase cost|margin/i)).not.toBeInTheDocument();
});

test("shows backend-calculated PI totals and SUPER-ADMIN approval", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token"); window.history.replaceState({}, "", "/proforma-invoices/pi-1");
  mockedGetCurrentUser.mockResolvedValue({ id: "super-id", email: "super@example.com", is_active: true, roles: [{ name: "SUPER-ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "PI-000001" })).toBeInTheDocument();
  expect(screen.getByText("Indian Rupees One Hundred Eighteen Only")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
});

test("shows Tax Invoice creation from invoiceable PI quantity", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token"); window.history.replaceState({}, "", "/tax-invoices");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Tax Invoices & Billing" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Invoiceable PI line" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Tax Invoices" })).toBeInTheDocument();
  expect(screen.queryByText(/vendor rate|purchase cost|margin/i)).not.toBeInTheDocument();
});

test("shows Invoice tax mode due date totals and SUPER-ADMIN approval", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token"); window.history.replaceState({}, "", "/tax-invoices/inv-1");
  mockedGetCurrentUser.mockResolvedValue({ id: "super-id", email: "super@example.com", is_active: true, roles: [{ name: "SUPER-ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "INV-000001" })).toBeInTheDocument();
  expect(screen.getByText(/Place of supply: West Bengal/)).toBeInTheDocument();
  expect(screen.getByText("Due date: 2026-09-26")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download / Preview PDF" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download / Preview Excel" })).toBeInTheDocument();
});

test("shows readable independent Quotation creation", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token"); window.history.replaceState({}, "", "/quotations");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Quotation Management" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Customer" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Free-text item" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Quotations" })).toBeInTheDocument();
  expect(screen.queryByText(/vendor rate|purchase cost|margin/i)).not.toBeInTheDocument();
});

test("shows Quotation revision history and SUPER-ADMIN approval", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token"); window.history.replaceState({}, "", "/quotations/q-1");
  mockedGetCurrentUser.mockResolvedValue({ id: "super-id", email: "super@example.com", is_active: true, roles: [{ name: "SUPER-ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "QTN-000001 / Revision 0" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Revision history" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
});
