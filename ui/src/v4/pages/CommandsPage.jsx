import { useDeferredValue } from 'react';
import { useCommandStore } from '../../stores/commandStore.js';
import PageSection from '../components/PageSection.jsx';

export default function CommandsPage() {
  const commandsById = useCommandStore((state) => state.commands);
  const deferredCommands = useDeferredValue(
    Object.values(commandsById).sort((left, right) => (right.timestamp || 0) - (left.timestamp || 0)),
  );

  return (
    <section className="v4-page">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Commands</p>
          <h1 className="v4-page__title">Command History</h1>
          <p className="v4-page__lede">
            The routed shell is ready for persistent audit history once the v4 REST endpoint is connected.
          </p>
        </div>
        <span className="v4-inline-badge">{deferredCommands.length} cached items</span>
      </header>

      <PageSection title="Recent Commands" eyebrow="Timeline">
        <div className="v4-table-wrap">
          <table className="v4-table">
            <thead>
              <tr>
                <th>Command ID</th>
                <th>Drone</th>
                <th>Command</th>
                <th>Status</th>
                <th>Retries</th>
              </tr>
            </thead>
            <tbody>
              {deferredCommands.length === 0 && (
                <tr>
                  <td colSpan="5" className="v4-empty">No commands have been cached yet.</td>
                </tr>
              )}
              {deferredCommands.map((command) => (
                <tr key={command.cmd_id || command.id}>
                  <td>{command.cmd_id || command.id}</td>
                  <td>{command.drone_id || command.droneId}</td>
                  <td>{command.command}</td>
                  <td>{command.status || 'UNKNOWN'}</td>
                  <td>{Math.max(0, (command.attempt_count ?? 1) - 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageSection>

      <PageSection title="Detail Pane" eyebrow="Follow-On">
        <p className="v4-muted">
          Failure reasons, preflight snapshots, and the full requested-to-acked timeline will bind to the new
          `/api/commands` contract next.
        </p>
      </PageSection>
    </section>
  );
}
