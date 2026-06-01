/**
 * Visually hidden until focused, this is the first focusable element on the
 * page so a keyboard user can jump straight past the 240px sidebar nav into the
 * main content region (`<main id="main-content">`) instead of tabbing through
 * every nav item on every view.
 */
export default function SkipToContent() {
  return (
    <a className="skip-link" href="#main-content">
      Skip to content
    </a>
  );
}
