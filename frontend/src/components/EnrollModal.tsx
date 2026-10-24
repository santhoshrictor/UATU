import React, { useState, useEffect } from 'react';
import { Camera, RefreshCw, UserCheck, X, CheckCircle2, XCircle } from 'lucide-react';

export interface EnrollModalProps {
  showEnrollModal: boolean;
  setShowEnrollModal: (show: boolean) => void;
  enrollDeviceId: number;
  setEnrollDeviceId: (id: number) => void;
  enrollName: string;
  setEnrollName: (name: string) => void;
  enrollRoll: string;
  setEnrollRoll: (roll: string) => void;
  enrollId: string;
  setEnrollId: (id: string) => void;
  enrollLoading: boolean;
  enrollFeedback: { type: 'success' | 'error'; message: string } | null;
  setEnrollFeedback: (feedback: { type: 'success' | 'error'; message: string } | null) => void;
  handleEnrollSubmit: (e?: React.FormEvent) => Promise<void>;
}

export const EnrollModal: React.FC<EnrollModalProps> = ({
  showEnrollModal,
  setShowEnrollModal,
  enrollDeviceId,
  setEnrollDeviceId,
  enrollName,
  setEnrollName,
  enrollRoll,
  setEnrollRoll,
  enrollId,
  setEnrollId,
  enrollLoading,
  enrollFeedback,
  setEnrollFeedback,
  handleEnrollSubmit,
}) => {
  const [isFaceAligned, setIsFaceAligned] = useState<boolean>(false);
  const [alignmentAdvice, setAlignmentAdvice] = useState<string>('Position face inside the target circle');

  useEffect(() => {
    if (!showEnrollModal) {
      setIsFaceAligned(false);
      setAlignmentAdvice('Position face inside the target circle');
      return;
    }

    let isMounted = true;
    const pollFaceDetection = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/detect-face/${enrollDeviceId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (isMounted) {
          const aligned = Boolean(data.aligned);
          setIsFaceAligned(aligned);
          if (data.message) {
            setAlignmentAdvice(data.message);
          }
        }
      } catch (err) {
        if (isMounted) setIsFaceAligned(false);
      }
    };

    // Initial check and periodic polling
    pollFaceDetection();
    const timer = setInterval(pollFaceDetection, 350);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [showEnrollModal, enrollDeviceId]);

  if (!showEnrollModal) return null;

  return (
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

          {/* Viewfinder Feed with Interactive Biometric Guide */}
          <div>
            <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1.5">
              <span className="flex items-center gap-1.5">
                <Camera className="w-3.5 h-3.5 text-emerald-400" />
                LIVE VIEWFINDER (DEVICE {enrollDeviceId})
              </span>
              <span
                className={`text-[10px] flex items-center gap-1.5 font-mono px-2 py-0.5 rounded border transition-colors ${
                  isFaceAligned
                    ? 'text-emerald-400 bg-emerald-950/60 border-emerald-800/60'
                    : 'text-red-400 bg-red-950/60 border-red-800/60'
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isFaceAligned ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
                  }`}
                />
                {isFaceAligned ? 'ALIGNED // READY' : 'LOCK: ALIGN FACE'}
              </span>
            </div>
            <div className="relative aspect-video bg-black rounded-lg overflow-hidden flex items-center justify-center group shadow-inner">
              <img
                key={`viewfinder-stream-${enrollDeviceId}`}
                src={`http://127.0.0.1:8000/api/webcam-stream/${enrollDeviceId}?raw=true`}
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

              {/* Interactive Face-Alignment Guide Overlay (Turns Green when aligned, Red when unaligned) */}
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div
                  className={`relative w-44 h-56 sm:w-52 sm:h-64 rounded-full border-[2.5px] transition-all duration-300 flex items-center justify-center ${
                    isFaceAligned
                      ? 'border-emerald-400 shadow-[0_0_35px_rgba(52,211,153,0.55)] bg-emerald-500/5 ring-4 ring-emerald-400/20'
                      : 'border-red-500 shadow-[0_0_25px_rgba(239,68,68,0.4)] bg-red-500/5 ring-4 ring-red-500/15'
                  }`}
                >
                  {/* Cardinal alignment ticks */}
                  <div
                    className={`absolute -top-1.5 left-1/2 -translate-x-1/2 w-4 h-1 rounded-full transition-colors duration-300 ${
                      isFaceAligned ? 'bg-emerald-400' : 'bg-red-500'
                    }`}
                  />
                  <div
                    className={`absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-4 h-1 rounded-full transition-colors duration-300 ${
                      isFaceAligned ? 'bg-emerald-400' : 'bg-red-500'
                    }`}
                  />
                  <div
                    className={`absolute top-1/2 -left-1.5 -translate-y-1/2 w-1 h-4 rounded-full transition-colors duration-300 ${
                      isFaceAligned ? 'bg-emerald-400' : 'bg-red-500'
                    }`}
                  />
                  <div
                    className={`absolute top-1/2 -right-1.5 -translate-y-1/2 w-1 h-4 rounded-full transition-colors duration-300 ${
                      isFaceAligned ? 'bg-emerald-400' : 'bg-red-500'
                    }`}
                  />

                  {/* Center lock indicator */}
                  {isFaceAligned ? (
                    <div className="w-9 h-9 rounded-full bg-emerald-950/80 border border-emerald-400/80 flex items-center justify-center shadow-lg shadow-emerald-950/60 animate-pulse">
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    </div>
                  ) : (
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500/50 animate-ping" />
                  )}
                </div>

                {/* Floating Alignment Guidance Pill */}
                <div
                  className={`absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-[11px] font-mono tracking-wide border backdrop-blur-md transition-all duration-300 flex items-center gap-1.5 shadow-xl ${
                    isFaceAligned
                      ? 'bg-emerald-950/90 text-emerald-300 border-emerald-500/70 shadow-emerald-950/60'
                      : 'bg-red-950/90 text-red-300 border-red-500/70 shadow-red-950/60'
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      isFaceAligned ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
                    }`}
                  />
                  <span>{alignmentAdvice}</span>
                </div>
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
              disabled={!isFaceAligned || enrollLoading}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg font-mono text-xs font-semibold shadow-lg transition-all duration-200 ${
                isFaceAligned && !enrollLoading
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/50 hover:shadow-emerald-900/60 hover:scale-[1.02] cursor-pointer'
                  : 'bg-slate-800 text-slate-500 border border-slate-700/60 cursor-not-allowed opacity-50'
              }`}
              title={
                isFaceAligned
                  ? 'Face aligned! Click to capture and extract 512-d biometric embedding'
                  : 'Align face inside the target circle (guide turns green) to enable capture'
              }
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
  );
};

export default EnrollModal;
