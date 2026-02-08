import CommandQueue from './CommandQueue';
import QuickActions from './QuickActions';

export default function RightPanel() {
  return (
    <div className="right-panel">
      <QuickActions />
      <CommandQueue />
    </div>
  );
}
