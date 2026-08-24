import { useEffect,useState } from "react";
import { Link } from "react-router-dom";
import { getNumbering,getSystemStatus,type Numbering,type SystemStatus } from "../api/administration";
import { useAuth } from "../auth/AuthContext";

export function AdministrationPage(){const {token}=useAuth();const [numbering,setNumbering]=useState<Numbering[]>([]);const [status,setStatus]=useState<SystemStatus|null>(null);useEffect(()=>{if(token)void Promise.all([getNumbering(token),getSystemStatus(token)]).then(([n,s])=>{setNumbering(n);setStatus(s);});},[token]);return <section className="admin-page page-stack">
  <header className="page-heading"><p>SUPER-ADMIN</p><h1>Administration</h1></header>
  <nav className="section-tabs" aria-label="Administration sections"><Link className="active" to="/users">Users &amp; Access</Link><Link to="/administration/organization-settings">Organization / Bank Settings</Link><Link to="/alerts">Alert Rules</Link></nav>
  <section className="wcdms-card system-card"><h2>System Status</h2>{status?<dl><div><dt>Application</dt><dd>{status.application} {status.version}</dd></div><div><dt>Environment</dt><dd>{status.environment}</dd></div><div><dt>Database</dt><dd><span className={`status-dot ${status.database==="connected"?"success":"danger"}`}/>{status.database}</dd></div><div><dt>Schema revision</dt><dd>{status.schema_revision}</dd></div></dl>:<p className="contained-empty">Loading system status…</p>}</section>
  <section className="wcdms-card numbering-card"><h2>Numbering</h2><p>Read-only visibility protects issued numbers and concurrency-safe sequences.</p><div className="table-container"><table><thead><tr><th>Type</th><th>Prefix</th><th>Next sequence</th><th>Preview</th></tr></thead><tbody>{numbering.map(row=><tr key={row.id}><td>{row.document_type}</td><td>{row.prefix}</td><td>{row.next_number}</td><td>{row.preview}</td></tr>)}</tbody></table></div></section>
  <p className="page-note">Backups and migrations remain deployment operations and cannot be run from this page.</p>
</section>}
