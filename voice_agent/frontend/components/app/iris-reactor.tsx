'use client';

import {
  type AgentState,
  useMultibandTrackVolume,
  useSessionContext,
  useVoiceAssistant,
} from '@livekit/components-react';

export type ReactorState = AgentState | 'standby' | 'ready';

export function IrisReactor({
  state = 'ready',
  bands = [],
}: {
  state?: ReactorState;
  bands?: number[];
}) {
  const energy = Math.min(
    1,
    (bands.reduce((sum, band) => sum + band, 0) / Math.max(bands.length, 1)) * 3
  );

  return (
    <div
      className="iris-bubble-stage"
      data-state={state}
      role="img"
      aria-label={`IRIS status: ${state}`}
    >
      <div
        className="iris-bubble-wrapper"
        style={{
          transform: `scale(${1 + energy * 0.15})`,
          transition: 'transform 100ms ease-out',
        }}
      >
        <div className="loader loader_bubble" />
      </div>
    </div>
  );
}

export function LiveIrisReactor({ phase }: { phase?: ReactorState }) {
  const session = useSessionContext();
  const { state, audioTrack } = useVoiceAssistant();
  const track = state === 'speaking' ? audioTrack : session.local.microphoneTrack;
  const bands = useMultibandTrackVolume(track, {
    bands: 16,
    updateInterval: 100,
    analyserOptions: { fftSize: 256, smoothingTimeConstant: 0.85 },
  });

  return <IrisReactor state={phase ?? (session.isConnected ? state : 'ready')} bands={bands} />;
}
