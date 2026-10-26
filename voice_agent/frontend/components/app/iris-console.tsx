'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Camera,
  CircleHelp,
  Copy,
  Cpu,
  Languages,
  Layers,
  Mic,
  Monitor,
  Pause,
  Play,
  Power,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
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
    label: 'UATU Surveillance Intelligence Online',
    detail: 'On-premise edge AI ready for multi-camera video intelligence & safety queries.',
  },
  connecting: {
    label: 'Establishing Secure Telemetry',
    detail: 'Initializing local edge inference, audio pipelines, and WebRTC streaming.',
  },
  initializing: {
    label: 'UATU Engine Syncing',
    detail: 'Connecting to CAM-01..CAM-09 camera channels and local indexed seed store.',
  },
  listening: {
    label: 'Listening to Operator Voice',
    detail: 'Speak in English, Tamil, or Tanglish. Real-time workplace intelligence active.',
  },
  thinking: {
    label: 'Analyzing Video Events & Telemetry',
    detail: 'Cross-referencing camera feeds, turnstiles, and safety alert registers.',
  },
  speaking: {
    label: 'UATU Synthesizing Evidence Brief',
    detail: 'Streaming evidence-backed response. Interrupt anytime to refine query.',
  },
  idle: {
    label: 'UATU Voice Ready',
    detail: 'Standing by for workplace safety, perimeter, and access investigation queries.',
  },
  'pre-connect-buffering': {
    label: 'Buffering Telemetry',
    detail: 'Preparing ultra-low-latency real-time voice pipeline.',
  },
  failed: {
    label: 'Connection Interrupted',
    detail: 'Re-authenticate or verify local LiveKit / FastAPI backend server status.',
  },
  disconnected: {
    label: 'Awaiting Operator Session',
    detail: 'Click connect to initiate authenticated AI voice investigation.',
  },
};

interface QuickPrompt {
  id: string;
  tag: string;
  query: string;
}

const QUICK_PROMPTS: QuickPrompt[] = [
  {
    id: 'qp-1',
    tag: 'STORES / ACCESS AUDIT',
    query:
      'Show all after-hours entries into Stores 2 last Friday and identify unmatched access-card events.',
  },
  {
    id: 'qp-2',
    tag: 'CANTEEN / OVERSTAY',
    query: 'Show employees in the canteen for more than 45 minutes yesterday.',
  },
  {
    id: 'qp-3',
    tag: 'TOOL ROOM / ASSET AUDIT',
    query: 'Find the video when the welding machine was removed from Tool Room.',
  },
  {
    id: 'qp-4',
    tag: 'SAFETY / CRITICAL ALERTS',
    query: 'Show all critical fire, smoke, or worker fall alerts today.',
  },
  {
    id: 'qp-5',
    tag: 'INFRASTRUCTURE / STORAGE',
    query: 'Check camera health, FPS status, and 30-day storage capacity.',
  },
];

