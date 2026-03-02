/**
 * FormationSelector — V / Line / Circle formation picker with spacing input (W15 G12).
 *
 * Props:
 *   value    : { shape: 'V' | 'LINE' | 'CIRCLE', spacing_m: number }
 *   onChange : (newValue) => void
 */

const SHAPES = [
  { id: 'V',      label: 'V Formation',   icon: '✈',  desc: 'Lead + two flanking drones' },
  { id: 'LINE',   label: 'Line',          icon: '▬',  desc: 'Sequential single-file line' },
  { id: 'CIRCLE', label: 'Circle',        icon: '⬤',  desc: 'Equidistant ring around centre' },
];

export default function FormationSelector({ value, onChange }) {
  const { shape, spacing_m } = value || { shape: 'V', spacing_m: 5 };

  return (
    <div>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '14px' }}>
        {SHAPES.map((s) => {
          const active = shape === s.id;
          return (
            <button
              key={s.id}
              onClick={() => onChange({ shape: s.id, spacing_m })}
              style={{
                flex: 1,
                padding: '12px 8px',
                borderRadius: '8px',
                border: active ? '2px solid #3b82f6' : '2px solid #e5e7eb',
                background: active ? '#eff6ff' : '#f9fafb',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ fontSize: '22px', marginBottom: '4px' }}>{s.icon}</div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: active ? '#1d4ed8' : '#374151' }}>
                {s.label}
              </div>
              <div style={{ fontSize: '10px', color: '#6b7280', marginTop: '2px' }}>{s.desc}</div>
            </button>
          );
        })}
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: '#374151' }}>
        Spacing between drones:
        <input
          type="range"
          min={2}
          max={50}
          value={spacing_m}
          onChange={(e) => onChange({ shape, spacing_m: Number(e.target.value) })}
          style={{ flex: 1 }}
        />
        <span style={{ minWidth: '40px', fontWeight: 600, color: '#1d4ed8' }}>{spacing_m} m</span>
      </label>
    </div>
  );
}
