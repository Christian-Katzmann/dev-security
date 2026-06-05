from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import json
import logging
import re
import secrets
import sqlite3

from . import lifecycle
from .model import Finding, SecurityCase, redact_text, sanitize_json
from .decisions import (
    CASE_DECISION_STATUSES,
    GATED_SUPPRESSION_SEVERITIES,
    SUPPRESSING_DECISION_STATUSES,
    VEX_STATUSES,
    assemble_suppression,
    dependency_fields_from_case,
    normalize_case_decision,
    normalize_vex_status,
)


class HumanConfirmationRequired(ValueError):
    """Raised when a high/critical case suppression is attempted without an
    explicit human-authorization signal.

    Subclasses ``ValueError`` so existing callers that already treat a refused
    decision as a ``ValueError`` keep failing safe; callers that want to surface
    the distinct *pending* outcome (the case-resolution apply path) catch this
    type first and divert the item to ``requires_human_confirmation`` instead of
    rejecting it.
    """
from .asset_graph import (
    CONFIDENCE_LEVELS as ASSET_CONFIDENCE_LEVELS,
    EDGE_TYPES as ASSET_EDGE_TYPES,
    NODE_TYPES as ASSET_NODE_TYPES,
    AssetEdge,
    derive_asset_nodes,
)
from .crown_jewels import mark_crown_jewels
from .honey_keys import HONEY_KEY_PREFIX, utc_now
from .platform_posture import platform_posture_snapshot_fingerprint
from .managed_tools import new_ownership_id, upsert_manifest_record, utc_now as managed_utc_now
from .sbom import SBOMComponent, component_fingerprint
from .silent_upgrades import annotate_dependency_changes
from .vex import build_vex_document, parse_vex_document


logger = logging.getLogger("security_observatory.storage")


def _decode_cases(cases_json: Any) -> list[Any]:
    """Decode a scan's ``cases_json`` column, degrading on a corrupt row.

    A hand-edited, truncated, or otherwise malformed ``cases_json`` value must
    never crash the dashboard/MCP read path (S-023). On a JSON decode failure —
    or a value that decodes to something other than a list — we warn and return
    an empty list so the rest of the payload still renders. Callers that only
    want dict cases keep filtering with ``isinstance(item, dict)``; this helper
    is the single source of truth for "read the cases column safely".
    """
    try:
        cases = json.loads(cases_json)
    except (TypeError, json.JSONDecodeError) as exc:
        logger.warning("cases_json could not be decoded, skipping row: %s", exc)
        return []
    if not isinstance(cases, list):
        logger.warning(
            "cases_json decoded to %s, expected a list; skipping row",
            type(cases).__name__,
        )
        return []
    return cases


# Monotonic schema version tracked via SQLite's ``PRAGMA user_version`` (S-026).
# It is the single source of truth for whether a destructive, run-once migration
# still needs to apply, replacing the old fragile "parse sqlite_master SQL for a
# substring" sentinel. Bump this whenever you add a numbered migration step to
# ``_run_schema_migrations`` below, and document the step in that ledger.
#
# Migration ledger (see ``_run_schema_migrations``):
#   1 -> widen the case-resolution and case-decision status CHECK constraints
#        (adds requires_confirmation / requires_human_confirmation / in_progress).
#
# Additive ``alter table ... add column`` migrations are NOT versioned here: they
# live in ``_ensure_columns``, which diffs columns and is naturally idempotent and
# version-independent. Only destructive table rebuilds, which must run exactly
# once, are gated on ``user_version``.
SCHEMA_USER_VERSION = 1


def _sql_in_check(column: str, values: Any) -> str:
    """Render a SQLite ``check(col in (...))`` clause from a Python value set.

    The single point where a canonical status set becomes a CHECK constraint, so
    the SQL and the Python source of truth cannot drift. Values are sorted for a
    deterministic DDL string (CHECK membership is order-independent, but a stable
    rendering keeps ``sqlite_master.sql`` reproducible across runs).
    """
    rendered = ", ".join(f"'{value}'" for value in sorted(values))
    return f"check({column} in ({rendered}))"


#: ``case_decisions.status`` CHECK clause, derived from the canonical decision
#: vocabulary so the schema, the migrated-table mirror, and
#: ``lifecycle.DECISION_STATUSES`` are physically the same set. Substituted into
#: ``SCHEMA`` (below) and into ``_migrate_case_decision_status_constraint``.
CASE_DECISION_STATUS_CHECK = _sql_in_check("status", lifecycle.DECISION_STATUSES)


#: Asset-graph CHECK clauses, GENERATED from the canonical vocabularies in
#: ``asset_graph`` so the schema and that source-of-truth cannot drift. The same
#: confidence clause guards both ``asset_nodes`` and ``asset_edges`` (a node's
#: confidence is how sure we are the asset is real; an edge's is how sure we are
#: the relationship holds). Substituted into ``SCHEMA`` below and guarded by a
#: drift test in ``tests/test_asset_graph.py``.
ASSET_NODE_TYPE_CHECK = _sql_in_check("node_type", ASSET_NODE_TYPES)
ASSET_EDGE_TYPE_CHECK = _sql_in_check("edge_type", ASSET_EDGE_TYPES)
ASSET_CONFIDENCE_CHECK = _sql_in_check("confidence", ASSET_CONFIDENCE_LEVELS)


SCHEMA = """
create table if not exists scans (
  id text primary key,
  repo_name text not null,
  repo_path text not null,
  started_at text not null,
  finished_at text,
  profile text not null,
  health_score integer not null,
  status text not null,
  scanner_status_json text not null,
  cases_json text not null default '[]',
  report_path text
);

create table if not exists findings (
  id integer primary key autoincrement,
  scan_id text not null,
  repo_name text not null,
  scanner text not null,
  severity text not null,
  category text not null,
  title text not null,
  file text,
  line integer,
  remediation text,
  vulnerability_id text,
  package_name text,
  package_version text,
  package_ecosystem text,
  package_url text,
  fixed_version text,
  component_fingerprint text,
  component_package_key text,
  component_match_confidence text,
  component_match_reason text,
  old_version text,
  new_version text,
  behavior_category text,
  evidence_summary text,
  before_behavior text,
  after_behavior text,
  ioc_pack_id text,
  ioc_source text,
  ioc_advisory_url text,
  ioc_confidence text,
  ioc_match_type text,
  ioc_indicator text,
  install_recency_confidence text,
  last_install_signal_at text,
  install_recency_evidence text,
  rotation_surfaces_json text,
  fingerprint text not null,
  created_at text not null,
  foreign key(scan_id) references scans(id)
);

create index if not exists idx_scans_repo_started on scans(repo_name, started_at desc);
create index if not exists idx_findings_scan on findings(scan_id);
create index if not exists idx_findings_fingerprint on findings(fingerprint);

create table if not exists sbom_components (
  id integer primary key autoincrement,
  scan_id text not null,
  repo_name text not null,
  source_format text not null,
  source_file text,
  bom_ref text,
  name text,
  version text,
  ecosystem text,
  component_type text,
  package_url text,
  license text,
  supplier text,
  source_path text,
  component_fingerprint text not null,
  created_at text not null,
  foreign key(scan_id) references scans(id)
);

create index if not exists idx_sbom_components_scan on sbom_components(scan_id);
create index if not exists idx_sbom_components_repo on sbom_components(repo_name, scan_id);
create index if not exists idx_sbom_components_fingerprint on sbom_components(component_fingerprint);

create table if not exists dependency_manifest_entries (
  id integer primary key autoincrement,
  scan_id text not null,
  repo_name text not null,
  manifest_path text not null,
  ecosystem text not null,
  name text not null,
  declaration text not null,
  normalized_declaration text not null,
  scope text not null,
  manifest_fingerprint text not null,
  created_at text not null,
  foreign key(scan_id) references scans(id)
);

create index if not exists idx_dependency_manifest_scan on dependency_manifest_entries(scan_id);
create index if not exists idx_dependency_manifest_repo on dependency_manifest_entries(repo_name, scan_id);
create index if not exists idx_dependency_manifest_package on dependency_manifest_entries(ecosystem, name);

create table if not exists ioc_packs (
  pack_id text primary key,
  source text not null,
  published_at text,
  advisory_url text,
  confidence text not null,
  source_file text,
  raw_json text not null,
  imported_at text not null
);

create table if not exists ioc_indicators (
  id integer primary key autoincrement,
  pack_id text not null,
  ecosystem text not null,
  name text,
  versions_json text not null,
  namespace_prefix text,
  domain text,
  confidence text,
  source_file text,
  source_line integer,
  indicator_json text not null,
  created_at text not null,
  foreign key(pack_id) references ioc_packs(pack_id) on delete cascade
);

create index if not exists idx_ioc_indicators_pack on ioc_indicators(pack_id);
create index if not exists idx_ioc_indicators_package on ioc_indicators(ecosystem, name);

create table if not exists dependency_trust_enrichments (
  id integer primary key autoincrement,
  scan_id text not null,
  repo_name text not null,
  component_fingerprint text,
  component_package_key text,
  package_name text,
  package_version text,
  package_ecosystem text,
  package_url text,
  source_repo text,
  source_repo_url text,
  source_repo_confidence text not null,
  source_repo_reason text not null,
  scorecard_score real,
  scorecard_status text not null,
  criticality_score real,
  criticality_status text not null,
  checked_at text,
  freshness text not null,
  status text not null,
  cache_key text,
  error text,
  created_at text not null,
  foreign key(scan_id) references scans(id)
);

create index if not exists idx_dependency_trust_scan on dependency_trust_enrichments(scan_id);
create index if not exists idx_dependency_trust_repo on dependency_trust_enrichments(repo_name, scan_id);
create index if not exists idx_dependency_trust_component on dependency_trust_enrichments(component_fingerprint);

create table if not exists platform_posture_snapshots (
  id integer primary key autoincrement,
  scan_id text not null,
  repo_name text not null,
  scanner text not null,
  source text not null,
  target text not null,
  status text not null,
  summary_json text not null,
  snapshot_json text not null,
  snapshot_fingerprint text not null,
  created_at text not null,
  foreign key(scan_id) references scans(id)
);

create index if not exists idx_platform_posture_scan on platform_posture_snapshots(scan_id);
create index if not exists idx_platform_posture_repo on platform_posture_snapshots(repo_name, scan_id);

create table if not exists case_decisions (
  case_id text primary key,
  repo_name text not null,
  -- Canonical decision vocabulary lives in lifecycle.DECISION_STATUSES; the
  -- CHECK clause below is GENERATED from it (see CASE_DECISION_STATUS_CHECK), so
  -- the SQL and the canonical set cannot silently diverge. 'in_progress' (S-035)
  -- is a non-suppressing intermediate state; older DBs are widened by
  -- _migrate_case_decision_status_constraint (preserve rows, no rebuild of data).
  status text not null __CASE_DECISION_STATUS_CHECK__,
  note text,
  vex_status text,
  vex_justification text,
  vulnerability_id text,
  package_name text,
  package_version text,
  package_ecosystem text,
  package_url text,
  component_package_key text,
  fixed_version text,
  created_at text not null,
  updated_at text not null
);

create index if not exists idx_case_decisions_repo on case_decisions(repo_name, status);

create table if not exists case_resolution_runs (
  id text primary key,
  repo_name text not null,
  scan_id text,
  action text not null,
  scope text not null,
  source text not null,
  imported_at text not null,
  applied_at text,
  status text not null check(status in ('previewed', 'applied', 'partially_applied', 'rejected', 'requires_confirmation')),
  summary_json text not null default '{}'
);

create table if not exists case_resolution_items (
  id text primary key,
  run_id text not null,
  case_id text not null,
  repo_name text not null,
  scan_id text,
  ai_disposition text not null,
  mapped_decision text,
  confidence text not null,
  reason text not null,
  evidence_json text not null default '[]',
  recommended_next_step text,
  applied_decision_json text,
  status text not null check(status in ('pending', 'applied', 'left_open', 'rejected', 'requires_human_confirmation')),
  warning text,
  created_at text not null,
  foreign key(run_id) references case_resolution_runs(id)
);

create index if not exists idx_case_resolution_runs_repo on case_resolution_runs(repo_name, imported_at desc);
create index if not exists idx_case_resolution_items_run on case_resolution_items(run_id);
create index if not exists idx_case_resolution_items_case on case_resolution_items(case_id);

create table if not exists observatory_settings (
  key text primary key,
  value text not null
);

create table if not exists managed_tool_installations (
  ownership_id text primary key,
  tool_id text not null,
  version text not null,
  install_root text not null,
  binary_path text not null,
  source text not null,
  checksum text,
  installer_version text not null,
  installed_at text not null,
  active integer not null default 1,
  version_check_status text not null default 'not_checked',
  version_check_output text,
  version_checked_at text,
  metadata_json text not null default '{}'
);

create index if not exists idx_managed_tool_installations_tool on managed_tool_installations(tool_id, active);

create table if not exists agent_lab_proposals (
  id text primary key,
  external_proposal_id text not null,
  repo_name text not null,
  repo_path text,
  context_id text not null,
  context_hash text,
  adapter_id text not null,
  agent_label text not null,
  agent_created_at text,
  summary text not null,
  recommended_tools_json text not null,
  recommended_packs_json text not null,
  requested_permissions_json text not null,
  requested_execution_json text not null,
  expected_evidence_gaps_json text not null,
  blocked_requests_json text not null,
  notes text,
  validation_status text not null check(validation_status in ('valid')),
  validation_errors_json text not null,
  approval_state text not null check(approval_state in ('pending', 'approved', 'denied')),
  approval_note text,
  decided_by text,
  imported_at text not null,
  updated_at text not null,
  approved_at text,
  denied_at text,
  raw_proposal_json text not null,
  final_execution_plan_json text not null
);

create index if not exists idx_agent_lab_proposals_repo on agent_lab_proposals(repo_name, imported_at desc);
create index if not exists idx_agent_lab_proposals_state on agent_lab_proposals(approval_state, updated_at desc);

create table if not exists fix_proposals (
  id text primary key,
  repo_name text not null,
  repo_path text,
  case_id text,
  base_branch text not null,
  head_branch text not null,
  title text not null,
  diff text not null,
  diff_sha256 text not null,
  fix_class text not null,
  auto_merge_eligible integer not null default 0,
  classification_json text not null default '{}',
  source text not null,
  status text not null check(status in ('proposed', 'reviewed', 'auto_merge_authorized', 'requires_human')) default 'proposed',
  clean_room_status text not null check(clean_room_status in ('pending', 'approved', 'rejected')) default 'pending',
  clean_room_reviewer text,
  clean_room_checked_invariants_json text not null default '[]',
  clean_room_notes text,
  clean_room_diff_sha256 text,
  clean_room_reviewed_at text,
  landing_outcome text,
  landing_reasons_json text not null default '[]',
  landing_decided_at text,
  created_at text not null,
  updated_at text not null
);

create index if not exists idx_fix_proposals_repo on fix_proposals(repo_name, created_at desc);
create index if not exists idx_fix_proposals_status on fix_proposals(status, updated_at desc);

create table if not exists honey_keys (
  id text primary key,
  project_id text not null,
  repo_id text,
  name text not null,
  token_prefix text not null,
  token_hash text not null,
  status text not null check(status in ('active', 'triggered', 'archived')),
  placement_path text,
  note text,
  created_at text not null,
  created_by text,
  last_triggered_at text,
  trigger_count integer not null default 0,
  archived_at text
);

create table if not exists honey_key_events (
  id text primary key,
  honey_key_id text not null,
  project_id text not null,
  repo_id text,
  triggered_at text not null,
  ip_address text,
  user_agent text,
  method text not null,
  path text not null,
  headers_json text not null,
  body_summary text,
  confidence real not null,
  source_type text not null check(source_type in ('api_call', 'url_open', 'unknown')),
  reason text not null,
  approximate_geo text,
  created_at text not null,
  foreign key(honey_key_id) references honey_keys(id)
);

create table if not exists security_project_status (
  project_id text primary key,
  status text not null check(status in ('green', 'yellow', 'red')),
  reason text not null,
  last_event_at text
);

create table if not exists honey_incidents (
  event_id text primary key,
  investigating integer not null default 0,
  secrets_rotated integer not null default 0,
  logs_reviewed integer not null default 0,
  archived_reset integer not null default 0,
  accepted_risk_note text,
  closed_at text,
  created_at text not null,
  updated_at text not null,
  foreign key(event_id) references honey_key_events(id)
);

create index if not exists idx_honey_keys_project on honey_keys(project_id, status);
create unique index if not exists idx_honey_keys_token_hash on honey_keys(token_hash);
create index if not exists idx_honey_events_project on honey_key_events(project_id, triggered_at desc);
create index if not exists idx_honey_events_key on honey_key_events(honey_key_id, triggered_at desc);

-- Asset graph (Honeygraph campaign): the nodes worth protecting and how they
-- connect. Purely additive — created via `if not exists` on every open, so an
-- existing history DB gains both tables on next launch with no data migration.
-- The CHECK enums are substituted from asset_graph's canonical vocabularies.
create table if not exists asset_nodes (
  id integer primary key autoincrement,
  scan_id text not null,
  repo_name text not null,
  node_type text not null __ASSET_NODE_TYPE_CHECK__,
  identity_key text not null,
  label text not null,
  is_crown_jewel integer not null default 0,
  confidence text not null __ASSET_CONFIDENCE_CHECK__,
  created_at text not null,
  foreign key(scan_id) references scans(id)
);

create index if not exists idx_asset_nodes_scan on asset_nodes(scan_id);
create index if not exists idx_asset_nodes_repo on asset_nodes(repo_name, scan_id);
-- A node's identity within a scan is (node_type, identity_key); the unique index
-- makes that the physical contract so derivation can never double-insert one.
create unique index if not exists idx_asset_nodes_identity on asset_nodes(scan_id, node_type, identity_key);

create table if not exists asset_edges (
  id integer primary key autoincrement,
  scan_id text not null,
  repo_name text not null,
  src_node_id integer not null,
  dst_node_id integer not null,
  edge_type text not null __ASSET_EDGE_TYPE_CHECK__,
  confidence text not null __ASSET_CONFIDENCE_CHECK__,
  reason text not null,
  created_at text not null,
  foreign key(scan_id) references scans(id),
  foreign key(src_node_id) references asset_nodes(id),
  foreign key(dst_node_id) references asset_nodes(id)
);

create index if not exists idx_asset_edges_scan on asset_edges(scan_id);
create index if not exists idx_asset_edges_repo on asset_edges(repo_name, scan_id);
create index if not exists idx_asset_edges_src on asset_edges(src_node_id);
create index if not exists idx_asset_edges_dst on asset_edges(dst_node_id);
"""

