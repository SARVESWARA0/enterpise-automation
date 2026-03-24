import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Enterprise Autopilot — Multi-Agent Workflow System",
  description: "Autonomous enterprise workflow execution with multi-agent orchestration, real-time streaming, and complete audit trails.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Sidebar />
        <main className="main-content">{children}</main>
      </body>
    </html>
  );
}
