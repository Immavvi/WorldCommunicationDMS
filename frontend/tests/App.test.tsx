import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import App from "../src/App";
import { ApiError } from "../src/api/client";
import { changePassword, getCurrentUser } from "../src/api/auth";
import { createUser, listUsers, resetUserPassword, setUserActive } from "../src/api/users";
import { createMasterData, deleteMasterData, listMasterData, setPrimaryOrganization } from "../src/api/masterData";
import { getLoaImport, resolveLoaImportMasters } from "../src/api/loaImports";

vi.mock("../src/api/auth", () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  changePassword: vi.fn(),
}));

vi.mock("../src/api/users", () => ({
  listUsers: vi.fn().mockResolvedValue({ items: [], offset: 0, limit: 50 }),
  createUser: vi.fn().mockResolvedValue({}),
  assignUserRole: vi.fn().mockResolvedValue({}),
  setUserActive: vi.fn().mockResolvedValue({}),
  resetUserPassword: vi.fn().mockResolvedValue(undefined),
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

vi.mock("../src/api/loaImports", () => ({
  uploadRailwayLoa: vi.fn().mockResolvedValue({ id: "import-1" }),
  getLoaImport: vi.fn().mockResolvedValue({
    id: "import-1", original_filename: "Railway LOA.xlsx", mime_type: "application/xlsx",
    extension: "xlsx", size_bytes: 2048, uploaded_by_user_id: "admin-id",
    uploaded_at: "2026-08-24T10:00:00Z", status: "NEEDS_REVIEW",
    extraction_method: "XLSX", extraction_warnings: ["UOM needs review"],
    duplicate_candidates: [], loa_number: "LOA/RAIL/20", loa_date: "2026-08-24",
    railway_zone_id: "zone-1", railway_division_id: "division-1",
    loa_date_provenance: "SOURCE_EXTRACTED", loa_date_source: "Semantic LOA date label",
    completion_period: "6 months", completion_date: "2027-02-24",
    completion_date_provenance: "DERIVED", project_candidates: [],
    authority_candidates: [{ text: "SSE/TELE/STORE", role: "CONSIGNEE", source: "Consignee label" }],
    boq_reconciliation: { source_rows_detected: 12, extracted_successfully: 11,
      needs_review: 1, document_coverage_status: "COMPLETE", complete: false },
    boq_readiness_issues: [{ scope: "LINE", line_number: 12, field: "outcome",
      message: "Schedule A - Sn. 12 remains needs review." }],
    work_description: "Railway communication supply", contract_value: "2469.00",
    schedules: [{ id: "schedule-1", sequence: 1, source_key: "schedule-a",
      title_raw: "Schedule A", title_normalized: "Schedule A", reconciliation_status: "NEEDS_REVIEW",
      groups: [{ id: "group-1", sequence: 1, source_key: "group-1",
        title_raw: "Awarded Quantities And Rates", title_normalized: "Awarded Quantities And Rates",
        source_kind: "AWARDED", reconciliation_status: "NEEDS_REVIEW" }] }],
    lines: Array.from({ length: 12 }, (_, index) => ({ id: `line-${index + 1}`,
      line_number: index + 1, group_id: "group-1", source_serial: String(index + 1),
      description: index === 11 ? "Unresolved equipment" : `IP communication terminal ${index + 1}`,
      unit_text: "Nos", quantity: "3.0000", rate: "823.00", amount: "2469.00",
      extraction_outcome: index === 11 ? "NEEDS_REVIEW" : "EXTRACTED" })),
  }),
  saveLoaImportReview: vi.fn(), retryLoaImport: vi.fn(), resolveLoaImportMasters: vi.fn(), approveLoaImport: vi.fn(),
  cancelLoaImport: vi.fn(), openOriginalLoa: vi.fn(), mapRailwayCustomer: vi.fn(),
}));

vi.mock("../src/api/masterData", () => ({
  listMasterData: vi.fn().mockResolvedValue({ items: [], total: 0, offset: 0, limit: 50 }),
  createMasterData: vi.fn().mockResolvedValue({}),
  updateMasterData: vi.fn().mockResolvedValue({}),
  deleteMasterData: vi.fn().mockResolvedValue(undefined),
  setPrimaryOrganization: vi.fn().mockResolvedValue({}),
  setMasterDataActive: vi.fn().mockResolvedValue({}),
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

vi.mock("../src/api/reporting", () => ({
  getDashboard: vi.fn().mockResolvedValue({operational:{active_projects:3,
    overdue_deliveries:1,my_attention:2,unread_notifications:1},financial:{invoice_value:"125000.00",
    received:"50000.00",outstanding:"75000.00",overdue_invoices:1}}),
  getReport: vi.fn().mockResolvedValue([{id:"po-1",number:"PO-000001",vendor:"Vendor",
    project:"Project",status:"ISSUED",ordered_quantity:"10.0000"}]),
  exportReport: vi.fn(),
}));

vi.mock("../src/api/administration", () => ({
  getNumbering: vi.fn().mockResolvedValue([{
    id: "series-1", document_type: "PURCHASE_ORDER", prefix: "PO-",
    next_number: 42, padding: 6, preview: "PO-000042",
  }]),
  getSystemStatus: vi.fn().mockResolvedValue({
    status: "healthy", application: "WCDMS", version: "0.1.0",
    environment: "test", database: "connected", schema_revision: "test-schema",
  }),
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
const mockedChangePassword = vi.mocked(changePassword);
const mockedCreateUser = vi.mocked(createUser);
const mockedListUsers = vi.mocked(listUsers);
const mockedResetUserPassword = vi.mocked(resetUserPassword);
const mockedSetUserActive = vi.mocked(setUserActive);
const mockedListMasterData = vi.mocked(listMasterData);
const mockedCreateMasterData = vi.mocked(createMasterData);
const mockedDeleteMasterData = vi.mocked(deleteMasterData);
const mockedSetPrimaryOrganization = vi.mocked(setPrimaryOrganization);

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

test("shows role-aware management dashboard and drill-down cards", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  mockedGetCurrentUser.mockResolvedValue({id:"super-id",email:"super@example.com",
    is_active:true,roles:[{name:"SUPER-ADMIN"}]});
  render(<App />);
  expect(await screen.findByRole("heading",{name:"Dashboard"})).toBeInTheDocument();
  expect(screen.getByText("Active Projects")).toBeInTheDocument();
  expect(screen.getByText("Finance & Collections")).toBeInTheDocument();
  expect(screen.getByText("₹1,25,000.00")).toBeInTheDocument();
  expect(screen.getByRole("link",{name:"Reports"})).toBeInTheDocument();
});

test("shows grouped reports, filters, table and Excel control", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({},"","/reports?report=purchase-orders");
  mockedGetCurrentUser.mockResolvedValue({id:"admin-id",email:"admin@example.com",
    is_active:true,roles:[{name:"ADMIN"}]});
  render(<App />);
  expect(await screen.findByRole("heading",{name:"Reports"})).toBeInTheDocument();
  expect(await screen.findByText("PO-000001")).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Export Excel"})).toBeInTheDocument();
  expect(screen.queryByRole("button",{name:"receivables"})).not.toBeInTheDocument();
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

  expect(await screen.findByRole("link", { name: "Administration" })).toBeInTheDocument();
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
  await waitFor(() => expect(screen.queryByRole("link", { name: "Administration" })).not.toBeInTheDocument());
});

test("shows safe administration status and read-only numbering to SUPER-ADMIN", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/administration");
  mockedGetCurrentUser.mockResolvedValue({
    id: "super-admin-id", email: "superadmin@example.com", is_active: true,
    roles: [{ name: "SUPER-ADMIN" }],
  });

  render(<App />);

  expect(await screen.findByRole("heading", { name: "Administration" })).toBeInTheDocument();
  expect(await screen.findByText("PO-000042")).toBeInTheDocument();
  expect(screen.getByText("test-schema")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Users & Access" })).toHaveAttribute("href", "/users");
  expect(screen.getByRole("link", { name: "Organization / Bank Settings" })).toHaveAttribute("href", "/administration/organization-settings");
});

test("shows dedicated snapshot-safe organization and bank settings to SUPER-ADMIN", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/administration/organization-settings");
  mockedGetCurrentUser.mockResolvedValue({ id: "super-id", email: "super@example.com", is_active: true, roles: [{ name: "SUPER-ADMIN" }] });
  mockedListMasterData.mockImplementation(async (_token, resource) => ({
    items: resource === "organizations" ? [{ id: "org-1", resource, is_active: true, created_at: "", updated_at: "1", data: { code: "WC", legal_name: "World Communication", is_primary: true } }]
      : resource === "bank-accounts" ? [{ id: "bank-1", resource, is_active: true, created_at: "", updated_at: "", data: { organization_id: "org-1", account_name: "Current Account", bank_name: "Bank", account_number: "****1234", ifsc: "BANK0001", is_default: true } }]
      : [], total: resource === "organizations" || resource === "bank-accounts" ? 1 : 0, offset: 0, limit: 50,
  }));
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Organization / Bank Settings" })).toBeInTheDocument();
  expect(await screen.findByDisplayValue("World Communication")).toBeInTheDocument();
  expect(screen.getByText("****1234")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Default Document Settings" })).toBeInTheDocument();
});

test("SUPER-ADMIN can configure the initial World Communication organization", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/administration/organization-settings");
  mockedGetCurrentUser.mockResolvedValue({ id: "super-id", email: "super@example.com", is_active: true, roles: [{ name: "SUPER-ADMIN" }] });
  let configured = false;
  const organization = { id: "org-new", resource: "organizations", is_active: true, created_at: "", updated_at: "1", data: { code: "WC", legal_name: "World Communication" } };
  mockedListMasterData.mockImplementation(async (_token, resource) => ({ items: configured && resource === "organizations" ? [organization] : [], total: configured && resource === "organizations" ? 1 : 0, offset: 0, limit: 50 }));
  mockedCreateMasterData.mockImplementation(async (_token, resource) => { configured = true; return { ...organization, resource }; });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Configure Organization" }));
  fireEvent.change(screen.getByPlaceholderText("e.g. WC"), { target: { value: "WC" } });
  fireEvent.change(screen.getByPlaceholderText("World Communication"), { target: { value: "World Communication" } });
  fireEvent.click(screen.getByRole("button", { name: "Save organization" }));
  await waitFor(() => expect(mockedCreateMasterData).toHaveBeenCalledWith("valid-token", "organizations", expect.objectContaining({ code: "WC", legal_name: "World Communication" })));
  expect(await screen.findByDisplayValue("World Communication")).toBeInTheDocument();
  expect(screen.queryByText(/Customers|Vendors|OEMs/)).not.toBeInTheDocument();
});

test("SUPER-ADMIN can persist the existing organization as primary without changing child defaults", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/administration/organization-settings");
  mockedGetCurrentUser.mockResolvedValue({ id: "super-id", email: "super@example.com", is_active: true, roles: [{ name: "SUPER-ADMIN" }] });
  let primary = false;
  mockedListMasterData.mockImplementation(async (_token, resource) => {
    const data = resource === "organizations" ? [{ id: "org-1", resource, is_active: true, created_at: "", updated_at: "1", data: { code: "WC", legal_name: "World Communication", is_primary: primary } }]
      : resource === "organization-addresses" ? [{ id: "address-1", resource, is_active: true, created_at: "", updated_at: "", data: { organization_id: "org-1", label: "World Communication", address_line_1: "12 Park Street", city: "Kolkata", state: "West Bengal", postal_code: "700016", country: "India", is_default: true } }]
      : resource === "gst-registrations" ? [{ id: "gst-1", resource, is_active: true, created_at: "", updated_at: "", data: { organization_id: "org-1", gstin: "19ABCDE1234F1Z5", is_default: true } }]
      : [{ id: "bank-1", resource, is_active: true, created_at: "", updated_at: "", data: { organization_id: "org-1", account_name: "WORLD COMMUNICATION", is_default: true } }];
    return { items: data, total: data.length, offset: 0, limit: 50 };
  });
  mockedSetPrimaryOrganization.mockImplementation(async () => { primary = true; return { id: "org-1", resource: "organizations", is_active: true, created_at: "", updated_at: "2", data: { code: "WC", legal_name: "World Communication", is_primary: true } }; });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Set as Primary Organization" }));
  await waitFor(() => expect(mockedSetPrimaryOrganization).toHaveBeenCalledWith("valid-token", "org-1"));
  expect(await screen.findByText("✓ PRIMARY")).toBeInTheDocument();
  expect(screen.getAllByText("World Communication").length).toBeGreaterThan(0);
  const defaultAddress = document.querySelector(".default-address-value");
  expect(defaultAddress).toHaveTextContent("12 Park Street");
  expect(defaultAddress).toHaveTextContent("Kolkata, West Bengal - 700016");
  expect(defaultAddress).not.toHaveTextContent(/^World Communication$/);
  expect(screen.getAllByText("19ABCDE1234F1Z5").length).toBeGreaterThan(0);
  expect(screen.getAllByText("WORLD COMMUNICATION").length).toBeGreaterThan(0);
  expect(mockedCreateMasterData).not.toHaveBeenCalled();
});

test("denies an ADMIN direct access to organization and bank settings", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/administration/organization-settings");
  mockedGetCurrentUser.mockResolvedValue({ id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }] });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Access denied" })).toBeInTheDocument();
});

test("forces a temporary-password user to the password change page", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true,
    must_change_password: true, roles: [{ name: "ADMIN" }],
  });

  render(<App />);

  expect(await screen.findByRole("heading", { name: "My Profile" })).toBeInTheDocument();
  expect(screen.getByText(/must change the temporary password/i)).toBeInTheDocument();
});

