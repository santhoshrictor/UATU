import { useState } from 'react';
import {
  Mic,
  ShieldCheck,
  ExternalLink,
  X,
  Minus,
  Maximize2,
  Minimize2,
  Columns,
  Radio,
} from 'lucide-react';

type AssistantViewMode = 'docked' | 'split' | 'fullscreen';

export function UATUVoiceAssistantLauncher() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [viewMode, setViewMode] = useState<AssistantViewMode>('split');

  const getDrawerWidthClass = () => {
    switch (viewMode) {
      case 'split':
        return 'w-full lg:w-1/2 max-w-none';
      case 'fullscreen':
        return 'w-full max-w-none';
      case 'docked':
      default:
        return 'w-full max-w-xl';
    }
  };

  return (
    <>
      {/* Top Navbar Action Button */}
      <button
        onClick={() => {
          setIsOpen(true);
          setIsMinimized(false);
        }}
        className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 hover:border-emerald-500/60 transition-all font-mono text-xs tracking-wider font-semibold shadow-[0_0_12px_rgba(16,185,129,0.15)]"
        title="Open IRIS / UATU Bilingual Voice & Query Decision-Support Center"
      >
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
        </span>
        <Mic className="w-3.5 h-3.5 text-emerald-400" />
        <span className="hidden sm:inline">Ask IRIS AI</span>
      </button>

      {/* Persistent Audio / Minimized Status Pill at Bottom-Right */}
      {isOpen && isMinimized && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-3 px-4 py-2.5 rounded-lg bg-slate-900/95 border border-emerald-500/40 shadow-[0_0_24px_rgba(16,185,129,0.25)] backdrop-blur-md animate-in slide-in-from-bottom-2 duration-200">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
            <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
            <div className="flex flex-col">
              <span className="font-mono text-xs font-bold text-emerald-400 tracking-wider">
                IRIS AI ACTIVE
              </span>
              <span className="text-[10px] text-slate-400 font-sans">
                Voice link connected &bull; Listening
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 ml-2 border-l border-slate-800 pl-2">
            <button
              onClick={() => setIsMinimized(false)}
              className="px-2 py-1 rounded text-xs font-mono font-semibold bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 transition-colors"
              title="Expand IRIS Console"
            >
              Expand Console
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 text-slate-400 hover:text-rose-400 rounded transition-colors"
              title="Close Voice Session"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Non-Blocking Side-by-Side Investigation Drawer */}
      {isOpen && !isMinimized && (
        <div className="fixed inset-0 z-50 pointer-events-none flex justify-end">
          <div
            className={`pointer-events-auto relative ${getDrawerWidthClass()} h-full bg-slate-950/95 border-l border-emerald-500/30 flex flex-col shadow-[0_0_50px_rgba(0,0,0,0.85)] backdrop-blur-sm animate-in slide-in-from-right duration-250 transition-all`}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/90">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <div>
                  <h3 className="text-xs sm:text-sm font-semibold text-slate-100 font-mono tracking-wider">
                    IRIS AI // VOICE &amp; QUERY COMMAND CENTER
                  </h3>
                  <p className="text-[10px] text-slate-400 font-sans">
                    On-Premise Video Intelligence &bull; Live Camera Dashboard Unblocked
                  </p>
                </div>
              </div>

              {/* Window Controls: Split, Maximize, Minimize, External, Close */}
              <div className="flex items-center gap-1">
                {/* Split 50/50 vs Docked Toggle */}
                <button
                  onClick={() =>
                    setViewMode((prev) => (prev === 'split' ? 'docked' : 'split'))
                  }
                  className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-slate-800/60 rounded transition-colors"
                  title={
                    viewMode === 'split'
                      ? 'Switch to Compact Docked Mode'
                      : 'Switch to 50/50 Split Screen Mode'
                  }
                >
                  <Columns className="w-4 h-4" />
                </button>

                {/* Fullscreen vs Restored Toggle */}
                <button
                  onClick={() =>
                    setViewMode((prev) => (prev === 'fullscreen' ? 'split' : 'fullscreen'))
                  }
                  className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-slate-800/60 rounded transition-colors"
                  title={
                    viewMode === 'fullscreen' ? 'Restore to Split Mode' : 'Expand to Fullscreen'
                  }
                >
                  {viewMode === 'fullscreen' ? (
                    <Minimize2 className="w-4 h-4" />
                  ) : (
                    <Maximize2 className="w-4 h-4" />
                  )}
                </button>

                {/* Minimize to PIP Pill */}
                <button
                  onClick={() => setIsMinimized(true)}
                  className="p-1.5 text-slate-400 hover:text-amber-400 hover:bg-slate-800/60 rounded transition-colors"
                  title="Minimize to Floating Status Pill (Keep Voice Active)"
                >
                  <Minus className="w-4 h-4" />
                </button>

                {/* External Window */}
                <a
                  href="http://localhost:3000"
                  target="_blank"
                  rel="noreferrer"
                  className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-slate-800/60 rounded transition-colors"
                  title="Open IRIS Console in dedicated browser window"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>

                {/* Close */}
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800/60 rounded transition-colors ml-1"
                  aria-label="Close IRIS Console"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Embedded Console Frame */}
            <div className="flex-1 bg-slate-950 relative">
              <iframe
                src="http://localhost:3000"
                title="IRIS AI Voice & Query Console"
                className="w-full h-full border-none"
                allow="microphone; camera; display-capture"
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
