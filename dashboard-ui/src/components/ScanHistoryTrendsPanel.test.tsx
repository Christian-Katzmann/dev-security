import {render, screen, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, describe, expect, it, vi, type Mock} from 'vitest';
import ScanHistoryTrendsPanel from './ScanHistoryTrendsPanel';
import {emptySummary, type DashboardSummary, type ScanHistoryItem} from '../dashboardData';

function scan(id: string, health: number, finishedAt: string): ScanHistoryItem {
  return {
    id,
    repo_name: 'acme',
    started_at: finishedAt,
    finished_at: finishedAt,
    health_score: health,
    status: 'ok',
    profile: 'quick',
  };
}

// Three scans, newest last by timestamp. trendValues() orders oldest -> newest;
// the pickers order newest -> oldest. Default head = newest (s3), base = next
// older same-repo scan (s2).
const history: ScanHistoryItem[] = [
  scan('s1', 60, '2026-05-28T10:00:00Z'),
  scan('s2', 72, '2026-05-29T10:00:00Z'),
  scan('s3', 84, '2026-05-30T10:00:00Z'),
];

const summary: DashboardSummary = {
  ...emptySummary,
  repos: [],
  history,
  findings: [],
};

const diffPayload = {
  base: {scan_id: 's2', repo_name: 'acme', profile: 'quick', started_at: '2026-05-29T10:00:00Z', finished_at: '2026-05-29T10:00:00Z', health_score: 72, status: 'ok'},
  head: {scan_id: 's3', repo_name: 'acme', profile: 'quick', started_at: '2026-05-30T10:00:00Z', finished_at: '2026-05-30T10:00:00Z', health_score: 84, status: 'ok'},
  health_delta: 12,
  same_repo: true,
  counts: {new: 1, recurring: 2, resolved: 3},
  new_cases: [],
  recurring_cases: [],
  resolved_cases: [{case_id: 'R-1', title: 'Leaked token rotated', next_step: 'Verified — not found in scan s3.'}],
};

function fetchMock() {
  return vi.fn(async (input: RequestInfo | URL) => ({
    ok: true,
    status: 200,
    json: async () => diffPayload,
    text: async () => JSON.stringify(diffPayload),
  } as Response));
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('ScanHistoryTrendsPanel (S-039, S-042)', () => {
  it('renders the full per-scan posture series, not just a 7-bar week proxy', async () => {
    render(<ScanHistoryTrendsPanel summary={summary} />);
    // The sparkline reads from the real history series (trendValues).
    const sparkline = screen.getByRole('img', {name: /posture trend across 3 scans/i});
    expect(sparkline).toBeInTheDocument();
    // Latest health is surfaced from the series (84/100).
    expect(screen.getByText('Health 84/100')).toBeInTheDocument();
    // Let the on-mount diff fetch settle so the render stays act()-clean.
    await waitFor(() => expect(fetch).toHaveBeenCalled());
  });

  it('drives /api/scan-diff with the default base and head on mount', async () => {
    render(<ScanHistoryTrendsPanel summary={summary} />);
    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
    const url = String((fetch as Mock).mock.calls[0][0]);
    expect(url).toContain('/api/scan-diff');
    expect(url).toContain('base=s2');
    expect(url).toContain('head=s3');
    // The diff result renders from the response.
    expect(await screen.findByText('+12')).toBeInTheDocument();
    expect(screen.getByText('Leaked token rotated')).toBeInTheDocument();
  });

  it('lets the user compare two arbitrary scans — base selection flows into the diff request', async () => {
    const user = userEvent.setup();
    render(<ScanHistoryTrendsPanel summary={summary} />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());

    // Pick an older base (s1) against the same head (s3): the request must
    // carry BOTH chosen scans, proving arbitrary scan-to-scan comparison.
    const baseSelect = screen.getByLabelText('Base scan');
    await user.selectOptions(baseSelect, 's1');

    await waitFor(() => {
      const last = String((fetch as Mock).mock.calls.at(-1)?.[0]);
      expect(last).toContain('base=s1');
      expect(last).toContain('head=s3');
    });
  });

  it('shows an honest empty state with fewer than two scans', () => {
    render(<ScanHistoryTrendsPanel summary={{...summary, history: [history[0]]}} />);
    expect(screen.getByText(/run at least two scans/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('Base scan')).not.toBeInTheDocument();
  });

  it('surfaces the closure-proof binding for resolved cases', async () => {
    render(<ScanHistoryTrendsPanel summary={summary} />);
    const list = await screen.findByRole('list');
    expect(within(list).getByText(/verified — not found in scan s3/i)).toBeInTheDocument();
  });
});
