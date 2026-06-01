export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export type SeverityCounts = Partial<Record<Severity, number>>;

export type CategoryCounts = Record<string, number>;

export type ScannerStatus = {
  scanner: string;
  available: boolean;
  command?: string[];
  status?: string;
  error?: string | null;
  findings?: number;
};

export type ScannerCatalogItem = {
  scanner: string;
  label: string;
  area: string;
  covers: string;
  profile: string;
  install: string;
  next_step: string;
  built_in?: boolean;
  tool_id?: string;
  category?: string;
  profile_ids?: string[];
  recommended_pack_ids?: ToolPackId[];
  install_state?: ToolInstallState;
};

export type ToolKind = 'scanner' | 'plugin' | 'app' | 'mcp-connector' | 'workflow';
export type ToolCategory =
  | 'code-security'
  | 'secrets'
  | 'dependencies'
  | 'supply-chain'
  | 'infrastructure'
  | 'ai-agent'
  | 'platform-posture'
  | 'external-surface'
  | 'defense-intel';
export type ToolLifecycle = 'available' | 'beta' | 'advanced' | 'coming-soon' | 'deprecated' | 'hidden';
export type ToolInstallState = 'built-in' | 'managed' | 'detected' | 'missing' | 'unavailable' | 'not-configured' | 'coming-soon';
export type ToolInstallMethod = 'built-in' | 'homebrew' | 'uv-tool' | 'manual' | 'docker-optional' | 'managed-future' | 'none';
export type ToolInstallOwner = 'devsec' | 'external' | 'user' | 'not-applicable';
export type ToolInstallDetection = 'built-in' | 'path-binary' | 'config-preflight' | 'cache-preflight' | 'registry-future' | 'none';
export type ToolUninstallPosture = 'not-needed' | 'devsec-managed' | 'user-owned' | 'manual-only' | 'not-supported';
export type ToolNetworkAccess = 'none' | 'optional' | 'required';
export type ToolExternalTargets = 'none' | 'repo-derived' | 'user-provided';
export type ToolCredentialUse = 'none' | 'optional' | 'required';
export type ToolEvidenceType =
  | 'source-pattern'
  | 'secret-match'
  | 'dependency-advisory'
  | 'sbom'
  | 'iac-policy'
  | 'workflow-policy'
  | 'install-hook'
  | 'ai-config'
  | 'platform-posture'
  | 'behavior-diff'
  | 'ioc-match'
  | 'external-observation';
export type ToolPackId = 'starter' | 'secrets' | 'dependencies' | 'ai-agent' | 'iac' | 'platform-posture' | 'advanced-dependency' | 'external-surface';
export type ToolPackRole = 'included' | 'optional' | 'coming-soon';

export type SetupKind = 'none' | 'env-var' | 'api-key' | 'oauth' | 'file-path' | 'config-block';
export type SetupProbeKind = 'shell' | 'http' | 'binary-version' | 'directory-exists';

export type SetupProbe = {
  kind: SetupProbeKind;
  spec: Record<string, string>;
};

export type ToolInstallContract = {
  method: ToolInstallMethod;
  owner: ToolInstallOwner;
  detection: ToolInstallDetection;
  binary?: string;
  alternate_binaries?: string[];
  managed_package?: string;
  instructions?: string;
  next_step?: string;
  uninstall_posture: ToolUninstallPosture;
};

export type ToolPolicy = {
  local_only: boolean;
  writes_files: boolean;
  network_access: ToolNetworkAccess;
  external_targets: ToolExternalTargets;
  uses_credentials: ToolCredentialUse;
  destructive_action: boolean;
  needs_approval: boolean;
  allowed_for_agent_lab: boolean;
  stores_results_locally: boolean;
  sends_source_off_machine: boolean;
  requires_human_setup: boolean;
  default_enabled: boolean;
};

export type ToolCapabilities = {
  finding_categories: string[];
  evidence_types: ToolEvidenceType[];
  scan_profiles: string[];
  requires_previous_scan: boolean;
  requires_artifacts: boolean;
  requires_repo_remote: boolean;
};

export type ToolPackMembership = {
  pack_id: ToolPackId;
  role: ToolPackRole;
  default_enabled: boolean;
};

export type ToolDerivedLabels = {
  safety: string[];
  install: string[];
  agent_lab: string;
};

export type ToolInstallPreview = {
  tool_id?: string;
  pack_id?: string;
  install_state?: ToolInstallState | string;
  action: string;
  preview_available: boolean;
  execution_available: boolean;
  execution_reason?: string;
  managed?: boolean;
  approved_managed_proof?: boolean;
  target_version?: string;
  target_version_label?: string;
  proof_level?: string;
  proof_level_label?: string;
  expected_proof_level?: string;
  expected_proof_level_label?: string;
  proof_caveat?: string;
  install_method?: string;
  install_root?: string;
  binary_path?: string;
  shim_path?: string;
  owned_paths?: string[];
  network_access?: boolean;
  version_check?: {
    status?: string;
    command?: string[];
    output?: string;
    timeout_seconds?: number;
  };
  uninstall_boundary?: string;
  detected_user_binary?: string | null;
  ownership?: ManagedToolOwnership;
  pack_install_supported?: boolean;
  status_counts?: Record<string, number>;
  notes?: string[];
  tool_previews?: ToolInstallPreview[];
  leaves_detected_tools_alone?: boolean;
};

export type ManagedToolOwnership = {
  tool_id: string;
  ownership_id: string | null;
  verified: boolean;
  status: string;
  install_root: string | null;
  binary_path: string | null;
  version: string | null;
  source: string | null;
  installed_at: string | null;
  evidence: string[];
  problems: string[];
  proof_level?: string | null;
  proof_level_label?: string | null;
};

export type ToolCatalogItem = {
  id: string;
  kind: ToolKind;
  label: string;
  summary: string;
  description?: string;
  category: ToolCategory;
  scanner_key?: string;
  legacy_scanner?: ScannerCatalogItem;
  lifecycle: ToolLifecycle;
  install_state: ToolInstallState;
  install: ToolInstallContract;
  policy: ToolPolicy;
  capabilities: ToolCapabilities;
  derived_labels: ToolDerivedLabels;
  packs: ToolPackMembership[];
  profiles: string[];
  managed_ownership?: ManagedToolOwnership;
  install_preview?: ToolInstallPreview;
  docs_path?: string;
  homepage_url?: string;
  setup_kind: SetupKind;
  setup_requirement?: string;
  setup_probe?: SetupProbe;
  setup_token_create_url?: string;
  branding: ToolBranding;
};

export type ToolBranding = {
  // Hex string sampled from the tool's wordmark. Rendered as a 4px left-edge
  // stripe on cards and a 1px underline beneath the tool name on the detail
  // page. Tools without a vetted upstream mark inherit DëvSec's accent.
  accent_color: string;
  // Filename under ``/tool-logos/`` (served from ``dashboard-ui/public``).
  // ``null`` falls back to the category icon.
  logo?: string | null;
};

export type ToolCatalogPayload = {
  items: ToolCatalogItem[];
};

export type SecurityPackTool = {
  id: string;
  label: string;
  summary: string;
  role: ToolPackRole;
  default_enabled: boolean;
  install_state: ToolInstallState;
  lifecycle: ToolLifecycle;
  derived_labels?: ToolDerivedLabels;
  install_preview?: ToolInstallPreview;
};

export type SecurityPackCatalogItem = {
  id: ToolPackId;
  label: string;
  summary: string;
  mvp_state: 'real' | 'coming-soon' | string;
  visibility: string;
  primary_profile: string | null;
  secondary_profiles: string[];
  status_counts: Record<string, number>;
  ready_count: number;
  missing_count: number;
  display_only_count: number;
  tools: SecurityPackTool[];
  install_preview: ToolInstallPreview;
};

export type ScanProfilePackReference = {
  id: ToolPackId;
  label: string;
  mvp_state: string;
  visibility: string;
  ready_count: number;
  missing_count: number;
  display_only_count: number;
  status_counts: Record<string, number>;
};

export type ScanProfileCatalogItem = {
  id: string;
  label: string;
  command: string;
  summary: string;
  scanner_keys: string[];
  primary_pack_ids: ToolPackId[];
  supporting_pack_ids: ToolPackId[];
  recommended_pack_ids: ToolPackId[];
  recommended_packs: ScanProfilePackReference[];
  notes: string[];
};

export type AgentLabAdapterId = 'codex' | 'claude-code' | 'local-agent' | 'manual-json';

export type AgentLabContextPayload = {
  schema_version: 'agent-lab.context.v1' | string;
  context_id?: string;
  context_hash?: string;
  created_at?: string;
  repo?: {
    name?: string;
    path?: string | null;
  };
  tool_catalog?: ToolCatalogItem[];
  security_packs?: SecurityPackCatalogItem[];
  scan_profiles?: ScanProfileCatalogItem[];
  scan_history_summary?: Record<string, unknown>;
  allowed_scan_profile_ids?: string[];
  allowed_tool_ids?: string[];
  blocked_tool_ids?: string[];
  blocked_actions?: string[];
  non_runnable_pack_rules?: Record<string, unknown>;
  policy_boundaries?: Record<string, unknown>;
};

export type AgentLabRecommendedTool = {
  tool_id: string;
  label?: string;
  reason?: string;
  expected_benefit?: string;
  policy?: ToolPolicy;
  safety_labels?: string[];
  agent_safety_labels?: string[];
  install_state?: ToolInstallState | string;
  lifecycle?: ToolLifecycle | string;
};

export type AgentLabRecommendedPack = {
  pack_id: ToolPackId | string;
  label?: string;
  reason?: string;
  runnable?: boolean;
  mvp_state?: string;
};

export type AgentLabRequestedExecution = {
  action: string;
  scan_profile_id?: string;
  profile_label?: string;
  tool_ids?: string[];
  mode?: string;
  requires_approval?: boolean;
  reason?: string;
  status?: string;
  scan_id?: string;
  report_path?: string;
};

export type AgentLabEvidenceGap = {
  tool_id?: string | null;
  tool_label?: string;
  scanner?: string;
  scan_profile_id?: string;
  reason?: string;
  gap_type?: string;
  install_state?: string;
  user_message?: string;
  source?: string;
};

export type AgentLabBlockedRequest = {
  reason?: string;
  detail?: string;
  tool_id?: string | null;
  scan_profile_id?: string | null;
  source?: string;
};

