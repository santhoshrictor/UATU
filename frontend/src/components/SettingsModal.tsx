import React, { useState, useEffect } from 'react';
import {
  Settings,
  X,
  UserPlus,
  FileSpreadsheet,
  Shield,
  ShieldCheck,
  Lock,
} from 'lucide-react';
import { FortressAuditModal } from './FortressAuditModal';
import { Button } from './ui/button';

export interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenEnroll: () => void;
  onFortressAuthorized?: (sessionToken: string, username: string, trustScore: number, targetDate: string) => void;
  backendUrl?: string;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onOpenEnroll,
  onFortressAuthorized,
  backendUrl = 'http://127.0.0.1:8000',
}) => {
  const [showFortressModal, setShowFortressModal] = useState<boolean>(false);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !showFortressModal) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, showFortressModal]);

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
          <Button
            onClick={onClose}
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-slate-400 hover:text-white"
            title="Close Settings"
            aria-label="Close Settings"
          >
            <X className="w-5 h-5" />
          </Button>
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
                <Button
                  type="button"
                  onClick={() => {
                    onClose();
                    onOpenEnroll();
                  }}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs tracking-wider font-mono shadow-lg shadow-emerald-950/40"
                >
                  <UserPlus className="w-4 h-4" />
                  <span>Launch Enrollment</span>
                </Button>
              </div>
            </div>

            {/* Option 2: Audit Log Telemetry & Export */}
            <div className="flex flex-col justify-between p-5 rounded-lg bg-slate-950/70 border border-slate-800 hover:border-amber-500/40 transition-all group">
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 group-hover:scale-105 transition-transform">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-100 font-mono text-sm">
                      Audit Log Export
                    </h3>
                    <span className="flex items-center gap-1 text-[10px] font-mono text-amber-400 bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-800/40">
                      <Lock className="w-3 h-3" />
                      Zero-Trust
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                    Securely preview and export date-wise chronological records of camera alerts, face mismatches, operator actions, and AI voice query telemetry.
                  </p>
                </div>
              </div>

              {/* Fortress Entry Action */}
              <div className="pt-5 mt-4 space-y-2 border-t border-slate-800/80">
                <div className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                  <span>Requires SuperAdmin OTP &amp; Hardware Fingerprint</span>
                </div>

                <Button
                  type="button"
                  onClick={() => setShowFortressModal(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-xs tracking-wider font-mono shadow-lg shadow-amber-950/40"
                  title="Verify SuperAdmin Credentials & Contextual OTP to Export Audit Logs"
                >
                  <Shield className="w-4 h-4" />
                  <span>Fortress Preview &amp; Export</span>
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
            <span>Audit integrity: ISO-27001 compliant immutable event logging</span>
          </div>
          <Button
            onClick={onClose}
            variant="secondary"
            size="sm"
            className="h-7 px-3 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
          >
            Close
          </Button>
        </div>
      </div>

      {/* Fortress Zero-Trust Verification Modal */}
      <FortressAuditModal
        isOpen={showFortressModal}
        onClose={() => setShowFortressModal(false)}
        onAuthorized={(sessionToken, username, trustScore, targetDate) => {
          setShowFortressModal(false);
          onClose();
          onFortressAuthorized?.(sessionToken, username, trustScore, targetDate);
        }}
        backendUrl={backendUrl}
      />
    </div>
  );
};

export default SettingsModal;
