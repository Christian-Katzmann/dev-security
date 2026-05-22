// Catalog Tool detail — placeholder shell for Step 1.1. Step 3.3 fills it in
// against mockup (1): hero block with name + version + Install/Snooze,
// two-column body with Overview + Capabilities and a Technical Specs sidebar.

export type CatalogToolPageProps = {
  toolId: string;
  onBack: () => void;
};

export default function CatalogToolPage({toolId, onBack}: CatalogToolPageProps) {
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