test("SUPER-ADMIN can create, deactivate, and reset a user from the register", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/users");
  mockedGetCurrentUser.mockResolvedValue({
    id: "super-id", email: "super@example.com", is_active: true,
    roles: [{ name: "SUPER-ADMIN" }],
  });
  mockedListUsers.mockResolvedValue({ items: [{
    id: "user-1", display_name: "Operations Admin", email: "ops@example.com",
    is_active: true, roles: [{ name: "ADMIN" }],
  }], offset: 0, limit: 50 });

  render(<App />);
  expect(await screen.findByRole("heading", { name: "Users" })).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("Display name"), { target: { value: "New User" } });
  fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "new@example.com" } });
  fireEvent.change(screen.getByPlaceholderText("Temporary password"), { target: { value: "temporary-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Create user" }));
  await waitFor(() => expect(mockedCreateUser).toHaveBeenCalled());

  fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
  await waitFor(() => expect(mockedSetUserActive).toHaveBeenCalledWith("valid-token", "user-1", false));
  fireEvent.click(screen.getByRole("button", { name: "Reset password" }));
  fireEvent.change(screen.getByPlaceholderText("New password"), { target: { value: "replacement-password" } });
  fireEvent.change(screen.getByPlaceholderText("Reset reason"), { target: { value: "Recovery" } });
  fireEvent.click(screen.getByRole("button", { name: "Set password" }));
  await waitFor(() => expect(mockedResetUserPassword).toHaveBeenCalledWith(
    "valid-token", "user-1", "replacement-password", "Recovery",
  ));
});

