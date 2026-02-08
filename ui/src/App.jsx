import { useEffect } from 'react';
import { getSocket } from './socket';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import CenterMap from './components/CenterMap';
import RightPanel from './components/RightPanel';
import BottomStrip from './components/BottomStrip';
import ConfirmDialog from './components/ConfirmDialog';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  useEffect(() => { getSocket(); }, []);

  return (
    <div className="app-shell">
      <TopBar />
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
    </div>
  );
}