export type AgentLabExecutionPreviewItem = {
  index?: number;
  action?: string;
  scan_profile_id?: string;
  profile_label?: string;
  mode?: string;
  reason?: string;
  status?: string;
  scanner_names?: string[];
  tools?: {
    tool_id?: string;
    tool_label?: string;
    scanner?: string | null;
    scan_profile_id?: string;
    install_state?: string;
    lifecycle?: string;
    safety_labels?: string[];
    status?: string;
  }[];
  evidence_gaps?: AgentLabEvidenceGap[];
  blocked?: AgentLabBlockedRequest[];
};

export type AgentLabExecutionPreview = {
  version?: string;
  proposal_id?: string;
  approval_state?: string;
  requested_mode?: string;
  execution_surface?: string;
  dry_run?: boolean;
  can_execute?: boolean;
  requires_approval?: boolean;
  scan_profile_ids?: string[];
  scanner_names?: string[];
  items?: AgentLabExecutionPreviewItem[];
  evidence_gaps?: AgentLabEvidenceGap[];
  blocked_items?: AgentLabBlockedRequest[];
  policy_gates?: Record<string, unknown>;
};

export type AgentLabProposal = {
  id: string;
  external_proposal_id?: string;
  repo_name?: string;
  repo_path?: string | null;
  context_id?: string;
  context_hash?: string | null;
  source?: {
    adapter_id?: AgentLabAdapterId | string;
    agent_label?: string;
    created_at?: string | null;
  };
  summary?: string;
  recommended_tools?: AgentLabRecommendedTool[];
  recommended_packs?: AgentLabRecommendedPack[];
  requested_permissions?: string[];
  requested_execution?: AgentLabRequestedExecution[];
  expected_evidence_gaps?: AgentLabEvidenceGap[];
  blocked_requests?: AgentLabBlockedRequest[];
  notes?: string | null;
  validation_status?: string;
  validation_errors?: string[];
  approval_state?: 'pending' | 'approved' | 'denied' | string;
  approval_note?: string | null;
  decided_by?: string | null;
  imported_at?: string;
  updated_at?: string;
  approved_at?: string | null;
  denied_at?: string | null;
  raw_proposal?: Record<string, unknown>;
  final_execution_plan?: {
    version?: string;
    approval_required?: boolean;
    approval_state?: string;
    items?: AgentLabRequestedExecution[];
    last_preview?: AgentLabExecutionPreview;
    last_execution?: {
      job_id?: string;
      mode?: string;
      status?: string;
      started_at?: string;
      finished_at?: string;
      scanner_names?: string[];
      scan_id?: string;
      report_path?: string;
      error?: string;
      evidence_gaps?: AgentLabEvidenceGap[];
    };
  };
};

export type ScannerDoctorStatus = 'ran' | 'missing' | 'error' | 'not-run';

export type ScannerRecommendedPack = {
  id: ToolPackId;
  label: string;
  mvp_state: string;
  visibility: string;
  ready_count: number;
  missing_count: number;
  display_only_count: number;
  status_counts: Record<string, number>;
};

export type ScannerDoctorItem = ScannerCatalogItem & {
  status: ScannerDoctorStatus;
  findings: number;
  repoNames: string[];
  command?: string[];
  error?: string | null;
  action: string;
  tool?: ToolCatalogItem;
  recommendedPacks: ScannerRecommendedPack[];
  last_run: string | null;
};

export type ScannerDoctorGroup = {
  area: string;
  items: ScannerDoctorItem[];
};

export type RepositorySummary = {
  scan_id: string | null;
  repo: string;
  path: string;
  health: number;
  last_scan: string | null;
  status: string;
  profile: string;
  report_path: string | null;
  counts: SeverityCounts;
  categories: CategoryCounts;
  raw_counts?: SeverityCounts;
  raw_categories?: CategoryCounts;
  scanners: ScannerStatus[];
  cases?: SecurityCase[];
  active_cases?: SecurityCase[];
  suppressed_cases?: SecurityCase[];
  case_counts?: {
    action_level?: Record<string, number>;
    severity?: Record<string, number>;
    category?: Record<string, number>;
  };
  suppressed_counts?: SuppressedCounts;
  suppression_reasons?: SuppressionReason[];
  previous_scan_id?: string | null;
  previous_health?: number | null;
  health_delta?: number | null;
  case_delta?: CaseDelta;
  dependency_delta?: DependencyDelta;
  dependency_trust?: DependencyTrustRecord[];
  platform_posture?: PlatformPostureSnapshot | null;
  rotation_state?: RotationStateSignal | null;
  case_resolution_runs?: CaseResolutionRun[];
};

// Rotation status vocabulary — mirrors security_observatory/rotation.py.
// Words, not symbols, per the voice doctrine. The lone ⚠ carve-out is
// only for IN_GRACE entries inside 4h of revoke (see RotationStatusCard).
export type RotationStatus =
  | 'NEVER'
  | 'HEALTH_CHECK'
  | 'PREFLIGHT'
  | 'ACQUIRED'
  | 'WAITING_FOR_PASTE'
  | 'STAGED_CANARY'
  | 'DEPLOYED_CANARY'
  | 'IN_CANARY_VERIFY'
  | 'VERIFIED_CANARY'
  | 'STAGED_PROD'
  | 'DEPLOYED_PROD'
  | 'VERIFIED'
  | 'IN_SOAK'
  | 'SOAKED'
  | 'IN_GRACE'
  | 'ROTATED'
  | 'HALTED'
  | 'HEALTH_CHECK_FAILED'
  | 'CANARY_VERIFY_FAILED'
  | 'SOAK_FAILED'
  | 'ROLLED_BACK'
  | 'MANUAL'
  | 'unknown';

export type RotationStack = 'vercel' | 'python-cli';

export type RotationStateSignal = {
  scaffolded: boolean;
  stack: RotationStack | string | null;
  stack_supported: boolean;
  secret_count: number;
  needs_attention_count: number;
  in_grace_count: number;
  last_event_at: string | null;
};

export type RotationSecretRow = {
  secret: string;
  class: string | null;
  rotation_warning: string | null;
  soak_window_minutes: number | null;
  console_url: string | null;
  status: RotationStatus | string;
  last_rotated_at: string | null;
  days_since_rotation: number | null;
  cadence_days: number | null;
  next_rotation_due: string | null;
  rotation_id: string | null;
  in_grace_until: string | null;
  needs_attention: boolean;
  manually_marked: boolean;
  override_kind: string | null;
  emergency_mode: boolean;
  active_job_id: string | null;
};

export type RotationReceiptMeta = {
  filename: string;
  modified_at: string;
};

export type RotationConsistencyWarning = {
  kind: string;
  secret?: string | null;
  rotation_id?: string | null;
  state_status?: string | null;
  history_status?: string[] | string | null;
  history_step?: string | null;
  detail: string;
};

export type RotationConsistency = {
  ok: boolean;
  warnings: RotationConsistencyWarning[];
};

export type RotationStatusPayload = {
  repo: string;
  rotation_state: RotationStateSignal;
  secrets: RotationSecretRow[];
  receipts: RotationReceiptMeta[];
  consistency: RotationConsistency;
};

export type RotationEvent = {
  timestamp: string | null;
  secret: string;
  rotation_id: string | null;
  step: string | null;
  outcome: string | null;
  note: string | null;
  duration_ms: number | null;
  override_kind: string | null;
};

export type RotationHistoryPayload = {
  repo: string;
  events: RotationEvent[];
};

export type RotationScaffoldHandoff =
  | {
      supported: true;
      stack: RotationStack | string | null;
      working_directory: string;
      command: string;
      next_steps: string[];
      why_not_shelled_out: string;
    }
  | {
      supported: false;
      stack: RotationStack | string | null;
      message: string;
    };

// Coarse phase vocabulary the dashboard surfaces while a rotation is running.
// Mirrors dashboard_server._classify_stdout_line in Python. Words, not symbols.
export type RotationJobPhase =
  | 'queued'
  | 'initiated'
  | 'health_check'
  | 'preflight'
  | 'acquire'
  | 'waiting_for_paste'
  | 'stage_canary'
  | 'verify_canary'
  | 'stage_prod'
  | 'verify_prod'
  | 'soak'
  | 'grace'
  | 'revoke'
  | 'verified'
  | 'halted'
  | 'unknown';

export type RotationJobStatus =
  | 'queued'
  | 'running'
  | 'complete'
  | 'halted'
  | 'failed';

export type RotationJob = {
  id: string;
  kind: 'rotation';
  status: RotationJobStatus;
  repo: string;
  repo_path: string;
  secret: string;
  command: string;
  options: {
    no_soak: boolean;
    skip_health_check: boolean;
    soak_minutes: number | null;
    test_mode: boolean;
    acknowledged_skipping_soak: boolean;
    acknowledged_skipping_health_check: boolean;
    emergency_mode: boolean;
    acknowledged_cached_caller_risk: boolean;
  };
  phase: RotationJobPhase | string;
  message: string;
  stdout_tail: string[];
  events_seen: number;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  error: string | null;
  receipt_filename: string | null;
  receipt_url: string | null;
  verification_status: string | null;
  paste_in_progress?: boolean;
  paste_submitted_at?: string | null;
};

export type RotationTriggerOptions = {
  no_soak?: boolean;
  acknowledged_skipping_soak?: boolean;
  skip_health_check?: boolean;
  acknowledged_skipping_health_check?: boolean;
  soak_minutes?: number;
  test_mode?: boolean;
  emergency_mode?: boolean;
  acknowledged_cached_caller_risk?: boolean;
};

export type RotationTriggerRequest = {
  secret: string;
  confirmed: true;
  confirmation_phrase: string;
  options?: RotationTriggerOptions;
};

/**
 * Tier 5R confirmation phrase from docs/agent-safety.md. The dashboard modal
 * and the slash command both substitute the secret name into this string; the
 * server refuses any other shape. Single source of truth for the wire format.
 */
export function rotationConfirmationPhrase(secret: string, options: { emergencyMode?: boolean } = {}): string {
  if (options.emergencyMode) {
    return `Yes, rotate \`${secret}\` emergency-mode and accept that the old key dies immediately with no grace.`;
  }
  return `Yes, rotate \`${secret}\` and accept the irreversible provider-side change.`;
}

export type BatchFilterPreset = 'all_actionable' | 'never_rotated' | 'needs_attention';

export type BatchJobStatus =
  | 'running'
  | 'complete'
  | 'complete_with_errors'
  | 'stopped'
  | 'halted_awaiting_decision';

