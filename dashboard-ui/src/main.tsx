import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import SetupCardDemo from './components/catalog/SetupCardDemo.tsx';
import ErrorBoundary from './components/ErrorBoundary.tsx';
import './index.css';

function installHardRefreshShortcut() {
  window.addEventListener(
    'keydown',
    (event) => {
      const key = event.key.toLowerCase();
      const usesCommand = event.metaKey && !event.ctrlKey;
      const usesControl = event.ctrlKey && !event.metaKey;

      if (key !== 'r' || event.altKey || (!usesCommand && !usesControl)) {
        return;
      }

      event.preventDefault();
      const url = new URL(window.location.href);
      url.searchParams.set('_refresh', String(Date.now()));
      window.location.replace(url);
    },
    {capture: true},
  );
}

installHardRefreshShortcut();

// Hidden visual-verification route. Opening `?setupCardDemo=1` boots the
// SetupCard storybook page instead of the dashboard. Mock fetch handlers
// inside the demo component intercept every `/api/...` call so no real
// network traffic or Keychain access happens during a walkthrough.
const showSetupCardDemo = new URLSearchParams(window.location.search).has('setupCardDemo');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      {showSetupCardDemo ? <SetupCardDemo /> : <App />}
    </ErrorBoundary>
  </StrictMode>,
);
