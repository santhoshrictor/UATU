import { useState, useEffect } from 'react';
import { Mic, ShieldCheck, ExternalLink, X, RotateCcw, AlertCircle, RefreshCw } from 'lucide-react';

export function UATUVoiceAssistantLauncher() {
  const [isOpen, setIsOpen] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);
  const [isConsoleReady, setIsConsoleReady] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  // Check if IRIS Console server on port 3000 is reachable when drawer opens
  const checkConsoleReachability = async () => {
    setIsChecking(true);
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2500);
      await fetch('http://localhost:3000', {
        method: 'HEAD',
        mode: 'no-cors',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      setIsConsoleReady(true);
    } catch {
      // If fetch fails or aborts
      setIsConsoleReady(false);
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      void checkConsoleReachability();
    }
  }, [isOpen, iframeKey]);

  const handleReconnect = () => {
    setIframeKey((prev) => prev + 1);
    void checkConsoleReachability();
  };

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
                <button
                  onClick={handleReconnect}
                  disabled={isChecking}
                  className="p-1.5 text-slate-400 hover:text-emerald-400 rounded transition-colors"
                  title="Reconnect / Reload IRIS Telemetry Console"
                >
                  <RotateCcw className={`w-4 h-4 ${isChecking ? 'animate-spin text-emerald-400' : ''}`} />
                </button>
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

            {/* Diagnostic Alert if port 3000 is delayed or offline */}
            {isConsoleReady === false && (
              <div className="px-5 py-2.5 bg-amber-950/60 border-b border-amber-500/30 flex items-center justify-between text-xs text-amber-200">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>
                    IRIS Web Console server (port 3000) not responding. Ensure <code>start_iris.bat</code> is running.
                  </span>
                </div>
                <button
                  onClick={handleReconnect}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 font-mono text-[11px] font-semibold transition-all shrink-0 ml-3"
                >
                  <RefreshCw className="w-3 h-3" />
                  Reconnect
                </button>
              </div>
            )}

            {/* Embedded Console Frame */}
            <div className="flex-1 bg-slate-950 relative">
              <iframe
                key={iframeKey}
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

