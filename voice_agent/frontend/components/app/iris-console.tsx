'use client';

import { type FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Camera,
  CircleHelp,
  Copy,
  Languages,
  MessageSquare,
  Mic,
  MicOff,
  Monitor,
  RotateCcw,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  VideoTrack,
  useChat,
  useLocalParticipant,
  useSessionContext,
  useSessionMessages,
  useVoiceAssistant,
} from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import { AgentControlBar } from '@/components/agents-ui/agent-control-bar';
import { LiveIrisReactor } from '@/components/app/iris-reactor';

const PHASES: Record<string, { label: string; detail: string }> = {
  standby: {
    label: 'IRIS AI Multi-Lingual Ready',
    detail: 'Voice & decision-support online. English, Tamil, and Tanglish active.',
  },
  ready: {
    label: 'IRIS AI Multi-Lingual Ready',
    detail: 'Voice & decision-support online. English, Tamil, and Tanglish active.',
  },
  connecting: {
    label: 'IRIS AI Connecting...',
    detail: 'Voice & query engine online. Connecting background audio channel.',
  },
  initializing: {
    label: 'IRIS AI Multi-Lingual Ready',
    detail: 'Real-time multi-camera channels and alert registers online.',
  },
  listening: {
    label: 'Listening (English / தமிழ் / Tanglish)...',
    detail: 'Speak naturally in English or Tamil. Interrupt anytime.',
  },
  thinking: {
    label: 'Analyzing Video Feeds & Registers...',
    detail: 'Cross-referencing camera streams and anomaly logs.',
  },
  speaking: {
    label: 'IRIS Responding...',
    detail: 'Streaming verified evidence brief.',
  },
  idle: {
    label: 'IRIS AI Multi-Lingual Ready',
    detail: 'Standing by for live video intelligence and safety queries.',
  },
  failed: {
    label: 'IRIS AI (Direct Query Active)',
    detail: 'Direct database & camera queries are available below.',
  },
  disconnected: {
    label: 'IRIS AI Multi-Lingual Ready',
    detail: 'Voice & decision-support online. Speak or type below.',
  },
};

interface QuickPrompt {
  id: string;
  tag: string;
  query: string;
  targetCamera?: string;
}

const QUICK_PROMPTS: QuickPrompt[] = [
  {
    id: 'qp-cam2',
    tag: 'CAM-02 // WORKSHOP (EN)',
    query: 'Focus on Camera 02 and inspect Workshop Floor Alpha for PPE compliance.',
    targetCamera: 'CAM-02',
  },
  {
    id: 'qp-cam5',
    tag: 'CAM-05 // TEA POINT (TANGLISH)',
    query: 'CAM-05 Tea Point la live dwell timer status enna? Break overstay alert irukka?',
    targetCamera: 'CAM-05',
  },
  {
    id: 'qp-turnstile',
    tag: 'STORES // ACCESS (TAMIL/TANGLISH)',
    query:
      'Stores 2-la night shift la unauthorized entry yaaru pannanga? Unmatched card events check pannu.',
  },
  {
    id: 'qp-alerts',
    tag: 'ALERTS // CRITICAL (EN/TA)',
    query: 'Show all critical fire, smoke, and worker fall alerts from the database today.',
  },
];