export type BatchJobSnapshot = {
  id: string;
  kind: 'rotation_batch';
  status: BatchJobStatus | string;
  repo: string;
  repo_path: string;
  filter: BatchFilterPreset | string;
  queue: string[];
  completed: string[];
  halted: string[];
  current_secret: string | null;
  current_job_id: string | null;
  position: number;
  total: number;
  halt_on_error: boolean;
  halted_awaiting_decision: boolean;
  started_at: string | null;
  finished_at: string | null;
  batch_receipt: string | null;
};

export type BatchTriggerRequest = {
  filter: BatchFilterPreset;
  confirmed: boolean;
  confirmation_phrase: string;
};

export function batchRotationConfirmationPhrase(
  count: number,
  options: { hasClassB?: boolean } = {},
): string {
  const suffix = options.hasClassB
    ? ' This includes provider-side changes for Class B secrets.'
    : '';
  return `Yes, rotate ${count} secrets and accept the irreversible provider-side changes.${suffix}`;
}

export type HoneyKeyStatus = 'active' | 'triggered' | 'archived';

export type HoneyKey = {
  id: string;
  project_id: string;
  repo_id: string | null;
  name: string;
  token_prefix: string;
  status: HoneyKeyStatus;
  placement_path: string | null;
  note: string | null;
  created_at: string;
  created_by: string | null;
  last_triggered_at: string | null;
  trigger_count: number;
  archived_at: string | null;
};

export type HoneyKeyEvent = {
  id: string;
  honey_key_id: string;
  project_id: string;
  repo_id: string | null;
  triggered_at: string;
  ip_address: string | null;
  user_agent: string | null;
  method: string;
  path: string;
  headers?: Record<string, string>;
  body_summary: string | null;
  confidence: number;
  source_type: 'api_call' | 'url_open' | 'unknown';
  reason: string;
  approximate_geo?: string | null;
  created_at: string;
  incident?: HoneyIncident | null;
};

