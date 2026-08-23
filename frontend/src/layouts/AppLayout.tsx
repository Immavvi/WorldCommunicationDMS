import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function AppLayout({ children }: { children: ReactNode }) {
  const { logout, user } = useAuth();
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16 text-slate-100">
      <div className="mx-auto max-w-4xl">
        {user && (
          <header className="mb-8 flex items-center justify-between border-b border-slate-800 pb-4">
            <Link to="/" className="font-semibold tracking-wide text-cyan-400">WCDMS</Link>
            <div className="flex items-center gap-4 text-sm">
              <Link to="/master-data">Master Data</Link>
              <Link to="/projects">Projects & LOAs</Link>
              <Link to="/procurement">Procurement & POs</Link>
              <Link to="/receiving">GRN / Receipts</Link>
              <Link to="/dispatch">Challans / Dispatch</Link>
              <Link to="/proforma-invoices">Proforma Invoices</Link>
              {user.roles.some((role) => role.name === "SUPER-ADMIN") && <Link to="/users">Users</Link>}
              <span>{user.roles.map((role) => role.name).join(", ")}</span>
              <button className="text-cyan-400" onClick={logout} type="button">Logout</button>
            </div>
          </header>
        )}
        {children}
      </div>
    </main>
  );
}
