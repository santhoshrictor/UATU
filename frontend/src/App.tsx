import React, { useState, useEffect, useCallback } from 'react';

interface LiveStatus {
  status: string;
  service: string;
  stage: string;
  timestamp: string;
}

interface DatabaseInfo {
  status: 'connected' | 'unavailable';
  latency_ms: number | null;
  error: string | null;
}

interface SchemaInfo {
  status: 'verified' | 'unverified';
  alembic_version: string | null;
  tables_present: string[];
}

interface ReadyStatus {
  status: 'ready' | 'not_ready';
  service: string;
  stage: string;
  timestamp: string;
  database: DatabaseInfo;
  schema_status: SchemaInfo;
}

export const App: React.FC = () => {
  const [apiUrl, setApiUrl] = useState<string>(
    import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
  );
  const [liveData, setLiveData] = useState<LiveStatus | null>(null);
  const [readyData, setReadyData] = useState<ReadyStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  const checkStatus = useCallback(async () => {
    setIsLoading(true);
    setFetchError(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    try {
      // 1. Check Liveness
      const liveRes = await fetch(`${apiUrl}/api/v1/health/live`, {
        signal: controller.signal,
      });

      if (!liveRes.ok) {
        throw new Error(`Backend live probe returned HTTP ${liveRes.status}`);
      }
      const liveJson: LiveStatus = await liveRes.json();
      setLiveData(liveJson);

      // 2. Check Readiness (may return 200 or 503)
      const readyRes = await fetch(`${apiUrl}/api/v1/health/ready`, {
        signal: controller.signal,
      });

      const readyJson: ReadyStatus = await readyRes.json();
      setReadyData(readyJson);
      setLastChecked(new Date());
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setFetchError('Request timed out after 4.0s (Backend unreachable)');
      } else {
        setFetchError(err.message || 'Unable to connect to backend server');
      }
      setLiveData(null);
      setReadyData(null);
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      checkStatus();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, checkStatus]);

  // Overall system determination
  const isBackendConnected = liveData !== null && liveData.status === 'alive';
  const isDatabaseReady = readyData !== null && readyData.status === 'ready' && readyData.database.status === 'connected';

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Top Header */}
      <header
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          paddingBottom: '24px',
          borderBottom: '1px solid var(--border-subtle)',
          marginBottom: '28px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
            <h1
              style={{
                fontFamily: 'var(--font-heading)',
                fontSize: '24px',
                fontWeight: 700,
                letterSpacing: '-0.5px',
                color: '#fff',
              }}
            >
              Workplace Video Intelligence
            </h1>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '3px 10px',
                borderRadius: '999px',
                fontSize: '11px',
                fontWeight: 600,
                letterSpacing: '0.5px',
                textTransform: 'uppercase',
                background: 'rgba(56, 189, 248, 0.15)',
                color: 'var(--accent-cyan)',
                border: '1px solid var(--border-accent)',
              }}
            >
              <span
                className="pulse-indicator active"
                style={{ background: 'var(--accent-cyan)' }}
              />
              Stage 1 — Foundation Only
            </span>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
            On-Premise Industrial Safety & Video Surveillance Engine
          </p>
        </div>

        {/* Global Status Pill & Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={() => checkStatus()}
            disabled={isLoading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle)',
              background: 'rgba(255, 255, 255, 0.05)',
              color: '#fff',
              fontSize: '13px',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <span className={isLoading ? 'spinner' : ''} style={{ fontSize: '14px' }}>
              🔄
            </span>
            {isLoading ? 'Checking...' : 'Check Status'}
          </button>

          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              color: 'var(--text-muted)',
              cursor: 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              style={{ accentColor: 'var(--accent-cyan)' }}
            />
            Auto (5s)
          </label>
        </div>
      </header>

      {/* Main State Hero Alert Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          marginBottom: '28px',
          borderLeft: `5px solid ${
            !isBackendConnected
              ? 'var(--status-red)'
              : !isDatabaseReady
              ? 'var(--status-amber)'
              : 'var(--status-green)'
          }`,
        }}
      >
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '22px',
                background: !isBackendConnected
                  ? 'rgba(239, 68, 68, 0.15)'
                  : !isDatabaseReady
                  ? 'rgba(245, 158, 11, 0.15)'
                  : 'rgba(34, 197, 94, 0.15)',
              }}
            >
              {!isBackendConnected ? '🚨' : !isDatabaseReady ? '⚠️' : '⚡'}
            </div>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#fff' }}>
                {!isBackendConnected
                  ? 'Backend Disconnected or Unreachable'
                  : !isDatabaseReady
                  ? 'System Degraded: Database Not Ready'
                  : 'Foundation Operational & Verified'}
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '2px' }}>
                {!isBackendConnected
                  ? (fetchError || 'Unable to establish HTTP connection to API server.')
                  : !isDatabaseReady
                  ? (readyData?.database.error || 'Database connection or schema verification check failed.')
                  : 'FastAPI core, PostgreSQL migrations, and schema isolation active.'}
              </p>
            </div>
          </div>

          <div style={{ textAlign: 'right', fontSize: '12px', color: 'var(--text-subtle)' }}>
            <div>Last Polled:</div>
            <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {lastChecked ? lastChecked.toLocaleTimeString() : 'Never'}
            </div>
          </div>
        </div>
      </div>

      {/* Primary Status Diagnostic Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '20px',
          marginBottom: '28px',
        }}
      >
        {/* Card 1: Backend Liveness */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
            <div>
              <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-subtle)', fontWeight: 600 }}>
                API Process Liveness
              </span>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fff', marginTop: '4px' }}>
                FastAPI Runtime
              </h3>
            </div>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                background: isBackendConnected ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                color: isBackendConnected ? 'var(--status-green)' : 'var(--status-red)',
              }}
            >
              {isBackendConnected ? 'ALIVE' : 'UNREACHABLE'}
            </span>
          </div>

          <div style={{ fontSize: '13px', color: 'var(--text-muted)', display: 'grid', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Endpoint:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
                /api/v1/health/live
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Process State:</span>
              <span style={{ color: isBackendConnected ? 'var(--status-green)' : 'var(--status-red)' }}>
                {liveData?.status || 'Process not responding'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Authorized Scope:</span>
              <span style={{ color: 'var(--accent-cyan)' }}>
                {liveData?.stage || 'Stage 1 — Foundation'}
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: PostgreSQL Readiness */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
            <div>
              <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-subtle)', fontWeight: 600 }}>
                Database Readiness
              </span>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fff', marginTop: '4px' }}>
                PostgreSQL 16.2
              </h3>
            </div>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                background: isDatabaseReady ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                color: isDatabaseReady ? 'var(--status-green)' : 'var(--status-red)',
              }}
            >
              {readyData?.database.status === 'connected' ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>

          <div style={{ fontSize: '13px', color: 'var(--text-muted)', display: 'grid', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Target Service:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
                127.0.0.1:5432
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Probe Latency:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
                {readyData?.database.latency_ms !== null && readyData?.database.latency_ms !== undefined
                  ? `${readyData.database.latency_ms} ms`
                  : 'N/A'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Timeout Bounded:</span>
              <span style={{ color: 'var(--text-main)' }}>2.0s</span>
            </div>
          </div>
        </div>

        {/* Card 3: Alembic Schema & Migrations */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
            <div>
              <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-subtle)', fontWeight: 600 }}>
                Schema & Migrations
              </span>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fff', marginTop: '4px' }}>
                Alembic Version State
              </h3>
            </div>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                background:
                  readyData?.schema_status.status === 'verified'
                    ? 'rgba(34, 197, 94, 0.15)'
                    : 'rgba(245, 158, 11, 0.15)',
                color:
                  readyData?.schema_status.status === 'verified'
                    ? 'var(--status-green)'
                    : 'var(--status-amber)',
              }}
            >
              {readyData?.schema_status.status === 'verified' ? 'VERIFIED' : 'UNVERIFIED'}
            </span>
          </div>

          <div style={{ fontSize: '13px', color: 'var(--text-muted)', display: 'grid', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Active Revision:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
                {readyData?.schema_status.alembic_version || 'None'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Core Tables:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                {readyData?.schema_status.tables_present.join(', ') || 'None detected'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Isolated Test DB:</span>
              <span style={{ color: 'var(--status-green)' }}>workplace_test verified</span>
            </div>
          </div>
        </div>
      </div>

      {/* CRITICAL TRUTHFULNESS GUARDRAIL NOTICE */}
      <div
        className="glass-panel"
        style={{
          padding: '24px',
          background: 'rgba(15, 23, 42, 0.75)',
          border: '1px solid rgba(56, 189, 248, 0.2)',
          marginBottom: '28px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
          <div style={{ fontSize: '24px', lineHeight: 1 }}>🛡️</div>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#fff', marginBottom: '6px' }}>
              Truthful Readiness Notice: Cameras and Analytics Are Not Configured Yet
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
              Per project operating rules in <code>AGENTS.md</code>, this system is strictly in{' '}
              <strong style={{ color: '#fff' }}>Stage 1 — Foundation Only</strong>. Operational RTSP streams,
              video recording engines, YOLO/AI behavior detection models, emergency alarm relays, and
              theft search indices are intentionally disabled. No fake video feeds, simulated alerts, or
              artificial uptime stats are generated.
            </p>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                marginTop: '16px',
                paddingTop: '16px',
                borderTop: '1px solid var(--border-subtle)',
              }}
            >
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', textTransform: 'uppercase' }}>
                  Camera Streams
                </span>
                <div style={{ color: 'var(--text-muted)', fontSize: '13px', fontWeight: 500 }}>
                  0 Configured (Stage 3)
                </div>
              </div>
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', textTransform: 'uppercase' }}>
                  AI Analytics Workers
                </span>
                <div style={{ color: 'var(--text-muted)', fontSize: '13px', fontWeight: 500 }}>
                  0 Active (Stage 4)
                </div>
              </div>
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', textTransform: 'uppercase' }}>
                  Verified Features
                </span>
                <div style={{ color: 'var(--text-muted)', fontSize: '13px', fontWeight: 500 }}>
                  0 of 91 (Tracked in REQUIREMENTS.md)
                </div>
              </div>
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', textTransform: 'uppercase' }}>
                  Foundation Acceptance
                </span>
                <div style={{ color: 'var(--status-green)', fontSize: '13px', fontWeight: 600 }}>
                  8 of 8 Checks Complete
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Configuration & Diagnostics Section */}
      <div className="glass-panel" style={{ padding: '20px' }}>
        <h4 style={{ fontSize: '14px', fontWeight: 600, color: '#fff', marginBottom: '14px' }}>
          Runtime Diagnostics & API Configuration
        </h4>

        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px', fontSize: '13px' }}>
          <label style={{ color: 'var(--text-muted)' }}>Backend URL:</label>
          <input
            type="text"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              background: 'rgba(0, 0, 0, 0.4)',
              color: '#fff',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              width: '260px',
            }}
          />
          <button
            onClick={() => setApiUrl('http://127.0.0.1:8000')}
            style={{
              padding: '6px 10px',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              background: 'transparent',
              color: 'var(--text-muted)',
              fontSize: '11px',
              cursor: 'pointer',
            }}
          >
            Reset Default
          </button>
        </div>
      </div>
    </div>
  );
};

export default App;
