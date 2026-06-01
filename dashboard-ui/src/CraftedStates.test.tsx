import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {axe} from 'jest-axe';
import {describe, expect, it, vi} from 'vitest';
import {FirstFetchErrorState, HistoryRecoveryNotice, LoadingState, RunErrorNotice} from './App';
import type {HistoryRecovery} from './dashboardData';

// Step 3.1 crafted states. These pin the three lenses Stage D was missing:
// the corruption-recovery banner, the differentiated scan-failure cards, and
// the loading / first-fetch-failure states. They regress loudly if any of them
// silently drops back to bare text or signals a state by color alone.

const recovery: HistoryRecovery = {
  status: 'recovered',
  message:
    'Your scan history could not be read and was quarantined. The previous database is preserved on this machine; a fresh history was started.',
  quarantined_path: '/Users/you/.security-observatory/history.corrupt-2026-06-01.sqlite3',
};

describe('HistoryRecoveryNotice (corruption recovery banner)', () => {
  it('renders the calm preserved-and-recovered message', () => {
    render(<HistoryRecoveryNotice recovery={recovery} />);
    expect(screen.getByText('History recovered')).toBeInTheDocument();
    expect(screen.getByText('Your scan history was quarantined and rebuilt.')).toBeInTheDocument();
    expect(screen.getByText(/preserved on this machine/)).toBeInTheDocument();
  });

  it('surfaces the quarantined path so the operator can find the old database', () => {
    render(<HistoryRecoveryNotice recovery={recovery} />);
    expect(screen.getByText(recovery.quarantined_path as string)).toBeInTheDocument();
  });

  it('omits the path row when no path is provided', () => {
    render(<HistoryRecoveryNotice recovery={{...recovery, quarantined_path: null}} />);
    expect(screen.queryByText('Preserved at')).not.toBeInTheDocument();
  });

  it('carries its meaning in words, not color alone (a screen reader hears the full state)', () => {
    const {container} = render(<HistoryRecoveryNotice recovery={recovery} />);
    // The eyebrow + headline + body together name the event with no reliance on
    // the green register; strip the markup and the sentence still stands.
    expect(container.textContent).toContain('History recovered');
    expect(container.textContent).toContain('quarantined and rebuilt');
  });

  it('has no axe violations', async () => {
    const {container} = render(<HistoryRecoveryNotice recovery={recovery} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('RunErrorNotice (differentiated scan-failure states)', () => {
  it('routes a missing tool to Verification, not a retry', () => {
    const onOpenVerification = vi.fn();
    const onRetry = vi.fn();
    render(
      <RunErrorNotice
        error={{kind: 'missing-tool', message: 'Semgrep is not installed.'}}
        onOpenVerification={onOpenVerification}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText('Setup needed')).toBeInTheDocument();
    expect(screen.getByRole('button', {name: /Open Verification/})).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: /Try again/})).not.toBeInTheDocument();
  });

  it('offers a retry for an interrupted run', async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(<RunErrorNotice error={{kind: 'errored', message: 'Lost contact with the running check.'}} onRetry={onRetry} />);
    expect(screen.getByText('Run interrupted')).toBeInTheDocument();
    await user.click(screen.getByRole('button', {name: /Try again/}));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('offers a retry for a check that ran but failed', () => {
    render(<RunErrorNotice error={{kind: 'failed', message: 'The scan reported a failure.'}} onRetry={vi.fn()} />);
    expect(screen.getByText('Check failed')).toBeInTheDocument();
    expect(screen.getByRole('button', {name: /Try again/})).toBeInTheDocument();
  });

  it('keeps a precondition quiet — distinct copy, no action', () => {
    render(<RunErrorNotice error={{kind: 'validation', message: 'Select a repository first.'}} onRetry={vi.fn()} onOpenVerification={vi.fn()} />);
    expect(screen.getByText('Before you run')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('falls back to a per-kind supporting line when no detail is supplied', () => {
    render(<RunErrorNotice error={{kind: 'failed', message: 'The scan reported a failure.'}} onRetry={vi.fn()} />);
    expect(screen.getByText(/ran to completion but reported a failure/)).toBeInTheDocument();
  });

  it('prefers a caller-supplied detail over the per-kind fallback', () => {
    render(<RunErrorNotice error={{kind: 'errored', message: 'Run stopped.', detail: 'ECONNREFUSED 127.0.0.1:8876'}} onRetry={vi.fn()} />);
    expect(screen.getByText('ECONNREFUSED 127.0.0.1:8876')).toBeInTheDocument();
    expect(screen.queryByText(/transient hiccup/)).not.toBeInTheDocument();
  });

  it('has no axe violations across every kind', async () => {
    for (const kind of ['missing-tool', 'errored', 'failed', 'validation'] as const) {
      const {container} = render(
        <RunErrorNotice error={{kind, message: `${kind} headline`}} onRetry={vi.fn()} onOpenVerification={vi.fn()} />,
      );
      expect(await axe(container)).toHaveNoViolations();
    }
  });
});

describe('LoadingState (§7.6)', () => {
  it('exposes a polite live region with a caption', () => {
    render(<LoadingState label="Loading your security posture" />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('Loading your security posture')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const {container} = render(<LoadingState />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('FirstFetchErrorState (§7.5 first-fetch failure)', () => {
  it('reads as a connection problem, not data loss, and offers a retry', async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(<FirstFetchErrorState detail="Dashboard API returned 503" onRetry={onRetry} />);
    expect(screen.getByText("We couldn't load your security data.")).toBeInTheDocument();
    expect(screen.getByText(/scan history is untouched/)).toBeInTheDocument();
    expect(screen.getByText('Dashboard API returned 503')).toBeInTheDocument();
    await user.click(screen.getByRole('button', {name: /Try again/}));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('renders without a detail line when none is given', () => {
    render(<FirstFetchErrorState detail={null} onRetry={vi.fn()} />);
    expect(screen.getByText('Can\'t reach the dashboard')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const {container} = render(<FirstFetchErrorState detail="boom" onRetry={vi.fn()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