test("a logged-in user can submit their own password change", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/profile");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true,
    roles: [{ name: "ADMIN" }],
  });
  mockedChangePassword.mockResolvedValue(undefined);

  render(<App />);
  expect(await screen.findByRole("heading", { name: "My Profile" })).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("Current password"), { target: { value: "current-password" } });
  fireEvent.change(screen.getByPlaceholderText("New password"), { target: { value: "replacement-password" } });
  fireEvent.change(screen.getByPlaceholderText("Confirm new password"), { target: { value: "replacement-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Change password" }));
  await waitFor(() => expect(mockedChangePassword).toHaveBeenCalledWith(
    "valid-token", "current-password", "replacement-password",
  ));
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
  expect(screen.getByRole("button", { name: "Upload Railway LOA" })).toBeInTheDocument();
  expect(screen.getAllByText("Create LOA Manually").length).toBeGreaterThan(0);
});

test("provides owner-facing Railway hierarchy master forms", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/master-data?type=railway-divisions");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Add Railway Divisions" })).toBeInTheDocument();
  expect(screen.getByLabelText("Railway Zone")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add to Railway Master" })).toBeInTheDocument();
  expect(screen.queryByText(/managed through its validated API/)).not.toBeInTheDocument();
});

test("confirms and refreshes Railway master deletion with blocked errors visible", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/master-data?type=railway-zones");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  const zone = {
    id: "zone-delete", resource: "railway-zones", is_active: true,
    created_at: "2026-08-26T10:00:00Z", updated_at: "2026-08-26T10:00:00Z",
    data: { code: "DEL", name: "Deletable Railway", aliases: [] },
  };
  mockedListMasterData.mockImplementation(async (_token, resource) => ({
    items: resource === "railway-zones" ? [zone] : [], total: resource === "railway-zones" ? 1 : 0,
    offset: 0, limit: 50,
  }));
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Delete Deletable Railway" }));
  await waitFor(() => expect(mockedDeleteMasterData).toHaveBeenCalledWith(
    "valid-token", "railway-zones", "zone-delete",
  ));

  mockedDeleteMasterData.mockRejectedValueOnce(new ApiError(
    "This Railway master is already in use. Deactivate it instead.", 409, "master_record_in_use",
  ));
  fireEvent.click(screen.getByRole("button", { name: "Delete Deletable Railway" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This Railway master is already in use. Deactivate it instead.",
  );
});

