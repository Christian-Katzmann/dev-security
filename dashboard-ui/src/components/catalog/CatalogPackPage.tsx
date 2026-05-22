// Catalog Pack detail — matches mockup (2): a paper hero block for the curated
// bundle (eyebrow + tool count, display headline, summary, primary "Install
// Bundle" + secondary "View contents") and an Essential Utilities 2-up grid
// of the included tools. A "Recommended scan profile" line lives between the
// hero and the grid so the user can leave with one concrete next action even
// when broad pack install is disabled.
//
// Open questions resolved here:
//   1. Install Bundle copy (MVP gap). No pack-level install exists yet, so
//      the hero never offered a disabled "Install bundle" / "View contents"
//      pair pretending to be buttons. Instead the slot holds one calm note
//      that names the gap and points at the utility grid below, where each
//      tool installs individually.
//   2. Display-only packs (External Surface, IaC, Platform Posture, Advanced
//      Dependency) share the same hero shape — the note shifts to a coming-
//      soon framing.
//   3. Mockup's ENTERPRISE / FREE / PRO tier badges don't map to DëvSec data.
//      They are replaced with the pack-role chip (Included / Optional /
//      Coming soon) on every utility card — the role is real catalog data and
//      it is what a user actually needs to know about a tool inside a pack.

import {useCallback, useMemo} from 'react';
import {ArrowLeft, ArrowRight, Package, SlidersHorizontal} from 'lucide-react';
import {
  DashboardSummary,
  SecurityPackCatalogItem,
  SecurityPackTool,
  ToolPackRole,
} from '../../dashboardData';
import {
  catalogIcon,
  catalogInstallLabels,
  catalogPackIconCategory,
} from './catalogHelpers';
import {useCatalogData} from './useCatalogData';

export type CatalogPackPageProps = {
  summary: DashboardSummary;
  onRefresh: () => Promise<void>;
  packId: string;
  onBack: () => void;
  onOpenTool: (toolId: string) => void;
  onOpenProfile: (profile: string) => void;
};

const roleLabels: Record<ToolPackRole, string> = {
  included: 'Included',
  optional: 'Optional',
  'coming-soon': 'Coming soon',
};

const roleTones: Record<ToolPackRole, 'low' | 'info' | 'neutral'> = {
  included: 'low',
  optional: 'info',
  'coming-soon': 'neutral',
};

function isComingSoonPack(pack: SecurityPackCatalogItem): boolean {
  return pack.mvp_state !== 'real';
}

function isComingSoonTool(tool: SecurityPackTool): boolean {
  return tool.lifecycle === 'coming-soon' || tool.install_state === 'coming-soon';
}

// Tool ordering inside the grid: required-installed tools first, then
// optional, then coming-soon. Alphabetical inside each bucket to stay stable.
function sortTools(tools: SecurityPackTool[]): SecurityPackTool[] {
  const bucket = (tool: SecurityPackTool) => {
    if (isComingSoonTool(tool)) return 2;
    if (tool.role === 'optional') return 1;
    return 0;
  };
  return [...tools].sort((a, b) => {
    const diff = bucket(a) - bucket(b);
    if (diff !== 0) return diff;
    return a.label.localeCompare(b.label);
  });
}

export default function CatalogPackPage({
  summary,
  onRefresh,
  packId,
  onBack,
  onOpenTool,
  onOpenProfile,
}: CatalogPackPageProps) {
  const {packs} = useCatalogData(summary, onRefresh);
  const pack = useMemo(() => packs.find((item) => item.id === packId), [packs, packId]);
  const tools = useMemo(() => (pack ? sortTools(pack.tools) : []), [pack]);

  const onOpenProfileClick = useCallback(() => {
    if (pack?.primary_profile) onOpenProfile(pack.primary_profile);
  }, [pack, onOpenProfile]);

  if (!pack) {
    return (
      <div className="catalog-pack">
        <button type="button" className="catalog-pack-back" onClick={onBack}>
          <ArrowLeft size={14} />
          Back to catalog
        </button>
        <section className="catalog-pack-missing">
          <h1>Pack not found</h1>
          <p>This pack id is not in the current summary. It may have been removed or renamed.</p>
        </section>
      </div>
    );
  }

  const comingSoon = isComingSoonPack(pack);
  const toolCount = pack.tools.length;
  const heroCategory = catalogPackIconCategory(pack.id);
  const installNote = comingSoon
    ? 'This bundle is on the roadmap. The included tools below install individually once each one ships.'
    : 'Pack-level install is on the roadmap. Each utility in the grid below installs on its own.';

  return (
    <div className="catalog-pack">
      <button type="button" className="catalog-pack-back" onClick={onBack}>
        <ArrowLeft size={14} />
        Back to catalog
      </button>

      <section className="catalog-pack-hero" data-category={heroCategory}>
        <div className="catalog-pack-hero-eyebrow">
          <span className="catalog-pack-eyebrow-label">
            <i />
            {comingSoon ? 'Coming soon bundle' : 'Curated bundle'}
          </span>
          <span className="catalog-pack-eyebrow-meta">{toolCount} {toolCount === 1 ? 'tool' : 'tools'}</span>
        </div>
        <h1>{pack.label}.</h1>
        <p>{pack.summary}</p>
        <p className="catalog-pack-hero-note">{installNote}</p>
      </section>

      {pack.primary_profile && (
        <section className="catalog-pack-profile">
          <div className="catalog-pack-profile-copy">
            <span className="eyebrow">Recommended scan profile</span>
            <p>
              Pair this pack with the <code>{pack.primary_profile}</code> profile when you are ready to run a scan.
            </p>
          </div>
          <button type="button" className="catalog-pack-profile-cta" onClick={onOpenProfileClick}>
            <SlidersHorizontal size={14} />
            Open profile
          </button>
        </section>
      )}

      <section className="catalog-pack-utilities" aria-label="Essential utilities">
        <header className="catalog-pack-utilities-head">
          <div>
            <h2>Essential utilities</h2>
            <p>The tools this bundle covers. Each one installs and runs on its own — the bundle just explains how they fit together.</p>
          </div>
          <span className="catalog-pack-utilities-meta">
            <Package size={14} />
            {toolCount} {toolCount === 1 ? 'tool' : 'tools'}
          </span>
        </header>
        <div className="catalog-pack-utility-grid">
          {tools.map((tool) => {
            const soon = isComingSoonTool(tool);
            return (
              <article
                key={tool.id}
                className={`catalog-pack-utility ${soon ? 'muted' : ''}`}
                data-category={heroCategory}
              >
                <header className="catalog-pack-utility-head">
                  <div className="catalog-pack-utility-icon">{catalogIcon(heroCategory)}</div>
                  <span className={`catalog-pack-utility-role ${roleTones[tool.role]}`}>
                    {roleLabels[tool.role]}
                  </span>
                </header>
                <h3>{tool.label}</h3>
                <p>{tool.summary}</p>
                <footer className="catalog-pack-utility-foot">
                  <span className="catalog-pack-utility-status">{catalogInstallLabels[tool.install_state]}</span>
                  <button
                    type="button"
                    className="catalog-pack-utility-action"
                    onClick={() => onOpenTool(tool.id)}
                  >
                    View tool
                    <ArrowRight size={14} />
                  </button>
                </footer>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
