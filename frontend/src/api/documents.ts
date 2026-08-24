import { ApiError } from "./client";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export async function downloadDocument(
  token: string,
  type: string,
  id: string,
  format: "pdf" | "excel",
) {
  const response = await fetch(`${apiBaseUrl}/documents/${type}/${id}/${format}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new ApiError("Document export could not be generated.", response.status);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename =
    disposition.match(/filename="([^"]+)"/)?.[1] ??
    `document.${format === "pdf" ? "pdf" : "xlsx"}`;
  const url = URL.createObjectURL(await response.blob());
  const anchor = window.document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
