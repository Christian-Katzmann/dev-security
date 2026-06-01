import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {axe} from 'jest-axe';
import {useState} from 'react';
import {describe, expect, it, vi} from 'vitest';
import Dialog from './Dialog';

function ThreeButtonDialog({onClose = () => {}}: {onClose?: () => void}) {
  return (
    <>
      <button type="button">outside</button>
      <Dialog ariaLabel="Test dialog" onClose={onClose} backdropClassName="backdrop" className="panel">
        <button type="button">first</button>
        <button type="button">middle</button>
        <button type="button">last</button>
      </Dialog>
    </>
  );
}

describe('Dialog primitive (S-041)', () => {
  it('exposes dialog semantics (role, aria-modal, accessible name)', () => {
    render(<ThreeButtonDialog />);
    const dialog = screen.getByRole('dialog', {name: 'Test dialog'});
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('moves focus to the first focusable control on open', () => {
    render(<ThreeButtonDialog />);
    expect(screen.getByText('first')).toHaveFocus();
  });

  it('closes on Escape', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ThreeButtonDialog onClose={onClose} />);
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('traps Tab inside the dialog (wraps last -> first)', async () => {
    const user = userEvent.setup();
    render(<ThreeButtonDialog />);
    // Focus starts on "first". Tab forward to the last control...
    await user.tab();
    expect(screen.getByText('middle')).toHaveFocus();
    await user.tab();
    expect(screen.getByText('last')).toHaveFocus();
    // ...and one more Tab wraps back to the first, never reaching "outside".
    await user.tab();
    expect(screen.getByText('first')).toHaveFocus();
  });

  it('traps Shift+Tab inside the dialog (wraps first -> last)', async () => {
    const user = userEvent.setup();
    render(<ThreeButtonDialog />);
    expect(screen.getByText('first')).toHaveFocus();
    await user.tab({shift: true});
    expect(screen.getByText('last')).toHaveFocus();
  });

  it('restores focus to the opener when it unmounts', async () => {
    const user = userEvent.setup();

    function Wrapper() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            open dialog
          </button>
          {open && (
            <Dialog ariaLabel="Closable" onClose={() => setOpen(false)} backdropClassName="bd" className="p">
              <button type="button">inside</button>
            </Dialog>
          )}
        </>
      );
    }

    render(<Wrapper />);
    const opener = screen.getByText('open dialog');
    await user.click(opener);
    expect(screen.getByText('inside')).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(opener).toHaveFocus();
  });

  it('has no axe violations', async () => {
    const {container} = render(<ThreeButtonDialog />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
