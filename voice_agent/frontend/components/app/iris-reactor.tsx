'use client';

import { type CSSProperties, memo, useEffect, useRef } from 'react';
import {
  type AgentState,
  useMultibandTrackVolume,
  useSessionContext,
  useVoiceAssistant,
} from '@livekit/components-react';

export type ReactorState = AgentState | 'standby';

// Server and browser engines can differ at the last floating-point digit.
const coordinate = (value: number) => Number(value.toFixed(3));
const AUDIO_BANDS = 32;

const TICKS = Array.from({ length: 120 }, (_, i) => {
  const angle = (i / 120) * Math.PI * 2;
  const inner = i % 10 === 0 ? 354 : i % 5 === 0 ? 361 : 366;
  return {
    x1: coordinate(400 + Math.cos(angle) * inner),
    y1: coordinate(400 + Math.sin(angle) * inner),
    x2: coordinate(400 + Math.cos(angle) * 372),
    y2: coordinate(400 + Math.sin(angle) * 372),
    major: i % 10 === 0,
  };
});

const ReactorGeometry = memo(function ReactorGeometry() {
  return (
    <svg className="iris-reactor__geometry" viewBox="0 0 800 800" fill="none" aria-hidden="true">
      <g className="iris-orbit iris-orbit--outer">
        <circle cx="400" cy="400" r="379" stroke="currentColor" strokeOpacity=".13" />
        {TICKS.map((tick, i) => (
          <line
            key={i}
            {...{ x1: tick.x1, y1: tick.y1, x2: tick.x2, y2: tick.y2 }}
            stroke={tick.major ? '#fca55c' : '#65d9ef'}
            strokeOpacity={tick.major ? '.8' : '.34'}
            strokeWidth={tick.major ? 1.5 : 0.65}
          />
        ))}
        <circle
          cx="400"
          cy="400"
          r="345"
          stroke="#50eaff"
          strokeWidth="1.4"
          strokeDasharray="110 680 60 500"
        />
        <circle
          cx="400"
          cy="400"
          r="385"
          stroke="#ff9147"
          strokeWidth="2"
          strokeDasharray="3 22 3 180"
          strokeOpacity=".6"
        />
      </g>
      <g className="iris-orbit iris-orbit--middle">
        <circle
          cx="400"
          cy="400"
          r="294"
          stroke="#60edff"
          strokeWidth="1"
          strokeDasharray="210 280 25 700"
        />
        <circle
          cx="400"
          cy="400"
          r="287"
          stroke="#d4fbff"
          strokeWidth="2"
          strokeDasharray="2 18"
          strokeOpacity=".45"
        />
      </g>
      <g className="iris-orbit iris-orbit--inner">
        <circle
          cx="400"
          cy="400"
          r="117"
          stroke="#70f4ff"
          strokeWidth="2"
          strokeDasharray="100 200 40 395"
        />
        <circle
          cx="400"
          cy="400"
          r="109"
          stroke="#ffb36c"
          strokeWidth="1"
          strokeDasharray="2 14"
          strokeOpacity=".7"
        />
      </g>
      <path d="M400 8v12M400 780v12M8 400h12M780 400h12" stroke="#9ce9f2" strokeOpacity=".5" />
    </svg>
  );
});

export function IrisReactor({
  state = 'standby',
  bands = [],
}: {
  state?: ReactorState;
  bands?: number[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const energy = Math.min(
    1,
    (bands.reduce((sum, band) => sum + band, 0) / Math.max(bands.length, 1)) * 3
  );

  useEffect(() => {
    ref.current?.style.setProperty('--iris-energy', String(energy));
  }, [energy]);

  return (
    <div
      ref={ref}
      className="iris-reactor"
      data-state={state}
      role="img"
      aria-label={`IRIS reactor: ${state}`}
    >
      <div className="iris-reactor__atmosphere" />
      <div className="iris-reactor__image iris-reactor__image--base" />
      <div className="iris-reactor__image iris-reactor__image--core" />
      <div className="iris-reactor__image iris-reactor__image--outer" />
      <div className="iris-reactor__image iris-reactor__image--middle" />
      <div className="iris-reactor__image iris-reactor__image--inner" />
      <div className="iris-reactor__radial-wave iris-reactor__radial-wave--one" />
      <div className="iris-reactor__radial-wave iris-reactor__radial-wave--two" />
      <div className="iris-reactor__corona" />
      <ReactorGeometry />
      <svg className="iris-reactor__spectrum" viewBox="0 0 800 800" aria-hidden="true">
        {Array.from({ length: AUDIO_BANDS }, (_, i) => {
          const angle = (i / AUDIO_BANDS) * Math.PI * 2;
          const level = Math.min(1, (bands[i] ?? 0) * 4);
          const inner = 319;
          const outer = inner + 3 + level * 28;
          return (
            <line
              key={i}
              x1={coordinate(400 + Math.cos(angle) * inner)}
              y1={coordinate(400 + Math.sin(angle) * inner)}
              x2={coordinate(400 + Math.cos(angle) * outer)}
              y2={coordinate(400 + Math.sin(angle) * outer)}
              stroke={i < 8 || i > 24 ? '#ff9c56' : '#69edff'}
              strokeWidth="2.4"
              strokeLinecap="round"
              opacity={0.3 + level * 0.7}
            />
          );
        })}
      </svg>
      <div
        className="iris-reactor__lens"
        style={{ '--lens-scale': 1 + energy * 0.24 } as CSSProperties}
      />
    </div>
  );
}

// The artwork remains mounted. Only this small subtree samples the active audio track.
export function LiveIrisReactor({ phase }: { phase?: ReactorState }) {
  const session = useSessionContext();
  const { state, audioTrack } = useVoiceAssistant();
  const track = state === 'speaking' ? audioTrack : session.local.microphoneTrack;
  const bands = useMultibandTrackVolume(track, {
    bands: AUDIO_BANDS,
    updateInterval: 100,
    analyserOptions: { fftSize: 512, smoothingTimeConstant: 0.85 },
  });
  return <IrisReactor state={phase ?? (session.isConnected ? state : 'standby')} bands={bands} />;
}
