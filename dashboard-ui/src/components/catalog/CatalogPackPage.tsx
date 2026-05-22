// Catalog Pack detail — placeholder shell for Step 1.1. Step 3.4 fills it in
// against mockup (2): curated bundle hero, "essential utilities" grid of the
// included tools, recommended scan profile line.

export type CatalogPackPageProps = {
  packId: string;
  onBack: () => void;
  onOpenTool: (toolId: string) => void;
};

export default function CatalogPackPage({packId, onBack, onOpenTool}: CatalogPackPageProps) {
  return (
    <div className="view-stack">
      <section>
        <button type="button" onClick={onBack}>Back</button>
        <h1>Catalog pack detail</h1>
        <p>Coming up: curated bundle hero with Install Bundle + View Contents, essential utilities grid, recommended scan profile.</p>
        <p>Pack id: <code>{packId}</code></p>
      </section>
      <button type="button" onClick={() => onOpenTool('preview-tool')}>Open sample tool (preview)</button>
    </div>
  );
}
