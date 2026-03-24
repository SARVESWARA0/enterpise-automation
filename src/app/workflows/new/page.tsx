'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const PRESET_WORKFLOWS = [
  { type: 'meeting_action_items', label: 'Meeting to Action Items', icon: '📋', description: 'Parse a meeting transcript and create tasks' },
  { type: 'sla_breach_prevention', label: 'SLA Breach Prevention', icon: '⚡', description: 'Handle overdue approvals and reroute to delegates' },
  { type: 'contract_lifecycle', label: 'Contract Lifecycle', icon: '📄', description: 'Process a contract through review, approval, and signing' },
  { type: 'vendor_onboarding', label: 'Vendor Onboarding', icon: '🏢', description: 'Onboard a new vendor with verification and setup' },
  { type: 'expense_approval', label: 'Expense Approval', icon: '💰', description: 'Route expense report through approval chain' },
  { type: 'leave_request', label: 'Leave Request', icon: '🏖️', description: 'Process employee leave request with approvals' },
];

export default function NewWorkflowPage() {
  const [selectedType, setSelectedType] = useState('');
  const [customType, setCustomType] = useState('');
  const [inputText, setInputText] = useState('');
  const [creating, setCreating] = useState(false);
  const router = useRouter();

  const handleCreate = async () => {
    const type = selectedType || customType.toLowerCase().replace(/\s+/g, '_');
    if (!type) return;
    setCreating(true);

    try {
      const inputData: Record<string, unknown> = {};
      
      // Parse input depending on type
      if (type === 'meeting_action_items') {
        inputData.transcript = inputText || 'Alice will complete the API integration by Friday. Bob should review the design docs. Someone needs to update the deployment pipeline. The budget report needs approval from management.';
        inputData.participants = 'team@company.com';
      } else if (type === 'sla_breach_prevention') {
        inputData.workflowId = 'sla-check-001';
        inputData.deadline = new Date(Date.now() - 7200000).toISOString(); // 2 hours overdue
        inputData.department = 'Engineering';
        inputData.taskType = inputText || 'approval request';
      } else {
        inputData.description = inputText || `${type} workflow`;
        inputData.triggerEvent = 'manual_trigger';
      }

      const res = await fetch('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, inputData }),
      });

      const data = await res.json();
      if (res.ok && data.workflowId) {
        router.push(`/workflows/${data.workflowId}`);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Create Custom Workflow</h1>
        <p className="page-subtitle">Select a preset or describe any workflow — the system will dynamically plan and execute it</p>
      </div>

      {/* Preset Workflows */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '12px', marginBottom: '24px' }}>
        {PRESET_WORKFLOWS.map((preset) => (
          <div key={preset.type} className="glass-card" style={{
            padding: '16px', cursor: 'pointer',
            borderColor: selectedType === preset.type ? 'var(--accent)' : undefined,
            background: selectedType === preset.type ? 'rgba(99, 102, 241, 0.1)' : undefined,
          }} onClick={() => { setSelectedType(preset.type); setCustomType(''); }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>{preset.icon}</div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '4px' }}>{preset.label}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{preset.description}</div>
          </div>
        ))}
      </div>

      {/* Custom Type */}
      <div className="glass-card" style={{ padding: '20px', marginBottom: '16px' }}>
        <h3 style={{ fontSize: '0.85rem', fontWeight: 600, margin: '0 0 12px 0' }}>Or describe a custom workflow</h3>
        <input className="input" placeholder="e.g., procurement_approval, it_incident_response, ..." value={customType}
          onChange={(e) => { setCustomType(e.target.value); setSelectedType(''); }} style={{ marginBottom: '12px' }} />
        
        <h3 style={{ fontSize: '0.85rem', fontWeight: 600, margin: '0 0 12px 0' }}>Context / Input Data</h3>
        <textarea className="input" placeholder="Add context, e.g., a meeting transcript, task description, or details..."
          value={inputText} onChange={(e) => setInputText(e.target.value)}
          style={{ minHeight: '120px', resize: 'vertical', fontFamily: 'inherit' }} />
      </div>

      <button className="btn-primary" onClick={handleCreate} disabled={creating || (!selectedType && !customType)} style={{ fontSize: '1rem', padding: '14px 32px' }}>
        {creating ? <><div className="spinner" /> Creating & Executing...</> : '🚀 Launch Workflow'}
      </button>
    </div>
  );
}
