import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Leaflet's default marker images are resolved relative to the CSS, which the
// bundler rewrites, so the pins would come out broken. These inline SVG pins
// avoid the whole problem and read better against the safe-zone circle.
function pin(color, ring) {
  return L.divIcon({
    className: "geofence-pin",
    html: `<span style="--pin:${color};--ring:${ring}"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

const PATIENT_PIN = pin("#dc2626", "rgba(220,38,38,0.25)");
const CENTRE_PIN = pin("#2563eb", "rgba(37,99,235,0.25)");
const CARETAKER_PIN = pin("#16a34a", "rgba(22,163,74,0.25)");

/**
 * A map that draws the safe zone as a real circle.
 *
 * The old Google embed could only drop a pin, so the boundary was invisible and
 * the radius was a number with nothing to compare it against. Here the circle
 * is on the map: drag the blue centre pin or click the map to move it, and the
 * circle grows and shrinks with the radius control as you slide it.
 */
function GeofenceMap({
  centre,
  radius,
  patient,
  caretaker,
  editable = false,
  onCentreChange,
  height = 260,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layersRef = useRef({});
  // Held in a ref so the Leaflet click and drag handlers, which are bound once,
  // always call the newest callback without being torn down and rebound.
  const centreChangeRef = useRef(onCentreChange);

  useEffect(() => {
    centreChangeRef.current = onCentreChange;
  }, [onCentreChange]);

  // Create the map once. Re-creating it on every render would reset the zoom
  // the moment a new position arrives from the poll.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;

    const map = L.map(containerRef.current, {
      zoomControl: true,
      attributionControl: true,
    }).setView([20.5937, 78.9629], 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layersRef.current = {};
    };
  }, []);

  // Clicking the map moves the centre, but only where that is allowed.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;

    const handleClick = (event) => {
      if (!editable) return;
      centreChangeRef.current?.({
        lat: event.latlng.lat,
        lng: event.latlng.lng,
      });
    };

    map.on("click", handleClick);
    return () => map.off("click", handleClick);
  }, [editable]);

  // Draw everything, then keep it in step with the props.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const layers = layersRef.current;

    // --- safe zone -------------------------------------------------------
    if (centre) {
      const position = [centre.lat, centre.lng];
      if (layers.circle) {
        layers.circle.setLatLng(position).setRadius(radius || 0);
      }
      else {
        layers.circle = L.circle(position, {
          radius: radius || 0,
          color: "#2563eb",
          weight: 2,
          fillColor: "#2563eb",
          fillOpacity: 0.12,
        }).addTo(map);
      }

      if (layers.centre) {
        layers.centre.setLatLng(position);
      }
      else {
        layers.centre = L.marker(position, {
          icon: CENTRE_PIN,
          draggable: editable,
          keyboard: false,
        }).addTo(map);
        layers.centre.on("dragend", (event) => {
          const { lat, lng } = event.target.getLatLng();
          centreChangeRef.current?.({ lat, lng });
        });
      }
      if (layers.centre.dragging) {
        if (editable) layers.centre.dragging.enable();
        else layers.centre.dragging.disable();
      }
    }
    else {
      if (layers.circle) {
        layers.circle.remove();
        layers.circle = null;
      }
      if (layers.centre) {
        layers.centre.remove();
        layers.centre = null;
      }
    }

    // --- the people ------------------------------------------------------
    const markers = [
      ["patient", patient, PATIENT_PIN],
      ["caretaker", caretaker, CARETAKER_PIN],
    ];
    for (const [key, point, icon] of markers) {
      if (point) {
        const position = [point.lat, point.lng];
        if (layers[key]) layers[key].setLatLng(position);
        else layers[key] = L.marker(position, { icon }).addTo(map);
      }
      else if (layers[key]) {
        layers[key].remove();
        layers[key] = null;
      }
    }
  }, [centre, radius, patient, caretaker, editable]);

  // Frame the circle and everyone on it, but only when the shape of the
  // picture changes. Refitting on every position update would fight the user
  // panning the map.
  const fitKey = [
    centre ? `${centre.lat.toFixed(4)},${centre.lng.toFixed(4)}` : "-",
    Math.round(radius || 0),
    patient ? `${patient.lat.toFixed(3)},${patient.lng.toFixed(3)}` : "-",
  ].join("|");

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const layers = layersRef.current;

    const bounds = L.latLngBounds([]);
    if (layers.circle) bounds.extend(layers.circle.getBounds());
    if (patient) bounds.extend([patient.lat, patient.lng]);
    if (caretaker) bounds.extend([caretaker.lat, caretaker.lng]);

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [28, 28], maxZoom: 17 });
    }
    // caretaker deliberately left out: it moves constantly while sharing, and
    // refitting on each of its updates would keep yanking the view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  // Leaflet measures the container when the map is created. Inside a panel
  // that is still laying out, that measurement is zero and the tiles come out
  // grey until something forces a resize.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    const timer = setTimeout(() => map.invalidateSize(), 120);
    return () => clearTimeout(timer);
  }, [height]);

  return (
    <div className="geofence-map" style={{ height }}>
      <div ref={containerRef} className="geofence-map-canvas" />
      <div className="geofence-map-legend">
        <span><i className="dot patient" /> Patient</span>
        {centre && <span><i className="dot centre" /> Safe zone centre</span>}
        {caretaker && <span><i className="dot caretaker" /> You</span>}
        {editable && <span className="hint">Click the map or drag the blue pin</span>}
      </div>
    </div>
  );
}

export default GeofenceMap;
