import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createLoa, createProject, listLoas, listProjects, type Loa, type Project } from "../api/contracts";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function ProjectsPage() {
  const { token } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loas, setLoas] = useState<Loa[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    if (!token) return;
    try { setProjects(await listProjects(token)); setLoas(await listLoas(token)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Unable to load contracts."); }
  }, [token]);
  useEffect(() => void load(), [load]);

  async function addProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token) return; const form = event.currentTarget; const d = new FormData(form);
    try { await createProject(token, { code: d.get("code"), name: d.get("name"), customer_party_id: d.get("customer_party_id"), business_scope: d.get("business_scope"), railway_division_id: d.get("railway_division_id") || null }); form.reset(); await load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Unable to create project."); }
  }
  async function addLoa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token) return; const form = event.currentTarget; const d = new FormData(form);
    try { await createLoa(token, { project_id: d.get("project_id"), loa_number: d.get("loa_number"), loa_date: d.get("loa_date"), description: d.get("description"), original_contract_value: d.get("original_contract_value") }); form.reset(); await load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Unable to create LOA."); }
  }
  return <section className="space-y-8"><div><p className="text-sm tracking-[.2em] text-cyan-400">CONTRACTS</p><h1 className="text-3xl font-semibold">Projects & LOAs</h1></div>{error && <p role="alert" className="text-rose-400">{error}</p>}<form onSubmit={addProject} className="grid gap-2 rounded border border-slate-700 p-4 md:grid-cols-5"><input name="code" placeholder="Project code" required className="rounded bg-slate-800 p-2"/><input name="name" placeholder="Work title" required className="rounded bg-slate-800 p-2"/><input name="customer_party_id" placeholder="Customer UUID" required className="rounded bg-slate-800 p-2"/><select name="business_scope" className="rounded bg-slate-800 p-2"><option>NON_RAILWAY</option><option>RAILWAY</option></select><button className="rounded bg-cyan-500 p-2 text-slate-950">Create project</button><input name="railway_division_id" placeholder="Railway division UUID (if applicable)" className="rounded bg-slate-800 p-2 md:col-span-2"/></form><form onSubmit={addLoa} className="grid gap-2 rounded border border-slate-700 p-4 md:grid-cols-6"><select name="project_id" required className="rounded bg-slate-800 p-2">{projects.map(p => <option value={p.id} key={p.id}>{p.code} — {p.name}</option>)}</select><input name="loa_number" placeholder="LOA number" required className="rounded bg-slate-800 p-2"/><input name="loa_date" type="date" required className="rounded bg-slate-800 p-2"/><input name="original_contract_value" type="number" step="0.01" defaultValue="0.00" className="rounded bg-slate-800 p-2"/><input name="description" placeholder="Work description" className="rounded bg-slate-800 p-2"/><button className="rounded bg-cyan-500 p-2 text-slate-950">Create LOA</button></form><div className="rounded border border-slate-700"><table className="w-full text-left"><thead><tr><th className="p-3">LOA</th><th>Project</th><th>Status</th><th>Value</th></tr></thead><tbody>{loas.map(loa => <tr key={loa.id} className="border-t border-slate-800"><td className="p-3"><Link className="text-cyan-400" to={`/loas/${loa.id}`}>{loa.loa_number}</Link></td><td>{projects.find(p => p.id === loa.project_id)?.code}</td><td>{loa.status}</td><td>{loa.original_contract_value}</td></tr>)}</tbody></table></div></section>;
}
