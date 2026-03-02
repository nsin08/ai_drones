/**
 * MissionBuilderMap — React-Leaflet map with click-to-add-waypoint (W15 G12).
 *
 * Props:
 *   waypoints    : [{id, lat, lng, alt_m}]
 *   onMapClick   : ({lat, lng, shiftKey}) => void
 *                  shiftKey=true → caller should treat as geofence point
 *   geofence     : [{lat, lng}]  — rendered as a polygon overlay
 *   mode         : 'waypoint' | 'geofence'  — visual cue for cursor style
 */

import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { MapContainer, Marker, Polygon, Popup, TileLayer, useMapEvents } from 'react-leaflet';

// Fix Leaflet's default icon path broken by Vite's asset hashing
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
  iconUrl:       new URL('leaflet/dist/images/marker-icon.png',   import.meta.url).href,
  shadowUrl:     new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href,
});

const GEOFENCE_STYLE = { color: '#f59e0b', fillColor: '#fef3c7', fillOpacity: 0.15, weight: 2 };

const GEOFENCE_ICON = L.divIcon({
  className: '',
  html: '<div style="width:10px;height:10px;border-radius:50%;background:#f59e0b;border:2px solid #b45309;"></div>',
  iconAnchor: [5, 5],
});

/** Hidden child component that captures map click events. */
function ClickCapture({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick({
        lat: e.latlng.lat,
        lng: e.latlng.lng,
        shiftKey: e.originalEvent.shiftKey,
      });
    },
  });
  return null;
}

export default function MissionBuilderMap({ waypoints = [], geofence = [], onMapClick, mode = 'waypoint' }) {
  const geofencePositions = geofence.map((p) => [p.lat, p.lng]);
  const cursor = mode === 'geofence' ? 'crosshair' : 'pointer';

  return (
    <div style={{ height: '420px', borderRadius: '8px', overflow: 'hidden', border: '1px solid #e5e7eb', cursor }}>
      <MapContainer
        center={[32.08, 34.78]}
        zoom={14}
        style={{ height: '100%', width: '100%', cursor }}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors'
        />

        <ClickCapture onMapClick={onMapClick} />

        {geofencePositions.length >= 3 && (
          <Polygon positions={geofencePositions} pathOptions={GEOFENCE_STYLE} />
        )}

        {geofence.map((pt, idx) => (
          <Marker key={`gf-${idx}`} position={[pt.lat, pt.lng]} icon={GEOFENCE_ICON}>
            <Popup><strong>Geofence G{idx + 1}</strong></Popup>
          </Marker>
        ))}

        {waypoints.map((wp, idx) => (
          <Marker key={wp.id} position={[wp.lat, wp.lng]}>
            <Popup>
              <strong>WP{idx + 1}</strong>
              <br />
              {wp.lat.toFixed(5)}, {wp.lng.toFixed(5)}
              <br />
              Alt: {wp.alt_m} m
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