export function IrisConsole({ appConfig }: { appConfig: AppConfig }) {
  const session = useSessionContext();
  const { state: agentState } = useVoiceAssistant();
  const { messages } = useSessionMessages(session);
  const { isCameraEnabled, isScreenShareEnabled } = useLocalParticipant();
  const { send } = useChat();

  const [isStarting, setIsStarting] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [motionPaused, setMotionPaused] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [connectionError, setConnectionError] = useState('');
  const [activePromptId, setActivePromptId] = useState<string | null>(null);

  const phase =
    isStarting || session.connectionState === 'connecting'
      ? 'connecting'
      : !session.isConnected
        ? 'standby'
        : agentState;
  const status = PHASES[phase] ?? PHASES.idle;
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
      setConnectionError(
        'Could not start UATU session. Check microphone permissions and confirm livekit-server and agent are running.'
      );
    } finally {
      setIsStarting(false);
    }
  }

  async function endCall() {
    setIsChatOpen(false);
    try {
      await session.end();
    } catch {
      setConnectionError('Could not disconnect cleanly. Please refresh the page.');
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
    } catch {
      setConnectionError('Could not restart. End session and connect again.');
    } finally {
      setIsStarting(false);
    }
  }

  async function handleQuickPrompt(prompt: QuickPrompt) {
    setActivePromptId(prompt.id);
    setTimeout(() => setActivePromptId(null), 1500);

    // Always copy to clipboard for operator convenience
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(prompt.query);
      } catch {}
    }

    if (session.isConnected) {
      try {
        await send(prompt.query);
        setIsChatOpen(true);
        toast.success('Query transmitted to UATU agent', {
          description: `"${prompt.query.slice(0, 55)}..."`,
        });
      } catch (err) {
        console.error('Failed to send prompt:', err);
        toast.error('Failed to transmit query. Copied to clipboard.');
      }
    } else {
      toast.info('Query copied to clipboard', {
        description: 'Connect to UATU Voice AI to speak or submit this query automatically.',
      });
    }
  }

  return (
    <div
      className="iris-console"
      data-phase={phase}
      data-chat={isChatOpen ? 'open' : 'closed'}
      data-motion={motionPaused ? 'paused' : 'running'}
    >
      <div className="iris-console__texture" aria-hidden="true" />

      {/* Top Industrial Surveillance Header */}
      <header className="iris-header">
        <Link className="iris-brand" href="/" aria-label="UATU Home">
          <span className="iris-brand__mark">
            <ShieldCheck size={24} strokeWidth={1.8} className="text-emerald-400" />
          </span>
          <span>
            <strong>
              UATU<span className="iris-brand__period">.</span>
            </strong>
            <small>EDGE AI VOICE & SEARCH ASSISTANT</small>
            <span className="iris-brand__subtitle">
              On-Premise Evidence-Grounded Video Intelligence • English & Tamil/Tanglish
            </span>
          </span>
        </Link>

        <div className="iris-header__right">
          <div className="uatu-header-tags hidden items-center gap-2 lg:flex">
            <span className="uatu-chip uatu-chip--mode">
              <Cpu size={11} /> ON-PREMISE EDGE AI // HITL VERIFIED
            </span>
            <span className="uatu-chip uatu-chip--scope">
              <Layers size={11} /> CAM-01..CAM-09
            </span>
            <span className="uatu-chip uatu-chip--lang">
              <Languages size={11} /> EN / TA / TANGLISH
            </span>
          </div>

          <span className={`iris-connection ${session.isConnected ? 'is-live' : ''}`}>
            <i />
            {session.isConnected ? 'SESSION CONNECTED' : isStarting ? 'CONNECTING' : 'STANDBY'}
          </span>
          <span className="iris-header__divider" />
          {session.isConnected && (
            <button
              className="iris-icon-button"
              onClick={() => void restartCall()}
              disabled={isStarting}
              aria-label="Restart conversation"
              title="Restart session with fresh context"
            >
              <RotateCcw size={15} />
            </button>
          )}
          <button
            className="iris-icon-button"
            onClick={() => setMotionPaused(!motionPaused)}
            aria-label={motionPaused ? 'Resume animation' : 'Pause animation'}
            title={motionPaused ? 'Resume animation' : 'Pause animation'}
          >
            {motionPaused ? <Play size={15} /> : <Pause size={15} />}
          </button>
          <button
            className="iris-icon-button"
            onClick={() => setHelpOpen(!helpOpen)}
            aria-label="How to use UATU"
            aria-expanded={helpOpen}
          >
            <CircleHelp size={17} />
          </button>
        </div>
      </header>

      {/* HUD Operational Status Bar */}
      <div className="uatu-hud-status-bar">
        <div className="uatu-hud-badge">
          <span className="uatu-hud-label">SYSTEM MODE</span>
          <strong className="text-emerald-400">
            ON-PREMISE EDGE AI // HUMAN-IN-THE-LOOP VERIFIED
          </strong>
        </div>
        <div className="uatu-hud-badge">
          <span className="uatu-hud-label">CAMERA MATRIX SCOPE</span>
          <strong className="text-slate-200">CAM-01..CAM-09 (9 Zones Indexed)</strong>
        </div>
        <div className="uatu-hud-badge">
          <span className="uatu-hud-label">LANGUAGE ENGINE</span>
          <strong className="text-emerald-400">EN / TA / TANGLISH ACTIVE</strong>
        </div>
      </div>

      <main className="iris-workspace" id="main-content">
        <section className="iris-center" aria-label="UATU voice interface">
          <div className="iris-reactor-caption">
            <span className="iris-tiny-cross">+</span> MULTI-CAMERA VOICE INTELLIGENCE{' '}
            <span className="iris-caption-line" /> <span>UATU / SURVEILLANCE CORE</span>
          </div>

          <div className="iris-reactor-stage">
            <LiveIrisReactor phase={phase} />
            <span className="iris-stage-coordinate iris-stage-coordinate--left">
              EVIDENCE / STREAM
            </span>
            <span className="iris-stage-coordinate iris-stage-coordinate--right">
              TAMIL / ENGLISH
            </span>
          </div>

          <div className="iris-center__status" aria-live="polite" aria-atomic="true">
            <div className="iris-state-label">
              <span />
              {phase === 'standby'
                ? 'AWAITING OPERATOR VOICE / QUERY'
                : phase.replaceAll('-', ' ').toUpperCase()}
            </div>
            <h2>{status.label}</h2>
            <p>{status.detail}</p>
          </div>

          {!session.isConnected && (
            <div className="iris-start-area">
              <button
                className="iris-start-button"
                disabled={isStarting}
                onClick={() => void startCall()}
              >
                <Power size={17} strokeWidth={1.6} />
                <span>{isStarting ? 'Connecting to UATU...' : appConfig.startButtonText}</span>
                <span className="iris-start-button__arrow">↗</span>
              </button>
              <span className="iris-start-hint">
                <Mic size={11} /> Microphone access enabled for bilingual voice commands
              </span>
            </div>
          )}

          {connectionError && (
            <p className="iris-connection-error" role="alert">
              {connectionError}
            </p>
          )}

          {session.isConnected && (
            <div className="iris-live-controls">
              <AgentControlBar
                variant="livekit"
                isConnected={session.isConnected}
                isChatOpen={isChatOpen}
                onIsChatOpenChange={setIsChatOpen}
                onDisconnect={() => void endCall()}
                controls={{
                  leave: true,
                  microphone: true,
                  camera: appConfig.supportsVideoInput,
                  screenShare: appConfig.supportsScreenShare,
                  chat: appConfig.supportsChatInput,
                }}
              />
            </div>
          )}

          {/* Quick Investigation Prompts Bar */}
          <div className="uatu-quick-prompts-container" aria-label="Quick Investigation Prompts">
            <div className="uatu-quick-prompts-header">
              <span className="flex items-center gap-1.5 font-mono text-[10px] tracking-wider text-emerald-400 uppercase">
                <Sparkles size={12} /> Quick Investigation Queries (Section 4 Grounded)
              </span>
              <span className="text-[10px] text-slate-400">
                Click chip to transmit or speak query directly into microphone
              </span>
            </div>

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
                          <Copy size={11} className="text-emerald-400" />
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

      {/* Video Preview */}
      {video && !isChatOpen && (
        <div className="iris-video-preview">
          <span>
            {isScreenShareEnabled ? <Monitor size={12} /> : <Camera size={12} />}
            {isScreenShareEnabled ? 'OPERATOR SCREEN' : 'OPERATOR CAMERA'}
          </span>
          <VideoTrack trackRef={video} />
        </div>
      )}

      {/* Live Conversation Transcript Drawer */}
      {session.isConnected && isChatOpen && (
        <aside className="iris-conversation" aria-label="Conversation">
          <header>
            <span>
              <span className="iris-tiny-cross">+</span> UATU INVESTIGATION TRANSCRIPT
            </span>
            <button
              className="iris-icon-button"
              onClick={() => setIsChatOpen(false)}
              aria-label="Close conversation"
            >
              <X size={17} />
            </button>
          </header>
          <AgentChatTranscript
            agentState={agentState}
            messages={messages}
            className="iris-conversation__messages"
          />
        </aside>
      )}

      {/* Help Modal */}
      {helpOpen && (
        <section className="iris-help" aria-label="How to use UATU">
          <button
            className="iris-icon-button"
            onClick={() => setHelpOpen(false)}
            aria-label="Close help"
          >
            <X size={16} />
          </button>
          <span className="iris-eyebrow">UATU OPERATOR MANUAL</span>
          <h2>Voice & Search Center</h2>
          <p>
            Connect, allow microphone access, and query surveillance channels naturally in English
            or Tamil/Tanglish.
          </p>
          <p className="font-mono text-[11px] text-emerald-300">
            Example Tamil: “Stores 2-la night yaaru entry pannanga?” / “Tool room la welding machine
            irukka?”
          </p>
          <p>
            Click any <strong>Quick Investigation Chip</strong> to instantly submit complex
            multi-camera queries or test edge fallback telemetry.
          </p>
          <p className="text-[11px] text-amber-300">
            <ShieldAlert size={12} className="mr-1 inline" />
            Core Principle: All theft, safety violation, and HR disciplinary alerts require human
            investigator review before executive action.
          </p>
        </section>
      )}

      {/* Mandatory Section 1 Core Principle Persistent Compliance Banner */}
      <div className="uatu-compliance-banner">
        <span className="uatu-compliance-badge">SECTION 1 COMPLIANCE</span>
        <p className="uatu-compliance-text">
          <strong>CORE PRINCIPLE:</strong> Evidence-based decision-support platform. All high-impact
          safety, security, HR, or theft-related events require authorized human investigator
          review.
        </p>
      </div>

      <footer className="iris-footer">
        <span>
          <i /> UATU VIDEO INTELLIGENCE PLATFORM
        </span>
        <span className="iris-footer__center">
          CAM-01..CAM-09 INDEXED • BI-LINGUAL VOICE DECISION SUPPORT • ON-PREMISE AIR-GAPPED READY
        </span>
        <span>
          STATUS: OPERATIONAL <span className="iris-tiny-cross">+</span>
        </span>
      </footer>
    </div>
  );
}
