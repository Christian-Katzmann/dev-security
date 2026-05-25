// Catalog Browse — the list view. Matches mockup (4): paper-card featured tool
// banner with one primary Install action and a quiet "View docs" secondary, a
// single category chip row beneath the banner, then a 4-up grid of tool cards.
//
// Rules of the road for this route, all from DESIGN.md:
//   - One primary action on the page (Install on the featured banner).
//   - Severity is earned (§3.4) — setup and policy pills use neutral copy,
//     never security-severity language.
//   - Paper surface, not the sage/teal hero — same rhythm as CatalogHome.
//   - 30–40% air; sentence case; no looping motion; mono only on telemetry.
//
// Search lives in the top toolbar (the global pattern), not on this page.
// Coming-soon tools still appear in the grid but in a muted variant with no
// install button — they teach future coverage without faking active state.
//
// Three open questions resolved here, with the rule in code, not a curated
// string:
//   1. Featured tool — pick the tool with the highest pack count that has a
//      managed install path (so the Install CTA is meaningful). Alphabetical
//      tiebreaker. Falls back to the highest-pack-count non-coming-soon tool.
//   2. Priority pill — derived from policy fields, not category:
//        Approval required → policy.needs_approval.
//        Needs context     → policy.uses_credentials === 'required' or
//                            policy.external_targets !== 'none'.
//        Default check     → policy.default_enabled.
//      Tools that match nothing get no pill — sparingly is the point.
//      Note: these pills use info/neutral/ready treatment. Critical/elevated/
//      warning/low words stay reserved for security severity.
//   3. Filter row on mobile — chips wrap rather than horizontally scroll.
//      Calmer wins. No carousel chrome at any breakpoint.

import {useCallback, useMemo, useState} from 'react';
import {ArrowRight, Download} from 'lucide-react';
import {
  DashboardSummary,
  ToolCatalogItem,
  ToolCategory,
} from '../../dashboardData';
import {
  canInstallViaPackageManager,
  catalogCategoryLabels,
  catalogCategoryOrder,
  catalogIcon,
  catalogInstallLabels,
  catalogInstallMethodLabels,
  previewCanInstall,
} from './catalogHelpers';
import {useCatalogData} from './useCatalogData';

export type CatalogBrowseProps = {
  summary: DashboardSummary;
  onRefresh: () => Promise<void>;
  onOpenTool: (toolId: string) => void;
  onBack: () => void;
};

type Priority = {label: string; tone: 'info' | 'neutral' | 'low'};

function isComingSoon(tool: ToolCatalogItem): boolean {
  return tool.lifecycle === 'coming-soon' || tool.install_state === 'coming-soon';
}

function isBrowsable(tool: ToolCatalogItem): boolean {
  return tool.lifecycle !== 'hidden' && tool.lifecycle !== 'deprecated';
}

function hasManagedInstallPath(tool: ToolCatalogItem): boolean {
  return tool.install.method !== 'built-in' && tool.install.method !== 'none' && !isComingSoon(tool);
}

function priorityForTool(tool: ToolCatalogItem): Priority | null {
  if (isComingSoon(tool)) return null;
  if (tool.policy.needs_approval) return {label: 'Approval required', tone: 'info'};
  if (tool.policy.uses_credentials === 'required' || tool.policy.external_targets !== 'none') {
    return {label: 'Needs context', tone: 'neutral'};
  }
  if (tool.policy.default_enabled) return {label: 'Default check', tone: 'low'};
  return null;
}

// Featured-tool rule: highest pack-count tool that has a real install path, so
// the Install CTA on the banner is meaningful. Alphabetical tiebreaker keeps
// the choice stable across renders. Fallback walks the same ranking without
// the install-path filter so the banner never disappears entirely.
function pickFeatured(catalog: ToolCatalogItem[]): ToolCatalogItem | null {
  const browsable = catalog.filter((tool) => isBrowsable(tool) && !isComingSoon(tool));
  if (!browsable.length) return null;
  const score = (tool: ToolCatalogItem) => tool.packs.length;
  const byRank = [...browsable].sort((a, b) => {
    const diff = score(b) - score(a);
    return diff !== 0 ? diff : a.label.localeCompare(b.label);
  });
  return byRank.find(hasManagedInstallPath) ?? byRank[0];
}

function bottomMonoRight(tool: ToolCatalogItem): string {
  // The mockup shows license. DëvSec doesn't carry license data on
  // ToolCatalogItem yet, so surface the next-most-informative concrete value:
  // the install method (Homebrew, uv tool, Built in, Manual, etc.). A real
  // license field would be the right thing to add to ToolCatalogItem
  // eventually, but inventing one here would be worse than this honest stand-in.
  return catalogInstallMethodLabels[tool.install.method];
}

function bottomMonoLeft(tool: ToolCatalogItem): string {
  return catalogInstallLabels[tool.install_state];
}

