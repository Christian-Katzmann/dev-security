import {useCallback, useEffect, useRef, type KeyboardEvent, type ReactNode, type RefObject} from 'react';

// Selector for everything a keyboard can land on inside the dialog. Disabled
// controls and tabindex="-1" elements are intentionally excluded from the trap
// rotation — they can still be focused programmatically, just not Tab-reached.
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'summary',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export type DialogProps = {
  /** Accessible name for the dialog (maps to aria-label). */
  ariaLabel: string;
  /** Called on Escape, backdrop click, or any explicit close control. */
  onClose: () => void;
  children: ReactNode;
  /** Class applied to the full-screen backdrop that hosts the panel. */
  backdropClassName?: string;
  /** Class applied to the role="dialog" panel element. */
  className?: string;
  /** Clicking the backdrop closes the dialog. Defaults to true. */
  closeOnBackdropClick?: boolean;
  /**
   * Control to focus on open instead of the first focusable element — e.g. a
   * primary text input. Lets a caller keep a crafted initial focus without an
   * `autoFocus` attribute, which would steal focus before this primitive can
   * record the opener for focus-restore.
   */
  initialFocusRef?: RefObject<HTMLElement | null>;
};

/**
 * The single keyboard-accessible modal surface for the dashboard.
 *
 * Owns the three things every modal must do and none of the four were doing:
 *  - trap Tab/Shift+Tab focus inside the panel,
 *  - close on Escape,
 *  - restore focus to the control that opened it on unmount.
 *
 * It is deliberately presentation-agnostic: callers pass their own backdrop and
 * panel classes so each modal keeps its existing chrome (Tailwind utility
 * overlays or Mistglass `*-modal` classes) while sharing one behavior layer.
 */
export default function Dialog({
  ariaLabel,
  onClose,
  children,
  backdropClassName,
  className,
  closeOnBackdropClick = true,
  initialFocusRef,
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Move focus into the dialog on mount and restore it to the opener on unmount.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    if (panel) {
      const target = initialFocusRef?.current ?? panel.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (target ?? panel).focus();
    }
    return () => {
      // Guard: the opener may have been removed from the DOM while the modal
      // was open (e.g. the row it lived in re-rendered).
      if (opener && typeof opener.focus === 'function' && document.contains(opener)) {
        opener.focus();
      }
    };
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (focusable.length === 0) {
        // Nothing tabbable: keep focus pinned to the panel itself.
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !panel.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last || !panel.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  return (
    <div
      className={backdropClassName}
      onKeyDown={handleKeyDown}
      onMouseDown={
        closeOnBackdropClick
          ? (event) => {
              if (event.target === event.currentTarget) onClose();
            }
          : undefined
      }
    >
      <div ref={panelRef} role="dialog" aria-modal="true" aria-label={ariaLabel} tabIndex={-1} className={className}>
        {children}
      </div>
    </div>
  );
}
