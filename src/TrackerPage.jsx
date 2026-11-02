import { useCallback, useEffect, useRef, useState } from "react";
import {
  MapPin,
  Navigation,
  RefreshCcw,
  ShieldAlert,
  ShieldCheck,
  Wifi,
  WifiOff,
} from "lucide-react";

import GeofenceMap from "./GeofenceMap.jsx";

const API = import.meta.env.VITE_API_URL || "";

// The phone sends a position at most this often. Anything faster drains the
// battery without telling the caregiver anything new.
const PING_INTERVAL_MS = 8000;

function formatClock(value) {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString();
}

// Browsers hand out GPS only on a secure origin. localhost is treated as one,
// a plain http:// LAN address is not: the permission prompt never appears and
// watchPosition stays silent, which looks exactly like a denied permission.
function secureOriginProblem() {
  if (window.isSecureContext) return null;
  const httpsUrl = new URL(window.location.href);
  httpsUrl.protocol = "https:";
  return httpsUrl.toString();
}

/**
 * The page the patient opens from the tracking link on their own phone.
 *
 * It never signs in. The token in the link identifies the patient, the browser
 * shares GPS, and every position goes to the backend, which mirrors it into
 * Firebase and Telegram and checks it against the caregiver's safe zone.
 */
function TrackerPage({ token }) {
  const [session, setSession] = useState(null);
  const [fetchError, setFetchError] = useState("");
  const [position, setPosition] = useState(null);
  const [fenceState, setFenceState] = useState(null);
  const [sharing, setSharing] = useState(false);
  const [statusMessage, setStatusMessage] = useState(() =>
    navigator.geolocation
      ? "Starting location sharing..."
      : "This browser cannot share location.",
  );
  const [sentAt, setSentAt] = useState("");
  const [panicSending, setPanicSending] = useState(false);

  const lastPingRef = useRef(0);
  const latestPositionRef = useRef(null);
  const wakeLockRef = useRef(null);
  const [httpsUrl] = useState(secureOriginProblem);

  useEffect(() => {
    if (!token) return;

    fetch(`${API}/api/track/session?token=${encodeURIComponent(token)}`)
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Tracking link failed.");
        return data;
      })
      .then(setSession)
      .catch((error) =>
        setFetchError(
          error instanceof TypeError
            ? "Cannot reach the CareBot server. Stay on the same Wi-Fi and try again."
            : error.message,
        ),
      );
  }, [token]);

  const loadError = token
    ? fetchError
    : "This link is missing its tracking code. Ask for a new link.";

  const sendPing = useCallback(
    async (coords, force = false) => {
      const now = Date.now();
      if (!force && now - lastPingRef.current < PING_INTERVAL_MS) return;
      lastPingRef.current = now;

      try {
        const response = await fetch(`${API}/api/track/ping`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token, source: "phone", location: coords }),
        });
        const data = await response.json();
        if (!response.ok) {
          setStatusMessage(data.error || "The server did not accept the location.");
          return;
        }
        setFenceState(data);
        setSentAt(new Date().toISOString());
        setStatusMessage(
          data.fence
            ? data.inside
              ? `Inside ${data.fence.label}`
              : `Outside ${data.fence.label} - your caregiver has been alerted`
            : "Location shared with your caregiver",
        );
      } catch {
        setStatusMessage("Location found, but the server could not be reached.");
      }
    },
    [token],
  );

  useEffect(() => {
    if (!session || !navigator.geolocation || httpsUrl) return undefined;

    const watchId = navigator.geolocation.watchPosition(
      (browserPosition) => {
        const coords = {
          lat: browserPosition.coords.latitude,
          lng: browserPosition.coords.longitude,
          accuracy: browserPosition.coords.accuracy,
        };
        latestPositionRef.current = coords;
        setPosition(coords);
        setSharing(true);
        sendPing(coords);
      },
      (error) => {
        setSharing(false);
        setStatusMessage(
          error.code === error.PERMISSION_DENIED
            ? "Allow location for this page so your family can find you."
            : "Waiting for a GPS signal. Step near a window or go outside.",
        );
      },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 5000 },
    );

    // watchPosition goes quiet when the patient stands still, so a timer keeps
    // the caregiver's map fresh with the last known fix.
    const heartbeat = setInterval(() => {
      if (latestPositionRef.current) sendPing(latestPositionRef.current);
    }, PING_INTERVAL_MS);

    return () => {
      navigator.geolocation.clearWatch(watchId);
      clearInterval(heartbeat);
    };
  }, [session, sendPing, httpsUrl]);

  useEffect(() => {
    // A locked screen suspends geolocation on most phones, so hold a wake lock
    // while the page is open and take it again after the phone is unlocked.
    let cancelled = false;

    const requestWakeLock = async () => {
      if (!("wakeLock" in navigator)) return;
      try {
        const lock = await navigator.wakeLock.request("screen");
        if (cancelled) {
          lock.release();
          return;
        }
        wakeLockRef.current = lock;
      } catch {
        // Denied wake locks only mean a dimmer screen, not a broken page.
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible") requestWakeLock();
    };

    requestWakeLock();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", handleVisibility);
      wakeLockRef.current?.release().catch(() => {});
      wakeLockRef.current = null;
    };
  }, []);

  const sendPanic = async () => {
    setPanicSending(true);
    try {
      const response = await fetch(`${API}/api/track/panic`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, location: latestPositionRef.current }),
      });
      const data = await response.json();
      setStatusMessage(
        response.ok
          ? "Help is on the way. Your caregiver has your location."
          : data.error || "Could not send the help alert.",
      );
    } catch {
      setStatusMessage("Could not reach the server to send help.");
    } finally {
      setPanicSending(false);
    }
  };

  if (loadError) {
    return (
      <div className="tracker-page">
        <div className="tracker-card tracker-error">
          <ShieldAlert size={34} />
          <h1>Tracking link problem</h1>
          <p>{loadError}</p>
        </div>
      </div>
    );
  }

  if (httpsUrl) {
    return (
      <div className="tracker-page">
        <div className="tracker-card">
          <header className="tracker-header">
            <div>
              <span className="tracker-eyebrow">CareBot live tracking</span>
              <h1>Open the secure link</h1>
            </div>
          </header>
          <div className="tracker-status danger">
            <ShieldAlert size={22} />
            <span>
              This phone will not share its location over a plain http address,
              so it never asks for permission.
            </span>
          </div>
          <p className="tracker-note">
            Tap the secure link below. The phone shows a certificate warning the
            first time because the certificate was made on your own computer:
            tap <b>Advanced</b>, then <b>Proceed</b>. After that the location
            prompt appears and tracking starts.
          </p>
          <a className="tracker-secure-link" href={httpsUrl}>
            {httpsUrl}
          </a>
          <a className="tracker-panic" href={httpsUrl}>
            <ShieldCheck size={22} />
            Open the secure page
          </a>
          <p className="tracker-note">
            If the secure link does not answer, the dev server is still on http.
            On the computer, run
            {" "}
            <code>powershell -ExecutionPolicy Bypass -File scripts\make-cert.ps1</code>
            {" "}
            and restart <code>npm run dev</code>.
          </p>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="tracker-page">
        <div className="tracker-card">
          <h1>Opening your tracking page...</h1>
        </div>
      </div>
    );
  }

  const fence = fenceState?.fence || session.fence;
  const outside = fenceState?.inside === false;
  const mapUrl = position
    ? `https://www.google.com/maps?q=${position.lat},${position.lng}`
    : "";

  return (
    <div className={`tracker-page ${outside ? "outside" : ""}`}>
      <div className="tracker-card">
        <header className="tracker-header">
          <div>
            <span className="tracker-eyebrow">CareBot live tracking</span>
            <h1>{session.patientName}</h1>
          </div>
          <span className={`tracker-pill ${sharing ? "on" : "off"}`}>
            {sharing ? <Wifi size={16} /> : <WifiOff size={16} />}
            {sharing ? "Sharing" : "Waiting"}
          </span>
        </header>

        <div className={`tracker-status ${outside ? "danger" : "safe"}`}>
          {outside ? <ShieldAlert size={22} /> : <ShieldCheck size={22} />}
          <span>{statusMessage}</span>
        </div>

        {position ? (
          <GeofenceMap
            centre={fence}
            radius={fence?.radius || 0}
            patient={position}
            height={240}
          />
        ) : (
          <div className="tracker-map placeholder">
            <MapPin size={26} />
            <span>Waiting for the first GPS fix...</span>
          </div>
        )}

        <dl className="tracker-facts">
          <div>
            <dt>Latitude</dt>
            <dd>{position ? position.lat.toFixed(6) : "--"}</dd>
          </div>
          <div>
            <dt>Longitude</dt>
            <dd>{position ? position.lng.toFixed(6) : "--"}</dd>
          </div>
          <div>
            <dt>Accuracy</dt>
            <dd>{position ? `${Math.round(position.accuracy)} m` : "--"}</dd>
          </div>
          <div>
            <dt>Safe zone</dt>
            <dd>
              {fence
                ? `${fence.label} · ${Math.round(fence.radius)} m`
                : "Not set by caregiver"}
            </dd>
          </div>
          <div>
            <dt>Distance from centre</dt>
            <dd>
              {fenceState?.distance != null
                ? `${Math.round(fenceState.distance)} m`
                : "--"}
            </dd>
          </div>
          <div>
            <dt>Last sent</dt>
            <dd>{formatClock(sentAt)}</dd>
          </div>
        </dl>

        <button className="tracker-panic" onClick={sendPanic} disabled={panicSending}>
          <ShieldAlert size={22} />
          {panicSending ? "Sending help alert..." : "I need help"}
        </button>

        <div className="tracker-actions">
          <button
            className="outline-btn"
            onClick={() =>
              latestPositionRef.current && sendPing(latestPositionRef.current, true)
            }
          >
            <RefreshCcw size={16} />
            Send location now
          </button>
          {mapUrl && (
            <a className="outline-btn" href={mapUrl} target="_blank" rel="noreferrer">
              <Navigation size={16} />
              Open in Maps
            </a>
          )}
        </div>

        {session.caregivers?.length > 0 && (
          <div className="tracker-caregivers">
            <h4>Your caregivers</h4>
            {session.caregivers.map((caregiver) => (
              <div key={caregiver.name}>
                <b>{caregiver.name}</b>
                {caregiver.phone && <a href={`tel:${caregiver.phone}`}>{caregiver.phone}</a>}
              </div>
            ))}
          </div>
        )}

        <p className="tracker-note">
          Keep this page open while you are out. It shares your location with your
          caregiver and raises an alert if you leave the safe zone.
        </p>
      </div>
    </div>
  );
}

export default TrackerPage;
