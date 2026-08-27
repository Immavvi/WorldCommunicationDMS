import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  createMasterData,
  deleteMasterData,
  listMasterData,
  setMasterDataActive,
  updateMasterData,
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
  const [searchParams] = useSearchParams();
  const requestedReturn = searchParams.get("returnTo");
  const returnTo = requestedReturn?.startsWith("/loa-imports/") ? requestedReturn : null;
  const requestedResource = searchParams.get("type");
  const [resource, setResource] = useState<string>(resources.some(([value]) => value === requestedResource) ? requestedResource! : resources[0][0]);
  const [records, setRecords] = useState<MasterRecord[]>([]);
  const [railwayMasters, setRailwayMasters] = useState<Record<string, MasterRecord[]>>({});
  const [editing, setEditing] = useState<MasterRecord | null>(null);
  const [search, setSearch] = useState("");
  const [railwayZoneFilter, setRailwayZoneFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setError(null);
      setRecords((await listMasterData(token, resource)).items);
      if (resource.startsWith("railway-")) {
        const related = ["railway-zones", "railway-divisions", "railway-locations"];
        const lists = await Promise.all(related.map((name) => listMasterData(token, name)));
        setRailwayMasters(Object.fromEntries(related.map((name, index) => [name, lists[index].items])));
      }
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Unable to load master data.");
    }
  }, [resource, token]);

  useEffect(() => void load(), [load]);
  useEffect(() => setEditing(null), [resource]);

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
    if (resource.startsWith("railway-")) {
      payload.aliases = String(values.get("aliases") ?? "").split(",").map((value) => value.trim()).filter(Boolean);
      if (resource === "railway-divisions") payload.zone_id = String(values.get("zone_id") ?? "");
      if (["railway-locations", "railway-authorities"].includes(resource)) payload.division_id = String(values.get("division_id") ?? "");
      if (resource === "railway-locations") payload.location_type = String(values.get("location_type") ?? "OTHER");
      if (resource === "railway-authorities") {
        payload.location_id = String(values.get("location_id") ?? "") || null;
        payload.designation = String(values.get("designation") ?? "") || null;
        payload.roles = values.getAll("roles").map(String);
      }
    }
    try {
      if (editing) await updateMasterData(token, resource, editing.id, payload);
      else await createMasterData(token, resource, payload);
      form.reset();
      setEditing(null);
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

  async function remove(record: MasterRecord) {
    if (!token || !window.confirm(`Delete ${displayName(record)} permanently?`)) return;
    try {
      setError(null);
      await deleteMasterData(token, resource, record.id);
      if (editing?.id === record.id) setEditing(null);
      await load();
    } catch (exception) {
      setError(
        exception instanceof ApiError
          ? exception.message
          : "Unable to delete Railway master record.",
      );
    }
  }

  const railwayResource = ["railway-zones", "railway-divisions", "railway-locations", "railway-authorities"].includes(resource);
  const simpleCreate = ["organizations", "parties", "product-categories"].includes(resource);
  const zones = railwayMasters["railway-zones"] ?? [];
  const divisions = railwayMasters["railway-divisions"] ?? [];
  const locations = railwayMasters["railway-locations"] ?? [];
  const filteredRecords = records.filter((record) => {
    if (!JSON.stringify(record.data).toLowerCase().includes(search.toLowerCase())) return false;
    if (!railwayZoneFilter || resource === "railway-zones") return true;
    if (resource === "railway-divisions") return record.data.zone_id === railwayZoneFilter;
    const division = divisions.find((item) => item.id === record.data.division_id);
    return division?.data.zone_id === railwayZoneFilter;
  });
  const suggestedName = editing ? "" : searchParams.get("suggestion") ?? "";
  const suggestedDivision = editing ? "" : searchParams.get("division_id") ?? "";
  const editData = editing?.data ?? (suggestedName ? { name: suggestedName, aliases: [suggestedName], division_id: suggestedDivision } : {});

  return (
    <section className="space-y-6">
      {returnTo && (
  <Link className="button-secondary" to={returnTo}>
    ← Return to LOA Review
  </Link>
)}
      <div><p className="text-sm tracking-[0.2em] text-cyan-400">MASTER DATA</p><h1 className="mt-2 text-3xl font-semibold">Master Data Foundation</h1></div>
      <label className="block max-w-md">Master type<select aria-label="Master type" className="mt-1 w-full rounded bg-slate-800 p-2" value={resource} onChange={(event) => setResource(event.target.value)}>{resources.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      {error && <p className="text-rose-400" role="alert">{error}</p>}
      {suggestedName && <p className="settings-feedback">Extracted suggestion — confirm or edit the canonical Railway master data before saving.</p>}
      {resource === "railway-zones" && records.some((record) => record.data.classification_warning) && <div className="settings-feedback error"><strong>Railway hierarchy review required</strong><ul>{records.filter((record) => record.data.classification_warning).map((record) => <li key={record.id}>{displayName(record)}: {String(record.data.classification_warning)}</li>)}</ul></div>}
      {simpleCreate && <form className="grid gap-3 rounded border border-slate-700 bg-slate-900 p-4 md:grid-cols-3" onSubmit={create}><input className="rounded bg-slate-800 p-2" name="code" placeholder="Code" required /><input className="rounded bg-slate-800 p-2" name="name" placeholder="Name" required /><button className="rounded bg-cyan-500 p-2 font-semibold text-slate-950" type="submit">Create</button></form>}
      {railwayResource && <form key={`${resource}-${editing?.id ?? "new"}`} className="wcdms-card settings-form" onSubmit={create}><h2>{editing ? "Edit" : "Add"} {resources.find(([value]) => value === resource)?.[1]}</h2><label>Code<input name="code" defaultValue={String(editData.code ?? "")} required /></label><label>Canonical name<input name="name" defaultValue={String(editData.name ?? "")} required /></label><label>Aliases<input name="aliases" defaultValue={Array.isArray(editData.aliases) ? editData.aliases.join(", ") : ""} placeholder="Comma-separated matching aliases" /></label>{resource === "railway-divisions" && <label>Railway Zone<select name="zone_id" defaultValue={String(editData.zone_id ?? "")} required><option value="">Select Railway Zone</option>{zones.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{displayName(item)}</option>)}</select></label>}{["railway-locations", "railway-authorities"].includes(resource) && <label>Railway Division<select name="division_id" defaultValue={String(editData.division_id ?? "")} required><option value="">Select Railway Division</option>{divisions.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{displayName(item)} — {displayName(zones.find((zone) => zone.id === item.data.zone_id) ?? item)}</option>)}</select></label>}{resource === "railway-locations" && <label>Location type<select name="location_type" defaultValue={String(editData.location_type ?? "OTHER")} required>{["STATION", "STORE", "OFFICE", "DEPOT", "YARD", "LC_GATE", "BUILDING", "OTHER"].map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select></label>}{resource === "railway-authorities" && <><label>Canonical designation<input name="designation" defaultValue={String(editData.designation ?? "")} /></label><label>Railway Location (optional)<select name="location_id" defaultValue={String(editData.location_id ?? "")}><option value="">No specific location</option>{locations.filter((item) => item.is_active && (!editData.division_id || item.data.division_id === editData.division_id)).map((item) => <option key={item.id} value={item.id}>{displayName(item)}</option>)}</select></label><fieldset><legend>Role compatibility</legend>{["ISSUING_AUTHORITY", "EXECUTION_AUTHORITY", "CONSIGNEE", "BILL_TO", "SHIP_TO"].map((role) => <label className="check-field" key={role}><input type="checkbox" name="roles" value={role} defaultChecked={Array.isArray(editData.roles) && editData.roles.includes(role)} />{role.replaceAll("_", " ")}</label>)}</fieldset></>}<div className="import-actions"><button className="button-primary" type="submit">{editing ? "Save Changes" : "Add to Railway Master"}</button>{editing && <button className="button-secondary" type="button" onClick={() => setEditing(null)}>Cancel</button>}</div></form>}
      {!simpleCreate && !railwayResource && <p className="rounded border border-slate-700 bg-slate-900 p-4 text-slate-300">This master uses structured relationships and is managed through its validated API in this foundation release.</p>}
      {railwayResource && resource !== "railway-zones" && <label className="block max-w-md">Filter by Railway Zone<select aria-label="Filter by Railway Zone" value={railwayZoneFilter} onChange={(event) => setRailwayZoneFilter(event.target.value)}><option value="">All Railway Zones</option>{zones.map((zone) => <option key={zone.id} value={zone.id}>{displayName(zone)}</option>)}</select></label>}
      <label className="block max-w-md">Search<input aria-label="Search master data" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search code, name or alias" /></label>
      <div className="overflow-x-auto rounded border border-slate-700"><table className="w-full text-left"><thead className="bg-slate-900"><tr><th className="p-3">Code</th><th className="p-3">Name</th>{railwayResource && <th className="p-3">Hierarchy / Roles</th>}<th className="p-3">Status</th><th className="p-3">Action</th></tr></thead><tbody>{filteredRecords.map((record) => <tr className="border-t border-slate-800" key={record.id}><td className="p-3">{String(record.data.code ?? "—")}</td><td className="p-3">{displayName(record)}</td>{railwayResource && <td className="p-3">{resource === "railway-divisions" ? displayName(zones.find((item) => item.id === record.data.zone_id) ?? record) : ["railway-locations", "railway-authorities"].includes(resource) ? displayName(divisions.find((item) => item.id === record.data.division_id) ?? record) : Array.isArray(record.data.aliases) ? record.data.aliases.join(", ") || "—" : "—"}{resource === "railway-authorities" && Array.isArray(record.data.roles) && <><br /><small>{record.data.roles.join(", ")}</small></>}</td>}<td className="p-3">{record.is_active ? "Active" : "Inactive"}</td><td className="p-3"><div className="import-actions">{railwayResource && <button className="button-secondary" onClick={() => setEditing(record)} type="button">Edit</button>}<button className="text-cyan-400" onClick={() => void toggle(record)} type="button">{record.is_active ? "Deactivate" : "Activate"}</button></div></td></tr>)}</tbody></table>{filteredRecords.length === 0 && <p className="p-4">No {resources.find(([value]) => value === resource)?.[1]} configured{search ? " for this search" : ""}.</p>}</div>
      {railwayResource && filteredRecords.length > 0 && <section className="wcdms-card"><h2>Delete unused Railway master</h2><p>Physical deletion is available only when no WCDMS record references the master.</p><div className="import-actions">{filteredRecords.map((record) => <button className="button-secondary" key={record.id} type="button" onClick={() => void remove(record)}>Delete {displayName(record)}</button>)}</div></section>}
    </section>
  );
}
