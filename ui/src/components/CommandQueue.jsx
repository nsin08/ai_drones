import { useMemo } from 'react';
import { useCommandStore } from '../stores/commandStore';
import { ACK_TIMEOUT_SEC } from '../constants';

const STATUS_DOT = {
  REQUESTED: '#60a5fa',   /* blue */
  ACKED:     '#34d399',   /* green */
  FAILED:    '#f87171',   /* red */
  TIMED_OUT: '#fbbf24',   /* amber */
  COMPLETED_LATE: '#fbbf24',
  FAILED_LATE: '#f87171',
};

function timeSince(ts) {
  if (!ts) return '-';
  const diff = Math.round((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  return `${Math.floor(diff / 60)}m ago`;
}

export default function CommandQueue() {
  const commandMap = useCommandStore((s) => s.commands);
  const clearOld = useCommandStore((s) => s.clearOld);

  const commands = useMemo(
    () => Object.values(commandMap).sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)),
    [commandMap],
  );

  const toMs = (ts) => {
    if (!ts) return null;
    if (typeof ts === 'string') {
      const parsed = Date.parse(ts);
      return parsed || null;
    }
    return ts < 1e12 ? ts * 1000 : ts;
  };

  return (
    <div className="panel-section" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-section__title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Command Queue</span>
        <button
          onClick={() => clearOld(0)}
          style={{
            fontSize: '0.6rem', cursor: 'pointer', background: 'none',
            border: '1px solid var(--text-dim)', color: 'var(--text-dim)',
            borderRadius: 4, padding: '2px 6px',
          }}
        >
          Clear
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {commands.length === 0 && (
          <div style={{ color: 'var(--text-dim)', fontSize: '0.7rem', padding: 8 }}>
            No commands sent yet.
          </div>
        )}
        {commands.map((c) => {
          const dot = STATUS_DOT[c.status] || '#666';
          const sentAt = toMs(c.sentAt ?? c.sent_epoch ?? c.timestamp);
          const ackAt = toMs(c.ackAt ?? c.ack_timestamp);
          const isLateAck = c.late || (c.status || '').includes('LATE') ||
            (c.status === 'ACKED' && ackAt && sentAt && (ackAt - sentAt > ACK_TIMEOUT_SEC * 1000));
          return (
            <div key={c.id || c.cmd_id} className="command-row">
              <span className="command-status-dot" style={{ background: dot }} title={c.status} />
              <span className="command-verb">{c.command}</span>
              <span className="command-target">{c.droneId || c.drone_id}</span>
              {isLateAck && <span className="late-ack-badge">LATE</span>}
              <span className="command-time">{timeSince(sentAt)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
