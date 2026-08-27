import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createLoa, createProject, listLoas, listProjects, type Loa, type Project } from "../api/contracts";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { uploadRailwayLoa } from "../api/loaImports";

export function ProjectsPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loas, setLoas] = useState<Loa[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
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
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token) return; const form = event.currentTarget; const data = new FormData(form); const file = data.get("loa_file");
    if (!(file instanceof File) || !file.size) return;
    try { setError(null); setUploading(true); const result = await uploadRailwayLoa(token, file); navigate(`/loa-imports/${result.id}`); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Unable to upload Railway LOA."); }
    finally { setUploading(false); }
  }
  return <section className="space-y-8 contracts-page"><div><p className="text-sm tracking-[.2em] text-cyan-400">CONTRACTS</p><h1 className="text-3xl font-semibold">Projects & LOAs</h1></div>{error && <p role="alert" className="text-rose-400">{error}</p>}<form onSubmit={upload} className="loa-upload-card"><h2>Upload Railway LOA</h2><p>Select a PDF or XLSX. WCDMS preserves the original, extracts contract details and BOQ rows, then opens a mandatory review.</p><input aria-label="Railway LOA file" name="loa_file" type="file" accept=".pdf,.xlsx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required disabled={uploading}/><button className="button-primary" disabled={uploading}>{uploading ? "Extracting Railway LOA…" : "Upload Railway LOA"}</button>{uploading && <p role="status">Original saved. Extracting document structure and BOQ items…</p>}</form><details className="manual-contracts"><summary className="button-secondary">Create LOA Manually</summary><form onSubmit={addProject} className="grid gap-2 rounded border border-slate-700 p-4 md:grid-cols-5"><h2 className="md:col-span-5">Create Project</h2><input name="code" placeholder="Project code" required/><input name="name" placeholder="Work title" required/><input name="customer_party_id" placeholder="Customer UUID" required/><select name="business_scope"><option>NON_RAILWAY</option><option>RAILWAY</option></select><button>Create project</button><input name="railway_division_id" placeholder="Railway division UUID (if applicable)" className="md:col-span-2"/></form><form onSubmit={addLoa} className="grid gap-2 rounded border border-slate-700 p-4 md:grid-cols-6"><h2 className="md:col-span-6">Create / Register LOA</h2><select name="project_id" required>{projects.map(p => <option value={p.id} key={p.id}>{p.code} — {p.name}</option>)}</select><input name="loa_number" placeholder="LOA number" required/><input name="loa_date" aria-label="LOA Issued Date" type="date" required/><input name="original_contract_value" type="number" step="0.01" defaultValue="0.00"/><input name="description" placeholder="Work description"/><button>Create LOA Manually</button></form></details><div><h2>Project &amp; LOA register</h2><div className="table-container"><table className="w-full text-left"><thead><tr><th>LOA</th><th>Project</th><th>Status</th><th>Value</th></tr></thead><tbody>{loas.map(loa => <tr key={loa.id}><td><Link to={`/loas/${loa.id}`}>{loa.loa_number}</Link></td><td>{projects.find(p => p.id === loa.project_id)?.code}</td><td>{loa.status}</td><td>{loa.original_contract_value}</td></tr>)}</tbody></table></div></div></section>;
}
