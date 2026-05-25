// SetupCard — one typed component that reads a tool's setup_kind /
// setup_requirement / setup_probe and renders the right input UX. Five
// render branches; nothing here is per-tool. The Tool detail page mounts
// this whenever install_state === 'not-configured' && setup_kind !== 'none'.
//
// Voice register (docs/agent-voice.md): neutral additive verbs from the
// locked vocabulary — Connect, Store, Stored, Forget, Test connection, Save.
// No severity language; no exclamation marks; no fake urgency. Probe failure
// reads as a calm operational outcome ("Probe exited 1") rather than panic.
//
// State boundary: SetupCard owns its own form/probe/keychain state. It never
// touches the catalog mutation slot in useCatalogData — that slot belongs to
// install/uninstall flows. The only cross-component effect is a catalog
// refresh on probe success so the Tool detail page can re-render with the
// 'detected' eyebrow once the backend flips install_state.

import {useCallback, useEffect, useMemo, useState} from 'react';
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  Loader2,
  PlayCircle,
  RotateCcw,
  Save,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import {ToolCatalogItem, SetupKind, SetupProbe} from '../../dashboardData';
import {responseErrorMessage} from '../../uiHelpers';

export type SetupCardProps = {
  tool: ToolCatalogItem;
  onRefresh?: () => Promise<void> | void;
};

type ProbeResult = {
  success: boolean;
  summary: string;
  output: string;
  command: string | null;
  returncode: number | null;
};

type AsyncStatus = 'idle' | 'running' | 'complete' | 'error';

type AsyncSlot = {
  status: AsyncStatus;
  message?: string;
};

const IDLE: AsyncSlot = {status: 'idle'};

// What the probe spec tells us about how to bind a credential to an env var
// at probe-run time. For api-key / env-var kinds, the same name does double
// duty: it's the env var the tool will see AND the Keychain key under
// (DëvSec, <tool>:<key>). Keeping one identifier here is the simplest
// truthful default until a tool actually needs them split.
function credentialKeyFromProbe(probe?: SetupProbe): string | null {
  if (!probe) return null;
  const spec = probe.spec ?? {};
  return spec.env_from_credential || spec.env_var || null;
}

function configKeyFromProbe(probe?: SetupProbe): string | null {
  if (!probe) return null;
  return probe.spec?.config_key || null;
}

function defaultEnvVarName(tool: ToolCatalogItem): string {
  return credentialKeyFromProbe(tool.setup_probe) ?? 'API_TOKEN';
}

function defaultFileConfigKey(tool: ToolCatalogItem): string {
  return configKeyFromProbe(tool.setup_probe) ?? 'path';
}

// Tools without a probe still get a card — they just won't show a
// "Test connection" button. That's an honest state, not a bug.
function probeKindLabel(probe?: SetupProbe): string {
  if (!probe) return '';
  if (probe.kind === 'shell') return 'Run probe command';
  if (probe.kind === 'binary-version') return 'Check binary version';
  if (probe.kind === 'directory-exists') return 'Verify directory exists';
  if (probe.kind === 'http') return 'Check endpoint reachable';
  return 'Test connection';
}

function setupKindHeader(kind: SetupKind): string {
  if (kind === 'env-var') return 'Set an environment variable';
  if (kind === 'api-key') return 'Connect an API key';
  if (kind === 'oauth') return 'Connect via OAuth';
  if (kind === 'file-path') return 'Set a file or directory path';
  if (kind === 'config-block') return 'Save a configuration block';
  return 'Needs setup';
}

async function readJson<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

