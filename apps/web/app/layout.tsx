import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "RelayGuard — Crash-safe memory for incident agents",
  description: "Read-only audit dashboard for RelayGuard demo incidents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
