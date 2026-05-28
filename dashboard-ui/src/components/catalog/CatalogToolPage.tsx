// Catalog Tool detail — matches mockup (1): paper hero with back link, icon,
// label, "Verified · by DëvSec Core" eyebrow, and a single primary action
// (Install). Two-column body underneath — Overview + Core capabilities on the
// left, Technical specs + Read documentation sidebar on the right. Policy,
// safety, and setup detail live below the fold so the first screen stays calm.
//
// Routing decisions (consistent with DESIGN.md §0 and §4):
//   - One primary action on the page (Install). No secondary "snooze" /
//     "later" affordance — DëvSec doesn't have a snooze concept and a button
//     that just goes Back is a lie.
//   - Install is enabled only when the install_preview is a real managed
//     install path with execution_available. For everything else the button
//     keeps the next-step copy and is visually quieter (no fake affordance).
//   - Display-only tools (External Surface, lifecycle/install_state =
//     coming-soon) get no Install — the action region is a single calm note
//     instead.
//
// Honesty about specs (open question from the campaign): the mockup shows
// Version / Size / Last Updated / License / Requirements. DëvSec only
// genuinely knows the managed-install target version today; everything else
// is unknown. We surface what's real and show "—" with a TODO for the rest
// rather than fabricate plausible-looking values.

import {useCallback, useMemo, useState} from 'react';
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleSlash,
  Clipboard,
  ClipboardCheck,
  Download,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import {DashboardSummary, ToolCatalogItem, formatRelativeTime} from '../../dashboardData';
import {humanizeKey} from '../../uiHelpers';
import {
  canInstallViaPackageManager,
  catalogCapabilityLabels,
  catalogCategoryLabels,
  catalogCredentialLabels,
  catalogInstallDetectionLabels,
  catalogInstallLabels,
  catalogInstallMethodLabels,
  catalogInstallOwnerLabels,
  catalogNetworkLabels,
  catalogPackLabels,
  catalogPolicySummary,
  catalogProfileRole,
  catalogTargetLabels,
  catalogUninstallLabels,
  isManualInstall,
  packageManagerCommand,
  previewCanInstall,
  toolAccent,
  toolLogo,
} from './catalogHelpers';
import {useCatalogData} from './useCatalogData';
import SetupCard from './SetupCard';

export type CatalogToolPageProps = {
  summary: DashboardSummary;
  onRefresh: () => Promise<void>;
  toolId: string;
  onBack: () => void;
};

type Spec = {label: string; value: string; mono?: boolean};

function isDisplayOnly(tool: ToolCatalogItem): boolean {
  return tool.lifecycle === 'coming-soon' || tool.install_state === 'coming-soon';
}

// Tools that are already on the user's machine — either built into DëvSec,
// detected on PATH, owned by a verified DëvSec-managed install, or installed
// but needing further config (e.g. an env-var credential). None of these need
// a hero Install CTA; an Install button on a tool that's already installed is
// the F-004 lie.
function isAlreadyInstalled(tool: ToolCatalogItem): boolean {
  return (
    tool.install_state === 'built-in' ||
    tool.install_state === 'detected' ||
    tool.install_state === 'managed' ||
    tool.install_state === 'not-configured'
  );
}

// Specs the mockup asks for. Only Version and Requirements have real backing
// today; the rest are honest blanks with a TODO so the gap is visible to the
// next person who touches this file.
function specsFor(tool: ToolCatalogItem): Spec[] {
  const version = tool.install_preview?.target_version_label
    ?? tool.install_preview?.target_version
    ?? '—';
  return [
    {label: 'Version', value: version, mono: true},
    // TODO: needs ToolInstallPreview.install_size_bytes (or similar) from the
    // managed-install backend; today no field carries an install size.
    {label: 'Size', value: '—', mono: true},
    // TODO: needs ToolInstallPreview.updated_at / ToolCatalogEntry.updated_at
    // — neither is published yet.
    {label: 'Last updated', value: '—', mono: true},
    // TODO: needs ToolCatalogEntry.license — not in the catalog schema yet.
    {label: 'License', value: '—', mono: true},
    {label: 'Requirements', value: catalogInstallMethodLabels[tool.install.method]},
  ];
}