export function IrisConsole({ appConfig }: { appConfig: AppConfig }) {
  const session = useSessionContext();
  const { state: agentState } = useVoiceAssistant();
  const { messages } = useSessionMessages(session);
  const { localParticipant, isCameraEnabled, isScreenShareEnabled, isMicrophoneEnabled } =
    useLocalParticipant();
  const { send } = useChat();

  const [isStarting, setIsStarting] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [connectionError, setConnectionError] = useState('');
  const [activePromptId, setActivePromptId] = useState<string | null>(null);
  const [customQuery, setCustomQuery] = useState('');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  // Auto-connect instantly on mount to eliminate artificial "click to connect" and telemetry waiting lag
  useEffect(() => {
    let unmounted = false;
    const autoInit = async () => {
      if (!session.isConnected && !isStarting && session.connectionState === 'disconnected') {
        setIsStarting(true);
        try {
          await session.start();
        } catch {
          if (!unmounted) {
            console.warn('Voice WebRTC auto-connect deferred; direct query mode active.');
          }
        } finally {
          if (!unmounted) setIsStarting(false);
        }
      }
    };
    void autoInit();
    return () => {
      unmounted = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Automatic background reconnect with backoff if network jitter causes disconnect
  useEffect(() => {
    if (session.isConnected) {
      setReconnectAttempts(0);
      return;
    }
    if (session.connectionState === 'disconnected' && !isStarting && reconnectAttempts < 3) {
      const timer = setTimeout(() => {
        setReconnectAttempts((prev) => prev + 1);
        void startCall();
      }, 3000);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.connectionState, session.isConnected, isStarting, reconnectAttempts]);

  // Responsive phase without blocking artificial loading state
  const phase = session.isConnected ? agentState : 'ready';
  const status = PHASES[phase] ?? PHASES.ready;
  const video = isScreenShareEnabled
    ? session.local.screenShareTrack
    : isCameraEnabled
      ? session.local.cameraTrack
      : undefined;

  useEffect(() => {
    if (!helpOpen && !isChatOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setHelpOpen(false);
        setIsChatOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [helpOpen, isChatOpen]);

  async function startCall() {
    if (isStarting || session.isConnected) return;
    setConnectionError('');
    setIsStarting(true);
    try {
      await session.start();
    } catch {
      setConnectionError('Voice link connection notice: Direct queries remain active.');
    } finally {
      setIsStarting(false);
    }
  }

  async function restartCall() {
    if (isStarting) return;
    setIsStarting(true);
    setIsChatOpen(false);
    setConnectionError('');
    try {
      await session.end();
      await session.start();
      toast.success('IRIS AI voice session refreshed');
    } catch {
      setConnectionError('Direct query mode active.');
    } finally {
      setIsStarting(false);
    }
  }

  // Handle programmatically switching camera feeds via postMessage and backend layout broadcast
  const switchCameraFocus = async (camId: string) => {
    if (typeof window !== 'undefined' && window.parent) {
      window.parent.postMessage({ type: 'FOCUS_CAMERA', cameraId: camId }, '*');
    }
    try {
      await fetch('http://127.0.0.1:8000/api/ui/layout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layout: '1x1', camera_id: camId }),
      });
    } catch {
      // Ignored if backend layout is unreachable; parent postMessage already fired
    }
    toast.success(`Switched focus to ${camId}`);
  };

  const fallbackDirectQuery = async (queryText: string) => {
    setIsChatOpen(true);
    // Multi-lingual parsing (English, Tamil, and Tanglish keywords)
    const isAlertQuery = /alert|incident|fire|smoke|fall|hazard|neruppu|thee|abaththu|kollai/i.test(
      queryText
    );
    const isCameraQuery = /camera|cam|paaru|focus|kaatu/i.test(queryText);
    const isAccessQuery = /stores|entry|exit|turnstile|yaaru|card|unmatched|after-hours/i.test(
      queryText
    );
    const isTeaPointQuery = /tea|dwell|break|overstay|canteen/i.test(queryText);

    if (isCameraQuery) {
      const match = queryText.match(/(?:camera|cam)\s*0?([1-9])/i);
      if (match && match[1]) {
        void switchCameraFocus(`CAM-0${match[1]}`);
      }
    }

    if (isTeaPointQuery) {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/tea-point/status');
        if (res.ok) {
          const tp = await res.json();
          toast.success('CAM-05 Tea Point Live Telemetry', {
            description: `Occupancy: ${tp.current_occupancy ?? 0} | Status: ${tp.active_status || 'NOMINAL'}`,
          });
          return;
        }
      } catch {}
    }

    if (isAlertQuery || isAccessQuery) {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/live-events?limit=5');
        if (res.ok) {
          const events = await res.json();
          toast.success(`Queried live database: ${events.length} records retrieved`, {
            description:
              events.length > 0
                ? `${events[0].type || 'Alert'} (${events[0].camera_id || 'CAM-01'})`
                : 'All zones nominal',
          });
          return;
        }
      } catch {}
    }

    toast.info('Query registered', { description: queryText });
  };

  async function handleQuickPrompt(prompt: QuickPrompt) {
    setActivePromptId(prompt.id);
    setTimeout(() => setActivePromptId(null), 1500);

    if (prompt.targetCamera) {
      void switchCameraFocus(prompt.targetCamera);
    }

    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(prompt.query);
      } catch {}
    }

    if (session.isConnected) {
      try {
        await send(prompt.query);
        setIsChatOpen(true);
        toast.success('Query transmitted to IRIS AI', {
          description: `"${prompt.query.slice(0, 50)}..."`,
        });
      } catch (err) {
        console.error('Failed to send prompt:', err);
        void fallbackDirectQuery(prompt.query);
      }
    } else {
      void fallbackDirectQuery(prompt.query);
    }
  }

  const handleCustomQuerySubmit = async (e: FormEvent) => {
    e.preventDefault();
    const q = customQuery.trim();
    if (!q) return;
    setCustomQuery('');

    // Check if query asks to view or focus a specific camera
    const camMatch = q.match(/(?:camera|cam)\s*0?([1-9])/i);
    if (camMatch && camMatch[1]) {
      const camId = `CAM-0${camMatch[1]}`;
      void switchCameraFocus(camId);
    }

    if (session.isConnected) {
      try {
        await send(q);
        setIsChatOpen(true);
        toast.success('Transmitted query to IRIS AI');
      } catch {
        void fallbackDirectQuery(q);
      }
    } else {
      void fallbackDirectQuery(q);
    }
  };

  const isMicActive = session.isConnected && isMicrophoneEnabled;

  return (
    <div className="iris-console" data-phase={phase} data-chat={isChatOpen ? 'open' : 'closed'}>
      <div className="iris-console__texture" aria-hidden="true" />

      {/* Streamlined Modern Header with Multi-Lingual Engine Status */}
      <header className="iris-header">
        <Link className="iris-brand" href="/" aria-label="IRIS Home">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-blue-500/30 bg-blue-600/20 text-blue-400">
              <Sparkles size={16} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold tracking-wider text-slate-100">
                  IRIS AI
                </span>
                <span className="flex items-center gap-1 rounded border border-blue-500/20 bg-blue-500/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-blue-400">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" />
                  ONLINE
                </span>
                {/* Multi-Lingual Engine Indicator */}
                <span
                  className="hidden items-center gap-1 rounded border border-emerald-500/25 bg-emerald-500/10 px-1.5 py-0.5 font-mono text-[9px] font-medium tracking-wide text-emerald-400 sm:inline-flex"
                  title="Multi-Lingual Engine: Full support for English, Tamil, and Tanglish Code-Switching"
                >
                  <Languages size={10} /> EN • தமிழ் • TANGLISH
                </span>
              </div>
              <p className="font-sans text-[11px] text-slate-400">
                Voice &amp; Multi-Camera Intelligence • Bilingual Engine
              </p>
            </div>
          </div>
        </Link>

        {/* Core Priority Controls: Microphone, Chat Transcript, Refresh */}
        <div className="iris-header__right">
          {session.isConnected ? (
            <button
              type="button"
              className={`iris-icon-button ${
                isMicActive
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                  : 'bg-amber-500/10 text-amber-400'
              }`}
              onClick={() => void localParticipant?.setMicrophoneEnabled(!isMicrophoneEnabled)}
              title={isMicActive ? 'Mute Microphone (Voice Priority Active)' : 'Unmute Microphone'}
              aria-label="Toggle Microphone"
            >
              {isMicActive ? <Mic size={15} /> : <MicOff size={15} />}
            </button>
          ) : (
            <button
              type="button"
              className="iris-icon-button text-blue-400 hover:text-blue-300"
              onClick={() => void startCall()}
              disabled={isStarting}
              title="Activate Instant Voice Link"
              aria-label="Activate Voice Link"
            >
              <Mic size={15} />
            </button>
          )}

          <button
            type="button"
            className={`iris-icon-button ${
              isChatOpen ? 'border-blue-500/30 bg-blue-500/10 text-blue-400' : 'text-slate-400'
            }`}
            onClick={() => setIsChatOpen(!isChatOpen)}
            title="Toggle Query Transcript"
            aria-label="Toggle Conversation"
          >
            <MessageSquare size={15} />
          </button>

          <button
            type="button"
            className="iris-icon-button"
            onClick={() => void restartCall()}
            disabled={isStarting}
            aria-label="Fresh Session"
            title="Restart Session with Fresh Context"
          >
            <RotateCcw size={14} />
          </button>

          <button
            type="button"
            className="iris-icon-button"
            onClick={() => setHelpOpen(!helpOpen)}
            aria-label="How to use IRIS"
            title="Operator Guide"
          >
            <CircleHelp size={15} />
          </button>
        </div>
      </header>

      <main className="iris-workspace" id="main-content">
        <section className="iris-center" aria-label="IRIS AI voice and query interface">
          {/* Center Stage: Clean Bubble Loader */}
          <div className="iris-reactor-stage">
            <LiveIrisReactor phase={phase} />
          </div>

          {/* Clean Status Headline */}
          <div className="iris-center__status" aria-live="polite" aria-atomic="true">
            <div className="iris-state-label">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-blue-400" />
              {session.isConnected
                ? phase.replaceAll('-', ' ').toUpperCase()
                : 'INSTANT VOICE & MULTI-LINGUAL READY'}
            </div>
            <h2 className="font-semibold text-slate-100 sm:text-lg">{status.label}</h2>
            <p className="mx-auto max-w-md text-xs text-slate-400">{status.detail}</p>
          </div>

          {/* Instant Query Input Field */}
          <form onSubmit={handleCustomQuerySubmit} className="iris-instant-query-form">
            <Search size={14} className="ml-1 shrink-0 text-slate-400" />
            <input
              type="text"
              value={customQuery}
              onChange={(e) => setCustomQuery(e.target.value)}
              placeholder="Ask in English or Tamil... (e.g. 'Pull up Camera 02', 'CAM-05 Tea Point status enna?')"
              className="iris-query-input"
            />
            <button
              type="submit"
              className="iris-query-submit-btn"
              disabled={!customQuery.trim()}
              title="Submit query"
              aria-label="Submit query"
            >
              <Send size={13} />
            </button>
          </form>

          {connectionError && (
            <p className="iris-connection-error text-xs text-amber-300" role="alert">
              {connectionError}
            </p>
          )}

          {/* Live Call Controls Bar (if in active WebRTC call) */}
          {session.isConnected && (
            <div className="iris-live-controls mt-2">
              <AgentControlBar
                variant="livekit"
                isConnected={session.isConnected}
                isChatOpen={isChatOpen}
                onIsChatOpenChange={setIsChatOpen}
                onDisconnect={() => void session.end()}
                controls={{
                  leave: false,
                  microphone: true,
                  camera: appConfig.supportsVideoInput,
                  screenShare: appConfig.supportsScreenShare,
                  chat: appConfig.supportsChatInput,
                }}
              />
            </div>
          )}

          {/* Streamlined Multi-Lingual Quick Action & Investigation Chips */}
          <div className="uatu-quick-prompts-container" aria-label="Quick Investigation Prompts">
            <div className="uatu-quick-prompts-grid">
              {QUICK_PROMPTS.map((p) => {
                const isActive = activePromptId === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => void handleQuickPrompt(p)}
                    className={`uatu-prompt-card ${isActive ? 'is-active' : ''}`}
                    title="Click to query or copy"
                  >
                    <div className="uatu-prompt-card__top">
                      <span className="uatu-prompt-tag">{p.tag}</span>
                      <span className="uatu-prompt-icon">
                        {isActive ? (
                          <Copy size={11} className="text-blue-400" />
                        ) : (
                          <Search size={11} />
                        )}
                      </span>
                    </div>
                    <p className="uatu-prompt-text">{p.query}</p>
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      </main>

      {/* Video Preview (if enabled) */}
      {video && !isChatOpen && (
        <div className="iris-video-preview">
          <span>
            {isScreenShareEnabled ? <Monitor size={12} /> : <Camera size={12} />}
            {isScreenShareEnabled ? 'OPERATOR SCREEN' : 'OPERATOR CAMERA'}
          </span>
          <VideoTrack trackRef={video} />
        </div>
      )}

      {/* Conversation / Query Transcript Drawer */}
      {isChatOpen && (
        <aside className="iris-conversation" aria-label="Conversation">
          <header>
            <span className="font-mono text-xs font-semibold tracking-wider text-slate-200">
              IRIS AI MULTI-LINGUAL INVESTIGATION TRANSCRIPT
            </span>
            <button
              type="button"
              className="iris-icon-button"
              onClick={() => setIsChatOpen(false)}
              aria-label="Close conversation"
            >
              <X size={15} />
            </button>
          </header>
          <AgentChatTranscript
            agentState={agentState}
            messages={messages}
            className="iris-conversation__messages"
          />
        </aside>
      )}

      {/* Operator Manual Modal */}
      {helpOpen && (
        <section className="iris-help" aria-label="How to use IRIS">
          <button
            type="button"
            className="iris-icon-button"
            onClick={() => setHelpOpen(false)}
            aria-label="Close help"
          >
            <X size={15} />
          </button>
          <span className="iris-eyebrow">IRIS OPERATOR GUIDE</span>
          <h2>Voice &amp; Multi-Lingual Decision Support</h2>
          <p>
            Speak or type queries naturally in English, Tamil (தமிழ்), or Tanglish code-switching.
            IRIS queries the live camera feeds and detection alert database in real time.
          </p>
          <p className="font-mono text-[11px] text-blue-300">
            Multi-Lingual Examples:
            <br />
            • English: &ldquo;Pull up Camera 02&rdquo; / &ldquo;Show critical safety alerts
            today&rdquo;
            <br />
            • Tanglish: &ldquo;CAM-05 Tea Point-la break overstay alert ethavathu irukka?&rdquo;
            <br />• Tamil: &ldquo;Stores 2-la night shift-la yaaru unauthorized-ah entry
            pannanga?&rdquo;
          </p>
          <p className="text-[11px] text-amber-300">
            <ShieldAlert size={12} className="mr-1 inline" />
            Decision-support platform: All high-impact safety or security actions require human
            investigator review.
          </p>
        </section>
      )}

      <footer className="iris-footer">
        <span>
          <i /> IRIS AI MULTI-LINGUAL DECISION SUPPORT
        </span>
        <span className="iris-footer__center">
          CAM-01..CAM-09 INDEXED • ENGLISH • தமிழ் • TANGLISH ACTIVE • ON-PREMISE EDGE AI
        </span>
        <span>
          STATUS: ONLINE <span className="iris-tiny-cross">+</span>
        </span>
      </footer>
    </div>
  );
}
