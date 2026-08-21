import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import App from "../src/App";

vi.mock("../src/api/client", () => ({
  getHealthStatus: vi.fn().mockResolvedValue({ status: "ok", service: "wcdms-api" })
}));

test("renders the foundation status page", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "Foundation status" })).toBeInTheDocument();
});
