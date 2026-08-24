import type { ReactNode, SVGProps } from "react";

const paths: Record<string, ReactNode> = {
  dashboard: <><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></>,
  projects: <><path d="M3 7h18v13H3z"/><path d="M8 7V4h8v3"/></>,
  document: <><path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6M9 13h8M9 17h8"/></>,
  cart: <><path d="M3 4h2l2.5 11h10l2-7H7"/><circle cx="9" cy="20" r="1"/><circle cx="17" cy="20" r="1"/></>,
  receipt: <><path d="M12 3a9 9 0 1 0 7 14"/><path d="M12 7v6l4 2M18 4v5h5"/></>,
  asset: <><rect x="5" y="9" width="14" height="11" rx="2"/><path d="M8 9V6a4 4 0 0 1 8 0v3M12 13v3"/></>,
  truck: <><path d="M3 6h11v11H3zM14 10h4l3 4v3h-7z"/><circle cx="7" cy="19" r="2"/><circle cx="18" cy="19" r="2"/></>,
  payment: <><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M8 15h4"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  report: <><path d="M5 3h14v18H5zM9 17v-4M12 17V9M15 17v-7"/></>,
  master: <><circle cx="12" cy="12" r="3"/><path d="M19 15l2 1-2 4-2-1a8 8 0 0 1-3 2v2h-4v-2a8 8 0 0 1-3-2l-2 1-2-4 2-1a8 8 0 0 1 0-4L3 10l2-4 2 1a8 8 0 0 1 3-2V3h4v2a8 8 0 0 1 3 2l2-1 2 4-2 1a8 8 0 0 1 0 4z"/></>,
  shield: <path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/>, chevron: <path d="M15 18l-6-6 6-6"/>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3M15 4h5v16h-5"/></>, arrow: <path d="M5 12h14M15 8l4 4-4 4"/>,
  alert: <><path d="M12 3L2 21h20z"/><path d="M12 9v5M12 18h.01"/></>, box: <><path d="M4 7l8-4 8 4-8 4zM4 7v10l8 4 8-4V7M12 11v10"/></>,
};
export function Icon({name,...props}:{name:string}&SVGProps<SVGSVGElement>){return <svg aria-hidden="true" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" viewBox="0 0 24 24" {...props}>{paths[name]??paths.document}</svg>}
