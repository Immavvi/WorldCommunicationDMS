import { useEffect,useMemo,useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { listAssets,type Asset } from "../api/assets";
import { myAttention,type Alert } from "../api/attention";
import { listLoas,listProjects,type Loa,type Project } from "../api/contracts";
import { getDashboard,type Dashboard } from "../api/reporting";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icon";

const indian=(value:string|number)=>`₹${Number(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const relative=(value:string)=>{const hours=Math.max(0,Math.floor((Date.now()-new Date(value).getTime())/3600000));return hours<1?"Just now":hours<24?`${hours}h ago`:`${Math.floor(hours/24)}d ago`};
const metricConfig=[
  ["active_projects","Active Projects","projects","/projects","View all projects"],["active_loas","Active LOAs","document","/projects#loas","View all LOAs"],
  ["active_purchase_orders","Open POs","cart","/procurement","View all POs"],["overdue_deliveries","Pending Deliveries","truck","/procurement","View all deliveries"],
  ["open_requirements","Open Requirements","receipt","/procurement","View requirements"],["dispatched_quantity","Dispatched Quantity","document","/dispatch","View all challans"],
  ["assets_installed","Assets Installed","box","/assets","View all assets"],["critical_alerts","Critical Alerts","alert","/alerts","View all alerts"],
] as const;

export function DashboardPage(){const {token,user}=useAuth();const [data,setData]=useState<Dashboard|null>(null);const [alerts,setAlerts]=useState<Alert[]>([]);const [projects,setProjects]=useState<Project[]>([]);const [loas,setLoas]=useState<Loa[]>([]);const [assets,setAssets]=useState<Asset[]>([]);
  useEffect(()=>{if(!token)return;void Promise.all([getDashboard(token),myAttention(token),listProjects(token),listLoas(token),listAssets(token)]).then(([d,a,p,l,s])=>{setData(d);setAlerts(a);setProjects(p);setLoas(l);setAssets(s)});},[token]);
  const now=new Date();const hour=now.getHours();const greeting=hour<12?"Good Morning":hour<17?"Good Afternoon":"Good Evening";const name=user?.display_name?.trim()||user?.email.split("@")[0]||"";
  const assetCounts=useMemo(()=>assets.reduce<Record<string,number>>((acc,a)=>{acc[a.status]=(acc[a.status]??0)+1;return acc},{}),[assets]);
  if(!data)return <div className="dashboard-loading">Loading dashboard…</div>;
  const operational=data.operational;const financial=data.financial;return <section className="dashboard"><h1 className="sr-only">Dashboard</h1>
    <header className="dashboard-greeting"><div><h2>{greeting}, {name}</h2><p>Here's what's happening with your business today.</p></div><div className="date-card"><span>▣ {now.toLocaleDateString("en-IN",{day:"2-digit",month:"long",year:"numeric",weekday:"long"})}</span><span>◷ {now.toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"})}</span></div></header>
    <div className="metric-grid">{metricConfig.map(([key,label,icon,to,action])=><Link className="metric-card" to={to} key={key}><span className="metric-icon"><Icon name={icon}/></span><span className="metric-body"><span>{label}</span><strong>{String(operational[key]??0)}</strong><small>{action}<Icon name="arrow"/></small></span></Link>)}</div>
    <div className="dashboard-middle"><section className="panel attention-panel"><h3>MY ATTENTION</h3>{alerts.length===0?<p className="empty-message">No active items require your attention.</p>:alerts.slice(0,4).map(a=><Link to="/alerts" key={a.id} className="attention-row"><i className={`severity ${a.severity.toLowerCase()}`}/><span>{a.title}</span><time>{relative(a.triggered_at)}</time></Link>)}<Link className="panel-action" to="/alerts">View All Alerts <Icon name="arrow"/></Link></section>
      <section className="panel project-panel"><div className="panel-title"><h3>PROJECT OVERVIEW</h3><Link to="/projects">View All Projects <Icon name="arrow"/></Link></div><div className="table-scroll"><table><thead><tr><th>Project Name</th><th>Scope</th><th>LOA No.</th><th>PO Progress</th><th>Received</th><th>Dispatch</th><th>Billing</th></tr></thead><tbody>{projects.length===0?<tr><td colSpan={7} className="empty-cell">No active projects yet.</td></tr>:projects.slice(0,4).map(p=><tr key={p.id}><td>{p.name}</td><td>{p.business_scope.replace("_"," ")}</td><td>{loas.find(l=>l.project_id===p.id)?.loa_number??"—"}</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>)}</tbody></table></div></section></div>
    <div className="dashboard-bottom">{financial&&<section className="panel financial-panel"><h2 className="sr-only">Finance &amp; Collections</h2><h3>FINANCIAL OVERVIEW <small>(This Financial Year)</small></h3><div>{[["invoice_value","Tax Invoiced"],["received","Amount Received"],["outstanding","Outstanding"],["overdue_outstanding","Overdue"]].map(([key,label])=><Link to={key==="received"?"/payments":key==="invoice_value"?"/tax-invoices":"/receivables"} key={key}><span className="finance-icon">₹</span><small>{label}</small><strong>{indian(financial[key]??0)}</strong></Link>)}</div></section>}
      <section className="panel billing-panel"><h3>MONTHLY BILLING VS COLLECTION</h3><div className="chart-empty"><span className="bar-symbol"/><p>Monthly series is not available from the current reporting API.</p></div></section>
      <section className="panel asset-panel"><h3>ASSET STATUS</h3><div className="asset-content"><div className="donut" style={{"--installed":`${assets.length?((assetCounts.INSTALLED??0)+(assetCounts.IN_SERVICE??0))/assets.length*100:0}%`} as CSSProperties}><span><strong>{assets.length}</strong>Total Assets</span></div><div className="asset-legend">{[["INSTALLED","Installed"],["AVAILABLE","Available"],["UNDER_REPAIR","Under Repair"],["DAMAGED","Damaged"]].map(([key,label])=><p key={key}><i className={key.toLowerCase()}/><span>{label}</span><strong>{assetCounts[key]??0}</strong></p>)}</div></div></section>
    </div>
  </section>}
