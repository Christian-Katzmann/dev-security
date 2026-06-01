import {Archive, CheckCircle2, Copy, KeyRound, ShieldAlert} from 'lucide-react';
import {useMemo, useState} from 'react';
import {
  DashboardSummary,
  HoneyIncident,
  HoneyKeyEvent,
  HoneyKey,
  HoneyKeyStatus,
  TargetSelection,
  formatDate,
  honeyKeyById,
  latestOpenHoneyKeyEvent,
} from '../dashboardData';

type HoneyKeysViewProps = {
  summary: DashboardSummary;
  target: TargetSelection;
  onRefresh: () => Promise<void>;
};

type CreatedHoneyKey = {
  key: HoneyKey;
  raw_token: string;
  snippets: Record<string, string>;
  notice: string;
};

const placementTemplates = ['.env.backup', 'legacy-prod-config.json', 'internal-admin-notes.md'];
const statusLabels: Record<HoneyKeyStatus, string> = {
  active: 'Active',
  triggered: 'Triggered',
  archived: 'Archived',
};

type IncidentStep = 'investigating' | 'secrets_rotated' | 'logs_reviewed' | 'archived_reset';

const incidentSteps: {id: IncidentStep; label: string; detail: string}[] = [
  {
    id: 'investigating',
    label: 'Investigating',
    detail: 'Check whether the repo was public, leaked, cloned, scraped, or accessed unexpectedly.',
  },
  {
    id: 'secrets_rotated',
    label: 'Real secrets rotated',
    detail: 'Rotate real credentials if exposure is plausible.',
  },
  {
    id: 'logs_reviewed',
    label: 'Logs reviewed',
    detail: 'Review commits, CI logs, deploy logs, dependency activity, access logs, integrations, and AI-agent activity.',
  },
  {
    id: 'archived_reset',
    label: 'Archived or reset',
    detail: 'Archive this Honey Key or place a fresh decoy after the investigation.',
  },
];

