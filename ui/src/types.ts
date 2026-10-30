export type Condition = "D0" | "D1" | "D2" | "D3" | "D4";
export type TaskClass = "inbox" | "schedule" | "research";

export interface Metrics {
  total_runs: number;
  leaks_before: number;
  leaks_after: number;
  leak_rate_before: number;
  leak_rate_after: number;
  improvement: number;
  blocked_actions: number;
  avg_policy_bytes: number;
  utility_benign_d0: number;
  utility_benign_d4: number;
  utility_under_attack_d0: number;
  utility_under_attack_d4: number;
  adaptive_asr_d0: number;
  adaptive_asr_d4: number;
  false_block_rate: number;
  potency: number;
  attack_potency_low?: boolean;
}

export interface CurvePoint {
  iter: number;
  train_leak: number;
  heldout_leak: number;
  utility: number;
  policy_bytes?: number;
  train_ci?: [number, number];
  heldout_ci?: [number, number];
}

export interface ConditionStats {
  episodes: number;
  leak_rate: number;
  leak_ci?: [number, number];
  utility: number;
  utility_under_attack: number;
  targeted_asr: number;
  blocked_actions: number;
  ask_count: number;
  false_block_rate: number;
  latency_ms: number;
  tokens: number;
}

export interface PolicyJson {
  version?: number;
  task_class?: string;
  allowed_tools: string[];
  allowed_hosts: string[];
  denied_tools: string[];
  arg_rules?: Record<string, Record<string, Record<string, unknown>>>;
  flow_rules?: FlowRule[];
  on_violation?: string;
}

export interface FlowRule {
  id: string;
  when: string;
  sinks: string[];
  require: Record<string, string | boolean>;
}

export interface Summary {
  run_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  synthetic_fixture: boolean;
  dataset_source: "nemotron_personas_india" | "fallback";
  config: {
    dataset: string;
    n_eval: number;
    n_fit: number;
    agent_label: string;
    model: string;
    attack_types: string[];
    canary_categories: string[];
    compute_label: string;
    region: string;
    enforcement: "gateway" | "openshell";
  };
  metrics: Metrics;
  policy: {
    allowed_tools: string[];
    allowed_hosts: string[];
    denied_tools: string[];
    catalog_tools: number;
    catalog_hosts: number;
    permissions_reduced: number;
    json: PolicyJson;
    openshell_yaml: string;
  };
  curve: CurvePoint[];
  conditions: Record<Condition, ConditionStats>;
  per_model: ModelRow[];
  example_trace_ids: { persona_id: string; episode_id: string; d4_episode_id?: string };
  cost: { tokens: number; usd_estimate: number };
  notes?: string[];
  paired_mcnemar?: { before_only: number; after_only: number; p_value: number };
  source?: string;
}

export interface ModelRow {
  model: string;
  leak_rate_d0: number;
  leak_rate_d4: number;
  utility_d0: number;
  utility_d4: number;
  tokens: number;
  latency_ms: number;
}

export interface AttackTrace {
  vector: "email" | "calendar" | "web";
  goal: string;
  template_id: string;
  split: string;
  adaptive_round: number;
  target_category: string;
  attacker: string;
}

export interface Step {
  t: number;
  role: string;
  content: string;
  tool_call?: { name: string; args: Record<string, unknown>; call_id?: string | null } | null;
  tool_result?: string | null;
  provenance?: { trusted: boolean; source: string };
  gateway?: { decision: string; rule_id: string; reason: string } | null;
  ts?: string;
}

export interface Episode {
  episode_id: string;
  run_id: string;
  persona_id: string;
  split: string;
  condition: Condition;
  model: string;
  task_class: TaskClass;
  task_text: string;
  attack: AttackTrace | null;
  steps: Step[];
  outcome: {
    utility_ok: boolean;
    utility_detail: string;
    leak: { detected: boolean; canary_ids: string[]; via_tool?: string | null; via_host?: string | null; step?: number | null };
    unauthorized_action: { detected: boolean; tool?: string | null; step?: number | null };
    blocked_count: number;
    ask_count: number;
    false_blocks: number;
    benign_calls: number;
  };
  tokens: number;
  latency_ms: number;
  enforcement: string;
  synthetic_fixture: boolean;
  notes: string[];
}

export interface EpisodeRow {
  episode_id: string;
  persona_id: string;
  condition: Condition;
  task_class: TaskClass;
  attack: AttackTrace | null;
  outcome: Episode["outcome"];
  tokens: number;
  latency_ms: number;
  split: string;
}

export interface RunListItem {
  run_id: string;
  status: string;
  synthetic_fixture: boolean;
  dataset_source: string;
  leak_rate_before: number;
  leak_rate_after: number;
  finished_at: string | null;
  mtime: number;
  source: string;
}

export interface PolicyBundle {
  version: number;
  union: PolicyJson;
  by_task_class: Record<string, PolicyJson>;
  changelog: {
    iteration: number;
    task_class: string;
    tool: string;
    action: string;
    detail: string;
    reason: string;
  }[];
  rejected: string[];
  catalog: { tools: number };
}
