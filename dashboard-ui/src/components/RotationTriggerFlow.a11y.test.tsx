import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {axe} from 'jest-axe';
import {describe, expect, it, vi} from 'vitest';
import type {ProjectRepo, RotationSecretRow} from '../dashboardData';
import RotationTriggerFlow from './RotationTriggerFlow';

// A real, complex migrated modal — the strongest "key rendered view" the
// harness can assert against. On the initial confirm step it does no network
// I/O, so it renders cleanly in jsdom.
const repo: ProjectRepo = {name: 'example.app', path: '/Users/dev/example.app'};

const secret: RotationSecretRow = {
  secret: 'STRIPE_API_KEY',
  class: 'B-API',
  rotation_warning: null,
  soak_window_minutes: 15,
  console_url: null,
  status: 'ROTATED',
  last_rotated_at: null,
  days_since_rotation: null,
  cadence_days: 90,
  next_rotation_due: null,
  rotation_id: null,
  in_grace_until: null,
  needs_attention: false,
  manually_marked: false,
  override_kind: null,
  emergency_mode: false,
  active_job_id: null,
};

function renderFlow() {
  const onClose = vi.fn();
  const onDone = vi.fn();
  const result = render(
    <RotationTriggerFlow repo={repo} secret={secret} onClose={onClose} onDone={onDone} />,
  );
  return {onClose, onDone, ...result};
}

describe('RotationTriggerFlow routes through the shared Dialog (S-041)', () => {
  it('renders as an accessible modal dialog', () => {
    renderFlow();
    const dialog = screen.getByRole('dialog', {name: /Rotate STRIPE_API_KEY/});
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('closes on Escape via the shared primitive', async () => {
    const user = userEvent.setup();
    const {onClose} = renderFlow();
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('has no axe violations on the confirm step', async () => {
    const {container} = renderFlow();
    expect(await axe(container)).toHaveNoViolations();
  });
});
