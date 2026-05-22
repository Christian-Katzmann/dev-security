// Catalog Home — placeholder shell for Step 1.1. Step 3.1 fills it in against
// the base marketplace mockup. Sits at the top of the catalog IA: hero +
// Featured Packs + Popular Plugins.
//
// Back navigation: Home has no Back — it's the root of the catalog. Browse /
// Tool / Pack all return to the route they came from (Home or Browse). The
// router passes a single onBack callback; the receiving route decides what to
// say. Single "Back" label per route keeps the chrome calm — no per-route
// breadcrumb strip.
//
// Step 1.2: the hook is wired in so future rebuild steps inherit the data
// plumbing for free. Placeholders stay visible — Step 3.1 starts rendering
// from `catalog`, `packs`, and the install/uninstall handlers.

import {DashboardSummary} from '../../dashboardData';
import {useCatalogData} from './useCatalogData';

export type CatalogHomeProps = {
  summary: DashboardSummary;
  onRefresh: () => Promise<void>;
  onOpenBrowse: () => void;
  onOpenTool: (toolId: string) => void;
  onOpenPack: (packId: string) => void;
};

export default function CatalogHome({summary, onRefresh, onOpenBrowse, onOpenTool, onOpenPack}: CatalogHomeProps) {
  // Subscribe to the shared catalog data so Step 3.1 only needs to render it.
  // Intentionally unused for now — keep the placeholder visible.
  void useCatalogData(summary, onRefresh);
  return (
    <div className="view-stack">
      <section>
        <h1>Catalog home</h1>
        <p>Coming up: hero with one CTA, three featured packs, four popular plugins.</p>
      </section>
      <div style={{display: 'flex', gap: 12, flexWrap: 'wrap'}}>
        <button type="button" onClick={onOpenBrowse}>Browse all tools (preview)</button>
        <button type="button" onClick={() => onOpenTool('preview-tool')}>Open sample tool (preview)</button>
        <button type="button" onClick={() => onOpenPack('preview-pack')}>Open sample pack (preview)</button>
      </div>
    </div>
  );
}