test("prefills but does not auto-create an extracted Railway authority suggestion", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/master-data?type=railway-authorities&division_id=division-1&suggestion=DSTE%2FTEST");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  render(<App />);
  expect((await screen.findAllByDisplayValue("DSTE/TEST")).length).toBeGreaterThan(0);
  expect(screen.getByText(/confirm or edit the canonical Railway master data/)).toBeInTheDocument();
  expect(mockedCreateMasterData).not.toHaveBeenCalled();
});

test("preserves return navigation from Railway Master to LOA review", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/master-data?type=railway-authorities&returnTo=%2Floa-imports%2Fimport-1");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  render(<App />);
  expect(await screen.findByRole("link", { name: "← Return to LOA Review" })).toHaveAttribute(
    "href", "/loa-imports/import-1",
  );
});

test("shows extracted Railway LOA fields and BOQ in mandatory review", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/loa-imports/import-1");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "LOA/RAIL/20" })).toBeInTheDocument();
  expect(screen.getByText("Railway LOA.xlsx")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "BOQ / Item Schedule" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Schedule" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Sn. No." })).toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "Item code" })).not.toBeInTheDocument();
  expect(screen.getAllByText("Schedule A").length).toBeGreaterThan(0);
  expect(screen.getAllByLabelText("Reviewed Sn. No.")).toHaveLength(12);
  expect(screen.getByRole("columnheader", { name: "Outcome" })).toBeInTheDocument();
  expect(screen.getByDisplayValue("IP communication terminal 1")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "View Extraction Details" }));
  expect(screen.getByText(/Semantic LOA date label/)).toBeInTheDocument();
  expect(screen.getAllByText(/SSE\/TELE\/STORE/).length).toBeGreaterThan(0);
  expect(screen.getByText("✓ Matched with Railway Zone Master")).toBeInTheDocument();
  expect(screen.getByText("✓ Matched with Railway Division Master")).toBeInTheDocument();
  expect(screen.getByText(/Master mapping: Not configured \(optional\)/)).toBeInTheDocument();
  expect(screen.queryByText(/Railway Customer mapping required/)).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Required Before Registration" })).toBeInTheDocument();
  expect(screen.getByText("BOQ Items — All")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(13);
  fireEvent.click(screen.getByRole("button", { name: "Review Missing / Unresolved Items" }));
  expect(screen.getByText("Unresolved BOQ Items — 1")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "View BOQ Items" }));
  await waitFor(() => expect(screen.getByText("BOQ Items — All")).toBeInTheDocument());
  expect(screen.getAllByRole("row")).toHaveLength(13);
  fireEvent.click(screen.getByRole("button", { name: "Review Missing / Unresolved Items" }));
  fireEvent.click(screen.getByRole("button", { name: "View BOQ Items" }));
  await waitFor(() => expect(screen.getAllByRole("row")).toHaveLength(13));
  expect(screen.getByRole("button", { name: "Approve & Create LOA" })).toBeDisabled();
});

