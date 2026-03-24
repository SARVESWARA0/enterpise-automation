'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { href: '/', label: 'Dashboard', icon: '◆' },
  { href: '/employees', label: 'Employees', icon: '◈' },
  { href: '/workflows', label: 'Workflows', icon: '▶' },
  { href: '/workflows/new', label: 'Custom Workflow', icon: '✦' },
  { href: '/sla', label: 'SLA Monitor', icon: '⚡' },
  { href: '/audit', label: 'Audit Trail', icon: '◉' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '36px', height: '36px',
            background: 'linear-gradient(135deg, var(--gradient-start), var(--gradient-end))',
            borderRadius: '10px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.1rem',
          }}>⟡</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>Autopilot</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Enterprise</div>
          </div>
        </div>
      </div>

      <nav style={{ flex: 1, paddingTop: '12px' }}>
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href) && item.href !== '/workflows/new');
          return (
            <Link key={item.href} href={item.href} className={`sidebar-link ${isActive ? 'active' : ''}`}>
              <span style={{ fontSize: '1rem', width: '20px', textAlign: 'center' }}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
          <div className="pulse-dot" style={{ background: 'var(--success)' }} />
          System Online
        </div>
        <div>Multi-Agent Orchestrator v2.0</div>
      </div>
    </aside>
  );
}
