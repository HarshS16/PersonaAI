import { api } from "@/lib/api";

async function download(path: string, filename: string): Promise<void> {
  const res = await fetch(`/api/backend${path}`, { credentials: "include" });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const accountApi = {
  exportJson: () => download("/account/export", "persona-export.json"),
  exportZip: () => download("/account/export.zip", "persona-export.zip"),
  deleteAccount: (password?: string) =>
    api<void>("/account/delete", {
      method: "POST",
      body: JSON.stringify({ password: password || null }),
    }),
};
