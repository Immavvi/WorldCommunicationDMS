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