export type HoneyIncident = {
  event_id: string;
  investigating: boolean;
  secrets_rotated: boolean;
  logs_reviewed: boolean;
  archived_reset: boolean;
  accepted_risk_note: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SecurityProjectStatus = {
  project_id: string;
  status: 'green' | 'yellow' | 'red';
  reason: string;
  last_event_at: string | null;
};

export type Finding = {
  id: number;
  scan_id: string;
  repo_name: string;
  scanner: string;
  severity: Severity;
  category: string;
  title: string;
  file: string | null;
  line: number | null;
  remediation: string | null;
  vulnerability_id?: string | null;
  package_name?: string | null;
  package_version?: string | null;
  package_ecosystem?: string | null;
  package_url?: string | null;
  component_fingerprint?: string | null;
  component_package_key?: string | null;
  old_version?: string | null;
  new_version?: string | null;
  behavior_category?: string | null;
  evidence_summary?: string | null;
  before_behavior?: string | null;
  after_behavior?: string | null;
  ioc_pack_id?: string | null;
  ioc_source?: string | null;
  ioc_advisory_url?: string | null;
  ioc_confidence?: string | null;
  ioc_match_type?: 'exact match' | 'namespace watch' | 'domain watch' | string | null;
  ioc_indicator?: string | null;
  fingerprint: string;
  suppressed?: boolean;
  suppression?: Suppression;
  created_at: string;
};

export type AttentionBucket = 'fix-now' | 'verify' | 'watch' | 'info';

// Canonical case-decision vocabulary — mirrors lifecycle.DECISION_STATUSES on
// the backend. `in_progress` (S-035) is "fix applied, awaiting rescan proof".
export type CaseDecisionStatus = 'verified' | 'false_positive' | 'accepted_risk' | 'fixed' | 'in_progress';
// The rich lifecycle / presentation state a case *is* at a glance
// (lifecycle.LIFECYCLE_STATES). Distinct from the scan-diff axis below.
export type CaseLifecycleState = 'open' | 'verified' | 'in_progress' | 'accepted_risk' | 'resolved';
// The scan-diff axis: how a case MOVED between two scans. This is a separate
// machine from the lifecycle state above — a case can be diff `recurring` and
// lifecycle `in_progress` at once. Kept as `CaseChangeStatus` for back-compat;
// `CaseDiffStatus` is the clearer name for the same distinct axis.
export type CaseChangeStatus = 'new' | 'recurring' | 'resolved';
export type CaseDiffStatus = CaseChangeStatus;
export type VexStatus = 'affected' | 'not_affected' | 'fixed' | 'under_investigation';
export type AiFollowUpActionId = 'verify_findings' | 'fix_vulnerabilities' | 'create_remediation_plan' | 'explain_risk' | 'recheck_after_fixes';
export type AiFollowUpScopeId = 'critical' | 'critical_high' | 'all_open' | 'selected_cases' | 'new_since_last_scan';
export type AiDisposition = 'confirmed_real' | 'false_positive' | 'docs_example' | 'accepted_risk' | 'already_fixed' | 'fixed_by_agent' | 'needs_review';

export type AiFollowUpPromptResponse = {
  repo: string;
  repo_path?: string | null;
  scan_id?: string | null;
  action: AiFollowUpActionId;
  scope: AiFollowUpScopeId;
  case_count: number;
  preview: string;
  prompt: string;
  case_ids?: string[];
};

export type CaseResolutionPreviewItem = {
  id: string;
  case_id: string;
  display_id?: string;
  repo_name?: string | null;
  scan_id?: string | null;
  ai_disposition?: AiDisposition | string;
  disposition: AiDisposition | string;
  mapped_decision?: CaseDecisionStatus | null;
  confidence: 'high' | 'medium' | 'low' | string;
  reason: string;
  evidence?: unknown[];
  recommended_next_step?: string | null;
  status: 'pending' | 'applied' | 'left_open' | 'rejected';
  warning?: string | null;
  created_at?: string;
};

export type CaseResolutionRun = {
  id: string;
  run_id: string;
  repo: string;
  repo_name: string;
  scan_id?: string | null;
  action: AiFollowUpActionId | string;
  scope: AiFollowUpScopeId | string;
  source: string;
  imported_at: string;
  applied_at?: string | null;
  status: 'previewed' | 'applied' | 'partially_applied' | 'rejected' | string;
  summary: {
    total?: number;
    will_apply?: number;
    will_leave_open?: number;
    rejected?: number;
    warnings?: string[];
    dispositions?: Record<string, number>;
    statuses?: Record<string, number>;
  };
  items: CaseResolutionPreviewItem[];
  valid?: boolean;
};

export type CaseResolutionPreviewResponse = CaseResolutionRun & {
  valid: boolean;
};

export type CaseResolutionApplyResponse = {
  run_id: string;
  applied: number;
  left_open: number;
  rejected: number;
  case_ids: string[];
  warnings: string[];
};

export type CaseDelta = {
  new: number;
  recurring: number;
  resolved: number;
};

export type DependencyChangeType = 'added' | 'removed' | 'upgraded' | 'downgraded' | 'version-changed' | 'license-changed';

export type DependencyDeltaStatus = 'no-sbom' | 'first-scan' | 'unchanged' | 'changed';
export type DependencyCveStatus = 'has-cve' | 'no-cve' | 'not-checked' | 'unknown';
export type DependencyMatchConfidence = 'strong' | 'weak-match' | 'unknown';
export type SilentUpgradeStatus = 'flagged' | 'explained' | 'not-silent' | 'unknown';
export type SilentUpgradeKind = 'direct' | 'transitive' | string;

export type DependencyDeltaCounts = Partial<Record<DependencyChangeType, number>>;
export type DependencyCveCounts = Partial<Record<DependencyCveStatus, number>>;

export type DependencyComponent = {
  package_key: string;
  name: string | null;
  version: string | null;
  ecosystem: string | null;
  component_type: string | null;
  package_url: string | null;
  license: string | null;
  supplier: string | null;
  source_path: string | null;
  source_format: string | null;
  source_file: string | null;
  bom_ref: string | null;
  component_fingerprint: string | null;
};

export type DependencyChange = {
  repo_name: string;
  scan_id: string;
  previous_scan_id: string;
  package_key: string;
  change_type: DependencyChangeType;
  change_types: DependencyChangeType[];
  name: string | null;
  ecosystem: string | null;
  component_type: string | null;
  package_url: string | null;
  source_path: string | null;
  previous_version: string | null;
  current_version: string | null;
  previous_license: string | null;
  current_license: string | null;
  version_changed: boolean;
  license_changed: boolean;
  version_direction: 'upgraded' | 'downgraded' | 'changed' | null;
  previous_component: DependencyComponent | null;
  current_component: DependencyComponent | null;
  match_confidence?: DependencyMatchConfidence;
  match_label?: string;
  metadata_warnings?: string[];
  cve_status?: DependencyCveStatus;
  cve_label?: string;
  cve_reason?: string;
  checked_by?: string[];
  silent_upgrade?: {
    status: SilentUpgradeStatus | string;
    kind?: SilentUpgradeKind | null;
    label?: string | null;
    reason?: string | null;
    manifest_path?: string | null;
    manifest_scope?: string | null;
    manifest_declaration?: string | null;
  };
};

export type DependencyDelta = {
  repo_name: string;
  scan_id: string;
  previous_scan_id: string | null;
  has_previous_scan: boolean;
  status: DependencyDeltaStatus;
  current_count: number;
  previous_count: number;
  counts: DependencyDeltaCounts;
  cve_counts?: DependencyCveCounts;
  comparison_explanation?: string;
  changes: DependencyChange[];
};

export type DependencyTrustRecord = {
  id?: number;
  scan_id: string;
  repo_name: string;
  component_fingerprint: string | null;
  component_package_key: string | null;
  package_name: string | null;
  package_version: string | null;
  package_ecosystem: string | null;
  package_url: string | null;
  source_repo: string | null;
  source_repo_url: string | null;
  source_repo_confidence: string;
  source_repo_reason: string;
  scorecard_score: number | null;
  scorecard_status: string;
  criticality_score: number | null;
  criticality_status: string;
  checked_at: string | null;
  freshness: 'fresh' | 'stale' | 'unknown' | 'unavailable' | string;
  status: string;
  cache_key: string | null;
  error?: string | null;
};

export type PlatformPostureSnapshot = {
  id?: number;
  scan_id: string;
  repo_name: string;
  scanner: string;
  source: string;
  target: string;
  status: 'checked' | 'partial' | 'skipped' | 'empty' | 'unknown' | string;
  reason?: string | null;
  summary?: {
    records?: number;
    failed?: number;
    passed?: number;
    skipped?: number;
    by_status?: Record<string, number>;
    failed_by_severity?: Record<string, number>;
    failed_by_namespace?: Record<string, number>;
  };
  records?: unknown[];
  snapshot_fingerprint?: string | null;
  created_at?: string | null;
};

export type CaseDecision = {
  case_id: string;
  repo_name: string;
  status: CaseDecisionStatus;
  note: string | null;
  vex_status?: VexStatus | null;
  vex_justification?: string | null;
  vex_reason?: string | null;
  vulnerability_id?: string | null;
  package_name?: string | null;
  package_version?: string | null;
  package_ecosystem?: string | null;
  package_url?: string | null;
  component_package_key?: string | null;
  fixed_version?: string | null;
  created_at: string;
  updated_at: string;
};

export type SuppressionReason = {
  reason: string;
  decision_status: CaseDecisionStatus | string;
  vex_status: VexStatus | string;
  cases: number;
  findings: number;
};

export type SuppressedCounts = {
  cases: number;
  findings: number;
  reasons: SuppressionReason[];
};

export type Suppression = {
  case_id?: string;
  repo_name?: string;
  status?: CaseDecisionStatus | string;
  decision_status?: CaseDecisionStatus | string;
  vex_status?: VexStatus | string;
  reason?: string;
  vex_justification?: string;
  vex_reason?: string;
  vulnerability_id?: string | null;
  package_name?: string | null;
  package_ecosystem?: string | null;
  package_url?: string | null;
  component_package_key?: string | null;
  matched_by?: string;
  updated_at?: string | null;
};

/**
 * The case shape as it actually arrives over the wire. These are exactly the
 * backend `SecurityCase` dataclass fields (`model.py` / built in `cases.py`)
 * plus the fields the read path injects on top: `scan_id`/`repo`/`repo_name`
 * identity, the change-tracking lifecycle fields, the decision/suppression
 * envelope, the honey-incident link, and `inferred_secret_name` (added only for
 * scaffolded secrets cases in `assemble_summary_payload`). Drifted aliases the
 * backend never emits used to live here as decorative fallbacks; they have been
 * removed (S-022) so the type can't lie about the contract.
 */
export type SecurityCase = {
  // Backend dataclass fields (the canonical wire shape).
  case_id?: string | number;
  title?: string;
  plain_english_risk?: string;
  action_level?: AttentionBucket | string;
  confidence?: string | number | null;
  category?: string;
  severity?: Severity;
  affected_files?: string[];
  evidence?: unknown[];
  scanners?: string[];
  fix_steps?: string[];
  agent_prompt?: string;
  priority_reasons?: string[];
  install_recency?: {
    confidence?: 'strong' | 'weak' | 'unknown' | string | null;
    last_install_signal_at?: string | null;
    evidence?: string[];
  } | null;
  rotation_surfaces?: string[];
  // Server-injected on the read path.
  scan_id?: string;
  repo?: string;
  repo_name?: string;
  inferred_secret_name?: string | null;
  created_at?: string;
  decision?: CaseDecision;
  suppressed?: boolean;
  suppression?: Suppression;
  change_status?: CaseChangeStatus;
  lifecycle_state?: CaseLifecycleState;
  previous_scan_id?: string;
  resolved_by_scan_id?: string;
  resolved_at?: string;
  honey_event_id?: string;
  incident?: HoneyIncident | null;
};

export type DisplayCase = {
  id: string;
  repoName: string;
  bucket: AttentionBucket;
  title: string;
  why: string;
  location: string;
  confidence: string;
  sources: string[];
  nextStep: string;
  severity?: Severity;
  category?: string;
  scanId?: string;
  agentPrompt?: string;
  createdAt?: string;
  decision?: CaseDecision;
  suppressed?: boolean;
  suppression?: Suppression;
  changeStatus?: CaseChangeStatus;
  lifecycleState?: CaseLifecycleState;
  resolvedByScanId?: string;
  resolvedAt?: string;
  honeyEventId?: string;
  incident?: HoneyIncident | null;
  installRecency?: SecurityCase['install_recency'];
  rotationSurfaces?: string[];
  /**
   * Best-effort env-var name from `infer_secret_name` on the backend, present
   * only on secrets-category cases when rotation is scaffolded for the repo.
   * The case card uses this to pre-fill the rotation modal.
   */
  inferredSecretName?: string;
};

export type ScanCompleteness = {
  checksRan: string[];
  checksMissing: string[];
  cannotProve: string[];
};

export type ScanHistoryItem = {
  id: string;
  repo_name: string;
  started_at: string;
  finished_at: string | null;
  health_score: number;
  status: string;
  profile: string;
};

/**
 * Set only when ObservatoryDB found the history database unreadable, quarantined
 * it, and started a fresh history. Mirrors the `payload.history_recovery` shape
 * built in `dashboard_server.assemble_summary_payload`. A machine-wide event, not
 * repo-scoped — the dashboard surfaces it so an emptied history reads as a
 * preserved-and-recovered moment, never silent data loss.
 */
export type HistoryRecovery = {
  status: string;
  message: string;
  quarantined_path: string | null;
};

export type DashboardSummary = {
  repos: RepositorySummary[];
  history: ScanHistoryItem[];
  findings: Finding[];
  active_findings?: Finding[];
  suppressed_findings?: Finding[];
  cases?: SecurityCase[];
  active_cases?: SecurityCase[];
  suppressed_cases?: SecurityCase[];
  case_decisions?: CaseDecision[];
  suppressed_counts?: SuppressedCounts;
  suppression_reasons?: SuppressionReason[];
  honey_keys?: HoneyKey[];
  honey_key_events?: HoneyKeyEvent[];
  project_statuses?: SecurityProjectStatus[];
  honey_event_retention_days?: number;
  scanner_catalog?: ScannerCatalogItem[];
  tool_catalog?: ToolCatalogItem[];
  security_packs?: SecurityPackCatalogItem[];
  scan_profiles?: ScanProfileCatalogItem[];
  managed_tools?: unknown[];
  agent_lab_proposals?: AgentLabProposal[];
  case_resolution_runs?: CaseResolutionRun[];
  completeness?: {
    checks_ran?: string[];
    checks_skipped?: string[];
    checks_missing?: string[];
    cannot_prove?: string[];
  };
  scan_completeness?: {
    checks_ran?: string[];
    checks_skipped?: string[];
    checks_missing?: string[];
    cannot_prove?: string[];
  };
  environment?: {
    scm_token_present?: boolean;
  };
  recovery_playbooks?: RecoveryPlaybook[];
  history_recovery?: HistoryRecovery;
};

export type RecoveryPlaybookItem = {
  case_id: string;
  repo: string;
  title: string;
  severity: Severity;
  category: string;
  action_level: string;
  scan_id: string | null;
  location: string;
  affected_files: string[];
  scanners: string[];
};

export type RecoveryPlaybook = {
  id: string;
  title: string;
  summary: string;
  severity: Severity;
  scanners: string[];
  estimated_minutes: number;
  estimate_label: string;
  steps: string[];
  case_count: number;
  affected_files: string[];
  items: RecoveryPlaybookItem[];
};

export type ProjectRepo = {
  name: string;
  path: string;
};

export type ProjectsPayload = {
  root: string;
  repos: ProjectRepo[];
};

export type DashboardMode = 'all-repos' | 'repo';

export type TargetSelection =
  | {mode: 'all-repos'}
  | {mode: 'repo'; repo: ProjectRepo};

export const emptySummary: DashboardSummary = {
  repos: [],
  history: [],
  findings: [],
  agent_lab_proposals: [],
};

const severityWeight: Record<Severity, number> = {
  critical: 5,
  high: 4,
  medium: 3,
  low: 2,
  info: 1,
};

export const severities: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

export const attentionBuckets: AttentionBucket[] = ['fix-now', 'verify', 'watch', 'info'];

export const attentionBucketLabels: Record<AttentionBucket, string> = {
  'fix-now': 'Fix now',
  verify: 'Verify',
  watch: 'Watch',
  info: 'Info',
};

export const caseDecisionLabels: Record<CaseDecisionStatus, string> = {
  verified: 'Verified',
  false_positive: 'False positive',
  accepted_risk: 'Accepted risk',
  fixed: 'Marked fixed',
  in_progress: 'Fix in progress',
};

// What a case *is* at a glance (lifecycle.LIFECYCLE_STATES). `in_progress` is
// the "fix applied, awaiting rescan proof" verifying beat.
export const caseLifecycleLabels: Record<CaseLifecycleState, string> = {
  open: 'Open',
  verified: 'Verified',
  in_progress: 'Verifying',
  accepted_risk: 'Accepted risk',
  resolved: 'Resolved',
};

export const caseChangeLabels: Record<CaseChangeStatus, string> = {
  new: 'New',
  recurring: 'Still open',
  resolved: 'Resolved',
};

export const dependencyChangeLabels: Record<DependencyChangeType, string> = {
  added: 'Added',
  removed: 'Removed',
  upgraded: 'Upgraded',
  downgraded: 'Downgraded',
  'version-changed': 'Version changed',
  'license-changed': 'License changed',
};

export const dependencyDeltaStatuses: Record<DependencyDeltaStatus, string> = {
  'no-sbom': 'No SBOM',
  'first-scan': 'First scan',
  unchanged: 'No changes',
  changed: 'Changed',
};

export const dependencyCveStatusLabels: Record<DependencyCveStatus, string> = {
  'has-cve': 'Known CVE',
  'no-cve': 'No CVE found',
  'not-checked': 'Not checked',
  unknown: 'Unknown',
};

export const dependencyMatchLabels: Record<DependencyMatchConfidence, string> = {
  strong: 'Strong match',
  'weak-match': 'Weak match',
  unknown: 'Unknown',
};

export const scannerStatusLabels: Record<ScannerDoctorStatus, string> = {
  ran: 'Ran',
  missing: 'Not installed',
  error: 'Error',
  'not-run': 'Not run',
};

export const defaultScannerCatalog: ScannerCatalogItem[] = [
  {
    scanner: 'ioc-watch',
    label: 'IOC Watch',
    area: 'Named-campaign defense',
    covers: 'Local IOC packs matched against saved SBOM components, namespace watches, and known campaign domains.',
    profile: 'default, deps, full, ioc',
    install: 'Built in. No install needed.',
    next_step: 'Run security-scan ioc after an SBOM-backed dependency scan.',
    built_in: true,
  },
  {
    scanner: 'ai-static',
    label: 'Built-in AI static checks',
    area: 'AI agent/MCP',
    covers: 'Prompt files, MCP configs, agent-readable instructions, and risky local tool setup.',
    profile: 'quick, ai, full',
    install: 'Built in. No install needed.',
    next_step: 'Run a quick or AI scan to include this check.',
    built_in: true,
  },
  {
    scanner: 'install-hooks',
    label: 'Install hook classifier',
    area: 'Supply-chain surfaces',
    covers: 'Package install scripts and Python build hooks classified by install-time execution risk.',
    profile: 'default, quick, deps, full',
    install: 'Built in. No install needed.',
    next_step: 'Run a default, quick, dependency, or full scan to include install-hook classification.',
    built_in: true,
  },
  {
    scanner: 'workflow-audit',
    label: 'Workflow surface audit',
    area: 'Supply-chain surfaces',
    covers: 'GitHub Actions pins, fetch-and-exec patterns, secret handling, token permissions, and pull_request_target risk.',
    profile: 'default, quick, iac, full',
    install: 'Built in. No install needed.',
    next_step: 'Run a default, quick, IaC, or full scan to include workflow surface raw findings.',
    built_in: true,
  },
  {
    scanner: 'semgrep',
    label: 'Semgrep',
    area: 'Code security',
    covers: 'Code vulnerability patterns such as injection, unsafe parsing, and insecure defaults.',
    profile: 'quick, code, full',
    install: './install-security-observatory.sh or brew install semgrep',
    next_step: 'Install Semgrep, then rerun the code or quick scan.',
  },
  {
    scanner: 'gitleaks',
    label: 'Gitleaks',
    area: 'Secrets',
    covers: 'Fast detection of exposed API keys, tokens, passwords, and private keys.',
    profile: 'quick, secrets, full',
    install: './install-security-observatory.sh or brew install gitleaks',
    next_step: 'Install Gitleaks, then rerun the secrets or quick scan.',
  },
  {
    scanner: 'trufflehog',
    label: 'TruffleHog',
    area: 'Secrets',
    covers: 'Deeper second-opinion secret detection.',
    profile: 'secrets, full',
    install: './install-security-observatory.sh or brew install trufflehog',
    next_step: 'Install TruffleHog, then rerun the secrets or full scan.',
  },
  {
    scanner: 'trivy',
    label: 'Trivy',
    area: 'Dependencies / IaC',
    covers: 'Filesystem, dependency, secret, and infrastructure misconfiguration checks.',
    profile: 'deps, secrets, iac, full',
    install: './install-security-observatory.sh or brew install trivy',
    next_step: 'Install Trivy, then rerun the dependency, secrets, IaC, or full scan.',
  },
  {
    scanner: 'osv-scanner',
    label: 'OSV-Scanner',
    area: 'Dependencies / SBOM',
    covers: 'Open-source dependency vulnerabilities from OSV advisories.',
    profile: 'quick, deps, full',
    install: './install-security-observatory.sh or brew install osv-scanner',
    next_step: 'Install OSV-Scanner, then rerun the dependency or quick scan.',
  },
  {
    scanner: 'syft',
    label: 'Syft',
    area: 'Dependencies / SBOM',
    covers: 'Software bill of materials generation.',
    profile: 'deps, full',
    install: './install-security-observatory.sh or brew install syft',
    next_step: 'Install Syft, then rerun the dependency or full scan.',
  },
  {
    scanner: 'grype',
    label: 'Grype',
    area: 'Dependencies / SBOM',
    covers: 'Dependency vulnerability scanning from an SBOM or repository filesystem.',
    profile: 'deps, full',
    install: './install-security-observatory.sh or brew install grype',
    next_step: 'Install Grype, then rerun the dependency or full scan.',
  },
  {
    scanner: 'checkov',
    label: 'Checkov',
    area: 'Infrastructure',
    covers: 'Terraform, Kubernetes, and cloud configuration policy checks.',
    profile: 'iac, full',
    install: './install-security-observatory.sh or uv tool install checkov',
    next_step: 'Install Checkov, then rerun the IaC or full scan.',
  },
  {
    scanner: 'medusa',
    label: 'Medusa',
    area: 'AI agent/MCP',
    covers: 'MCP, prompt injection, AI editor config, and repo-poisoning checks.',
    profile: 'ai, full',
    install: './install-security-observatory.sh or uv tool install medusa-security',
    next_step: 'Install Medusa, then rerun the AI or full scan.',
  },
  {
    scanner: 'malcontent',
    label: 'malcontent',
    area: 'Behavioral drift',
    covers: 'Advanced diffing of old and new dependency artifacts for suspicious behavior changes.',
    profile: 'behavioral-drift',
    install: 'Install malcontent separately, then provide local package artifacts under the behavioral artifact cache.',
    next_step: 'Run security-scan --behavioral-drift after at least two SBOM-backed dependency scans.',
  },
  {
    scanner: 'legitify',
    label: 'legitify',
    area: 'Platform posture',
    covers: 'Optional connected checks for repository branch protection, Actions permissions, webhooks, and SCM settings.',
    profile: 'platform-posture',
    install: 'brew install legitify, then set SCM_TOKEN for the platform posture profile.',
    next_step: 'Run security-scan --platform-posture only when you want a token-backed platform check.',
  },
];

export const categoryLabels: Record<string, string> = {
  'code-security': 'Code vulnerabilities',
  secrets: 'Leaked secrets',
  dependencies: 'Dependency risks',
  iac: 'Infrastructure exposure',
  workflow: 'Workflow surfaces',
  'install-hooks': 'Install hooks',
  'platform-posture': 'Platform posture',
  'supply-chain-ioc': 'Named-campaign matches',
  'silent-upgrade': 'Silent dependency changes',
  'ai-risk': 'AI agent risks',
  system: 'System checks',
};

export function categoryLabel(category: string): string {
  return categoryLabels[category] ?? category.replace(/[-_]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

export function severityLabel(severity: Severity): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1);
}

export function averageHealth(summary: DashboardSummary): number {
  if (!summary.repos.length) return 100;
  const total = summary.repos.reduce((sum, repo) => sum + repo.health, 0);
  return Math.round(total / summary.repos.length);
}

export function categoryTotal(summary: DashboardSummary, category: string): number {
  return summary.repos.reduce((sum, repo) => sum + (repo.categories[category] ?? 0), 0);
}

export function severityTotal(summary: DashboardSummary, severity: Severity): number {
  return summary.repos.reduce((sum, repo) => sum + (repo.counts[severity] ?? 0), 0);
}

function severityCountTotal(counts?: SeverityCounts): number {
  return severities.reduce((sum, severity) => sum + (counts?.[severity] ?? 0), 0);
}

export function activeRawFindingCount(summary: DashboardSummary): number {
  return summary.repos.reduce((sum, repo) => sum + severityCountTotal(repo.counts), 0);
}

export function repoHasPreCaseScan(repo: RepositorySummary): boolean {
  const activeRaw = severityCountTotal(repo.counts);
  const caseCount = (repo.active_cases ?? repo.cases ?? []).length + (repo.suppressed_cases ?? []).length;
  return activeRaw > 0 && caseCount === 0;
}

export function preCaseScanRepos(summary: DashboardSummary): RepositorySummary[] {
  return summary.repos.filter(repoHasPreCaseScan);
}

export function preCaseRawFindingCount(summary: DashboardSummary): number {
  return preCaseScanRepos(summary).reduce((sum, repo) => sum + severityCountTotal(repo.counts), 0);
}

export function caseBackedRawFindingCount(summary: DashboardSummary): number {
  return summary.repos
    .filter((repo) => !repoHasPreCaseScan(repo))
    .reduce((sum, repo) => sum + severityCountTotal(repo.counts), 0);
}

function activeFindingRecords(summary: DashboardSummary): Finding[] {
  return summary.active_findings ?? summary.findings.filter((finding) => !finding.suppressed);
}

export function totalFindings(summary: DashboardSummary): number {
  return activeFindingRecords(summary).length;
}

export function unresolvedRisk(summary: DashboardSummary): number {
  return severityTotal(summary, 'critical') + severityTotal(summary, 'high');
}

export function sortedFindings(summary: DashboardSummary, category?: string): Finding[] {
  return [...activeFindingRecords(summary)]
    .filter((finding) => !category || finding.category === category)
    .sort((a, b) => severityWeight[b.severity] - severityWeight[a.severity]);
}

export function latestScanTime(summary: DashboardSummary): string | null {
  return summary.repos
    .map((repo) => repo.last_scan)
    .filter((value): value is string => Boolean(value))
    .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] ?? null;
}

