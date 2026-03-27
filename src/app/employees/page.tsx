"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Employee {
  id: string;
  employee_id: string | null;
  name: string;
  email: string;
  company_email: string | null;
  role: string;
  department: string;
  buddy: string | null;
  status: string;
  created_at: string;
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/employees`)
      .then((r) => r.json())
      .then(setEmployees)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ minHeight: "100vh", padding: 24, background: "var(--bg-primary)" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 32 }}>
          <div>
            <h1 style={{ fontSize: "1.6rem", fontWeight: 800, marginBottom: 4, color: "var(--text-bright)" }}>
              Employee Directory
            </h1>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              {employees.length} employees registered
            </p>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <a href="/" className="btn-secondary">← Back</a>
          </div>
        </div>

        {/* Table */}
        <div className="panel" style={{ overflow: "auto" }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: "center" }}>
              <div className="spinner" style={{ margin: "0 auto" }} />
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-sans)" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Employee ID", "Name", "Email", "Company Email", "Role", "Department", "Buddy", "Status", "Joined"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "12px 16px", textAlign: "left", fontSize: "0.65rem",
                        fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em",
                        color: "var(--text-muted)", fontFamily: "var(--font-mono)"
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {employees.map((emp) => (
                  <tr key={emp.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={cellStyle}>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent)", fontWeight: 600 }}>
                        {emp.employee_id || "—"}
                      </span>
                    </td>
                    <td style={{ ...cellStyle, fontWeight: 600, color: "var(--text-bright)" }}>{emp.name}</td>
                    <td style={cellStyle}>{emp.email}</td>
                    <td style={cellStyle}>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: emp.company_email ? "var(--success)" : "var(--text-muted)" }}>
                        {emp.company_email || "—"}
                      </span>
                    </td>
                    <td style={cellStyle}>{emp.role}</td>
                    <td style={cellStyle}>{emp.department}</td>
                    <td style={cellStyle}>{emp.buddy || "—"}</td>
                    <td style={cellStyle}>
                      <span className={`badge badge-${emp.status.toLowerCase()}`}>
                        {emp.status === "ACTIVE" && "●"} {emp.status}
                      </span>
                    </td>
                    <td style={{ ...cellStyle, color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.7rem" }}>
                      {new Date(emp.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

const cellStyle: React.CSSProperties = {
  padding: "12px 16px",
  fontSize: "0.8rem",
  color: "var(--text-secondary)",
};

