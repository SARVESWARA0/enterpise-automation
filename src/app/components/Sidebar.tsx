"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Sidebar() {
  const pathname = usePathname();
  
  return (
    <nav style={{ width: 220, background: "var(--bg-secondary)", borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "20px 24px", fontFamily: "var(--font-mono)", fontWeight: 800, color: "var(--text-bright)", letterSpacing: "-0.02em" }}>
        <span style={{ color: "var(--accent)" }}></span> Autopilot
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, padding: "0 12px" }}>
        <NavItem href="/" icon="•" label="Home" active={pathname === "/"} />
        <NavItem href="/employees" icon="•" label="Employees" active={pathname === "/employees"} />
        <NavItem href="/workflows" icon="•" label="Workflows" active={pathname?.startsWith("/workflows")} />
        <NavItem href="/audits" icon="•" label="Audit Logs" active={pathname === "/audits"} />
      </div>
    </nav>
  );
}

function NavItem({ href, icon, label, active }: { href: string; icon: string; label: string; active?: boolean }) {
  return (
    <Link href={href} style={{
      display: "flex", alignItems: "center", gap: 12, padding: "10px 16px",
      borderRadius: "var(--radius-sm)", 
      color: active ? "var(--text-bright)" : "var(--text-secondary)",
      background: active ? "var(--bg-hover)" : "transparent",
      textDecoration: "none", fontSize: "0.85rem", fontWeight: 500,
      transition: "background 0.2s, color 0.2s"
    }}
      onMouseOver={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-bright)"; }}
      onMouseOut={(e) => { 
        if (!active) {
            e.currentTarget.style.background = "transparent"; 
            e.currentTarget.style.color = "var(--text-secondary)"; 
        }
      }}
    >
      <span style={{ fontSize: "1.1rem" }}>{icon}</span> {label}
    </Link>
  );
}