export function findingScanTime(summary: DashboardSummary, finding: Finding): string | null {
  const repo = summary.repos.find((item) => item.scan_id === finding.scan_id);
  if (repo?.last_scan) return repo.last_scan;
  const historyItem = summary.history.find((item) => item.id === finding.scan_id);
  return historyItem?.finished_at ?? historyItem?.started_at ?? finding.created_at;
}

export function reportDownloadUrl(scanId: string, kind: 'raw' | 'prompt'): string {
  return `/api/report?scanId=${encodeURIComponent(scanId)}&kind=${kind}`;
}

export function reportViewUrl(scanId: string, kind: 'raw' | 'prompt'): string {
  return `/report/?scanId=${encodeURIComponent(scanId)}&kind=${kind}`;
}

export function honeyKeyCounts(summary: DashboardSummary): Record<HoneyKeyStatus, number> {
  return {
    active: summary.honey_keys?.filter((key) => key.status === 'active').length ?? 0,
    triggered: summary.honey_keys?.filter((key) => key.status === 'triggered').length ?? 0,
    archived: summary.honey_keys?.filter((key) => key.status === 'archived').length ?? 0,
  };
}

export function latestHoneyKeyEvent(summary: DashboardSummary): HoneyKeyEvent | null {
  return [...(summary.honey_key_events ?? [])].sort((a, b) => new Date(b.triggered_at).getTime() - new Date(a.triggered_at).getTime())[0] ?? null;
}

export function latestOpenHoneyKeyEvent(summary: DashboardSummary): HoneyKeyEvent | null {
  return [...(summary.honey_key_events ?? [])]
    .filter((event) => !event.incident?.closed_at)
    .sort((a, b) => new Date(b.triggered_at).getTime() - new Date(a.triggered_at).getTime())[0] ?? null;
}

export function honeyKeyById(summary: DashboardSummary, keyId: string): HoneyKey | undefined {
  return summary.honey_keys?.find((key) => key.id === keyId);
}

