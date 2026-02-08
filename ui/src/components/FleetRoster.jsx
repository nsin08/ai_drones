import { useFleetStore } from '../stores/fleetStore';
import { useSelectionStore } from '../stores/selectionStore';
import { useUIStore } from '../stores/uiStore';
import { ROLE_COLORS, ROLES } from '../constants';
import { sendCommand } from '../api';
import { Battery, ChevronDown } from 'lucide-react';
import { useState } from 'react';

export default function FleetRoster() {
  const drones = useFleetStore((s) => s.drones);
  const { selected, toggle, selectAll, clearSelection } = useSelectionStore();
  const { filters, setFilter } = useUIStore();
  const [roleDropdown, setRoleDropdown] = useState(null);

  let list = Object.values(drones).sort((a, b) => (a.drone_id > b.drone_id ? 1 : -1));

  // Apply filters
  if (filters.role) list = list.filter((d) => d.mission_role === filters.role || d.current_role === filters.role);
  if (filters.status) list = list.filter((d) => d.status === filters.status);
  if (filters.search) {
    const q = filters.search.toLowerCase();
    list = list.filter((d) => d.drone_id.toLowerCase().includes(q));
  }

  const isOutOfFormation = (d) => ['HOLD', 'RTL', 'LAND'].includes(d.mode);

  const handleRoleChange = async (droneId, role) => {
    setRoleDropdown(null);
    try {
      await sendCommand('set_role', { drone_id: droneId, role });
    } catch (e) {
      console.error('set_role failed', e);
    }
  };

  return (
    <div className="panel-section" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-section__title" style={{ display: 'flex', justifyContent: 'space-between' }}>
        Fleet Roster ({list.length})
        <span style={{ display: 'flex', gap: 4 }}>
          <button style={{ fontSize: '0.6rem', background: 'none', color: 'var(--accent-cyan)' }}
            onClick={() => selectAll(list.map((d) => d.drone_id))}>All</button>
          <button style={{ fontSize: '0.6rem', background: 'none', color: 'var(--text-muted)' }}
            onClick={clearSelection}>None</button>
        </span>
      </div>

      <div className="filters-row">
        <input placeholder="Search..." value={filters.search}
          onChange={(e) => setFilter('search', e.target.value)} />
        <select value={filters.role} onChange={(e) => setFilter('role', e.target.value)}>
          <option value="">All Roles</option>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
          <option value="">All Status</option>
          <option value="ACTIVE">Active</option>
          <option value="DISABLED">Disabled</option>
        </select>
      </div>

      <ul className="roster-list" style={{ flex: 1, overflowY: 'auto' }}>
        {list.map((d) => {
          const role = d.mission_role || d.current_role || 'UNKNOWN';
          const color = ROLE_COLORS[role] || ROLE_COLORS.UNKNOWN;
          const isSel = selected.has(d.drone_id);
          return (
            <li
              key={d.drone_id}
              className={`roster-item ${isSel ? 'roster-item--selected' : ''}`}
              onClick={() => toggle(d.drone_id)}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
              <span className="roster-item__id">{d.drone_id}</span>
              <span className="roster-item__role" style={{ background: color + '22', color }}>
                {role}
              </span>
              {/* Role dropdown */}
              <span style={{ position: 'relative' }}>
                <button style={{ background: 'none', color: 'var(--text-muted)', padding: 0 }}
                  onClick={(e) => { e.stopPropagation(); setRoleDropdown(roleDropdown === d.drone_id ? null : d.drone_id); }}>
                  <ChevronDown size={12} />
                </button>
                {roleDropdown === d.drone_id && (
                  <div style={{
                    position: 'absolute', top: 16, left: 0, zIndex: 10,
                    background: 'var(--bg-card)', border: '1px solid var(--border)',
                    borderRadius: 4, padding: 4, minWidth: 100,
                  }}>
                    {ROLES.map((r) => (
                      <div key={r}
                        style={{ padding: '3px 8px', fontSize: '0.68rem', cursor: 'pointer', color: ROLE_COLORS[r] }}
                        onClick={(e) => { e.stopPropagation(); handleRoleChange(d.drone_id, r); }}>
                        {r}
                      </div>
                    ))}
                  </div>
                )}
              </span>
              <span className="roster-item__bat" style={{ marginLeft: 'auto', color: (d.battery_pct ?? 100) < 20 ? 'var(--accent-red)' : 'var(--text-secondary)' }}>
                <Battery size={11} style={{ verticalAlign: 'middle' }} /> {(d.battery_pct ?? 0).toFixed(0)}%
              </span>
              <span className="roster-item__mode">{d.mode || '-'}</span>
              {isOutOfFormation(d) && <span className="roster-item__chip">OOF</span>}
            </li>
          );
        })}
      </ul>

      {selected.size > 0 && (
        <div style={{ padding: '6px 0', fontSize: '0.72rem', color: 'var(--accent-cyan)' }}>
          {selected.size} selected
        </div>
      )}
    </div>
  );
}
