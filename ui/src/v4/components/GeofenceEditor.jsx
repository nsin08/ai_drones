/**
 * GeofenceEditor — click-to-add geofence polygon point list (W15 G12).
 *
 * Geofence points are added by clicking the map in MissionBuilderMap (the
 * parent page manages combined state).  This component renders the point list
 * and a Clear button.
 *
 * Props:
 *   points   : [{lat, lng}]
 *   onClear  : () => void
 *   onDelete : (idx) => void
 */

export default function GeofenceEditor({ points = [], onClear, onDelete }) {
  const isValid = points.length >= 3;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontSize: '13px', color: '#374151', fontWeight: 600 }}>
          Geofence points{' '}
          <span style={{ fontWeight: 400, color: '#9ca3af' }}>
            ({points.length}/3 min)
          </span>
        </span>
        {points.length > 0 && (
          <button
            onClick={onClear}
            style={{
              fontSize: '12px',
              color: '#ef4444',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Clear all
          </button>
        )}
      </div>

      {points.length === 0 ? (
        <p style={{ fontSize: '12px', color: '#9ca3af', fontStyle: 'italic' }}>
          Hold Shift and click the map to define geofence vertices.
        </p>
      ) : (
        <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {points.map((pt, idx) => (
            <li
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '5px 8px',
                background: '#fffbeb',
                borderRadius: '5px',
                border: '1px solid #fde68a',
                fontSize: '12px',
                fontFamily: 'monospace',
              }}
            >
              <span style={{ flex: 1, color: '#78350f' }}>
                G{idx + 1}  {pt.lat.toFixed(5)}, {pt.lng.toFixed(5)}
              </span>
              <button
                aria-label="Remove geofence point"
                onClick={() => onDelete(idx)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d97706' }}
              >
                ✕
              </button>
            </li>
          ))}
        </ol>
      )}

      {!isValid && points.length > 0 && (
        <p style={{ fontSize: '11px', color: '#f59e0b', marginTop: '6px' }}>
          ⚠ Need at least 3 points to form a valid geofence.
        </p>
      )}
      {isValid && (
        <p style={{ fontSize: '11px', color: '#10b981', marginTop: '6px' }}>
          ✓ Geofence polygon is valid ({points.length} vertices).
        </p>
      )}
    </div>
  );
}
