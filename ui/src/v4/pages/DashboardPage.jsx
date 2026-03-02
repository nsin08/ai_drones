import BottomStrip from '../../components/BottomStrip.jsx';
import CenterMap from '../../components/CenterMap.jsx';
import ConfirmDialog from '../../components/ConfirmDialog.jsx';
import ErrorBoundary from '../../components/ErrorBoundary.jsx';
import LeftPanel from '../../components/LeftPanel.jsx';
import RightPanel from '../../components/RightPanel.jsx';

export default function DashboardPage() {
  return (
    <section className="v4-page v4-dashboard">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Dashboard</p>
          <h1 className="v4-page__title">Live Operations</h1>
          <p className="v4-page__lede">
            The existing v3 monitoring stack is mounted here while the routed v4 shell is built out.
          </p>
        </div>
        <span className="v4-inline-badge">Safe command skeleton wired</span>
      </header>

      <div className="app-body">
        <LeftPanel />
        <div className="app-center">
          <ErrorBoundary>
            <CenterMap />
          </ErrorBoundary>
          <BottomStrip />
        </div>
        <RightPanel />
      </div>

      <ConfirmDialog />
    </section>
  );
}
