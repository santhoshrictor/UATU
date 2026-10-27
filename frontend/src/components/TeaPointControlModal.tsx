import React, { useState } from 'react';
import {
  Coffee,
  X,
  Clock,
  Zap,
  CheckCircle2,
  Sliders,
} from 'lucide-react';
import { Button } from './ui/button';

export interface TeaPointConfig {
  camera_id: string;
  zone: string;
  break_window: {
    start: string;
    end: string;
    label: string;
    is_active_now: boolean;
  };
  threshold_seconds: number;
  demo_mode: boolean;
  allowed_demo_thresholds: number[];
  current_occupancy: number;
  current_dwell_seconds: number;
  is_overstay: boolean;
  last_alert_time?: number;
}

export interface TeaPointControlModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: TeaPointConfig | null;
  countdownSec?: number;
  currentDwellSec?: number;
  onResetTimer?: () => void;
  onUpdateConfig: (newThreshold: number, demoMode: boolean) => Promise<void>;
  onTriggerDemoException: () => Promise<void>;
}

export const TeaPointControlModal: React.FC<TeaPointControlModalProps> = ({
  isOpen,
  onClose,
  config,
  countdownSec,
  currentDwellSec,
  onResetTimer,
  onUpdateConfig,
  onTriggerDemoException,
}) => {
  const [selectedThreshold, setSelectedThreshold] = useState<number>(
    config?.threshold_seconds ?? 60
  );
  const [demoMode, setDemoMode] = useState<boolean>(config?.demo_mode ?? true);
  const [loading, setLoading] = useState<boolean>(false);
  const [triggering, setTriggering] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  if (!isOpen || !config) return null;

  const handleApplyThreshold = async (seconds: number) => {
    setSelectedThreshold(seconds);
    setLoading(true);
    setFeedback(null);
    try {
      await onUpdateConfig(seconds, demoMode);
      setFeedback(`Threshold updated to ${seconds >= 60 ? `${seconds / 60} min` : `${seconds}s`}`);
      setTimeout(() => setFeedback(null), 2500);
    } catch {
      setFeedback('Failed to update threshold');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleDemoMode = async () => {
    const next = !demoMode;
    setDemoMode(next);
    setLoading(true);
    try {
      await onUpdateConfig(selectedThreshold, next);
      setFeedback(`Evaluation demo mode ${next ? 'activated' : 'deactivated'}`);
      setTimeout(() => setFeedback(null), 2500);
    } catch {
      setFeedback('Failed to update demo mode');
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerException = async () => {
    setTriggering(true);
    setFeedback(null);
    try {
      await onTriggerDemoException();
      setFeedback('Long Break Exception alert & snapshot triggered successfully!');
      setTimeout(() => {
        setFeedback(null);
        onClose();
      }, 1500);
    } catch {
      setFeedback('Error triggering exception');
    } finally {
      setTriggering(false);
    }
  };

  const effectiveCountdown = countdownSec !== undefined ? countdownSec : Math.max(0, config.threshold_seconds - (config.current_dwell_seconds || 0));
  const countMin = Math.floor(effectiveCountdown / 60);
  const countSec = Math.floor(effectiveCountdown % 60);
  const countdownFormatted = `${String(countMin).padStart(2, '0')}:${String(countSec).padStart(2, '0')}`;

  const threshMin = Math.floor(config.threshold_seconds / 60);
  const threshSec = Math.floor(config.threshold_seconds % 60);
  const threshFormatted = `${String(threshMin).padStart(2, '0')}:${String(threshSec).padStart(2, '0')}`;
  const isOverstay = countdownSec !== undefined ? countdownSec <= 0 : (currentDwellSec !== undefined ? currentDwellSec >= config.threshold_seconds : config.is_overstay);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-[#0b132b] border border-[#162347] rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden text-slate-100 flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#162347] bg-[#080f22]/90">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Coffee className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight">
                  CAM-05 Tea Point Break Monitor
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold uppercase">
                  Schedule Policy
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Designated Refreshment Hub & Break Compliance Rules
              </p>
            </div>
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

        {/* Modal Body */}
        <div className="p-6 space-y-5 overflow-y-auto max-h-[80vh]">
          {/* Policy Information Box */}
          <div className="bg-[#080f22] border border-[#162347] rounded-xl p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400 uppercase font-semibold">
                Scheduled Break Window
              </span>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-semibold ${
                  config.break_window.is_active_now
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 animate-pulse'
                    : 'bg-blue-500/10 text-blue-300 border-blue-500/30'
                }`}
              >
                {config.break_window.is_active_now ? 'BREAK ACTIVE NOW' : '10:00 AM – 10:10 AM IST'}
              </span>
            </div>

            <div className="text-xs text-slate-300 font-sans leading-relaxed">
              Standard workplace policy allows a <strong>10-minute break</strong> window (10:00 AM – 10:10 AM).
              Worker presence lingering past the scheduled duration or exceeding allowed limits triggers an automated
              <strong> Long Break Exception</strong> with forensic snapshot burn-in.
            </div>

            {/* Live Dwell Meter */}
            <div className="pt-2 border-t border-[#162347] flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-1.5 text-slate-400">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                <span>Countdown:</span>
                <strong className={isOverstay ? 'text-red-400 font-bold animate-pulse' : 'text-emerald-400'}>
                  {countdownFormatted}
                </strong>
                <span className="text-slate-500">/ {threshFormatted} limit</span>
              </div>

              <div className="flex items-center gap-2">
                {onResetTimer && (
                  <button
                    type="button"
                    onClick={() => {
                      onResetTimer();
                      setFeedback('Dwell timer reset to 00:00');
                      setTimeout(() => setFeedback(null), 2000);
                    }}
                    className="text-[10px] font-mono px-2 py-0.5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer"
                    title="Reset dwell timer to 0"
                  >
                    Reset
                  </button>
                )}
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${
                    isOverstay
                      ? 'bg-red-950/80 text-red-300 border-red-500/50 animate-pulse'
                      : config.current_occupancy > 0
                      ? 'bg-amber-950/50 text-amber-300 border-amber-500/40'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}
                >
                  {isOverstay
                    ? 'OVERSTAY DETECTED'
                    : config.current_occupancy > 0
                    ? `OCCUPIED (${config.current_occupancy}P)`
                    : 'IDLE / VACANT'}
                </span>
              </div>
            </div>
          </div>

          {/* Quick Demo Threshold Multiplier */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-mono text-slate-300 font-semibold flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-blue-400" />
                <span>Demo Break Threshold (Quick Multiplier)</span>
              </label>
              <span className="text-[10px] font-mono text-slate-400">
                Active: <strong className="text-white">{config.threshold_seconds / 60} Min</strong>
              </span>
            </div>

            <div className="grid grid-cols-4 gap-2">
              {[
                { label: '1 Min', sec: 60, tag: 'Demo' },
                { label: '2 Min', sec: 120, tag: 'Demo' },
                { label: '5 Min', sec: 300, tag: 'Buffer' },
                { label: '10 Min', sec: 600, tag: 'Policy' },
              ].map((item) => (
                <button
                  key={item.sec}
                  type="button"
                  onClick={() => handleApplyThreshold(item.sec)}
                  disabled={loading}
                  className={`py-2 px-2.5 rounded-xl border text-xs font-mono flex flex-col items-center justify-center transition-all ${
                    config.threshold_seconds === item.sec
                      ? 'bg-blue-600 border-blue-400 text-white font-bold shadow-lg shadow-blue-600/30'
                      : 'bg-[#080f22] border-[#162347] text-slate-300 hover:border-slate-600 hover:text-white'
                  }`}
                >
                  <span className="text-xs">{item.label}</span>
                  <span className="text-[9px] opacity-75 font-sans uppercase">{item.tag}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Evaluation Demo Mode Toggle */}
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#080f22] border border-[#162347]">
            <div className="flex flex-col">
              <span className="text-xs font-bold text-slate-200 font-sans">
                Evaluation Demo Mode
              </span>
              <span className="text-[11px] text-slate-400 font-mono mt-0.5">
                Allows testing overstay rules at any hour of the day without waiting for 10:00 AM
              </span>
            </div>

            <button
              type="button"
              onClick={handleToggleDemoMode}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                demoMode ? 'bg-emerald-600' : 'bg-slate-700'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                  demoMode ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Direct Jury Demonstration Trigger Button */}
          <div className="pt-2">
            <Button
              onClick={handleTriggerException}
              disabled={triggering}
              className="w-full h-11 bg-gradient-to-r from-amber-600 to-red-600 hover:from-amber-500 hover:to-red-500 text-white font-mono text-xs font-bold tracking-wide rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-red-950/40 cursor-pointer"
            >
              <Zap className="w-4 h-4 text-amber-200" />
              <span>{triggering ? 'Capturing Snapshot & Dispatching Alert...' : 'Simulate Long Break Overstay (Instant Exception)'}</span>
            </Button>
            <p className="text-[11px] text-slate-500 font-mono text-center mt-1.5">
              Instantly simulates 1.5 min overstay, burns in HUD timestamp overlay, and saves snapshot to local storage.
            </p>
          </div>

          {/* Feedback message */}
          {feedback && (
            <div className="p-2.5 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs font-mono text-center flex items-center justify-center gap-2 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{feedback}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TeaPointControlModal;
