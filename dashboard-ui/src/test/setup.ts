import '@testing-library/jest-dom/vitest';
import {cleanup} from '@testing-library/react';
import {toHaveNoViolations} from 'jest-axe';
import {afterEach, expect} from 'vitest';

// jest-axe ships its matcher for jest; register it on vitest's expect.
expect.extend(toHaveNoViolations);

// React Testing Library does not auto-clean between tests under vitest.
afterEach(() => {
  cleanup();
});