function normalizeBucket(value: string | undefined, severity?: Severity): AttentionBucket {
  // The backend (Python) encodes the action level as `fix_now`; the dashboard
  // uses `fix-now`. That single snake_case→kebab boundary is the only alias we
  // translate — no blanket rewrite that could silently reshape other values.
  const normalized = value === 'fix_now' ? 'fix-now' : value;
  if (normalized === 'fix-now' || normalized === 'verify' || normalized === 'watch' || normalized === 'info') return normalized;
  if (severity === 'critical' || severity === 'high') return 'fix-now';
  if (severity === 'medium') return 'verify';
  if (severity === 'low') return 'watch';
  return 'info';
}

function confidenceLabel(confidence: string | number | null | undefined, severity?: Severity): string {
  if (typeof confidence === 'number') return confidence <= 1 ? `${Math.round(confidence * 100)}%` : `${Math.round(confidence)}%`;
  if (confidence?.trim()) return confidence.trim();
  if (severity === 'critical' || severity === 'high') return 'High enough to act';
  if (severity === 'medium') return 'Needs a quick check';
  return 'Low';
}

function whyForFinding(finding: Finding): string {
  if (finding.category === 'secrets') return 'A saved secret can let someone access accounts, services, or data without permission.';
  if (finding.category === 'dependencies') return 'This package may include a known weakness that is already documented elsewhere.';
  if (finding.category === 'silent-upgrade') return 'A package changed in the saved SBOM without a matching source-manifest dependency change.';
  if (finding.category === 'iac') return 'A configuration issue can accidentally expose infrastructure or data.';
  if (finding.category === 'workflow') return 'A workflow can expose tokens or run untrusted automation in a risky way.';
  if (finding.category === 'install-hooks') return 'An install hook can run code when dependencies are installed.';
  if (finding.category === 'platform-posture') return 'A repository setting outside the code may make unsafe changes or broad automation permissions easier.';
  if (finding.category === 'ai-risk') return 'An AI agent or tool setup may be easier to misuse than intended.';
  if (finding.severity === 'critical' || finding.severity === 'high') return 'This looks important enough to fix before adding more work on top of it.';
  return 'This is worth checking so small security debt does not quietly pile up.';
}

function remediationForFinding(finding: Finding): string {
  if (finding.remediation?.trim()) return finding.remediation;
  if (finding.category === 'secrets') return 'Remove the value, rotate it if it was real, and store the replacement outside the repo.';
  if (finding.category === 'dependencies') return 'Update the affected package, then run the dependency check again.';
  if (finding.category === 'silent-upgrade') return 'Verify or revert the lockfile movement; this is a signal to check, not proof of compromise.';
  if (finding.category === 'iac') return 'Make the setting private by default, then run the infrastructure check again.';
  if (finding.category === 'workflow') return 'Pin actions, remove fetch-and-exec shell patterns, and narrow workflow token permissions.';
  if (finding.category === 'install-hooks') return 'Review the install-time command and remove unsafe remote execution or credential-file writes.';
  if (finding.category === 'platform-posture') return 'Restore the stricter platform setting, then rerun the connected posture check.';
  if (finding.category === 'ai-risk') return 'Narrow the tool permissions and keep untrusted text away from agent instructions.';
  return 'Ask an AI agent to inspect this file, make the smallest safe fix, and run the check again.';
}

function caseLocation(item: SecurityCase): string {
  return item.affected_files?.[0] ?? 'Repository';
}

function caseSources(item: SecurityCase): string[] {
  const sources = item.scanners ?? [];
  return [...new Set(sources.filter(Boolean).map((source) => String(source)))];
}

function caseToDisplayCase(item: SecurityCase, index: number): DisplayCase {
  const severity = item.severity;
  const scanId = item.scan_id;
  const title = item.title ?? 'Security case needs attention';
  const firstFixStep = item.fix_steps?.find((step) => step.trim());
  const repoName = String(item.repo_name ?? item.repo ?? 'repository');
  const changeStatus = item.change_status;
  return {
    id: String(item.case_id ?? `${scanId ?? 'case'}-${index}`),
    repoName,
    bucket: normalizeBucket(item.action_level, severity),
    title,
    why: item.plain_english_risk ?? 'This case may affect the safety or reliability of the project.',
    location: caseLocation(item),
    confidence: confidenceLabel(item.confidence, severity),
    sources: caseSources(item),
    nextStep: firstFixStep ?? 'Give this case to an AI agent and ask it to make the smallest safe fix.',
    severity,
    category: item.category,
    scanId,
    agentPrompt: item.agent_prompt,
    createdAt: item.created_at,
    decision: item.decision,
    suppressed: Boolean(item.suppressed),
    suppression: item.suppression,
    changeStatus,
    lifecycleState: item.lifecycle_state,
    resolvedByScanId: item.resolved_by_scan_id,
    resolvedAt: item.resolved_at,
    honeyEventId: item.honey_event_id,
    incident: item.incident,
    installRecency: item.install_recency,
    rotationSurfaces: item.rotation_surfaces,
    inferredSecretName: item.inferred_secret_name ?? undefined,
  };
}

function findingToDisplayCase(finding: Finding): DisplayCase {
  return {
    id: `${finding.scan_id}-${finding.fingerprint}-${finding.id}`,
    repoName: finding.repo_name,
    bucket: normalizeBucket(undefined, finding.severity),
    title: finding.title,
    why: whyForFinding(finding),
    location: formatLocation(finding),
    confidence: confidenceLabel(undefined, finding.severity),
    sources: [finding.scanner],
    nextStep: remediationForFinding(finding),
    severity: finding.severity,
    category: finding.category,
    scanId: finding.scan_id,
    createdAt: finding.created_at,
    suppressed: Boolean(finding.suppressed),
    suppression: finding.suppression,
  };
}

function sortDisplayCases(items: DisplayCase[]): DisplayCase[] {
  return items.sort((a, b) => {
    const changeSort = changeRank(a.changeStatus) - changeRank(b.changeStatus);
    if (changeSort) return changeSort;
    const decisionSort = decisionRank(a.decision?.status) - decisionRank(b.decision?.status);
    if (decisionSort) return decisionSort;
    return attentionBuckets.indexOf(a.bucket) - attentionBuckets.indexOf(b.bucket);
  });
}

export function displayCases(summary: DashboardSummary): DisplayCase[] {
  if (summary.cases !== undefined || summary.active_cases !== undefined || summary.suppressed_cases !== undefined) {
    const sourceCases = summary.cases?.length ? summary.cases : summary.active_cases ?? [];
    return sortDisplayCases(sourceCases.filter((item) => !item.suppressed).map(caseToDisplayCase));
  }

  return sortedFindings(summary).map(findingToDisplayCase);
}

export function suppressedDisplayCases(summary: DashboardSummary): DisplayCase[] {
  const suppressedCases = summary.suppressed_cases?.length
    ? summary.suppressed_cases
    : (summary.cases ?? []).filter((item) => item.suppressed);
  if (summary.cases !== undefined || summary.active_cases !== undefined || summary.suppressed_cases !== undefined) {
    return suppressedCases.length ? sortDisplayCases(suppressedCases.map(caseToDisplayCase)) : [];
  }
  if (suppressedCases.length) return sortDisplayCases(suppressedCases.map(caseToDisplayCase));
  return (summary.suppressed_findings ?? summary.findings.filter((finding) => finding.suppressed)).map(findingToDisplayCase);
}

export function actionBucketCounts(summary: DashboardSummary): Record<AttentionBucket, number> {
  const counts: Record<AttentionBucket, number> = {'fix-now': 0, verify: 0, watch: 0, info: 0};
  for (const item of displayCases(summary)) {
    if (caseNeedsAttention(item)) counts[item.bucket] += 1;
  }
  return counts;
}

function changeRank(status?: CaseChangeStatus): number {
  if (!status) return 1;
  return {new: 0, recurring: 1, resolved: 9}[status];
}

function decisionRank(status?: CaseDecisionStatus): number {
  if (!status) return 0;
  return {verified: 1, in_progress: 2, accepted_risk: 3, fixed: 4, false_positive: 5}[status];
}

export function caseNeedsAttention(item: DisplayCase): boolean {
  if (item.changeStatus === 'resolved') return false;
  if (item.decision?.status === 'false_positive' || item.decision?.status === 'accepted_risk') return false;
  return true;
}

export function caseDecisionCounts(summary: DashboardSummary): Record<CaseDecisionStatus | 'open', number> {
  const counts: Record<CaseDecisionStatus | 'open', number> = {open: 0, verified: 0, false_positive: 0, accepted_risk: 0, fixed: 0, in_progress: 0};
  for (const item of displayCases(summary)) {
    counts[item.decision?.status ?? 'open'] += 1;
  }
  return counts;
}

export function caseChangeCounts(summary: DashboardSummary): Record<CaseChangeStatus, number> {
  const counts: Record<CaseChangeStatus, number> = {new: 0, recurring: 0, resolved: 0};
  for (const item of displayCases(summary)) {
    if (item.changeStatus) counts[item.changeStatus] += 1;
  }
  return counts;
}

export function aggregateCaseDelta(summary: DashboardSummary): CaseDelta {
  return summary.repos.reduce(
    (total, repo) => ({
      new: total.new + (repo.case_delta?.new ?? 0),
      recurring: total.recurring + (repo.case_delta?.recurring ?? 0),
      resolved: total.resolved + (repo.case_delta?.resolved ?? 0),
    }),
    {new: 0, recurring: 0, resolved: 0},
  );
}

export function staleRepoCount(summary: DashboardSummary, maxAgeDays = 7): number {
  const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000;
  return summary.repos.filter((repo) => !repo.last_scan || new Date(repo.last_scan).getTime() < cutoff).length;
}

export function toolCatalogItems(summary: DashboardSummary): ToolCatalogItem[] {
  return summary.tool_catalog ?? [];
}

export function securityPackItems(summary: DashboardSummary): SecurityPackCatalogItem[] {
  return summary.security_packs ?? [];
}

function scannerCatalogForSummary(summary: DashboardSummary): ScannerCatalogItem[] {
  if (summary.scanner_catalog?.length) return summary.scanner_catalog;
  const legacyItems = (summary.tool_catalog ?? [])
    .map((item): ScannerCatalogItem | null => {
      if (item.legacy_scanner) return item.legacy_scanner;
      if (!item.scanner_key) return null;
      return {
        scanner: item.scanner_key,
        label: item.label,
        area: item.category,
        covers: item.summary,
        profile: item.profiles.join(', '),
        install: item.install.instructions ?? '',
        next_step: item.install.next_step ?? '',
        built_in: item.install_state === 'built-in' || item.install.method === 'built-in',
      };
    })
    .filter((item): item is ScannerCatalogItem => item !== null);
  return legacyItems.length ? legacyItems : defaultScannerCatalog;
}

