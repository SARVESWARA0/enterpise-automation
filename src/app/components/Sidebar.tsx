"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: "⌂" },
  { href: "/employees", label: "Employees", icon: "◉" },
  { href: "/workflows", label: "Workflows", icon: "▸" },
  { href: "/tasks", label: "Project Tracker", icon: "☰" },
  { href: "/sla", label: "SLA Prevention", icon: "⏱" },
  { href: "/onboarding", label: "Onboarding", icon: "★" },
  { href: "/audits", label: "Audit Logs", icon: "⎔" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <nav style={{
      width: 230,
      background: "var(--bg-secondary)",
      borderRight: "1px solid var(--border)",
      display: "flex",
      flexDirection: "column",
    }}>
      {/* Logo */}
      <div style={{
        padding: "22px 24px 18px",
        fontFamily: "var(--font-mono)",
        fontWeight: 800,
        fontSize: "0.9rem",
        color: "var(--text-bright)",
        letterSpacing: "-0.02em",
        borderBottom: "1px solid var(--border)",
      }}>
        <span style={{ color: "var(--accent)" }}>ET</span> Autopilot
      </div>

      {/* Nav Items */}
      <div style={{ display: "flex", flexDirection: "column", gap: 2, padding: "12px 10px", flex: 1 }}>
        {NAV_ITEMS.map((item) => {
          const isActive = item.href === "/"
            ? pathname === "/"
            : pathname?.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 14px",
                borderRadius: "var(--radius-sm)",
                color: isActive ? "var(--text-bright)" : "var(--text-secondary)",
                background: isActive ? "rgba(99,102,241,0.08)" : "transparent",
                borderLeft: isActive ? "2px solid var(--accent)" : "2px solid transparent",
                textDecoration: "none",
                fontSize: "0.85rem",
                fontWeight: isActive ? 600 : 500,
                transition: "all 0.15s ease",
              }}
            >
              <span style={{ fontSize: "0.9rem", width: 20, textAlign: "center", opacity: isActive ? 1 : 0.5 }}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </div>

      {/* Footer */}
      <div style={{
        padding: "12px 16px",
        borderTop: "1px solid var(--border)",
        fontSize: "0.65rem",
        color: "var(--text-muted)",
        fontFamily: "var(--font-mono)",
      }}>
        v2.0 — Hackathon 2026
      </div>
    </nav>
  );
}
