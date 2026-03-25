import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ET Autopilot — Autonomous Enterprise Workflows",
  description: "Multi-agent AI that plans, executes, verifies and recovers enterprise workflows with zero hand-holding.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