function toolByScanner(summary: DashboardSummary): Map<string, ToolCatalogItem> {
  const tools = new Map<string, ToolCatalogItem>();
  for (const item of summary.tool_catalog ?? []) {
    if (item.scanner_key) tools.set(item.scanner_key, item);
  }
  return tools;
}

function packById(summary: DashboardSummary): Map<ToolPackId, SecurityPackCatalogItem> {
  return new Map((summary.security_packs ?? []).map((pack) => [pack.id, pack]));
}

function recommendedPacksForScanner(item: ScannerCatalogItem, tool: ToolCatalogItem | undefined, packs: Map<ToolPackId, SecurityPackCatalogItem>): ScannerRecommendedPack[] {
  const packIds = item.recommended_pack_ids?.length
    ? item.recommended_pack_ids
    : tool?.packs.map((pack) => pack.pack_id) ?? [];
  const seen = new Set<ToolPackId>();
  return packIds
    .filter((packId) => {
      if (seen.has(packId)) return false;
      seen.add(packId);
      return true;
    })
    .map((packId) => packs.get(packId))
    .filter((pack): pack is SecurityPackCatalogItem => Boolean(pack))
    .map((pack) => ({
      id: pack.id,
      label: pack.label,
      mvp_state: pack.mvp_state,
      visibility: pack.visibility,
      ready_count: pack.ready_count,
      missing_count: pack.missing_count,
      display_only_count: pack.display_only_count,
      status_counts: pack.status_counts,
    }));
}

export function scannerDoctorGroups(summary: DashboardSummary): ScannerDoctorGroup[] {
  const catalog = scannerCatalogForSummary(summary);
  const statuses = latestScannerStatuses(summary);
  const tools = toolByScanner(summary);
  const packs = packById(summary);
  const groups = new Map<string, ScannerDoctorItem[]>();

  for (const item of catalog) {
    const tool = tools.get(item.scanner);
    const recommendedPacks = recommendedPacksForScanner(item, tool, packs);
    const records = statuses.get(item.scanner) ?? [];
    const failed = records.find((record) => !record.status.available || record.status.error);
    const successful = records.find((record) => record.status.available && !record.status.error);
    const status: ScannerDoctorStatus = failed
      ? failed.status.available ? 'error' : 'missing'
      : successful ? 'ran' : 'not-run';
    const findings = records.reduce((sum, record) => sum + (record.status.findings ?? 0), 0);
    const repoNames = [...new Set(records.map((record) => record.repoName))].sort((a, b) => a.localeCompare(b));
    const action = scannerAction(item, status, failed?.status.error, tool, recommendedPacks);
    const last_run = mostRecentLastScan(records.filter((record) => record.status.available));
    const doctorItem: ScannerDoctorItem = {
      ...item,
      status,
      findings,
      repoNames,
      command: failed?.status.command ?? successful?.status.command,
      error: failed?.status.error ?? null,
      action,
      tool,
      recommendedPacks,
      last_run,
    };
    const group = groups.get(item.area) ?? [];
    group.push(doctorItem);
    groups.set(item.area, group);
  }

  return [...groups.entries()].map(([area, items]) => ({
    area,
    items: items.sort((a, b) => scannerStatusRank(a.status) - scannerStatusRank(b.status) || a.label.localeCompare(b.label)),
  }));
}

export function scannerCoverageSummary(summary: DashboardSummary): string {
  if (!summary.repos.length) return 'Run a scan to see which security checks are actually available.';
  const items = scannerDoctorGroups(summary).flatMap((group) => group.items);
  const missing = items.filter((item) => item.status === 'missing').length;
  const errors = items.filter((item) => item.status === 'error').length;
  const ran = items.filter((item) => item.status === 'ran').length;
  const notRun = items.filter((item) => item.status === 'not-run').length;
  if (missing || errors) {
    return `Coverage is limited: ${missing + errors} scanner${missing + errors === 1 ? '' : 's'} need setup or repair before clean results mean much.`;
  }
  if (notRun) {
    return `${ran} scanner${ran === 1 ? '' : 's'} ran for this profile. Use the relevant opt-in profile when you need broader trust.`;
  }
  return 'All configured scanners ran without install or runtime errors.';
}

function latestScannerStatuses(summary: DashboardSummary): Map<string, {repoName: string; lastScan: string | null; status: ScannerStatus}[]> {
  const records = new Map<string, {repoName: string; lastScan: string | null; status: ScannerStatus}[]>();
  for (const repo of summary.repos) {
    for (const status of repo.scanners) {
      const list = records.get(status.scanner) ?? [];
      list.push({repoName: repositoryDisplayName(repo), lastScan: repo.last_scan, status});
      records.set(status.scanner, list);
    }
  }
  return records;
}

function mostRecentLastScan(records: {lastScan: string | null}[]): string | null {
  let latest: number | null = null;
  let latestIso: string | null = null;
  for (const record of records) {
    if (!record.lastScan) continue;
    const ms = Date.parse(record.lastScan);
    if (Number.isNaN(ms)) continue;
    if (latest === null || ms > latest) {
      latest = ms;
      latestIso = record.lastScan;
    }
  }
  return latestIso;
}

function scannerAction(
  item: ScannerCatalogItem,
  status: ScannerDoctorStatus,
  error?: string | null,
  tool?: ToolCatalogItem,
  recommendedPacks: ScannerRecommendedPack[] = [],
): string {
  const packText = recommendedPacks.length ? ` via ${recommendedPacks.map((pack) => pack.label).join(', ')}` : '';
  const profileHint = tool?.capabilities.scan_profiles[0] ?? item.profile_ids?.[0] ?? item.profile.split(',')[0]?.trim();
  const profileText = profileHint ? `the ${profileHint} profile` : 'the matching scan profile';
  const installState = tool?.install_state ?? item.install_state;
  const readyNow = installState === 'built-in' || installState === 'managed' || installState === 'detected';
  const packReadiness = recommendedPacks.length
    ? ` Pack readiness: ${recommendedPacks.map((pack) => `${pack.label} ${pack.ready_count} ready/${pack.missing_count} not installed`).join('; ')}.`
    : '';
  if (status === 'ran') return `Covered by ${item.profile}.${packReadiness} Raw findings are grouped into the cases above.`;
  if (status === 'not-run') {
    if (readyNow) return `${tool?.label ?? item.label} is ${installStateLabel(installState)}${packText}; run ${profileText} when you need this evidence.`;
    return `${item.next_step}${packText ? ` Pack context: open ${recommendedPacks.map((pack) => pack.label).join(', ')} before trusting a clean result.` : ''}`;
  }
  if (status === 'missing') {
    if (readyNow) return `${tool?.label ?? item.label} is now ${installStateLabel(installState)}${packText}; rerun ${profileText} to replace this old evidence gap.`;
    return `${item.install}${packText ? ` Recommended: open ${recommendedPacks.map((pack) => pack.label).join(', ')} or the ${tool?.label ?? item.label} tool page, then rerun ${profileText}.` : ''}`;
  }
  return error ? `Fix this scanner error, then rerun: ${error}` : `Run security-scan doctor, fix ${item.label}, then rerun the scan.`;
}

function installStateLabel(state?: ToolInstallState | string): string {
  if (state === 'built-in') return 'built in';
  if (state === 'managed') return 'DëvSec-managed';
  if (state === 'detected') return 'detected locally';
  if (state === 'not-configured') return 'installed but not configured';
  if (state === 'coming-soon') return 'display-only';
  if (state === 'unavailable') return 'unavailable';
  return 'not installed';
}

function scannerStatusRank(status: ScannerDoctorStatus): number {
  return {missing: 0, error: 1, 'not-run': 2, ran: 3}[status];
}

export function scanCompleteness(summary: DashboardSummary): ScanCompleteness {
  const payload = summary.scan_completeness ?? summary.completeness;
  const checksRan = new Set<string>();
  const checksMissing = new Set<string>();

  for (const check of payload?.checks_ran ?? []) checksRan.add(check);
  for (const check of [...(payload?.checks_skipped ?? []), ...(payload?.checks_missing ?? [])]) checksMissing.add(check);

  for (const repo of summary.repos) {
    for (const scanner of repo.scanners) {
      const label = categoryLabel(scanner.scanner);
      const status = scanner.status?.toLowerCase() ?? '';
      const skipped = status.includes('skip') || status.includes('missing') || status.includes('unavailable') || status.includes('error');
      if (scanner.available && !scanner.error && !skipped) checksRan.add(label);
      else checksMissing.add(label);
    }
  }

  if (!checksRan.size && summary.findings.length) {
    for (const finding of summary.findings) checksRan.add(categoryLabel(finding.category));
  }

  const cannotProve = payload?.cannot_prove?.length
    ? payload.cannot_prove
    : [
      'It cannot prove the project is safe.',
      'It cannot prove runtime behavior, deployed settings, or third-party accounts are secure.',
      'It cannot prove secrets found in history were never used.',
    ];

  return {
    checksRan: [...checksRan].sort((a, b) => a.localeCompare(b)),
    checksMissing: [...checksMissing].sort((a, b) => a.localeCompare(b)),
    cannotProve,
  };
}

export function latestRepoScan(summary: DashboardSummary): RepositorySummary | null {
  return [...summary.repos].sort((a, b) => new Date(b.last_scan ?? 0).getTime() - new Date(a.last_scan ?? 0).getTime())[0] ?? null;
}

export function weakestRepo(summary: DashboardSummary): RepositorySummary | null {
  return [...summary.repos].sort((a, b) => a.health - b.health)[0] ?? null;
}

function scanHistoryOrder(scan: ScanHistoryItem): number {
  const time = new Date(scan.finished_at ?? scan.started_at ?? 0).getTime();
  return Number.isNaN(time) ? 0 : time;
}

/**
 * Posture-over-time series for the trend sparkline: each completed scan's
 * health score (0–100), ordered oldest → newest and capped to the most recent
 * `points`. Returns `[]` when there is no history so callers render an honest
 * empty state instead of a fabricated line.
 */
export function trendValues(summary: DashboardSummary, points = 22): number[] {
  return [...summary.history]
    .sort((a, b) => scanHistoryOrder(a) - scanHistoryOrder(b))
    .slice(-points)
    .map((scan) => Math.max(0, Math.min(100, scan.health_score)));
}

export type ScanDiffEndpoint = {
  scan_id: string;
  repo_name: string;
  profile: string;
  started_at: string;
  finished_at: string | null;
  health_score: number;
  status: string;
};

