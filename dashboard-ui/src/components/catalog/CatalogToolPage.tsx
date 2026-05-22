// Catalog Tool detail — placeholder shell for Step 1.1. Step 3.3 fills it in
// against mockup (1): hero block with name + version + Install/Snooze,
// two-column body with Overview + Capabilities and a Technical Specs sidebar.
//
// Step 1.2: hook wired in. Step 3.3 will reach for the specific tool by id
// against `catalog`, render its detail, and call installManagedTool /
// uninstallManagedTool from this hook.

import {DashboardSummary} from '../../dashboardData';
import {useCatalogData} from './useCatalogData';

export type CatalogToolPageProps = {
  summary: DashboardSummary;
  onRefresh: () => Promise<void>;
  toolId: string;
  onBack: () => void;
};

export default function CatalogToolPage({summary, onRefresh, toolId, onBack}: CatalogToolPageProps) {
  void useCatalogData(summary, onRefresh);
  return (
    <div className="view-stack">
      <section>
        <button type="button" onClick={onBack}>Back</button>
        <h1>Catalog tool detail</h1>
        <p>Coming up: hero with Install / Snooze and a two-column body of overview, capabilities, and technical specs.</p>
        <p>Tool id: <code>{toolId}</code></p>
      </section>
    </div>
  );
}
