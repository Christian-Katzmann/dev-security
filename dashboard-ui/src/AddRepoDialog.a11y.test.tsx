import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {axe} from 'jest-axe';
import {useState} from 'react';
import {describe, expect, it, vi} from 'vitest';
import {AddRepoDialog} from './App';

// AddRepoDialog is the first-run gateway modal. Stage D migrated it onto the
// shared focus-trapping `Dialog` primitive (S-041), so these specs pin the
// behaviors that migration must preserve: dialog semantics, crafted initial
// focus on the path input, a real Tab trap, Escape-to-close, and zero axe
// violations. They regress loudly if the modal ever drifts off `Dialog` again.
function Harness({onClose = () => {}, onSubmit = () => {}}: {onClose?: () => void; onSubmit?: (path: string) => void}) {
  return (
    <>
      <button type="button">outside</button>
      <AddRepoDialog knownRepos={[]} existingRepos={[]} onSubmit={onSubmit} onClose={onClose} />
    </>
  );
}

describe('AddRepoDialog (S-041 — on the shared Dialog primitive)', () => {
  it('exposes dialog semantics (role, aria-modal, accessible name)', () => {
    render(<Harness />);
    const dialog = screen.getByRole('dialog', {name: 'Add a repository'});
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('focuses the path input on open (crafted initial focus preserved)', () => {
    render(<Harness />);
    expect(screen.getByPlaceholderText('/Users/you/code/your-project')).toHaveFocus();
  });

  it('traps Tab inside the dialog, never reaching the page behind it', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const dialog = screen.getByRole('dialog', {name: 'Add a repository'});
    const outside = screen.getByText('outside');
    // Walk forward past every control; focus must stay inside the panel and
    // wrap, never landing on the button rendered behind the modal.
    for (let i = 0; i < 6; i += 1) {
      await user.tab();
      expect(outside).not.toHaveFocus();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it('closes on Escape', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<Harness onClose={onClose} />);
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('restores focus to the opener when it closes', async () => {
    const user = userEvent.setup();

    function OpenerHarness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            open add-repo
          </button>
          {open && <AddRepoDialog knownRepos={[]} existingRepos={[]} onSubmit={() => {}} onClose={() => setOpen(false)} />}
        </>
      );
    }

    render(<OpenerHarness />);
    const opener = screen.getByText('open add-repo');
    await user.click(opener);
    expect(screen.getByPlaceholderText('/Users/you/code/your-project')).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(opener).toHaveFocus();
  });

  it('has no axe violations', async () => {
    const {container} = render(<Harness />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
