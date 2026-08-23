import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listLoas, listProjects, type Loa, type Project } from "../api/contracts";
import { createChallan, getDispatchAvailability, listChallans, type DispatchAvailability, type SupplyChallan } from "../api/dispatch";
import { listMasterData, type MasterRecord } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";

const label = (record: MasterRecord) => String(record.data.name ?? record.data.label ?? record.data.legal_name ?? record.id);
const resources = ["party-addresses", "organization-addresses", "railway-divisions", "railway-authorities", "railway-authority-addresses"];

export function DispatchPage() {
  const { token } = useAuth();
  const [challans, setChallans] = useState<SupplyChallan[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loas, setLoas] = useState<Loa[]>([]);
  const [masters, setMasters] = useState<Record<string, MasterRecord[]>>({});
  const [projectId, setProjectId] = useState("");
  const [availability, setAvailability] = useState<DispatchAvailability[]>([]);
  const project = projects.find((item) => item.id === projectId);
  const load = useCallback(async () => {
    if (!token) return;
    const [items, projectItems, loaItems, ...masterLists] = await Promise.all([
      listChallans(token), listProjects(token), listLoas(token), ...resources.map((resource) => listMasterData(token, resource)),
    ]);
    setChallans(items); setProjects(projectItems); setLoas(loaItems);
    setMasters(Object.fromEntries(resources.map((resource, index) => [resource, masterLists[index].items])));
  }, [token]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (token && projectId) void getDispatchAvailability(token, projectId).then(setAvailability); else setAvailability([]); }, [token, projectId]);
  const projectLoas = useMemo(() => loas.filter((item) => item.project_id === projectId), [loas, projectId]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token || !project) return;
    const form = event.currentTarget; const data = new FormData(form);
    const material = availability.find((item) => item.material_receipt_line_id === data.get("material"));
    if (!material) return;
    const railway = project.business_scope === "RAILWAY";
    await createChallan(token, {
      challan_date: data.get("date"), project_id: project.id, loa_id: data.get("loa") || undefined,
      business_scope: project.business_scope, customer_party_id: project.customer_party_id,
      railway_division_id: railway ? data.get("division") : undefined,
      consignee_authority_id: railway ? data.get("consignee") : undefined,
      ship_to_railway_address_id: railway ? data.get("railway_address") : undefined,
      ship_to_party_address_id: railway ? undefined : data.get("party_address"),
      dispatch_from_address_id: data.get("dispatch_from"), transporter: data.get("transporter") || undefined,
      vehicle_number: data.get("vehicle") || undefined,
      lines: [{ dispatched_quantity: data.get("quantity"), allocations: [{ material_receipt_line_id: material.material_receipt_line_id, allocated_quantity: data.get("quantity") }] }],
    });
    form.reset(); setProjectId(""); await load();
  }
  return <section className="space-y-8"><div><p className="text-sm tracking-[.2em] text-cyan-400">PHASE 07</p><h1 className="text-3xl font-semibold">Supply Challan & Dispatch</h1><p>Dispatch only verified, accepted material. Commercial purchase data is not shown.</p></div>
    <form onSubmit={create} className="grid gap-2 rounded border p-4 md:grid-cols-3"><h2 className="text-xl md:col-span-3">Create supply challan</h2>
      <select aria-label="Project" value={projectId} onChange={(event) => setProjectId(event.target.value)} required><option value="">Select project</option>{projects.map((item) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select>
      <select name="loa" aria-label="LOA"><option value="">No LOA</option>{projectLoas.map((item) => <option key={item.id} value={item.id}>{item.loa_number}</option>)}</select>
      <input name="date" type="date" aria-label="Challan date" required />
      <select name="material" aria-label="Verified material" required><option value="">Select verified material</option>{availability.filter((item) => Number(item.available_quantity) > 0).map((item) => <option key={item.material_receipt_line_id} value={item.material_receipt_line_id}>{item.description} — available {item.available_quantity} {item.unit}</option>)}</select>
      <input name="quantity" type="number" step="0.0001" min="0.0001" placeholder="Dispatch quantity" required />
      <select name="dispatch_from" aria-label="Dispatch from" required><option value="">Select dispatch origin</option>{(masters["organization-addresses"] ?? []).map((item) => <option key={item.id} value={item.id}>{label(item)}</option>)}</select>
      {project?.business_scope === "RAILWAY" ? <><select name="division" aria-label="Railway division" required><option value="">Select division</option>{(masters["railway-divisions"] ?? []).map((item) => <option key={item.id} value={item.id}>{label(item)}</option>)}</select><select name="consignee" aria-label="Railway consignee" required><option value="">Select consignee</option>{(masters["railway-authorities"] ?? []).map((item) => <option key={item.id} value={item.id}>{label(item)}</option>)}</select><select name="railway_address" aria-label="Railway ship-to" required><option value="">Select Railway address</option>{(masters["railway-authority-addresses"] ?? []).map((item) => <option key={item.id} value={item.id}>{label(item)}</option>)}</select></> : <select name="party_address" aria-label="Customer ship-to" required><option value="">Select customer address</option>{(masters["party-addresses"] ?? []).filter((item) => item.data.party_id === project?.customer_party_id).map((item) => <option key={item.id} value={item.id}>{label(item)}</option>)}</select>}
      <input name="transporter" placeholder="Transporter" /><input name="vehicle" placeholder="Vehicle number" /><button>Create draft Challan</button>
    </form><div><h2 className="text-xl">Supply challans</h2>{challans.map((item) => <article key={item.id}><Link to={`/supply-challans/${item.id}`}>{item.challan_number}</Link> — {item.customer_snapshot.legal_name} — {item.status}</article>)}</div></section>;
}
