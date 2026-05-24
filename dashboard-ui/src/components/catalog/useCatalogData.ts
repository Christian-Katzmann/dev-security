// useCatalogData — single source of truth for catalog data and the
// install/uninstall mutation state machine.
//
// Lifted out of ToolCatalogBrowse so all four catalog routes (Home, Browse,
// Tool, Pack) can share the same plumbing instead of each re-deriving the
// runtime map and re-implementing the managed-install fetch.
//
// Scope decision (Step 1.2 open question): mutation state is scoped to the
// hook call site, not lifted higher. Each route mounts useCatalogData, gets
// its own mutation slot, and resets when the route unmounts. The user
// installs from a route, sees feedback inline, then navigates away — there is
// no flow that asks "show me the install status from the route I left."
// Reset semantics are intentional, not a bug to fix later.
//
// All pure derivations (label maps, status buckets, copy fragments) live in
// catalogHelpers.tsx so they remain trivially testable.

import {useCallback, useMemo, useState} from 'react';
import {
  DashboardSummary,
  ScannerDoctorItem,
  SecurityPackCatalogItem,
  ToolCatalogItem,
  securityPackItems,
  toolCatalogItems,
} from '../../dashboardData';
import {responseErrorMessage} from '../../uiHelpers';
import {CatalogMutationState, catalogRuntimeMap} from './catalogHelpers';

export type UseCatalogDataResult = {
  catalog: ToolCatalogItem[];
  packs: SecurityPackCatalogItem[];
  runtime: Map<string, ScannerDoctorItem>;
  mutation: CatalogMutationState;
  installManagedTool: (toolId: string) => Promise<void>;
  installViaHomebrew: (toolId: string) => Promise<void>;
  uninstallManagedTool: (toolId: string, ownershipId?: string | null) => Promise<void>;
  resetMutation: () => void;
};

export function useCatalogData(
  summary: DashboardSummary,
  onRefresh: () => Promise<void>,
): UseCatalogDataResult {
  const catalog = useMemo(() => toolCatalogItems(summary), [summary]);
  const packs = useMemo(() => securityPackItems(summary), [summary]);
  const runtime = useMemo(() => catalogRuntimeMap(summary), [summary]);
  const [mutation, setMutation] = useState<CatalogMutationState>(null);

  const installManagedTool = useCallback(async (toolId: string) => {
    setMutation({toolId, kind: 'install', status: 'running', message: 'Installing managed copy...'});
    try {
      const response = await fetch('/api/managed-tools/install', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({toolId, confirmManagedInstall: true}),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Managed install failed.'));
      await onRefresh();
      setMutation({toolId, kind: 'install', status: 'complete', message: 'Managed copy installed and catalog refreshed.'});
    } catch (err) {
      setMutation({toolId, kind: 'install', status: 'error', message: err instanceof Error ? err.message : 'Managed install failed.'});
    }
  }, [onRefresh]);

  const installViaHomebrew = useCallback(async (toolId: string) => {
    setMutation({toolId, kind: 'install', status: 'running', message: 'Running brew install...'});
    try {
      const response = await fetch('/api/tools/install-via-pkg', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({toolId, confirmHomebrewInstall: true}),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Homebrew install failed.'));
      const body = await response.json().catch(() => ({}));
      await onRefresh();
      if (body && body.success === false) {
        const tail = String(body.stderr || body.stdout || '').trim().split('\n').slice(-3).join('\n');
        setMutation({toolId, kind: 'install', status: 'error', message: tail || 'brew install returned non-zero.'});
        return;
      }
      setMutation({toolId, kind: 'install', status: 'complete', message: 'Installed via Homebrew. Catalog refreshed.'});
    } catch (err) {
      setMutation({toolId, kind: 'install', status: 'error', message: err instanceof Error ? err.message : 'Homebrew install failed.'});
    }
  }, [onRefresh]);

  const uninstallManagedTool = useCallback(async (toolId: string, ownershipId?: string | null) => {
    if (!ownershipId) {
      setMutation({toolId, kind: 'uninstall', status: 'error', message: 'DëvSec ownership evidence is missing, so uninstall is blocked.'});
      return;
    }
    setMutation({toolId, kind: 'uninstall', status: 'running', message: 'Removing managed copy...'});
    try {
      const response = await fetch('/api/managed-tools/uninstall', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({toolId, ownershipId, confirmManagedUninstall: true}),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Managed uninstall failed.'));
      await onRefresh();
      setMutation({toolId, kind: 'uninstall', status: 'complete', message: 'Managed copy removed; detected user-owned tools were left alone.'});
    } catch (err) {
      setMutation({toolId, kind: 'uninstall', status: 'error', message: err instanceof Error ? err.message : 'Managed uninstall failed.'});
    }
  }, [onRefresh]);

  const resetMutation = useCallback(() => setMutation(null), []);

  return {catalog, packs, runtime, mutation, installManagedTool, installViaHomebrew, uninstallManagedTool, resetMutation};
}
