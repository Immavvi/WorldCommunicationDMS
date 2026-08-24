import { FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  createMasterData,
  listMasterData,
  setPrimaryOrganization,
  setMasterDataActive,
  updateMasterData,
  type MasterRecord,
} from "../api/masterData";
import { useAuth } from "../auth/AuthContext";

type Resource = "organizations" | "organization-addresses" | "gst-registrations" | "bank-accounts";

const resources: Resource[] = ["organizations", "organization-addresses", "gst-registrations", "bank-accounts"];
const text = (record: MasterRecord | undefined, key: string) => String(record?.data[key] ?? "");
const optional = (data: FormData, key: string) => String(data.get(key) ?? "").trim() || null;
const addressPresentation = (record: MasterRecord | undefined) => {
  if (!record) return "Not configured";
  const cityStatePostal = [
    text(record, "city"),
    [text(record, "state"), text(record, "postal_code")].filter(Boolean).join(" - "),
  ].filter(Boolean).join(", ");
  return [
    text(record, "label"), text(record, "address_line_1"), text(record, "address_line_2"),
    cityStatePostal, text(record, "country"),
  ].filter(Boolean).join("\n");
};

export function OrganizationSettingsPage() {
  const { token } = useAuth();
  const [records, setRecords] = useState<Record<Resource, MasterRecord[]>>({
    organizations: [], "organization-addresses": [], "gst-registrations": [], "bank-accounts": [],
  });
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [showOrganizationForm, setShowOrganizationForm] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const results = await Promise.all(resources.map((resource) => listMasterData(token, resource)));
      const next = Object.fromEntries(resources.map((resource, index) => [resource, results[index].items])) as Record<Resource, MasterRecord[]>;
      setRecords(next);
      setSelectedId((current) => current || next.organizations.find((item) => item.data.is_primary)?.id || next.organizations[0]?.id || "");
      setError(null);
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Unable to load organization settings.");
    }
  }, [token]);

  useEffect(() => void load(), [load]);
  const organization = records.organizations.find((item) => item.id === selectedId);
  const related = useMemo(() => ({
    addresses: records["organization-addresses"].filter((item) => item.data.organization_id === selectedId),
    gst: records["gst-registrations"].filter((item) => item.data.organization_id === selectedId),
    banks: records["bank-accounts"].filter((item) => item.data.organization_id === selectedId),
  }), [records, selectedId]);
  const defaultAddress = related.addresses.find((item) => item.data.is_default && item.is_active);

  async function perform(action: () => Promise<unknown>, success: string, form?: HTMLFormElement) {
    try {
      setError(null);
      await action();
      form?.reset();
      setMessage(success);
      await load();
    } catch (exception) {
      setMessage(null);
      setError(exception instanceof ApiError ? exception.message : "Unable to save organization settings.");
    }
  }

  function updateOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !organization) return;
    const data = new FormData(event.currentTarget);
    void perform(() => updateMasterData(token, "organizations", organization.id, {
      legal_name: String(data.get("legal_name")), trade_name: optional(data, "trade_name"),
      pan: optional(data, "pan"), email: optional(data, "email"), phone: optional(data, "phone"),
    }), "Organization profile updated.");
  }

  function createOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    void perform(async () => {
      const created = await createMasterData(token, "organizations", {
        code: String(data.get("code")), legal_name: String(data.get("legal_name")),
        trade_name: optional(data, "trade_name"), pan: optional(data, "pan"),
        email: optional(data, "email"), phone: optional(data, "phone"),
      });
      setSelectedId(created.id);
      setShowOrganizationForm(false);
    }, "World Communication organization configured.", form);
  }

  function addAddress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token || !selectedId) return;
    const form = event.currentTarget; const data = new FormData(form);
    void perform(() => createMasterData(token, "organization-addresses", {
      organization_id: selectedId, address_type: String(data.get("address_type")), label: String(data.get("label")),
      address_line_1: String(data.get("address_line_1")), address_line_2: optional(data, "address_line_2"),
      city: String(data.get("city")), district: optional(data, "district"), state: String(data.get("state")),
      state_code: optional(data, "state_code"), postal_code: String(data.get("postal_code")), country: String(data.get("country")),
      contact_name: optional(data, "contact_name"), phone: optional(data, "phone"), email: optional(data, "email"),
      is_default: data.get("is_default") === "on",
    }), "Address added.", form);
  }

  function addGst(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token || !selectedId) return;
    const form = event.currentTarget; const data = new FormData(form);
    void perform(() => createMasterData(token, "gst-registrations", {
      organization_id: selectedId, gstin: String(data.get("gstin")), registered_name: String(data.get("registered_name")),
      state: String(data.get("state")), state_code: String(data.get("state_code")), effective_from: String(data.get("effective_from")),
      effective_to: optional(data, "effective_to"), is_default: data.get("is_default") === "on",
    }), "GST registration added.", form);
  }

  function addBank(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token || !selectedId) return;
    const form = event.currentTarget; const data = new FormData(form);
    void perform(() => createMasterData(token, "bank-accounts", {
      organization_id: selectedId, account_name: String(data.get("account_name")), bank_name: String(data.get("bank_name")),
      branch_name: optional(data, "branch_name"), account_number: String(data.get("account_number")),
      account_type: optional(data, "account_type"), ifsc: String(data.get("ifsc")), swift: optional(data, "swift"),
      is_default: data.get("is_default") === "on",
    }), "Bank account added.", form);
  }

  function toggle(resource: Resource, record: MasterRecord) {
    if (!token) return;
    void perform(() => setMasterDataActive(token, resource, record.id, !record.is_active), `${record.is_active ? "Deactivated" : "Activated"} successfully.`);
  }

  function makePrimary() {
    if (!token || !organization) return;
    void (async () => {
      try {
        setError(null);
        await setPrimaryOrganization(token, organization.id);
        setMessage(`${text(organization, "legal_name")} is now the primary organization.`);
        await load();
      } catch (exception) {
        setMessage(null);
        const message = exception instanceof ApiError ? exception.message : "";
        setError(
          message && message !== "The request could not be completed."
            ? message
            : "Unable to set Primary Organization. Please try again.",
        );
      }
    })();
  }

  return <section className="organization-settings page-stack">
    <header className="page-heading"><p>SUPER-ADMIN</p><h1>Organization / Bank Settings</h1><span>Maintain World Communication identity and controlled financial master data.</span></header>
    <nav className="section-tabs" aria-label="Administration sections"><Link to="/users">Users &amp; Access</Link><Link className="active" to="/administration/organization-settings">Organization / Bank Settings</Link><Link to="/alerts">Alert Rules</Link></nav>
    {records.organizations.length > 1 && <label className="organization-picker">Organization<select aria-label="Organization" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{records.organizations.map((item) => <option key={item.id} value={item.id}>{text(item, "legal_name")}</option>)}</select></label>}
    {error && <p className="settings-feedback error" role="alert">{error}</p>}{message && <p className="settings-feedback success" role="status">{message}</p>}
    {!organization ? <section className="wcdms-card settings-card organization-empty"><header><div><h2>Organization Profile</h2><p>Configure World Communication, the company operating WCDMS.</p></div></header>{showOrganizationForm ? <form className="settings-form" onSubmit={createOrganization}>
      <label>Organization code<input name="code" placeholder="e.g. WC" required /></label><label>Legal name<input name="legal_name" placeholder="World Communication" required /></label><label>Trade name<input name="trade_name" /></label><label>PAN<input name="pan" maxLength={10} /></label><label>Email<input name="email" type="email" /></label><label>Phone<input name="phone" /></label><div className="settings-actions"><button className="button-secondary" onClick={() => setShowOrganizationForm(false)} type="button">Cancel</button><button className="button-primary" type="submit">Save organization</button></div>
    </form> : <div className="organization-empty-action"><p>No organization has been configured. Add World Communication before managing its addresses, GST registrations, and bank accounts.</p><button className="button-primary" onClick={() => setShowOrganizationForm(true)} type="button">Configure Organization</button></div>}</section> : <>
      <section className="wcdms-card settings-card"><header><div><h2>Organization Profile</h2><p>Authoritative legal identity used when creating new business documents.</p></div><div className="organization-profile-actions"><span className={`status-badge ${organization.is_active ? "enabled" : "disabled"}`}>{organization.is_active ? "ACTIVE" : "INACTIVE"}</span>{organization.data.is_primary ? <span className="status-badge primary">✓ PRIMARY</span> : <button className="button-secondary" onClick={makePrimary} type="button">Set as Primary Organization</button>}</div></header><form className="settings-form" onSubmit={updateOrganization} key={organization.updated_at}>
        <label>Organization code<input value={text(organization, "code")} disabled /></label><label>Legal name<input name="legal_name" defaultValue={text(organization, "legal_name")} required /></label><label>Trade name<input name="trade_name" defaultValue={text(organization, "trade_name")} /></label><label>PAN<input name="pan" defaultValue={text(organization, "pan")} maxLength={10} /></label><label>Email<input name="email" type="email" defaultValue={text(organization, "email")} /></label><label>Phone<input name="phone" defaultValue={text(organization, "phone")} /></label><div className="settings-actions"><button className="button-primary" type="submit">Save organization profile</button></div>
      </form></section>
      <SettingsTable title="Addresses" description="Registered, office, bill-to and dispatch/ship-to locations." columns={["Label", "Type", "Address", "Contact", "Default", "Status", "Action"]} empty="No organization addresses configured.">{related.addresses.map((item) => <tr key={item.id}><td>{text(item,"label")}</td><td>{text(item,"address_type")}</td><td>{[text(item,"address_line_1"),text(item,"address_line_2"),text(item,"city"),text(item,"state"),text(item,"postal_code")].filter(Boolean).join(", ")}</td><td>{text(item,"contact_name") || "—"}<br/><small>{text(item,"phone") || text(item,"email")}</small></td><td>{item.data.is_default ? "Yes" : "No"}</td><td>{item.is_active ? "Active" : "Inactive"}</td><td><button className="table-action" onClick={() => toggle("organization-addresses",item)} type="button">{item.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}</SettingsTable>
      <details className="wcdms-card settings-create"><summary>Add address</summary><form className="settings-form" onSubmit={addAddress}><label>Type<select name="address_type" required><option value="REGISTERED">Registered</option><option value="OFFICE">Office</option><option value="BILL_TO">Bill-to</option><option value="SHIP_TO">Ship-to / Dispatch</option></select></label><label>Label<input name="label" required /></label><label className="wide">Address line 1<input name="address_line_1" required /></label><label className="wide">Address line 2<input name="address_line_2" /></label><label>City<input name="city" required /></label><label>District<input name="district" /></label><label>State<input name="state" required /></label><label>State code<input name="state_code" maxLength={2} /></label><label>Postal code<input name="postal_code" required /></label><label>Country<input name="country" defaultValue="India" required /></label><label>Contact name<input name="contact_name" /></label><label>Phone<input name="phone" /></label><label>Email<input name="email" type="email" /></label><label className="check-field"><input name="is_default" type="checkbox" /> Default address</label><div className="settings-actions"><button className="button-primary" type="submit">Add address</button></div></form></details>
      <SettingsTable title="GST Registrations" description="Effective-dated registrations; changes apply only to newly created documents." columns={["GSTIN", "Registered name", "State", "Effective period", "Default", "Status", "Action"]} empty="No GST registrations configured.">{related.gst.map((item) => <tr key={item.id}><td>{text(item,"gstin")}</td><td>{text(item,"registered_name")}</td><td>{text(item,"state")} ({text(item,"state_code")})</td><td>{text(item,"effective_from")} – {text(item,"effective_to") || "Open"}</td><td>{item.data.is_default ? "Yes" : "No"}</td><td>{item.is_active ? "Active" : "Inactive"}</td><td><button className="table-action" onClick={() => toggle("gst-registrations",item)} type="button">{item.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}</SettingsTable>
      <details className="wcdms-card settings-create"><summary>Add GST registration</summary><form className="settings-form" onSubmit={addGst}><label>GSTIN<input name="gstin" maxLength={15} required /></label><label>Registered name<input name="registered_name" required /></label><label>State<input name="state" required /></label><label>State code<input name="state_code" maxLength={2} required /></label><label>Effective from<input name="effective_from" type="date" required /></label><label>Effective to<input name="effective_to" type="date" /></label><label className="check-field"><input name="is_default" type="checkbox" /> Default GST registration</label><div className="settings-actions"><button className="button-primary" type="submit">Add GST registration</button></div></form></details>
      <SettingsTable title="Bank Accounts" description="Sensitive financial master values. Account numbers are masked by the backend." columns={["Account name", "Bank / Branch", "Account", "IFSC", "Default", "Status", "Action"]} empty="No bank accounts configured.">{related.banks.map((item) => <tr key={item.id}><td>{text(item,"account_name")}</td><td>{text(item,"bank_name")}<br/><small>{text(item,"branch_name")}</small></td><td>{text(item,"account_number")}<br/><small>{text(item,"account_type")}</small></td><td>{text(item,"ifsc")}</td><td>{item.data.is_default ? "Yes" : "No"}</td><td>{item.is_active ? "Active" : "Inactive"}</td><td><button className="table-action" onClick={() => toggle("bank-accounts",item)} type="button">{item.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}</SettingsTable>
      <details className="wcdms-card settings-create"><summary>Add bank account</summary><form className="settings-form" onSubmit={addBank}><label>Account name<input name="account_name" required /></label><label>Bank name<input name="bank_name" required /></label><label>Branch name<input name="branch_name" /></label><label>Account number<input name="account_number" autoComplete="off" required /></label><label>Account type<input name="account_type" /></label><label>IFSC<input name="ifsc" maxLength={11} required /></label><label>SWIFT<input name="swift" maxLength={11} /></label><label className="check-field"><input name="is_default" type="checkbox" /> Default bank account</label><div className="settings-actions"><button className="button-primary" type="submit">Add bank account</button></div></form></details>
      <section className="wcdms-card default-settings"><h2>Default Document Settings</h2><div><span>Primary organization</span><strong>{organization.data.is_primary ? text(organization,"legal_name") : "Not configured"}</strong><span>Default address</span><strong className="default-address-value">{addressPresentation(defaultAddress)}</strong><span>Default GST registration</span><strong>{text(related.gst.find((item) => item.data.is_default && item.is_active),"gstin") || "Not configured"}</strong><span>Default bank account</span><strong>{text(related.banks.find((item) => item.data.is_default && item.is_active),"account_name") || "Not configured"}</strong></div><p>These defaults guide new document selection. Issued documents continue to render their persisted historical snapshots.</p></section>
    </>}
  </section>;
}

function SettingsTable({ title, description, columns, empty, children }: { title: string; description: string; columns: string[]; empty: string; children: ReactNode }) {
  const hasRows = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return <section className="wcdms-card settings-card settings-table"><header><div><h2>{title}</h2><p>{description}</p></div></header>{hasRows ? <div className="table-container"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{children}</tbody></table></div> : <p className="contained-empty">{empty}</p>}</section>;
}
