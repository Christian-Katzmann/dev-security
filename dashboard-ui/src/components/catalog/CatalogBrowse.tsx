// Catalog Browse — placeholder shell for Step 1.1. Step 3.2 fills it in
// against mockup (4): featured tool banner, single filter row, 4-up tool grid.

export type CatalogBrowseProps = {
  onOpenTool: (toolId: string) => void;
  onBack: () => void;
};

export default function CatalogBrowse({onOpenTool, onBack}: CatalogBrowseProps) {
  return (
    <div className="view-stack">
      <section>
        <button type="button" onClick={onBack}>Back to catalog home</button>
        <h1>Catalog browse</h1>
        <p>Coming up: featured tool banner, single filter chip row, 4-up tool grid.</p>
      </section>
      <button type="button" onClick={() => onOpenTool('preview-tool')}>Open sample tool (preview)</button>
    </div>
  );
}
