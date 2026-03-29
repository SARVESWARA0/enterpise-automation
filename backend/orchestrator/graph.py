"""
Strands Graph definition for workflow step orchestration.

Uses strands.multiagent.GraphBuilder with custom FunctionNode(MultiAgentBase) 
wrappers to implement the exec → verify → recovery graph pattern.

Graph shape per step:
  context_handling → execution → verification → [condition] → mark_completed | recovery | force_escalate
  recovery → [condition] → context_handling (retry loop) | mark_escalated | mark_skipped
"""

import json
import asyncio
from strands import Agent
from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
from strands.agent.agent_result import AgentResult
from strands.types.content import ContentBlock, Message


class FunctionNode(MultiAgentBase):
    """
    Wraps an async function as a Strands graph node.
    This bridges the spec's lambda-node approach with the real SDK's 
    requirement for Agent/MultiAgentBase instances.
    """

    def __init__(self, func, name: str = None):
        super().__init__()
        self.func = func
        self.name = name or func.__name__

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Execute the wrapped function and return a MultiAgentResult."""
        task_str = str(task) if not isinstance(task, str) else task

        try:
            result_text = await self.func(task_str, invocation_state)
        except Exception as e:
            result_text = json.dumps({"error": str(e), "status": "FAILURE"})

        agent_result = AgentResult(
            stop_reason="end_turn",
            message=Message(role="assistant", content=[ContentBlock(text=str(result_text))]),
            metrics={},
            state={},
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={self.name: NodeResult(result=agent_result, status=Status.COMPLETED)}
        )


# ── Pre-call validation (Fix 5) ─────────────────────────────────────────────

TOOL_REQUIRED_PARAMS = {
    "create_hr_account_tool": ["name", "email"],
    "create_email_account": ["employee_name", "employee_email", "department"],
    "create_jira_account_tool": ["name", "email"],
    "schedule_meeting_tool": ["name"],
    "send_onboarding_email_tool": ["employee_name", "employee_email"],
    "send_orientation_email_tool": ["recipient_emails", "new_employee_name"],
    "send_email": ["to", "subject", "body"],
    "log_audit_entry": ["workflow_id", "decision", "reason", "action_taken"],
    "escalate_to_it_tool": ["issue", "employee_name"],
    "lookup_tool_reliability": ["tool_name"],
    "get_workflow_context_tool": ["workflow_id"],
}


def _validate_params(tool_name: str, params: dict) -> list:
    """Returns list of missing required parameters. Empty list = valid."""
    required = TOOL_REQUIRED_PARAMS.get(tool_name, [])
    return [k for k in required if not params.get(k)]


# ── Deterministic error classifier (Fix 6) ──────────────────────────────────

def _classify_error(exec_result: dict) -> str:
    """Classify a tool execution result into a deterministic error category."""
    if not exec_result:
        return "UNKNOWN"

    # Check tool envelope success field
    output = exec_result.get("output", "")
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except Exception:
            pass

    # Direct success check on envelope
    if isinstance(output, dict) and output.get("success") is True:
        return "SUCCESS"
    if exec_result.get("status") == "SUCCESS":
        return "SUCCESS"

    error = str(exec_result.get("error", "")).lower()
    output_str = json.dumps(exec_result).lower()

    if "access denied" in error or "forbidden" in error or "401" in output_str or "403" in output_str:
        return "ACCESS_DENIED"
    if "503" in error or "504" in error or "timeout" in error or "temporarily" in error:
        return "TRANSIENT_INFRA"
    if "duplicate" in error or "constraint" in error or "already exists" in error:
        return "DATA_CONFLICT"
    if "missing required" in error or "unexpected keyword" in error or "pre-call validation" in error:
        return "SCHEMA_MISMATCH"
    if exec_result.get("status") == "FAILURE":
        return "TOOL_RETURNED_FALSE"
    return "UNKNOWN"


def build_step_graph(
    context_handling_agent: Agent,
    execution_agent: Agent,
    verification_agent: Agent,
    recovery_agent: Agent,
    emit_fn,
    workflow_id: str,
    step_context: dict,
    db_module,
    prior_outputs: dict = None,
):
    """
    Builds and compiles a Strands Graph for a single workflow step.
    
    Instead of a reusable compiled graph (which the real SDK doesn't support 
    for stateful node functions), we build a fresh graph per step with the 
    step context baked into closures.
    
    Returns: compiled Graph instance ready to invoke.
    """
    # Mutable state shared across all nodes via closure
    state = {
        "workflow_id": workflow_id,
        "step_id": step_context["step_id"],
        "step_name": step_context["step_name"],
        "tool_name": step_context["tool_name"],
        "parameters": step_context["parameters"],
        "step_db_id": step_context["step_db_id"],
        "workflow_context": step_context.get("workflow_context", {}),  # shared state from prior steps
        "retry_count": 0,
        "max_retries": 2,
        "exec_output": None,
        "verify_verdict": None,
        "verify_reason": None,
        "recovery_action": None,
        "recovery_params": None,
        "resolved_parameters": None,
        "final_status": None,
    }

    # ── Node functions ──────────────────────────────────────────────────────

    async def context_handling_fn(task_str, invocation_state=None):
        """Resolves step parameters from workflow context and updates shared state."""
        base_params = state.get("recovery_params") or state["parameters"]
        wf_ctx = state.get("workflow_context", {})

        await emit_fn("agent_active", "context_handler", {
            "active": True,
            "action": f"Resolving context for {state['tool_name']}",
        }, step_id=str(state["step_id"]))

        prompt = (
            f"Resolve parameters for a workflow step.\n"
            f"Step Name: {state['step_name']}\n"
            f"Tool: {state['tool_name']}\n"
            f"Current Parameters: {json.dumps(base_params)}\n"
            f"Workflow Context: {json.dumps(wf_ctx)}\n\n"
            f"Return the required JSON shape only."
        )

        try:
            context_output = await _stream_agent(
                workflow_id, "context_handler", context_handling_agent, prompt,
                emit_fn, step_id=str(state["step_id"])
            )
            parsed = _parse_agent_json(context_output)
        except Exception:
            parsed = {}

        resolved_params = parsed.get("resolved_parameters")
        # IMPORTANT: Always preserve the original parameter keys.
        # The context agent may only return a subset of fields; merge instead of overwriting.
        if isinstance(resolved_params, dict):
            state["resolved_parameters"] = {**dict(base_params), **resolved_params}
        else:
            state["resolved_parameters"] = dict(base_params)

        # Guardrail: never allow workflow_id to be inferred from generic IDs (e.g., employee id).
        # If this step has a workflow_id parameter, it must always be the canonical workflow UUID.
        if "workflow_id" in state["resolved_parameters"]:
            state["resolved_parameters"]["workflow_id"] = workflow_id

        ctx_updates = parsed.get("context_updates")
        if isinstance(ctx_updates, dict) and ctx_updates:
            state["workflow_context"][f"context_step_{state['step_id']}"] = ctx_updates

        await emit_fn("agent_active", "context_handler", {"active": False}, step_id=str(state["step_id"]))
        return json.dumps({
            "resolved_parameters": state.get("resolved_parameters", {}),
            "missing_required": parsed.get("missing_required", []),
        })

    async def execution_fn(task_str, invocation_state=None):
        """Calls the specified MCP tool via the Execution Agent with full workflow context."""
        params = state.get("resolved_parameters") or state.get("recovery_params") or state["parameters"]

        # Final guardrail before tool execution: enforce canonical workflow_id.
        # Prevents context-derived values (like SQL row "id") from corrupting workflow_id.
        if isinstance(params, dict) and "workflow_id" in params:
            params["workflow_id"] = workflow_id

        attempt = state["retry_count"] + 1

        await emit_fn("tool_call", "execution", {
            "tool": state["tool_name"],
            "parameters": params,
            "attempt": attempt,
        }, step_id=str(state["step_id"]))

        # ── Build context-aware prompt ──
        # The agent resolves empty/placeholder params using workflow context
        wf_ctx = state.get("workflow_context", {})
        context_block = ""
        if wf_ctx:
            # Compact summary: step_id → {key: value, ...}
            ctx_summary = {}
            for sid, data in wf_ctx.items():
                if isinstance(data, dict):
                    ctx_summary[str(sid)] = {k: str(v)[:200] for k, v in data.items()}
            context_block = (
                f"\n\nWORKFLOW CONTEXT (outputs from prior completed steps):\n"
                f"{json.dumps(ctx_summary, indent=2)}\n\n"
                f"IMPORTANT: If any parameter value is empty (\"\"), you MUST resolve it "
                f"from the WORKFLOW CONTEXT above. Extract the correct value even if the "
                f"key names differ (e.g., 'time' in context maps to 'meeting_time' parameter). "
                f"For list/array data (like SQL results), compose a comma-separated string. "
                f"After resolving, call the tool with the RESOLVED parameters."
            )

        prompt = (
            f"Execute this step:\n"
            f"Tool: {state['tool_name']}\n"
            f"Parameters: {json.dumps(params)}\n"
            f"{context_block}\n"
            f"Call the tool now with resolved parameters and return the JSON result object only."
        )

        try:
            exec_output = await _stream_agent(
                workflow_id, "execution", execution_agent, prompt,
                emit_fn, step_id=str(state["step_id"])
            )
        except Exception as e:
            exec_output = json.dumps({
                "status": "FAILURE", "tool_called": state["tool_name"],
                "output": None, "error": str(e)[:300]
            })

        exec_result = _parse_agent_json(exec_output)
        if not exec_result:
            exec_result = {
                "status": "FAILURE", "tool_called": state["tool_name"],
                "output": exec_output[:500], "error": "Could not parse execution result"
            }

        # Hard guardrail: the orchestrator, not the agent, is the source of truth for
        # which tool was called. This prevents UI/audit confusion if the execution agent
        # misreports tool_called.
        if isinstance(exec_result, dict):
            exec_result["tool_called"] = state["tool_name"]

        # Check tool-level success/failure
        output_data = exec_result.get("output", "")
        if isinstance(output_data, str):
            try:
                output_data = json.loads(output_data)
            except Exception:
                pass
        if isinstance(output_data, dict):
            # If the tool output self-identifies, ensure it matches the planned tool.
            # This prevents "tool drift" where an agent calls a different tool than instructed.
            # If the tool output self-identifies, ensure it matches the planned tool.
            # This prevents "tool drift" where an agent calls a different tool than instructed.
            out_tool = output_data.get("tool")
            
            if isinstance(out_tool, str) and out_tool and out_tool != state["tool_name"]:
                exec_result["status"] = "FAILURE"
                exec_result["error"] = f"Tool governance violation: planned '{state['tool_name']}', but output claims '{out_tool}'"
                exec_result["output"] = output_data
            # Schema validation for high-risk tools to prevent silent drift.
            if state["tool_name"] == "get_workflow_context_tool" and exec_result.get("status") != "FAILURE":
                if "success" not in output_data or "data" not in output_data:
                    exec_result["status"] = "FAILURE"
                    exec_result["error"] = "Invalid get_workflow_context_tool output shape (expected {success,data,...}). Possible tool drift."
                    exec_result["output"] = output_data
            elif output_data.get("success") is True:
                exec_result["status"] = "SUCCESS"
            elif output_data.get("success") is False:
                exec_result["status"] = "FAILURE"
                exec_result["error"] = output_data.get("error", "Tool returned failure")

        await emit_fn("tool_result", "execution", exec_result, step_id=str(state["step_id"]))

        db_module.log_agent_action(
            workflow_id=workflow_id, step_id=state["step_db_id"],
            agent_name="execution", action=f"called_tool:{state['tool_name']}",
            tool_name=state["tool_name"], input_data=params, output=exec_result
        )

        state["exec_output"] = exec_result
        state["recovery_params"] = None
        return json.dumps(exec_result)

    async def verification_fn(task_str, invocation_state=None):
        """Inspects execution output and returns VERIFIED or FAILED."""
        # ── Deterministic bypass (Fix 6) ──
        error_class = _classify_error(state["exec_output"])
        if error_class == "SUCCESS":
            state["verify_verdict"] = "VERIFIED"
            state["verify_reason"] = "Deterministic: success=true and no error fields"
            await emit_fn("agent_message", "verification", {
                "verdict": "VERIFIED",
                "reason": state["verify_reason"],
                "confidence": 1.0,
                "message": f"✅ {state['tool_name']} verified (deterministic bypass)"
            }, step_id=str(state["step_id"]))
            db_module.log_agent_action(
                workflow_id=workflow_id, step_id=state["step_db_id"],
                agent_name="verification", action="verify:VERIFIED",
                output={"verdict": "VERIFIED", "reason": state["verify_reason"], "bypass": True}
            )
            return json.dumps({"verdict": "VERIFIED", "confidence": 1.0})

        # ── Deterministic failure for known error classes ──
        if error_class in ("ACCESS_DENIED", "DATA_CONFLICT"):
            state["verify_verdict"] = "FAILED"
            state["verify_reason"] = f"Deterministic failure: {error_class}"
            await emit_fn("agent_message", "verification", {
                "verdict": "FAILED",
                "reason": state["verify_reason"],
                "confidence": 1.0,
                "message": f"❌ {state['tool_name']} failed ({error_class})"
            }, step_id=str(state["step_id"]))
            db_module.log_agent_action(
                workflow_id=workflow_id, step_id=state["step_db_id"],
                agent_name="verification", action=f"verify:FAILED:{error_class}",
                output={"verdict": "FAILED", "reason": state["verify_reason"]}
            )
            return json.dumps({"verdict": "FAILED", "confidence": 1.0})

        # ── LLM verification for ambiguous cases only ──
        await emit_fn("agent_message", "verification", {
            "message": f"Verifying output of: {state['tool_name']}..."
        }, step_id=str(state["step_id"]))

        verify_prompt = (
            f"Step: {state['step_name']}\n"
            f"Tool Called: {state['tool_name']}\n"
            f"Execution Output: {json.dumps(state['exec_output'])}\n\n"
            f"Provide your verification verdict JSON."
        )

        try:
            verify_text = await _stream_agent(
                workflow_id, "verification", verification_agent,
                verify_prompt, emit_fn, step_id=str(state["step_id"])
            )
        except Exception:
            verify_text = ""

        verify_result = _parse_agent_json(verify_text)
        if not verify_result or "verdict" not in verify_result:
            if state["exec_output"].get("status") == "SUCCESS":
                verify_result = {"verdict": "VERIFIED", "confidence": 0.8,
                                 "reason": "Inferred from execution status", "suggested_recovery": None}
            else:
                verify_result = {"verdict": "FAILED", "confidence": 0.7,
                                 "reason": "Inferred from execution failure", "suggested_recovery": "RETRY"}

        await emit_fn("agent_message", "verification", {
            "verdict": verify_result.get("verdict"),
            "reason": verify_result.get("reason"),
            "confidence": verify_result.get("confidence")
        }, step_id=str(state["step_id"]))

        db_module.log_agent_action(
            workflow_id=workflow_id, step_id=state["step_db_id"],
            agent_name="verification", action=f"verify:{verify_result['verdict']}",
            output=verify_result
        )

        state["verify_verdict"] = verify_result["verdict"]
        state["verify_reason"] = verify_result.get("reason", "")
        return json.dumps(verify_result)

    async def recovery_fn(task_str, invocation_state=None):
        """Decides recovery action for a failed step."""
        state["retry_count"] += 1

        # ── Max-retry hard override (Fix 9) ──
        if state["retry_count"] > state["max_retries"]:
            state["recovery_action"] = "ESCALATE"
            forced_result = {
                "action": "ESCALATE",
                "reason": f"Max retries ({state['max_retries']}) exhausted for {state['tool_name']}",
                "audit_message": f"{state['tool_name']} failed after {state['max_retries']} retries. Forced ESCALATE."
            }
            await emit_fn("recovery", "recovery", forced_result, step_id=str(state["step_id"]))
            db_module.log_audit(
                workflow_id=workflow_id, step_id=state["step_db_id"],
                decision="ESCALATE", reason=forced_result["reason"],
                action_taken=forced_result["audit_message"],
                agent_name="recovery", tool_name=state["tool_name"],
                retry_count=state["retry_count"], status="RECOVERY"
            )
            return json.dumps(forced_result)

        await emit_fn("recovery", "recovery", {
            "message": f"Failure detected on: {state['step_name']}. "
                       f"Analyzing recovery... (attempt {state['retry_count']}/{state['max_retries']})"
        }, step_id=str(state["step_id"]))

        # ── Build recovery prompt with full context (Fix 8) ──
        prior_context = ""
        wf_ctx = state.get("workflow_context", {})
        if wf_ctx:
            prior_summary = {str(k): {kk: str(vv)[:100] for kk, vv in v.items()} if isinstance(v, dict) else str(v)[:100]
                             for k, v in wf_ctx.items()}
            prior_context = f"\nPrior Step Outputs (available data from completed steps):\n{json.dumps(prior_summary, indent=2)}\n"

        recovery_prompt = (
            f"Failed Step: {state['step_name']}\n"
            f"Tool: {state['tool_name']}\n"
            f"Parameters: {json.dumps(state.get('recovery_params') or state['parameters'])}\n"
            f"Execution Output: {json.dumps(state['exec_output'])}\n"
            f"Error Classification: {_classify_error(state['exec_output'])}\n"
            f"Verification Verdict: {json.dumps({'verdict': state['verify_verdict'], 'reason': state['verify_reason']})}\n"
            f"Retry Count: {state['retry_count']}\n"
            f"Workflow ID: {workflow_id}\n"
            f"Employee Name: {_extract_employee_name(state['parameters'])}\n"
            f"{prior_context}\n"
            f"Decide recovery action. Return JSON only."
        )

        try:
            recovery_text = await _stream_agent(
                workflow_id, "recovery", recovery_agent,
                recovery_prompt, emit_fn, step_id=str(state["step_id"])
            )
        except Exception:
            recovery_text = ""

        recovery_result = _parse_agent_json(recovery_text)
        if not recovery_result or "action" not in recovery_result:
            recovery_result = {
                "action": "RETRY" if state["retry_count"] <= state["max_retries"] else "ESCALATE",
                "reason": "Auto-recovery decision",
                "audit_message": f"Auto-recovery for {state['tool_name']}"
            }

        await emit_fn("recovery", "recovery", {
            "action": recovery_result.get("action"),
            "reason": recovery_result.get("reason"),
            "audit_message": recovery_result.get("audit_message")
        }, step_id=str(state["step_id"]))

        db_module.log_audit(
            workflow_id=workflow_id, step_id=state["step_db_id"],
            decision=recovery_result["action"], reason=recovery_result.get("reason", ""),
            action_taken=recovery_result.get("audit_message", ""),
            agent_name="recovery", tool_name=state["tool_name"],
            retry_count=state["retry_count"], status="RECOVERY"
        )
        db_module.update_step(state["step_db_id"], status="RETRIED",
                              retry_count=state["retry_count"])

        state["recovery_action"] = recovery_result["action"]
        if recovery_result.get("modified_parameters"):
            state["recovery_params"] = recovery_result["modified_parameters"]

        # Handle escalation tool call if specified
        if recovery_result["action"] in ("ESCALATE", "REROUTE"):
            esc_tool = recovery_result.get("escalation_tool")
            esc_params = recovery_result.get("escalation_parameters", {})
            if esc_tool:
                await emit_fn("tool_call", "recovery", {
                    "tool": esc_tool, "parameters": esc_params,
                    "reason": f"Escalation: {recovery_result.get('reason', '')}"
                }, step_id=str(state["step_id"]))
                esc_prompt = (
                    f"Execute this escalation step:\n"
                    f"Tool: {esc_tool}\n"
                    f"Parameters: {json.dumps(esc_params)}\n"
                    f"Call the tool now and return the JSON result."
                )
                try:
                    esc_output = await _stream_agent(
                        workflow_id, "recovery", execution_agent,
                        esc_prompt, emit_fn, step_id=str(state["step_id"])
                    )
                    esc_result = _parse_agent_json(esc_output)
                    if isinstance(esc_result, dict) and esc_tool:
                        esc_result["tool_called"] = esc_tool
                    await emit_fn("tool_result", "recovery",
                                  esc_result or {"output": esc_output[:300]},
                                  step_id=str(state["step_id"]))
                except Exception:
                    pass

        return json.dumps(recovery_result)

    async def mark_completed_fn(task_str, invocation_state=None):
        db_module.update_step(state["step_db_id"], status="COMPLETED",
                              output=state.get("exec_output"))
        db_module.log_audit(
            workflow_id=workflow_id, step_id=state["step_db_id"],
            decision="COMPLETED", reason=state.get("verify_reason", ""),
            action_taken=f"{state['tool_name']} completed successfully",
            agent_name="verification", tool_name=state["tool_name"], status="COMPLETED"
        )
        state["final_status"] = "COMPLETED"
        await emit_fn("step_complete", "verification", {
            "step_id": state["step_id"],
            "name": state["step_name"],
            "output": state.get("exec_output", {}).get("output")
        }, step_id=str(state["step_id"]))
        return "COMPLETED"

    async def mark_escalated_fn(task_str, invocation_state=None):
        db_module.update_step(state["step_db_id"], status="ESCALATED")
        db_module.log_audit(
            workflow_id=workflow_id, step_id=state["step_db_id"],
            decision="ESCALATED",
            reason=f"Retries exhausted or unrecoverable error on {state['tool_name']}",
            action_taken="Escalated to human/IT support",
            agent_name="recovery", tool_name=state["tool_name"], status="ESCALATED"
        )
        state["final_status"] = "ESCALATED"
        await emit_fn("step_failed", "recovery", {
            "step_id": state["step_id"],
            "status": "ESCALATED",
            "reason": state.get("verify_reason", "Max retries exceeded")
        }, step_id=str(state["step_id"]))
        return "ESCALATED"

    async def mark_skipped_fn(task_str, invocation_state=None):
        db_module.update_step(state["step_db_id"], status="SKIPPED")
        state["final_status"] = "SKIPPED"
        await emit_fn("step_complete", "recovery", {
            "step_id": state["step_id"],
            "name": state["step_name"],
            "status": "SKIPPED"
        }, step_id=str(state["step_id"]))
        return "SKIPPED"

    # ── Routing conditions ──────────────────────────────────────────────────

    def route_verified(graph_state):
        """After verification: go to mark_completed if VERIFIED."""
        return state.get("verify_verdict") == "VERIFIED"

    def route_needs_recovery(graph_state):
        """After verification: go to recovery if FAILED and retries remain."""
        return (state.get("verify_verdict") != "VERIFIED"
                and state["retry_count"] < state["max_retries"])

    def route_force_escalate(graph_state):
        """After verification: force escalate if retries exhausted."""
        return (state.get("verify_verdict") != "VERIFIED"
                and state["retry_count"] >= state["max_retries"])

    def route_retry(graph_state):
        """After recovery: loop back to execution if RETRY."""
        return state.get("recovery_action") == "RETRY"

    def route_escalate(graph_state):
        """After recovery: escalate."""
        return state.get("recovery_action") in ("ESCALATE", "REROUTE")

    def route_skip(graph_state):
        """After recovery: skip."""
        return state.get("recovery_action") == "SKIP"

    # ── Build the graph ──────────────────────────────────────────────────────

    context_node = FunctionNode(context_handling_fn, "context_handling")
    exec_node = FunctionNode(execution_fn, "execution")
    verify_node = FunctionNode(verification_fn, "verification")
    recovery_node = FunctionNode(recovery_fn, "recovery")
    completed_node = FunctionNode(mark_completed_fn, "mark_completed")
    escalated_node = FunctionNode(mark_escalated_fn, "mark_escalated")
    skipped_node = FunctionNode(mark_skipped_fn, "mark_skipped")

    builder = GraphBuilder()

    builder.add_node(context_node, "context_handling")
    builder.add_node(exec_node, "execution")
    builder.add_node(verify_node, "verification")
    builder.add_node(recovery_node, "recovery")
    builder.add_node(completed_node, "mark_completed")
    builder.add_node(escalated_node, "mark_escalated")
    builder.add_node(skipped_node, "mark_skipped")

    builder.set_entry_point("context_handling")

    # context_handling → execution (always)
    builder.add_edge("context_handling", "execution")
    # execution → verification (always)
    builder.add_edge("execution", "verification")

    # verification → mark_completed (if VERIFIED)
    builder.add_edge("verification", "mark_completed", condition=route_verified)
    # verification → recovery (if FAILED, retries remain)
    builder.add_edge("verification", "recovery", condition=route_needs_recovery)
    # verification → mark_escalated (if FAILED, retries exhausted)
    builder.add_edge("verification", "mark_escalated", condition=route_force_escalate)

    # recovery → context_handling (retry loop)
    builder.add_edge("recovery", "context_handling", condition=route_retry)
    # recovery → mark_escalated (if ESCALATE/REROUTE)
    builder.add_edge("recovery", "mark_escalated", condition=route_escalate)
    # recovery → mark_skipped (if SKIP)
    builder.add_edge("recovery", "mark_skipped", condition=route_skip)

    # Safety limits
    builder.set_max_node_executions(15)
    builder.set_execution_timeout(300)

    return builder.build(), state


# ── Streaming helper ──────────────────────────────────────────────────────────

async def _stream_agent(workflow_id, agent_name, agent, prompt, emit_fn, step_id=None):
    """
    Call an agent using stream_async() and forward events to SSE.
    Returns the full accumulated text response.
    """
    full_text = ""
    current_tool_name = None

    try:
        async with asyncio.timeout(60):
            async for event in agent.stream_async(prompt):
                if "data" in event and event["data"]:
                    chunk = event["data"]
                    full_text += chunk
                    await emit_fn("token_stream", agent_name, {
                        "chunk": chunk,
                        "tool_context": current_tool_name,
                    }, step_id=step_id)

                if "current_tool_use" in event and event["current_tool_use"]:
                    tool_info = event["current_tool_use"]
                    tool_name = tool_info.get("name", "")
                    if tool_name and tool_name != current_tool_name:
                        current_tool_name = tool_name
                        await emit_fn("agent_tool_start", agent_name, {
                            "tool": tool_name,
                            "input": tool_info.get("input", {}),
                        }, step_id=step_id)

                if "reasoningText" in event and event["reasoningText"]:
                    await emit_fn("token_stream", agent_name, {
                        "chunk": event["reasoningText"],
                        "is_reasoning": True,
                    }, step_id=step_id)

                if "result" in event:
                    result = event["result"]
                    result_text = str(result)
                    if result_text and not full_text:
                        full_text = result_text

        return full_text
        
    except asyncio.TimeoutError:
        return json.dumps({"status": "FAILURE", "error": f"Agent {agent_name} API call timed out after 60s."})

    except Exception as e:
        # Fall back to synchronous call
        try:
            result = await asyncio.to_thread(agent, prompt)
            return str(result)
        except Exception as e2:
            return json.dumps({"status": "FAILURE", "error": str(e2)[:300]})


def _parse_agent_json(raw_text: str) -> dict:
    """Best-effort parse JSON from an agent's text response using balanced-brace matching."""
    text = raw_text.strip()
    # Strip markdown fences
    if "```" in text:
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    # Try full text first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Balanced brace extraction — find first { and match its closing }
    start = text.find("{")
    if start == -1:
        return {}
    depth, end = 0, -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return {}
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return {}


def _extract_employee_name(params: dict) -> str:
    """Extract employee name from step parameters."""
    return params.get("name", params.get("employee_name", "unknown"))
