import React, { useState, useEffect } from 'react';
import {
  Settings,
  X,
  UserPlus,
  FileSpreadsheet,
  Calendar,
  Shield,
  ShieldCheck,
  Loader2,
} from 'lucide-react';
import { FortressAuditModal } from './FortressAuditModal';

export interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenEnroll: () => void;
  onFortressAuthorized?: (sessionToken: string, username: string, trustScore: number) => void;
  backendUrl?: string;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onOpenEnroll,
  onFortressAuthorized,
  backendUrl = 'http://127.0.0.1:8000',
}) => {
  // Today's date in local YYYY-MM-DD format
  const getTodayDateStr = () => {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const [selectedDate, setSelectedDate] = useState<string>(getTodayDateStr());
  const [showFortressModal, setShowFortressModal] = useState<boolean>(false);
  const [logCount, setLogCount] = useState<number | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [isLoadingLogs, setIsLoadingLogs] = useState<boolean>(false);

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

  // Query audit logs metadata for the selected date whenever date changes or modal opens
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    const fetchLogInfo = async () => {
      setIsLoadingLogs(true);
      try {
        const res = await fetch(`${backendUrl}/api/audit-logs?date=${encodeURIComponent(selectedDate)}`);
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setLogCount(data.count ?? 0);
            if (Array.isArray(data.available_dates)) {
              setAvailableDates(data.available_dates);
            }
          }
        } else {
          if (isMounted) setLogCount(0);
        }
      } catch (err) {
        console.warn('Failed to query audit logs:', err);
        if (isMounted) setLogCount(0);
      } finally {
        if (isMounted) setIsLoadingLogs(false);
      }
    };

    fetchLogInfo();
    return () => {
      isMounted = false;
    };
  }, [isOpen, selectedDate, backendUrl]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl max-w-2xl w-full overflow-hidden text-slate-100 flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <Settings className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold tracking-wide uppercase font-mono text-slate-100">
                System Settings & Operations
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                UATU Core Configuration, Biometric Enrollment & Audit Management
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close Settings"
            aria-label="Close Settings"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body: 2 Primary Options */}
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Option 1: Biometric Personnel Enrollment */}
            <div className="flex flex-col justify-between p-5 rounded-lg bg-slate-950/70 border border-slate-800 hover:border-emerald-500/40 transition-all group">
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-100 font-mono text-sm">
                    Biometric Enrollment
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                    Register personnel faces using live webcam or connected CCTV feed. Computes 512-D ArcFace biometric embeddings with badge assignment.
                  </p>
                </div>
              </div>

              <div className="pt-5 mt-4 border-t border-slate-800/80">
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    onOpenEnroll();
                  }}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-slate-950 font-semibold text-xs uppercase tracking-wider font-mono transition-all shadow-lg shadow-emerald-950/40"
                >
                  <UserPlus className="w-4 h-4" />
                  <span>Launch Enrollment</span>
                </button>
              </div>
            </div>

            {/* Option 2: Audit Log CSV Export */}
            <div className="flex flex-col justify-between p-5 rounded-lg bg-slate-950/70 border border-slate-800 hover:border-cyan-500/40 transition-all group">
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 group-hover:scale-105 transition-transform">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-100 font-mono text-sm">
                    Audit Log Export
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                    Export date-wise chronological records of camera alerts, face mismatches, operator acknowledgments, and AI voice commands to CSV.
                  </p>
                </div>
              </div>

              {/* Date Selection Controls */}
              <div className="pt-4 mt-2 space-y-3 border-t border-slate-800/80">
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Select Audit Date:</span>
                  </label>
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    max={getTodayDateStr()}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
                  />
                </div>

                {/* Telemetry Record Counter */}
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 px-1">
                  <span>Logged Records:</span>
                  {isLoadingLogs ? (
                    <span className="flex items-center gap-1 text-slate-500">
                      <Loader2 className="w-3 h-3 animate-spin" /> Fetching...
                    </span>
                  ) : (
                    <span className="text-cyan-400 font-semibold">
                      {logCount !== null ? `${logCount} Events` : 'Ready'}
                    </span>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => setShowFortressModal(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 active:bg-amber-600 text-slate-950 font-semibold text-xs uppercase tracking-wider font-mono transition-all shadow-lg shadow-amber-950/40"
                  title="Verify SuperAdmin Credentials & Contextual OTP to Export Audit Logs"
                >
                  <Shield className="w-4 h-4" />
                  <span>Fortress Preview & Export</span>
                </button>
              </div>
            </div>
          </div>

          {/* Available Dates Quick-Pills */}
          {availableDates.length > 0 && (
            <div className="p-3 rounded-lg bg-slate-950/40 border border-slate-800/60 flex items-center gap-2 overflow-x-auto text-[11px] font-mono text-slate-400">
              <span className="whitespace-nowrap text-slate-500">Available Dates:</span>
              <div className="flex items-center gap-1.5">
                {availableDates.slice(0, 5).map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setSelectedDate(d)}
                    className={`px-2 py-0.5 rounded border transition-colors ${
                      selectedDate === d
                        ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 font-semibold'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
            <span>Audit integrity: ISO-27001 compliant immutable event logging</span>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            Close
          </button>
        </div>
      </div>

      {/* Fortress Zero-Trust Verification Modal */}
      <FortressAuditModal
        isOpen={showFortressModal}
        onClose={() => setShowFortressModal(false)}
        onAuthorized={(sessionToken, username, trustScore) => {
          setShowFortressModal(false);
          onClose();
          onFortressAuthorized?.(sessionToken, username, trustScore);
        }}
        targetDate={selectedDate}
        backendUrl={backendUrl}
      />
    </div>
  );
};

export default SettingsModal;
