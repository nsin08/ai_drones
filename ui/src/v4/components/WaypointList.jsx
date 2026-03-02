/**
 * WaypointList — ordered list of mission waypoints with reorder and delete (W15 G12).
 *
 * Props:
 *   waypoints   : [{id, lat, lng, alt_m}]
 *   onReorder   : (fromIdx, toIdx) => void
 *   onDelete    : (id) => void
 *   onAltChange : (id, newAlt) => void
 */

export default function WaypointList({ waypoints = [], onReorder, onDelete, onAltChange }) {
  if (waypoints.length === 0) {
    return (
      <p className="v4-card__meta" style={{ fontStyle: 'italic', color: '#9ca3af' }}>
        Click on the map to add waypoints.
      </p>
    );
  }

  return (
    <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {waypoints.map((wp, idx) => (
        <li
          key={wp.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 10px',
            background: '#f9fafb',
            borderRadius: '6px',
            border: '1px solid #e5e7eb',
            fontSize: '13px',
          }}
        >
          {/* Index badge */}
          <span
            style={{
              minWidth: '22px',
              height: '22px',
              borderRadius: '50%',
              background: '#3b82f6',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '11px',
            }}
          >
            {idx + 1}
          </span>

          {/* Coordinates */}
          <span style={{ flex: 1, fontFamily: 'monospace', fontSize: '12px', color: '#374151' }}>
            {wp.lat.toFixed(5)}, {wp.lng.toFixed(5)}
          </span>

          {/* Alt input */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#6b7280' }}>
            Alt
            <input
              type="number"
              value={wp.alt_m}
              min={0}
              max={400}
              style={{ width: '56px', padding: '2px 4px', borderRadius: '4px', border: '1px solid #d1d5db', fontSize: '12px' }}
              onChange={(e) => onAltChange(wp.id, Number(e.target.value))}
            />
            m
          </label>

          {/* Reorder buttons */}
          <button
            aria-label="Move up"
            disabled={idx === 0}
            onClick={() => onReorder(idx, idx - 1)}
            style={{ background: 'none', border: 'none', cursor: idx === 0 ? 'default' : 'pointer', padding: '2px 4px', color: idx === 0 ? '#d1d5db' : '#6b7280' }}
          >
            ▲
          </button>
          <button
            aria-label="Move down"
            disabled={idx === waypoints.length - 1}
            onClick={() => onReorder(idx, idx + 1)}
            style={{ background: 'none', border: 'none', cursor: idx === waypoints.length - 1 ? 'default' : 'pointer', padding: '2px 4px', color: idx === waypoints.length - 1 ? '#d1d5db' : '#6b7280' }}
          >
            ▼
          </button>

          {/* Delete */}
          <button
            aria-label="Remove waypoint"
            onClick={() => onDelete(wp.id)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', fontWeight: 700, padding: '2px 6px' }}
          >
            ✕
          </button>
        </li>
      ))}
    </ol>
  );
}
