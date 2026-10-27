import { useEffect } from 'react';
import { toast as sonnerToast } from 'sonner';
import { useAgent, useSessionContext } from '@livekit/components-react';

export function useAgentErrors() {
  const agent = useAgent();
  const session = useSessionContext();

  useEffect(() => {
    if (session.isConnected && agent.state === 'failed') {
      const reasons = agent.failureReasons;
      console.warn('LiveKit Agent state failed:', reasons);

      sonnerToast.info('Voice Agent Reconnecting', {
        description:
          'Voice agent is re-establishing audio telemetry in background. Direct queries & camera focus remain online.',
        duration: 4000,
      });

      // Avoid permanently severing the room; attempt seamless background reconnection
      const timer = setTimeout(async () => {
        try {
          await session.end();
          await session.start();
        } catch (e) {
          console.warn('Background auto-reconnect deferred; direct mode active:', e);
        }
      }, 2000);

      return () => clearTimeout(timer);
    }
  }, [agent.state, agent.failureReasons, session]);
}
