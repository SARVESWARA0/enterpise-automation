'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface Employee {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  status: string;
  createdAt: string;
  workflows?: Array<{ id: string; type: string; status: string }>;
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', role: '', department: '' });
  const router = useRouter();

  const fetchEmployees = () => {
    fetch('/api/employees').then(r => r.json()).then(d => { setEmployees(d); setLoading(false); }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchEmployees(); const i = setInterval(fetchEmployees, 4000); return () => clearInterval(i); }, []);

  const handleCreate = async () => {
    if (!form.name || !form.email || !form.role || !form.department) return;
    setCreating(true);
    try {
      const res = await fetch('/api/employees', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok) {
        setShowModal(false);
        setForm({ name: '', email: '', role: '', department: '' });
        fetchEmployees();
        // Redirect to the workflow execution page
        if (data.workflowId) {
          router.push(`/workflows/${data.workflowId}`);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">Employees</h1>
          <p className="page-subtitle">Manage employees — creating an employee auto-triggers onboarding</p>
        </div>
        <button className="btn-primary" onClick={() => setShowModal(true)}>
          <span>+</span> Create Employee
        </button>
      </div>

      <div className="glass-card" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" style={{ margin: '0 auto' }} /></div>
        ) : employees.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>No employees yet. Click &quot;Create Employee&quot; to start!</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Department</th>
                <th>Status</th>
                <th>Latest Workflow</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((emp) => (
                <tr key={emp.id}>
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{emp.name}</td>
                  <td>{emp.email}</td>
                  <td>{emp.role}</td>
                  <td>{emp.department}</td>
                  <td><span className={`badge badge-${emp.status.toLowerCase()}`}>{emp.status}</span></td>
                  <td>
                    {emp.workflows && emp.workflows.length > 0 ? (
                      <a href={`/workflows/${emp.workflows[0].id}`} style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: '0.8rem' }}>
                        View Workflow →
                      </a>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>—</span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.8rem' }}>{new Date(emp.createdAt).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create Employee Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: 0, marginBottom: '20px' }}>Create New Employee</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '20px', marginTop: 0 }}>
              This will automatically trigger the onboarding workflow with multi-agent execution.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <input className="input" placeholder="Full Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input className="input" placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              <input className="input" placeholder="Role (e.g., Software Engineer)" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} />
              <select className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
                <option value="">Select Department</option>
                <option value="Engineering">Engineering</option>
                <option value="Product">Product</option>
                <option value="Design">Design</option>
                <option value="Marketing">Marketing</option>
                <option value="Human Resources">Human Resources</option>
                <option value="Finance">Finance</option>
                <option value="Operations">Operations</option>
              </select>
              <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                <button className="btn-primary" onClick={handleCreate} disabled={creating} style={{ flex: 1 }}>
                  {creating ? <><div className="spinner" /> Creating...</> : '🚀 Create & Start Onboarding'}
                </button>
                <button className="btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
