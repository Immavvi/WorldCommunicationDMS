import { apiRequest } from "./client";

export type AssetEvent = {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string;
  to_location_snapshot: string | null;
  event_at: string;
  reason: string;
};

export type Asset = {
  id: string;
  asset_number: string;
  manufacturer_serial_number: string;
  product_snapshot: string;
  oem_snapshot: string | null;
  model_snapshot: string | null;
  status: string;
  project_snapshot: string;
  loa_snapshot: string | null;
  current_site: string | null;
  current_building: string | null;
  current_room: string | null;
  current_rack: string | null;
  current_position: string | null;
  warranty_expiry_date: string | null;
  events: AssetEvent[];
};

export type RegistrationPosition = {
  material_receipt_line_id: string;
  receipt_number: string;
  product_snapshot: string;
  accepted_quantity: number;
  already_registered: number;
  remaining_quantity: number;
};

export const listAssets = (token: string, search = "") =>
  apiRequest<Asset[]>(`/assets${search ? `?search=${encodeURIComponent(search)}` : ""}`, { token });
export const assetRegistrationPositions = (token: string) =>
  apiRequest<RegistrationPosition[]>("/assets/registration-position", { token });
export const registerAssets = (token: string, materialReceiptLineId: string, serials: string[]) =>
  apiRequest<Asset[]>("/assets/register", {
    method: "POST",
    token,
    body: JSON.stringify({
      material_receipt_line_id: materialReceiptLineId,
      assets: serials.map((manufacturer_serial_number) => ({ manufacturer_serial_number })),
    }),
  });
export const transitionAsset = (token: string, assetId: string, action: string, reason: string) =>
  apiRequest<Asset>(`/assets/${assetId}/actions`, {
    method: "POST",
    token,
    body: JSON.stringify({ action, reason }),
  });
