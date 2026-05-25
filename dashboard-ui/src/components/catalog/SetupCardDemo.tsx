// SetupCardDemo — storybook-style page that renders all five SetupCard
// branches side-by-side with mock catalog data. Opened via
// ``?setupCardDemo=1`` so the visual hierarchy of each kind can be verified
// without going through the real "install legitify → flips to
// not-configured → SetupCard appears" path.
//
// This file is loaded by main.tsx only when the query param is present —
// it ships in the bundle but never renders during normal app use. The mock
// fetch wrapper below keeps the demo self-contained: every `/api/...` call
// resolves locally, no network traffic, no risk of touching the user's
// Keychain.

import {useEffect} from 'react';
import SetupCard from './SetupCard';
import {ToolCatalogItem, SetupKind} from '../../dashboardData';

type DemoState = {
  credentials: Record<string, Record<string, string>>;
  configs: Record<string, Record<string, string>>;
};

const demoState: DemoState = {credentials: {}, configs: {}};

function installDemoFetch() {
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const method = (init?.method ?? 'GET').toUpperCase();
    const credentialKeyMatch = url.match(/^\/api\/tools\/([^/]+)\/credentials\/keys$/);
    const credentialPostMatch = url.match(/^\/api\/tools\/([^/]+)\/credentials$/);
    const credentialDeleteMatch = url.match(/^\/api\/tools\/([^/]+)\/credentials\/([^/]+)$/);
    const configMatch = url.match(/^\/api\/tools\/([^/]+)\/setup\/config$/);
    const probeMatch = url.match(/^\/api\/tools\/([^/]+)\/setup\/probe$/);

    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});

    if (credentialKeyMatch) {
      const toolId = decodeURIComponent(credentialKeyMatch[1]);
      return json({tool_id: toolId, keys: Object.keys(demoState.credentials[toolId] ?? {})});
    }
    if (credentialPostMatch && method === 'POST') {
      const toolId = decodeURIComponent(credentialPostMatch[1]);
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      demoState.credentials[toolId] = {
        ...(demoState.credentials[toolId] ?? {}),
        [body.key]: body.value,
      };
      return json({
        tool_id: toolId,
        key: body.key,
        stored: true,
        keys: Object.keys(demoState.credentials[toolId]),
      });
    }
    if (credentialDeleteMatch && method === 'DELETE') {
      const toolId = decodeURIComponent(credentialDeleteMatch[1]);
      const key = decodeURIComponent(credentialDeleteMatch[2]);
      const had = Boolean(demoState.credentials[toolId]?.[key]);
      if (had) delete demoState.credentials[toolId][key];
      return json({
        tool_id: toolId,
        key,
        deleted: had,
        keys: Object.keys(demoState.credentials[toolId] ?? {}),
      });
    }
    if (configMatch) {
      const toolId = decodeURIComponent(configMatch[1]);
      if (method === 'GET') {
        return json({tool_id: toolId, values: demoState.configs[toolId] ?? {}});
      }
      if (method === 'POST') {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        demoState.configs[toolId] = body.values ?? {};
        return json({tool_id: toolId, values: demoState.configs[toolId], stored: true});
      }
      if (method === 'DELETE') {
        const had = Boolean(demoState.configs[toolId]);
        delete demoState.configs[toolId];
        return json({tool_id: toolId, values: {}, removed: had});
      }
    }
    if (probeMatch && method === 'POST') {
      const toolId = decodeURIComponent(probeMatch[1]);
      // Mock outcome: success if a credential or config value exists.
      const hasCred = Object.keys(demoState.credentials[toolId] ?? {}).length > 0;
      const hasConfig = Object.keys(demoState.configs[toolId] ?? {}).length > 0;
      const success = hasCred || hasConfig;
      return json({
        tool_id: toolId,
        success,
        summary: success ? 'Probe succeeded.' : 'Probe exited 1.',
        output: success
          ? 'mock: 1 repo scanned\nmock: 0 findings'
          : 'mock: missing token\nmock: refusing to run without credentials',
        command: 'demo --probe',
        returncode: success ? 0 : 1,
        duration_seconds: 0.04,
      });
    }
    return realFetch(input, init);
  };
}

