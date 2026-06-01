import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {describe, expect, it} from 'vitest';

// S-040 is enforced in CSS, not in a component, so the regression guard reads
// the stylesheet directly: a global :focus-visible ring must exist, and no
// control may opt out by suppressing its focus indicator. vitest runs from the
// dashboard-ui package root, so resolve the stylesheet relative to cwd.
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

/** Returns the body of `<selector> { ... }` for the first matching rule. */
function ruleBody(selector: string): string {
  const start = css.indexOf(selector);
  if (start === -1) return '';
  const open = css.indexOf('{', start);
  const close = css.indexOf('}', open);
  return css.slice(open + 1, close);
}

describe('global focus-visible ring (S-040)', () => {
  it('defines a focus-ring design token', () => {
    expect(css).toMatch(/--focus-ring:/);
  });

  it('paints a visible :focus-visible outline on the primary controls', () => {
    for (const el of ['a', 'button', 'input', 'select', 'textarea']) {
      expect(css).toMatch(new RegExp(`${el}:focus-visible`));
    }
    const body = ruleBody('button:focus-visible');
    expect(body).toMatch(/outline:\s*2px solid var\(--focus-ring\)/);
    expect(body).toMatch(/outline-offset/);
  });

  it('does not let the setup-card controls suppress their focus ring', () => {
    for (const selector of ['.setup-card-input:focus-visible', '.setup-card-textarea:focus-visible']) {
      const body = ruleBody(selector);
      expect(body).not.toMatch(/outline:\s*none/);
      expect(body).toMatch(/outline:\s*2px solid var\(--focus-ring\)/);
    }
  });

  it('leaves no control :focus-visible rule that sets outline:none', () => {
    // `.mist-main` is the programmatically-focused content landing region (the
    // skip-link target), not an interactive control — it is allowed to opt out.
    const offenders = [...css.matchAll(/([^{}]*):focus-visible\s*\{([^}]*)\}/g)]
      .filter((m) => /outline:\s*none/.test(m[2]))
      .filter((m) => !/\.mist-main/.test(m[1]));
    expect(offenders).toHaveLength(0);
  });
});
