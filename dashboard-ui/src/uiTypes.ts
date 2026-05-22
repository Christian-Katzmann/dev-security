// Cross-cutting UI types shared between App.tsx and component-local modules
// like components/catalog/. Kept here so importing the catalog helpers does
// not pull App.tsx into a circular dependency.

export type Tone = 'low' | 'warn' | 'high' | 'crit' | 'info' | 'neutral';
