import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
