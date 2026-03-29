"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SCENARIOS = [
  {
    icon: "👋",
    title: "Employee Onboarding",
    desc: "Full autonomous onboarding: HR account, email, JIRA, buddy assignment, orientation, welcome email.",
    request: "Onboard Priya Sharma as a new Software Engineer in the Engineering department. Her email is priya.sharma@company.com.",
    name: "Priya Sharma",
    email: "priya.sharma@company.com",
    role: "Software Engineer",
    department: "Engineering",
    trigger: "employee_onboarding",
  },
  {
    icon: "💬",
    title: "Meeting Action Items",
    desc: "Extract action items from transcript, create tasks for each, and send a summary email to stakeholders.",
    request: "Process this meeting transcript: Sprint planning discussed UI refresh (Alice), API migration (Bob), deadline Friday. Carol to update staging. David to review security. Send summary to team.",
    trigger: "meeting_action_items",
  },
  {
    icon: "⏱️",
    title: "SLA Breach Response",
    desc: "Detect SLA breach, find delegate, reroute approval, and log audit trail for compliance.",
    request: "SLA breach detected for ticket PROD-4521 in Engineering department. The original assignee is on leave. Reroute and escalate appropriately.",
    trigger: "sla_breach",
  },
];

export default function LandingPage() {
  const [selected, setSelected] = useState<number | null>(null);
  const [customRequest, setCustomRequest] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleRun = async () => {
    setLoading(true);
    try {
      const body = { request: customRequest, trigger: "manual" };

      const res = await fetch(`${API}/api/workflows/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      router.push(`/workflows/${data.workflowId}`);
    } catch (err) {
      console.error("Failed to start workflow:", err);
      setLoading(false);
    }
  };

  return (
    <div className="landing">
      <div className="landing-hero">
        <h1>Enterprise Autopilot</h1>
        <p>
          Multi-agent AI that plans, executes, verifies, and recovers enterprise
          workflows autonomously — with <strong>zero hand-holding</strong>.
        </p>
        <div className="metric-banner">
          <span className="pulse-dot" style={{ background: "#10b981" }} />
          ET AI Hackathon 2026 — PS2: Agentic AI
        </div>
      </div>

      <div className="scenario-grid">
        {SCENARIOS.map((s, i) => (
          <div
            key={i}
            className={`scenario-card${selected === i ? " active" : ""}`}
            onClick={() => {
              if (s.trigger === "employee_onboarding") router.push("/onboarding");
              else if (s.trigger === "meeting_action_items") router.push("/tasks");
              else if (s.trigger === "sla_breach") router.push("/sla");
            }}
            style={{ cursor: "pointer" }}
          >
            <div className="scenario-icon">{s.icon}</div>
            <div className="scenario-title">{s.title}</div>
            <div className="scenario-desc">{s.desc}</div>
          </div>
        ))}
      </div>

      <div className="custom-input-area">
        <textarea
          className="input-field"
          style={{ minHeight: "120px", resize: "vertical", fontSize: "16px", padding: "16px" }}
          placeholder="Or describe a custom workflow here..."
          value={customRequest}
          onChange={(e) => setCustomRequest(e.target.value)}
        />
      </div>

      <button
        className="btn-primary"
        disabled={loading || !customRequest.trim()}
        onClick={handleRun}
        style={{ minWidth: 200 }}
      >
        {loading ? (
          <>
            <div className="spinner" /> Starting...
          </>
        ) : (
          "Run Workflow"
        )}
      </button>

      
    </div>
  );
}
