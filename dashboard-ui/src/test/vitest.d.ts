import 'vitest';

// jest-axe's `toHaveNoViolations` is registered on vitest's expect in
// src/test/setup.ts. Teach the type-checker about it so `npm run lint`
// (tsc --noEmit) stays clean.
interface AxeMatchers<R = unknown> {
  toHaveNoViolations(): R;
}

declare module 'vitest' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface Assertion<T = unknown> extends AxeMatchers<T> {}
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
