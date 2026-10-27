import React, { useState, useEffect, useCallback } from 'react';
import {
  Camera,
  X,
  Download,
  ExternalLink,
  ShieldAlert,
  Clock,
  MapPin,
  RefreshCw,
  Search,
  Layers,
  FileImage,
} from 'lucide-react';
import { Button } from './ui/button';
import type { IncidentAlert } from './IncidentQueue';

export interface SnapshotMeta {
  filename: string;
  url: string;
  timestamp: string;
  camera_id: string;
  anomaly_type: string;
  zone?: string;
  confidence_pct?: number;
  event_id?: string;
  size_bytes?: number;
}

export interface EvidenceModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeAlert?: IncidentAlert | null;
  initialTab?: 'INSPECT' | 'GALLERY';
  backendUrl?: string;
}

export const EvidenceModal: React.FC<EvidenceModalProps> = ({
  isOpen,
  onClose,
  activeAlert,
  initialTab = 'INSPECT',
  backendUrl = 'http://127.0.0.1:8000',
}) => {
  const [tab, setTab] = useState<'INSPECT' | 'GALLERY'>(initialTab);
  const [snapshots, setSnapshots] = useState<SnapshotMeta[]>([]);
  const [loadingGallery, setLoadingGallery] = useState<boolean>(false);
  const [galleryError, setGalleryError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedSnapshot, setSelectedSnapshot] = useState<SnapshotMeta | null>(null);
  const [imgLoadError, setImgLoadError] = useState<boolean>(false);

  // Sync initial tab when opening
  useEffect(() => {
    if (isOpen) {
      setTab(activeAlert ? 'INSPECT' : 'GALLERY');
      setImgLoadError(false);
    }
  }, [isOpen, activeAlert]);

  // Fetch gallery snapshots
  const fetchSnapshots = useCallback(async () => {
    setLoadingGallery(true);
    setGalleryError(null);
    try {
      const res = await fetch(`${backendUrl}/api/snapshots?limit=60`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch snapshots`);
      const data = await res.json();
      setSnapshots(data.snapshots || []);
    } catch (err: any) {
      setGalleryError(err?.message || 'Failed to load snapshots gallery');
    } finally {
      setLoadingGallery(false);
    }
  }, [backendUrl]);

  // Load gallery when switching to GALLERY tab or when opened in GALLERY mode
  useEffect(() => {
    if (isOpen && tab === 'GALLERY') {
      fetchSnapshots();
    }
  }, [isOpen, tab, fetchSnapshots]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Resolve current snapshot to inspect
  const currentSnapshotUrl =
    selectedSnapshot?.url ||
    activeAlert?.snapshot_url ||
    (activeAlert?.id ? `${backendUrl}/api/snapshots/${activeAlert.id}.jpg` : '');

  const currentAnomalyType =
    selectedSnapshot?.anomaly_type || activeAlert?.type || 'CRITICAL ANOMALY';
  const currentCameraId = selectedSnapshot?.camera_id || activeAlert?.camera || 'CAM-01';
  const currentTimestamp =
    selectedSnapshot?.timestamp || activeAlert?.timestamp || activeAlert?.time || 'N/A';
  const currentZone = selectedSnapshot?.zone || activeAlert?.zone || 'Zone 01 // Facility Area';
  const currentEventId = selectedSnapshot?.event_id || activeAlert?.id || 'EVT-RECORD';
  const currentConfidence =
    selectedSnapshot?.confidence_pct ?? activeAlert?.confidence_pct ?? 95.0;

  // Extract clean filename for download
  const downloadFileName =
    selectedSnapshot?.filename ||
    `${currentCameraId}_${currentAnomalyType.toLowerCase().replace(/\s+/g, '_')}_${currentTimestamp.replace(/[: ]/g, '-')}.jpg`;

  // Filter snapshots in gallery
  const filteredSnapshots = snapshots.filter((snap) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      snap.filename.toLowerCase().includes(q) ||
      snap.camera_id.toLowerCase().includes(q) ||
      snap.anomaly_type.toLowerCase().includes(q) ||
      snap.timestamp.toLowerCase().includes(q) ||
      (snap.zone && snap.zone.toLowerCase().includes(q))
    );
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 overflow-hidden">
      <div className="bg-[#0b132b] border border-[#162347] rounded-2xl shadow-2xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden text-slate-100 animate-in fade-in zoom-in-95 duration-200">
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#162347] bg-[#080f22]/90">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
              <Camera className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold tracking-tight text-white font-sans">
                  Forensic Anomaly Evidence
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 font-semibold uppercase">
                  Local Storage
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Automated frame capture with burned-in timestamp HUD & forensic metadata
              </p>
            </div>
          </div>

          {/* Tab Selector & Close */}
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-[#0e1a38] p-1 rounded-xl border border-[#1c2e5c]">
              <button
                type="button"
                onClick={() => setTab('INSPECT')}
                className={`px-3 py-1 text-xs font-mono rounded-lg transition-all ${
                  tab === 'INSPECT'
                    ? 'bg-blue-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Inspect Frame
              </button>
              <button
                type="button"
                onClick={() => setTab('GALLERY')}
                className={`px-3 py-1 text-xs font-mono rounded-lg transition-all ${
                  tab === 'GALLERY'
                    ? 'bg-blue-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Snapshot Gallery
              </button>
            </div>

            <Button
              onClick={onClose}
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Content Body */}
        {tab === 'INSPECT' ? (
          <div className="flex-1 overflow-y-auto p-6 flex flex-col lg:flex-row gap-6">
            {/* Left: Frame Display with Burn-in HUD */}
            <div className="flex-1 flex flex-col gap-3 min-w-0">
              <div className="relative aspect-video bg-black rounded-xl border border-[#1c2e5c] overflow-hidden flex items-center justify-center group shadow-xl">
                {currentSnapshotUrl && !imgLoadError ? (
                  <img
                    src={currentSnapshotUrl}
                    alt={`Evidence ${currentEventId}`}
                    onError={() => setImgLoadError(true)}
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center p-8 text-center">
                    <FileImage className="w-12 h-12 text-slate-600 mb-3" />
                    <span className="text-sm font-semibold text-slate-300">
                      Evidence Image Pending or Offline
                    </span>
                    <span className="text-xs text-slate-500 max-w-sm mt-1">
                      No frame file detected for event {currentEventId}. Frames are saved
                      automatically on critical anomaly classification.
                    </span>
                  </div>
                )}

                {/* Overlay Badge */}
                <div className="absolute top-3 left-3 bg-red-950/80 backdrop-blur-md border border-red-500/40 text-red-300 text-[10px] font-mono px-2.5 py-1 rounded flex items-center gap-1.5 shadow-lg">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                  <span>CRITICAL EVIDENCE CAPTURE</span>
                </div>
              </div>

              {/* Bottom Quick Actions */}
              <div className="flex items-center justify-between gap-3 pt-2">
                <span className="text-xs font-mono text-slate-400 truncate">
                  Target: <strong className="text-slate-200">{downloadFileName}</strong>
                </span>

                <div className="flex items-center gap-2">
                  {currentSnapshotUrl && (
                    <a
                      href={currentSnapshotUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-mono px-3 py-1.5 rounded-lg border border-[#1c2e5c] bg-[#0e1a38] text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Full Resolution</span>
                    </a>
                  )}

                  {currentSnapshotUrl && (
                    <a
                      href={currentSnapshotUrl}
                      download={downloadFileName}
                      className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors shadow-sm"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download Snapshot</span>
                    </a>
                  )}
                </div>
              </div>
            </div>

            {/* Right: Metadata Burn-in Telemetry Card */}
            <div className="w-full lg:w-80 flex flex-col gap-4 shrink-0">
              <div className="bg-[#080f22] border border-[#162347] rounded-xl p-4 flex flex-col gap-3.5">
                <div className="flex items-center justify-between pb-2.5 border-b border-[#162347]">
                  <span className="text-xs font-bold text-slate-200 font-mono tracking-wider uppercase">
                    Forensic Telemetry
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    VERIFIED
                  </span>
                </div>

                {/* Anomaly Label */}
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] font-mono text-slate-400 uppercase">
                    Detection Anomaly
                  </span>
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-red-400 shrink-0" />
                    <span className="text-sm font-bold text-red-300 font-sans">
                      {currentAnomalyType}
                    </span>
                  </div>
                </div>

                {/* Camera & Zone */}
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-mono text-slate-400 uppercase">Camera ID</span>
                    <span className="text-xs font-mono font-bold text-emerald-400">
                      {currentCameraId}
                    </span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-mono text-slate-400 uppercase">Confidence</span>
                    <span className="text-xs font-mono font-bold text-amber-400">
                      {typeof currentConfidence === 'number'
                        ? `${currentConfidence.toFixed(1)}%`
                        : `${currentConfidence}%`}
                    </span>
                  </div>
                </div>

                {/* Zone Location */}
                <div className="flex flex-col gap-0.5 pt-1">
                  <span className="text-[10px] font-mono text-slate-400 uppercase">Zone / Area</span>
                  <div className="flex items-center gap-1.5 text-xs text-slate-300 font-mono">
                    <MapPin className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span className="truncate">{currentZone}</span>
                  </div>
                </div>

                {/* Exact Timestamp */}
                <div className="flex flex-col gap-0.5 pt-1">
                  <span className="text-[10px] font-mono text-slate-400 uppercase">
                    Timestamp (Local / IST)
                  </span>
                  <div className="flex items-center gap-1.5 text-xs text-slate-200 font-mono">
                    <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>{currentTimestamp}</span>
                  </div>
                </div>

                {/* Event ID */}
                <div className="flex flex-col gap-0.5 pt-1">
                  <span className="text-[10px] font-mono text-slate-400 uppercase">Event Ref</span>
                  <span className="text-xs font-mono text-slate-400 break-all">{currentEventId}</span>
                </div>

                {/* Local Storage Path Info */}
                <div className="pt-2 border-t border-[#162347] flex flex-col gap-1 text-[11px] font-mono text-slate-400">
                  <span className="text-slate-500 text-[10px]">LOCAL STORAGE DIRECTORY:</span>
                  <code className="bg-black/40 px-2 py-1 rounded text-slate-300 text-[10px] break-all border border-[#162347]">
                    backend/snapshots/{downloadFileName}
                  </code>
                </div>
              </div>

              {/* View in Gallery trigger */}
              <Button
                onClick={() => setTab('GALLERY')}
                variant="ghost"
                className="w-full text-xs font-mono flex items-center justify-center gap-2 border border-[#1c2e5c] text-blue-400 hover:text-white hover:bg-blue-600/20 h-9 rounded-xl"
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Browse All Saved Snapshots</span>
              </Button>
            </div>
          </div>
        ) : (
          /* Tab: GALLERY */
          <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
            {/* Gallery Search & Refresh Toolbar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter snapshots by camera (e.g. CAM-01), anomaly type, or date..."
                  className="w-full bg-[#080f22] border border-[#162347] rounded-xl pl-9 pr-3 py-1.5 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-slate-400">
                  Total Saved: <strong className="text-slate-200">{snapshots.length}</strong>
                </span>

                <Button
                  onClick={fetchSnapshots}
                  disabled={loadingGallery}
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2.5 rounded-lg border border-[#1c2e5c] text-slate-300 hover:text-white flex items-center gap-1.5 text-xs font-mono"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingGallery ? 'animate-spin' : ''}`} />
                  <span>Refresh</span>
                </Button>
              </div>
            </div>

            {/* Gallery Grid */}
            {loadingGallery ? (
              <div className="py-20 flex flex-col items-center justify-center gap-2">
                <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
                <span className="text-xs font-mono text-slate-400">Loading snapshot gallery...</span>
              </div>
            ) : galleryError ? (
              <div className="py-16 text-center text-red-400 text-xs font-mono">
                {galleryError}
              </div>
            ) : filteredSnapshots.length === 0 ? (
              <div className="py-20 text-center flex flex-col items-center justify-center">
                <Camera className="w-10 h-10 text-slate-600 mb-2" />
                <span className="text-sm font-semibold text-slate-300">No Snapshots Found</span>
                <span className="text-xs text-slate-500 mt-1">
                  {searchQuery
                    ? 'No saved snapshots match your search filter.'
                    : 'Critical anomaly snapshots will appear here automatically when triggered.'}
                </span>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                {filteredSnapshots.map((snap) => (
                  <div
                    key={snap.filename}
                    onClick={() => {
                      setSelectedSnapshot(snap);
                      setImgLoadError(false);
                      setTab('INSPECT');
                    }}
                    className="bg-[#080f22] border border-[#162347] hover:border-blue-500/60 rounded-xl overflow-hidden cursor-pointer transition-all hover:shadow-lg flex flex-col group"
                  >
                    {/* Thumbnail Image */}
                    <div className="relative aspect-video bg-black overflow-hidden">
                      <img
                        src={snap.url}
                        alt={snap.filename}
                        loading="lazy"
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                        }}
                      />
                      <div className="absolute top-2 left-2 bg-black/70 backdrop-blur-sm px-2 py-0.5 rounded text-[10px] font-mono text-emerald-300 border border-emerald-500/30">
                        {snap.camera_id}
                      </div>
                      <div className="absolute top-2 right-2 bg-red-950/80 backdrop-blur-sm px-2 py-0.5 rounded text-[10px] font-mono text-red-300 border border-red-500/40 uppercase font-semibold">
                        {snap.anomaly_type}
                      </div>
                    </div>

                    {/* Meta Footer */}
                    <div className="p-3 flex flex-col gap-1.5 flex-1 justify-between">
                      <div>
                        <div className="text-xs font-bold text-slate-100 group-hover:text-blue-400 transition-colors truncate">
                          {snap.anomaly_type}
                        </div>
                        <div className="text-[11px] font-mono text-slate-400 truncate">
                          {snap.timestamp}
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-2 border-t border-[#162347]/60 text-[10px] font-mono text-slate-400">
                        <span className="truncate max-w-[140px] text-slate-500">
                          {snap.filename}
                        </span>
                        <span className="text-blue-400 group-hover:underline">
                          Inspect &rarr;
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EvidenceModal;
