import { useEffect, useState } from "react";

import { getHealthStatus } from "../api/client";

export function StatusPage() {
  const [status, setStatus] = useState("Checking API connection…");

  useEffect(() => {
    void getHealthStatus()
      .then((health) => setStatus(`API ${health.status}`))
      .catch(() => setStatus("API status unavailable"));
  }, []);

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900 p-8 shadow-xl">
      <p className="text-sm font-medium tracking-[0.2em] text-cyan-400">WCDMS</p>
      <h1 className="mt-3 text-3xl font-semibold">Foundation status</h1>
      <p className="mt-4 text-slate-300">The application foundation is ready for the next approved phase.</p>
      <p className="mt-8 rounded-md bg-slate-800 px-4 py-3 text-sm" role="status">
        {status}
      </p>
    </section>
  );
}
