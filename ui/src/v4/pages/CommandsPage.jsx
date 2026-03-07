import { useEffect, useState, useDeferredValue } from 'react';
import { useCommandStore } from '../../stores/commandStore.js';
import { listCommands } from '../lib/apiClient.js';
import PageSection from '../components/PageSection.jsx';

const STATUS_COLORS = Object.freeze({
  REQUESTED: '#60a5fa',
  RETRYING: '#fbbf24',
  ACKED: '#34d399',
  TIMED_OUT: '#f87171',
  FAILED: '#ef4444',
  NACKED: '#fb923c',
});

function timeSince(ts) {
  if (!ts) return '—';
  const sec = Math.floor((Date.now() / 1000) - ts);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

export default function CommandsPage() {
  const commandsById = useCommandStore((state) => state.commands);
  const upsertCommand = useCommandStore((state) => state.upsertCommand);
  const [selectedId, setSelectedId] = useState(null);
  const [filter, setFilter] = useState('');

  // Fetch from /api/commands on mount
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await listCommands({ limit: 100 });
        const items = data?.items || data?.commands || (Array.isArray(data) ? data : []);
        items.forEach((cmd) => {
          upsertCommand({
            ...cmd,
            timestamp: (Date.parse(cmd.created_at || cmd.updated_at) || Date.now()) / 1000,
          });
        });
      } catch (err) {
        console.error('Failed to fetch commands:', err);
      }
    })();
    return () => { active = false; };
  }, [upsertCommand]);

  const allCommands = useDeferredValue(
    Object.values(commandsById).sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)),
  );

  const filtered = filter
    ? allCommands.filter((c) => {
        const q = filter.toLowerCase();
        return (
          (c.drone_id || c.droneId || '').toLowerCase().includes(q) ||
          (c.command || '').toLowerCase().includes(q) ||
          (c.status || '').toLowerCase().includes(q)
        );
      })
    : allCommands;

  const selected = filtered.find((c) => (c.cmd_id || c.id) === selectedId) || null;

  return (
    <section className="v4-page">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Commands</p>
          <h1 className="v4-page__title">Command History</h1>
          <p className="v4-page__lede">
            Live command feed with status tracking. Rows update in real-time via WebSocket.
          </p>
        </div>
        <span className="v4-inline-badge">{allCommands.length} command(s)</span>
      </header>

      {/* Filter */}
      <div style={{ marginBottom: '12px' }}>
        <input
          type="text"
          placeholder="Filter by drone, command, or status…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{
            width: '100%', maxWidth: '360px', padding: '8px 12px', borderRadius: '6px',
            border: '1px solid #374151', background: '#1e293b', color: '#e2e8f0',
            fontSize: '13px',
          }}
        />
      </div>

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
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan="6" className="v4-empty">No commands found.</td>
                </tr>
              )}
              {filtered.map((command) => {
                const cmdId = command.cmd_id || command.id;
                const status = (command.status || 'UNKNOWN').toUpperCase();
                const isSelected = cmdId === selectedId;
                return (
                  <tr
                    key={cmdId}
                    onClick={() => setSelectedId(cmdId)}
                    style={{
                      cursor: 'pointer',
                      background: isSelected ? 'rgba(59, 130, 246, 0.15)' : undefined,
                      borderLeft: isSelected ? '3px solid #3b82f6' : '3px solid transparent',
                    }}
                  >
                    <td className="v4-table__cell--mono">{cmdId}</td>
                    <td>{command.drone_id || command.droneId}</td>
                    <td>{command.command}</td>
                    <td>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '6px',
                      }}>
                        <span style={{
                          width: '8px', height: '8px', borderRadius: '50%',
                          background: STATUS_COLORS[status] || '#64748b',
                          display: 'inline-block',
                        }} />
                        {status}
                        {command.late && (
                          <span style={{ fontSize: '10px', color: '#f59e0b', fontWeight: 700 }}>LATE</span>
                        )}
                      </span>
                    </td>
                    <td>{Math.max(0, (command.attempt_count ?? 1) - 1)}</td>
                    <td style={{ fontSize: '12px', color: '#9ca3af' }}>{timeSince(command.timestamp)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </PageSection>

      {/* Detail Pane */}
      <PageSection title="Command Detail" eyebrow={selected ? (selected.cmd_id || selected.id) : 'Select a command'}>
        {selected ? (
          <div className="v4-card-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))' }}>
            <div className="v4-card">
              <h3 className="v4-card__title">Command</h3>
              <p className="v4-card__meta">{selected.command}</p>
            </div>
            <div className="v4-card">
              <h3 className="v4-card__title">Drone</h3>
              <p className="v4-card__meta">{selected.drone_id || selected.droneId}</p>
            </div>
            <div className="v4-card">
              <h3 className="v4-card__title">Status</h3>
              <p className="v4-card__meta" style={{ color: STATUS_COLORS[(selected.status || '').toUpperCase()] || '#94a3b8' }}>
                {(selected.status || 'UNKNOWN').toUpperCase()}
              </p>
            </div>
            <div className="v4-card">
              <h3 className="v4-card__title">Attempts</h3>
              <p className="v4-card__meta">{selected.attempt_count ?? 1}</p>
            </div>
            <div className="v4-card">
              <h3 className="v4-card__title">Requested By</h3>
              <p className="v4-card__meta">{selected.requested_by || selected.operator || '—'}</p>
            </div>
            {selected.rejection_reason && (
              <div className="v4-card">
                <h3 className="v4-card__title">Rejection Reason</h3>
                <p className="v4-card__meta" style={{ color: '#ef4444' }}>{selected.rejection_reason}</p>
              </div>
            )}
            {selected.preflight_snapshot && (
              <div className="v4-card" style={{ gridColumn: '1 / -1' }}>
                <h3 className="v4-card__title">Preflight Snapshot</h3>
                <pre style={{ fontSize: '11px', color: '#94a3b8', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(selected.preflight_snapshot, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <p className="v4-muted">Click a command row above to see full details.</p>
        )}
      </PageSection>
    </section>
  );
}
