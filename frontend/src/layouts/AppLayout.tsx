import { useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { DocumentExports } from "../components/DocumentExports";
import { Icon } from "../components/Icon";
import { NotificationBell } from "../components/NotificationBell";

const exports = [[/^\/quotations\/([^/]+)$/, "quotation"],[/^\/purchase-orders\/([^/]+)$/, "purchase-order"],[/^\/proforma-invoices\/([^/]+)$/, "proforma-invoice"],[/^\/tax-invoices\/([^/]+)$/, "tax-invoice"],[/^\/supply-challans\/([^/]+)$/, "supply-challan"]] as const;
const nav = [["/","Dashboard","dashboard"],["/projects","Projects","projects"],["/projects#loas","LOA / Contracts","document"],["/procurement","Procurement & POs","cart"],["/receiving","GRN / Receipts","receipt"],["/assets","Assets","asset"],["/dispatch","Supply Challans","truck"],["/quotations","Quotations","document"],["/proforma-invoices","Proforma Invoices","document"],["/tax-invoices","Tax Invoices","document"],["/payments","Payments","payment"],["/receivables","Receivables","document"],["/alerts","Alerts","bell"],["/reports","Reports","report"],["/master-data","Master Data","master"]] as const;

export function AppLayout({children}:{children:ReactNode}) {
  const {logout,user}=useAuth(); const location=useLocation(); const [collapsed,setCollapsed]=useState(false); const [mobile,setMobile]=useState(false);
  const exportRoute=exports.map(([pattern,type])=>({match:location.pathname.match(pattern),type})).find(x=>x.match);
  if(!user)return <main className="login-shell">{children}</main>;
  const isSuper=user.roles.some(r=>r.name==="SUPER-ADMIN"); const display=user.display_name?.trim()||user.email.split("@")[0]; const initials=display.split(/\s+/).slice(0,2).map(x=>x[0]?.toUpperCase()).join(""); const profileImage=user.email.toLowerCase()==="sanjiva.kumar@worldcommunication.in"?"/profile-images/sanjiva-kumar.jpg":null;
  return <div className={`app-shell ${collapsed?"sidebar-collapsed":""} ${mobile?"mobile-open":""}`}>
    <aside className="app-sidebar"><Link className="brand" to="/" aria-label="World Communication home"><img src="/world-communication-logo.png" alt="World Communication"/></Link>
      <nav className="sidebar-nav" aria-label="Primary navigation">{nav.map(([to,label,icon])=><NavLink key={to} to={to} end={to==="/"} onClick={()=>setMobile(false)} title={collapsed?label:undefined}><Icon name={icon}/><span>{label}</span></NavLink>)}{isSuper&&<NavLink aria-label="Administration" to="/administration"><Icon name="shield"/><span>Administration<small>SUPER-ADMIN ONLY</small></span></NavLink>}</nav>
      <button className="collapse-button" onClick={()=>setCollapsed(!collapsed)} type="button"><Icon name="chevron"/><span>Collapse Menu</span></button>
    </aside>
    <header className="app-header"><button className="mobile-menu" onClick={()=>setMobile(!mobile)} aria-label="Toggle navigation">☰</button><h1>WORLD COMMUNICATION DOCUMENT MANAGEMENT SYSTEM</h1><div className="header-account"><NotificationBell/><Link className="account-link" to="/profile"><span className="avatar">{initials}{profileImage&&<img src={profileImage} alt={`${display} profile`}/>}</span><span><strong>{display}</strong><small>{user.roles.map(r=>r.name).join(", ")}</small></span></Link><button className="logout-button" onClick={logout} title="Logout" aria-label="Logout"><Icon name="logout"/></button></div></header>
    <main className="app-content">{exportRoute?.match&&<DocumentExports type={exportRoute.type} id={exportRoute.match[1]}/>} {children}</main>
    <footer className="app-footer"><span>© {new Date().getFullYear()} World Communication. All rights reserved.</span><a href="https://www.worldcommunication.in">www.worldcommunication.in</a><span>WCDMS V1.0.0</span></footer>
    {mobile&&<button className="sidebar-backdrop" onClick={()=>setMobile(false)} aria-label="Close navigation"/>}
  </div>;
}