export type ScanDiffResult = {
  base: ScanDiffEndpoint;
  head: ScanDiffEndpoint;
  health_delta: number | null;
  same_repo: boolean;
  counts: {new: number; recurring: number; resolved: number};
  new_cases: SecurityCase[];
  recurring_cases: SecurityCase[];
  resolved_cases: SecurityCase[];
};

/**
 * Compare two arbitrary saved scans. The base/head ids both flow to the server
 * route, which reuses the per-repo delta engine to return the health delta plus
 * the new / recurring / resolved case sets (resolved cases carry their
 * closure-proof binding). Local-only request — no new egress.
 */
export async function fetchScanDiff(base: string, head: string): Promise<ScanDiffResult> {
  const params = new URLSearchParams({base, head});
  const response = await fetch(`/api/scan-diff?${params.toString()}`, {cache: 'no-store'});
  if (!response.ok) {
    throw new Error(`Scan comparison failed (${response.status})`);
  }
  return (await response.json()) as ScanDiffResult;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return 'Never';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export function formatRelativeTime(value: string | null | undefined, now: Date = new Date()): string | null {
  if (!value) return null;
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return null;
  const diffSec = Math.max(0, Math.round((now.getTime() - ms) / 1000));
  if (diffSec < 60) return 'just now';
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr} h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 30) return `${diffDay} d ago`;
  const diffMo = Math.round(diffDay / 30);
  if (diffMo < 12) return `${diffMo} mo ago`;
  const diffYr = Math.round(diffMo / 12);
  return `${diffYr} y ago`;
}

export function formatLocation(finding: Finding): string {
  const file = finding.file ?? 'repository';
  return finding.line ? `${file}:${finding.line}` : file;
}

export function scannerCount(summary: DashboardSummary, scannerName: string): number {
  return summary.repos.reduce((sum, repo) => {
    const scanner = repo.scanners.find((item) => item.scanner.toLowerCase().includes(scannerName));
    return sum + (scanner?.findings ?? 0);
  }, 0);
}

export function dependencyDeltas(summary: DashboardSummary): DependencyDelta[] {
  return summary.repos
    .map((repo) => repo.dependency_delta)
    .filter((delta): delta is DependencyDelta => Boolean(delta));
}

export function dependencyChanges(summary: DashboardSummary): DependencyChange[] {
  return dependencyDeltas(summary).flatMap((delta) => delta.changes ?? []);
}

export function dependencyTrustRecords(summary: DashboardSummary): DependencyTrustRecord[] {
  return summary.repos.flatMap((repo) => repo.dependency_trust ?? []);
}

export function behavioralDriftFindings(summary: DashboardSummary): Finding[] {
  return sortedFindings(summary, 'behavioral-drift');
}

export function iocMatchFindings(summary: DashboardSummary): Finding[] {
  return sortedFindings(summary, 'supply-chain-ioc');
}

export function platformPostureFindings(summary: DashboardSummary): Finding[] {
  return sortedFindings(summary, 'platform-posture');
}

export function platformPostureSnapshots(summary: DashboardSummary): PlatformPostureSnapshot[] {
  return summary.repos
    .map((repo) => repo.platform_posture)
    .filter((snapshot): snapshot is PlatformPostureSnapshot => Boolean(snapshot));
}

export function dependencyDeltaCounts(summary: DashboardSummary): Record<DependencyChangeType, number> {
  const counts: Record<DependencyChangeType, number> = {
    added: 0,
    removed: 0,
    upgraded: 0,
    downgraded: 0,
    'version-changed': 0,
    'license-changed': 0,
  };
  for (const delta of dependencyDeltas(summary)) {
    for (const key of Object.keys(counts) as DependencyChangeType[]) {
      counts[key] += delta.counts?.[key] ?? 0;
    }
  }
  return counts;
}

export function dependencyCveCounts(summary: DashboardSummary): Record<DependencyCveStatus, number> {
  const counts: Record<DependencyCveStatus, number> = {
    'has-cve': 0,
    'no-cve': 0,
    'not-checked': 0,
    unknown: 0,
  };
  for (const delta of dependencyDeltas(summary)) {
    for (const key of Object.keys(counts) as DependencyCveStatus[]) {
      counts[key] += delta.cve_counts?.[key] ?? 0;
    }
  }
  return counts;
}

export function repoKeyFromPath(path: string): string {
  const name = path.split('/').filter(Boolean).at(-1) ?? path;
  return name.trim().replace(/[^A-Za-z0-9_.-]+/g, '-').replace(/^-+|-+$/g, '') || 'repo';
}

export function repositoryDisplayName(repo: Pick<RepositorySummary, 'repo' | 'path'>): string {
  return repo.path.split('/').filter(Boolean).at(-1)?.trim() || repo.repo;
}

export function repoDisplayName(summary: DashboardSummary, repoKey: string): string {
  const normalizedKey = repoKeyFromPath(repoKey);
  const match = summary.repos.find((repo) => (
    repo.repo === repoKey ||
    repo.repo === normalizedKey ||
    repo.path === repoKey ||
    repoKeyFromPath(repo.path) === normalizedKey
  ));
  return match ? repositoryDisplayName(match) : repoKey;
}

export function targetValue(target: TargetSelection): string {
  return target.mode === 'all-repos' ? 'all-repos' : `repo:${target.repo.path}`;
}

export function targetLabel(target: TargetSelection): string {
  return target.mode === 'all-repos' ? 'All repos' : target.repo.name;
}

export function mergeProjectRepos(discovered: ProjectRepo[], custom: ProjectRepo[], scanned: RepositorySummary[]): ProjectRepo[] {
  const byPath = new Map<string, ProjectRepo>();
  for (const repo of [...discovered, ...custom]) {
    byPath.set(repo.path, repo);
  }
  for (const repo of scanned) {
    byPath.set(repo.path, {name: repo.path.split('/').filter(Boolean).at(-1) ?? repo.repo, path: repo.path});
  }
  return [...byPath.values()].sort((a, b) => a.name.localeCompare(b.name, undefined, {sensitivity: 'base'}));
}

function mergedSuppressionCounts(repos: RepositorySummary[], fallback?: SuppressedCounts): SuppressedCounts | undefined {
  if (!repos.length) return fallback;
  const reasons = new Map<string, SuppressionReason>();
  let cases = 0;
  let findings = 0;
  for (const repo of repos) {
    const counts = repo.suppressed_counts;
    cases += counts?.cases ?? 0;
    findings += counts?.findings ?? 0;
    for (const item of counts?.reasons ?? repo.suppression_reasons ?? []) {
      const key = `${item.reason}:${item.decision_status}:${item.vex_status}`;
      const current = reasons.get(key) ?? {
        reason: item.reason,
        decision_status: item.decision_status,
        vex_status: item.vex_status,
        cases: 0,
        findings: 0,
      };
      current.cases += item.cases;
      current.findings += item.findings;
      reasons.set(key, current);
    }
  }
  return {
    cases,
    findings,
    reasons: [...reasons.values()],
  };
}

export function filterSummaryByTarget(summary: DashboardSummary, target: TargetSelection): DashboardSummary {
  if (target.mode === 'all-repos') return summary;
  const repoKey = repoKeyFromPath(target.repo.path);
  const repos = summary.repos.filter((repo) => repo.path === target.repo.path || repo.repo === repoKey);
  const repoNames = new Set(repos.map((repo) => repo.repo));
  repoNames.add(repoKey);
  const targetKeys = summary.honey_keys?.filter((key) => key.repo_id === target.repo.path || key.project_id === repoKey) ?? [];
  const targetProjectIds = new Set([repoKey, ...targetKeys.map((key) => key.project_id)]);
  const findings = summary.findings.filter((finding) => repoNames.has(finding.repo_name));
  const activeFindings = summary.active_findings?.filter((finding) => repoNames.has(finding.repo_name));
  const suppressedFindings = summary.suppressed_findings?.filter((finding) => repoNames.has(finding.repo_name));
  const cases = summary.cases?.filter((item) => {
    const caseRepo = item.repo_name ?? item.repo;
    return !caseRepo || repoNames.has(caseRepo) || targetProjectIds.has(String(caseRepo));
  });
  const activeCases = summary.active_cases?.filter((item) => {
    const caseRepo = item.repo_name ?? item.repo;
    return !caseRepo || repoNames.has(caseRepo) || targetProjectIds.has(String(caseRepo));
  });
  const suppressedCases = summary.suppressed_cases?.filter((item) => {
    const caseRepo = item.repo_name ?? item.repo;
    return !caseRepo || repoNames.has(caseRepo) || targetProjectIds.has(String(caseRepo));
  });
  const suppressedCounts = mergedSuppressionCounts(repos, summary.suppressed_counts);
  return {
    repos,
    history: summary.history.filter((item) => repoNames.has(item.repo_name)),
    findings,
    active_findings: activeFindings,
    suppressed_findings: suppressedFindings,
    cases,
    active_cases: activeCases,
    suppressed_cases: suppressedCases,
    case_decisions: summary.case_decisions?.filter((decision) => repoNames.has(decision.repo_name) || targetProjectIds.has(decision.repo_name)),
    suppressed_counts: suppressedCounts,
    suppression_reasons: suppressedCounts?.reasons,
    honey_keys: targetKeys,
    honey_key_events: summary.honey_key_events?.filter((event) => targetProjectIds.has(event.project_id)),
    project_statuses: summary.project_statuses?.filter((status) => targetProjectIds.has(status.project_id)),
    honey_event_retention_days: summary.honey_event_retention_days,
    scanner_catalog: summary.scanner_catalog,
    tool_catalog: summary.tool_catalog,
    security_packs: summary.security_packs,
    scan_profiles: summary.scan_profiles,
    managed_tools: summary.managed_tools,
    agent_lab_proposals: summary.agent_lab_proposals?.filter((proposal) => {
      const proposalRepoName = String(proposal.repo_name ?? '');
      const proposalRepoPath = String(proposal.repo_path ?? '');
      return repoNames.has(proposalRepoName) || proposalRepoPath === target.repo.path || repoKeyFromPath(proposalRepoPath) === repoKey;
    }),
    case_resolution_runs: summary.case_resolution_runs?.filter((run) => repoNames.has(run.repo_name) || repoNames.has(run.repo)),
    recovery_playbooks: summary.recovery_playbooks?.filter((playbook) => playbook.items.some((item) => repoNames.has(item.repo))),
    completeness: summary.completeness,
    scan_completeness: summary.scan_completeness,
    environment: summary.environment,
    // Machine-wide, not repo-scoped — carry it through every target so the
    // recovery banner survives a repo filter.
    history_recovery: summary.history_recovery,
  };
}
