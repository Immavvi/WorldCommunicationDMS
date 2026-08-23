import { apiRequest } from "./client";

export type MasterRecord = {
  id: string;
  resource: string;
  data: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type MasterList = { items: MasterRecord[]; total: number; offset: number; limit: number };

export function listMasterData(token: string, resource: string): Promise<MasterList> {
  return apiRequest<MasterList>(`/master-data/${resource}`, { token });
}

export function createMasterData(
  token: string,
  resource: string,
  data: Record<string, unknown>,
): Promise<MasterRecord> {
  return apiRequest<MasterRecord>(`/master-data/${resource}`, {
    method: "POST",
    token,
    body: JSON.stringify(data),
  });
}

export function setMasterDataActive(
  token: string,
  resource: string,
  id: string,
  active: boolean,
): Promise<MasterRecord> {
  return apiRequest<MasterRecord>(`/master-data/${resource}/${id}/active?active=${active}`, {
    method: "PATCH",
    token,
  });
}
