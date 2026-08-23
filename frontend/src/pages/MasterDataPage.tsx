import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  createMasterData,
  listMasterData,
  setMasterDataActive,
  type MasterRecord,
} from "../api/masterData";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const resources = [
  ["organizations", "Organizations"],
  ["parties", "Customers / Vendors / OEMs"],
  ["railway-zones", "Railway Zones"],
  ["railway-divisions", "Railway Divisions"],
  ["railway-locations", "Railway Locations"],
  ["railway-authorities", "Railway Authorities"],
  ["product-categories", "Product Categories"],
  ["products", "Products"],
  ["units", "Units"],
  ["hsn-codes", "HSN Codes"],
  ["payment-terms", "Payment Terms"],
  ["terms-condition-sets", "Terms & Conditions"],
  ["projects", "Projects"],
  ["loas", "LOA References"],
] as const;

function displayName(record: MasterRecord): string {
  return String(record.data.name ?? record.data.legal_name ?? record.data.loa_number ?? record.id);
}

export function MasterDataPage() {
  const { token } = useAuth();
  const [resource, setResource] = useState<string>(resources[0][0]);
  const [records, setRecords] = useState<MasterRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setError(null);
      setRecords((await listMasterData(token, resource)).items);
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Unable to load master data.");
    }
  }, [resource, token]);

  useEffect(() => void load(), [load]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const code = String(values.get("code") ?? "");
    const name = String(values.get("name") ?? "");
    const payload: Record<string, unknown> = { code };
    if (resource === "organizations" || resource === "parties") {
      payload.legal_name = name;
      if (resource === "parties") payload.roles = ["CUSTOMER"];
    } else {
      payload.name = name;
    }
    try {
      await createMasterData(token, resource, payload);
      form.reset();
      await load();
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Unable to create master record.");
    }
  }

  async function toggle(record: MasterRecord) {
    if (!token) return;
    try {
      await setMasterDataActive(token, resource, record.id, !record.is_active);
      await load();
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Unable to update master record.");
    }
  }

  const simpleCreate = ["organizations", "parties", "railway-zones", "product-categories"].includes(resource);

  return (
    <section className="space-y-6">
      <div><p className="text-sm tracking-[0.2em] text-cyan-400">MASTER DATA</p><h1 className="mt-2 text-3xl font-semibold">Master Data Foundation</h1></div>
      <label className="block max-w-md">Master type<select aria-label="Master type" className="mt-1 w-full rounded bg-slate-800 p-2" value={resource} onChange={(event) => setResource(event.target.value)}>{resources.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      {error && <p className="text-rose-400" role="alert">{error}</p>}
      {simpleCreate && <form className="grid gap-3 rounded border border-slate-700 bg-slate-900 p-4 md:grid-cols-3" onSubmit={create}><input className="rounded bg-slate-800 p-2" name="code" placeholder="Code" required /><input className="rounded bg-slate-800 p-2" name="name" placeholder="Name" required /><button className="rounded bg-cyan-500 p-2 font-semibold text-slate-950" type="submit">Create</button></form>}
      {!simpleCreate && <p className="rounded border border-slate-700 bg-slate-900 p-4 text-slate-300">This master uses structured relationships and is managed through its validated API in this foundation release.</p>}
      <div className="overflow-x-auto rounded border border-slate-700"><table className="w-full text-left"><thead className="bg-slate-900"><tr><th className="p-3">Code</th><th className="p-3">Name</th><th className="p-3">Status</th><th className="p-3">Action</th></tr></thead><tbody>{records.map((record) => <tr className="border-t border-slate-800" key={record.id}><td className="p-3">{String(record.data.code ?? "—")}</td><td className="p-3">{displayName(record)}</td><td className="p-3">{record.is_active ? "Active" : "Inactive"}</td><td className="p-3"><button className="text-cyan-400" onClick={() => void toggle(record)} type="button">{record.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}</tbody></table></div>
    </section>
  );
}
