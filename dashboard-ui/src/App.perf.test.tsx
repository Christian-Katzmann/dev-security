import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, describe, expect, it, vi, type Mock} from 'vitest';
import * as dashboardData from './dashboardData';

// S-028 regression guard — the deterministic stand-in for the manual React
// Profiler pass. `search` is local state on the 4,500-line root, so every
// keystroke re-renders the whole shell. The derived passes (`filterSummaryByTarget`
// in the root, `displayCases` in CasesView) are now memoized on `[summary, target]`,
// so typing must NOT re-invoke them. Pre-memoization these fired once per keystroke;
// the assertions below would have read +N. We spy on the two derived passes that
// `App.tsx` imports from `dashboardData` (the local `activeCaseList`/`buildActivity`
// are wrapped in the same `useMemo` pattern alongside them).
vi.mock('./dashboardData', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./dashboardData')>();
  return {
    ...actual,
    filterSummaryByTarget: vi.fn(actual.filterSummaryByTarget),
    displayCases: vi.fn(actual.displayCases),
  };
});

// A large seeded summary: 60 active cases give the derived passes real work to do
// (sort + map + attention filter), so a re-run would be a measurable cost.
const seededSummary = {
  repos: [],
  history: [],
  findings: [],
  active_cases: Array.from({length: 60}, (_, i) => ({
    case_id: `C-${i}`,
    repo_name: `repo-${i % 6}`,
    severity: i % 3 === 0 ? 'high' : i % 3 === 1 ? 'critical' : 'medium',
    title: `Seeded case ${i}`,
    category: 'secrets',
    action_level: 'fix_now',
    created_at: '2026-05-30T10:00:00Z',
  })),
};

function jsonResponse(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as Response;
}

beforeEach(() => {
  (dashboardData.filterSummaryByTarget as Mock).mockClear();
  (dashboardData.displayCases as Mock).mockClear();
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/summary')) return jsonResponse(seededSummary);
      if (url.includes('/api/projects')) return jsonResponse({repos: []});
      return jsonResponse({});
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('S-028 — memoized derived state survives search-box typing', () => {
  it('does not re-run filterSummaryByTarget on every keystroke', async () => {
    const {default: App} = await import('./App');
    render(<App />);

    const filterSpy = dashboardData.filterSummaryByTarget as Mock;
    // Wait until the seeded summary has flowed through the derived pass.
    await waitFor(() =>
      expect(filterSpy.mock.calls.some((call) => (call[0] as {active_cases?: unknown[]})?.active_cases?.length === 60)).toBe(true),
    );
    // Let the projects fetch settle so the call count is stable.
    await waitFor(() => expect((global.fetch as Mock).mock.calls.length).toBeGreaterThanOrEqual(2));

    const search = screen.getByLabelText('Search the dashboard');
    const callsBeforeTyping = filterSpy.mock.calls.length;

    await userEvent.type(search, 'stripe token');

    // Memoized on [summary, target]; neither changes while typing → zero re-runs.
    expect(filterSpy.mock.calls.length).toBe(callsBeforeTyping);
    expect((search as HTMLInputElement).value).toBe('stripe token');
  });
});
