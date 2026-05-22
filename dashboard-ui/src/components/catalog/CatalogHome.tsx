// Catalog Home — the catalog root. Sets the visual rhythm the other three
// routes inherit. Hero banner with one primary action, three featured Security
// Packs, four popular plugins. No filter chrome, no severity chips on home
// cards (DESIGN.md §3.4 — severity is earned), no install-state chips on home
// cards. The page is intentionally light so the §0 smell test holds: 30–40%
// air, sentence case, one primary action.

import {useMemo} from 'react';
import {ArrowRight, Package, ShieldCheck} from 'lucide-react';
import {DashboardSummary, SecurityPackCatalogItem, ToolCatalogItem} from '../../dashboardData';
import {
  catalogCategoryLabels,
  catalogIcon,
  catalogPackIconCategory,
  catalogPackOrder,
} from './catalogHelpers';
import {useCatalogData} from './useCatalogData';

export type CatalogHomeProps = {
  summary: DashboardSummary;
  onRefresh: () => Promise<void>;
  onOpenBrowse: () => void;
  onOpenTool: (toolId: string) => void;
  onOpenPack: (packId: string) => void;
};

// Featured-pack rule: take the first three "real" MVP packs in the canonical
// catalogPackOrder. If fewer than three real packs exist (test data, early
// install), fall back to the canonical order so the row still renders 3.
function pickFeaturedPacks(packs: SecurityPackCatalogItem[]): SecurityPackCatalogItem[] {
  const byId = new Map(packs.map((pack) => [pack.id, pack]));
  const ordered = catalogPackOrder
    .map((id) => byId.get(id))
    .filter((pack): pack is SecurityPackCatalogItem => Boolean(pack));
  const real = ordered.filter((pack) => pack.mvp_state === 'real');
  const featured = real.slice(0, 3);
  if (featured.length === 3) return featured;
  for (const pack of ordered) {
    if (featured.length >= 3) break;
    if (!featured.some((existing) => existing.id === pack.id)) featured.push(pack);
  }
  return featured;
}

// Popular-plugins rule: the cross-cutting tools — tools that belong to the
// most packs. Honest signal (it's just `packs.length`), no curated string list.
// Tiebreak alphabetical so the order is stable across renders. Coming-soon and
// hidden tools are excluded; this row is meant to drive an install.
function pickPopularPlugins(catalog: ToolCatalogItem[]): ToolCatalogItem[] {
  const eligible = catalog.filter((item) => item.lifecycle !== 'hidden' && item.lifecycle !== 'coming-soon' && item.lifecycle !== 'deprecated' && item.install_state !== 'coming-soon');
  return [...eligible]
    .sort((a, b) => {
      const packDiff = b.packs.length - a.packs.length;
      if (packDiff !== 0) return packDiff;
      return a.label.localeCompare(b.label);
    })
    .slice(0, 4);
}

export default function CatalogHome({summary, onRefresh, onOpenBrowse, onOpenTool, onOpenPack}: CatalogHomeProps) {
  const {catalog, packs} = useCatalogData(summary, onRefresh);
  const featuredPacks = useMemo(() => pickFeaturedPacks(packs), [packs]);
  const popularPlugins = useMemo(() => pickPopularPlugins(catalog), [catalog]);

  return (
    <div className="catalog-home">
      <section className="catalog-home-hero">
        <div className="catalog-home-hero-copy">
          <div className="eyebrow">Tool catalog</div>
          <h1>Secure your stack with one click.</h1>
          <p>Browse curated security packs and standalone plugins. Install what you need, when you need it — DëvSec leaves your other tooling alone.</p>
          <button type="button" className="catalog-home-cta" onClick={onOpenBrowse}>
            Browse all tools
            <ArrowRight size={16} />
          </button>
        </div>
        <div className="catalog-home-hero-art" aria-hidden>
          <ShieldCheck size={96} strokeWidth={1.25} />
        </div>
      </section>

      <section className="catalog-home-section">
        <header className="catalog-home-section-head">
          <div>
            <h2>Featured security packs</h2>
            <p>Curated bundles for specific compliance and threat models.</p>
          </div>
          <button type="button" className="catalog-home-section-link" onClick={onOpenBrowse}>
            View all packs
            <ArrowRight size={14} />
          </button>
        </header>
        <div className="catalog-home-pack-grid">
          {featuredPacks.map((pack) => {
            const category = catalogPackIconCategory(pack.id);
            const toolCount = pack.tools.length;
            return (
              <article key={pack.id} className="catalog-home-pack-card" data-category={category}>
                <div className="catalog-home-pack-icon">{catalogIcon(category)}</div>
                <h3>{pack.label}</h3>
                <p>{pack.summary}</p>
                <div className="catalog-home-pack-meta">
                  <Package size={14} />
                  <span>{toolCount} {toolCount === 1 ? 'tool' : 'tools'} included</span>
                </div>
                <button type="button" className="catalog-home-card-action" onClick={() => onOpenPack(pack.id)}>
                  View bundle
                </button>
              </article>
            );
          })}
        </div>
      </section>

      <section className="catalog-home-section">
        <header className="catalog-home-section-head">
          <div>
            <h2>Popular plugins</h2>
            <p>Cross-cutting tools that show up across the most packs.</p>
          </div>
        </header>
        <div className="catalog-home-plugin-grid">
          {popularPlugins.map((tool) => (
            <article key={tool.id} className="catalog-home-plugin-card" data-category={tool.category}>
              <header className="catalog-home-plugin-head">
                <div className="catalog-home-plugin-icon">{catalogIcon(tool.category)}</div>
                <div className="catalog-home-plugin-title">
                  <h3>{tool.label}</h3>
                  <span>{catalogCategoryLabels[tool.category]}</span>
                </div>
              </header>
              <p>{tool.summary}</p>
              <button type="button" className="catalog-home-card-action primary" onClick={() => onOpenTool(tool.id)}>
                One-click install
              </button>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
