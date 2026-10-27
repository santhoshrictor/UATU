import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  CreditCard,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Camera,
  X,
  ChevronDown,
  Grid,
  LayoutGrid,
  List,
  MapPin,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import { EnrollModal } from './components/EnrollModal';
import { SettingsModal } from './components/SettingsModal';
import { AuditLogsPage } from './components/AuditLogsPage';
import { IncidentQueue, type IncidentAlert, type AlertSeverity } from './components/IncidentQueue';
import { LeftSidebar, type NavTabId } from './components/LeftSidebar';
import { TopHeader } from './components/TopHeader';
import { CameraCard, type CameraCardData } from './components/CameraCard';
import { RecentAlertsPanel } from './components/RecentAlertsPanel';
import { EvidenceModal } from './components/EvidenceModal';
import { Button } from './components/ui/button';
import { FlowButton } from './components/ui/flow-button';
import { UATUVoiceAssistantLauncher } from './components/UATUVoiceAssistantLauncher';

/* =========================================================================
   TYPE DEFINITIONS
   ========================================================================= */

type AccessVerdict = 'AUTHORIZED' | 'MISMATCH' | 'TAILGATING';
type GridLayout = '1x1' | '2x2' | '3x3';
type ViewMode = 'grid' | 'list' | 'map';

interface CameraChannel extends CameraCardData {
  customFileName?: string;
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

interface InfraStatus {
  backendOnline: boolean;
  postgresActive: boolean;
  dbLatencyMs: number | null;
  serverVersion: string | null;
  lastProbeTime: string | null;
  probeError: string | null;
}

/* =========================================================================
   TIME UTILITIES
   ========================================================================= */

function formatUtcTime(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false }) + ' UTC';
}

function formatCardDate(): string {
  return new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatCardTime(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false });
}

/* =========================================================================
   DEFAULT 9-CAMERA MULTIVIEW CONFIGURATION (3x3 MATRIX)
   ========================================================================= */

const INITIAL_CAMERAS: CameraChannel[] = [
  {
    id: 'CAM-01',
    name: 'Main Entrance',
    zone: 'Zone 01 // Main Turnstile North',
    sourceType: 'WEBCAM',
    deviceId: 0,
    streamUrl: 'http://127.0.0.1:8000/api/webcam-stream/0',
    isOnline: true,
    fps: 30,
    resolution: '640x480',
    occupancy: 0,
    entry: 0,
    exit: 0,
  },
  {
    id: 'CAM-02',
    name: 'Production Floor',
    zone: 'Zone 01 // Optical Turnstile B',
    sourceType: 'WEBCAM',
    deviceId: 1,
    streamUrl: 'http://127.0.0.1:8000/api/webcam-stream/1',
    isOnline: true,
    fps: 30,
    resolution: '640x480',
    occupancy: 0,
    entry: 0,
    exit: 0,
  },
  {
    id: 'CAM-03',
    name: 'Warehouse',
    zone: 'Zone 03 // Logistics Yard North',
    sourceType: 'BACKEND_LOOP',
    streamUrl: 'http://127.0.0.1:8000/api/video-stream',
    isOnline: false,
    fps: 0,
    resolution: '1080p',
    occupancy: 0,
    entry: 0,
    exit: 0,
  },
  {
    id: 'CAM-04',
    name: 'Loading Dock',
    zone: 'Zone 02 // Precision Machining Line',
    sourceType: 'STANDBY',
    streamUrl: '',
    isOnline: false,
    fps: 0,
    resolution: '1080p',
    occupancy: 0,
    entry: 0,
    exit: 0,
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
    occupancy: 0,
    entry: 0,
    exit: 0,
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
    occupancy: 0,
    entry: 0,
    exit: 0,
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
    occupancy: 0,
    entry: 0,
    exit: 0,
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
    occupancy: 0,
    entry: 0,
    exit: 0,
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
    occupancy: 0,
    entry: 0,
    exit: 0,
  },
];

const INITIAL_ACCESS_EVENT: AccessEvent = {
  id: 'STANDBY',
  badgeId: 'STANDBY',
  employeeName: 'Awaiting Credential Scan',
  department: 'Turnstile Access Lane',
  faceMatchScore: 0.0,
  verdict: 'AUTHORIZED',
  zone: 'Zone 01 // Main Turnstile North',
  readerId: 'HID-SIGNO-40-A1',
  timestamp: '--:--:--',
  occupancyDetected: 0,
};

const INITIAL_ALERTS: IncidentAlert[] = [];

/* =========================================================================
   MAIN COMMAND CENTER COMPONENT
   ========================================================================= */

