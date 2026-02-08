import { useMemo, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Polygon, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { useFleetStore } from '../stores/fleetStore';
import { useMissionStore } from '../stores/missionStore';
import { useSelectionStore } from '../stores/selectionStore';
import { TILE_URL, MAP_CENTER, MAP_ZOOM, ROLE_COLORS } from '../constants';

/* -- SVG marker icon factory -- */
function droneIcon(color = '#22d3ee', mode = 'AUTO') {
  const ring = ['HOLD', 'RTL', 'LAND'].includes(mode) ? '#fbbf24' : color;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">
    <circle cx="14" cy="14" r="12" fill="${color}33" stroke="${ring}" stroke-width="2"/>
    <circle cx="14" cy="14" r="4" fill="${color}"/>
  </svg>`;
  return L.divIcon({
    html: svg,
    className: '',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

/* -- Click-to-add handler for mission planning -- */
function MapClickHandler() {
  const { missionType, missionState } = useMissionStore();
  const addWp = useMissionStore((s) => s.addPlanWaypoint);
  const { planGeofence, setPlanGeofence, planAssetRoute, setPlanAssetRoute } = useMissionStore();

  useMapEvents({
    click(e) {
      if (missionState !== 'PLANNING') return;
      const { lat, lng: lon } = e.latlng;
      if (missionType === 'PATROL') {
        addWp({ lat: +lat.toFixed(6), lon: +lon.toFixed(6), alt_m: 50 });
      } else if (missionType === 'PERIMETER') {
        setPlanGeofence([...planGeofence, { lat: +lat.toFixed(6), lon: +lon.toFixed(6) }]);
      } else if (missionType === 'ESCORT') {
        setPlanAssetRoute([...planAssetRoute, { lat: +lat.toFixed(6), lon: +lon.toFixed(6) }]);
      }
    },
  });
  return null;
}

export default function CenterMap() {
  const drones = useFleetStore((s) => s.drones);
  const { missionType, planWaypoints, planGeofence, planAssetRoute } = useMissionStore();
  const toggle = useSelectionStore((s) => s.toggle);
  const tileSources = useMemo(() => ([
    TILE_URL,
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
  ]), []);
  const [tileIdx, setTileIdx] = useState(0);
  const [tileWarning, setTileWarning] = useState(false);
  const tileErrorsRef = useRef(0);
  const tileUrl = tileSources[tileIdx] || tileSources[0];

  return (
    <div className="center-map">
      <MapContainer center={MAP_CENTER} zoom={MAP_ZOOM} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          key={tileUrl}
          url={tileUrl}
          subdomains={['a', 'b', 'c']}
          eventHandlers={{
            tileerror: () => {
              tileErrorsRef.current += 1;
              if (tileErrorsRef.current >= 3 && tileIdx < tileSources.length - 1) {
                tileErrorsRef.current = 0;
                setTileIdx((idx) => Math.min(idx + 1, tileSources.length - 1));
                return;
              }
              if (tileIdx >= tileSources.length - 1 && tileErrorsRef.current > 10) {
                setTileWarning(true);
              }
            },
          }}
        />
        <MapClickHandler />

        {/* Drone markers */}
        {Object.values(drones).map((d) => {
          if (d.latitude == null || d.longitude == null) return null;
          const role = d.mission_role || d.current_role || 'UNKNOWN';
          const color = ROLE_COLORS[role] || ROLE_COLORS.UNKNOWN;
          return (
            <Marker
              key={d.drone_id}
              position={[d.latitude, d.longitude]}
              icon={droneIcon(color, d.mode)}
              eventHandlers={{ click: () => toggle(d.drone_id) }}
            >
              <Popup>
                <div style={{ fontSize: '0.75rem', color: '#333', lineHeight: 1.5 }}>
                  <b>{d.drone_id}</b> - {role}<br />
                  Battery: {(d.battery_pct ?? 0).toFixed(1)}%<br />
                  Mode: {d.mode || 'UNKNOWN'}<br />
                  Alt: {(d.altitude_m ?? 0).toFixed(1)}m
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Trails */}
        {Object.values(drones).map((d) => {
          if (!d.trail || d.trail.length < 2) return null;
          const role = d.mission_role || d.current_role || 'UNKNOWN';
          const color = ROLE_COLORS[role] || ROLE_COLORS.UNKNOWN;
          const isOOF = ['HOLD', 'RTL', 'LAND'].includes(d.mode);
          return (
            <Polyline
              key={`trail-${d.drone_id}`}
              positions={d.trail.map((p) => [p.lat, p.lon])}
              pathOptions={{ color, weight: isOOF ? 1 : 2, opacity: isOOF ? 0.3 : 0.6, dashArray: isOOF ? '4 4' : undefined }}
            />
          );
        })}

        {/* Planning overlays */}
        {missionType === 'PATROL' && planWaypoints.length > 0 && (
          <>
            <Polyline
              positions={planWaypoints.map((w) => [w.lat, w.lon])}
              pathOptions={{ color: '#60a5fa', weight: 2, dashArray: '6 4' }}
            />
            {planWaypoints.map((w, i) => (
              <Marker key={`wp-${i}`} position={[w.lat, w.lon]}
                icon={L.divIcon({
                  html: `<div style="background:#60a5fa;color:#000;width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700">${i + 1}</div>`,
                  className: '', iconSize: [20, 20], iconAnchor: [10, 10],
                })} />
            ))}
          </>
        )}

        {missionType === 'PERIMETER' && planGeofence.length > 1 && (
          <Polygon
            positions={planGeofence.map((p) => [p.lat, p.lon])}
            pathOptions={{ color: '#e879f9', weight: 2, fillOpacity: 0.08 }}
          />
        )}

        {missionType === 'ESCORT' && planAssetRoute.length > 1 && (
          <Polyline
            positions={planAssetRoute.map((p) => [p.lat, p.lon])}
            pathOptions={{ color: '#fbbf24', weight: 3, dashArray: '8 4' }}
          />
        )}
      </MapContainer>
      {tileWarning && tileIdx >= tileSources.length - 1 && (
        <div style={{
          position: 'absolute', right: 12, bottom: 12, zIndex: 999,
          background: 'rgba(15,23,42,0.8)', color: 'var(--text-primary)',
          padding: '6px 10px', borderRadius: 6, fontSize: '0.7rem',
          border: '1px solid var(--border)',
        }}>
          Map tiles unavailable. Check internet or set VITE_MAP_TILE_URL.
        </div>
      )}
    </div>
  );
}
