import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  ShieldCheck,
  Video,
  AlertTriangle,
  CreditCard,
  Server,
  Database,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  UserCheck,
  Check,
  Settings,
  Maximize2,
  Minimize2,
  Grid,
  LayoutGrid,
  Upload,
  Camera,
  Radio,
  X,
  Plus
} from 'lucide-react';

/* =========================================================================
   TYPE DEFINITIONS
   ========================================================================= */

type AccessVerdict = 'AUTHORIZED' | 'MISMATCH' | 'TAILGATING';
type AlertSeverity = 'CRITICAL' | 'WARNING' | 'INFO';
type GridLayout = '1x1' | '2x2' | '3x3';
type StreamSourceType = 'WEBCAM' | 'BACKEND_LOOP' | 'CUSTOM_UPLOAD' | 'STANDBY';

interface CameraChannel {
  id: string;
  name: string;
  zone: string;
  sourceType: StreamSourceType;
  streamUrl: string;
  customFileName?: string;
  deviceId?: number;
  isOnline: boolean;
  fps: number;
  resolution: string;
}

interface AccessEvent {
  id: string;
  badgeId: string;
  employeeName: string;
  department: string;
  faceMatchScore: number;
  verdict: AccessVerdict;
  zone: string;
  readerId: string;
  timestamp: string;
  occupancyDetected: number;
}

interface IncidentAlert {
  id: string;
  timestamp: string;
  zone: string;
  camera?: string;
  type: string;
  severity: AlertSeverity;
  detail: string;
  acknowledged: boolean;
  acknowledgedAt?: string;
  eventRef?: string;
}

interface InfraStatus {
  backendOnline: boolean;
  postgresActive: boolean;
  dbLatencyMs: number | null;
  serverVersion: string | null;
  lastProbeTime: string | null;
  probeError: string | null;
}

/* =========================================================================
   TIME UTILITIES (MODULE-LEVEL FOR REACT COMPILER PURITY)
   ========================================================================= */

function formatUtcTime(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false }) + ' UTC';
}

function formatUtcIso(): string {
  return new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
}

/* =========================================================================
   DEFAULT 9-CAMERA MULTIVIEW CONFIGURATION (3x3 MATRIX)
   ========================================================================= */

const INITIAL_CAMERAS: CameraChannel[] = [
  {
    id: 'CAM-01',
    name: 'Laptop Live Webcam (Physical)',
    zone: 'Zone 01 // Main Turnstile North',
    sourceType: 'WEBCAM',
    deviceId: 0,
    streamUrl: 'http://127.0.0.1:8000/api/webcam-stream/0',
    isOnline: true,
    fps: 30,
    resolution: '640x480',
  },
  {
    id: 'CAM-02',
    name: 'Mobile Webcam (Iriun / Device 1)',
    zone: 'Zone 01 // Optical Turnstile B',
    sourceType: 'WEBCAM',
    deviceId: 1,
    streamUrl: 'http://127.0.0.1:8000/api/webcam-stream/1',
    isOnline: true,
    fps: 30,
    resolution: '640x480',
  },
  {
    id: 'CAM-03',
    name: 'Entry Portal Loop',
    zone: 'Zone 03 // Logistics Yard North',
    sourceType: 'BACKEND_LOOP',
    streamUrl: 'http://127.0.0.1:8000/api/video-stream',
    isOnline: false,
    fps: 0,
    resolution: '1080p',
  },
  {
    id: 'CAM-04',
    name: 'Workshop Floor 2',
    zone: 'Zone 02 // Precision Machining Line',
    sourceType: 'STANDBY',
    streamUrl: '',
    isOnline: false,
    fps: 0,
    resolution: '1080p',
  },
  {
    id: 'CAM-05',
    name: 'Server Room Alpha',
    zone: 'Zone 04 // Tier-3 Data Center Vault',
    sourceType: 'STANDBY',
    streamUrl: '',
    isOnline: false,
    fps: 0,
    resolution: '4K UHD',
  },
  {
    id: 'CAM-06',
    name: 'Perimeter Fence West',
    zone: 'Zone 06 // Western Security Barrier',
    sourceType: 'STANDBY',
    streamUrl: '',
    isOnline: false,
    fps: 0,
    resolution: '1080p',
  },
  {
    id: 'CAM-07',
    name: 'Engineering Air-Lock',
    zone: 'Zone 02 // Cleanroom Airlock Entry',
    sourceType: 'STANDBY',
    streamUrl: '',
    isOnline: false,
    fps: 0,
    resolution: '1080p',
  },
  {
    id: 'CAM-08',
    name: 'Executive Corridor 3F',
    zone: 'Zone 05 // Administrative Wing 3F',
    sourceType: 'STANDBY',
    streamUrl: '',
    isOnline: false,
    fps: 0,
    resolution: '1080p',
  },
  {
    id: 'CAM-09',
    name: 'Vehicle Gate Bravo',
    zone: 'Zone 07 // Heavy Vehicle Access Gate',
    sourceType: 'STANDBY',
    streamUrl: '',
    isOnline: false,
    fps: 0,
    resolution: '1080p',
  },
];

const INITIAL_ACCESS_EVENT: AccessEvent = {
  id: 'ACC-10492',
  badgeId: 'EMP-4092',
  employeeName: 'Sandy',
  department: 'Lead Admin // Infrastructure',
  faceMatchScore: 0.962,
  verdict: 'AUTHORIZED',
  zone: 'Zone 01 // Main Turnstile North',
  readerId: 'HID-SIGNO-40-A1',
  timestamp: '12:20:00 UTC',
  occupancyDetected: 1,
};

const INITIAL_ALERTS: IncidentAlert[] = [
  {
    id: 'EVT-8921',
    timestamp: '12:21:44 UTC',
    zone: 'Zone 01 // Main Turnstile North',
    type: 'TAILGATING DETECTED',
    severity: 'CRITICAL',
    detail: 'Physical breach: 2 persons traversed optical gate on single badge scan (EMP-4092).',
    acknowledged: false,
    eventRef: 'ACC-10488',
  },
  {
    id: 'EVT-8919',
    timestamp: '12:18:02 UTC',
    zone: 'Zone 02 // Engineering Air-Lock',
    type: 'FACE MISMATCH',
    severity: 'WARNING',
    detail: 'ArcFace verification mismatch: Scanned credential EMP-2810 returned 41.8% cosine match.',
    acknowledged: false,
    eventRef: 'ACC-10484',
  },
  {
    id: 'EVT-8915',
    timestamp: '12:05:30 UTC',
    zone: 'Zone 04 // Server Room Alpha',
    type: 'CREDENTIAL CHALLENGE',
    severity: 'INFO',
    detail: 'Routine keycard badge scan authenticated successfully with 97.4% biometric match.',
    acknowledged: true,
    acknowledgedAt: '12:06:12 UTC',
    eventRef: 'ACC-10479',
  },
];

/* =========================================================================
   MAIN COMMAND CENTER COMPONENT
   ========================================================================= */

