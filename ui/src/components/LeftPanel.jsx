import MissionSetup from './MissionSetup';
import FleetRoster from './FleetRoster';

export default function LeftPanel() {
  return (
    <div className="left-panel">
      <MissionSetup />
      <FleetRoster />
    </div>
  );
}
