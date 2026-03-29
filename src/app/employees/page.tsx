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
    <div className="page-container">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Employee Directory</h1>
          <p>{employees.length} employees registered</p>
        </div>
      </div>

      <div className="panel" style={{ overflow: "auto" }}>
        {loading ? (
          <div className="loading-state">
            <div className="spinner" />
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Employee ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Company Email</th>
                <th>Role</th>
                <th>Department</th>
                <th>Buddy</th>
                <th>Status</th>
                <th>Joined</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((emp) => (
                <tr key={emp.id} style={{ cursor: "default" }}>
                  <td className="cell-accent">{emp.employee_id || "—"}</td>
                  <td className="cell-bright">{emp.name}</td>
                  <td>{emp.email}</td>
                  <td>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: emp.company_email ? "var(--success)" : "var(--text-muted)" }}>
                      {emp.company_email || "—"}
                    </span>
                  </td>
                  <td>{emp.role}</td>
                  <td>{emp.department}</td>
                  <td>{emp.buddy || "—"}</td>
                  <td>
                    <span className={`badge badge-${emp.status.toLowerCase()}`}>
                      {emp.status}
                    </span>
                  </td>
                  <td className="cell-mono">{new Date(emp.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
