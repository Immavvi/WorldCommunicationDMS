import { FormEvent, useEffect, useState } from "react";

import {
  assetRegistrationPositions,
  listAssets,
  registerAssets,
  transitionAsset,
  type Asset,
  type RegistrationPosition,
} from "../api/assets";
import { useAuth } from "../auth/AuthContext";

export function AssetsPage() {
  const { token, user } = useAuth();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [positions, setPositions] = useState<RegistrationPosition[]>([]);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [receiptLine, setReceiptLine] = useState("");
  const [serials, setSerials] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  const refresh = async () => {
    try {
      const [assetRows, positionRows] = await Promise.all([
        listAssets(token!, search),
        assetRegistrationPositions(token!),
      ]);
      setAssets(assetRows);
      setPositions(positionRows);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load Assets.");
    }
  };

  useEffect(() => {
    void refresh();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const values = serials.split("\n").map((value) => value.trim()).filter(Boolean);
      await registerAssets(token!, receiptLine, values);
      setSerials("");
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Asset registration failed.");
    }
  };

  const location = (asset: Asset) =>
    [asset.current_site, asset.current_building, asset.current_room, asset.current_rack, asset.current_position]
      .filter(Boolean)
      .join(" / ") || "—";

  const runAction = async (action: string) => {
    if (!selected) return;
    try {
      const updated = await transitionAsset(token!, selected.id, action, `${action} from Asset register`);
      setSelected(updated);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Asset action failed.");
    }
  };

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Assets</h1>
      {error && <p role="alert" className="text-red-300">{error}</p>}
      <form className="rounded border border-slate-700 p-4" onSubmit={submit}>
        <h2 className="mb-3 font-semibold">Register serial numbers from accepted receipt</h2>
        <select aria-label="Eligible receipt line" value={receiptLine} onChange={(event) => setReceiptLine(event.target.value)} required>
          <option value="">Select accepted receipt line</option>
          {positions.filter((row) => row.remaining_quantity > 0).map((row) => (
            <option value={row.material_receipt_line_id} key={row.material_receipt_line_id}>
              {row.receipt_number} — {row.product_snapshot} — Accepted: {row.accepted_quantity}, Registered: {row.already_registered}, Remaining: {row.remaining_quantity}
            </option>
          ))}
        </select>
        <textarea className="mt-3 block w-full bg-slate-900 p-2" aria-label="Serial numbers" placeholder="One manufacturer serial number per line" value={serials} onChange={(event) => setSerials(event.target.value)} required />
        <button className="mt-3 text-cyan-400" type="submit">Register Assets</button>
      </form>
      <div className="flex gap-2">
        <input aria-label="Search assets" className="bg-slate-900 p-2" value={search} onChange={(event) => setSearch(event.target.value)} />
        <button type="button" onClick={() => void refresh()}>Search</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead><tr><th>Asset</th><th>Serial</th><th>Product / OEM / Model</th><th>Status</th><th>Project</th><th>Location</th><th>Warranty</th></tr></thead>
          <tbody>{assets.map((asset) => (
            <tr key={asset.id} onClick={() => setSelected(asset)} className="cursor-pointer border-t border-slate-800">
              <td>{asset.asset_number}</td><td>{asset.manufacturer_serial_number}</td><td>{[asset.product_snapshot, asset.oem_snapshot, asset.model_snapshot].filter(Boolean).join(" / ")}</td><td>{asset.status}</td><td>{asset.project_snapshot}</td><td>{location(asset)}</td><td>{asset.warranty_expiry_date ?? "—"}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {selected && <article className="rounded border border-slate-700 p-4">
        <h2 className="font-semibold">{selected.asset_number} lifecycle</h2>
        <p>Source: {selected.project_snapshot}{selected.loa_snapshot ? ` / ${selected.loa_snapshot}` : ""}</p>
        <p>Location: {location(selected)}</p>
        <p>Warranty expiry: {selected.warranty_expiry_date ?? "Not recorded"}</p>
        <div className="flex gap-3">
          {selected.status === "REGISTERED" && <button type="button" onClick={() => void runAction("MAKE_AVAILABLE")}>Make available</button>}
          {selected.status === "AVAILABLE" && <button type="button" onClick={() => void runAction("ALLOCATE")}>Allocate</button>}
          {user?.roles.some((role) => role.name === "SUPER-ADMIN") && !["RETIRED", "DISPOSED"].includes(selected.status) && <button type="button" onClick={() => void runAction("RETIRE")}>Retire</button>}
        </div>
        <ol>{selected.events.map((event) => <li key={event.id}>{event.event_at}: {event.event_type} → {event.to_status} — {event.reason}</li>)}</ol>
      </article>}
    </section>
  );
}
