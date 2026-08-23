import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import App from "../src/App";
import { getCurrentUser } from "../src/api/auth";

vi.mock("../src/api/auth", () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
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