# Bind the case-decision CHECK to the canonical set at import time. A bare literal
# here would let the SQL drift from lifecycle.DECISION_STATUSES; the substitution
# makes them the same source.
SCHEMA = SCHEMA.replace("__CASE_DECISION_STATUS_CHECK__", CASE_DECISION_STATUS_CHECK)
SCHEMA = SCHEMA.replace("__ASSET_NODE_TYPE_CHECK__", ASSET_NODE_TYPE_CHECK)
SCHEMA = SCHEMA.replace("__ASSET_EDGE_TYPE_CHECK__", ASSET_EDGE_TYPE_CHECK)
SCHEMA = SCHEMA.replace("__ASSET_CONFIDENCE_CHECK__", ASSET_CONFIDENCE_CHECK)


class ObservatoryDB:
    # SQLite can leave sidecar files (rollback journal, write-ahead log) next to
    # the database. A stale one beside a corrupt DB would be replayed into the
    # fresh replacement and re-corrupt it, so we clear them on quarantine.
    _SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Corruption-recovery signal. Stays False/None on the happy path; set
        # when a corrupt history file was quarantined and replaced with a fresh
        # DB, so callers (dashboard, MCP) can surface a calm "history was
        # corrupted and quarantined; previous data preserved at <path>" message
        # instead of a raw traceback. The corrupt file is preserved, never
        # deleted — see .adx/risks.json (local-security-data).
        self.recovered_from_corruption = False
        self.quarantined_path: Path | None = None
        try:
            self._connect_and_initialize()
        except sqlite3.DatabaseError as error:
            if isinstance(error, sqlite3.OperationalError):
                # Transient / environmental: database locked by another writer,
                # unable to open, disk I/O. The bytes are NOT known to be bad —
                # quarantining here would destroy a healthy DB a concurrent
                # process is mid-write on. Surface it untouched.
                raise
            # Genuine corruption (SQLITE_NOTADB / SQLITE_CORRUPT: "file is not a
            # database", "disk image is malformed") from a disk-full mid-write,
            # an interrupted scan, or stray bytes. Preserve the file, then open a
            # fresh, usable DB so the tool stays trustworthy instead of 500-ing.
            self._quarantine_corrupt_db()
            self._connect_and_initialize()

    def _connect_and_initialize(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            # A brand-new database (no tables yet) already matches the latest
            # SCHEMA, so it is stamped straight to SCHEMA_USER_VERSION and skips
            # every back-fill migration. We detect "fresh" before applying SCHEMA,
            # since the `create table if not exists` below would otherwise mask it.
            # Any pre-existing table means a real database that may still need a
            # versioned migration — including partial fixtures without a `scans`
            # table — so it is never treated as fresh.
            fresh = (
                conn.execute(
                    "select 1 from sqlite_master where type = 'table' limit 1"
                ).fetchone()
                is None
            )
            conn.executescript(SCHEMA)
            self.conn = conn
            self._ensure_columns()
            self._run_schema_migrations(fresh=fresh)
            conn.commit()
        except BaseException:
            # Never leak the half-open handle; the caller decides whether the
            # failure is recoverable corruption worth quarantining.
            conn.close()
            raise

    def _quarantine_corrupt_db(self) -> None:
        """Preserve a corrupt history DB by moving it aside, never deleting it.

        Renames the database to ``<name>.corrupt-<UTC timestamp>`` and clears any
        stale SQLite sidecar files so the fresh replacement starts clean. Records
        ``quarantined_path`` and sets ``recovered_from_corruption`` so callers can
        explain what happened.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        quarantine = self.db_path.with_name(f"{self.db_path.name}.corrupt-{timestamp}")
        # Two corruptions within the same second must not overwrite each other.
        collision = 1
        while quarantine.exists():
            quarantine = self.db_path.with_name(
                f"{self.db_path.name}.corrupt-{timestamp}-{collision}"
            )
            collision += 1
        self.db_path.replace(quarantine)
        for suffix in self._SIDECAR_SUFFIXES:
            self.db_path.with_name(f"{self.db_path.name}{suffix}").unlink(missing_ok=True)
        self.recovered_from_corruption = True
        self.quarantined_path = quarantine

    def close(self) -> None:
        self.conn.close()

    def _ensure_columns(self) -> None:
        columns = {row["name"] for row in self.conn.execute("pragma table_info(scans)").fetchall()}
        if "cases_json" not in columns:
            self.conn.execute("alter table scans add column cases_json text not null default '[]'")
        honey_columns = {row["name"] for row in self.conn.execute("pragma table_info(honey_keys)").fetchall()}
        if honey_columns and "note" not in honey_columns:
            self.conn.execute("alter table honey_keys add column note text")
        finding_columns = {row["name"] for row in self.conn.execute("pragma table_info(findings)").fetchall()}
        for column in (
            "vulnerability_id",
            "package_name",
            "package_version",
            "package_ecosystem",
            "package_url",
            "fixed_version",
            "component_fingerprint",
            "component_package_key",
            "component_match_confidence",
            "component_match_reason",
            "old_version",
            "new_version",
            "behavior_category",
            "evidence_summary",
            "before_behavior",
            "after_behavior",
            "ioc_pack_id",
            "ioc_source",
            "ioc_advisory_url",
            "ioc_confidence",
            "ioc_match_type",
            "ioc_indicator",
            "install_recency_confidence",
            "last_install_signal_at",
            "install_recency_evidence",
            "rotation_surfaces_json",
        ):
            if finding_columns and column not in finding_columns:
                self.conn.execute(f"alter table findings add column {column} text")
        decision_columns = {row["name"] for row in self.conn.execute("pragma table_info(case_decisions)").fetchall()}
        for column in (
            "vex_status",
            "vex_justification",
            "vulnerability_id",
            "package_name",
            "package_version",
            "package_ecosystem",
            "package_url",
            "component_package_key",
            "fixed_version",
        ):
            if decision_columns and column not in decision_columns:
                self.conn.execute(f"alter table case_decisions add column {column} text")
        managed_columns = {row["name"] for row in self.conn.execute("pragma table_info(managed_tool_installations)").fetchall()}
        for column, definition in (
            ("version_check_status", "text not null default 'not_checked'"),
            ("version_check_output", "text"),
            ("version_checked_at", "text"),
            ("metadata_json", "text not null default '{}'"),
        ):
            if managed_columns and column not in managed_columns:
                self.conn.execute(f"alter table managed_tool_installations add column {column} {definition}")

    def _run_schema_migrations(self, *, fresh: bool) -> None:
        """Apply destructive, run-once schema migrations gated on PRAGMA user_version.

        ``user_version`` (0 on every pre-S-026 database) is the single migration
        counter. Each numbered step runs only when the stored version is below it,
        then the version is bumped so the step never re-runs — this replaces the
        old ``select sql from sqlite_master`` substring sentinel, which inferred
        "needs migration" by string-matching the live CREATE TABLE SQL.

        Migration ledger — apply strictly in order:
          1 -> widen the case-resolution and case-decision status CHECK
               constraints (requires_confirmation / requires_human_confirmation /
               in_progress).

        Additive column adds stay in ``_ensure_columns`` (self-idempotent,
        version-independent). A freshly created database already matches the
        latest SCHEMA, so it is stamped to SCHEMA_USER_VERSION without rebuilding.
        """
        if fresh:
            self.conn.execute(f"pragma user_version = {SCHEMA_USER_VERSION}")
            return
        version = self.conn.execute("pragma user_version").fetchone()[0]
        if version >= SCHEMA_USER_VERSION:
            return
        if version < 1:
            self._migrate_resolution_status_constraints()
            self._migrate_case_decision_status_constraint()
        self.conn.execute(f"pragma user_version = {SCHEMA_USER_VERSION}")

    def _migrate_resolution_status_constraints(self) -> None:
        """Widen the case-resolution status CHECK constraints (migration step 1).

        The high/critical suppression gate adds a ``requires_confirmation`` run
        status and a ``requires_human_confirmation`` item status. SQLite can't
        ALTER a CHECK constraint in place, so we rebuild each table (preserving
        every audit row). Whether this rebuild is needed is decided by
        ``user_version`` in ``_run_schema_migrations`` — fresh and already-migrated
        databases never reach this method — so it rebuilds unconditionally here.
        """
        rebuilds = (
            (
                "case_resolution_runs",
                """
                create table case_resolution_runs__migrate (
                  id text primary key,
                  repo_name text not null,
                  scan_id text,
                  action text not null,
                  scope text not null,
                  source text not null,
                  imported_at text not null,
                  applied_at text,
                  status text not null check(status in ('previewed', 'applied', 'partially_applied', 'rejected', 'requires_confirmation')),
                  summary_json text not null default '{}'
                )
                """,
            ),
            (
                "case_resolution_items",
                """
                create table case_resolution_items__migrate (
                  id text primary key,
                  run_id text not null,
                  case_id text not null,
                  repo_name text not null,
                  scan_id text,
                  ai_disposition text not null,
                  mapped_decision text,
                  confidence text not null,
                  reason text not null,
                  evidence_json text not null default '[]',
                  recommended_next_step text,
                  applied_decision_json text,
                  status text not null check(status in ('pending', 'applied', 'left_open', 'rejected', 'requires_human_confirmation')),
                  warning text,
                  created_at text not null,
                  foreign key(run_id) references case_resolution_runs(id)
                )
                """,
            ),
        )
        for table, create_sql in rebuilds:
            row = self.conn.execute(
                "select sql from sqlite_master where type = 'table' and name = ?",
                (table,),
            ).fetchone()
            if not row or not row["sql"]:
                continue
            self.conn.execute(create_sql)
            self.conn.execute(f"insert into {table}__migrate select * from {table}")
            self.conn.execute(f"drop table {table}")
            self.conn.execute(f"alter table {table}__migrate rename to {table}")
        # Recreate the indexes the rebuild may have dropped (no-op if present).
        self.conn.execute("create index if not exists idx_case_resolution_runs_repo on case_resolution_runs(repo_name, imported_at desc)")
        self.conn.execute("create index if not exists idx_case_resolution_items_run on case_resolution_items(run_id)")
        self.conn.execute("create index if not exists idx_case_resolution_items_case on case_resolution_items(case_id)")

    def _migrate_case_decision_status_constraint(self) -> None:
        """Widen the ``case_decisions.status`` CHECK constraint (migration step 1).

        S-035 added the non-suppressing ``in_progress`` lifecycle state to the
        canonical decision vocabulary (``lifecycle.DECISION_STATUSES``). SQLite
        cannot ALTER a CHECK constraint in place, so we rebuild the table,
        preserving every recorded decision row. This is a widen, never a narrow:
        old-shape rows survive intact. Whether the rebuild is needed is decided by
        ``user_version`` in ``_run_schema_migrations`` (fresh and already-migrated
        databases never reach this method), so it rebuilds unconditionally here.
        """
        row = self.conn.execute(
            "select sql from sqlite_master where type = 'table' and name = 'case_decisions'"
        ).fetchone()
        if not row or not row["sql"]:
            return
        # Carry every column across by name (the table may have gained columns
        # via ALTER on very old databases, so position-based `select *` is
        # unsafe — list the canonical columns explicitly).
        columns = [r["name"] for r in self.conn.execute("pragma table_info(case_decisions)").fetchall()]
        col_list = ", ".join(columns)
        self.conn.execute(
            f"""
            create table case_decisions__migrate (
              case_id text primary key,
              repo_name text not null,
              status text not null {CASE_DECISION_STATUS_CHECK},
              note text,
              vex_status text,
              vex_justification text,
              vulnerability_id text,
              package_name text,
              package_version text,
              package_ecosystem text,
              package_url text,
              component_package_key text,
              fixed_version text,
              created_at text not null,
              updated_at text not null
            )
            """
        )
        self.conn.execute(
            f"insert into case_decisions__migrate ({col_list}) select {col_list} from case_decisions"
        )
        self.conn.execute("drop table case_decisions")
        self.conn.execute("alter table case_decisions__migrate rename to case_decisions")
        self.conn.execute("create index if not exists idx_case_decisions_repo on case_decisions(repo_name, status)")

    def record_managed_tool(
        self,
        *,
        tool_id: str,
        version: str,
        install_root: str,
        binary_path: str,
        source: str,
        checksum: str | None = None,
        installer_version: str = "security-observatory",
        ownership_id: str | None = None,
        installed_at: str | None = None,
        active: bool = True,
        version_check_status: str = "not_checked",
        version_check_output: str | None = None,
        version_checked_at: str | None = None,
        metadata: dict[str, Any] | None = None,
        sync_manifest: bool = True,
    ) -> dict[str, Any]:
        ownership = ownership_id or new_ownership_id(tool_id)
        installed = installed_at or managed_utc_now()
        with self.conn:
            self.conn.execute(
                """
                insert into managed_tool_installations
                (ownership_id, tool_id, version, install_root, binary_path, source, checksum, installer_version,
                 installed_at, active, version_check_status, version_check_output, version_checked_at, metadata_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(ownership_id) do update set
                  tool_id = excluded.tool_id,
                  version = excluded.version,
                  install_root = excluded.install_root,
                  binary_path = excluded.binary_path,
                  source = excluded.source,
                  checksum = excluded.checksum,
                  installer_version = excluded.installer_version,
                  installed_at = excluded.installed_at,
                  active = excluded.active,
                  version_check_status = excluded.version_check_status,
                  version_check_output = excluded.version_check_output,
                  version_checked_at = excluded.version_checked_at,
                  metadata_json = excluded.metadata_json
                """,
                (
                    ownership,
                    tool_id,
                    version,
                    install_root,
                    binary_path,
                    source,
                    checksum,
                    installer_version,
                    installed,
                    1 if active else 0,
                    version_check_status,
                    version_check_output,
                    version_checked_at,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
        record = self.get_managed_tool(ownership)
        if record and sync_manifest:
            upsert_manifest_record(record)
        return record or {}

    def get_managed_tool(self, ownership_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "select * from managed_tool_installations where ownership_id = ?",
            (ownership_id,),
        ).fetchone()
        return _public_managed_tool(row) if row else None

    def list_managed_tools(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        where = "where active = 1" if active_only else ""
        rows = self.conn.execute(
            f"""
            select *
            from managed_tool_installations
            {where}
            order by tool_id asc, installed_at desc, ownership_id asc
            """
        ).fetchall()
        return [_public_managed_tool(row) for row in rows]

    def deactivate_managed_tool(self, ownership_id: str) -> dict[str, Any] | None:
        with self.conn:
            self.conn.execute(
                "update managed_tool_installations set active = 0 where ownership_id = ?",
                (ownership_id,),
            )
        record = self.get_managed_tool(ownership_id)
        if record:
            upsert_manifest_record(record)
        return record

    def save_agent_lab_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        now = _optional_text(proposal.get("updated_at")) or utc_now()
        with self.conn:
            self.conn.execute(
                """
                insert into agent_lab_proposals
                (id, external_proposal_id, repo_name, repo_path, context_id, context_hash, adapter_id, agent_label,
                 agent_created_at, summary, recommended_tools_json, recommended_packs_json, requested_permissions_json,
                 requested_execution_json, expected_evidence_gaps_json, blocked_requests_json, notes, validation_status,
                 validation_errors_json, approval_state, approval_note, decided_by, imported_at, updated_at, approved_at,
                 denied_at, raw_proposal_json, final_execution_plan_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  repo_name = excluded.repo_name,
                  repo_path = excluded.repo_path,
                  context_id = excluded.context_id,
                  context_hash = excluded.context_hash,
                  adapter_id = excluded.adapter_id,
                  agent_label = excluded.agent_label,
                  agent_created_at = excluded.agent_created_at,
                  summary = excluded.summary,
                  recommended_tools_json = excluded.recommended_tools_json,
                  recommended_packs_json = excluded.recommended_packs_json,
                  requested_permissions_json = excluded.requested_permissions_json,
                  requested_execution_json = excluded.requested_execution_json,
                  expected_evidence_gaps_json = excluded.expected_evidence_gaps_json,
                  blocked_requests_json = excluded.blocked_requests_json,
                  notes = excluded.notes,
                  validation_status = excluded.validation_status,
                  validation_errors_json = excluded.validation_errors_json,
                  approval_state = 'pending',
                  approval_note = null,
                  decided_by = null,
                  updated_at = excluded.updated_at,
                  approved_at = null,
                  denied_at = null,
                  raw_proposal_json = excluded.raw_proposal_json,
                  final_execution_plan_json = excluded.final_execution_plan_json
                """,
                (
                    str(proposal["id"]),
                    str(proposal["external_proposal_id"]),
                    str(proposal.get("repo_name") or "repository"),
                    _optional_text(proposal.get("repo_path")),
                    str(proposal["context_id"]),
                    _optional_text(proposal.get("context_hash")),
                    str(proposal["adapter_id"]),
                    str(proposal.get("agent_label") or proposal["adapter_id"]),
                    _optional_text(proposal.get("agent_created_at")),
                    redact_text(str(proposal.get("summary") or ""))[:1200],
                    _json(proposal.get("recommended_tools") or []),
                    _json(proposal.get("recommended_packs") or []),
                    _json(proposal.get("requested_permissions") or []),
                    _json(proposal.get("requested_execution") or []),
                    _json(proposal.get("expected_evidence_gaps") or []),
                    _json(proposal.get("blocked_requests") or []),
                    redact_text(str(proposal.get("notes") or "").strip())[:2000] or None,
                    "valid",
                    _json(proposal.get("validation_errors") or []),
                    "pending",
                    None,
                    None,
                    str(proposal.get("imported_at") or now),
                    now,
                    None,
                    None,
                    _json(proposal.get("raw_proposal") or {}),
                    _json(proposal.get("final_execution_plan") or {}),
                ),
            )
        saved = self.get_agent_lab_proposal(str(proposal["id"]))
        if not saved:
            raise ValueError("Agent Lab proposal could not be saved.")
        return saved

    def get_agent_lab_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "select * from agent_lab_proposals where id = ?",
            (proposal_id,),
        ).fetchone()
        return _public_agent_lab_proposal(row) if row else None

    def list_agent_lab_proposals(
        self,
        *,
        repo_name: str | None = None,
        approval_state: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if repo_name:
            conditions.append("repo_name = ?")
            params.append(repo_name)
        if approval_state:
            conditions.append("approval_state = ?")
            params.append(approval_state)
        where = f"where {' and '.join(conditions)}" if conditions else ""
        params.append(max(1, min(int(limit), 200)))
        rows = self.conn.execute(
            f"""
            select *
            from agent_lab_proposals
            {where}
            order by imported_at desc, id asc
            limit ?
            """,
            params,
        ).fetchall()
        return [_public_agent_lab_proposal(row) for row in rows]

    def set_agent_lab_proposal_approval(
        self,
        *,
        proposal_id: str,
        approval_state: str,
        note: str | None = None,
        decided_by: str | None = None,
    ) -> dict[str, Any]:
        clean_id = proposal_id.strip()
        clean_state = approval_state.strip().lower().replace("declined", "denied")
        if clean_state not in {"pending", "approved", "denied"}:
            raise ValueError("Unsupported Agent Lab approval state.")
        current = self.get_agent_lab_proposal(clean_id)
        if not current:
            raise ValueError("Agent Lab proposal not found.")
        now = utc_now()
        final_plan = dict(current.get("final_execution_plan") or {})
        final_plan["approval_state"] = clean_state
        for item in final_plan.get("items") or []:
            if isinstance(item, dict):
                item["status"] = {
                    "pending": "pending_approval",
                    "approved": "approved_pending_execution",
                    "denied": "denied",
                }[clean_state]
        with self.conn:
            self.conn.execute(
                """
                update agent_lab_proposals
                set approval_state = ?,
                    approval_note = ?,
                    decided_by = ?,
                    updated_at = ?,
                    approved_at = ?,
                    denied_at = ?,
                    final_execution_plan_json = ?
                where id = ?
                """,
                (
                    clean_state,
                    redact_text((note or "").strip())[:1000] or None,
                    redact_text((decided_by or "").strip())[:120] or None,
                    now,
                    now if clean_state == "approved" else None,
                    now if clean_state == "denied" else None,
                    _json(final_plan),
                    clean_id,
                ),
            )
        saved = self.get_agent_lab_proposal(clean_id)
        if not saved:
            raise ValueError("Agent Lab proposal not found.")
        return saved

    def update_agent_lab_execution_plan(
        self,
        *,
        proposal_id: str,
        final_execution_plan: dict[str, Any],
    ) -> dict[str, Any]:
        clean_id = proposal_id.strip()
        if not clean_id:
            raise ValueError("Agent Lab proposal id is required.")
        current = self.get_agent_lab_proposal(clean_id)
        if not current:
            raise ValueError("Agent Lab proposal not found.")
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                update agent_lab_proposals
                set final_execution_plan_json = ?,
                    updated_at = ?
                where id = ?
                """,
                (_json(final_execution_plan), now, clean_id),
            )
        saved = self.get_agent_lab_proposal(clean_id)
        if not saved:
            raise ValueError("Agent Lab proposal not found.")
        return saved

    def save_scan(
        self,
        *,
        scan_id: str,
        repo_name: str,
        repo_path: str,
        started_at: str,
        finished_at: str,
        profile: str,
        health_score: int,
        status: str,
        scanner_statuses: list[dict[str, Any]],
        findings: list[Finding],
        report_path: str,
        cases: list[SecurityCase] | list[dict[str, Any]] | None = None,
        sbom_components: list[SBOMComponent] | list[dict[str, Any]] | None = None,
        dependency_manifest_entries: list[Any] | None = None,
        dependency_trust_enrichments: list[Any] | None = None,
        platform_posture_snapshot: dict[str, Any] | None = None,
        iac_resources: list[Any] | None = None,
        crown_jewels: list[Any] | None = None,
    ) -> None:
        # Persist only redacted, whitelist-validated cases. A raw dict skips
        # SecurityCase.__post_init__ (token redaction + action_level/confidence
        # whitelist), so any dict input is rebuilt through the dataclass before
        # it can reach cases_json — the redaction contract can never be bypassed,
        # whether the caller passed a typed case or a dict.
        case_dicts = [
            (case if isinstance(case, SecurityCase) else SecurityCase(**case)).to_dict()
            for case in (cases or [])
        ]
        component_dicts = [
            component.to_dict() if isinstance(component, SBOMComponent) else dict(component)
            for component in (sbom_components or [])
        ]
        component_rows = [_sbom_component_row(component, scan_id, repo_name) for component in component_dicts]
        manifest_rows = [
            _dependency_manifest_row(item.to_dict() if hasattr(item, "to_dict") else dict(item), scan_id, repo_name)
            for item in (dependency_manifest_entries or [])
        ]
        trust_dicts = [
            item.to_dict() if hasattr(item, "to_dict") else dict(item)
            for item in (dependency_trust_enrichments or [])
        ]
        trust_rows = [_dependency_trust_row(item, scan_id, repo_name) for item in trust_dicts]
        platform_posture_row = (
            _platform_posture_snapshot_row(platform_posture_snapshot, scan_id, repo_name)
            if platform_posture_snapshot
            else None
        )
        # Asset-graph nodes are derived from artifacts this method already holds
        # (SBOM components + findings + recovered IaC resources), so a scan with
        # no SBOM and no IaC simply yields a smaller node set rather than
        # failing. Edges are wired separately via ``replace_asset_edges``; this
        # method persists only the nodes.
        asset_nodes = derive_asset_nodes(
            components=component_dicts, findings=findings, iac_resources=iac_resources
        )
        # Crown jewels are human-declared (never inferred): a scan-time pass flips
        # ``is_crown_jewel`` on the nodes whose identity a label matches. No labels
        # (absent ``.devsec/crown-jewels.json``) leaves every node unmarked.
        if crown_jewels:
            asset_nodes = mark_crown_jewels(asset_nodes, crown_jewels)
        component_created_at = utc_now()
        trust_created_at = utc_now()
        platform_created_at = utc_now()
        node_created_at = utc_now()
        with self.conn:
            self.conn.execute(
                """
                insert or replace into scans
                (id, repo_name, repo_path, started_at, finished_at, profile, health_score, status, scanner_status_json, cases_json, report_path)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_id,
                    repo_name,
                    repo_path,
                    started_at,
                    finished_at,
                    profile,
                    health_score,
                    status,
                    json.dumps(scanner_statuses, sort_keys=True),
                    json.dumps(case_dicts, sort_keys=True),
                    report_path,
                ),
            )
            self.conn.execute("delete from findings where scan_id = ?", (scan_id,))
            self.conn.executemany(
                """
                insert into findings
                (scan_id, repo_name, scanner, severity, category, title, file, line, remediation, vulnerability_id, package_name, package_version, package_ecosystem, package_url, fixed_version, component_fingerprint, component_package_key, component_match_confidence, component_match_reason, old_version, new_version, behavior_category, evidence_summary, before_behavior, after_behavior, ioc_pack_id, ioc_source, ioc_advisory_url, ioc_confidence, ioc_match_type, ioc_indicator, install_recency_confidence, last_install_signal_at, install_recency_evidence, rotation_surfaces_json, fingerprint, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        scan_id,
                        repo_name,
                        finding.scanner,
                        finding.severity,
                        finding.category,
                        finding.title,
                        finding.file,
                        finding.line,
                        finding.remediation,
                        finding.vulnerability_id,
                        finding.package_name,
                        finding.package_version,
                        finding.package_ecosystem,
                        finding.package_url,
                        finding.fixed_version,
                        finding.component_fingerprint,
                        finding.component_package_key,
                        finding.component_match_confidence,
                        finding.component_match_reason,
                        finding.old_version,
                        finding.new_version,
                        finding.behavior_category,
                        finding.evidence_summary,
                        finding.before_behavior,
                        finding.after_behavior,
                        finding.ioc_pack_id,
                        finding.ioc_source,
                        finding.ioc_advisory_url,
                        finding.ioc_confidence,
                        finding.ioc_match_type,
                        finding.ioc_indicator,
                        finding.install_recency_confidence,
                        finding.last_install_signal_at,
                        finding.install_recency_evidence,
                        finding.rotation_surfaces_json,
                        finding.fingerprint,
                        finding.timestamp,
                    )
                    for finding in findings
                ],
            )
            self.conn.execute("delete from sbom_components where scan_id = ?", (scan_id,))
            self.conn.executemany(
                """
                insert into sbom_components
                (scan_id, repo_name, source_format, source_file, bom_ref, name, version, ecosystem, component_type, package_url, license, supplier, source_path, component_fingerprint, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["scan_id"],
                        row["repo_name"],
                        row["source_format"],
                        row["source_file"],
                        row["bom_ref"],
                        row["name"],
                        row["version"],
                        row["ecosystem"],
                        row["component_type"],
                        row["package_url"],
                        row["license"],
                        row["supplier"],
                        row["source_path"],
                        row["component_fingerprint"],
                        component_created_at,
                    )
                    for row in component_rows
                ],
            )
            self.conn.execute("delete from dependency_manifest_entries where scan_id = ?", (scan_id,))
            self.conn.executemany(
                """
                insert into dependency_manifest_entries
                (scan_id, repo_name, manifest_path, ecosystem, name, declaration, normalized_declaration, scope, manifest_fingerprint, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["scan_id"],
                        row["repo_name"],
                        row["manifest_path"],
                        row["ecosystem"],
                        row["name"],
                        row["declaration"],
                        row["normalized_declaration"],
                        row["scope"],
                        row["manifest_fingerprint"],
                        component_created_at,
                    )
                    for row in manifest_rows
                ],
            )
            self.conn.execute("delete from dependency_trust_enrichments where scan_id = ?", (scan_id,))
            self.conn.executemany(
                """
                insert into dependency_trust_enrichments
                (scan_id, repo_name, component_fingerprint, component_package_key, package_name, package_version, package_ecosystem, package_url, source_repo, source_repo_url, source_repo_confidence, source_repo_reason, scorecard_score, scorecard_status, criticality_score, criticality_status, checked_at, freshness, status, cache_key, error, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["scan_id"],
                        row["repo_name"],
                        row["component_fingerprint"],
                        row["component_package_key"],
                        row["package_name"],
                        row["package_version"],
                        row["package_ecosystem"],
                        row["package_url"],
                        row["source_repo"],
                        row["source_repo_url"],
                        row["source_repo_confidence"],
                        row["source_repo_reason"],
                        row["scorecard_score"],
                        row["scorecard_status"],
                        row["criticality_score"],
                        row["criticality_status"],
                        row["checked_at"],
                        row["freshness"],
                        row["status"],
                        row["cache_key"],
                        row["error"],
                        trust_created_at,
                    )
                    for row in trust_rows
                ],
            )
            # Replace this scan's asset graph. Drop edges before nodes (the FK
            # points edges -> nodes); both are empty on a first save, so this is a
            # no-op on re-save when no edges have been recovered yet.
            self.conn.execute("delete from asset_edges where scan_id = ?", (scan_id,))
            self.conn.execute("delete from asset_nodes where scan_id = ?", (scan_id,))
            self.conn.executemany(
                """
                insert into asset_nodes
                (scan_id, repo_name, node_type, identity_key, label, is_crown_jewel, confidence, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        scan_id,
                        repo_name,
                        node.node_type,
                        node.identity_key,
                        node.label,
                        1 if node.is_crown_jewel else 0,
                        node.confidence,
                        node_created_at,
                    )
                    for node in asset_nodes
                ],
            )
            self.conn.execute("delete from platform_posture_snapshots where scan_id = ?", (scan_id,))
            if platform_posture_row:
                self.conn.execute(
                    """
                    insert into platform_posture_snapshots
                    (scan_id, repo_name, scanner, source, target, status, summary_json, snapshot_json, snapshot_fingerprint, created_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        platform_posture_row["scan_id"],
                        platform_posture_row["repo_name"],
                        platform_posture_row["scanner"],
                        platform_posture_row["source"],
                        platform_posture_row["target"],
                        platform_posture_row["status"],
                        platform_posture_row["summary_json"],
                        platform_posture_row["snapshot_json"],
                        platform_posture_row["snapshot_fingerprint"],
                        platform_created_at,
                    ),
                )

    def list_sbom_components(self, scan_id: str | None = None, repo_name: str | None = None) -> list[dict[str, Any]]:
        conditions = []
        params: list[str] = []
        if scan_id:
            conditions.append("scan_id = ?")
            params.append(scan_id)
        if repo_name:
            conditions.append("repo_name = ?")
            params.append(repo_name)
        where = f"where {' and '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"""
            select *
            from sbom_components
            {where}
            order by name asc, version asc, id asc
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def list_dependency_manifest_entries(self, scan_id: str | None = None, repo_name: str | None = None) -> list[dict[str, Any]]:
        conditions = []
        params: list[str] = []
        if scan_id:
            conditions.append("scan_id = ?")
            params.append(scan_id)
        if repo_name:
            conditions.append("repo_name = ?")
            params.append(repo_name)
        where = f"where {' and '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"""
            select *
            from dependency_manifest_entries
            {where}
            order by manifest_path asc, ecosystem asc, name asc, id asc
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def list_asset_nodes(self, scan_id: str | None = None, repo_name: str | None = None) -> list[dict[str, Any]]:
        """Return asset-graph nodes for a scan/repo, oldest-id first (stable order)."""
        conditions = []
        params: list[str] = []
        if scan_id:
            conditions.append("scan_id = ?")
            params.append(scan_id)
        if repo_name:
            conditions.append("repo_name = ?")
            params.append(repo_name)
        where = f"where {' and '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"""
            select *
            from asset_nodes
            {where}
            order by node_type asc, identity_key asc, id asc
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def list_asset_edges(self, scan_id: str | None = None, repo_name: str | None = None) -> list[dict[str, Any]]:
        """Return asset-graph edges for a scan/repo, oldest-id first (stable order)."""
        conditions = []
        params: list[str] = []
        if scan_id:
            conditions.append("scan_id = ?")
            params.append(scan_id)
        if repo_name:
            conditions.append("repo_name = ?")
            params.append(repo_name)
        where = f"where {' and '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"""
            select *
            from asset_edges
            {where}
            order by id asc
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def replace_asset_edges(
        self,
        *,
        scan_id: str,
        repo_name: str,
        edges: Iterable[AssetEdge],
    ) -> int:
        """Replace this scan's asset edges, resolving endpoints by node identity.

        The seam the dependency-edge (1.2) and IaC-edge (1.3) steps build on:
        they emit :class:`AssetEdge` objects addressed by the endpoints'
        ``identity_key`` and call here. We map each identity to the numeric
        ``asset_nodes.id`` already persisted for this scan, so edges reference the
        scan's existing nodes and never mint duplicates. An edge whose source or
        destination node does not exist in this scan is skipped (it cannot be a
        valid relationship); the count of edges actually written is returned.
        """
        identity_to_id = {
            (row["node_type"], row["identity_key"]): row["id"]
            for row in self.list_asset_nodes(scan_id=scan_id, repo_name=repo_name)
        }
        # Resolution is by identity_key alone; node_type is not known to the
        # edge, so build a key index keyed on identity_key (last writer wins only
        # if two node types share an identity_key, which the unique index makes
        # rare — components are fingerprints, surfaces are paths).
        key_to_id: dict[str, int] = {}
        for (_node_type, identity_key), node_id in identity_to_id.items():
            key_to_id.setdefault(identity_key, node_id)
        created_at = utc_now()
        rows = []
        for edge in edges:
            src_id = key_to_id.get(edge.src_identity_key.strip())
            dst_id = key_to_id.get(edge.dst_identity_key.strip())
            if src_id is None or dst_id is None:
                continue
            rows.append(
                (
                    scan_id,
                    repo_name,
                    src_id,
                    dst_id,
                    edge.edge_type,
                    edge.confidence,
                    edge.reason,
                    created_at,
                )
            )
        with self.conn:
            self.conn.execute("delete from asset_edges where scan_id = ?", (scan_id,))
            self.conn.executemany(
                """
                insert into asset_edges
                (scan_id, repo_name, src_node_id, dst_node_id, edge_type, confidence, reason, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def import_ioc_packs(self, packs: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> None:
        imported_at = utc_now()
        with self.conn:
            for pack in packs:
                pack_id = _optional_text(pack.get("id") or pack.get("pack_id"))
                if not pack_id:
                    continue
                indicators = [dict(item) for item in pack.get("indicators", []) if isinstance(item, dict)]
                pack_json = {
                    "id": pack_id,
                    "source": _optional_text(pack.get("source")) or pack_id,
                    "published_at": _optional_text(pack.get("published_at")),
                    "advisory_url": _optional_text(pack.get("advisory_url")),
                    "confidence": _optional_text(pack.get("confidence")) or "medium",
                    "source_file": _optional_text(pack.get("source_file")),
                    "indicators": indicators,
                }
                self.conn.execute(
                    """
                    insert into ioc_packs
                    (pack_id, source, published_at, advisory_url, confidence, source_file, raw_json, imported_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(pack_id) do update set
                      source = excluded.source,
                      published_at = excluded.published_at,
                      advisory_url = excluded.advisory_url,
                      confidence = excluded.confidence,
                      source_file = excluded.source_file,
                      raw_json = excluded.raw_json,
                      imported_at = excluded.imported_at
                    """,
                    (
                        pack_id,
                        pack_json["source"],
                        pack_json["published_at"],
                        pack_json["advisory_url"],
                        pack_json["confidence"],
                        pack_json["source_file"],
                        json.dumps(pack_json, sort_keys=True),
                        imported_at,
                    ),
                )
                self.conn.execute("delete from ioc_indicators where pack_id = ?", (pack_id,))
                self.conn.executemany(
                    """
                    insert into ioc_indicators
                    (pack_id, ecosystem, name, versions_json, namespace_prefix, domain, confidence, source_file, source_line, indicator_json, created_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            pack_id,
                            _optional_text(indicator.get("ecosystem")) or "other",
                            _optional_text(indicator.get("name")),
                            json.dumps(_list_text(indicator.get("versions")), sort_keys=True),
                            _optional_text(indicator.get("namespace_prefix")),
                            _optional_text(indicator.get("domain")),
                            _optional_text(indicator.get("confidence")) or pack_json["confidence"],
                            _optional_text(indicator.get("source_file")) or pack_json["source_file"],
                            _optional_int(indicator.get("source_line")),
                            json.dumps(indicator, sort_keys=True),
                            imported_at,
                        )
                        for indicator in indicators
                    ],
                )

    def list_ioc_packs(self, pack_ids: list[str] | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if pack_ids:
            placeholders = ", ".join("?" for _ in pack_ids)
            where = f"where pack_id in ({placeholders})"
            params.extend(pack_ids)
        pack_rows = self.conn.execute(
            f"""
            select *
            from ioc_packs
            {where}
            order by published_at desc, pack_id asc
            """,
            params,
        ).fetchall()
        packs: list[dict[str, Any]] = []
        for pack_row in pack_rows:
            indicators = [
                _public_ioc_indicator(row)
                for row in self.conn.execute(
                    """
                    select *
                    from ioc_indicators
                    where pack_id = ?
                    order by id asc
                    """,
                    (pack_row["pack_id"],),
                ).fetchall()
            ]
            packs.append(
                {
                    "id": pack_row["pack_id"],
                    "source": pack_row["source"],
                    "published_at": pack_row["published_at"],
                    "advisory_url": pack_row["advisory_url"],
                    "confidence": pack_row["confidence"],
                    "source_file": pack_row["source_file"],
                    "imported_at": pack_row["imported_at"],
                    "indicators": indicators,
                }
            )
        return packs

    def list_dependency_trust_enrichments(self, scan_id: str | None = None, repo_name: str | None = None) -> list[dict[str, Any]]:
        conditions = []
        params: list[str] = []
        if scan_id:
            conditions.append("scan_id = ?")
            params.append(scan_id)
        if repo_name:
            conditions.append("repo_name = ?")
            params.append(repo_name)
        where = f"where {' and '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"""
            select *
            from dependency_trust_enrichments
            {where}
            order by package_name asc, package_version asc, id asc
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def list_platform_posture_snapshots(
        self,
        scan_id: str | None = None,
        repo_name: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if scan_id:
            conditions.append("scan_id = ?")
            params.append(scan_id)
        if repo_name:
            conditions.append("repo_name = ?")
            params.append(repo_name)
        where = f"where {' and '.join(conditions)}" if conditions else ""
        params.append(limit)
        rows = self.conn.execute(
            f"""
            select *
            from platform_posture_snapshots
            {where}
            order by created_at desc, id desc
            limit ?
            """,
            params,
        ).fetchall()
        return [_public_platform_posture_snapshot(row) for row in rows]

    def latest_platform_posture_snapshot(
        self,
        repo_name: str,
        before_started_at: str | None = None,
        scan_id: str | None = None,
    ) -> dict[str, Any] | None:
        if scan_id:
            rows = self.list_platform_posture_snapshots(scan_id=scan_id, repo_name=repo_name, limit=1)
            return rows[0] if rows else None
        params: list[Any] = [repo_name]
        before_clause = ""
        if before_started_at:
            before_clause = "and s.started_at < ?"
            params.append(before_started_at)
        row = self.conn.execute(
            f"""
            select p.*
            from platform_posture_snapshots p
            join scans s on s.id = p.scan_id
            where p.repo_name = ?
            {before_clause}
            order by s.started_at desc, p.id desc
            limit 1
            """,
            params,
        ).fetchone()
        return _public_platform_posture_snapshot(row) if row else None

    # --- Set-based read helpers for the dashboard payload (S-027) ------------
    # These batch the per-repo fan-out that the dashboard payload used to run.
    # Persistence owns the schema and the queries; the UI-payload assembly that
    # consumes them lives in `dashboard_payload.assemble_dashboard_payload`
    # (S-017), keeping this module free of any scanner-orchestration import.

    def latest_scans(self) -> list[sqlite3.Row]:
        """The most recent scan per repo, ordered worst-health-first.

        Same selection the dashboard payload has always used; lifted into a
        named query so the assembly layer reads rows instead of embedding SQL.
        """
        return self.conn.execute(
            """
            select s.*
            from scans s
            join (
              select repo_name, max(started_at) as started_at
              from scans
              group by repo_name
            ) last on last.repo_name = s.repo_name and last.started_at = s.started_at
            order by s.health_score asc, s.repo_name asc
            """
        ).fetchall()

    def recent_scan_history(self, *, limit: int = 200) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute(
                """
                select id, repo_name, started_at, finished_at, health_score, status, profile
                from scans
                order by started_at desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        ]

    def previous_scans_for_latest(
        self, latest_rows: list[sqlite3.Row]
    ) -> dict[str, dict[str, Any] | None]:
        """Batch the per-repo previous-scan lookup, keyed by latest scan id.

        For each latest scan (repo R, started_at T) the "previous" scan is the
        most recent scan of R strictly before T — exactly what ``_previous_scan``
        returns one repo at a time. We pull the two most recent scans per repo in
        a single window query and resolve the previous in memory, so the lookup
        no longer runs one query per repo. (A repo whose two newest scans share
        an identical ``started_at`` is the same tie ``_previous_scan`` already
        resolved arbitrarily; real scans use distinct timestamps.)
        """
        repo_names = sorted({str(row["repo_name"]) for row in latest_rows})
        by_repo: dict[str, list[dict[str, Any]]] = {}
        if repo_names:
            placeholders = ",".join("?" for _ in repo_names)
            rows = self.conn.execute(
                f"""
                select * from (
                  select s.*, row_number() over (
                    partition by repo_name order by started_at desc, id desc
                  ) as _rownum
                  from scans s
                  where repo_name in ({placeholders})
                )
                where _rownum <= 2
                """,
                repo_names,
            ).fetchall()
            for row in rows:
                data = dict(row)
                data.pop("_rownum", None)
                by_repo.setdefault(str(data["repo_name"]), []).append(data)
        previous: dict[str, dict[str, Any] | None] = {}
        for row in latest_rows:
            cutoff = str(row["started_at"])
            candidates = [
                scan
                for scan in by_repo.get(str(row["repo_name"]), [])
                if str(scan["started_at"]) < cutoff
            ]
            candidates.sort(key=lambda scan: str(scan["started_at"]), reverse=True)
            previous[str(row["id"])] = candidates[0] if candidates else None
        return previous

    def _rows_by_scan(
        self, scan_ids: list[str], query_template: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Run one ``where scan_id in (...)`` query and bucket rows per scan.

        ``query_template`` must contain a single ``{ph}`` placeholder slot for
        the id list and select a ``scan_id`` column. Every requested scan id is
        present in the result (empty list when it has no rows), matching the
        per-scan ``list_*`` helpers this batches.
        """
        result: dict[str, list[dict[str, Any]]] = {str(scan_id): [] for scan_id in scan_ids}
        unique_ids = list(dict.fromkeys(str(scan_id) for scan_id in scan_ids))
        if not unique_ids:
            return result
        placeholders = ",".join("?" for _ in unique_ids)
        rows = self.conn.execute(query_template.format(ph=placeholders), unique_ids).fetchall()
        for row in rows:
            result.setdefault(str(row["scan_id"]), []).append(dict(row))
        return result

    def findings_for_scans(self, scan_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        return self._rows_by_scan(
            scan_ids,
            "select * from findings where scan_id in ({ph}) order by severity desc, id asc",
        )

    def sbom_components_for_scans(self, scan_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        return self._rows_by_scan(
            scan_ids,
            "select * from sbom_components where scan_id in ({ph}) order by name asc, version asc, id asc",
        )

    def dependency_manifest_entries_for_scans(self, scan_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        return self._rows_by_scan(
            scan_ids,
            "select * from dependency_manifest_entries where scan_id in ({ph}) "
            "order by manifest_path asc, ecosystem asc, name asc, id asc",
        )

    def dependency_trust_for_scans(self, scan_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        return self._rows_by_scan(
            scan_ids,
            "select * from dependency_trust_enrichments where scan_id in ({ph}) "
            "order by package_name asc, package_version asc, id asc",
        )

    def platform_posture_for_scans(self, scan_ids: list[str]) -> dict[str, dict[str, Any] | None]:
        """Latest posture snapshot per scan (mirrors ``latest_platform_posture_snapshot``)."""
        result: dict[str, dict[str, Any] | None] = {str(scan_id): None for scan_id in scan_ids}
        unique_ids = list(dict.fromkeys(str(scan_id) for scan_id in scan_ids))
        if not unique_ids:
            return result
        placeholders = ",".join("?" for _ in unique_ids)
        rows = self.conn.execute(
            f"""
            select *
            from platform_posture_snapshots
            where scan_id in ({placeholders})
            order by created_at desc, id desc
            """,
            unique_ids,
        ).fetchall()
        for row in rows:
            scan_id = str(row["scan_id"])
            if result.get(scan_id) is None:
                result[scan_id] = _public_platform_posture_snapshot(row)
        return result

    def case_resolution_runs_for_dashboard(
        self,
        repo_names: list[str],
        *,
        global_limit: int = 50,
        per_repo_limit: int = 5,
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        """Batched resolution-run fetch for the dashboard payload.

        Returns ``(global_runs, runs_by_repo)`` where ``global_runs`` mirrors
        ``list_case_resolution_runs(limit=global_limit)`` and ``runs_by_repo[R]``
        mirrors ``list_case_resolution_runs(repo_name=R, limit=per_repo_limit)``.
        Every run's items are pulled in a single ``where run_id in (...)`` query
        — collapsing the per-run ``case_resolution_items`` N+1 the per-repo loop
        used to trigger once per run, once per repo.
        """
        clean_global = max(1, min(int(global_limit or 50), 200))
        clean_per_repo = max(1, min(int(per_repo_limit or 5), 200))
        global_rows = self.conn.execute(
            "select * from case_resolution_runs order by imported_at desc limit ?",
            (clean_global,),
        ).fetchall()
        repo_rows: list[sqlite3.Row] = []
        clean_repos = sorted({str(name).strip() for name in repo_names if str(name).strip()})
        if clean_repos:
            placeholders = ",".join("?" for _ in clean_repos)
            repo_rows = self.conn.execute(
                f"""
                select * from (
                  select r.*, row_number() over (
                    partition by repo_name order by imported_at desc
                  ) as _rownum
                  from case_resolution_runs r
                  where repo_name in ({placeholders})
                )
                where _rownum <= ?
                order by imported_at desc
                """,
                (*clean_repos, clean_per_repo),
            ).fetchall()
        run_ids = list(dict.fromkeys(row["id"] for row in (*global_rows, *repo_rows)))
        items_by_run: dict[str, list[sqlite3.Row]] = {}
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            item_rows = self.conn.execute(
                f"""
                select *
                from case_resolution_items
                where run_id in ({placeholders})
                order by created_at asc, id asc
                """,
                run_ids,
            ).fetchall()
            for item in item_rows:
                items_by_run.setdefault(str(item["run_id"]), []).append(item)
        global_runs = [
            _public_case_resolution_run(row, items_by_run.get(str(row["id"]), []))
            for row in global_rows
        ]
        runs_by_repo: dict[str, list[dict[str, Any]]] = {}
        for row in repo_rows:
            runs_by_repo.setdefault(str(row["repo_name"]), []).append(
                _public_case_resolution_run(row, items_by_run.get(str(row["id"]), []))
            )
        return global_runs, runs_by_repo

    def dashboard_payload(self) -> dict[str, Any]:
        """Assemble the ``/api/summary`` payload.

        The assembly itself — catalog embedding plus per-repo enrichment — lives
        in ``dashboard_payload.assemble_dashboard_payload`` (S-017) so this module
        owns schema and queries only and carries no scanner-orchestration import.
        Imported lazily to keep the persistence module free of an import cycle.
        """
        from .dashboard_payload import assemble_dashboard_payload

        return assemble_dashboard_payload(self)

    def scan_export(self, scan_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("select * from scans where id = ?", (scan_id,)).fetchone()
        if not row:
            return None
        findings = [
            dict(item)
            for item in self.conn.execute(
                "select * from findings where scan_id = ? order by severity desc, id asc",
                (scan_id,),
            ).fetchall()
        ]
        scan = dict(row)
        cases = _decode_cases(scan["cases_json"])
        case_decisions = self.case_decisions_map()
        for case in cases:
            if isinstance(case, dict):
                case["scan_id"] = scan["id"]
                case["repo"] = scan["repo_name"]
                case["repo_name"] = scan["repo_name"]
                _attach_case_decision(case, case_decisions)
        assembled = assemble_suppression(
            [case for case in cases if isinstance(case, dict)],
            findings,
            case_decisions,
        )
        return {
            "scan_id": scan["id"],
            "repo": scan["repo_name"],
            "repo_path": scan["repo_path"],
            "report_path": scan["report_path"],
            "started_at": scan["started_at"],
            "finished_at": scan["finished_at"],
            "profile": scan["profile"],
            "health_score": scan["health_score"],
            "status": scan["status"],
            "scanners": json.loads(scan["scanner_status_json"]),
            "cases": assembled["cases"],
            "active_cases": assembled["active_cases"],
            "suppressed_cases": assembled["suppressed_cases"],
            "findings": assembled["findings"],
            "active_findings": assembled["active_findings"],
            "suppressed_findings": assembled["suppressed_findings"],
            "suppressed_counts": assembled["suppressed_counts"],
            "suppression_reasons": assembled["suppressed_counts"]["reasons"],
            "dependency_trust": self.list_dependency_trust_enrichments(scan_id=scan_id, repo_name=scan["repo_name"]),
            "platform_posture": self.latest_platform_posture_snapshot(repo_name=scan["repo_name"], scan_id=scan_id),
        }

    def scan_diff(self, base_id: str, head_id: str) -> dict[str, Any] | None:
        """Diff two *arbitrary* scans (base -> head).

        Reuses the same `_scan_delta` engine that powers the per-repo
        "since last scan" deltas, but lets the caller pick any base and head
        rather than only a scan and its immediate predecessor. Returns the
        health delta plus the new / recurring / resolved case sets; resolved
        cases carry the closure-proof binding (`resolved_by_scan_id`,
        `lifecycle_state: resolved`) that `_scan_delta` attaches. Returns None
        if either scan id is unknown.
        """
        base_row = self.conn.execute("select * from scans where id = ?", (base_id,)).fetchone()
        head_row = self.conn.execute("select * from scans where id = ?", (head_id,)).fetchone()
        if not base_row or not head_row:
            return None
        delta = _scan_delta(head_row, dict(base_row))
        case_changes = delta["case_changes"]
        head_cases = []
        for item in _decode_cases(head_row["cases_json"]):
            if not isinstance(item, dict):
                continue
            case = {
                "scan_id": head_row["id"],
                "repo": head_row["repo_name"],
                "repo_name": head_row["repo_name"],
                **item,
            }
            case_id = str(case.get("case_id") or case.get("id") or "")
            case["change_status"] = case_changes.get(case_id, "new")
            head_cases.append(case)
        new_cases = [case for case in head_cases if case.get("change_status") == "new"]
        recurring_cases = [case for case in head_cases if case.get("change_status") == "recurring"]
        return {
            "base": _scan_endpoint_meta(base_row),
            "head": _scan_endpoint_meta(head_row),
            "health_delta": delta["health_delta"],
            "same_repo": base_row["repo_name"] == head_row["repo_name"],
            "counts": {
                "new": len(new_cases),
                "recurring": len(recurring_cases),
                "resolved": delta["resolved_count"],
            },
            "new_cases": new_cases,
            "recurring_cases": recurring_cases,
            "resolved_cases": delta["resolved_cases"],
        }

    def _previous_scan(self, repo_name: str, started_at: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            select *
            from scans
            where repo_name = ? and started_at < ?
            order by started_at desc
            limit 1
            """,
            (repo_name, started_at),
        ).fetchone()
        return dict(row) if row else None

    def previous_scan_for_repo(self, repo_name: str, before_started_at: str) -> dict[str, Any] | None:
        return self._previous_scan(repo_name, before_started_at)

    def latest_scan_for_repo(self, repo_name: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            select *
            from scans
            where repo_name = ?
            order by started_at desc
            limit 1
            """,
            (repo_name,),
        ).fetchone()
        return dict(row) if row else None

    def _dependency_delta(self, latest: sqlite3.Row, previous: dict[str, Any] | None) -> dict[str, Any]:
        current_components = self.list_sbom_components(scan_id=latest["id"], repo_name=latest["repo_name"])
        previous_components = (
            self.list_sbom_components(scan_id=str(previous["id"]), repo_name=str(previous["repo_name"]))
            if previous
            else []
        )
        current_manifest_entries = self.list_dependency_manifest_entries(scan_id=latest["id"], repo_name=latest["repo_name"])
        previous_manifest_entries = (
            self.list_dependency_manifest_entries(scan_id=str(previous["id"]), repo_name=str(previous["repo_name"]))
            if previous
            else []
        )
        current_dependency_findings = [
            dict(row)
            for row in self.conn.execute(
                "select * from findings where scan_id = ? and category = 'dependencies'",
                (latest["id"],),
            ).fetchall()
        ]
        return _dependency_delta(
            latest,
            previous,
            current_components,
            previous_components,
            current_dependency_findings,
            current_manifest_entries,
            previous_manifest_entries,
        )

    def case_decisions_map(self) -> dict[str, dict[str, Any]]:
        rows = self.conn.execute("select * from case_decisions order by updated_at desc").fetchall()
        return {str(row["case_id"]): normalize_case_decision(dict(row)) for row in rows}

    def export_vex_decisions(self, *, repo_name: str | None = None, tool_version: str = "0.1.0") -> dict[str, Any]:
        return build_vex_document(
            self.case_decisions_map().values(),
            repo_name=repo_name.strip() if repo_name else None,
            tool_version=tool_version,
        )

    def import_vex_decisions(self, document: dict[str, Any], *, repo_name: str | None = None) -> dict[str, Any]:
        parsed = parse_vex_document(document, repo_name=repo_name.strip() if repo_name else None)
        imported = 0
        warnings = list(parsed["warnings"])
        imported_case_ids = []
        for decision in parsed["decisions"]:
            try:
                saved = self.set_case_decision(
                    case_id=decision["case_id"],
                    repo_name=decision["repo_name"],
                    status=decision["status"],
                    note=decision.get("note"),
                    vex_status=decision.get("vex_status"),
                    vex_justification=decision.get("vex_justification"),
                    vulnerability_id=decision.get("vulnerability_id"),
                    package_name=decision.get("package_name"),
                    package_version=decision.get("package_version"),
                    package_ecosystem=decision.get("package_ecosystem"),
                    package_url=decision.get("package_url"),
                    component_package_key=decision.get("component_package_key"),
                    fixed_version=decision.get("fixed_version"),
                    # A VEX document is an explicit, operator-authored suppression
                    # record (imported by hand or CI), not an AI proposal derived
                    # from finding text — so it carries human authorization.
                    human_authorized=True,
                )
            except ValueError as exc:
                warnings.append(f"{decision.get('case_id') or 'decision'}: {exc}")
                continue
            if saved:
                imported += 1
                imported_case_ids.append(saved["case_id"])
        return {
            "imported": imported,
            "skipped": int(parsed["skipped"]) + max(0, len(parsed["decisions"]) - imported),
            "case_ids": imported_case_ids,
            "warnings": _dedupe_text(warnings),
        }

    def save_case_resolution_run(self, run: dict[str, Any]) -> dict[str, Any]:
        run_id = str(run.get("run_id") or run.get("id") or "").strip()
        repo_name = str(run.get("repo_name") or run.get("repo") or "").strip()
        action = str(run.get("action") or "").strip()
        scope = str(run.get("scope") or "").strip()
        source = str(run.get("source") or "json_import").strip() or "json_import"
        status = str(run.get("status") or "previewed").strip()
        if not run_id:
            raise ValueError("Resolution run id is required.")
        if not repo_name:
            raise ValueError("Resolution run repo is required.")
        if status not in {"previewed", "applied", "partially_applied", "rejected", "requires_confirmation"}:
            raise ValueError("Unsupported resolution run status.")
        imported_at = str(run.get("imported_at") or utc_now())
        applied_at = _optional_text(run.get("applied_at"))
        summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
        items = [item for item in (run.get("items") or []) if isinstance(item, dict)]
        with self.conn:
            self.conn.execute(
                """
                insert into case_resolution_runs
                (id, repo_name, scan_id, action, scope, source, imported_at, applied_at, status, summary_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  repo_name = excluded.repo_name,
                  scan_id = excluded.scan_id,
                  action = excluded.action,
                  scope = excluded.scope,
                  source = excluded.source,
                  applied_at = excluded.applied_at,
                  status = excluded.status,
                  summary_json = excluded.summary_json
                """,
                (
                    run_id,
                    repo_name,
                    _optional_text(run.get("scan_id")),
                    action,
                    scope,
                    source,
                    imported_at,
                    applied_at,
                    status,
                    _json(summary),
                ),
            )
            self.conn.execute("delete from case_resolution_items where run_id = ?", (run_id,))
            for item in items:
                item_id = str(item.get("id") or "").strip() or f"{run_id}:{item.get('case_id')}"
                item_status = str(item.get("status") or "pending").strip()
                if item_status not in {"pending", "applied", "left_open", "rejected", "requires_human_confirmation"}:
                    item_status = "rejected"
                self.conn.execute(
                    """
                    insert into case_resolution_items
                    (id, run_id, case_id, repo_name, scan_id, ai_disposition, mapped_decision,
                     confidence, reason, evidence_json, recommended_next_step, applied_decision_json,
                     status, warning, created_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        run_id,
                        str(item.get("case_id") or "").strip(),
                        str(item.get("repo_name") or repo_name).strip(),
                        _optional_text(item.get("scan_id") or run.get("scan_id")),
                        str(item.get("ai_disposition") or item.get("disposition") or "").strip(),
                        _optional_text(item.get("mapped_decision")),
                        str(item.get("confidence") or "medium").strip() or "medium",
                        redact_text(str(item.get("reason") or "").strip())[:2000],
                        _json(item.get("evidence") if isinstance(item.get("evidence"), list) else []),
                        _decision_text(item.get("recommended_next_step")),
                        _json(item.get("applied_decision")) if item.get("applied_decision") is not None else None,
                        item_status,
                        _decision_text(item.get("warning")),
                        str(item.get("created_at") or imported_at),
                    ),
                )
        saved = self.get_case_resolution_run(run_id)
        if not saved:
            raise ValueError("Resolution run was not saved.")
        return saved

    def get_case_resolution_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("select * from case_resolution_runs where id = ?", (run_id,)).fetchone()
        if not row:
            return None
        items = self.conn.execute(
            "select * from case_resolution_items where run_id = ? order by created_at asc, id asc",
            (run_id,),
        ).fetchall()
        return _public_case_resolution_run(row, items)

    def list_case_resolution_runs(self, *, repo_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        clean_limit = max(1, min(int(limit or 50), 200))
        params: list[Any] = []
        where = ""
        if repo_name:
            where = "where repo_name = ?"
            params.append(repo_name.strip())
        params.append(clean_limit)
        rows = self.conn.execute(
            f"""
            select *
            from case_resolution_runs
            {where}
            order by imported_at desc
            limit ?
            """,
            params,
        ).fetchall()
        runs = []
        for row in rows:
            item_rows = self.conn.execute(
                "select * from case_resolution_items where run_id = ? order by created_at asc, id asc",
                (row["id"],),
            ).fetchall()
            runs.append(_public_case_resolution_run(row, item_rows))
        return runs

    def update_case_resolution_run(
        self,
        run_id: str,
        *,
        status: str,
        item_updates: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if status not in {"previewed", "applied", "partially_applied", "rejected", "requires_confirmation"}:
            raise ValueError("Unsupported resolution run status.")
        now = utc_now()
        updates = item_updates or {}
        with self.conn:
            self.conn.execute(
                "update case_resolution_runs set status = ?, applied_at = ? where id = ?",
                (status, now if status != "previewed" else None, run_id),
            )
            for item_id, update in updates.items():
                item_status = str(update.get("status") or "").strip()
                if item_status not in {"pending", "applied", "left_open", "rejected", "requires_human_confirmation"}:
                    continue
                self.conn.execute(
                    """
                    update case_resolution_items
                    set status = ?,
                        warning = coalesce(?, warning),
                        applied_decision_json = ?
                    where id = ? and run_id = ?
                    """,
                    (
                        item_status,
                        _decision_text(update.get("warning")),
                        _json(update.get("applied_decision")) if update.get("applied_decision") is not None else None,
                        item_id,
                        run_id,
                    ),
                )
            item_rows = self.conn.execute(
                "select status, ai_disposition from case_resolution_items where run_id = ?",
                (run_id,),
            ).fetchall()
            status_counts = Counter(str(row["status"]) for row in item_rows)
            disposition_counts = Counter(str(row["ai_disposition"]) for row in item_rows)
            row = self.conn.execute("select summary_json from case_resolution_runs where id = ?", (run_id,)).fetchone()
            summary = _json_load(row["summary_json"], {}) if row else {}
            summary["statuses"] = dict(sorted(status_counts.items()))
            summary["dispositions"] = dict(sorted(disposition_counts.items()))
            summary["will_apply"] = int(status_counts.get("pending", 0))
            summary["will_leave_open"] = int(status_counts.get("left_open", 0))
            summary["rejected"] = int(status_counts.get("rejected", 0))
            summary["requires_confirmation"] = int(status_counts.get("requires_human_confirmation", 0))
            self.conn.execute(
                "update case_resolution_runs set summary_json = ? where id = ?",
                (_json(summary), run_id),
            )
        return self.get_case_resolution_run(run_id)

    def save_fix_proposal(self, record: dict[str, Any]) -> dict[str, Any]:
        proposal_id = str(record.get("id") or "").strip()
        if not proposal_id:
            raise ValueError("Fix proposal id is required.")
        repo_name = str(record.get("repo_name") or "").strip()
        if not repo_name:
            raise ValueError("Fix proposal repo is required.")
        status = str(record.get("status") or "proposed").strip()
        if status not in {"proposed", "reviewed", "auto_merge_authorized", "requires_human"}:
            raise ValueError("Unsupported fix proposal status.")
        clean_room_status = str(record.get("clean_room_status") or "pending").strip()
        if clean_room_status not in {"pending", "approved", "rejected"}:
            raise ValueError("Unsupported clean-room review status.")
        now = _optional_text(record.get("updated_at")) or utc_now()
        # The diff is stored verbatim: the caller (fix_proposals.propose_fix) has
        # already redacted it and hashed *that* redacted text, so re-redacting here
        # would risk drifting the stored bytes from the recorded diff_sha256.
        with self.conn:
            self.conn.execute(
                """
                insert into fix_proposals
                (id, repo_name, repo_path, case_id, base_branch, head_branch, title, diff, diff_sha256,
                 fix_class, auto_merge_eligible, classification_json, source, status, clean_room_status,
                 clean_room_reviewer, clean_room_checked_invariants_json, clean_room_notes,
                 clean_room_diff_sha256, clean_room_reviewed_at, landing_outcome, landing_reasons_json,
                 landing_decided_at, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  repo_name = excluded.repo_name,
                  repo_path = excluded.repo_path,
                  case_id = excluded.case_id,
                  base_branch = excluded.base_branch,
                  head_branch = excluded.head_branch,
                  title = excluded.title,
                  diff = excluded.diff,
                  diff_sha256 = excluded.diff_sha256,
                  fix_class = excluded.fix_class,
                  auto_merge_eligible = excluded.auto_merge_eligible,
                  classification_json = excluded.classification_json,
                  source = excluded.source,
                  status = excluded.status,
                  clean_room_status = excluded.clean_room_status,
                  updated_at = excluded.updated_at
                """,
                (
                    proposal_id,
                    repo_name,
                    _optional_text(record.get("repo_path")),
                    _optional_text(record.get("case_id")),
                    str(record.get("base_branch") or "main"),
                    str(record.get("head_branch") or ""),
                    redact_text(str(record.get("title") or ""))[:300],
                    str(record.get("diff") or ""),
                    str(record.get("diff_sha256") or ""),
                    str(record.get("fix_class") or "unknown"),
                    1 if record.get("auto_merge_eligible") else 0,
                    _json(record.get("classification") or {}),
                    str(record.get("source") or "mcp_write"),
                    status,
                    clean_room_status,
                    _optional_text(record.get("clean_room_reviewer")),
                    _json(record.get("clean_room_checked_invariants") or []),
                    redact_text(str(record.get("clean_room_notes") or "").strip())[:2000] or None,
                    _optional_text(record.get("clean_room_diff_sha256")),
                    _optional_text(record.get("clean_room_reviewed_at")),
                    _optional_text(record.get("landing_outcome")),
                    _json(record.get("landing_reasons") or []),
                    _optional_text(record.get("landing_decided_at")),
                    str(record.get("created_at") or now),
                    now,
                ),
            )
        saved = self.get_fix_proposal(proposal_id)
        if not saved:
            raise ValueError("Fix proposal could not be saved.")
        return saved

    def get_fix_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "select * from fix_proposals where id = ?",
            (str(proposal_id or "").strip(),),
        ).fetchone()
        return _public_fix_proposal(row) if row else None

    def list_fix_proposals(
        self,
        *,
        repo_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if repo_name:
            conditions.append("repo_name = ?")
            params.append(repo_name.strip())
        if status:
            conditions.append("status = ?")
            params.append(status.strip())
        where = f"where {' and '.join(conditions)}" if conditions else ""
        params.append(max(1, min(int(limit or 50), 200)))
        rows = self.conn.execute(
            f"""
            select *
            from fix_proposals
            {where}
            order by created_at desc, id asc
            limit ?
            """,
            params,
        ).fetchall()
        return [_public_fix_proposal(row) for row in rows]

    def record_fix_proposal_review(
        self,
        *,
        proposal_id: str,
        approved: bool,
        checked_invariants: list[str] | None = None,
        reviewer: str | None = None,
        notes: str | None = None,
        clean_room_diff_sha256: str | None = None,
    ) -> dict[str, Any]:
        clean_id = str(proposal_id or "").strip()
        current = self.get_fix_proposal(clean_id)
        if not current:
            raise ValueError("Fix proposal not found.")
        clean_room_status = "approved" if approved else "rejected"
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                update fix_proposals
                set clean_room_status = ?,
                    clean_room_reviewer = ?,
                    clean_room_checked_invariants_json = ?,
                    clean_room_notes = ?,
                    clean_room_diff_sha256 = ?,
                    clean_room_reviewed_at = ?,
                    status = case
                      when status in ('auto_merge_authorized', 'requires_human') then status
                      else 'reviewed'
                    end,
                    updated_at = ?
                where id = ?
                """,
                (
                    clean_room_status,
                    redact_text((reviewer or "").strip())[:120] or None,
                    _json([str(item).strip() for item in (checked_invariants or []) if str(item).strip()]),
                    redact_text((notes or "").strip())[:2000] or None,
                    _optional_text(clean_room_diff_sha256) or current.get("diff_sha256"),
                    now,
                    now,
                    clean_id,
                ),
            )
        return self.get_fix_proposal(clean_id)

    def record_fix_proposal_landing(
        self,
        *,
        proposal_id: str,
        outcome: str,
        reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        clean_id = str(proposal_id or "").strip()
        clean_outcome = str(outcome or "").strip()
        if clean_outcome not in {"auto_merge", "requires_human", "blocked"}:
            raise ValueError("Unsupported fix landing outcome.")
        current = self.get_fix_proposal(clean_id)
        if not current:
            raise ValueError("Fix proposal not found.")
        status = "auto_merge_authorized" if clean_outcome == "auto_merge" else "requires_human"
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                update fix_proposals
                set landing_outcome = ?,
                    landing_reasons_json = ?,
                    landing_decided_at = ?,
                    status = ?,
                    updated_at = ?
                where id = ?
                """,
                (
                    clean_outcome,
                    _json([str(item).strip() for item in (reasons or []) if str(item).strip()]),
                    now,
                    status,
                    now,
                    clean_id,
                ),
            )
        return self.get_fix_proposal(clean_id)

    def set_case_decision(
        self,
        *,
        case_id: str,
        repo_name: str,
        status: str | None,
        note: str | None = None,
        vex_status: str | None = None,
        vex_justification: str | None = None,
        vulnerability_id: str | None = None,
        package_name: str | None = None,
        package_version: str | None = None,
        package_ecosystem: str | None = None,
        package_url: str | None = None,
        component_package_key: str | None = None,
        fixed_version: str | None = None,
        human_authorized: bool = False,
    ) -> dict[str, Any] | None:
        clean_case_id = case_id.strip()
        clean_repo_name = repo_name.strip() or "repository"
        clean_status = (status or "").strip()
        clean_note = redact_text((note or "").strip())[:1000] or None
        if not clean_case_id:
            raise ValueError("case_id is required")
        if clean_status in {"", "open"}:
            with self.conn:
                self.conn.execute("delete from case_decisions where case_id = ?", (clean_case_id,))
            return None
        if clean_status not in CASE_DECISION_STATUSES:
            raise ValueError("Unsupported case decision")
        inferred_case = self._latest_case_for_decision(clean_case_id, clean_repo_name)
        # Severity gate (the one irreversible-ish control on this surface): hiding
        # a high/critical finding always needs a human. Severity is read from the
        # recorded case — never from caller-supplied text — so poisoned finding
        # text cannot lower a case's severity to slip past the gate. This is the
        # chokepoint every write path crosses, so the gate cannot be bypassed by a
        # caller that skips the higher-level case-resolution layer.
        if not human_authorized and clean_status in SUPPRESSING_DECISION_STATUSES:
            severity = str((inferred_case or {}).get("severity") or "").strip().casefold()
            if severity in GATED_SUPPRESSION_SEVERITIES:
                raise HumanConfirmationRequired(
                    f"Suppressing a {severity} case requires explicit human confirmation."
                )
        inferred_fields = dependency_fields_from_case(inferred_case) if inferred_case else {}
        dependency_fields = {
            "vulnerability_id": vulnerability_id,
            "package_name": package_name,
            "package_version": package_version,
            "package_ecosystem": package_ecosystem,
            "package_url": package_url,
            "component_package_key": component_package_key,
            "fixed_version": fixed_version,
        }
        for key, value in inferred_fields.items():
            if not dependency_fields.get(key):
                dependency_fields[key] = value
        dependency_fields = {key: _decision_text(value) for key, value in dependency_fields.items()}
        if vex_status and str(vex_status).strip().casefold().replace("-", "_").replace(" ", "_") not in VEX_STATUSES:
            raise ValueError("Unsupported VEX status")
        clean_vex_status = normalize_vex_status(vex_status, clean_status)
        if clean_vex_status not in VEX_STATUSES:
            raise ValueError("Unsupported VEX status")
        clean_vex_justification = redact_text((vex_justification or clean_note or "").strip())[:1000] or None
        is_dependency_decision = bool(dependency_fields.get("vulnerability_id") and dependency_fields.get("package_name"))
        if is_dependency_decision and clean_status in SUPPRESSING_DECISION_STATUSES and not clean_vex_justification:
            raise ValueError("Dependency suppressions need a human-readable justification.")
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                insert into case_decisions
                (case_id, repo_name, status, note, vex_status, vex_justification, vulnerability_id, package_name, package_version, package_ecosystem, package_url, component_package_key, fixed_version, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(case_id) do update set
                  repo_name = excluded.repo_name,
                  status = excluded.status,
                  note = excluded.note,
                  vex_status = excluded.vex_status,
                  vex_justification = excluded.vex_justification,
                  vulnerability_id = excluded.vulnerability_id,
                  package_name = excluded.package_name,
                  package_version = excluded.package_version,
                  package_ecosystem = excluded.package_ecosystem,
                  package_url = excluded.package_url,
                  component_package_key = excluded.component_package_key,
                  fixed_version = excluded.fixed_version,
                  updated_at = excluded.updated_at
                """,
                (
                    clean_case_id,
                    clean_repo_name,
                    clean_status,
                    clean_note,
                    clean_vex_status,
                    clean_vex_justification,
                    dependency_fields.get("vulnerability_id"),
                    dependency_fields.get("package_name"),
                    dependency_fields.get("package_version"),
                    dependency_fields.get("package_ecosystem"),
                    dependency_fields.get("package_url"),
                    dependency_fields.get("component_package_key"),
                    dependency_fields.get("fixed_version"),
                    now,
                    now,
                ),
            )
        row = self.conn.execute("select * from case_decisions where case_id = ?", (clean_case_id,)).fetchone()
        return normalize_case_decision(dict(row)) if row else None

    def _latest_case_for_decision(self, case_id: str, repo_name: str) -> dict[str, Any] | None:
        rows = self.conn.execute(
            """
            select cases_json
            from scans
            where repo_name = ?
            order by started_at desc
            """,
            (repo_name,),
        ).fetchall()
        for row in rows:
            for case in _decode_cases(row["cases_json"]):
                if isinstance(case, dict) and _case_identity(case) == case_id:
                    return case
        return None

    def honey_signing_secret(self) -> str:
        row = self.conn.execute("select value from observatory_settings where key = 'honey_signing_secret'").fetchone()
        if row:
            return str(row["value"])
        value = secrets.token_urlsafe(32)
        with self.conn:
            self.conn.execute(
                "insert into observatory_settings (key, value) values ('honey_signing_secret', ?)",
                (value,),
            )
        return value

    def honey_event_retention_days(self) -> int:
        row = self.conn.execute("select value from observatory_settings where key = 'honey_event_retention_days'").fetchone()
        if row:
            try:
                return max(1, min(3650, int(row["value"])))
            except (TypeError, ValueError):
                return 90
        with self.conn:
            self.conn.execute(
                "insert or ignore into observatory_settings (key, value) values ('honey_event_retention_days', '90')",
            )
        return 90

    def prune_honey_key_events(self, *, retention_days: int) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self.conn:
            self.conn.execute("delete from honey_key_events where triggered_at < ?", (cutoff,))

    def create_honey_key(
        self,
        *,
        key_id: str,
        project_id: str,
        repo_id: str | None,
        name: str,
        token_hash: str,
        placement_path: str | None,
        note: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                insert into honey_keys
                (id, project_id, repo_id, name, token_prefix, token_hash, status, placement_path, note, created_at, created_by, trigger_count)
                values (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, 0)
                """,
                (key_id, project_id, repo_id, name, HONEY_KEY_PREFIX, token_hash, placement_path, note, now, created_by),
            )
            self.conn.execute(
                """
                insert into security_project_status (project_id, status, reason, last_event_at)
                values (?, 'green', 'No Honey Key has been triggered.', null)
                on conflict(project_id) do nothing
                """,
                (project_id,),
            )
        return self.get_honey_key(key_id) or {}

    def get_honey_key(self, key_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("select * from honey_keys where id = ?", (key_id,)).fetchone()
        return _public_honey_key(row) if row else None

    def find_honey_key_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        row = self.conn.execute("select * from honey_keys where token_hash = ?", (token_hash,)).fetchone()
        return dict(row) if row else None

    def list_honey_keys(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            rows = self.conn.execute(
                "select * from honey_keys where project_id = ? order by created_at desc",
                (project_id,),
            ).fetchall()
        else:
            rows = self.conn.execute("select * from honey_keys order by created_at desc").fetchall()
        return [_public_honey_key(row) for row in rows]

    def archive_honey_key(self, key_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.conn:
            self.conn.execute(
                "update honey_keys set status = 'archived', archived_at = ? where id = ?",
                (now, key_id),
            )
            self.conn.execute(
                """
                update honey_incidents
                set archived_reset = 1, updated_at = ?
                where event_id in (select id from honey_key_events where honey_key_id = ?)
                """,
                (now, key_id),
            )
        return self.get_honey_key(key_id)

    def record_honey_key_trigger(
        self,
        *,
        honey_key: dict[str, Any],
        ip_address: str | None,
        user_agent: str | None,
        method: str,
        path: str,
        headers: dict[str, Any],
        body_summary: str | None,
        confidence: float,
        source_type: str,
        approximate_geo: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        event_id = secrets.token_hex(12)
        project_id = str(honey_key["project_id"])
        key_id = str(honey_key["id"])
        status = str(honey_key["status"])
        with self.conn:
            self.conn.execute(
                """
                insert into honey_key_events
                (id, honey_key_id, project_id, repo_id, triggered_at, ip_address, user_agent, method, path, headers_json, body_summary, confidence, source_type, reason, approximate_geo, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    key_id,
                    project_id,
                    honey_key.get("repo_id"),
                    now,
                    ip_address,
                    user_agent,
                    method,
                    path,
                    json.dumps(headers, sort_keys=True),
                    body_summary,
                    confidence,
                    source_type if source_type in {"api_call", "url_open", "unknown"} else "unknown",
                    "Honey Key was accessed or used",
                    approximate_geo,
                    now,
                ),
            )
            self.conn.execute(
                """
                insert into honey_incidents (event_id, created_at, updated_at)
                values (?, ?, ?)
                on conflict(event_id) do nothing
                """,
                (event_id, now, now),
            )
            if status != "archived":
                self.conn.execute(
                    """
                    update honey_keys
                    set status = 'triggered', last_triggered_at = ?, trigger_count = trigger_count + 1
                    where id = ?
                    """,
                    (now, key_id),
                )
                self.conn.execute(
                    """
                    insert into security_project_status (project_id, status, reason, last_event_at)
                    values (?, 'red', 'Honey Key was accessed or used', ?)
                    on conflict(project_id) do update set status = excluded.status, reason = excluded.reason, last_event_at = excluded.last_event_at
                    """,
                    (project_id, now),
                )
            else:
                self.conn.execute(
                    "update honey_keys set last_triggered_at = ?, trigger_count = trigger_count + 1 where id = ?",
                    (now, key_id),
                )
        return self.get_honey_key_event(event_id) or {}

    def get_honey_key_event(self, event_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("select * from honey_key_events where id = ?", (event_id,)).fetchone()
        return _public_honey_event(row) if row else None

    def list_honey_key_events(self, project_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if project_id:
            rows = self.conn.execute(
                "select * from honey_key_events where project_id = ? order by triggered_at desc limit ?",
                (project_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute("select * from honey_key_events order by triggered_at desc limit ?", (limit,)).fetchall()
        incidents = self.honey_incident_map()
        return [_public_honey_event(row, incidents.get(str(row["id"]))) for row in rows]

    def honey_incident_map(self) -> dict[str, dict[str, Any]]:
        return {
            str(row["event_id"]): _public_honey_incident(row)
            for row in self.conn.execute("select * from honey_incidents").fetchall()
        }

    def set_honey_incident_step(self, event_id: str, step: str, complete: bool) -> dict[str, Any]:
        clean_event_id = event_id.strip()
        if step not in {"investigating", "secrets_rotated", "logs_reviewed", "archived_reset"}:
            raise ValueError("Unsupported Honey Key incident step")
        event = self.get_honey_key_event(clean_event_id)
        if not event:
            raise ValueError("Honey Key event not found")
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                insert into honey_incidents (event_id, created_at, updated_at)
                values (?, ?, ?)
                on conflict(event_id) do nothing
                """,
                (clean_event_id, now, now),
            )
            self.conn.execute(
                f"update honey_incidents set {step} = ?, updated_at = ? where event_id = ?",
                (1 if complete else 0, now, clean_event_id),
            )
        return self.honey_incident_map()[clean_event_id]

    def close_honey_incident(self, event_id: str, accepted_risk_note: str | None = None) -> dict[str, Any]:
        clean_event_id = event_id.strip()
        event = self.get_honey_key_event(clean_event_id)
        if not event:
            raise ValueError("Honey Key event not found")
        note = redact_text((accepted_risk_note or "").strip())[:1000] or None
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                insert into honey_incidents (event_id, created_at, updated_at)
                values (?, ?, ?)
                on conflict(event_id) do nothing
                """,
                (clean_event_id, now, now),
            )
            row = self.conn.execute("select * from honey_incidents where event_id = ?", (clean_event_id,)).fetchone()
            if not row:
                raise ValueError("Honey Key incident not found")
            if not row["archived_reset"] and not note:
                raise ValueError("Archive/reset the Honey Key or add an accepted-risk note before closing the incident.")
            self.conn.execute(
                """
                update honey_incidents
                set accepted_risk_note = ?, closed_at = ?, updated_at = ?
                where event_id = ?
                """,
                (note, now, now, clean_event_id),
            )
            project_id = str(event["project_id"])
            open_count = self.conn.execute(
                """
                select count(*) as count
                from honey_key_events e
                left join honey_incidents i on i.event_id = e.id
                where e.project_id = ? and i.closed_at is null
                """,
                (project_id,),
            ).fetchone()["count"]
            if int(open_count) == 0:
                self.conn.execute(
                    """
                    insert into security_project_status (project_id, status, reason, last_event_at)
                    values (?, 'green', 'Honey Key incident closed.', ?)
                    on conflict(project_id) do update set status = excluded.status, reason = excluded.reason, last_event_at = excluded.last_event_at
                    """,
                    (project_id, now),
                )
        return self.honey_incident_map()[clean_event_id]

    def project_statuses(self) -> dict[str, dict[str, Any]]:
        return {row["project_id"]: dict(row) for row in self.conn.execute("select * from security_project_status").fetchall()}


def _sbom_component_row(component: dict[str, Any], scan_id: str, repo_name: str) -> dict[str, Any]:
    row = {
        "scan_id": scan_id,
        "repo_name": repo_name,
        "source_format": _optional_text(component.get("source_format")) or "unknown",
        "source_file": _optional_text(component.get("source_file")),
        "bom_ref": _optional_text(component.get("bom_ref")),
        "name": _optional_text(component.get("name")),
        "version": _optional_text(component.get("version")),
        "ecosystem": _optional_text(component.get("ecosystem")),
        "component_type": _optional_text(component.get("component_type")),
        "package_url": _optional_text(component.get("package_url")),
        "license": _optional_text(component.get("license")),
        "supplier": _optional_text(component.get("supplier")),
        "source_path": _optional_text(component.get("source_path")),
        "component_fingerprint": _optional_text(component.get("component_fingerprint")),
    }
    if not row["component_fingerprint"]:
        row["component_fingerprint"] = component_fingerprint(
            package_url=row["package_url"],
            ecosystem=row["ecosystem"],
            component_type=row["component_type"],
            name=row["name"],
            version=row["version"],
            bom_ref=row["bom_ref"],
        )
    return row


def _dependency_manifest_row(record: dict[str, Any], scan_id: str, repo_name: str) -> dict[str, Any]:
    declaration = _optional_text(record.get("declaration")) or ""
    normalized_declaration = _optional_text(record.get("normalized_declaration")) or declaration.strip().casefold()
    return {
        "scan_id": scan_id,
        "repo_name": repo_name,
        "manifest_path": _optional_text(record.get("manifest_path")) or "manifest",
        "ecosystem": _optional_text(record.get("ecosystem")) or "other",
        "name": _optional_text(record.get("name")) or "unknown",
        "declaration": declaration,
        "normalized_declaration": normalized_declaration,
        "scope": _optional_text(record.get("scope")) or "dependencies",
        "manifest_fingerprint": _optional_text(record.get("manifest_fingerprint")) or "",
    }


def _dependency_trust_row(record: dict[str, Any], scan_id: str, repo_name: str) -> dict[str, Any]:
    return {
        "scan_id": scan_id,
        "repo_name": repo_name,
        "component_fingerprint": _optional_text(record.get("component_fingerprint")),
        "component_package_key": _optional_text(record.get("component_package_key")),
        "package_name": _optional_text(record.get("package_name")),
        "package_version": _optional_text(record.get("package_version")),
        "package_ecosystem": _optional_text(record.get("package_ecosystem")),
        "package_url": _optional_text(record.get("package_url")),
        "source_repo": _optional_text(record.get("source_repo")),
        "source_repo_url": _optional_text(record.get("source_repo_url")),
        "source_repo_confidence": _optional_text(record.get("source_repo_confidence")) or "unknown",
        "source_repo_reason": _optional_text(record.get("source_repo_reason")) or "No source repository resolution was recorded.",
        "scorecard_score": _optional_float(record.get("scorecard_score")),
        "scorecard_status": _optional_text(record.get("scorecard_status")) or "not_checked",
        "criticality_score": _optional_float(record.get("criticality_score")),
        "criticality_status": _optional_text(record.get("criticality_status")) or "not_checked",
        "checked_at": _optional_text(record.get("checked_at")),
        "freshness": _optional_text(record.get("freshness")) or "unknown",
        "status": _optional_text(record.get("status")) or "unknown",
        "cache_key": _optional_text(record.get("cache_key")),
        "error": redact_text(_optional_text(record.get("error")) or "") or None,
    }


def _platform_posture_snapshot_row(snapshot: dict[str, Any], scan_id: str, repo_name: str) -> dict[str, Any]:
    clean_snapshot = dict(snapshot) if isinstance(snapshot, dict) else {}
    if clean_snapshot.get("reason"):
        clean_snapshot["reason"] = redact_text(str(clean_snapshot["reason"]))
    summary = clean_snapshot.get("summary") if isinstance(clean_snapshot.get("summary"), dict) else {}
    fingerprint = _optional_text(clean_snapshot.get("snapshot_fingerprint")) or platform_posture_snapshot_fingerprint(clean_snapshot)
    return {
        "scan_id": scan_id,
        "repo_name": repo_name,
        "scanner": _optional_text(clean_snapshot.get("scanner")) or "legitify",
        "source": _optional_text(clean_snapshot.get("source")) or "legitify",
        "target": _optional_text(clean_snapshot.get("target")) or "repository",
        "status": _optional_text(clean_snapshot.get("status")) or "unknown",
        "summary_json": json.dumps(summary, sort_keys=True),
        "snapshot_json": json.dumps(clean_snapshot, sort_keys=True),
        "snapshot_fingerprint": fingerprint,
    }


def _public_platform_posture_snapshot(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    try:
        summary = json.loads(data.get("summary_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        summary = {}
    try:
        snapshot = json.loads(data.get("snapshot_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        snapshot = {}
    records = snapshot.get("records") if isinstance(snapshot, dict) else []
    reason = snapshot.get("reason") if isinstance(snapshot, dict) else None
    return {
        "id": data.get("id"),
        "scan_id": data.get("scan_id"),
        "repo_name": data.get("repo_name"),
        "scanner": data.get("scanner"),
        "source": data.get("source"),
        "target": data.get("target"),
        "status": data.get("status"),
        "reason": reason,
        "summary": summary if isinstance(summary, dict) else {},
        "records": records if isinstance(records, list) else [],
        "snapshot_fingerprint": data.get("snapshot_fingerprint"),
        "created_at": data.get("created_at"),
    }


def _public_ioc_indicator(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    try:
        versions = json.loads(data.get("versions_json") or "[]")
    except (TypeError, json.JSONDecodeError):
        versions = []
    return {
        "ecosystem": data.get("ecosystem"),
        "name": data.get("name"),
        "versions": versions if isinstance(versions, list) else [],
        "namespace_prefix": data.get("namespace_prefix"),
        "domain": data.get("domain"),
        "confidence": data.get("confidence"),
        "source_file": data.get("source_file"),
        "source_line": data.get("source_line"),
    }


def _public_agent_lab_proposal(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    final_plan = _json_load(data.get("final_execution_plan_json"), {})
    if isinstance(final_plan, dict):
        final_plan["approval_state"] = data.get("approval_state")
    return {
        "id": data.get("id"),
        "external_proposal_id": data.get("external_proposal_id"),
        "repo_name": data.get("repo_name"),
        "repo_path": data.get("repo_path"),
        "context_id": data.get("context_id"),
        "context_hash": data.get("context_hash"),
        "source": {
            "adapter_id": data.get("adapter_id"),
            "agent_label": data.get("agent_label"),
            "created_at": data.get("agent_created_at"),
        },
        "summary": data.get("summary"),
        "recommended_tools": _json_load(data.get("recommended_tools_json"), []),
        "recommended_packs": _json_load(data.get("recommended_packs_json"), []),
        "requested_permissions": _json_load(data.get("requested_permissions_json"), []),
        "requested_execution": _json_load(data.get("requested_execution_json"), []),
        "expected_evidence_gaps": _json_load(data.get("expected_evidence_gaps_json"), []),
        "blocked_requests": _json_load(data.get("blocked_requests_json"), []),
        "notes": data.get("notes"),
        "validation_status": data.get("validation_status"),
        "validation_errors": _json_load(data.get("validation_errors_json"), []),
        "approval_state": data.get("approval_state"),
        "approval_note": data.get("approval_note"),
        "decided_by": data.get("decided_by"),
        "imported_at": data.get("imported_at"),
        "updated_at": data.get("updated_at"),
        "approved_at": data.get("approved_at"),
        "denied_at": data.get("denied_at"),
        "raw_proposal": _json_load(data.get("raw_proposal_json"), {}),
        "final_execution_plan": final_plan,
    }


def _public_fix_proposal(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data.get("id"),
        "repo_name": data.get("repo_name"),
        "repo_path": data.get("repo_path"),
        "case_id": data.get("case_id"),
        "base_branch": data.get("base_branch"),
        "head_branch": data.get("head_branch"),
        "title": data.get("title"),
        "diff": data.get("diff"),
        "diff_sha256": data.get("diff_sha256"),
        "fix_class": data.get("fix_class"),
        "auto_merge_eligible": bool(data.get("auto_merge_eligible")),
        "classification": _json_load(data.get("classification_json"), {}),
        "source": data.get("source"),
        "status": data.get("status"),
        "clean_room_status": data.get("clean_room_status"),
        "clean_room_reviewer": data.get("clean_room_reviewer"),
        "clean_room_checked_invariants": _json_load(data.get("clean_room_checked_invariants_json"), []),
        "clean_room_notes": data.get("clean_room_notes"),
        "clean_room_diff_sha256": data.get("clean_room_diff_sha256"),
        "clean_room_reviewed_at": data.get("clean_room_reviewed_at"),
        "landing_outcome": data.get("landing_outcome"),
        "landing_reasons": _json_load(data.get("landing_reasons_json"), []),
        "landing_decided_at": data.get("landing_decided_at"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def _public_case_resolution_run(
    row: sqlite3.Row | dict[str, Any],
    item_rows: list[sqlite3.Row | dict[str, Any]],
) -> dict[str, Any]:
    data = dict(row)
    summary = _json_load(data.get("summary_json"), {})
    items = [_public_case_resolution_item(item) for item in item_rows]
    return {
        "id": data.get("id"),
        "run_id": data.get("id"),
        "repo": data.get("repo_name"),
        "repo_name": data.get("repo_name"),
        "scan_id": data.get("scan_id"),
        "action": data.get("action"),
        "scope": data.get("scope"),
        "source": data.get("source"),
        "imported_at": data.get("imported_at"),
        "applied_at": data.get("applied_at"),
        "status": data.get("status"),
        "summary": summary,
        "items": items,
    }


def _public_case_resolution_item(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    case_id = str(data.get("case_id") or "")
    display_tail = re.sub(r"[^A-Za-z0-9]", "", case_id)[-4:].upper() or "0000"
    return {
        "id": data.get("id"),
        "run_id": data.get("run_id"),
        "case_id": case_id,
        "display_id": f"F-{display_tail}",
        "repo_name": data.get("repo_name"),
        "scan_id": data.get("scan_id"),
        "ai_disposition": data.get("ai_disposition"),
        "disposition": data.get("ai_disposition"),
        "mapped_decision": data.get("mapped_decision"),
        "confidence": data.get("confidence"),
        "reason": data.get("reason"),
        "evidence": _json_load(data.get("evidence_json"), []),
        "recommended_next_step": data.get("recommended_next_step"),
        "applied_decision": _json_load(data.get("applied_decision_json"), {}) if data.get("applied_decision_json") else None,
        "status": data.get("status"),
        "warning": data.get("warning"),
        "created_at": data.get("created_at"),
    }


def _json(value: Any) -> str:
    return json.dumps(sanitize_json(value), sort_keys=True)


def _json_load(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _list_text(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = _optional_text(value)
    return [text] if text else []


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _decision_text(value: Any) -> str | None:
    text = _optional_text(value)
    return redact_text(text)[:1000] if text else None


def _dedupe_text(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _counts_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _case_counts(cases: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts = {
        "action_level": {},
        "severity": {},
        "category": {},
    }
    for case in cases:
        for key in counts:
            value = str(case.get(key) or "unknown")
            counts[key][value] = counts[key].get(value, 0) + 1
    return counts


def _scan_endpoint_meta(row: sqlite3.Row) -> dict[str, Any]:
    """Public metadata for one endpoint of a scan diff (base or head)."""
    return {
        "scan_id": row["id"],
        "repo_name": row["repo_name"],
        "profile": row["profile"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "health_score": row["health_score"],
        "status": row["status"],
    }


def _scan_delta(latest: sqlite3.Row, previous: dict[str, Any] | None) -> dict[str, Any]:
    latest_cases = [item for item in _decode_cases(latest["cases_json"]) if isinstance(item, dict)]
    latest_ids = {_case_identity(item) for item in latest_cases}
    if not previous:
        return {
            "previous_scan_id": None,
            "previous_health": None,
            "health_delta": None,
            "case_changes": {case_id: "new" for case_id in latest_ids if case_id},
            "new_cases": len([case_id for case_id in latest_ids if case_id]),
            "recurring_cases": 0,
            "resolved_count": 0,
            "resolved_cases": [],
        }

    previous_cases = [item for item in _decode_cases(previous["cases_json"]) if isinstance(item, dict)]
    previous_by_id = {_case_identity(item): item for item in previous_cases if _case_identity(item)}
    previous_ids = set(previous_by_id)
    case_changes = {
        case_id: "recurring" if case_id in previous_ids else "new"
        for case_id in latest_ids
        if case_id
    }
    resolved_ids = sorted(previous_ids - latest_ids)
    resolved_cases = []
    for case_id in resolved_ids:
        case = dict(previous_by_id[case_id])
        case["scan_id"] = previous["id"]
        case["repo"] = previous["repo_name"]
        case["repo_name"] = previous["repo_name"]
        case["change_status"] = "resolved"
        case["previous_scan_id"] = previous["id"]
        # Closure proof (S-035): bind the resolved case to the scan + diff entry
        # that closed it instead of closing by disappearance. The case itself is
        # the diff `resolved[]` entry; `resolved_by_scan_id` names the rescan
        # that proved it gone, and `lifecycle_state` reads `resolved`.
        case["resolved_by_scan_id"] = latest["id"]
        case["resolved_at"] = latest["finished_at"] or latest["started_at"]
        case["lifecycle_state"] = lifecycle.RESOLVED
        case["next_step"] = (
            f"Verified — this case was not found in scan {latest['id']}, "
            "which is the rescan that closed it. Watch future scans for recurrence."
        )
        resolved_cases.append(case)

    return {
        "previous_scan_id": previous["id"],
        "previous_health": previous["health_score"],
        "health_delta": int(latest["health_score"]) - int(previous["health_score"]),
        "case_changes": case_changes,
        "new_cases": sum(1 for value in case_changes.values() if value == "new"),
        "recurring_cases": sum(1 for value in case_changes.values() if value == "recurring"),
        "resolved_count": len(resolved_cases),
        "resolved_cases": resolved_cases,
    }


DEPENDENCY_RISK_MOVEMENTS = (
    "vulnerability-introduced",
    "vulnerability-fixed",
    "recurring-risk",
    "unknown",
)


def _dependency_risk_movements(
    latest: sqlite3.Row,
    previous: dict[str, Any] | None,
    delta: dict[str, Any],
    dependency_delta: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    latest_cases = [item for item in _decode_cases(latest["cases_json"]) if isinstance(item, dict)]
    previous_cases = [item for item in _decode_cases(previous["cases_json"]) if isinstance(item, dict)] if previous else []
    previous_dependency_keys = {
        key
        for key in (_dependency_case_key(case) for case in previous_cases)
        if key
    }
    changes_by_package_key = {
        str(change.get("package_key")): change
        for change in dependency_delta.get("changes", [])
        if isinstance(change, dict) and change.get("package_key")
    }
    movements: dict[str, dict[str, Any]] = {}

    for case in latest_cases:
        case_id = _case_identity(case)
        if not case_id or case.get("category") != "dependencies":
            continue
        case_key = _dependency_case_key(case)
        dependency_change = _case_dependency_change(case, changes_by_package_key)
        if case_key and case_key in previous_dependency_keys:
            movements[case_id] = _risk_movement(
                "recurring-risk",
                "This issue was also present in the previous scan.",
                dependency_change,
            )
        elif previous and dependency_change:
            movements[case_id] = _risk_movement(
                "vulnerability-introduced",
                _introduced_reason(dependency_change),
                dependency_change,
            )
        else:
            movements[case_id] = _risk_movement(
                "unknown",
                "This issue is present now, but there is not enough package history to say what changed.",
                dependency_change,
            )

    for case in delta.get("resolved_cases", []):
        if not isinstance(case, dict) or case.get("category") != "dependencies":
            continue
        case_id = _case_identity(case)
        if not case_id:
            continue
        dependency_change = _case_dependency_change(case, changes_by_package_key)
        if dependency_change:
            movements[case_id] = _risk_movement(
                "vulnerability-fixed",
                _fixed_reason(dependency_change),
                dependency_change,
            )
        else:
            movements[case_id] = _risk_movement(
                "unknown",
                "The latest scan no longer finds this issue, but the package change that removed it is not clear.",
                None,
            )
    return movements


def _dependency_risk_counts(movements: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {movement: 0 for movement in DEPENDENCY_RISK_MOVEMENTS}
    for movement in movements.values():
        key = str(movement.get("risk_movement") or "unknown")
        counts[key if key in counts else "unknown"] += 1
    return counts


def _attach_dependency_risk_movement(case: dict[str, Any], movement: dict[str, Any] | None) -> None:
    if not movement:
        return
    case.update(movement)
    reason = str(movement.get("risk_movement_reason") or "")
    if reason:
        existing = str(case.get("plain_english_risk") or "")
        if reason not in existing:
            case["plain_english_risk"] = f"{existing} {reason}".strip()
    if movement.get("risk_movement") == "vulnerability-fixed":
        case["next_step"] = "This issue was not found in the latest scan. Keep the package change and watch future scans."


def _risk_movement(label: str, reason: str, dependency_change: dict[str, Any] | None) -> dict[str, Any]:
    movement = label if label in DEPENDENCY_RISK_MOVEMENTS else "unknown"
    return {
        "risk_movement": movement,
        "risk_movement_label": {
            "vulnerability-introduced": "Vulnerability introduced",
            "vulnerability-fixed": "Vulnerability fixed",
            "recurring-risk": "Recurring risk",
            "unknown": "Unknown",
        }[movement],
        "risk_movement_reason": reason,
        "dependency_change": dependency_change,
    }


def _introduced_reason(change: dict[str, Any]) -> str:
    name = str(change.get("name") or "this package")
    previous_version = change.get("previous_version")
    current_version = change.get("current_version")
    change_type = str(change.get("change_type") or "")
    if change_type == "added":
        return f"This looks new because {name} was added in this scan."
    if previous_version and current_version:
        return f"This looks new after {name} changed from {previous_version} to {current_version}."
    return f"This looks new after {name} changed."


def _fixed_reason(change: dict[str, Any]) -> str:
    name = str(change.get("name") or "this package")
    previous_version = change.get("previous_version")
    current_version = change.get("current_version")
    change_type = str(change.get("change_type") or "")
    if change_type == "removed":
        return f"The latest scan no longer finds this issue after {name} was removed."
    if previous_version and current_version:
        return f"The latest scan no longer finds this issue after {name} changed from {previous_version} to {current_version}."
    return f"The latest scan no longer finds this issue after {name} changed."


def _case_dependency_change(case: dict[str, Any], changes_by_package_key: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for package_key in _case_package_keys(case):
        change = changes_by_package_key.get(package_key)
        if change:
            return change
    return None


def _case_package_keys(case: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for evidence in case.get("evidence", []):
        if not isinstance(evidence, dict):
            continue
        direct = _optional_text(evidence.get("component_package_key"))
        if direct and direct not in keys:
            keys.append(direct)
        derived = _component_package_key(evidence)
        if derived and derived not in keys:
            keys.append(derived)
    return keys


def _dependency_case_key(case: dict[str, Any]) -> str | None:
    vulnerability = _case_vulnerability(case)
    package = _case_package(case)
    if vulnerability and package:
        return f"{vulnerability}:{package}"
    if vulnerability:
        return vulnerability
    return None


def _case_vulnerability(case: dict[str, Any]) -> str | None:
    for evidence in case.get("evidence", []):
        if isinstance(evidence, dict) and evidence.get("vulnerability_id"):
            return str(evidence["vulnerability_id"]).upper()
    title = str(case.get("title") or "")
    match = re.search(r"\b(?:CVE-\d{4}-\d+|GHSA-[A-Za-z0-9-]+|PYSEC-\d{4}-\d+|OSV-\d+)\b", title, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _case_package(case: dict[str, Any]) -> str | None:
    for evidence in case.get("evidence", []):
        if isinstance(evidence, dict) and evidence.get("package_name"):
            return str(evidence["package_name"]).casefold()
    title = str(case.get("title") or "")
    match = re.match(r"(.+?) dependency vulnerability", title, re.IGNORECASE)
    return match.group(1).casefold() if match else None


DEPENDENCY_DELTA_TYPES = ("added", "removed", "upgraded", "downgraded", "version-changed", "license-changed")
DEPENDENCY_VULNERABILITY_SCANNERS = {"trivy", "osv-scanner", "grype"}


def _dependency_delta(
    latest: sqlite3.Row,
    previous: dict[str, Any] | None,
    current_components: list[dict[str, Any]],
    previous_components: list[dict[str, Any]],
    current_dependency_findings: list[dict[str, Any]],
    current_manifest_entries: list[dict[str, Any]] | None = None,
    previous_manifest_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    counts = {change_type: 0 for change_type in DEPENDENCY_DELTA_TYPES}
    base = {
        "repo_name": latest["repo_name"],
        "scan_id": latest["id"],
        "previous_scan_id": previous["id"] if previous else None,
        "has_previous_scan": bool(previous),
        "current_count": len(current_components),
        "previous_count": len(previous_components) if previous else 0,
        "counts": counts,
        "changes": [],
        "cve_counts": {"has-cve": 0, "no-cve": 0, "not-checked": 0, "unknown": 0},
        "comparison_explanation": "",
    }

    if not current_components:
        return {
            **base,
            "status": "no-sbom",
            "comparison_explanation": "The latest scan did not save an SBOM, so package changes could not be compared.",
        }
    if not previous:
        return {
            **base,
            "status": "first-scan",
            "comparison_explanation": "This scan saved a package inventory. A second scan of the same repo is needed for change comparison.",
        }

    current_by_key = _component_snapshot(current_components)
    previous_by_key = _component_snapshot(previous_components)
    changes: list[dict[str, Any]] = []

    for package_key in sorted(current_by_key.keys() - previous_by_key.keys()):
        _append_dependency_change(
            changes,
            counts,
            package_key=package_key,
            change_types=["added"],
            current=current_by_key[package_key],
            previous=None,
            latest=latest,
            previous_scan=previous,
        )

    for package_key in sorted(previous_by_key.keys() - current_by_key.keys()):
        _append_dependency_change(
            changes,
            counts,
            package_key=package_key,
            change_types=["removed"],
            current=None,
            previous=previous_by_key[package_key],
            latest=latest,
            previous_scan=previous,
        )

    for package_key in sorted(current_by_key.keys() & previous_by_key.keys()):
        current = current_by_key[package_key]
        previous_component = previous_by_key[package_key]
        change_types: list[str] = []
        if _component_value(current.get("version")) != _component_value(previous_component.get("version")):
            change_types.append("version-changed")
            comparison = _compare_versions(previous_component.get("version"), current.get("version"))
            if comparison is not None and comparison < 0:
                change_types.append("upgraded")
            elif comparison is not None and comparison > 0:
                change_types.append("downgraded")
        if _component_value(current.get("license")) != _component_value(previous_component.get("license")):
            change_types.append("license-changed")
        if change_types:
            _append_dependency_change(
                changes,
                counts,
                package_key=package_key,
                change_types=change_types,
                current=current,
                previous=previous_component,
                latest=latest,
                previous_scan=previous,
            )

    vulnerability_check = _dependency_vulnerability_check(latest)
    finding_keys = _dependency_finding_package_keys(current_dependency_findings)
    finding_names = _dependency_finding_package_names(current_dependency_findings)
    annotate_dependency_changes(changes, current_manifest_entries or [], previous_manifest_entries or [])
    for change in changes:
        _annotate_dependency_change(change, vulnerability_check, finding_keys, finding_names)

    cve_counts = {"has-cve": 0, "no-cve": 0, "not-checked": 0, "unknown": 0}
    for change in changes:
        status = str(change.get("cve_status") or "unknown")
        cve_counts[status if status in cve_counts else "unknown"] += 1

    return {
        **base,
        "status": "changed" if changes else "unchanged",
        "counts": counts,
        "cve_counts": cve_counts,
        "comparison_explanation": (
            "Dependency changes were compared with the previous SBOM."
            if changes
            else "The latest SBOM matches the previous saved package inventory."
        ),
        "changes": sorted(changes, key=_dependency_change_sort_key),
    }


def _component_snapshot(components: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for component in components:
        public_component = _public_component(component)
        package_key = str(public_component["package_key"])
        existing = snapshot.get(package_key)
        if not existing or _component_sort_key(public_component) < _component_sort_key(existing):
            snapshot[package_key] = public_component
    return snapshot


def _public_component(component: dict[str, Any]) -> dict[str, Any]:
    package_key = _component_package_key(component)
    return {
        "package_key": package_key,
        "name": component.get("name"),
        "version": component.get("version"),
        "ecosystem": component.get("ecosystem"),
        "component_type": component.get("component_type"),
        "package_url": component.get("package_url"),
        "license": component.get("license"),
        "supplier": component.get("supplier"),
        "source_path": component.get("source_path"),
        "source_format": component.get("source_format"),
        "source_file": component.get("source_file"),
        "bom_ref": component.get("bom_ref"),
        "component_fingerprint": component.get("component_fingerprint"),
    }


def _append_dependency_change(
    changes: list[dict[str, Any]],
    counts: dict[str, int],
    *,
    package_key: str,
    change_types: list[str],
    current: dict[str, Any] | None,
    previous: dict[str, Any] | None,
    latest: sqlite3.Row,
    previous_scan: dict[str, Any],
) -> None:
    unique_types = [change_type for change_type in DEPENDENCY_DELTA_TYPES if change_type in set(change_types)]
    for change_type in unique_types:
        counts[change_type] += 1
    changes.append(
        {
            "repo_name": latest["repo_name"],
            "scan_id": latest["id"],
            "previous_scan_id": previous_scan["id"],
            "package_key": package_key,
            "change_type": _primary_dependency_change_type(unique_types),
            "change_types": unique_types,
            "name": (current or previous or {}).get("name"),
            "ecosystem": (current or previous or {}).get("ecosystem"),
            "component_type": (current or previous or {}).get("component_type"),
            "package_url": (current or previous or {}).get("package_url"),
            "source_path": (current or previous or {}).get("source_path"),
            "previous_version": previous.get("version") if previous else None,
            "current_version": current.get("version") if current else None,
            "previous_license": previous.get("license") if previous else None,
            "current_license": current.get("license") if current else None,
            "version_changed": "version-changed" in unique_types,
            "license_changed": "license-changed" in unique_types,
            "version_direction": _version_direction(unique_types),
            "previous_component": previous,
            "current_component": current,
        }
    )


def _annotate_dependency_change(
    change: dict[str, Any],
    vulnerability_check: dict[str, Any],
    finding_keys: set[str],
    finding_names: set[str],
) -> None:
    match_confidence = _dependency_change_match_confidence(change)
    metadata_warnings = _dependency_change_metadata_warnings(change)
    has_matching_finding = str(change.get("package_key") or "") in finding_keys
    name = _component_value(change.get("name"))
    if name and name in finding_names:
        has_matching_finding = True

    if has_matching_finding:
        cve_status = "has-cve"
        cve_reason = "A dependency vulnerability finding matched this package change."
    elif vulnerability_check["status"] != "checked":
        cve_status = "not-checked"
        cve_reason = "No dependency vulnerability scanner completed for this scan."
    elif match_confidence == "unknown":
        cve_status = "unknown"
        cve_reason = "Package metadata is too incomplete to compare confidently with vulnerability findings."
    else:
        cve_status = "no-cve"
        cve_reason = "Dependency vulnerability scanners ran and did not report a matching CVE for this package change."

    change["match_confidence"] = match_confidence
    change["match_label"] = {
        "strong": "Strong match",
        "weak-match": "Weak match",
        "unknown": "Unknown",
    }[match_confidence]
    change["metadata_warnings"] = metadata_warnings
    change["cve_status"] = cve_status
    change["cve_label"] = {
        "has-cve": "Known CVE",
        "no-cve": "No CVE found",
        "not-checked": "Not checked",
        "unknown": "Unknown",
    }[cve_status]
    change["cve_reason"] = cve_reason
    change["checked_by"] = vulnerability_check["scanners"]


def _dependency_vulnerability_check(scan: sqlite3.Row) -> dict[str, Any]:
    try:
        scanner_statuses = json.loads(scan["scanner_status_json"])
    except (KeyError, TypeError, json.JSONDecodeError):
        scanner_statuses = []
    checked_by = []
    for scanner in scanner_statuses:
        if not isinstance(scanner, dict):
            continue
        name = str(scanner.get("scanner") or "").casefold()
        if name not in DEPENDENCY_VULNERABILITY_SCANNERS:
            continue
        status = str(scanner.get("status") or "").casefold()
        skipped = any(token in status for token in ("skip", "missing", "unavailable", "error"))
        if scanner.get("available") and not scanner.get("error") and not skipped:
            checked_by.append(str(scanner.get("scanner") or name))
    return {"status": "checked" if checked_by else "not-checked", "scanners": sorted(set(checked_by))}


def _dependency_finding_package_keys(findings: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for finding in findings:
        direct = _optional_text(finding.get("component_package_key"))
        if direct:
            keys.add(direct)
        if not any((finding.get("package_url"), finding.get("package_ecosystem"), finding.get("package_name"), finding.get("component_fingerprint"))):
            continue
        package_key = _component_package_key(
            {
                "package_url": finding.get("package_url"),
                "ecosystem": finding.get("package_ecosystem"),
                "component_type": None,
                "name": finding.get("package_name"),
                "bom_ref": None,
                "component_fingerprint": finding.get("component_fingerprint"),
            }
        )
        if package_key:
            keys.add(package_key)
    return keys


def _dependency_finding_package_names(findings: list[dict[str, Any]]) -> set[str]:
    return {
        name
        for name in (_component_value(finding.get("package_name")) for finding in findings)
        if name
    }


def _dependency_change_match_confidence(change: dict[str, Any]) -> str:
    component = change.get("current_component") or change.get("previous_component") or {}
    if not isinstance(component, dict):
        return "unknown"
    if component.get("package_url"):
        return "strong"
    if component.get("name"):
        return "weak-match"
    return "unknown"


def _dependency_change_metadata_warnings(change: dict[str, Any]) -> list[str]:
    component = change.get("current_component") or change.get("previous_component") or {}
    if not isinstance(component, dict):
        return ["Unknown metadata"]
    warnings: list[str] = []
    if not component.get("name"):
        warnings.append("Unknown package")
    if not (change.get("current_version") or change.get("previous_version")):
        warnings.append("Missing version")
    if not component.get("package_url"):
        warnings.append("Missing purl")
    if not (component.get("ecosystem") or _ecosystem_from_package_url(component.get("package_url"))):
        warnings.append("Unknown ecosystem")
    return warnings


def _primary_dependency_change_type(change_types: list[str]) -> str:
    for change_type in ("added", "removed", "upgraded", "downgraded", "version-changed", "license-changed"):
        if change_type in change_types:
            return change_type
    return "version-changed"


def _version_direction(change_types: list[str]) -> str | None:
    if "upgraded" in change_types:
        return "upgraded"
    if "downgraded" in change_types:
        return "downgraded"
    if "version-changed" in change_types:
        return "changed"
    return None


def _dependency_change_sort_key(change: dict[str, Any]) -> tuple[int, str, str]:
    rank = {
        "added": 0,
        "upgraded": 1,
        "downgraded": 2,
        "version-changed": 3,
        "license-changed": 4,
        "removed": 5,
    }
    return (
        rank.get(str(change.get("change_type")), 99),
        str(change.get("ecosystem") or ""),
        str(change.get("name") or change.get("package_key") or "").casefold(),
    )


def _component_sort_key(component: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(component.get("name") or "").casefold(),
        str(component.get("version") or "").casefold(),
        str(component.get("source_path") or "").casefold(),
        str(component.get("package_url") or "").casefold(),
    )


def _component_package_key(component: dict[str, Any]) -> str:
    package_url = _optional_text(component.get("package_url"))
    if package_url:
        return f"purl|{_package_url_without_version(package_url).casefold()}"
    ecosystem = _component_value(component.get("ecosystem"))
    component_type = _component_value(component.get("component_type"))
    name = _component_value(component.get("name"))
    if any((ecosystem, component_type, name)):
        return "|".join(["component", ecosystem, component_type, name])
    bom_ref = _component_value(component.get("bom_ref"))
    if bom_ref:
        return f"bom-ref|{bom_ref}"
    return f"fingerprint|{_component_value(component.get('component_fingerprint'))}"


def _package_url_without_version(package_url: str) -> str:
    base = package_url.split("?", 1)[0].split("#", 1)[0]
    if "@" not in base:
        return base
    head, tail = base.rsplit("@", 1)
    return head if "/" not in tail else base


def _ecosystem_from_package_url(package_url: Any) -> str | None:
    text = _optional_text(package_url)
    if not text or not text.startswith("pkg:"):
        return None
    return text[4:].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0] or None


def _component_value(value: Any) -> str:
    return str(value or "").strip().casefold()


def _compare_versions(previous: Any, current: Any) -> int | None:
    previous_tokens = _version_tokens(previous)
    current_tokens = _version_tokens(current)
    if previous_tokens is None or current_tokens is None:
        return None
    max_length = max(len(previous_tokens), len(current_tokens))
    padded_previous = [*previous_tokens, *([0] * (max_length - len(previous_tokens)))]
    padded_current = [*current_tokens, *([0] * (max_length - len(current_tokens)))]
    for previous_token, current_token in zip(padded_previous, padded_current):
        if previous_token == current_token:
            continue
        if isinstance(previous_token, int) and isinstance(current_token, int):
            return -1 if previous_token < current_token else 1
        if isinstance(previous_token, int):
            return 1
        if isinstance(current_token, int):
            return -1
        return -1 if str(previous_token) < str(current_token) else 1
    return 0


def _version_tokens(value: Any) -> list[int | str] | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    raw_tokens = re.findall(r"\d+|[a-z]+", text.lstrip("v"))
    if not raw_tokens or not any(token.isdigit() for token in raw_tokens):
        return None
    return [int(token) if token.isdigit() else token for token in raw_tokens]


def _case_identity(case: dict[str, Any]) -> str:
    return str(case.get("case_id") or case.get("id") or "").strip()


def _attach_case_decision(case: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> None:
    case_id = _case_identity(case)
    decision = decisions.get(case_id)
    if decision:
        case["decision"] = decision
    _attach_lifecycle_state(case)


def _attach_lifecycle_state(case: dict[str, Any]) -> None:
    """Stamp the canonical lifecycle state on a case from its decision + diff.

    Lets the dashboard show the verifying beat: a ``fixed`` decision on a case
    that still appears reads ``in_progress`` (awaiting rescan proof), and a case
    a rescan no longer found reads ``resolved`` bound to the closing scan.
    """
    decision_status = (case.get("decision") or {}).get("status")
    case["lifecycle_state"] = lifecycle.lifecycle_state(
        decision_status, diff_status=case.get("change_status")
    )


def _public_managed_tool(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["active"] = bool(data.get("active"))
    try:
        data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
    except json.JSONDecodeError:
        data["metadata"] = {}
    return data


def _public_honey_key(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data.pop("token_hash", None)
    return data


def _public_honey_incident(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for key in ("investigating", "secrets_rotated", "logs_reviewed", "archived_reset"):
        data[key] = bool(data[key])
    return data


def _public_honey_event(row: sqlite3.Row, incident: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dict(row)
    data["headers"] = json.loads(data.pop("headers_json") or "{}")
    data["incident"] = incident
    return data


def _latest_honey_events_by_project(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        project_id = str(event.get("project_id"))
        if project_id and project_id not in latest:
            latest[project_id] = event
    return latest


def _honey_event_case(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": f"honey-key-{event.get('id')}",
        "repo": event.get("project_id"),
        "repo_name": event.get("project_id"),
        "title": "Honey Key triggered",
        "plain_english_risk": "A decoy secret was touched, which means a sensitive location in the codebase may have been accessed.",
        "action_level": "fix_now",
        "confidence": "high",
        "category": "honeytokens",
        "severity": "critical",
        "affected_files": [],
        "evidence": [
            {
                "scanner": "Honey Keys",
                "title": "Decoy secret touched",
                "location": event.get("path") or "Honey Key trigger endpoint",
            }
        ],
        "scanners": ["Honey Keys"],
        "fix_steps": [
            "Check whether this repo was public, leaked, cloned, scraped, or accessed unexpectedly.",
            "Review recent commits, CI logs, deploy logs, dependency activity, and access logs.",
            "Rotate real secrets in this repo if exposure is plausible.",
            "Review third-party integrations and AI-agent activity.",
            "Archive or reset the Honey Key after investigation.",
        ],
        "agent_prompt": "Investigate possible unauthorized access after a Honey Key was accessed or used.",
        "source_fingerprints": [str(event.get("id"))],
        "next_step": "Investigate possible unauthorized access and rotate real secrets if exposure is plausible.",
        "created_at": event.get("triggered_at"),
        "honey_key_id": event.get("honey_key_id"),
        "honey_event_id": event.get("id"),
        "incident": event.get("incident"),
    }
