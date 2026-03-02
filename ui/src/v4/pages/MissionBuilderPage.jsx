/**
 * MissionBuilderPage — interactive PATROL mission builder (W15 G12).
 *
 * - Click map           → add waypoint
 * - Shift + click map   → add geofence vertex
 * - Toggle mode button  → switch click intent
 * - Submit              → validates geofence ⊇ waypoints → POST /api/missions
 */

import { useState } from 'react';
import axios from 'axios';
import PageSection from '../components/PageSection.jsx';
import MissionBuilderMap from '../components/MissionBuilderMap.jsx';
import WaypointList from '../components/WaypointList.jsx';
import GeofenceEditor from '../components/GeofenceEditor.jsx';
import FormationSelector from '../components/FormationSelector.jsx';

// ---------------------------------------------------------------------------
// Geometry helper: ray-cast point-in-polygon
// ---------------------------------------------------------------------------

function pointInPolygon(lat, lng, polygon) {
  if (polygon.length < 3) return true; // no geofence → do not block
  let inside = false;
  const n = polygon.length;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = polygon[i].lng, yi = polygon[i].lat;
    const xj = polygon[j].lng, yj = polygon[j].lat;
    const intersect =
      yi > lat !== yj > lat &&
      lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function waypointsOutsideGeofence(waypoints, geofence) {
  if (geofence.length < 3) return [];
  return waypoints.filter((wp) => !pointInPolygon(wp.lat, wp.lng, geofence));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const MISSION_TYPES = ['PATROL', 'ESCORT', 'SURVEY', 'DELIVERY'];

let _nextId = 1;
function newId() { return `wp-${_nextId++}`; }

export default function MissionBuilderPage() {
  const [missionType, setMissionType] = useState('PATROL');
  const [waypoints, setWaypoints] = useState([]);
  const [geofence, setGeofence] = useState([]);
  const [formation, setFormation] = useState({ shape: 'V', spacing_m: 5 });
  const [mode, setMode] = useState('waypoint'); // 'waypoint' | 'geofence'
  const [submitStatus, setSubmitStatus] = useState('idle'); // idle | loading | success | error
  const [submitMessage, setSubmitMessage] = useState('');

  // ------------------------------------------------------------------
  // Map click handler
  // ------------------------------------------------------------------

  function handleMapClick({ lat, lng, shiftKey }) {
    if (shiftKey || mode === 'geofence') {
      setGeofence((prev) => [...prev, { lat, lng }]);
    } else {
      setWaypoints((prev) => [...prev, { id: newId(), lat, lng, alt_m: 30 }]);
    }
  }

  // ------------------------------------------------------------------
  // Waypoint callbacks
  // ------------------------------------------------------------------

  function handleDeleteWaypoint(id) {
    setWaypoints((prev) => prev.filter((wp) => wp.id !== id));
  }

  function handleReorderWaypoint(fromIdx, toIdx) {
    setWaypoints((prev) => {
      const updated = [...prev];
      const [item] = updated.splice(fromIdx, 1);
      updated.splice(toIdx, 0, item);
      return updated;
    });
  }

  function handleAltChange(id, newAlt) {
    setWaypoints((prev) =>
      prev.map((wp) => (wp.id === id ? { ...wp, alt_m: newAlt } : wp))
    );
  }

  // ------------------------------------------------------------------
  // Geofence callbacks
  // ------------------------------------------------------------------

  function handleClearGeofence() { setGeofence([]); }

  function handleDeleteGeofencePoint(idx) {
    setGeofence((prev) => prev.filter((_, i) => i !== idx));
  }

  // ------------------------------------------------------------------
  // Validation
  // ------------------------------------------------------------------

  const outsideWaypoints = waypointsOutsideGeofence(waypoints, geofence);
  const geofenceValid = geofence.length === 0 || geofence.length >= 3;
  const canSubmit =
    missionType &&
    waypoints.length > 0 &&
    geofenceValid &&
    outsideWaypoints.length === 0 &&
    submitStatus !== 'loading';

  // ------------------------------------------------------------------
  // Submit
  // ------------------------------------------------------------------

  async function handleSubmit() {
    if (!canSubmit) return;
    setSubmitStatus('loading');
    setSubmitMessage('');

    const payload = {
      type: missionType,
      created_by: 'mission-builder-ui',
      config: {
        geofence,
        formation,
      },
      tasks: [
        {
          type: 'WAYPOINT_NAV',
          waypoints: waypoints.map(({ lat, lng, alt_m }) => ({ lat, lng, alt_m })),
          formation: formation.shape,
        },
      ],
    };

    try {
      const res = await axios.post('/api/missions', payload);
      setSubmitStatus('success');
      setSubmitMessage(`Mission created — ID: ${res.data.mission_id || res.data.id || 'OK'}`);
      // Reset builder
      setWaypoints([]);
      setGeofence([]);
      setFormation({ shape: 'V', spacing_m: 5 });
    } catch (err) {
      setSubmitStatus('error');
      setSubmitMessage(err?.response?.data?.detail || err.message || 'Submission failed');
    }
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <section className="v4-page">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Mission Builder</p>
          <h1 className="v4-page__title">Interactive Mission Planner</h1>
          <p className="v4-page__lede">
            Click the map to add waypoints. Shift+click (or switch mode) to draw the geofence boundary.
          </p>
        </div>
        {/* Mode toggle */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            onClick={() => setMode('waypoint')}
            style={{
              padding: '8px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '13px',
              background: mode === 'waypoint' ? '#3b82f6' : '#e5e7eb',
              color: mode === 'waypoint' ? '#fff' : '#374151',
            }}
          >
            ✈ Waypoints
          </button>
          <button
            onClick={() => setMode('geofence')}
            style={{
              padding: '8px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '13px',
              background: mode === 'geofence' ? '#f59e0b' : '#e5e7eb',
              color: mode === 'geofence' ? '#fff' : '#374151',
            }}
          >
            ⬡ Geofence
          </button>
        </div>
      </header>

      {/* Toast */}
      {submitStatus !== 'idle' && submitMessage && (
        <div style={{
          padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontWeight: 500,
          background: submitStatus === 'success' ? '#d1fae5' : '#fee2e2',
          color: submitStatus === 'success' ? '#065f46' : '#b91c1c',
          border: `1px solid ${submitStatus === 'success' ? '#6ee7b7' : '#fca5a5'}`,
        }}>
          {submitStatus === 'success' ? '✓ ' : '✕ '}{submitMessage}
        </div>
      )}

      {/* Map */}
      <PageSection title="Map" eyebrow={`Mode: ${mode === 'waypoint' ? 'Add Waypoints' : 'Draw Geofence'}`}>
        <MissionBuilderMap
          waypoints={waypoints}
          geofence={geofence}
          onMapClick={handleMapClick}
          mode={mode}
        />
      </PageSection>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        {/* Waypoints + Mission type */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <PageSection title="Mission Type" eyebrow="Configuration">
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {MISSION_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() => setMissionType(t)}
                  style={{
                    padding: '6px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
                    background: missionType === t ? '#1d4ed8' : '#e5e7eb',
                    color: missionType === t ? '#fff' : '#374151',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </PageSection>

          <PageSection title={`Waypoints (${waypoints.length})`} eyebrow="Route">
            {outsideWaypoints.length > 0 && (
              <p style={{ color: '#dc2626', fontSize: '12px', marginBottom: '8px', fontWeight: 600 }}>
                ⚠ {outsideWaypoints.length} waypoint(s) outside the geofence boundary.
              </p>
            )}
            <WaypointList
              waypoints={waypoints}
              onReorder={handleReorderWaypoint}
              onDelete={handleDeleteWaypoint}
              onAltChange={handleAltChange}
            />
          </PageSection>
        </div>

        {/* Geofence + Formation */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <PageSection title="Geofence" eyebrow="Boundary">
            <GeofenceEditor
              points={geofence}
              onClear={handleClearGeofence}
              onDelete={handleDeleteGeofencePoint}
            />
          </PageSection>

          <PageSection title="Formation" eyebrow="Drone Arrangement">
            <FormationSelector value={formation} onChange={setFormation} />
          </PageSection>
        </div>
      </div>

      {/* Submit bar */}
      <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '16px' }}>
        <span style={{ fontSize: '12px', color: '#9ca3af' }}>
          {waypoints.length} waypoint(s) · {geofence.length} geofence pts · {formation.shape} / {formation.spacing_m}m
        </span>
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          style={{
            padding: '10px 28px', borderRadius: '8px', border: 'none', cursor: canSubmit ? 'pointer' : 'not-allowed',
            fontWeight: 700, fontSize: '14px',
            background: canSubmit ? '#1d4ed8' : '#9ca3af',
            color: '#fff',
            opacity: canSubmit ? 1 : 0.7,
          }}
        >
          {submitStatus === 'loading' ? 'Submitting…' : '➤ Submit Mission'}
        </button>
      </div>
    </section>
  );
}