export default function CatalogBrowse({summary, onRefresh, onOpenTool, onBack}: CatalogBrowseProps) {
  const {catalog, mutation, installManagedTool, installViaPackageManager} = useCatalogData(summary, onRefresh);
  const [activeCategory, setActiveCategory] = useState<ToolCategory | 'all'>('all');

  const browsable = useMemo(
    () => catalog.filter(isBrowsable),
    [catalog],
  );
  const featured = useMemo(() => pickFeatured(browsable), [browsable]);

  const categories = useMemo(() => {
    return catalogCategoryOrder.filter((category) =>
      browsable.some((tool) => tool.category === category && !isComingSoon(tool)),
    ).slice(0, 5);
  }, [browsable]);

  const filtered = useMemo(() => {
    if (activeCategory === 'all') return browsable;
    return browsable.filter((tool) => tool.category === activeCategory);
  }, [browsable, activeCategory]);

  // Sort order: not-installed tools first (so install candidates are immediately
  // visible without scanning), then installed tools alphabetically, then
  // coming-soon at the bottom (still visible for future coverage).
  const sortedGrid = useMemo(() => {
    const rank = (tool: ToolCatalogItem): number => {
      if (isComingSoon(tool)) return 2;
      if (tool.install_state === 'missing') return 0;
      return 1;
    };
    return [...filtered].sort((a, b) => {
      const diff = rank(a) - rank(b);
      if (diff !== 0) return diff;
      return a.label.localeCompare(b.label);
    });
  }, [filtered]);

  // The Featured Install button must reflect the *runtime* install state and
  // dispatch to the install path that actually fits the tool. Managed and
  // package-manager (homebrew, uv-tool) tools can be installed in one click
  // from the banner; manual-install tools need the tool page (copy command
  // + mark installed) so the banner falls through to "View tool" for them.
  const featuredPackageInstallable = featured ? canInstallViaPackageManager(featured) : false;
  const featuredManagedInstallable = featured ? previewCanInstall(featured.install_preview) : false;
  const featuredInstallEnabled = featuredPackageInstallable || featuredManagedInstallable;
  const featuredMutating = featured && mutation?.toolId === featured.id && mutation.status === 'running';

  const installFeatured = useCallback(() => {
    if (!featured || !featuredInstallEnabled) return;
    if (featuredPackageInstallable) {
      void installViaPackageManager(featured.id);
      return;
    }
    void installManagedTool(featured.id);
  }, [featured, featuredInstallEnabled, featuredPackageInstallable, installManagedTool, installViaPackageManager]);

  const openFeaturedTool = useCallback(() => {
    if (!featured) return;
    onOpenTool(featured.id);
  }, [featured, onOpenTool]);

  return (
    <div className="catalog-browse">
      <button type="button" className="catalog-browse-back" onClick={onBack}>
        Back to catalog
      </button>

      {featured && (
        <section className="catalog-browse-featured">
          <div className="catalog-browse-featured-copy">
            <div className="eyebrow">Featured</div>
            <h1>Featured: {featured.label}</h1>
            <p>{featured.summary}</p>
            <div className="catalog-browse-featured-actions">
              {featuredInstallEnabled && (
                <button
                  type="button"
                  className="catalog-browse-cta"
                  onClick={installFeatured}
                  disabled={Boolean(featuredMutating)}
                >
                  <Download size={15} />
                  {featuredMutating ? 'Installing...' : 'Install'}
                </button>
              )}
              <button
                type="button"
                className="catalog-browse-cta-secondary"
                onClick={openFeaturedTool}
              >
                <ArrowRight size={14} />
                View tool
              </button>
            </div>
            {mutation && featured && mutation.toolId === featured.id && mutation.status !== 'running' && (
              <p className={`catalog-browse-featured-message ${mutation.status}`}>{mutation.message}</p>
            )}
          </div>
          <div className="catalog-browse-featured-art" aria-hidden>
            <div className="catalog-browse-featured-mark" data-category={featured.category}>
              {catalogIcon(featured.category)}
            </div>
          </div>
        </section>
      )}

      <section className="catalog-browse-filters" aria-label="Filter tools by category">
        <span className="catalog-browse-filter-label">Filter by</span>
        <div className="catalog-browse-chip-row">
          <button
            type="button"
            className={`catalog-browse-chip ${activeCategory === 'all' ? 'active' : ''}`}
            onClick={() => setActiveCategory('all')}
          >
            All tools
          </button>
          {categories.map((category) => (
            <button
              key={category}
              type="button"
              className={`catalog-browse-chip ${activeCategory === category ? 'active' : ''}`}
              onClick={() => setActiveCategory(category)}
            >
              {catalogCategoryLabels[category]}
            </button>
          ))}
        </div>
      </section>

      <section className="catalog-browse-grid" aria-label="Tool catalog">
        {sortedGrid.length === 0 ? (
          <p className="catalog-browse-empty">No tools in this category yet.</p>
        ) : sortedGrid.map((tool) => {
          const soon = isComingSoon(tool);
          const priority = soon ? null : priorityForTool(tool);
          return (
            <article
              key={tool.id}
              className={`catalog-browse-card ${soon ? 'muted' : ''}`}
              data-category={tool.category}
            >
              <button
                type="button"
                className="catalog-browse-card-button"
                onClick={() => onOpenTool(tool.id)}
                aria-label={`View ${tool.label}`}
              >
                <header className="catalog-browse-card-head">
                  <div className="catalog-browse-card-icon">{catalogIcon(tool.category)}</div>
                  {soon ? (
                    <span className="catalog-browse-pill neutral">Coming soon</span>
                  ) : priority ? (
                    <span className={`catalog-browse-pill ${priority.tone}`}>
                      <i />
                      {priority.label}
                    </span>
                  ) : null}
                </header>
                <h3>{tool.label}</h3>
                <p>{tool.summary}</p>
                <footer className="catalog-browse-card-foot">
                  <span>{bottomMonoLeft(tool)}</span>
                  <span>{bottomMonoRight(tool)}</span>
                </footer>
              </button>
            </article>
          );
        })}
      </section>
    </div>
  );
}
