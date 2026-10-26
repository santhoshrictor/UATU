'use client';

import { useEffect, useMemo, useState } from 'react';
import { LogLevel, Room, TokenSource } from 'livekit-client';
import { useSession } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react/dist/ssr';
import type { AppConfig } from '@/app-config';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { IrisConsole } from '@/components/app/iris-console';
import { Toaster } from '@/components/ui/sonner';
import { useAgentErrors } from '@/hooks/useAgentErrors';
import { useDebugMode } from '@/hooks/useDebug';
import { VOICE_CAPTURE_DEFAULTS } from '@/lib/iris-audio';

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';

function AppSetup() {
  useDebugMode({ enabled: IN_DEVELOPMENT, logLevel: LogLevel.warn });
  useAgentErrors();

  return null;
}

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const tokenSource = useMemo(() => {
    return TokenSource.endpoint('/api/token');
  }, []);

  const room = useMemo(
    () =>
      new Room({
        audioCaptureDefaults: VOICE_CAPTURE_DEFAULTS,
        adaptiveStream: true,
        dynacast: true,
      }),
    []
  );

  const session = useSession(tokenSource, {
    room,
    agentConnectTimeoutMilliseconds: 60_000,
    ...(appConfig.agentName ? { agentName: appConfig.agentName } : {}),
  });

  useEffect(() => {
    const room = session.room;
    return () => {
      void room.disconnect();
    };
  }, [session.room]);

  if (!mounted) {
    return (
      <div className="iris-console" data-phase="standby" suppressHydrationWarning>
        <div className="iris-console__texture" aria-hidden="true" />
      </div>
    );
  }

  return (
    <AgentSessionProvider session={session}>
      <AppSetup />
      <IrisConsole appConfig={appConfig} />
      <StartAudioButton label="Start Audio" />
      <Toaster
        icons={{
          warning: <WarningIcon weight="bold" />,
        }}
        position="top-center"
        className="toaster group"
        style={
          {
            '--normal-bg': 'var(--popover)',
            '--normal-text': 'var(--popover-foreground)',
            '--normal-border': 'var(--border)',
          } as React.CSSProperties
        }
      />
    </AgentSessionProvider>
  );
}