const mockTools: Array<{title: string; tool: ToolCatalogItem}> = [
  {
    title: 'env-var · single environment variable',
    tool: mockTool({
      id: 'demo-env',
      label: 'demo-env',
      setup_kind: 'env-var',
      requirement: 'Set the API_TOKEN environment variable used by the tool at runtime.',
      probeKind: 'shell',
      probeSpec: {command: 'demo --check', env_from_credential: 'API_TOKEN'},
    }),
  },
  {
    title: 'api-key · with token-generation deep link',
    tool: mockTool({
      id: 'demo-api',
      label: 'demo-api',
      setup_kind: 'api-key',
      requirement: 'GitHub Personal Access Token with `repo` + `admin:repo_hook` scopes.',
      probeKind: 'shell',
      probeSpec: {command: 'legitify analyze --repo Legit-Labs/legitify', env_from_credential: 'SCM_TOKEN'},
      tokenUrl:
        'https://github.com/settings/tokens/new?scopes=repo,admin:repo_hook&description=D%C3%ABvSec%20demo',
    }),
  },
  {
    title: 'oauth · falls back to api-key in v1',
    tool: mockTool({
      id: 'demo-oauth',
      label: 'demo-oauth',
      setup_kind: 'oauth',
      requirement: 'Connect the tool to your account. Until OAuth is wired, paste a static token.',
      probeKind: 'shell',
      probeSpec: {command: 'demo --check', env_from_credential: 'OAUTH_TOKEN'},
    }),
  },
  {
    title: 'file-path · directory must exist on disk',
    tool: mockTool({
      id: 'demo-path',
      label: 'demo-path',
      setup_kind: 'file-path',
      requirement: 'Path to the behavioral artifact cache used for dependency diffing.',
      probeKind: 'directory-exists',
      probeSpec: {config_key: 'artifact_cache_dir'},
    }),
  },
  {
    title: 'config-block · multi-line TOML / YAML',
    tool: mockTool({
      id: 'demo-config',
      label: 'demo-config',
      setup_kind: 'config-block',
      requirement: 'Paste a TOML block declaring the tool\'s rule paths and skip rules.',
      probeKind: 'directory-exists',
      probeSpec: {config_key: 'config_toml'},
    }),
  },
];

export default function SetupCardDemo() {
  useEffect(() => {
    installDemoFetch();
  }, []);
  return (
    <main className="setup-card-demo">
      <header className="setup-card-demo-head">
        <h1>SetupCard — render branches</h1>
        <p>
          Storybook-style preview. Each card is wired to an in-page mock fetch handler, so paste any
          value, click Store / Save, then Test connection to walk through the success and failure
          paths without touching the real backend.
        </p>
      </header>
      <div className="setup-card-demo-grid">
        {mockTools.map((entry) => (
          <section key={entry.tool.id} className="setup-card-demo-cell">
            <h2 className="setup-card-demo-title">{entry.title}</h2>
            <SetupCard tool={entry.tool} />
          </section>
        ))}
      </div>
    </main>
  );
}

function mockTool({
  id,
  label,
  setup_kind,
  requirement,
  probeKind,
  probeSpec,
  tokenUrl,
}: {
  id: string;
  label: string;
  setup_kind: SetupKind;
  requirement: string;
  probeKind: 'shell' | 'http' | 'binary-version' | 'directory-exists';
  probeSpec: Record<string, string>;
  tokenUrl?: string;
}): ToolCatalogItem {
  return {
    id,
    kind: 'scanner',
    label,
    summary: 'Demo tool — not real.',
    category: 'platform-posture',
    lifecycle: 'available',
    install_state: 'not-configured',
    install: {
      method: 'manual',
      owner: 'external',
      detection: 'path-binary',
      uninstall_posture: 'manual-only',
    },
    policy: {
      local_only: false,
      writes_files: false,
      network_access: 'optional',
      external_targets: 'none',
      uses_credentials: 'required',
      destructive_action: false,
      needs_approval: false,
      allowed_for_agent_lab: false,
      stores_results_locally: true,
      sends_source_off_machine: false,
      requires_human_setup: true,
      default_enabled: false,
    },
    capabilities: {
      finding_categories: [],
      evidence_types: [],
      scan_profiles: [],
      requires_previous_scan: false,
      requires_artifacts: false,
      requires_repo_remote: false,
    },
    derived_labels: {safety: [], install: [], agent_lab: 'blocked'},
    packs: [],
    profiles: [],
    setup_kind,
    setup_requirement: requirement,
    setup_probe: {
      kind: probeKind,
      spec: probeSpec,
    },
    setup_token_create_url: tokenUrl,
    branding: {accent_color: '#3c4b48'},
  };
}
