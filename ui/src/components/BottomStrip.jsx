import { useState } from 'react';
import { useFleetStore } from '../stores/fleetStore';
import { useEventStore } from '../stores/eventStore';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts';
import { ROLE_COLORS } from '../constants';

const TABS = ['Altitude', 'Battery', 'Events'];

/* ------------------------------------------------------------------ */
/* AltitudeChart                                                       */
/* ------------------------------------------------------------------ */
function AltitudeChart({ drones }) {
  const series = Object.values(drones).map((d) => ({
    name: d.drone_id,
    data: d.trail?.map((pt, i) => ({ t: i, alt: pt.alt ?? d.altitude_m ?? d.altitude ?? 0 })) || [],
    color: ROLE_COLORS[d.mission_role || d.current_role || d.role] || '#60a5fa',
  }));

  if (!series.length) return <Empty msg="No telemetry yet" />;

  /* Flatten for shared X-axis */
  const maxLen = Math.max(...series.map((s) => s.data.length));
  const merged = [];
  for (let i = 0; i < maxLen; i++) {
    const pt = { t: i };
    series.forEach((s) => { pt[s.name] = s.data[i]?.alt ?? null; });
    merged.push(pt);
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={merged} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
        <XAxis dataKey="t" tick={{ fontSize: 10, fill: '#888' }} />
        <YAxis tick={{ fontSize: 10, fill: '#888' }} domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: 11 }} />
        {series.map((s) => (
          <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color} dot={false} strokeWidth={1.5} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ------------------------------------------------------------------ */
/* BatteryChart                                                        */
/* ------------------------------------------------------------------ */
function BatteryChart({ drones }) {
  const data = Object.values(drones)
    .sort((a, b) => a.drone_id.localeCompare(b.drone_id))
    .map((d) => ({
      name: d.drone_id,
      battery: d.battery_pct ?? d.battery ?? 0,
      color: (d.battery_pct ?? d.battery ?? 0) < 20 ? '#ef4444' : (d.battery_pct ?? d.battery ?? 0) < 40 ? '#fbbf24' : '#34d399',
    }));

  if (!data.length) return <Empty msg="No telemetry yet" />;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
        <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#888' }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#888' }} />
        <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: 11 }} />
        <Bar dataKey="battery" radius={[4, 4, 0, 0]}>
          {data.map((d, i) => <Cell key={i} fill={d.color} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ------------------------------------------------------------------ */
/* EventTimeline                                                       */
/* ------------------------------------------------------------------ */
function EventTimeline() {
  const events = useEventStore((s) => s.events);

  if (!events.length) return <Empty msg="No events yet" />;

  const toMs = (ts) => {
    if (!ts) return Date.now();
    const raw = typeof ts === 'string' ? Date.parse(ts) : ts;
    if (!raw) return Date.now();
    return raw < 1e12 ? raw * 1000 : raw;
  };

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '0 8px' }}>
      {events.map((ev, i) => (
        <div key={i} className="event-row">
          <span className="event-time">{new Date(toMs(ev.timestamp ?? ev.ts)).toLocaleTimeString()}</span>
          <span className={`event-type event-type--${ev.type}`}>{ev.type}</span>
          <span className="event-msg">{ev.message}</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Empty placeholder                                                   */
/* ------------------------------------------------------------------ */
function Empty({ msg }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-dim)', fontSize: '0.72rem' }}>
      {msg}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* BottomStrip                                                         */
/* ------------------------------------------------------------------ */
export default function BottomStrip() {
  const drones = useFleetStore((s) => s.drones);
  const [tab, setTab] = useState('Battery');

  return (
    <div className="bottom-strip">
      <div className="bottom-tabs">
        {TABS.map((t) => (
          <button key={t} className={`bottom-tab ${tab === t ? 'bottom-tab--active' : ''}`} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="bottom-chart">
        {tab === 'Altitude' && <AltitudeChart drones={drones} />}
        {tab === 'Battery' && <BatteryChart drones={drones} />}
        {tab === 'Events' && <EventTimeline />}
      </div>
    </div>
  );
}