export default function CatalogToolPage({summary, onRefresh, toolId, onBack}: CatalogToolPageProps) {
  const {
    catalog,
    runtime,
    mutation,
    installManagedTool,
    installViaPackageManager,
    markManualInstall,
  } = useCatalogData(summary, onRefresh);
  const tool = useMemo(() => catalog.find((item) => item.id === toolId), [catalog, toolId]);
  const runtimeItem = useMemo(
    () => (tool?.scanner_key ? runtime.get(tool.scanner_key) : undefined),
    [runtime, tool],
  );

  // Package-manager tools (homebrew, uv-tool) that are not installed can be
  // installed via /api/tools/install-via-pkg on the user's behalf. The
  // binary name comes from the catalog, not user input, so it isn't
  // shell-injectable.
  const packageInstallable = tool ? canInstallViaPackageManager(tool) : false;
  const managedInstallable = tool ? previewCanInstall(tool.install_preview) : false;
  const manualInstallable = tool ? isManualInstall(tool) : false;
  const installEnabled = managedInstallable || packageInstallable;
  const pkgCommand = tool ? packageManagerCommand(tool) : null;
  const displayOnly = tool ? isDisplayOnly(tool) : false;
  const alreadyInstalled = tool ? isAlreadyInstalled(tool) : false;
  const mutating = tool && mutation?.toolId === tool.id && mutation.status === 'running';
  const installLabel = mutating
    ? 'Installing...'
    : packageInstallable && pkgCommand
      ? `Install (${pkgCommand})`
      : 'Install plugin';

  const onInstall = useCallback(() => {
    if (!tool || !installEnabled) return;
    if (packageInstallable) {
      void installViaPackageManager(tool.id);
      return;
    }
    void installManagedTool(tool.id);
  }, [tool, installEnabled, packageInstallable, installManagedTool, installViaPackageManager]);

  const onMarkInstalled = useCallback(() => {
    if (!tool || !manualInstallable) return;
    void markManualInstall(tool.id);
  }, [tool, manualInstallable, markManualInstall]);

  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle');
  const manualCommandText = useMemo(() => {
    if (!tool) return '';
    return tool.install.instructions ?? tool.install.next_step ?? '';
  }, [tool]);
  const onCopyCommand = useCallback(() => {
    if (!manualCommandText) return;
    const reset = () => window.setTimeout(() => setCopyState('idle'), 2000);
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(manualCommandText).then(
        () => {
          setCopyState('copied');
          reset();
        },
        () => {
          setCopyState('error');
          reset();
        },
      );
      return;
    }
    setCopyState('error');
    reset();
  }, [manualCommandText]);

  if (!tool) {
    return (
      <div className="catalog-tool">
        <button type="button" className="catalog-tool-back" onClick={onBack}>
          <ArrowLeft size={14} />
          Back to catalog
        </button>
        <section className="catalog-tool-missing">
          <h1>Tool not found</h1>
          <p>This catalog id is not in the current summary. It may have been removed or renamed.</p>
        </section>
      </div>
    );
  }

  const description = tool.description ?? tool.summary;
  const capabilities = catalogCapabilityLabels(tool).slice(0, 5);
  const specs = specsFor(tool);
  const docsHref = tool.docs_path ?? tool.homepage_url;
  const profileNames = tool.profiles.length ? tool.profiles : [];

  // Install action copy: when the install isn't directly executable, the
  // button doesn't disappear — it still shows the next step the user needs to
  // take, just visually quieter. That preserves the affordance without
  // pretending we can run it. Already-installed tools (built-in, detected,
  // managed) drop the button entirely; their next-step copy already explains
  // what to do.
  const installHelp = installEnabled
    ? null
    : tool.install.next_step ?? tool.install.instructions ?? null;
  // SetupCard takes over the body when a tool is installed but waiting on a
  // credential or config block. The hero eyebrow keeps the "Installed —
  // needs setup." copy so the user has a visual anchor for the state; the
  // standalone next-step paragraph below the hero disappears because the
  // SetupCard surface owns that affordance now.
  const setupCardActive = tool.install_state === 'not-configured' && tool.setup_kind !== 'none';
  const alreadyInstalledNote = alreadyInstalled && !setupCardActive
    ? (tool.install.next_step
        ?? (tool.install_state === 'built-in'
          ? `${tool.label} is built into DëvSec. Use it in any matching scan profile.`
          : `${tool.label} is installed locally. Use it in any matching scan profile.`))
    : null;

  return (
    <div className="catalog-tool">
      <button type="button" className="catalog-tool-back" onClick={onBack}>
        <ArrowLeft size={14} />
        Back to catalog
      </button>

      <section
        className="catalog-tool-hero"
        style={{['--tool-accent' as string]: toolAccent(tool)}}
      >
        <div className="catalog-tool-hero-head">
          <div className="catalog-tool-hero-icon">{toolLogo(tool)}</div>
          <div className="catalog-tool-hero-copy">
            <div className="catalog-tool-eyebrow">
              <span className="catalog-tool-verified">
                <ShieldCheck size={12} />
                Verified
              </span>
              <span>by DëvSec Core</span>
            </div>
            <h1 className="catalog-tool-hero-title">{tool.label}</h1>
            <p>{tool.summary}</p>
          </div>
          <div className="catalog-tool-hero-actions">
            {displayOnly ? (
              <span className="catalog-tool-display-note">
                <CircleSlash size={14} />
                Display only — no install or scan action in this version.
              </span>
            ) : alreadyInstalled ? (
              <span className="catalog-tool-display-note">
                <CheckCircle2 size={14} />
                {tool.install_state === 'built-in'
                  ? 'Built in — no install needed.'
                  : tool.install_state === 'managed'
                  ? 'Managed by DëvSec.'
                  : tool.install_state === 'not-configured'
                  ? 'Installed — needs setup.'
                  : 'Detected locally.'}
              </span>
            ) : manualInstallable ? (
              <span className="catalog-tool-display-note">
                <Download size={14} />
                Manual install — see steps below.
              </span>
            ) : (
              <button
                type="button"
                className={`catalog-tool-cta ${installEnabled ? '' : 'quiet'}`}
                onClick={onInstall}
                disabled={!installEnabled || Boolean(mutating)}
                title={installEnabled ? undefined : installHelp ?? undefined}
              >
                <Download size={15} />
                {installLabel}
              </button>
            )}
          </div>
        </div>
        {!displayOnly && !alreadyInstalled && !manualInstallable && !installEnabled && installHelp && (
          <p className="catalog-tool-hero-help">{installHelp}</p>
        )}
        {alreadyInstalled && alreadyInstalledNote && (
          <p className="catalog-tool-hero-help">{alreadyInstalledNote}</p>
        )}
        {mutation && mutation.toolId === tool.id && mutation.status !== 'running' && (
          <p className={`catalog-tool-hero-message ${mutation.status}`}>{mutation.message}</p>
        )}
      </section>

      {setupCardActive && <SetupCard tool={tool} onRefresh={onRefresh} />}

      {manualInstallable && (
        <section className="catalog-tool-manual-install">
          <header className="catalog-tool-card-head">
            <h2>Install manually</h2>
          </header>
          <p className="catalog-tool-manual-instructions">{manualCommandText || 'See upstream documentation for install steps.'}</p>
          <div className="catalog-tool-manual-actions">
            <button
              type="button"
              className="catalog-tool-manual-button"
              onClick={onCopyCommand}
              disabled={!manualCommandText}
            >
              {copyState === 'copied' ? <ClipboardCheck size={14} /> : <Clipboard size={14} />}
              {copyState === 'copied' ? 'Copied' : copyState === 'error' ? 'Copy unavailable' : 'Copy install command'}
            </button>
            <button
              type="button"
              className="catalog-tool-manual-button primary"
              onClick={onMarkInstalled}
              disabled={Boolean(mutating)}
            >
              <RefreshCw size={14} />
              {mutating ? 'Re-detecting…' : 'Mark installed'}
            </button>
          </div>
          <p className="catalog-tool-manual-hint">
            DëvSec waits for you to install the binary out-of-band. After install, click <strong>Mark installed</strong> so the catalog re-detects it on PATH.
          </p>
        </section>
      )}

      <div className="catalog-tool-body">
        <div className="catalog-tool-body-main">
          <section className="catalog-tool-card">
            <header className="catalog-tool-card-head">
              <h2>Overview</h2>
            </header>
            <p>{description}</p>
            {description !== tool.summary && <p className="catalog-tool-card-sub">{tool.summary}</p>}
          </section>

          <section className="catalog-tool-card">
            <header className="catalog-tool-card-head">
              <h2>Core capabilities</h2>
            </header>
            {capabilities.length ? (
              <ul className="catalog-tool-capability-list">
                {capabilities.map((label) => (
                  <li key={label}>
                    <CheckCircle2 size={16} />
                    <span>{label}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="catalog-tool-card-sub">No capability labels have been published yet.</p>
            )}
          </section>
        </div>

        <aside className="catalog-tool-body-side">
          <section className="catalog-tool-specs">
            <header className="catalog-tool-card-head">
              <h2>Technical specs</h2>
            </header>
            <dl className="catalog-tool-spec-list">
              {specs.map((spec) => (
                <div key={spec.label} className="catalog-tool-spec-row">
                  <dt>{spec.label}</dt>
                  <dd className={spec.mono ? 'mono' : ''}>{spec.value}</dd>
                </div>
              ))}
            </dl>
          </section>

          {docsHref ? (
            <a
              className="catalog-tool-docs-link"
              href={docsHref}
              target="_blank"
              rel="noreferrer"
            >
              <span className="catalog-tool-docs-label">
                <BookOpen size={16} />
                Read documentation
              </span>
              <ArrowRight size={16} />
            </a>
          ) : (
            <p className="catalog-tool-docs-empty">No documentation link published yet.</p>
          )}
        </aside>
      </div>

      <div className="catalog-tool-extras">
        <section className="catalog-tool-extras-section">
          <header className="catalog-tool-card-head">
            <h2>Safety and permissions</h2>
          </header>
          <p className="catalog-tool-card-sub">{catalogPolicySummary(tool)}</p>
          <dl className="catalog-tool-kv-grid">
            <Kv label="Network" value={catalogNetworkLabels[tool.policy.network_access]} />
            <Kv label="Credentials" value={catalogCredentialLabels[tool.policy.uses_credentials]} />
            <Kv label="Target" value={catalogTargetLabels[tool.policy.external_targets]} />
            <Kv label="File writes" value={tool.policy.writes_files ? 'Writes files' : 'Read-only'} />
            <Kv label="Approval" value={tool.policy.needs_approval ? 'Required' : 'Not required'} />
            <Kv label="Agent Lab" value={tool.derived_labels.agent_lab} />
          </dl>
        </section>

        <section className="catalog-tool-extras-section">
          <header className="catalog-tool-card-head">
            <h2>Setup and ownership</h2>
          </header>
          <dl className="catalog-tool-kv-grid">
            <Kv label="Category" value={catalogCategoryLabels[tool.category]} />
            <Kv label="Install state" value={catalogInstallLabels[tool.install_state]} />
            <Kv label="Method" value={catalogInstallMethodLabels[tool.install.method]} />
            <Kv label="Owner" value={catalogInstallOwnerLabels[tool.install.owner]} />
            <Kv label="Detection" value={catalogInstallDetectionLabels[tool.install.detection]} />
            <Kv label="Binary" value={tool.install.binary ?? 'Not required'} mono />
            <Kv label="Uninstall" value={catalogUninstallLabels[tool.install.uninstall_posture]} />
            {(() => {
              const preview = tool.install_preview;
              const achieved = preview?.proof_level_label;
              const expected = preview?.expected_proof_level_label;
              if (achieved) return <Kv label="Binary proof" value={achieved} />;
              if (expected) return <Kv label="Binary proof" value={`${expected} (expected)`} />;
              return null;
            })()}
            {runtimeItem && (() => {
              const relative = formatRelativeTime(runtimeItem.last_run);
              if (runtimeItem.status === 'ran' && relative) {
                return <Kv label="Last runtime" value={relative} />;
              }
              if (runtimeItem.status === 'not-run' || runtimeItem.status === 'missing') {
                return <Kv label="Last runtime" value="Never run" />;
              }
              return null;
            })()}
          </dl>
          {tool.install.next_step && (
            <p className="catalog-tool-next-step">
              <span className="catalog-tool-next-step-label">Next step</span>
              {tool.install.next_step}
            </p>
          )}
          {tool.install_preview?.proof_caveat
            && (tool.install_preview?.proof_level_label || tool.install_preview?.expected_proof_level_label) && (
            <p className="catalog-tool-muted">{tool.install_preview.proof_caveat}</p>
          )}
        </section>

        <section className="catalog-tool-extras-section">
          <header className="catalog-tool-card-head">
            <h2>Profiles and packs</h2>
          </header>
          <div className="catalog-tool-profile-list">
            {profileNames.length ? profileNames.map((profile) => (
              <span key={profile} className="catalog-tool-pill">
                <strong>{profile}</strong>
                <em>{catalogProfileRole(tool, profile)}</em>
              </span>
            )) : <span className="catalog-tool-muted">No active scan profile in this version.</span>}
          </div>
          <div className="catalog-tool-pack-list">
            {tool.packs.length ? tool.packs.map((pack) => (
              <span
                key={`${tool.id}:${pack.pack_id}`}
                className={`catalog-tool-pack-pill ${pack.role === 'coming-soon' ? 'muted' : ''}`}
              >
                {catalogPackLabels[pack.pack_id]} · {humanizeKey(pack.role)}
                {pack.default_enabled ? ' · default' : ''}
              </span>
            )) : <span className="catalog-tool-muted">No pack membership.</span>}
          </div>
        </section>
      </div>
    </div>
  );
}

function Kv({label, value, mono}: {label: string; value: string; mono?: boolean}) {
  return (
    <div className="catalog-tool-kv">
      <dt>{label}</dt>
      <dd className={mono ? 'mono' : ''}>{value}</dd>
    </div>
  );
}