test("keeps complete unmapped BOQ ready and reports Project code separately", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/loa-imports/import-1");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  const current = await vi.mocked(getLoaImport)("valid-token", "import-1");
  vi.mocked(getLoaImport).mockResolvedValueOnce({
    ...current,
    boq_readiness_issues: [],
    boq_reconciliation: {
      source_rows_detected: 12, extracted_successfully: 12, needs_review: 0,
      unparsed_rejected: 0, document_coverage_status: "COMPLETE", complete: true,
    },
    lines: current.lines.map((line) => ({
      ...line, product_id: undefined, unit_id: undefined, unit_text: "Numbers",
      extraction_outcome: "EXTRACTED" as const,
    })),
  });
  render(<App />);
  expect(await screen.findByText("✓ Complete — 12/12 source items reconciled")).toBeInTheDocument();
  expect(screen.queryByText("Mandatory BOQ mappings require review")).not.toBeInTheDocument();
  expect(screen.getByText("New Project code is required")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Review Missing / Unresolved Items" }));
  expect(screen.getByText("Unresolved BOQ Items — 0")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(1);
  fireEvent.input(screen.getByLabelText("New Project code"), { target: { value: "RAIL-NEW" } });
  await waitFor(() => expect(screen.queryByText("New Project code is required")).not.toBeInTheDocument());
});

test("refreshes Railway master matches with loading, immediate state, and errors", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/loa-imports/import-1");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  vi.mocked(resolveLoaImportMasters).mockRejectedValueOnce(new Error("network"));
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Refresh Railway Master Matches" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to refresh Railway Master matches.");

  let finishRefresh!: (value: Awaited<ReturnType<typeof getLoaImport>>) => void;
  vi.mocked(resolveLoaImportMasters).mockImplementationOnce(() => new Promise((resolve) => { finishRefresh = resolve; }));
  fireEvent.click(screen.getByRole("button", { name: "Refresh Railway Master Matches" }));
  expect(screen.getByRole("button", { name: "Refreshing Railway Master Matches…" })).toBeDisabled();
  const current = await vi.mocked(getLoaImport)("valid-token", "import-1");
  finishRefresh({
    ...current,
    authority_id: "authority-1",
    authority_candidates: current.authority_candidates.map((candidate) => ({
      ...candidate, master_id: "authority-1", master_status: "MATCHED" as const,
      master_detail: "Exactly one active authority matched the Division and contextual role.",
    })),
  });
  expect(await screen.findByText("Railway Master matches refreshed.")).toBeInTheDocument();
  expect(screen.getByText(/Exactly one active authority matched/)).toBeInTheDocument();
  expect(vi.mocked(resolveLoaImportMasters)).toHaveBeenLastCalledWith("valid-token", "import-1");
});

