import { useState } from 'react';
import { Mic, ShieldCheck, ExternalLink, X } from 'lucide-react';

export function UATUVoiceAssistantLauncher() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Top Navbar Action Button */}
      <button
        onClick={() => setIsOpen(true)}
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

      {/* Slide-over Investigation Drawer / Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-2xl h-full bg-slate-950 border-l border-slate-800 flex flex-col shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800 bg-slate-900/80">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <div>
                  <h3 className="text-sm font-semibold text-slate-100 font-mono tracking-wider">
                    IRIS AI // VOICE &amp; QUERY COMMAND CENTER
                  </h3>
                  <p className="text-[10px] text-slate-400 font-sans">
                    On-Premise Evidence-Grounded Video Intelligence &bull; English &amp; Tamil
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href="http://localhost:3000"
                  target="_blank"
                  rel="noreferrer"
                  className="p-1.5 text-slate-400 hover:text-emerald-400 rounded transition-colors"
                  title="Open IRIS Console in new browser window"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1.5 text-slate-400 hover:text-rose-400 rounded transition-colors"
                  aria-label="Close IRIS Console"
                >
                  <X className="w-5 h-5" />
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