export const App: React.FC = () => {
  // Navigation & View State
  const [navTab, setNavTab] = useState<NavTabId>('live');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [cameraFilter, setCameraFilter] = useState<string>('ALL');
  const [searchFilter, setSearchFilter] = useState<string>('');

  // Backend & Database Infrastructure Telemetry
  const [infra, setInfra] = useState<InfraStatus>({
    backendOnline: false,
    postgresActive: false,
    dbLatencyMs: null,
    serverVersion: null,
    lastProbeTime: null,
    probeError: null,
  });
  const [cardTime, setCardTime] = useState<string>(formatCardTime);
  const [cardDate, setCardDate] = useState<string>(formatCardDate);

  // Grid Layout State (1x1 Focus View, 2x2 Quad View, 3x3 Matrix View)
  const [gridLayout, setGridLayout] = useState<GridLayout>('2x2');
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
    setUploadMessage(null);
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

      const targetId = selectedCamForConfig.id;
      setCameras((prev) =>
        prev.map((c) =>
          c.id === targetId
            ? {
                ...c,
                sourceType: 'CUSTOM_UPLOAD',
                streamUrl,
                customFileName: file.name,
                isOnline: true,
              }
            : c
        )
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

  // Auto-recovery / reconnect tracking per camera
  const [streamErrors, setStreamErrors] = useState<Record<string, boolean>>({});

  // Access Control Simulation & Alert State
  const [currentAccess, setCurrentAccess] = useState<AccessEvent>(INITIAL_ACCESS_EVENT);
  const [alerts, setAlerts] = useState<IncidentAlert[]>(() => {
    try {
      const saved = localStorage.getItem('uatu_incident_queue');
      if (saved !== null) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          return parsed;
        }
      }
    } catch (err) {
      console.warn('[UATU Alert Bridge] Error reading persisted alerts queue from localStorage:', err);
    }
    return INITIAL_ALERTS;
  });
  const [alertFilter, setAlertFilter] = useState<'ALL' | 'UNACKNOWLEDGED'>('ALL');

  // Keep localStorage continuously synchronized with alerts state
  useEffect(() => {
    try {
      localStorage.setItem('uatu_incident_queue', JSON.stringify(alerts));
    } catch (err) {
      console.warn('[UATU Alert Bridge] Failed to persist alerts queue to localStorage:', err);
    }
  }, [alerts]);

  // Synchronize Incident Dispatch Queue and Live Camera Telemetry
  useEffect(() => {
    let isMounted = true;
    const fetchLiveEvents = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/live-events');
        if (res.ok && isMounted) {
          const data = await res.json();
          if (Array.isArray(data.events)) {
            const mappedAlerts: IncidentAlert[] = data.events.map((ev: any) => {
              const sev = (ev.alarm_class || ev.level || ev.severity || 'WARNING').toUpperCase() as AlertSeverity;
              const ts = ev.timestamp_ist || ev.timestamp || ev.time || '00:00:00 IST';
              return {
                id: ev.event_id || ev.id,
                timestamp: ts,
                time: ev.time || ts,
                zone: ev.zone || 'Facility Zone',
                camera: ev.camera_id || ev.camera || 'CAM-01',
                type: ev.event_type || ev.type || 'SECURITY_ALERT',
                severity: sev,
                level: sev,
                detail: ev.detail || ev.message || '',
                snapshot_url: ev.snapshot_url || '',
                confidence_pct: ev.confidence_pct,
                acknowledged: Boolean(ev.acknowledged),
                acknowledgedAt: ev.acknowledged_at_ist || undefined,
                eventRef: ev.event_ref,
              };
            });
            setAlerts(mappedAlerts);
          }
          const telemMap = data.camera_telemetry || data.telemetry;
          if (telemMap && typeof telemMap === 'object') {
            setCameras((prev) =>
              prev.map((c) => {
                const telem = telemMap[c.id];
                if (!telem) return c;
                return {
                  ...c,
                  occupancy: telem.occupancy !== undefined ? telem.occupancy : c.occupancy,
                  personCount: telem.person_count !== undefined ? telem.person_count : (telem.occupancy !== undefined ? telem.occupancy : c.personCount),
                  entry: telem.entry_count !== undefined ? telem.entry_count : c.entry,
                  exit: telem.exit_count !== undefined ? telem.exit_count : c.exit,
                  fps: telem.fps !== undefined && telem.fps > 0 ? telem.fps : c.fps,
                };
              })
            );
          }
        }
      } catch (err) {
        console.debug('[UATU Alert Bridge] Live events telemetry notice:', err);
      }
    };

    fetchLiveEvents();
    const interval = setInterval(fetchLiveEvents, 1500);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // System Settings & Audit Log Modal State
  const [showSettingsModal, setShowSettingsModal] = useState<boolean>(false);

  // Dedicated Audit Logs Dashboard View & Fortress Session State
  const [activeView, setActiveView] = useState<'MULTIVIEW' | 'AUDIT_LOGS'>('MULTIVIEW');
  const [auditTargetDate, setAuditTargetDate] = useState<string>(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  });
  const [fortressSession, setFortressSession] = useState<{
    token: string;
    username: string;
    trustScore: number;
  } | null>(() => {
    try {
      const raw = sessionStorage.getItem('uatu_fortress_session');
      if (raw) return JSON.parse(raw);
    } catch {}
    return null;
  });

  useEffect(() => {
    if (fortressSession) {
      sessionStorage.setItem('uatu_fortress_session', JSON.stringify(fortressSession));
    } else {
      sessionStorage.removeItem('uatu_fortress_session');
    }
  }, [fortressSession]);

  // Evidence Snapshot & Forensic Gallery Modal State
  const [selectedEvidenceAlert, setSelectedEvidenceAlert] = useState<IncidentAlert | null>(null);
  const [isEvidenceModalOpen, setIsEvidenceModalOpen] = useState<boolean>(false);
  const [evidenceModalTab, setEvidenceModalTab] = useState<'INSPECT' | 'GALLERY'>('INSPECT');

  const handleOpenEvidence = useCallback((alert: IncidentAlert) => {
    setSelectedEvidenceAlert(alert);
    setEvidenceModalTab('INSPECT');
    setIsEvidenceModalOpen(true);
  }, []);

  const handleOpenEvidenceGallery = useCallback(() => {
    setSelectedEvidenceAlert(null);
    setEvidenceModalTab('GALLERY');
    setIsEvidenceModalOpen(true);
  }, []);

  // Live Biometric Personnel Enrollment Modal State
  const [showEnrollModal, setShowEnrollModal] = useState<boolean>(false);
  const [enrollDeviceId, setEnrollDeviceId] = useState<number>(1);
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
  const [verifyDeviceId, setVerifyDeviceId] = useState<number>(1);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifyFeedback, setVerifyFeedback] = useState<{
    type: 'success' | 'warning' | 'error';
    message: string;
  } | null>(null);
  const [enrolledUsers, setEnrolledUsers] = useState<Array<{ employee_id: string; name: string; roll: string }>>([]);

  const refreshEnrolledUsers = useCallback(async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/enrolled-users');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.users)) {
          setEnrolledUsers(data.users);
          if (data.users.length > 0) {
            setVerifyEmployeeId((prev) => {
              if (prev === 'EMP-1001' && !data.users.some((u: { employee_id: string }) => u.employee_id === 'EMP-1001')) {
                return data.users[0].employee_id;
              }
              return prev;
            });
          }
        }
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    refreshEnrolledUsers();
  }, [refreshEnrolledUsers]);

  // Live System Clocks
  useEffect(() => {
    const interval = setInterval(() => {
      setCardTime(formatCardTime());
      setCardDate(formatCardDate());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Escape Key Focus Handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isEvidenceModalOpen) {
          setIsEvidenceModalOpen(false);
        }
        if (focusedCameraId) {
          setFocusedCameraId(null);
          setGridLayout('2x2');
        }
        if (selectedCamForConfig) {
          setSelectedCamForConfig(null);
        }
        if (showEnrollModal) {
          setShowEnrollModal(false);
        }
        if (showSettingsModal) {
          setShowSettingsModal(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [focusedCameraId, selectedCamForConfig, showEnrollModal, showSettingsModal, isEvidenceModalOpen]);

  // Infrastructure Probing
  const probeInfrastructure = useCallback(async () => {
    const start = performance.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3500);

      const res = await fetch('http://127.0.0.1:8000/', {
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const latency = performance.now() - start;

      if (res.ok) {
        const data = await res.json();
        setInfra({
          backendOnline: true,
          postgresActive: true,
          dbLatencyMs: latency,
          serverVersion: data.version || '1.0.0',
          lastProbeTime: formatUtcTime(),
          probeError: null,
        });
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Connection failed';
      setInfra((prev) => ({
        ...prev,
        backendOnline: false,
        postgresActive: false,
        lastProbeTime: formatUtcTime(),
        probeError: msg,
      }));
    }
  }, []);

  useEffect(() => {
    probeInfrastructure();
    const interval = setInterval(probeInfrastructure, 15000);
    return () => clearInterval(interval);
  }, [probeInfrastructure]);

  // WebSocket Live Alert Stream & Telemetry
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connectWs = () => {
      try {
        ws = new WebSocket('ws://127.0.0.1:8000/ws/alerts');

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'ALERTS_CLEARED') {
              setAlerts([]);
              localStorage.removeItem('uatu_incident_queue');
              return;
            }

            if (data.type === 'TELEMETRY_UPDATE') {
              const camId = data.camera_id || data.camera;
              if (camId && data.counts) {
                setCameras((prev) =>
                  prev.map((c) =>
                    c.id === camId
                      ? {
                          ...c,
                          occupancy: data.counts.occupancy !== undefined ? data.counts.occupancy : c.occupancy,
                          personCount: data.counts.persons !== undefined ? data.counts.persons : (data.counts.person_count !== undefined ? data.counts.person_count : (data.counts.occupancy !== undefined ? data.counts.occupancy : c.personCount)),
                          entry: data.counts.entry !== undefined ? data.counts.entry : (data.counts.entries !== undefined ? data.counts.entries : c.entry),
                          exit: data.counts.exit !== undefined ? data.counts.exit : (data.counts.exits !== undefined ? data.counts.exits : c.exit),
                          fps: data.counts.fps || c.fps,
                        }
                      : c
                  )
                );
              }
              return;
            }

            // Real-Time Detection Alert Received
            if (data.id || data.event_id || data.type || data.alert_type) {
              const alertId = String(data.id || data.event_id || `EVT-${Date.now()}`);
              const alertType = String(data.alert_type || data.type || data.event_type || 'SECURITY BREACH');
              const sev = (data.alarm_class || data.level || data.severity || 'WARNING').toUpperCase() as AlertSeverity;
              const ts = data.timestamp_ist || data.time || data.timestamp || new Date().toLocaleTimeString('en-US', { hour12: false }) + ' IST';
              const newAlert: IncidentAlert = {
                id: alertId,
                timestamp: ts,
                time: data.time || ts,
                zone: data.zone || 'Facility Zone',
                camera: data.camera || data.camera_id || 'CAM-01',
                type: alertType,
                severity: sev,
                level: sev,
                detail: data.detail || data.message || 'Automated sensor event triggered.',
                snapshot_url: data.snapshot_url || '',
                confidence_pct: data.confidence_pct,
                acknowledged: Boolean(data.acknowledged),
                eventRef: data.event_ref,
              };

              setAlerts((prev) => {
                const existingIdx = prev.findIndex((a) => a.id === alertId);
                if (existingIdx >= 0) {
                  const updated = [...prev];
                  updated[existingIdx] = { ...updated[existingIdx], ...newAlert };
                  return updated;
                }
                return [newAlert, ...prev];
              });

              const camId = data.camera || data.camera_id;
              if (camId) {
                setCameras((prev) =>
                  prev.map((c) =>
                    c.id === camId
                      ? {
                          ...c,
                          occupancy: data.occupancy !== undefined ? data.occupancy : c.occupancy,
                          personCount: data.person_count !== undefined ? data.person_count : (data.occupancy !== undefined ? data.occupancy : c.personCount),
                        }
                      : c
                  )
                );
              }
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
          }
        };

        ws.onclose = () => {
          reconnectTimer = setTimeout(connectWs, 3000);
        };
        ws.onerror = () => {
          ws?.close();
        };
      } catch (err) {
        reconnectTimer = setTimeout(connectWs, 3000);
      }
    };

    connectWs();
    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // Alert Reset
  const handleResetAlerts = async () => {
    setAlerts([]);
    localStorage.removeItem('uatu_incident_queue');
    try {
      await fetch('http://127.0.0.1:8000/api/live-events/reset', { method: 'POST' });
    } catch (err) {
      console.warn('[UATU Alert Bridge] Error resetting alert queue:', err);
    }
  };

  // Toggle Alert Acknowledge
  const toggleAcknowledge = async (id: string) => {
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

    try {
      await fetch(`http://127.0.0.1:8000/api/live-events/${encodeURIComponent(id)}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ acknowledged_by: 'Dashboard_Supervisor' }),
      });
    } catch {}
  };

  const unacknowledgedCount = useMemo(() => {
    return alerts.filter((a) => !a.acknowledged).length;
  }, [alerts]);

  // Visible Cameras Filtered
  const visibleCameras = useMemo(() => {
    let list = cameras;
    if (cameraFilter !== 'ALL') {
      list = cameras.filter((c) => c.id === cameraFilter);
    }
    if (searchFilter.trim()) {
      const q = searchFilter.toLowerCase();
      list = list.filter((c) => c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q) || c.zone.toLowerCase().includes(q));
    }
    if (gridLayout === '1x1') {
      const focused = list.find((c) => c.id === (focusedCameraId || 'CAM-01'));
      return focused ? [focused] : [list[0] || cameras[0]];
    }
    if (gridLayout === '2x2') {
      return list.slice(0, 4);
    }
    return list; // 3x3 returns all
  }, [gridLayout, focusedCameraId, cameras, cameraFilter, searchFilter]);

  const totalOccupancy = useMemo(() => {
    return cameras.reduce((acc, c) => acc + (c.occupancy ?? 0), 0);
  }, [cameras]);

  const totalPersons = useMemo(() => {
    return cameras.reduce((acc, c) => acc + (c.personCount ?? c.occupancy ?? 0), 0);
  }, [cameras]);

  const totalEntries = useMemo(() => {
    return cameras.reduce((acc, c) => acc + (c.entry ?? 0), 0);
  }, [cameras]);

  const totalExits = useMemo(() => {
    return cameras.reduce((acc, c) => acc + (c.exit ?? 0), 0);
  }, [cameras]);

  // Biometric Personnel Enrollment Submission
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
      refreshEnrolledUsers();
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

  // Live Verification Trigger (YOLOv8 + InsightFace ArcFace)
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
          camera: `CAM-0${verifyDeviceId + 1}`,
          type: 'Face Mismatch Detected',
          severity: 'WARNING',
          detail: `Optical ArcFace match scored ${data.match_score}% for scanned badge ${data.employee_id} (${data.employee_name}).`,
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
          camera: `CAM-0${verifyDeviceId + 1}`,
          type: 'Tailgating Detected',
          severity: 'CRITICAL',
          detail: `Multiple individuals detected passing optical turnstile with single RFID badge scan.`,
          acknowledged: false,
          eventRef: accessId,
        };
        setAlerts((prev) => [newAlert, ...prev]);
        setVerifyFeedback({
          type: 'error',
          message: `TAILGATING: Multiple persons detected at optical lane.`,
        });
      } else {
        setVerifyFeedback({
          type: 'success',
          message: `AUTHORIZED: Personnel verified (${data.employee_name}, Score: ${data.match_score}%).`,
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Verification failed';
      setVerifyFeedback({
        type: 'error',
        message: msg,
      });
    } finally {
      setIsVerifying(false);
    }
  };

  // Snapshot Downloader
  const handleSnapshot = (cam: CameraChannel) => {
    if (cam.streamUrl) {
      window.open(cam.streamUrl, '_blank');
    }
  };

  return (
    <div className="min-h-screen bg-[#060b18] text-[#f8fafc] flex font-sans selection:bg-blue-600 selection:text-white">
      {/* =====================================================================
          1. LEFT SIDEBAR NAVIGATION
          ===================================================================== */}
      <LeftSidebar
        activeTab={navTab}
        onSelectTab={(tab) => {
          if (tab === 'settings') {
            setShowSettingsModal(true);
          } else if (tab === 'reports') {
            setActiveView('AUDIT_LOGS');
            setNavTab(tab);
          } else {
            setActiveView('MULTIVIEW');
            setNavTab(tab);
          }
        }}
        systemOnline={infra.backendOnline}
        incidentCount={unacknowledgedCount}
        onSystemStatusClick={probeInfrastructure}
      />

      {/* =====================================================================
          2. MAIN CENTER WORKSPACE
          ===================================================================== */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto">
        {/* Top Header Bar */}
        <TopHeader
          unacknowledgedAlertsCount={unacknowledgedCount}
          occupancyCount={totalOccupancy}
          personCount={totalPersons}
          inCount={totalEntries}
          outCount={totalExits}
          onNotificationClick={() => setNavTab('incidents')}
          onSearch={(q) => setSearchFilter(q)}
        />

        {/* Dedicated Fortress Audit Logs or Main Workspace */}
        {activeView === 'AUDIT_LOGS' && fortressSession ? (
          <AuditLogsPage
            sessionToken={fortressSession.token}
            superadminUser={fortressSession.username}
            trustScore={fortressSession.trustScore}
            initialDate={auditTargetDate}
            onBackToMultiview={() => {
              setActiveView('MULTIVIEW');
              setNavTab('live');
            }}
            backendUrl="http://127.0.0.1:8000"
          />
        ) : (
          <main className="p-6 flex-1 flex flex-col gap-6">
            {/* View Controls Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-4">
              {/* Camera Selector Dropdown & Zone Summary Pill */}
              <div className="flex flex-wrap items-center gap-3">
                <div className="relative">
                  <select
                    value={cameraFilter}
                    onChange={(e) => setCameraFilter(e.target.value)}
                    className="appearance-none bg-[#0b132b] hover:bg-[#0e1838] border border-[#162347] rounded-xl pl-3.5 pr-8 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:border-blue-500 transition-colors cursor-pointer"
                  >
                    <option value="ALL">All Cameras</option>
                    {cameras.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.id} — {c.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>

                {/* Zone Count Summary Badge */}
                <div
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#0b132b] border border-[#162347] text-xs font-mono shadow-sm"
                  title="Aggregated Active Zone People Count"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-slate-400">Total Detected:</span>
                  <span className="text-emerald-400 font-bold">{totalPersons} Persons</span>
                  <span className="text-slate-600">|</span>
                  <span className="text-slate-400">Zones:</span>
                  <span className="text-slate-200 font-semibold">
                    {cameras.filter((c) => c.isOnline && c.sourceType !== 'STANDBY').length} Active
                  </span>
                </div>
              </div>

              {/* View Switchers & Ask IRIS AI FlowButton */}
              <div className="flex items-center gap-3">
                {/* Grid / List / Map Toggle Buttons */}
                <div className="flex items-center bg-[#0b132b] border border-[#162347] rounded-xl p-1 gap-1 text-xs">
                  <Button
                    onClick={() => {
                      setViewMode('grid');
                      setGridLayout((prev) => (prev === '2x2' ? '3x3' : '2x2'));
                    }}
                    variant={viewMode === 'grid' ? 'default' : 'ghost'}
                    size="sm"
                    className={`flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium transition-all ${
                      viewMode === 'grid'
                        ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm font-semibold'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                    }`}
                    title={gridLayout === '2x2' ? 'Toggle 3x3 Matrix' : 'Toggle 2x2 Quad'}
                  >
                    {gridLayout === '3x3' ? <Grid className="w-3.5 h-3.5" /> : <LayoutGrid className="w-3.5 h-3.5" />}
                    <span>{gridLayout === '3x3' ? '3x3 Matrix' : 'Grid'}</span>
                  </Button>

                  <Button
                    onClick={() => setViewMode('list')}
                    variant={viewMode === 'list' ? 'default' : 'ghost'}
                    size="sm"
                    className={`flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium transition-all ${
                      viewMode === 'list'
                        ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm font-semibold'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                    }`}
                    title="Compact Camera Table View"
                  >
                    <List className="w-3.5 h-3.5" />
                    <span>List</span>
                  </Button>

                  <Button
                    onClick={() => setViewMode('map')}
                    variant={viewMode === 'map' ? 'default' : 'ghost'}
                    size="sm"
                    className={`flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium transition-all ${
                      viewMode === 'map'
                        ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm font-semibold'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                    }`}
                    title="Facility Blueprint & Zone Map"
                  >
                    <MapPin className="w-3.5 h-3.5" />
                    <span>Map</span>
                  </Button>
                </div>

                {/* Ask IRIS AI FlowButton */}
                <UATUVoiceAssistantLauncher
                  trigger={(open) => (
                    <FlowButton
                      text="Ask IRIS AI"
                      onClick={open}
                    />
                  )}
                />
              </div>
            </div>

            {/* TAB CONTENT: LIVE VIEW */}
            {navTab === 'live' && (
              <>
                {viewMode === 'grid' && (
                  <div
                    className={`grid gap-5 transition-all duration-200 ${
                      gridLayout === '1x1'
                        ? 'grid-cols-1'
                        : gridLayout === '2x2'
                        ? 'grid-cols-1 lg:grid-cols-2'
                        : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'
                    }`}
                  >
                    {visibleCameras.map((cam) => (
                      <CameraCard
                        key={cam.id}
                        camera={cam}
                        isFocused={focusedCameraId === cam.id && gridLayout === '1x1'}
                        streamError={Boolean(streamErrors[cam.id])}
                        currentTimeString={cardTime}
                        currentDateString={cardDate}
                        onConfigureClick={(c) => openConfigModal(c as CameraChannel)}
                        onFocusToggle={(c) => {
                          if (gridLayout === '1x1') {
                            setGridLayout('2x2');
                            setFocusedCameraId(null);
                          } else {
                            setFocusedCameraId(c.id);
                            setGridLayout('1x1');
                          }
                        }}
                        onSnapshotClick={(c) => handleSnapshot(c as CameraChannel)}
                        onStreamErrorChange={(id, isErr) =>
                          setStreamErrors((prev) => ({ ...prev, [id]: isErr }))
                        }
                      />
                    ))}
                  </div>
                )}

                {/* 1x1 Focus Mode Escape Banner */}
                {gridLayout === '1x1' && (
                  <div className="bg-[#0b132b] rounded-xl border border-[#162347] px-4 py-2.5 flex items-center justify-between text-xs text-slate-400">
                    <span>
                      Press <kbd className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-200 font-mono">Esc</kbd> to return to standard grid
                    </span>
                    <Button
                      onClick={() => {
                        setGridLayout('2x2');
                        setFocusedCameraId(null);
                      }}
                      variant="ghost"
                      size="sm"
                      className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 font-semibold text-xs h-7 px-2.5"
                    >
                      Return to 2x2 View
                    </Button>
                  </div>
                )}

                {/* List View Mode */}
                {viewMode === 'list' && (
                  <div className="bg-[#0b132b] rounded-2xl border border-[#162347] overflow-hidden shadow-xl">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-[#0e1838] border-b border-[#162347] text-slate-400 font-mono">
                          <th className="py-3 px-4">CAMERA</th>
                          <th className="py-3 px-4">NAME &amp; LOCATION</th>
                          <th className="py-3 px-4">STREAM SOURCE</th>
                          <th className="py-3 px-4">FPS &amp; RESOLUTION</th>
                          <th className="py-3 px-4">OCCUPANCY</th>
                          <th className="py-3 px-4">STATUS</th>
                          <th className="py-3 px-4 text-right">ACTION</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#162347]/60">
                        {cameras.map((cam) => (
                          <tr key={cam.id} className="hover:bg-[#0e1838]/50 transition-colors">
                            <td className="py-3 px-4 font-bold text-white font-mono">{cam.id}</td>
                            <td className="py-3 px-4">
                              <div className="font-semibold text-slate-200">{cam.name}</div>
                              <div className="text-[11px] text-slate-400">{cam.zone}</div>
                            </td>
                            <td className="py-3 px-4 font-mono text-slate-300">
                              {cam.sourceType === 'WEBCAM' ? `Webcam (Dev ${cam.deviceId ?? 0})` : cam.sourceType}
                            </td>
                            <td className="py-3 px-4 font-mono text-slate-300">
                              {cam.fps || 30} FPS • {cam.resolution}
                            </td>
                            <td className="py-3 px-4 font-mono">
                              <span className="text-emerald-400 font-semibold">{cam.personCount ?? cam.occupancy ?? 0}</span> (OCC: {cam.occupancy ?? 0} | IN: {cam.entry ?? 0} / OUT: {cam.exit ?? 0})
                            </td>
                            <td className="py-3 px-4">
                              <span
                                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                                  cam.isOnline && cam.sourceType !== 'STANDBY'
                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                    : 'bg-slate-800 text-slate-400'
                                }`}
                              >
                                <span className={`w-1.5 h-1.5 rounded-full ${cam.isOnline ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                                {cam.isOnline && cam.sourceType !== 'STANDBY' ? 'Online' : 'Standby'}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <Button
                                onClick={() => openConfigModal(cam)}
                                variant="secondary"
                                size="sm"
                                className="h-7 px-2.5 rounded-lg bg-[#0e1838] hover:bg-blue-600 text-slate-300 hover:text-white border border-[#162347] text-xs"
                              >
                                Configure
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Map View Mode */}
                {viewMode === 'map' && (
                  <div className="bg-[#0b132b] rounded-2xl border border-[#162347] p-6 shadow-xl flex flex-col gap-4">
                    <div className="flex items-center justify-between pb-3 border-b border-[#162347]">
                      <div className="flex items-center gap-2">
                        <MapPin className="w-5 h-5 text-blue-400" />
                        <h2 className="text-base font-bold text-white">Facility Zone Sensor Map</h2>
                      </div>
                      <span className="text-xs text-slate-400 font-mono">9 Surveillance Zones Linked</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {cameras.map((cam) => (
                        <div
                          key={cam.id}
                          onClick={() => {
                            setFocusedCameraId(cam.id);
                            setGridLayout('1x1');
                            setViewMode('grid');
                          }}
                          className="bg-[#0e1838] border border-[#162347] hover:border-blue-500 p-4 rounded-xl cursor-pointer transition-all hover:scale-[1.01]"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-bold text-white text-sm">{cam.id}</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30">
                              Zone Active
                            </span>
                          </div>
                          <div className="font-semibold text-slate-200 text-xs">{cam.name}</div>
                          <div className="text-[11px] text-slate-400 mt-1">{cam.zone}</div>
                          <div className="mt-3 pt-2 border-t border-[#162347] flex items-center justify-between text-xs font-mono text-slate-400">
                            <span>Detected / Occupancy:</span>
                            <span className="text-emerald-400 font-bold">{cam.personCount ?? cam.occupancy ?? 0} Persons</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* TAB CONTENT: PEOPLE & ACCESS (Biometrics, ArcFace, RFID) */}
            {(navTab === 'access' || navTab === 'live') && (
              <div className="bg-[#0b132b] rounded-2xl border border-[#162347] p-5 shadow-xl flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#162347]">
                  <div className="flex items-center gap-2.5">
                    <CreditCard className="w-5 h-5 text-blue-400" />
                    <div>
                      <h2 className="text-base font-bold text-white tracking-wide">
                        Access Control &amp; Biometric Correlation
                      </h2>
                      <p className="text-xs text-slate-400">
                        Real-time RFID transaction matched against ArcFace facial embeddings (InsightFace)
                      </p>
                    </div>
                  </div>
                </div>

                {/* Telemetry Row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Credential Profile */}
                  <div className="bg-[#0e1838] rounded-xl border border-[#162347] p-4 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
                        <span>CREDENTIAL ID</span>
                        <span className="text-blue-400 font-semibold">RFID SCAN</span>
                      </div>
                      <div className="text-sm font-bold text-white">
                        {currentAccess.badgeId}: {currentAccess.employeeName}
                      </div>
                      <div className="text-xs text-slate-400 mt-1">{currentAccess.department}</div>
                    </div>
                    <div className="mt-3 pt-2 border-t border-[#162347] text-[11px] text-slate-400 flex items-center justify-between">
                      <span>Reader:</span>
                      <span className="font-mono text-slate-200">{currentAccess.readerId}</span>
                    </div>
                  </div>

                  {/* ArcFace Match Score */}
                  <div className="bg-[#0e1838] rounded-xl border border-[#162347] p-4 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
                        <span>ARCFACE MATCH SCORE</span>
                        <span className="font-mono text-slate-300">512-D COSINE</span>
                      </div>
                      <div className="flex items-baseline gap-2">
                        <span
                          className={`text-2xl font-mono font-extrabold ${
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
                          (Req: &ge; 50.0%)
                        </span>
                      </div>
                      <div className="w-full bg-[#162347] h-2 rounded-full overflow-hidden mt-3">
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
                    <div className="mt-3 pt-2 border-t border-[#162347] text-[11px] text-slate-400 flex items-center justify-between">
                      <span>Threshold:</span>
                      <span className="text-emerald-400 font-medium">50.0% Minimum</span>
                    </div>
                  </div>

                  {/* Security Verdict */}
                  <div className="bg-[#0e1838] rounded-xl border border-[#162347] p-4 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
                        <span>SECURITY VERDICT</span>
                        <span className="font-mono text-slate-400">TURNSTILE GATE</span>
                      </div>
                      <div className="mt-1">
                        {currentAccess.verdict === 'AUTHORIZED' && (
                          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold font-mono">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            AUTHORIZED
                          </div>
                        )}
                        {currentAccess.verdict === 'MISMATCH' && (
                          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold font-mono">
                            <AlertTriangle className="w-4 h-4 text-amber-400" />
                            MISMATCH
                          </div>
                        )}
                        {currentAccess.verdict === 'TAILGATING' && (
                          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-bold font-mono">
                            <XCircle className="w-4 h-4 text-red-400" />
                            TAILGATING
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="mt-3 pt-2 border-t border-[#162347] text-[11px] text-slate-400 flex items-center justify-between">
                      <span>Occupancy Detected:</span>
                      <span className="font-bold text-slate-200">{currentAccess.occupancyDetected} Person(s)</span>
                    </div>
                  </div>
                </div>

                {/* Live Trigger Controls */}
                <div className="bg-[#0e1838] rounded-xl border border-[#162347] p-4">
                  {verifyFeedback && (
                    <div
                      className={`mb-3 p-2.5 rounded-lg border text-xs font-mono flex items-center gap-2 ${
                        verifyFeedback.type === 'success'
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                          : verifyFeedback.type === 'warning'
                          ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                          : 'bg-red-500/10 border-red-500/30 text-red-300'
                      }`}
                    >
                      {verifyFeedback.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
                      {verifyFeedback.type === 'warning' && <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />}
                      {verifyFeedback.type === 'error' && <XCircle className="w-4 h-4 text-red-400 shrink-0" />}
                      <span>{verifyFeedback.message}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
                    <div className="sm:col-span-5">
                      <label className="block text-[11px] text-slate-400 font-medium mb-1">
                        Employee ID to Scan ({enrolledUsers.length} Enrolled)
                      </label>
                      <input
                        type="text"
                        list="enrolled-employees-list"
                        value={verifyEmployeeId}
                        onChange={(e) => setVerifyEmployeeId(e.target.value)}
                        placeholder="e.g. EMP-1001 or AUTO"
                        disabled={isVerifying}
                        className="w-full bg-[#0b132b] border border-[#162347] focus:border-blue-500 rounded-xl px-3 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none"
                      />
                      <datalist id="enrolled-employees-list">
                        <option value="AUTO">AUTO (1:N Biometric Retrieval)</option>
                        {enrolledUsers.map((u) => (
                          <option key={u.employee_id} value={u.employee_id}>
                            {u.name} ({u.employee_id}) - {u.roll}
                          </option>
                        ))}
                      </datalist>
                    </div>

                    <div className="sm:col-span-4">
                      <label className="block text-[11px] text-slate-400 font-medium mb-1">
                        Target Camera Feed
                      </label>
                      <select
                        value={verifyDeviceId}
                        onChange={(e) => setVerifyDeviceId(Number(e.target.value))}
                        disabled={isVerifying}
                        className="w-full bg-[#0b132b] border border-[#162347] focus:border-blue-500 rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                      >
                        <option value={0}>Device 0 — Mobile (Iriun)</option>
                        <option value={1}>Device 1 — Laptop Webcam</option>
                      </select>
                    </div>

                    <div className="sm:col-span-3">
                      <Button
                        onClick={handleLiveVerification}
                        disabled={isVerifying}
                        className="w-full flex items-center justify-center gap-2 h-9 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-900/30 disabled:opacity-50"
                      >
                        {isVerifying ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            <span>Verifying...</span>
                          </>
                        ) : (
                          <>
                            <ShieldCheck className="w-3.5 h-3.5" />
                            <span>Scan &amp; Verify</span>
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT: INCIDENTS */}
            {navTab === 'incidents' && (
              <div className="flex-1 bg-[#0b132b] rounded-2xl border border-[#162347] p-5 shadow-xl">
                <IncidentQueue
                  alerts={alerts}
                  unacknowledgedCount={unacknowledgedCount}
                  alertFilter={alertFilter}
                  onFilterChange={setAlertFilter}
                  onToggleAcknowledge={toggleAcknowledge}
                  onResetAlerts={handleResetAlerts}
                  onOpenEvidence={handleOpenEvidence}
                  onOpenEvidenceGallery={handleOpenEvidenceGallery}
                />
              </div>
            )}
          </main>
        )}
      </div>

      {/* =====================================================================
          3. RIGHT SIDEBAR (RECENT ALERTS PANEL)
          ===================================================================== */}
      <RecentAlertsPanel
        alerts={alerts}
        unacknowledgedCount={unacknowledgedCount}
        onViewAllClick={() => setNavTab('incidents')}
        onAlertClick={(alert) => toggleAcknowledge(alert.id)}
        onResetAlerts={handleResetAlerts}
        onOpenEvidence={handleOpenEvidence}
        onOpenEvidenceGallery={handleOpenEvidenceGallery}
      />

      {/* =====================================================================
          SOURCE CONFIGURATION MODAL (PER-TILE ASSIGNMENT)
          ===================================================================== */}
      {selectedCamForConfig && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b132b] border border-[#162347] rounded-2xl max-w-md w-full p-5 shadow-2xl flex flex-col gap-4 font-sans animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-[#162347]">
              <div className="flex items-center gap-2">
                <Camera className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-base text-white">
                  Configure Source // {selectedCamForConfig.id}
                </h3>
              </div>
              <Button
                onClick={() => setSelectedCamForConfig(null)}
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <div className="text-xs text-slate-400">
              Select stream ingestion source for <strong className="text-white">{selectedCamForConfig.name}</strong> ({selectedCamForConfig.zone}):
            </div>

            {/* Source Options */}
            <div className="space-y-3">
              {/* Hardware Webcam */}
              <div
                className={`p-3.5 rounded-xl border transition-colors ${
                  selectedCamForConfig.sourceType === 'WEBCAM'
                    ? 'bg-blue-600/10 border-blue-500/50'
                    : 'bg-[#0e1838] border-[#162347]'
                }`}
              >
                <div className="flex items-start gap-3">
                  <Camera className="w-5 h-5 text-blue-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white">
                        Local Hardware Webcam (DirectShow)
                      </span>
                      <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/30">
                        DEV {modalDeviceId}
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 mt-2.5">
                      <Button
                        type="button"
                        onClick={() => setModalDeviceId(0)}
                        variant={modalDeviceId === 0 ? 'default' : 'secondary'}
                        className={`h-auto px-2 py-1.5 rounded-lg text-left text-xs flex flex-col items-start ${
                          modalDeviceId === 0
                            ? 'bg-blue-600 hover:bg-blue-500 text-white font-bold'
                            : 'bg-[#0b132b] hover:bg-[#111c3d] text-slate-300 border border-[#162347]'
                        }`}
                      >
                        <div className="font-bold">Dev 0</div>
                        <div className="text-[10px] text-slate-400">Iriun / Mobile</div>
                      </Button>

                      <Button
                        type="button"
                        onClick={() => setModalDeviceId(1)}
                        variant={modalDeviceId === 1 ? 'default' : 'secondary'}
                        className={`h-auto px-2 py-1.5 rounded-lg text-left text-xs flex flex-col items-start ${
                          modalDeviceId === 1
                            ? 'bg-blue-600 hover:bg-blue-500 text-white font-bold'
                            : 'bg-[#0b132b] hover:bg-[#111c3d] text-slate-300 border border-[#162347]'
                        }`}
                      >
                        <div className="font-bold">Dev 1</div>
                        <div className="text-[10px] text-slate-400">Webcam</div>
                      </Button>

                      <Button
                        type="button"
                        onClick={() => setModalDeviceId(2)}
                        variant={modalDeviceId === 2 ? 'default' : 'secondary'}
                        className={`h-auto px-2 py-1.5 rounded-lg text-left text-xs flex flex-col items-start ${
                          modalDeviceId === 2
                            ? 'bg-blue-600 hover:bg-blue-500 text-white font-bold'
                            : 'bg-[#0b132b] hover:bg-[#111c3d] text-slate-300 border border-[#162347]'
                        }`}
                      >
                        <div className="font-bold">Dev 2</div>
                        <div className="text-[10px] text-slate-400">Aux Cam</div>
                      </Button>
                    </div>

                    <Button
                      type="button"
                      onClick={() => {
                        const targetId = selectedCamForConfig.id;
                        setCameras((prev) =>
                          prev.map((c) =>
                            c.id === targetId
                              ? {
                                  ...c,
                                  sourceType: 'WEBCAM',
                                  deviceId: modalDeviceId,
                                  streamUrl: `http://127.0.0.1:8000/api/webcam-stream/${modalDeviceId}`,
                                  isOnline: true,
                                }
                              : c
                          )
                        );
                        setSelectedCamForConfig(null);
                      }}
                      className="mt-3 w-full h-8 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg text-xs"
                    >
                      Apply Device {modalDeviceId}
                    </Button>
                  </div>
                </div>
              </div>

              {/* Backend Test Video Loop */}
              <div
                onClick={() => {
                  const targetId = selectedCamForConfig.id;
                  setCameras((prev) =>
                    prev.map((c) =>
                      c.id === targetId
                        ? {
                            ...c,
                            sourceType: 'BACKEND_LOOP',
                            streamUrl: 'http://127.0.0.1:8000/api/video-stream',
                            isOnline: true,
                          }
                        : c
                    )
                  );
                  setSelectedCamForConfig(null);
                }}
                className="p-3.5 bg-[#0e1838] hover:bg-[#162347] border border-[#162347] rounded-xl cursor-pointer transition-colors"
              >
                <div className="font-bold text-xs text-white">Default Video Test Loop</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Continuous CCTV simulation loop (/api/video-stream)</div>
              </div>

              {/* Upload Custom Sample Video File */}
              <div className="p-3.5 bg-[#0e1838] border border-[#162347] rounded-xl">
                <div className="flex items-start gap-3">
                  <Upload className="w-5 h-5 text-blue-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-white">
                        Upload Custom Sample Video
                      </span>
                      <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/30">
                        MP4 / AVI / MOV
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5 mb-2.5">
                      Upload local footage to feed into this camera node for live AI detection &amp; testing.
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="video/mp4,video/avi,video/mkv,video/quicktime,video/*"
                      onChange={handleFileUpload}
                      disabled={uploadLoading}
                      className="block w-full text-xs text-slate-400 file:mr-2.5 file:py-1.5 file:px-3 file:rounded-lg file:border file:border-[#162347] file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 file:cursor-pointer cursor-pointer"
                    />
                    {uploadLoading && (
                      <div className="text-xs font-mono text-blue-400 mt-2 flex items-center gap-1.5">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Uploading and initializing stream...</span>
                      </div>
                    )}
                    {uploadMessage && (
                      <div className="text-xs font-mono text-emerald-400 mt-2 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>{uploadMessage}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Standby Idle Mode */}
              <div
                onClick={() => {
                  const targetId = selectedCamForConfig.id;
                  setCameras((prev) =>
                    prev.map((c) =>
                      c.id === targetId
                        ? {
                            ...c,
                            sourceType: 'STANDBY',
                            streamUrl: '',
                            isOnline: false,
                          }
                        : c
                    )
                  );
                  setSelectedCamForConfig(null);
                }}
                className="p-3.5 bg-[#0e1838] hover:bg-[#162347] border border-[#162347] rounded-xl cursor-pointer transition-colors"
              >
                <div className="font-bold text-xs text-slate-300">Unassign / Set to Standby</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Disconnect feed and mark channel as idle</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          SETTINGS & BIOMETRIC ENROLLMENT MODALS
          ===================================================================== */}
      <EnrollModal
        showEnrollModal={showEnrollModal}
        setShowEnrollModal={setShowEnrollModal}
        enrollDeviceId={enrollDeviceId}
        setEnrollDeviceId={setEnrollDeviceId}
        enrollName={enrollName}
        setEnrollName={setEnrollName}
        enrollRoll={enrollRoll}
        setEnrollRoll={setEnrollRoll}
        enrollId={enrollId}
        setEnrollId={setEnrollId}
        enrollLoading={enrollLoading}
        enrollFeedback={enrollFeedback}
        setEnrollFeedback={setEnrollFeedback}
        handleEnrollSubmit={handleEnrollSubmit}
      />

      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        onOpenEnroll={() => {
          setShowEnrollModal(true);
          setEnrollFeedback(null);
        }}
        onFortressAuthorized={(token, user, score, targetDate) => {
          setFortressSession({ token, username: user, trustScore: score });
          if (targetDate) setAuditTargetDate(targetDate);
          setActiveView('AUDIT_LOGS');
          setShowSettingsModal(false);
        }}
      />

      {/* Forensic Evidence Snapshot Modal & Gallery */}
      <EvidenceModal
        isOpen={isEvidenceModalOpen}
        onClose={() => setIsEvidenceModalOpen(false)}
        activeAlert={selectedEvidenceAlert}
        initialTab={evidenceModalTab}
        backendUrl="http://127.0.0.1:8000"
      />
    </div>
  );
};

export default App;