test("uses Railway masters without exposing a mandatory Customer mapping workflow", async () => {
  sessionStorage.setItem("wcdms.access-token", "valid-token");
  window.history.replaceState({}, "", "/loa-imports/import-1");
  mockedGetCurrentUser.mockResolvedValue({
    id: "admin-id", email: "admin@example.com", is_active: true, roles: [{ name: "ADMIN" }],
  });
  render(<App />);
  expect(await screen.findByText("✓ Matched with Railway Zone Master")).toBeInTheDocument();
  expect(screen.getByText("✓ Matched with Railway Division Master")).toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "WCDMS Customer" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save Railway Mapping" })).not.toBeInTheDocument();
  expect(screen.queryByText(/Railway Customer mapping required/)).not.toBeInTheDocument();
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
  expect(await screen.findByText(/Accepted: 10, Registered: 7, Remaining: 3/)).toBeInTheDocument();
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
  expect(await screen.findByText("RCT-000001")).toBeInTheDocument();
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
  expect(await screen.findByText(/HIGH — Invoice overdue/)).toBeInTheDocument();
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
  expect(await screen.findByText("PARTIALLY_PAID_OVERDUE (4 days)")).toBeInTheDocument();
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
  expect(screen.getByRole("link", { name: "Supply Challans" })).toBeInTheDocument();
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