export default function HoneyKeysView({summary, target, onRefresh}: HoneyKeysViewProps) {
  const [name, setName] = useState('Legacy internal API key');
  const [placementPath, setPlacementPath] = useState(placementTemplates[0]);
  const [note, setNote] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isArchiving, setIsArchiving] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedHoneyKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [confirmPlacement, setConfirmPlacement] = useState(false);
  const [advancedPlacement, setAdvancedPlacement] = useState(false);
  const [isInserting, setIsInserting] = useState(false);
  const [insertedPath, setInsertedPath] = useState<string | null>(null);
  const [savingIncident, setSavingIncident] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const keys = summary.honey_keys ?? [];
    return {
      active: keys.filter((key) => key.status === 'active'),
      triggered: keys.filter((key) => key.status === 'triggered'),
      archived: keys.filter((key) => key.status === 'archived'),
    };
  }, [summary.honey_keys]);

  const latestEvent = latestOpenHoneyKeyEvent(summary);
  const latestEventKey = latestEvent ? honeyKeyById(summary, latestEvent.honey_key_id) : undefined;

  async function createHoneyKey() {
    if (target.mode !== 'repo') return;
    setIsCreating(true);
    setError(null);
    setCreated(null);
    setInsertedPath(null);
    setConfirmPlacement(false);
    setAdvancedPlacement(false);
    try {
      const response = await fetch('/api/honey/keys', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          repoPath: target.repo.path,
          repoName: target.repo.name,
          name,
          placementPath,
          note,
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      const payload: CreatedHoneyKey = await response.json();
      setCreated(payload);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create Honey Key');
    } finally {
      setIsCreating(false);
    }
  }

  async function archiveHoneyKey(keyId: string) {
    setIsArchiving(keyId);
    setError(null);
    try {
      const response = await fetch('/api/honey/archive', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: keyId}),
      });
      if (!response.ok) throw new Error(await response.text());
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to archive Honey Key');
    } finally {
      setIsArchiving(null);
    }
  }

  async function updateIncidentStep(eventId: string, step: IncidentStep, complete: boolean) {
    setSavingIncident(`${eventId}:${step}`);
    setError(null);
    try {
      const response = await fetch('/api/honey/incident-step', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({eventId, step, complete}),
      });
      if (!response.ok) throw new Error(await response.text());
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update incident');
    } finally {
      setSavingIncident(null);
    }
  }

  async function closeIncident(event: HoneyKeyEvent, acceptedRiskNote: string) {
    setSavingIncident(`${event.id}:close`);
    setError(null);
    try {
      const response = await fetch('/api/honey/incident-close', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({eventId: event.id, acceptedRiskNote}),
      });
      if (!response.ok) throw new Error(await response.text());
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to close incident');
    } finally {
      setSavingIncident(null);
    }
  }

  async function copyText(label: string, value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(label);
    window.setTimeout(() => setCopied(null), 1800);
  }

  async function insertDecoyFile() {
    if (target.mode !== 'repo' || !created) return;
    const snippet = created.snippets[placementPath] ?? created.snippets['.env.backup'];
    if (!snippet) return;
    const safePlacementPath = `.devsec/honeykeys/${created.key.id}-${placementPath.replace(/[^A-Za-z0-9_.-]+/g, '-')}`;
    const insertPath = advancedPlacement ? placementPath : safePlacementPath;
    setIsInserting(true);
    setError(null);
    setInsertedPath(null);
    try {
      const response = await fetch('/api/honey/insert', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          id: created.key.id,
          repoPath: target.repo.path,
          placementPath: insertPath,
          snippet,
          confirmPlacement,
          advancedPlacement,
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      const payload: {path: string; relative_path: string} = await response.json();
      setInsertedPath(payload.relative_path);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to insert decoy file');
    } finally {
      setIsInserting(false);
    }
  }

  return (
    <div className="p-6 md:p-12 flex flex-col gap-8 max-w-[1400px] w-full">
      <section className="border border-black/10 bg-white/70 p-6 md:p-8 shadow-[0_18px_60px_rgba(0,0,0,0.06)]">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-black/40 mb-4">
              <KeyRound className="w-4 h-4" strokeWidth={1.5} />
              Honey Keys
            </div>
            <h2 className="text-3xl md:text-5xl font-light tracking-tight text-black leading-tight">
              Honey Keys are DëvSec’s honeytoken feature: powerless decoy secrets that act as tripwires.
            </h2>
            <p className="mt-4 text-sm md:text-base leading-relaxed text-black/60">
              Honey Keys are fake, powerless decoy secrets. They alert you when touched. They do not prevent breaches by themselves.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3 w-full lg:w-[360px]">
            {(['active', 'triggered', 'archived'] as HoneyKeyStatus[]).map((status) => (
              <div key={status} className="border border-black/10 bg-[#fbfbfb] p-4 shadow-[inset_0_2px_0_rgba(17,17,17,0.88)]">
                <div className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-2">{statusLabels[status]}</div>
                <div className="text-3xl font-light text-black">{grouped[status].length}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {latestEvent && (
        <section className="border border-[#b91c1c] bg-white p-6 md:p-7 shadow-[inset_4px_0_0_#b91c1c]">
          <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-[#b91c1c] mb-3">
                <ShieldAlert className="w-4 h-4" strokeWidth={1.7} />
                Severity: Critical
              </div>
              <h3 className="text-2xl font-medium text-black">Honey Key triggered</h3>
              <p className="mt-3 text-sm leading-relaxed text-black/60">
                This indicates possible unauthorized access or that a decoy secret was touched. DëvSec cannot identify the person behind the request.
              </p>
            </div>
            <dl className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 text-sm min-w-0 xl:max-w-[760px]">
              <Metadata label="Repo" value={target.mode === 'repo' ? target.repo.name : latestEvent.project_id} />
              <Metadata label="Key" value={latestEventKey?.name ?? latestEvent.honey_key_id} />
              <Metadata label="Last triggered" value={formatDate(latestEvent.triggered_at)} />
              <Metadata label="Trigger count" value={String(latestEventKey?.trigger_count ?? 1)} />
              <Metadata label="Source IP" value={latestEvent.ip_address ?? 'Unknown'} />
              <Metadata label="User-agent" value={latestEvent.user_agent ?? 'Unknown'} wide />
            </dl>
          </div>
          <IncidentChecklist
            event={latestEvent}
            incident={latestEvent.incident}
            savingIncident={savingIncident}
            onToggle={updateIncidentStep}
            onClose={closeIncident}
          />
        </section>
      )}

      <section className="grid grid-cols-1 xl:grid-cols-[420px_minmax(0,1fr)] gap-6">
        <div className="border border-black/10 bg-[#fbfbfb]/85 p-5 md:p-6 h-fit">
          <h3 className="text-xl font-medium text-black">Create Honey Key</h3>
          <p className="mt-3 text-sm leading-relaxed text-black/60">
            Honey Keys are powerless decoy secrets that act as tripwires. If anyone — such as a hostile actor — tries to use them, DëvSec alerts you that a sensitive location in your codebase may have been accessed.
          </p>

          {target.mode !== 'repo' ? (
            <div className="mt-5 border border-black/10 bg-white/70 p-4 text-sm text-black/60">
              Select a repo target before creating a Honey Key. DëvSec will not place files in a repo automatically.
            </div>
          ) : (
            <div className="mt-5 flex flex-col gap-4">
              <label className="flex flex-col gap-2">
                <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">Display name</span>
                <input value={name} onChange={(event) => setName(event.target.value)} className="border border-black/10 bg-white px-3 py-2 text-sm outline-none focus:border-black/40" />
              </label>
              <label className="flex flex-col gap-2">
                <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">Suggested placement</span>
                <select value={placementPath} onChange={(event) => setPlacementPath(event.target.value)} className="border border-black/10 bg-white px-3 py-2 text-sm outline-none focus:border-black/40">
                  {placementTemplates.map((template) => <option key={template} value={template}>{template}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-2">
                <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">Note</span>
                <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} className="resize-none border border-black/10 bg-white px-3 py-2 text-sm outline-none focus:border-black/40" placeholder="Optional investigation context" />
              </label>
              <button type="button" onClick={createHoneyKey} disabled={isCreating} className="inline-flex items-center justify-center gap-2 border border-black bg-black text-white px-4 py-3 font-mono text-[10px] uppercase tracking-widest hover:bg-[#222] transition-colors disabled:opacity-50">
                <KeyRound className="w-4 h-4" strokeWidth={1.5} />
                {isCreating ? 'Creating...' : 'Create Honey Key'}
              </button>
            </div>
          )}

          {error && <div className="mt-5 border border-[#b91c1c]/40 bg-white p-3 text-xs text-[#7f1d1d]">{error}</div>}
        </div>

        <div className="flex flex-col gap-6 min-w-0">
          {created && (
            <div className="border border-black bg-white p-5 md:p-6">
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-5">
                <div>
                  <h3 className="text-xl font-medium text-black">Copy decoy snippet</h3>
                  <p className="mt-2 text-sm leading-relaxed text-black/60">
                    This is the only time the raw Honey Key is shown. DëvSec stores only a secure hash plus metadata.
                  </p>
                </div>
                <button type="button" onClick={() => copyText('raw-token', created.raw_token)} className="inline-flex items-center justify-center gap-2 border border-black/10 bg-[#fbfbfb] px-3 py-2 font-mono text-[10px] uppercase tracking-widest hover:border-black/40">
                  <Copy className="w-4 h-4" strokeWidth={1.5} />
                  Copy raw key
                </button>
              </div>
              <div className="grid gap-4">
                {Object.entries(created.snippets).map(([template, snippet]) => (
                  <div key={template} className="border border-black/10 bg-[#fbfbfb]">
                    <div className="flex items-center justify-between gap-3 border-b border-black/10 px-4 py-3">
                      <span className="font-mono text-[10px] uppercase tracking-widest text-black/45">{template}</span>
                      <button type="button" onClick={() => copyText(template, snippet)} className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-black hover:text-black/60">
                        <Copy className="w-3.5 h-3.5" strokeWidth={1.5} />
                        {copied === template ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <pre className="max-h-[220px] overflow-auto whitespace-pre-wrap break-all p-4 text-xs leading-relaxed text-black/70">{snippet}</pre>
                  </div>
                ))}
              </div>
              {target.mode === 'repo' && (
                <div className="mt-5 border border-black/10 bg-[#fbfbfb] p-4">
                  <h4 className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-3">Safe file insert</h4>
                  <p className="text-sm leading-relaxed text-black/60">
                    DëvSec can create <span className="font-mono text-xs text-black">.devsec/honeykeys/{created.key.id}-{placementPath.replace(/[^A-Za-z0-9_.-]+/g, '-')}</span> inside this repo. It will not overwrite an existing file, write outside the repo, commit the file, or create any real credential.
                  </p>
                  <label className="mt-4 flex items-start gap-3 text-sm leading-relaxed text-black/60">
                    <input
                      type="checkbox"
                      checked={advancedPlacement}
                      onChange={(event) => setAdvancedPlacement(event.target.checked)}
                      className="mt-1"
                    />
                    <span>
                      Advanced placement: use the realistic decoy path <span className="font-mono text-xs text-black">{placementPath}</span> instead of the inert DëvSec folder.
                    </span>
                  </label>
                  <label className="mt-4 flex items-start gap-3 text-sm leading-relaxed text-black/60">
                    <input
                      type="checkbox"
                      checked={confirmPlacement}
                      onChange={(event) => setConfirmPlacement(event.target.checked)}
                      className="mt-1"
                    />
                    <span>
                      I confirm this is a deliberate decoy placement. If I use advanced placement, I understand this creates a realistic-looking decoy file and I explicitly opt in.
                    </span>
                  </label>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={insertDecoyFile}
                      disabled={!confirmPlacement || isInserting || Boolean(insertedPath)}
                      className="inline-flex items-center justify-center gap-2 border border-black bg-black text-white px-4 py-3 font-mono text-[10px] uppercase tracking-widest hover:bg-[#222] transition-colors disabled:opacity-50"
                    >
                      <KeyRound className="w-4 h-4" strokeWidth={1.5} />
                      {isInserting ? 'Inserting...' : insertedPath ? 'Inserted' : 'Insert decoy file'}
                    </button>
                    {insertedPath && (
                      <span className="text-sm text-black/60">
                        Created <span className="font-mono text-xs text-black">{insertedPath}</span>. Review it before committing.
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          <HoneyKeyGroup title="Active Honey Keys" keys={grouped.active} onArchive={archiveHoneyKey} isArchiving={isArchiving} />
          <HoneyKeyGroup title="Triggered Honey Keys" keys={grouped.triggered} onArchive={archiveHoneyKey} isArchiving={isArchiving} />
          <HoneyKeyGroup title="Archived Honey Keys" keys={grouped.archived} onArchive={archiveHoneyKey} isArchiving={isArchiving} />
        </div>
      </section>

      <section className="border border-black/10 bg-white/60 p-5 text-sm leading-relaxed text-black/60">
        DëvSec keeps Honey Key events for {summary.honey_event_retention_days ?? 90} days by default. IP address and user-agent are treated as security log data and are used only for triage.
      </section>
    </div>
  );
}

function IncidentChecklist({
  event,
  incident,
  savingIncident,
  onToggle,
  onClose,
}: {
  event: HoneyKeyEvent;
  incident?: HoneyIncident | null;
  savingIncident: string | null;
  onToggle: (eventId: string, step: IncidentStep, complete: boolean) => Promise<void>;
  onClose: (event: HoneyKeyEvent, acceptedRiskNote: string) => Promise<void>;
}) {
  const done = incidentSteps.filter((step) => incident?.[step.id]).length;
  const canClose = Boolean(incident?.archived_reset || incident?.accepted_risk_note);
  const needsNote = !incident?.archived_reset;
  const closing = savingIncident === `${event.id}:close`;
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState('');

  return (
    <div className="mt-6 border-t border-black/10 pt-5">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <h4 className="font-mono text-[10px] uppercase tracking-widest text-black/40 mb-2">Incident response</h4>
          <p className="text-sm leading-relaxed text-black/60">
            Work through the response checklist, then close the incident after the key is archived/reset or with an accepted-risk note.
          </p>
        </div>
        <div className="border border-black/10 bg-[#fbfbfb] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-black/45">
          {done}/{incidentSteps.length} complete
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-3">
        {incidentSteps.map((step) => {
          const checked = Boolean(incident?.[step.id]);
          const saving = savingIncident === `${event.id}:${step.id}`;
          return (
            <label key={step.id} className={`flex items-start gap-3 border p-4 transition-colors ${checked ? 'border-black bg-[#fbfbfb]' : 'border-black/10 bg-white/65'}`}>
              <input
                type="checkbox"
                checked={checked}
                disabled={saving}
                onChange={(change) => void onToggle(event.id, step.id, change.target.checked)}
                className="mt-1"
              />
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-sm font-medium text-black">
                  {checked && <CheckCircle2 className="h-4 w-4 text-graph-gold" strokeWidth={1.6} />}
                  {step.label}
                </span>
                <span className="mt-1 block text-xs leading-relaxed text-black/55">{step.detail}</span>
              </span>
            </label>
          );
        })}
      </div>

      <div className="mt-4 border border-black/10 bg-white/60 p-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <p className="text-xs leading-relaxed text-black/55">
            {canClose
              ? 'This incident can be closed. It will leave the history in place and remove the active critical case.'
              : 'To close without archiving/resetting, add an accepted-risk note below.'}
          </p>
          {!(needsNote && noteOpen) && (
            <button
              type="button"
              onClick={() => (needsNote ? setNoteOpen(true) : void onClose(event, ''))}
              disabled={closing}
              className="inline-flex min-h-9 items-center justify-center gap-2 border border-black bg-black px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-white transition-colors hover:bg-[#222] disabled:opacity-50"
            >
              {closing ? 'Closing' : 'Close incident'}
            </button>
          )}
        </div>
        {needsNote && noteOpen && (
          <div className="mt-3 flex flex-col gap-3">
            <label className="flex flex-col gap-2">
              <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">Accepted-risk note (optional)</span>
              <textarea
                value={note}
                onChange={(change) => setNote(change.target.value)}
                rows={2}
                autoFocus
                placeholder="Why this incident is safe to close…"
                disabled={closing}
                className="resize-none border border-black/10 bg-white px-3 py-2 text-sm outline-none focus:border-black/40"
              />
            </label>
            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setNoteOpen(false)}
                disabled={closing}
                className="inline-flex min-h-9 items-center justify-center gap-2 border border-black/10 bg-white px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-black transition-colors hover:border-black/40 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void onClose(event, note.trim())}
                disabled={closing}
                className="inline-flex min-h-9 items-center justify-center gap-2 border border-black bg-black px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-white transition-colors hover:bg-[#222] disabled:opacity-50"
              >
                {closing ? 'Closing' : 'Close incident'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metadata({label, value, wide = false}: {label: string; value: string; wide?: boolean}) {
  return (
    <div className={`border border-black/10 bg-[#fbfbfb] p-3 min-w-0 ${wide ? 'sm:col-span-2' : ''}`}>
      <dt className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">{label}</dt>
      <dd className="text-sm text-black break-words">{value}</dd>
    </div>
  );
}

function HoneyKeyGroup({title, keys, onArchive, isArchiving}: {title: string; keys: HoneyKey[]; onArchive: (id: string) => void; isArchiving: string | null}) {
  return (
    <section className="border border-black/10 bg-white/65 p-5">
      <div className="flex items-center justify-between gap-4 mb-4">
        <h3 className="text-xl font-medium text-black">{title}</h3>
        <span className="font-mono text-[10px] uppercase tracking-widest text-black/35">{keys.length}</span>
      </div>
      {keys.length ? (
        <div className="grid gap-3">
          {keys.map((key) => (
            <article key={key.id} className="border border-black/10 bg-[#fbfbfb] p-4">
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <span className={`font-mono text-[9px] uppercase tracking-widest border px-2 py-1 ${key.status === 'triggered' ? 'border-[#b91c1c] text-[#b91c1c]' : 'border-black/10 text-black/45'}`}>
                      {statusLabels[key.status]}
                    </span>
                    <span className="font-mono text-[9px] uppercase tracking-widest text-black/35">{key.id}</span>
                  </div>
                  <h4 className="text-base font-medium text-black break-words">{key.name}</h4>
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-black/55">
                    <span>Placement: {key.placement_path ?? 'Not set'}</span>
                    <span>Last trigger: {formatDate(key.last_triggered_at)}</span>
                    <span>Trigger count: {key.trigger_count}</span>
                  </div>
                  {key.note && <p className="mt-3 text-xs leading-relaxed text-black/50">{key.note}</p>}
                </div>
                {key.status !== 'archived' && (
                  <button type="button" onClick={() => onArchive(key.id)} disabled={isArchiving === key.id} className="inline-flex items-center justify-center gap-2 border border-black/10 bg-white px-3 py-2 font-mono text-[10px] uppercase tracking-widest hover:border-black/40 disabled:opacity-50">
                    <Archive className="w-4 h-4" strokeWidth={1.5} />
                    {isArchiving === key.id ? 'Archiving' : 'Archive'}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="border border-black/10 bg-[#fbfbfb] p-5 text-sm text-black/55">
          No keys in this state.
        </div>
      )}
    </section>
  );
}