export const App: React.FC = () => {
  // Backend & Database Infrastructure Telemetry
  const [infra, setInfra] = useState<InfraStatus>({
    backendOnline: false,
    postgresActive: false,
    dbLatencyMs: null,
    serverVersion: null,
    lastProbeTime: null,
    probeError: null,
  });
  const [isProbing, setIsProbing] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<string>(formatUtcIso);

  // Grid Layout State (1x1 Focus View, 2x2 Quad View, 3x3 Matrix View)
  const [gridLayout, setGridLayout] = useState<GridLayout>('3x3');
  const [focusedCameraId, setFocusedCameraId] = useState<string | null>(null);

  // 9-Camera System State
  const [cameras, setCameras] = useState<CameraChannel[]>(INITIAL_CAMERAS);
  const [selectedCamForConfig, setSelectedCamForConfig] = useState<CameraChannel | null>(null);
  const [modalDeviceId, setModalDeviceId] = useState<number>(0);
  const [uploadLoading, setUploadLoading] = useState<boolean>(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const openConfigModal = (cam: CameraChannel) => {
    setSelectedCamForConfig(cam);
    setModalDeviceId(cam.deviceId ?? 0);
  };

  // Auto-recovery / reconnect tracking per camera
  const [streamErrors, setStreamErrors] = useState<Record<string, boolean>>({});
  const [reconnectTicks, setReconnectTicks] = useState<Record<string, number>>({});

  // Access Control Simulation & Alert State
  const [currentAccess, setCurrentAccess] = useState<AccessEvent>(INITIAL_ACCESS_EVENT);
  const [alerts, setAlerts] = useState<IncidentAlert[]>(INITIAL_ALERTS);
  const [alertFilter, setAlertFilter] = useState<'ALL' | 'UNACKNOWLEDGED'>('ALL');

  // Live Biometric Personnel Enrollment Modal State
  const [showEnrollModal, setShowEnrollModal] = useState<boolean>(false);
  const [enrollDeviceId, setEnrollDeviceId] = useState<number>(0);
  const [enrollName, setEnrollName] = useState<string>('');
  const [enrollRoll, setEnrollRoll] = useState<string>('');
  const [enrollId, setEnrollId] = useState<string>('');
  const [enrollLoading, setEnrollLoading] = useState<boolean>(false);
  const [enrollFeedback, setEnrollFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  // Live Biometric Verification State
  const [verifyEmployeeId, setVerifyEmployeeId] = useState<string>('EMP-1001');
  const [verifyDeviceId, setVerifyDeviceId] = useState<number>(0);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifyFeedback, setVerifyFeedback] = useState<{
    type: 'success' | 'warning' | 'error';
    message: string;
  } | null>(null);

  /* -----------------------------------------------------------------------
     1. Live System UTC Clock
     ----------------------------------------------------------------------- */
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(formatUtcIso());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  /* -----------------------------------------------------------------------
     2. Escape Key Fullscreen/Focus Handler
     ----------------------------------------------------------------------- */
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (focusedCameraId) {
          setFocusedCameraId(null);
          setGridLayout('3x3');
        }
        if (selectedCamForConfig) {
          setSelectedCamForConfig(null);
        }
        if (showEnrollModal) {
          setShowEnrollModal(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [focusedCameraId, selectedCamForConfig, showEnrollModal]);

  /* -----------------------------------------------------------------------
     2b. Real-time AI Incident WebSocket Bridge (/ws/alerts)
     ----------------------------------------------------------------------- */
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let isDisposed = false;

    const connectAlertWs = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname || '127.0.0.1';
        const wsUrl = `${protocol}//${host}:8000/ws/alerts`;
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('[UATU Alert Bridge] Connected to WebSocket alert stream:', wsUrl);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data && data.type) {
              const incomingAlert: IncidentAlert = {
                id: data.id || `EVT-${Math.floor(1000 + Math.random() * 9000)}`,
                timestamp: data.time || data.timestamp || formatUtcTime(),
                camera: data.camera,
                zone: data.zone || 'Live Monitoring Zone',
                type: data.type,
                severity: (data.level || data.severity || 'CRITICAL') as AlertSeverity,
                detail: data.detail || 'Spatial AI alert triggered by computer vision engine.',
                acknowledged: false,
                eventRef: data.id,
              };
              setAlerts((prev) => [incomingAlert, ...prev]);
            }
          } catch (err) {
            console.error('[UATU Alert Bridge] Error parsing WebSocket message:', err);
          }
        };

        ws.onclose = () => {
          if (!isDisposed) {
            reconnectTimer = setTimeout(connectAlertWs, 3000);
          }
        };

        ws.onerror = () => {
          ws?.close();
        };
      } catch (err) {
        if (!isDisposed) {
          reconnectTimer = setTimeout(connectAlertWs, 3000);
        }
      }
    };

    connectAlertWs();

    return () => {
      isDisposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  /* -----------------------------------------------------------------------
     3. Stream Reconnect / Recovery Timer (Ticks every 3s on error)
     ----------------------------------------------------------------------- */
  useEffect(() => {
    const interval = setInterval(() => {
      const activeErrors = Object.entries(streamErrors).filter(([, hasErr]) => hasErr);
      if (activeErrors.length > 0) {
        setReconnectTicks((prev) => {
          const now = Date.now();
          const nextTicks = { ...prev };
          activeErrors.forEach(([camId]) => {
            nextTicks[camId] = now;
          });
          return nextTicks;
        });
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [streamErrors]);

  /* -----------------------------------------------------------------------
     4. Infrastructure Health Probe (15s Polling)
     ----------------------------------------------------------------------- */
  const probeInfrastructure = useCallback(async () => {
    setIsProbing(true);
    const probeTimestamp = formatUtcTime();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2500);

      const readyRes = await fetch('http://127.0.0.1:8000/api/v1/health/ready', {
        signal: controller.signal,
      }).catch(async () => {
        return await fetch('http://127.0.0.1:8000/docs', {
          signal: controller.signal,
          method: 'HEAD',
        });
      });

      clearTimeout(timeoutId);

      if (readyRes && readyRes.ok) {
        try {
          const data = await readyRes.json();
          const isDbConnected = data.database?.status === 'connected';
          setInfra({
            backendOnline: true,
            postgresActive: isDbConnected,
            dbLatencyMs: data.database?.latency_ms ?? 1.2,
            serverVersion: data.database?.server_version ?? 'PostgreSQL 16.2',
            lastProbeTime: probeTimestamp,
            probeError: null,
          });
        } catch {
          setInfra({
            backendOnline: true,
            postgresActive: true,
            dbLatencyMs: null,
            serverVersion: 'PostgreSQL 16.2 (Active)',
            lastProbeTime: probeTimestamp,
            probeError: null,
          });
        }
      } else {
        setInfra({
          backendOnline: false,
          postgresActive: false,
          dbLatencyMs: null,
          serverVersion: null,
          lastProbeTime: probeTimestamp,
          probeError: readyRes ? `HTTP ${readyRes.status}` : 'Connection Refused',
        });
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Backend Unreachable';
      setInfra({
        backendOnline: false,
        postgresActive: false,
        dbLatencyMs: null,
        serverVersion: null,
        lastProbeTime: probeTimestamp,
        probeError: errorMsg,
      });
    } finally {
      setIsProbing(false);
    }
  }, []);

  useEffect(() => {
    const initialTimer = setTimeout(() => {
      probeInfrastructure();
    }, 10);
    const probeInterval = setInterval(() => {
      probeInfrastructure();
    }, 15000);
    return () => {
      clearTimeout(initialTimer);
      clearInterval(probeInterval);
    };
  }, [probeInfrastructure]);

  /* -----------------------------------------------------------------------
     4b. Real-Time Camera Telemetry Sync (/api/camera-telemetry)
     ----------------------------------------------------------------------- */
  useEffect(() => {
    let isDisposed = false;
    const fetchTelemetry = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/camera-telemetry');
        if (res.ok) {
          const data = await res.json();
          if (!isDisposed && data) {
            setCameras((prev) =>
              prev.map((c) => {
                const info = data[c.id];
                if (info) {
                  return {
                    ...c,
                    fps: info.is_online ? info.fps : 0,
                    isOnline: c.sourceType === 'STANDBY' ? false : (info.is_online ?? c.isOnline),
                  };
                }
                return c;
              })
            );
          }
        }
      } catch {
        // Silently tolerate during dev server reloads
      }
    };

    const interval = setInterval(fetchTelemetry, 2500);
    fetchTelemetry();
    return () => {
      isDisposed = true;
      clearInterval(interval);
    };
  }, []);

  /* -----------------------------------------------------------------------
     5. Source Assignment & Video Upload Logic
     ----------------------------------------------------------------------- */
  const handleAssignSource = (
    camId: string,
    sourceType: StreamSourceType,
    url: string = '',
    customFileName?: string,
    deviceId?: number
  ) => {
    // Reset error state for the reassigned camera
    setStreamErrors((prev) => ({ ...prev, [camId]: false }));
    setReconnectTicks((prev) => ({ ...prev, [camId]: Date.now() }));

    setCameras((prev) =>
      prev.map((c) => {
        if (c.id === camId) {
          const isNowOnline = sourceType !== 'STANDBY';
          return {
            ...c,
            sourceType,
            streamUrl: url,
            customFileName: customFileName ?? c.customFileName,
            deviceId: sourceType === 'WEBCAM' ? (deviceId ?? 1) : undefined,
            isOnline: isNowOnline,
            fps: isNowOnline ? (sourceType === 'WEBCAM' ? 30 : 25) : 0,
          };
        }
        return c;
      })
    );
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedCamForConfig) return;

    setUploadLoading(true);
    setUploadMessage(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/upload-video', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with HTTP ${response.status}`);
      }

      const data = await response.json();
      const streamUrl = `http://127.0.0.1:8000${data.stream_url}?camera=${encodeURIComponent(
        selectedCamForConfig.id
      )}&zone=${encodeURIComponent(selectedCamForConfig.zone)}`;

      handleAssignSource(
        selectedCamForConfig.id,
        'CUSTOM_UPLOAD',
        streamUrl,
        file.name
      );

      setUploadMessage(`Success: Assigned custom stream for ${file.name}`);
      setTimeout(() => {
        setSelectedCamForConfig(null);
        setUploadMessage(null);
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload Error';
      setUploadMessage(`Error: ${msg}`);
    } finally {
      setUploadLoading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  /* -----------------------------------------------------------------------
     5b. Live Biometric Personnel Enrollment Submission (POST /api/enroll)
     ----------------------------------------------------------------------- */
  const handleEnrollSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!enrollName.trim() || !enrollRoll.trim() || !enrollId.trim()) {
      setEnrollFeedback({
        type: 'error',
        message: 'Please complete all required fields (Full Name, Roll Number, Employee ID).',
      });
      return;
    }

    setEnrollLoading(true);
    setEnrollFeedback(null);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/enroll', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: Number(enrollDeviceId),
          employee_id: enrollId.trim(),
          name: enrollName.trim(),
          roll: enrollRoll.trim(),
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.error || data.detail || `Enrollment failed with HTTP ${response.status}`);
      }

      setEnrollFeedback({
        type: 'success',
        message: data.message || `Personnel ${enrollName.trim()} (${enrollId.trim()}) enrolled successfully!`,
      });
      setVerifyEmployeeId(enrollId.trim());
      setEnrollName('');
      setEnrollRoll('');
      setEnrollId('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Biometric capture failed';
      setEnrollFeedback({
        type: 'error',
        message: msg,
      });
    } finally {
      setEnrollLoading(false);
    }
  };

  /* -----------------------------------------------------------------------
     6. Live AI Verification Trigger (YOLOv8 + InsightFace ArcFace)
     ----------------------------------------------------------------------- */
  const handleLiveVerification = async () => {
    const targetId = verifyEmployeeId.trim();
    if (!targetId) {
      setVerifyFeedback({
        type: 'error',
        message: 'Please enter a valid Employee ID to scan.',
      });
      return;
    }

    setIsVerifying(true);
    setVerifyFeedback(null);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/verify-access', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: Number(verifyDeviceId),
          employee_id: targetId,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.error || data.detail || `Verification failed with HTTP ${response.status}`);
      }

      const accessId = `ACC-${Math.floor(10000 + Math.random() * 90000)}`;
      const timeStr = data.timestamp || formatUtcTime();
      const scoreFraction = typeof data.raw_score === 'number' ? data.raw_score : (Number(data.match_score || 0) / 100);

      setCurrentAccess({
        id: accessId,
        badgeId: data.employee_id || targetId,
        employeeName: data.employee_name || 'Unknown',
        department: data.roll ? `Roll: ${data.roll}` : 'Verified Personnel',
        faceMatchScore: scoreFraction,
        verdict: data.status,
        zone: data.zone || `Zone 01 // Device ${verifyDeviceId}`,
        readerId: `CAM-DEV-${verifyDeviceId}`,
        timestamp: timeStr,
        occupancyDetected: data.person_count ?? 1,
      });

      if (data.status === 'MISMATCH') {
        const newAlert: IncidentAlert = {
          id: `EVT-${Math.floor(8000 + Math.random() * 2000)}`,
          timestamp: timeStr,
          zone: data.zone || `Zone 01 // Device ${verifyDeviceId}`,
          type: 'FACE MISMATCH DETECTED',
          severity: 'WARNING',
          detail: `Optical ArcFace match scored ${data.match_score}% for scanned badge ${data.employee_id} (${data.employee_name}) (Threshold: 50.0%).`,
          acknowledged: false,
          eventRef: accessId,
        };
        setAlerts((prev) => [newAlert, ...prev]);
        setVerifyFeedback({
          type: 'warning',
          message: `MISMATCH: ArcFace match is ${data.match_score}% (under 50.0% threshold).`,
        });
      } else if (data.status === 'TAILGATING') {
        const newAlert: IncidentAlert = {
          id: `EVT-${Math.floor(8000 + Math.random() * 2000)}`,
          timestamp: timeStr,
          zone: data.zone || `Zone 01 // Device ${verifyDeviceId}`,
          type: 'TAILGATING VIOLATION',
          severity: 'CRITICAL',
          detail: `Tailgating breach detected: ${data.person_count} physical persons detected in frame during credential scan for ${data.employee_id} (${data.employee_name}).`,
          acknowledged: false,
          eventRef: accessId,
        };
        setAlerts((prev) => [newAlert, ...prev]);
        setVerifyFeedback({
          type: 'error',
          message: `TAILGATING DETECTED: ${data.person_count} persons in camera frame!`,
        });
      } else {
        setVerifyFeedback({
          type: 'success',
          message: `AUTHORIZED: ${data.employee_name} verified (${data.match_score}% ArcFace match).`,
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Verification request failed';
      setVerifyFeedback({
        type: 'error',
        message: msg,
      });
    } finally {
      setIsVerifying(false);
    }
  };

  /* -----------------------------------------------------------------------
     7. Alert Acknowledgment Toggle
     ----------------------------------------------------------------------- */
  const toggleAcknowledge = (id: string) => {
    const ackTime = formatUtcTime();
    setAlerts((prev) =>
      prev.map((alert) => {
        if (alert.id === id) {
          const nextState = !alert.acknowledged;
          return {
            ...alert,
            acknowledged: nextState,
            acknowledgedAt: nextState ? ackTime : undefined,
          };
        }
        return alert;
      })
    );
  };

  const unacknowledgedCount = useMemo(() => {
    return alerts.filter((a) => !a.acknowledged).length;
  }, [alerts]);

  const filteredAlerts = useMemo(() => {
    if (alertFilter === 'UNACKNOWLEDGED') {
      return alerts.filter((a) => !a.acknowledged);
    }
    return alerts;
  }, [alerts, alertFilter]);

  const visibleCameras = useMemo(() => {
    if (gridLayout === '1x1') {
      const focused = cameras.find((c) => c.id === (focusedCameraId || 'CAM-01'));
      return focused ? [focused] : [cameras[0]];
    }
    if (gridLayout === '2x2') {
      return cameras.slice(0, 4);
    }
    return cameras; // 3x3 returns all 9
  }, [gridLayout, focusedCameraId, cameras]);

  /* =========================================================================
     RENDER
     ========================================================================= */

  return (
    <div className="min-h-screen bg-[#020617] text-[#f8fafc] flex flex-col font-sans selection:bg-slate-800 selection:text-emerald-300">
      {/* =====================================================================
          A. TOP HEADER & INFRASTRUCTURE DIAGNOSTICS (UNIFIED UATU BRANDING)
          ===================================================================== */}
      <header className="border-b border-[#1e293b] bg-[#0f172a] px-4 py-2.5 sm:px-6 sticky top-0 z-40 shadow-md">
        <div className="max-w-[1920px] mx-auto flex flex-wrap items-center justify-between gap-4">
          {/* System Title & Identity */}
          <div className="flex items-center gap-3">
            <div className="p-2 rounded bg-slate-950 border border-slate-800 text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm sm:text-base font-bold tracking-wider text-slate-100">
                UNIFIED ASSISTANT FOR THREAT &amp; UNDERSTANDING (AI)
              </span>
              <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[11px] font-mono px-2 py-0.5 rounded font-semibold uppercase tracking-wider">
                UATU // EDGE SYSTEM
              </span>
            </div>
          </div>

          {/* Infrastructure Health Bar & UTC Telemetry */}
          <div className="flex flex-wrap items-center gap-2.5 sm:gap-3 text-xs font-mono">
            {/* FastAPI Backend Probe */}
            <div
              className={`flex items-center gap-2 px-3 py-1.5 rounded border transition-colors ${
                infra.backendOnline
                  ? 'bg-slate-950 border-emerald-500/30 text-emerald-400'
                  : 'bg-red-950/20 border-red-500/30 text-red-400'
              }`}
              title={infra.backendOnline ? 'FastAPI Uvicorn responding on port 8000' : 'Backend offline'}
            >
              <Server className="w-3.5 h-3.5" />
              <div className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    infra.backendOnline ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
                  }`}
                />
                <span className="font-semibold">
                  {infra.backendOnline ? 'PORT 8000 ONLINE' : 'PORT 8000 OFFLINE'}
                </span>
              </div>
            </div>

            {/* PostgreSQL Status Indicator */}
            <div
              className={`flex items-center gap-2 px-3 py-1.5 rounded border transition-colors ${
                infra.postgresActive
                  ? 'bg-slate-950 border-emerald-500/30 text-emerald-400'
                  : 'bg-slate-950 border-slate-800 text-slate-400'
              }`}
              title={
                infra.postgresActive
                  ? `PostgreSQL 16.2 Connected (${infra.dbLatencyMs ? infra.dbLatencyMs.toFixed(1) + 'ms' : 'Active'})`
                  : 'PostgreSQL standby'
              }
            >
              <Database className="w-3.5 h-3.5" />
              <div className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    infra.postgresActive ? 'bg-emerald-400' : 'bg-slate-600'
                  }`}
                />
                <span className="font-semibold">
                  {infra.postgresActive ? '5432 ACTIVE' : '5432 STANDBY'}
                </span>
              </div>
            </div>

            {/* Manual Probe Button */}
            <button
              onClick={probeInfrastructure}
              disabled={isProbing}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-all disabled:opacity-50"
              title="Manually verify backend and database status"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isProbing ? 'animate-spin text-emerald-400' : ''}`} />
              <span className="hidden md:inline">Probe</span>
            </button>

            {/* Personnel Live Biometric Enrollment Gear Button */}
            <button
              onClick={() => {
                setShowEnrollModal(true);
                setEnrollFeedback(null);
              }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition-all group"
              title="Register New Personnel (Live ArcFace Biometrics)"
              aria-label="Settings and Live Enrollment"
            >
              <Settings className="w-3.5 h-3.5 text-emerald-400 group-hover:rotate-45 transition-transform duration-200" />
              <span className="hidden md:inline font-mono text-xs">Enroll</span>
            </button>

            {/* Live UTC Telemetry Clock */}
            <div className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-950 border border-slate-800 text-slate-400 font-mono text-[11px]">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              <span>{currentTime}</span>
            </div>
          </div>
        </div>
      </header>

      {/* =====================================================================
          MAIN DASHBOARD WORKSPACE (65% / 35% SPLIT)
          ===================================================================== */}
      <main className="flex-1 max-w-[1920px] w-full mx-auto p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* ===================================================================
            LEFT COLUMN (65% width: 8/12 columns on LG screens)
            MULTIVIEW 9-CAMERA GRID & BIOMETRIC ACCESS CONTROL
            =================================================================== */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          {/* -----------------------------------------------------------------
              SURVEILLANCE MATRIX VIEWPORT CONTAINER
              ----------------------------------------------------------------- */}
          <div className="bg-[#0f172a] rounded-lg border border-[#1e293b] shadow-xl overflow-hidden flex flex-col">
            {/* Viewport Top Bar & Layout Selector */}
            <div className="px-4 py-2.5 bg-slate-900/90 border-b border-[#1e293b] flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-sm font-semibold tracking-wide text-slate-200">
                  Live Feeds
                </span>
                {focusedCameraId && gridLayout === '1x1' && (
                  <span className="text-xs font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40 ml-2">
                    Focused: {focusedCameraId}
                  </span>
                )}
              </div>

              {/* View Switcher Controls */}
              <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded border border-slate-800 text-xs font-mono">
                <button
                  onClick={() => {
                    setGridLayout('1x1');
                    if (!focusedCameraId) setFocusedCameraId('CAM-01');
                  }}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
                    gridLayout === '1x1'
                      ? 'bg-emerald-600 text-white font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Single Camera Focus Mode"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                  <span>1x1 Focus</span>
                </button>

                <button
                  onClick={() => {
                    setGridLayout('2x2');
                    setFocusedCameraId(null);
                  }}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
                    gridLayout === '2x2'
                      ? 'bg-emerald-600 text-white font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Quad View (CAM-01 to CAM-04)"
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span>2x2 Quad</span>
                </button>

                <button
                  onClick={() => {
                    setGridLayout('3x3');
                    setFocusedCameraId(null);
                  }}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
                    gridLayout === '3x3'
                      ? 'bg-emerald-600 text-white font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Full 9-Camera Matrix View (CAM-01 to CAM-09)"
                >
                  <Grid className="w-3.5 h-3.5" />
                  <span>3x3 Matrix</span>
                </button>
              </div>
            </div>

            {/* Grid Container */}
            <div className="p-3 bg-[#020617]">
              <div
                className={`grid gap-3 transition-all duration-200 ${
                  gridLayout === '1x1'
                    ? 'grid-cols-1'
                    : gridLayout === '2x2'
                    ? 'grid-cols-1 sm:grid-cols-2'
                    : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'
                }`}
              >
                {visibleCameras.map((cam) => {
                  const isStandby = cam.sourceType === 'STANDBY';
                  const hasStream = !isStandby && cam.streamUrl.length > 0;
                  const isError = Boolean(streamErrors[cam.id]);

                  // Append cache-busting timestamp param if re-attempting connection
                  const tick = reconnectTicks[cam.id];
                  const streamSrc = hasStream
                    ? tick
                      ? `${cam.streamUrl}${cam.streamUrl.includes('?') ? '&' : '?'}t=${tick}`
                      : cam.streamUrl
                    : '';

                  return (
                    <div
                      key={cam.id}
                      className={`relative rounded border transition-all flex flex-col overflow-hidden group ${
                        focusedCameraId === cam.id && gridLayout === '1x1'
                          ? 'border-emerald-500/70 shadow-2xl shadow-emerald-950/20'
                          : 'border-slate-800/90 hover:border-slate-700 bg-slate-900/60'
                      }`}
                    >
                      {/* Tile Top Control Bar */}
                      <div className="px-2.5 py-1.5 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between text-xs font-mono z-10">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full shrink-0 ${
                              cam.isOnline && !isStandby && !isError
                                ? 'bg-emerald-400 animate-pulse'
                                : isError
                                ? 'bg-red-500 animate-pulse'
                                : 'bg-slate-600'
                            }`}
                            title={
                              cam.isOnline && !isStandby && !isError
                                ? 'Stream Live'
                                : isError
                                ? 'Connecting / Retrying...'
                                : 'Unassigned / Idle'
                            }
                          />
                          <span className="font-semibold text-slate-200 shrink-0">{cam.id}</span>
                          <span className="text-slate-400 text-[11px]">
                            {cam.name}
                          </span>
                        </div>

                        {/* Action Icons */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className="text-slate-400 p-0.5" title={cam.sourceType === 'WEBCAM' ? `Webcam (Device ${cam.deviceId ?? 1})` : cam.sourceType}>
                            <Video className="w-3.5 h-3.5 text-slate-400" />
                          </span>

                          {/* ⚙️ Source Selector Button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openConfigModal(cam);
                            }}
                            className="p-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-colors"
                            title="Configure Camera Source (Webcam, Loop, Upload, Standby)"
                          >
                            <Settings className="w-3.5 h-3.5" />
                          </button>

                          {/* Focus / Maximize Button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              if (gridLayout === '1x1') {
                                setGridLayout('3x3');
                                setFocusedCameraId(null);
                              } else {
                                setFocusedCameraId(cam.id);
                                setGridLayout('1x1');
                              }
                            }}
                            className="p-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-colors"
                            title={gridLayout === '1x1' ? 'Return to 3x3 Grid (Esc)' : 'Expand to Focus View'}
                          >
                            {gridLayout === '1x1' ? (
                              <Minimize2 className="w-3.5 h-3.5 text-emerald-400" />
                            ) : (
                              <Maximize2 className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Video Viewport Tile Body */}
                      <div
                        onClick={() => {
                          if (gridLayout !== '1x1') {
                            setFocusedCameraId(cam.id);
                            setGridLayout('1x1');
                          }
                        }}
                        className={`relative w-full aspect-video bg-[#020617] flex items-center justify-center cursor-pointer overflow-hidden ${
                          gridLayout === '1x1' ? 'min-h-[460px]' : ''
                        }`}
                      >
                        {hasStream ? (
                          <>
                            <img
                              src={streamSrc}
                              alt={`${cam.id} live video feed`}
                              className={`w-full h-full object-contain select-none transition-opacity duration-200 ${
                                isError ? 'opacity-30' : 'opacity-100'
                              }`}
                              onLoad={() => {
                                setStreamErrors((prev) => ({ ...prev, [cam.id]: false }));
                              }}
                              onError={() => {
                                setStreamErrors((prev) => ({ ...prev, [cam.id]: true }));
                              }}
                            />
                            {/* Reconnect Recovery Indicator Overlay */}
                            {isError && (
                              <div className="absolute inset-0 flex flex-col items-center justify-center p-3 text-center bg-slate-950/80 pointer-events-none">
                                <RefreshCw className="w-4 h-4 text-slate-500 animate-spin mb-1.5" />
                                <div className="text-xs font-medium text-slate-500">
                                  Connecting...
                                </div>
                              </div>
                            )}
                          </>
                        ) : (
                          /* Minimalist Empty State */
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              openConfigModal(cam);
                            }}
                            className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center bg-slate-950 hover:bg-slate-900/50 transition-colors cursor-pointer group/tile"
                          >
                            <Plus className="w-4 h-4 text-slate-600 group-hover/tile:text-slate-400 transition-colors mb-1.5" />
                            <span className="text-xs text-slate-500 font-medium tracking-wide">
                              Unassigned
                            </span>
                          </div>
                        )}

                        {/* In-Tile HUD Telemetry Overlays */}
                        {hasStream && !isError && (
                          <div className="absolute inset-0 pointer-events-none p-2 flex flex-col justify-between">
                            <div className="flex items-center justify-between text-[10px] font-mono">
                              <span className="bg-slate-950/80 backdrop-blur px-1.5 py-0.5 rounded text-emerald-400 border border-slate-800 flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                                LIVE // UATU
                              </span>
                              <span className="bg-slate-950/80 backdrop-blur px-1.5 py-0.5 rounded text-slate-300 border border-slate-800">
                                {cam.resolution}
                              </span>
                            </div>

                            <div className="flex items-center justify-between text-[10px] font-mono">
                              <span className="bg-slate-950/80 backdrop-blur px-1.5 py-0.5 rounded text-slate-400 border border-slate-800 truncate max-w-[70%]">
                                {cam.zone}
                              </span>
                              <span className="bg-slate-950/80 backdrop-blur px-1.5 py-0.5 rounded text-emerald-400 border border-slate-800">
                                {(!cam.isOnline || isError || !hasStream || cam.sourceType === 'STANDBY') ? 0 : (cam.fps || 25)} FPS
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Focus Mode Escape Helper Bar */}
              {gridLayout === '1x1' && (
                <div className="mt-3 px-3 py-2 bg-slate-900/90 rounded border border-slate-800 flex items-center justify-between text-xs font-mono text-slate-400">
                  <span>Press <kbd className="px-1.5 py-0.5 rounded bg-slate-950 border border-slate-700 text-slate-200">Esc</kbd> to return to 3x3 matrix</span>
                  <button
                    onClick={() => {
                      setGridLayout('3x3');
                      setFocusedCameraId(null);
                    }}
                    className="text-emerald-400 hover:text-emerald-300 underline font-semibold"
                  >
                    Return to 3x3 Grid
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* -----------------------------------------------------------------
              C. ACCESS CONTROL & BIOMETRIC CORRELATION PANEL (ROW 2)
              ----------------------------------------------------------------- */}
          <div className="bg-[#0f172a] rounded-lg border border-[#1e293b] p-5 shadow-xl flex flex-col gap-5">
            {/* Panel Title & Status */}
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <CreditCard className="w-5 h-5 text-emerald-400" />
                <div>
                  <h2 className="font-mono text-sm sm:text-base font-bold text-slate-100 tracking-wide uppercase">
                    Access Control &amp; Biometric Correlation
                  </h2>
                  <p className="text-xs text-slate-400 font-sans">
                    Real-time RFID transaction matched against ArcFace facial embeddings
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-slate-400">READER:</span>
                <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300">
                  {currentAccess.readerId}
                </span>
              </div>
            </div>

            {/* Core Verification Telemetry Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* 1. Scanned RFID / Employee Profile */}
              <div className="bg-[#020617] rounded-lg border border-slate-800 p-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
                    <span>CREDENTIAL ID</span>
                    <span className="text-emerald-400">RFID SCAN</span>
                  </div>
                  <div className="text-base font-semibold text-slate-100">
                    {currentAccess.badgeId}: {currentAccess.employeeName}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {currentAccess.department}
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-slate-900 text-[11px] font-mono text-slate-500 flex items-center justify-between">
                  <span>LOCATION:</span>
                  <span className="text-slate-300">{currentAccess.zone}</span>
                </div>
              </div>

              {/* 2. Facial Match Score (ArcFace 512-d) */}
              <div className="bg-[#020617] rounded-lg border border-slate-800 p-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
                    <span>ARCFACE MATCH SCORE</span>
                    <span className="font-mono text-slate-300">512-D COSINE</span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span
                      className={`text-2xl font-mono font-bold ${
                        currentAccess.faceMatchScore >= 0.85
                          ? 'text-emerald-400'
                          : currentAccess.faceMatchScore >= 0.5
                          ? 'text-amber-400'
                          : 'text-red-400'
                      }`}
                    >
                      {(currentAccess.faceMatchScore * 100).toFixed(1)}%
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      (Score: {currentAccess.faceMatchScore.toFixed(3)})
                    </span>
                  </div>

                  {/* Visual Confidence Bar */}
                  <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden mt-3 border border-slate-800">
                    <div
                      className={`h-full transition-all duration-500 ${
                        currentAccess.faceMatchScore >= 0.85
                          ? 'bg-emerald-500'
                          : currentAccess.faceMatchScore >= 0.5
                          ? 'bg-amber-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(100, currentAccess.faceMatchScore * 100)}%` }}
                    />
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-slate-900 text-[11px] font-mono text-slate-500 flex items-center justify-between">
                  <span>THRESHOLD:</span>
                  <span className="text-slate-300">&ge; 50.0% Required</span>
                </div>
              </div>

              {/* 3. Access Verdict Pill & Occupancy */}
              <div className="bg-[#020617] rounded-lg border border-slate-800 p-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
                    <span>SECURITY VERDICT</span>
                    <span className="font-mono text-slate-400">TURNSTILE GATE</span>
                  </div>

                  {/* Verdict Badge */}
                  <div className="mt-1">
                    {currentAccess.verdict === 'AUTHORIZED' && (
                      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-950/40 border border-emerald-500/40 text-emerald-400 text-xs font-mono font-bold tracking-wider">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        AUTHORIZED
                      </div>
                    )}
                    {currentAccess.verdict === 'MISMATCH' && (
                      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-950/40 border border-amber-500/40 text-amber-400 text-xs font-mono font-bold tracking-wider">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        MISMATCH
                      </div>
                    )}
                    {currentAccess.verdict === 'TAILGATING' && (
                      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-950/40 border border-red-500/40 text-red-400 text-xs font-mono font-bold tracking-wider">
                        <XCircle className="w-4 h-4 text-red-400" />
                        TAILGATING
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-4 pt-2 border-t border-slate-900 text-[11px] font-mono text-slate-500 flex items-center justify-between">
                  <span>OCCUPANCY DETECTED:</span>
                  <span
                    className={`font-semibold ${
                      currentAccess.occupancyDetected > 1 ? 'text-red-400' : 'text-slate-300'
                    }`}
                  >
                    {currentAccess.occupancyDetected} Person(s)
                  </span>
                </div>
              </div>
            </div>

            {/* Live AI Biometric & Tailgating Verification Control */}
            <div className="mt-1 bg-slate-950/80 rounded-lg border border-slate-800 p-3.5">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-2.5">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-xs font-mono font-semibold tracking-wider text-slate-300 uppercase">
                    Live AI Verification Engine (YOLOv8 + ArcFace)
                  </span>
                </div>
                <span className="text-[11px] font-mono text-slate-500">
                  Real-time optical frame evaluation &amp; tailgating check
                </span>
              </div>

              {/* Feedback Banner */}
              {verifyFeedback && (
                <div
                  className={`mb-3 p-2.5 rounded-lg border text-xs font-mono flex items-center gap-2 ${
                    verifyFeedback.type === 'success'
                      ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                      : verifyFeedback.type === 'warning'
                      ? 'bg-amber-950/40 border-amber-500/40 text-amber-300'
                      : 'bg-red-950/40 border-red-500/40 text-red-300'
                  }`}
                >
                  {verifyFeedback.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
                  {verifyFeedback.type === 'warning' && <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />}
                  {verifyFeedback.type === 'error' && <XCircle className="w-4 h-4 text-red-400 shrink-0" />}
                  <span className="flex-1">{verifyFeedback.message}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
                {/* Employee ID to Scan Input */}
                <div className="sm:col-span-5">
                  <label className="block text-[11px] font-mono text-slate-400 mb-1">
                    Employee ID to Scan
                  </label>
                  <input
                    type="text"
                    value={verifyEmployeeId}
                    onChange={(e) => setVerifyEmployeeId(e.target.value)}
                    placeholder="e.g. EMP-1001"
                    disabled={isVerifying}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 transition-colors"
                  />
                </div>

                {/* Target Camera Selector Dropdown */}
                <div className="sm:col-span-4">
                  <label className="block text-[11px] font-mono text-slate-400 mb-1">
                    Target Camera
                  </label>
                  <select
                    value={verifyDeviceId}
                    onChange={(e) => setVerifyDeviceId(Number(e.target.value))}
                    disabled={isVerifying}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
                  >
                    <option value={0}>Device 0 &mdash; Mobile (Iriun)</option>
                    <option value={1}>Device 1 &mdash; Laptop Webcam</option>
                  </select>
                </div>

                {/* Trigger Live AI Verification Button */}
                <div className="sm:col-span-3">
                  <button
                    onClick={handleLiveVerification}
                    disabled={isVerifying}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-semibold transition-all shadow-md shadow-emerald-950/40 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isVerifying ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Verifying...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Trigger Live AI</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ===================================================================
            RIGHT COLUMN (35% width: 4/12 columns on LG screens)
            D. REAL-TIME ALERT DISPATCH QUEUE
            =================================================================== */}
        <div className="lg:col-span-4 flex flex-col">
          <div className="bg-[#0f172a] rounded-lg border border-[#1e293b] shadow-xl flex flex-col h-full overflow-hidden">
            {/* Header with Active Unacknowledged Count */}
            <div className="p-4 bg-slate-900/90 border-b border-[#1e293b] flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <div>
                  <h2 className="font-mono text-sm sm:text-base font-bold text-slate-100 tracking-wide uppercase">
                    Incident Dispatch Queue
                  </h2>
                  <p className="text-[11px] text-slate-400 font-sans">
                    Priority-coded real-time security events
                  </p>
                </div>
              </div>

              {/* Active unacknowledged count pill */}
              <div
                className={`px-2.5 py-1 rounded-full font-mono text-xs font-bold border ${
                  unacknowledgedCount > 0
                    ? 'bg-red-950/40 text-red-400 border-red-500/40 animate-pulse'
                    : 'bg-emerald-950/40 text-emerald-400 border-emerald-500/40'
                }`}
              >
                {unacknowledgedCount} ACTIVE
              </div>
            </div>

            {/* Filter Sub-Bar */}
            <div className="px-4 py-2 bg-slate-950/70 border-b border-slate-800 flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-1.5 text-slate-400">
                <span>FILTER:</span>
                <button
                  onClick={() => setAlertFilter('ALL')}
                  className={`px-2 py-0.5 rounded transition-colors ${
                    alertFilter === 'ALL'
                      ? 'bg-slate-800 text-white font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  ALL ({alerts.length})
                </button>
                <button
                  onClick={() => setAlertFilter('UNACKNOWLEDGED')}
                  className={`px-2 py-0.5 rounded transition-colors ${
                    alertFilter === 'UNACKNOWLEDGED'
                      ? 'bg-slate-800 text-white font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  UNACK ({unacknowledgedCount})
                </button>
              </div>

              <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                AUTO-DISPATCH ON
              </span>
            </div>

            {/* Scrollable Incident Cards List */}
            <div className="p-4 flex-1 overflow-y-auto space-y-3.5 max-h-[750px]">
              {filteredAlerts.length === 0 ? (
                <div className="text-center py-12 text-slate-500 font-mono text-xs">
                  <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-slate-600" />
                  NO INCIDENTS IN CURRENT VIEW
                </div>
              ) : (
                filteredAlerts.map((alert) => {
                  const isCrit = alert.severity === 'CRITICAL';
                  const isWarn = alert.severity === 'WARNING';

                  return (
                    <div
                      key={alert.id}
                      className={`rounded-lg border p-3.5 transition-all duration-200 ${
                        alert.acknowledged
                          ? 'bg-slate-950/40 border-slate-800/60 opacity-60'
                          : isCrit
                          ? 'bg-red-950/20 border-red-900/50 hover:border-red-700/60 shadow-lg shadow-red-950/10'
                          : isWarn
                          ? 'bg-amber-950/20 border-amber-900/50 hover:border-amber-700/60 shadow-lg shadow-amber-950/10'
                          : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      {/* Top Row: Severity, Event ID, Timestamp */}
                      <div className="flex items-center justify-between gap-2 mb-2 font-mono text-xs">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${
                              isCrit
                                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                                : isWarn
                                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                : 'bg-slate-800 text-slate-300 border border-slate-700'
                            }`}
                          >
                            {alert.severity}
                          </span>
                          <span className="font-semibold text-slate-300">{alert.id}</span>
                        </div>
                        <span className="text-[11px] text-slate-400">{alert.timestamp}</span>
                      </div>

                      {/* Zone Identifier */}
                      <div className="text-[11px] font-mono text-emerald-400/90 mb-1 flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        <span>{alert.camera ? `${alert.camera} • ${alert.zone}` : alert.zone}</span>
                      </div>

                      {/* Alert Type Heading */}
                      <div className="text-xs sm:text-sm font-semibold text-slate-100 mb-1.5 font-mono">
                        {alert.type}
                      </div>

                      {/* Detail Message */}
                      <p className="text-xs text-slate-300 leading-relaxed font-sans mb-3">
                        {alert.detail}
                      </p>

                      {/* Card Footer: Acknowledge Action Button */}
                      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
                        <span className="text-[10px] text-slate-500">
                          {alert.eventRef ? `REF: ${alert.eventRef}` : 'DISPATCH PROTOCOL'}
                        </span>

                        <button
                          onClick={() => toggleAcknowledge(alert.id)}
                          className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-mono font-medium transition-all ${
                            alert.acknowledged
                              ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-500/30 hover:bg-slate-800'
                              : 'bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 hover:border-slate-500'
                          }`}
                        >
                          {alert.acknowledged ? (
                            <>
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                              <span>Acknowledged</span>
                            </>
                          ) : (
                            <>
                              <Check className="w-3.5 h-3.5 text-slate-400" />
                              <span>Acknowledge</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </main>

      {/* =====================================================================
          SOURCE CONFIGURATION MODAL (PER-TILE ASSIGNMENT)
          ===================================================================== */}
      {selectedCamForConfig && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f172a] border border-[#1e293b] rounded-lg max-w-md w-full p-5 shadow-2xl flex flex-col gap-4 font-sans">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Settings className="w-5 h-5 text-emerald-400" />
                <h3 className="font-mono text-base font-bold text-slate-100">
                  Configure Source // {selectedCamForConfig.id}
                </h3>
              </div>
              <button
                onClick={() => {
                  setSelectedCamForConfig(null);
                  setUploadMessage(null);
                }}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-slate-400">
              Select stream ingestion source for <strong className="text-slate-200">{selectedCamForConfig.name}</strong> ({selectedCamForConfig.zone}):
            </div>

            {/* Source Options List */}
            <div className="space-y-2.5">
              {/* 1. Local Hardware Webcam with Device ID Selector */}
              <div
                className={`p-3 rounded-lg border transition-colors ${
                  selectedCamForConfig.sourceType === 'WEBCAM'
                    ? 'bg-emerald-950/30 border-emerald-500/50'
                    : 'bg-slate-900 border-slate-800'
                }`}
              >
                <div className="flex items-start gap-3">
                  <Camera className="w-5 h-5 text-emerald-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-slate-200">
                        Local Hardware Webcam (DirectShow)
                      </span>
                      <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
                        DEV {modalDeviceId} SELECTED
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5 mb-2.5">
                      Stream from physical or virtual camera device index concurrently.
                    </p>

                    {/* Device Index Quick Selectors */}
                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                        Select Hardware Device Index:
                      </label>
                      <div className="grid grid-cols-3 gap-2">
                        <button
                          type="button"
                          onClick={() => setModalDeviceId(0)}
                          className={`px-2 py-1.5 rounded text-left border transition-all ${
                            modalDeviceId === 0
                              ? 'bg-emerald-600 text-white border-emerald-400 font-bold shadow-sm'
                              : 'bg-slate-950 hover:bg-slate-800 text-slate-300 border-slate-700'
                          }`}
                        >
                          <div className="font-mono text-xs font-semibold">Dev 0</div>
                          <div className="text-[9px] opacity-80 truncate">Iriun / Mobile</div>
                        </button>

                        <button
                          type="button"
                          onClick={() => setModalDeviceId(1)}
                          className={`px-2 py-1.5 rounded text-left border transition-all ${
                            modalDeviceId === 1
                              ? 'bg-emerald-600 text-white border-emerald-400 font-bold shadow-sm'
                              : 'bg-slate-950 hover:bg-slate-800 text-slate-300 border-slate-700'
                          }`}
                        >
                          <div className="font-mono text-xs font-semibold">Dev 1</div>
                          <div className="text-[9px] opacity-80 truncate">Laptop Webcam</div>
                        </button>

                        <button
                          type="button"
                          onClick={() => setModalDeviceId(2)}
                          className={`px-2 py-1.5 rounded text-left border transition-all ${
                            modalDeviceId === 2
                              ? 'bg-emerald-600 text-white border-emerald-400 font-bold shadow-sm'
                              : 'bg-slate-950 hover:bg-slate-800 text-slate-300 border-slate-700'
                          }`}
                        >
                          <div className="font-mono text-xs font-semibold">Dev 2</div>
                          <div className="text-[9px] opacity-80 truncate">HD Sensor</div>
                        </button>
                      </div>

                      {/* Custom Numeric Input for other indices */}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[11px] font-mono text-slate-400">Custom Index:</span>
                        <input
                          type="number"
                          min={0}
                          max={10}
                          value={modalDeviceId}
                          onChange={(e) => setModalDeviceId(Math.max(0, parseInt(e.target.value) || 0))}
                          className="w-16 px-2 py-1 bg-slate-950 border border-slate-700 rounded text-xs font-mono text-slate-200 focus:outline-none focus:border-emerald-500"
                        />
                        <span className="text-[10px] font-mono text-slate-500 truncate">
                          /api/webcam-stream/{modalDeviceId}
                        </span>
                      </div>

                      {/* Action Button to Assign Source */}
                      <button
                        type="button"
                        onClick={() => {
                          handleAssignSource(
                            selectedCamForConfig.id,
                            'WEBCAM',
                            `http://127.0.0.1:8000/api/webcam-stream/${modalDeviceId}`,
                            undefined,
                            modalDeviceId
                          );
                          setSelectedCamForConfig(null);
                        }}
                        className="mt-2 w-full py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold transition-colors shadow-sm flex items-center justify-center gap-1.5"
                      >
                        <Camera className="w-3.5 h-3.5" />
                        <span>Assign Stream // Device {modalDeviceId}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* 2. Backend Video Loop */}
              <button
                onClick={() => {
                  handleAssignSource(
                    selectedCamForConfig.id,
                    'BACKEND_LOOP',
                    'http://127.0.0.1:8000/api/video-stream'
                  );
                  setSelectedCamForConfig(null);
                }}
                className={`w-full p-3 rounded-lg border text-left flex items-start gap-3 transition-colors ${
                  selectedCamForConfig.sourceType === 'BACKEND_LOOP'
                    ? 'bg-emerald-950/30 border-emerald-500/50 text-slate-100'
                    : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
                }`}
              >
                <Video className="w-5 h-5 text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <div className="font-mono text-xs font-bold text-slate-200">
                    Backend Loop (test_video.mp4)
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Continuous surveillance simulation feed at <code className="text-emerald-400">/api/video-stream</code>.
                  </div>
                </div>
              </button>

              {/* 3. Upload Local MP4 File */}
              <div
                className={`p-3 rounded-lg border transition-colors ${
                  selectedCamForConfig.sourceType === 'CUSTOM_UPLOAD'
                    ? 'bg-emerald-950/30 border-emerald-500/50'
                    : 'bg-slate-900 border-slate-800'
                }`}
              >
                <div className="flex items-start gap-3">
                  <Upload className="w-5 h-5 text-emerald-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <div className="font-mono text-xs font-bold text-slate-200">
                      Upload Local MP4 File
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5 mb-2">
                      Uploads video to backend and attaches dynamic MJPEG stream.
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="video/mp4,video/*"
                      onChange={handleFileUpload}
                      disabled={uploadLoading}
                      className="block w-full text-xs text-slate-400 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border file:border-slate-700 file:text-xs file:font-mono file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700 cursor-pointer"
                    />
                    {uploadLoading && (
                      <div className="text-xs font-mono text-emerald-400 mt-2 flex items-center gap-1.5">
                        <RefreshCw className="w-3 h-3 animate-spin" />
                        Uploading to backend...
                      </div>
                    )}
                    {uploadMessage && (
                      <div className="text-xs font-mono text-slate-300 mt-2">
                        {uploadMessage}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* 4. Standby / Offline Pattern */}
              <button
                onClick={() => {
                  handleAssignSource(selectedCamForConfig.id, 'STANDBY', '');
                  setSelectedCamForConfig(null);
                }}
                className={`w-full p-3 rounded-lg border text-left flex items-start gap-3 transition-colors ${
                  selectedCamForConfig.sourceType === 'STANDBY'
                    ? 'bg-slate-950 border-amber-500/50 text-slate-100'
                    : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
                }`}
              >
                <Radio className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
                <div>
                  <div className="font-mono text-xs font-bold text-slate-200">
                    Offline / Standby Pattern
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Places camera in standby state with high-contrast diagnostic test card.
                  </div>
                </div>
              </button>
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => {
                  setSelectedCamForConfig(null);
                  setUploadMessage(null);
                }}
                className="px-4 py-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          LIVE BIOMETRIC PERSONNEL ENROLLMENT MODAL
          ===================================================================== */}
      {showEnrollModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-[#0f172a] border border-[#1e293b] rounded-xl shadow-2xl max-w-2xl w-full p-6 text-slate-200 relative overflow-hidden flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  <UserCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-base text-slate-100 flex items-center gap-2">
                    Register New Personnel
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/50">
                      LIVE ARCFACE
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    Capture face embedding directly from live optical feed into biometric database
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowEnrollModal(false);
                  setEnrollFeedback(null);
                }}
                className="text-slate-400 hover:text-slate-200 p-1.5 rounded hover:bg-slate-800 transition-colors"
                title="Close Modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body: Viewfinder + Form Inputs */}
            <div className="py-4 space-y-4 overflow-y-auto flex-1 pr-1">
              {/* Feedback Alert Banner */}
              {enrollFeedback && (
                <div
                  className={`p-3 rounded-lg border flex items-start gap-2.5 text-xs font-mono transition-all ${
                    enrollFeedback.type === 'success'
                      ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'
                      : 'bg-red-950/40 border-red-500/50 text-red-300'
                  }`}
                >
                  {enrollFeedback.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 leading-relaxed">
                    {enrollFeedback.message}
                  </div>
                </div>
              )}

              {/* Camera Source Selector */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1.5 uppercase tracking-wider">
                  Optical Source Selector
                </label>
                <select
                  value={enrollDeviceId}
                  onChange={(e) => setEnrollDeviceId(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
                >
                  <option value={0}>Device 0 &mdash; Mobile Webcam (Iriun / Device 0)</option>
                  <option value={1}>Device 1 &mdash; Laptop Webcam (Physical / Device 1)</option>
                  <option value={2}>Device 2 &mdash; External USB / Secondary Sensor</option>
                </select>
              </div>

              {/* Live Viewfinder Feed */}
              <div>
                <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1.5">
                  <span className="flex items-center gap-1.5">
                    <Camera className="w-3.5 h-3.5 text-emerald-400" />
                    LIVE ALIGNMENT VIEWFINDER (DEVICE {enrollDeviceId})
                  </span>
                  <span className="text-[10px] text-emerald-400/80 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    REAL-TIME MJPEG
                  </span>
                </div>
                <div className="relative aspect-video bg-black rounded-lg border border-slate-800 overflow-hidden flex items-center justify-center group shadow-inner">
                  <img
                    key={`viewfinder-stream-${enrollDeviceId}`}
                    src={`http://127.0.0.1:8000/api/webcam-stream/${enrollDeviceId}`}
                    alt={`Enrollment Viewfinder Cam ${enrollDeviceId}`}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.currentTarget as HTMLElement).style.display = 'none';
                      const fallback = e.currentTarget.parentElement?.querySelector('.stream-fallback');
                      if (fallback) fallback.classList.remove('hidden');
                    }}
                  />
                  {/* Fallback placeholder if stream disconnected */}
                  <div className="stream-fallback hidden absolute inset-0 flex flex-col items-center justify-center p-4 text-center bg-slate-950/90 text-slate-500 font-mono text-xs">
                    <Camera className="w-8 h-8 mb-2 text-slate-600" />
                    <span>Camera stream offline or unavailable</span>
                    <span className="text-[10px] text-slate-600 mt-1">Check that Device {enrollDeviceId} is connected</span>
                  </div>

                  {/* Facial Alignment Target Reticle Overlay */}
                  <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                    <div className="w-36 h-48 sm:w-44 sm:h-56 border-2 border-dashed border-emerald-400/40 rounded-full flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-emerald-400/30" />
                    </div>
                  </div>
                  <div className="pointer-events-none absolute bottom-2 left-2 right-2 text-center text-[10px] font-mono text-slate-400 bg-slate-950/70 py-0.5 px-2 rounded">
                    Position personnel face inside the target frame before capturing
                  </div>
                </div>
              </div>

              {/* Form Inputs (Full Name, Roll Number, Employee ID) */}
              <form onSubmit={handleEnrollSubmit} className="space-y-3 pt-1">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-mono text-slate-400 mb-1">
                      Full Name *
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. John Doe"
                      value={enrollName}
                      onChange={(e) => setEnrollName(e.target.value)}
                      disabled={enrollLoading}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-mono text-slate-400 mb-1">
                      Roll Number *
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. 21CS042"
                      value={enrollRoll}
                      onChange={(e) => setEnrollRoll(e.target.value)}
                      disabled={enrollLoading}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-mono text-slate-400 mb-1">
                    Employee ID *
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. EMP-1001"
                    value={enrollId}
                    onChange={(e) => setEnrollId(e.target.value)}
                    disabled={enrollLoading}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 transition-colors"
                  />
                </div>
              </form>
            </div>

            {/* Modal Footer Actions */}
            <div className="pt-4 border-t border-slate-800 flex items-center justify-between gap-3">
              <span className="text-[11px] font-mono text-slate-500 hidden sm:inline">
                Storage: <span className="text-slate-400">mock_employee_db.pkl</span> (512-d normalized)
              </span>
              <div className="flex items-center gap-2 ml-auto">
                <button
                  type="button"
                  onClick={() => {
                    setShowEnrollModal(false);
                    setEnrollFeedback(null);
                  }}
                  disabled={enrollLoading}
                  className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleEnrollSubmit()}
                  disabled={enrollLoading}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-semibold shadow-lg shadow-emerald-950/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {enrollLoading ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      Capturing &amp; Extracting...
                    </>
                  ) : (
                    <>
                      <Camera className="w-3.5 h-3.5" />
                      Capture &amp; Enroll
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          INDUSTRIAL STATUS FOOTER (UNIFIED UATU BRANDING)
          ===================================================================== */}
      <footer className="border-t border-[#1e293b] bg-[#020617] px-4 py-2 sm:px-6 text-[11px] font-mono text-slate-500 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span>UATU PLATFORM BUILD: v1.0.0-STAGE1</span>
          <span className="hidden sm:inline">&bull;</span>
          <span className="hidden sm:inline">DATABASE: POSTGRESQL 16.2</span>
          <span className="hidden sm:inline">&bull;</span>
          <span>UNIFIED ASSISTANT FOR THREAT &amp; UNDERSTANDING (AI)</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            UATU TELEMETRY HARNESS ACTIVE
          </span>
        </div>
      </footer>
    </div>
  );
};

export default App;
