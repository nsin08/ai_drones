import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('UI ErrorBoundary caught', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: 16,
          color: 'var(--text-primary)',
          background: 'var(--bg-secondary)',
          height: '100%',
        }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>UI failed to load</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Check console logs for the first error line.
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
