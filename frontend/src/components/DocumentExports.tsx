import { useState } from "react";

import { downloadDocument } from "../api/documents";
import { useAuth } from "../auth/AuthContext";

export function DocumentExports({ type, id }: { type: string; id: string }) {
  const { token } = useAuth();
  const [error, setError] = useState("");

  async function download(format: "pdf" | "excel") {
    if (!token) return;
    setError("");
    try {
      await downloadDocument(token, type, id, format);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Document export failed.");
    }
  }

  return (
    <div className="mb-6 space-x-3 rounded border border-slate-700 p-3">
      <button onClick={() => void download("pdf")}>Download / Preview PDF</button>
      <button onClick={() => void download("excel")}>Download / Preview Excel</button>
      <span className="text-xs text-slate-400">Draft exports are marked DRAFT.</span>
      {error && <p role="alert" className="text-red-300">{error}</p>}
    </div>
  );
}
