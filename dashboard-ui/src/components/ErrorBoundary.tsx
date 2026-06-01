import {Component, type ErrorInfo, type ReactNode} from 'react';

type Props = {children: ReactNode};
type State = {error: Error | null; copied: boolean};

// Top-level boundary so a render-time throw anywhere in the dashboard degrades
// to a crafted fallback instead of white-screening the whole app. Local-first:
// the error is logged to the console only and offered for manual copy — nothing
// is sent off the machine.
export default class ErrorBoundary extends Component<Props, State> {
  state: State = {error: null, copied: false};

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {error};
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Dashboard render error', error, info.componentStack);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  private handleCopy = async (): Promise<void> => {
    const {error} = this.state;
    if (!error) return;
    const detail = error.stack ? `${error.message}\n\n${error.stack}` : error.message;
    try {
      await navigator.clipboard.writeText(detail);
      this.setState({copied: true});
      window.setTimeout(() => this.setState({copied: false}), 1800);
    } catch {
      // Clipboard unavailable — the detail stays visible below for manual copy.
    }
  };

  render(): ReactNode {
    const {error, copied} = this.state;
    if (!error) return this.props.children;
    const detail = error.stack ? `${error.message}\n\n${error.stack}` : error.message;
    return (
      <div className="app-error-boundary" role="alert">
        <div className="app-error-card">
          <h1>Something went wrong.</h1>
          <p>
            The dashboard hit an unexpected error and stopped rendering. Your local scan
            history is untouched — reloading usually clears it.
          </p>
          <div className="app-error-actions">
            <button type="button" className="button primary" onClick={this.handleReload}>
              Reload dashboard
            </button>
            <button type="button" className="button secondary" onClick={() => void this.handleCopy()}>
              {copied ? 'Copied error detail' : 'Copy error detail'}
            </button>
          </div>
          <details className="app-error-detail">
            <summary>Error detail</summary>
            <pre>{detail}</pre>
          </details>
        </div>
      </div>
    );
  }
}