export default function SetupCard({tool, onRefresh}: SetupCardProps) {
  const kind = tool.setup_kind;
  // oauth falls back to api-key behavior in v1. The first concrete case
  // (legitify) is a PAT; once a tool genuinely needs an OAuth dance we
  // wire the redirect flow then. The header copy still says OAuth so the
  // user knows what the tool wants.
  const effectiveKind: SetupKind = kind === 'oauth' ? 'api-key' : kind;
  const isCredentialKind = effectiveKind === 'env-var' || effectiveKind === 'api-key';
  const isConfigKind = effectiveKind === 'file-path' || effectiveKind === 'config-block';

  const credentialKey = useMemo(
    () => (isCredentialKind ? defaultEnvVarName(tool) : null),
    [tool, isCredentialKind],
  );
  const configKey = useMemo(
    () => (isConfigKind ? defaultFileConfigKey(tool) : null),
    [tool, isConfigKind],
  );

  const [credentialStored, setCredentialStored] = useState<boolean | null>(null);
  const [credentialValue, setCredentialValue] = useState<string>('');
  const [credentialSlot, setCredentialSlot] = useState<AsyncSlot>(IDLE);

  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [configDraft, setConfigDraft] = useState<string>('');
  const [configSlot, setConfigSlot] = useState<AsyncSlot>(IDLE);

  const [probeSlot, setProbeSlot] = useState<AsyncSlot>(IDLE);
  const [probeResult, setProbeResult] = useState<ProbeResult | null>(null);

  // Load existing keychain key list + config so the card can show "Stored"
  // when the user already pasted the value in an earlier session. A 503
  // (Keychain unsupported off-macOS) is a normal outcome; we surface a
  // gentle inline message and keep the form usable for the config-only
  // branches.
  useEffect(() => {
    let cancelled = false;
    if (isCredentialKind && credentialKey) {
      void (async () => {
        try {
          const response = await fetch(`/api/tools/${encodeURIComponent(tool.id)}/credentials/keys`);
          if (cancelled) return;
          if (response.status === 503) {
            setCredentialSlot({status: 'error', message: 'macOS Keychain is unavailable on this host.'});
            setCredentialStored(false);
            return;
          }
          if (!response.ok) {
            setCredentialStored(false);
            return;
          }
          const data = await readJson<{keys: string[]}>(response);
          setCredentialStored(Array.isArray(data.keys) && data.keys.includes(credentialKey));
        } catch {
          if (!cancelled) setCredentialStored(false);
        }
      })();
    }
    if (isConfigKind) {
      void (async () => {
        try {
          const response = await fetch(`/api/tools/${encodeURIComponent(tool.id)}/setup/config`);
          if (cancelled || !response.ok) return;
          const data = await readJson<{values: Record<string, string>}>(response);
          setConfigValues(data.values ?? {});
          if (configKey) setConfigDraft(data.values?.[configKey] ?? '');
        } catch {
          if (!cancelled) {
            setConfigValues({});
          }
        }
      })();
    }
    return () => {
      cancelled = true;
    };
  }, [tool.id, isCredentialKind, isConfigKind, credentialKey, configKey]);

  const onStoreCredential = useCallback(async () => {
    if (!credentialKey || !credentialValue) return;
    setCredentialSlot({status: 'running', message: 'Storing in Keychain…'});
    try {
      const response = await fetch(`/api/tools/${encodeURIComponent(tool.id)}/credentials`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({key: credentialKey, value: credentialValue}),
      });
      if (!response.ok) {
        throw new Error(await responseErrorMessage(response, 'Could not store credential.'));
      }
      setCredentialStored(true);
      setCredentialValue('');
      setCredentialSlot({status: 'complete', message: 'Stored in macOS Keychain.'});
    } catch (err) {
      setCredentialSlot({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not store credential.',
      });
    }
  }, [tool.id, credentialKey, credentialValue]);

  const onForgetCredential = useCallback(async () => {
    if (!credentialKey) return;
    setCredentialSlot({status: 'running', message: 'Removing from Keychain…'});
    try {
      const response = await fetch(
        `/api/tools/${encodeURIComponent(tool.id)}/credentials/${encodeURIComponent(credentialKey)}`,
        {method: 'DELETE'},
      );
      if (!response.ok) {
        throw new Error(await responseErrorMessage(response, 'Could not forget credential.'));
      }
      setCredentialStored(false);
      setProbeResult(null);
      setCredentialSlot({status: 'complete', message: 'Credential removed.'});
    } catch (err) {
      setCredentialSlot({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not forget credential.',
      });
    }
  }, [tool.id, credentialKey]);

  const onSaveConfig = useCallback(async () => {
    if (!configKey) return;
    const next = {...configValues, [configKey]: configDraft.trim()};
    setConfigSlot({status: 'running', message: 'Saving…'});
    try {
      const response = await fetch(`/api/tools/${encodeURIComponent(tool.id)}/setup/config`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({values: next}),
      });
      if (!response.ok) {
        throw new Error(await responseErrorMessage(response, 'Could not save.'));
      }
      const data = await readJson<{values: Record<string, string>}>(response);
      setConfigValues(data.values ?? {});
      setConfigSlot({status: 'complete', message: 'Saved.'});
    } catch (err) {
      setConfigSlot({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not save.',
      });
    }
  }, [tool.id, configKey, configValues, configDraft]);

  const onForgetConfig = useCallback(async () => {
    setConfigSlot({status: 'running', message: 'Removing…'});
    try {
      const response = await fetch(`/api/tools/${encodeURIComponent(tool.id)}/setup/config`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error(await responseErrorMessage(response, 'Could not remove.'));
      }
      setConfigValues({});
      setConfigDraft('');
      setProbeResult(null);
      setConfigSlot({status: 'complete', message: 'Removed.'});
    } catch (err) {
      setConfigSlot({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not remove.',
      });
    }
  }, [tool.id]);

  const onProbe = useCallback(async () => {
    setProbeSlot({status: 'running', message: 'Running probe…'});
    setProbeResult(null);
    try {
      const response = await fetch(`/api/tools/${encodeURIComponent(tool.id)}/setup/probe`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
      });
      if (!response.ok) {
        throw new Error(await responseErrorMessage(response, 'Probe failed to start.'));
      }
      const data = await readJson<ProbeResult>(response);
      setProbeResult(data);
      setProbeSlot({
        status: data.success ? 'complete' : 'error',
        message: data.summary,
      });
      if (data.success && onRefresh) {
        // On probe success the backend should flip install_state to
        // 'detected' next time the catalog is read; trigger a refresh so
        // the SetupCard collapses and the "Detected locally" eyebrow
        // appears without the user having to reload.
        await onRefresh();
      }
    } catch (err) {
      setProbeSlot({
        status: 'error',
        message: err instanceof Error ? err.message : 'Probe failed to start.',
      });
    }
  }, [tool.id, onRefresh]);

  const probeAvailable = useMemo(() => {
    if (!tool.setup_probe) return false;
    if (isCredentialKind && credentialStored !== true) return false;
    if (isConfigKind && configKey && !(configValues[configKey] ?? '').trim()) return false;
    return true;
  }, [tool.setup_probe, isCredentialKind, credentialStored, isConfigKind, configKey, configValues]);

  const header = setupKindHeader(kind);

  return (
    <section className="setup-card" data-setup-kind={kind}>
      <header className="setup-card-head">
        <div className="setup-card-eyebrow">
          <ShieldCheck size={12} />
          Needs setup
        </div>
        <h2>{header}</h2>
        {tool.setup_requirement && (
          <p className="setup-card-requirement">{tool.setup_requirement}</p>
        )}
        {kind === 'oauth' && (
          <p className="setup-card-note">
            OAuth handoff is not wired yet. For now, paste a personal access token below — the
            tool will receive it through the same env var the OAuth flow would inject.
          </p>
        )}
      </header>

      {isCredentialKind && credentialKey && (
        <div className="setup-card-row">
          <label className="setup-card-label" htmlFor={`setup-${tool.id}-${credentialKey}`}>
            <span className="setup-card-label-text">Environment variable</span>
            <code className="setup-card-mono">{credentialKey}</code>
          </label>
          {credentialStored ? (
            <div className="setup-card-stored">
              <span className="setup-card-stored-badge">
                <Check size={14} />
                Stored in macOS Keychain
              </span>
              <button
                type="button"
                className="setup-card-button quiet"
                onClick={onForgetCredential}
                disabled={credentialSlot.status === 'running'}
              >
                <Trash2 size={14} />
                Forget
              </button>
            </div>
          ) : (
            <div className="setup-card-input-row">
              <input
                id={`setup-${tool.id}-${credentialKey}`}
                type="password"
                autoComplete="off"
                spellCheck={false}
                className="setup-card-input"
                placeholder={`Paste ${credentialKey} value`}
                value={credentialValue}
                onChange={(event) => setCredentialValue(event.target.value)}
              />
              <button
                type="button"
                className="setup-card-button primary"
                onClick={onStoreCredential}
                disabled={!credentialValue || credentialSlot.status === 'running'}
              >
                {credentialSlot.status === 'running' ? <Loader2 className="setup-card-spin" size={14} /> : <Save size={14} />}
                Store in Keychain
              </button>
            </div>
          )}
          {effectiveKind === 'api-key' && tool.setup_token_create_url && !credentialStored && (
            <a
              className="setup-card-deeplink"
              href={tool.setup_token_create_url}
              target="_blank"
              rel="noreferrer"
            >
              Generate a token
              <ArrowUpRight size={12} />
            </a>
          )}
          {credentialSlot.message && (
            <p className={`setup-card-status ${credentialSlot.status}`}>
              {credentialSlot.status === 'error' && <AlertCircle size={12} />}
              {credentialSlot.message}
            </p>
          )}
        </div>
      )}

      {isConfigKind && configKey && (
        <div className="setup-card-row">
          <label className="setup-card-label" htmlFor={`setup-${tool.id}-${configKey}`}>
            <span className="setup-card-label-text">
              {effectiveKind === 'file-path' ? 'Path' : 'Config block'}
            </span>
            <code className="setup-card-mono">{configKey}</code>
          </label>
          {effectiveKind === 'file-path' ? (
            <div className="setup-card-input-row">
              <input
                id={`setup-${tool.id}-${configKey}`}
                type="text"
                autoComplete="off"
                spellCheck={false}
                className="setup-card-input"
                placeholder="/path/to/directory"
                value={configDraft}
                onChange={(event) => setConfigDraft(event.target.value)}
              />
              <button
                type="button"
                className="setup-card-button primary"
                onClick={onSaveConfig}
                disabled={!configDraft.trim() || configSlot.status === 'running'}
              >
                {configSlot.status === 'running' ? <Loader2 className="setup-card-spin" size={14} /> : <Save size={14} />}
                Save path
              </button>
            </div>
          ) : (
            <div className="setup-card-textarea-row">
              <textarea
                id={`setup-${tool.id}-${configKey}`}
                className="setup-card-textarea"
                spellCheck={false}
                rows={8}
                value={configDraft}
                placeholder="# Paste TOML / YAML config block here"
                onChange={(event) => setConfigDraft(event.target.value)}
              />
              <div className="setup-card-actions">
                <button
                  type="button"
                  className="setup-card-button primary"
                  onClick={onSaveConfig}
                  disabled={!configDraft.trim() || configSlot.status === 'running'}
                >
                  {configSlot.status === 'running' ? <Loader2 className="setup-card-spin" size={14} /> : <Save size={14} />}
                  Save
                </button>
              </div>
            </div>
          )}
          {configValues[configKey] && (
            <div className="setup-card-stored-config">
              <span className="setup-card-stored-badge">
                <Check size={14} />
                Saved
              </span>
              <button
                type="button"
                className="setup-card-button quiet"
                onClick={onForgetConfig}
                disabled={configSlot.status === 'running'}
              >
                <Trash2 size={14} />
                Forget
              </button>
            </div>
          )}
          {configSlot.message && (
            <p className={`setup-card-status ${configSlot.status}`}>
              {configSlot.status === 'error' && <AlertCircle size={12} />}
              {configSlot.message}
            </p>
          )}
        </div>
      )}

      {tool.setup_probe && (
        <div className="setup-card-probe">
          <div className="setup-card-probe-head">
            <div>
              <span className="setup-card-probe-label">{probeKindLabel(tool.setup_probe)}</span>
              {tool.setup_probe.spec.command && (
                <code className="setup-card-mono setup-card-probe-cmd">
                  {tool.setup_probe.spec.command}
                </code>
              )}
            </div>
            <button
              type="button"
              className="setup-card-button"
              onClick={onProbe}
              disabled={!probeAvailable || probeSlot.status === 'running'}
              title={probeAvailable ? undefined : 'Store the credential or save the path before testing.'}
            >
              {probeSlot.status === 'running' ? (
                <Loader2 className="setup-card-spin" size={14} />
              ) : probeSlot.status === 'complete' ? (
                <RotateCcw size={14} />
              ) : (
                <PlayCircle size={14} />
              )}
              {probeSlot.status === 'running' ? 'Testing…' : probeSlot.status === 'complete' ? 'Test again' : 'Test connection'}
            </button>
          </div>
          {probeResult && (
            <div className={`setup-card-probe-result ${probeResult.success ? 'success' : 'failure'}`}>
              <p className="setup-card-probe-summary">
                {probeResult.success ? <Check size={14} /> : <AlertCircle size={14} />}
                {probeResult.summary}
              </p>
              {probeResult.output && (
                <pre className="setup-card-probe-output">{probeResult.output}</pre>
              )}
              {probeResult.returncode != null && !probeResult.success && (
                <p className="setup-card-probe-note">
                  The credential stays stored — adjust scopes or path, then test again.
                </p>
              )}
            </div>
          )}
          {!probeResult && probeSlot.status === 'error' && (
            <p className="setup-card-status error">
              <AlertCircle size={12} />
              {probeSlot.message}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
