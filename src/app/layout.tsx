import type { Metadata } from "next";
import "./globals.css";

import Sidebar from "./components/Sidebar";

export const metadata: Metadata = {
  title: "ET Autopilot — Autonomous Enterprise Workflows",
  description: "Multi-agent AI that plans, executes, verifies and recovers enterprise workflows with zero hand-holding.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
        <Sidebar />
        {/* Main Content Area */}
        <main style={{ flex: 1, overflowY: "auto", background: "var(--bg-primary)" }}>
          {children}
        </main>
      </body>
    </html>
  );
}

