export type Decision = 'EXECUTE' | 'BLOCK' | 'ASK_CLARIFICATION' | 'REQUIRE_APPROVAL';
export type SignalKey = 'intent_clear' | 'evidence_sufficient' | 'action_supported' | 'safe_to_execute' | 'human_review_required';
export type Scenario = { id: string; title: string; message: string; category: string };
export type Result = {
 id: string; timestamp: string; user_request: string; context: Record<string, unknown>;
 agent_proposal: { tool: string; arguments: Record<string, unknown> } | null;
 proposal_mode?: string; risk: string | null;
 jev: (Record<SignalKey, number> & { next_action: { choice: string; probabilities: Record<string, number> } }) | null;
 jev_raw: unknown; policy_decision: Decision; policy: { rule: string; reason: string };
 user_response?: string | null;
 executed: boolean; tool_execution_result: unknown; duration_ms: number;
 error: {provider: string; kind: string; status: number | null} | null;
 timeline: {name: string; status: 'done' | 'waiting' | 'blocked'}[];
 thresholds: Record<string, number>; models: {agent: string; judge: string};
};
