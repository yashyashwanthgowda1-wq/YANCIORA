import type { Metadata, Viewport } from "next";
import { AppShell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "REDUTAX", template: "%s · REDUTAX" },
  description: "Indic-aware token efficiency and evaluation framework — Team YANCIORA (No. 46).",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#FFFFFF" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
