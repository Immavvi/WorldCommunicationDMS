import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return <section><h1 className="text-3xl font-semibold">Access denied</h1><p className="mt-3 text-slate-300">You do not have permission to view this page.</p><Link className="mt-6 inline-block text-cyan-400" to="/">Return to status</Link></section>;
}
