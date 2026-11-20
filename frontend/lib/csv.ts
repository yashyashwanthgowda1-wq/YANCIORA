/** CSV export (RFC 4180 quoting), with a UTF-8 BOM so spreadsheet apps read Indic text correctly. */

export type Cell = string | number | boolean | null | undefined;

export function csvCell(v: Cell): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv(header: string[], rows: Cell[][]): string {
  return [header, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
}

export function downloadText(filename: string, content: string, mime: string): void {
  const withBom = mime.startsWith("text/csv") ? "﻿" + content : content;
  const url = URL.createObjectURL(new Blob([withBom], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
