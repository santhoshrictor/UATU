import React, { useState, useEffect, useCallback } from 'react';

interface LiveStatus {
  status: string;
  service: string;
  stage: string;
  timestamp: string;
}

interface DatabaseInfo {
  status: 'connected' | 'unavailable';
  server_version: string | null;
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
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    try {
      // 1. Live probe for application process
      const liveRes = await fetch(`${apiUrl}/api/v1/health/live`, {
        signal: controller.signal,
      });

      if (!liveRes.ok) {
        throw new Error(`Backend live probe returned HTTP ${liveRes.status}`);
      }
      const liveJson: LiveStatus = await liveRes.json();
      setLiveData(liveJson);

      // 2. Readiness probe for database connection and active schema
      const readyRes = await fetch(`${apiUrl}/api/v1/health/ready`, {
        signal: controller.signal,
      });

      const readyJson: ReadyStatus = await readyRes.json();
      setReadyData(readyJson);
      setLastChecked(new Date());
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setFetchError('Request timed out (Backend process unreachable)');
      } else {
        setFetchError(err.message || 'Unable to connect to backend server');
      }
      // Truthfully reset live status on failure so stale green indicators are never displayed as current
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

  // Derived live probe states
  const isBackendConnected = liveData !== null && liveData.status === 'alive';
  const isDatabaseConnected = readyData !== null && readyData.database.status === 'connected';
  const isSchemaVerified = readyData !== null && readyData.schema_status.status === 'verified';
  const isRuntimeReady = isBackendConnected && isDatabaseConnected && isSchemaVerified;

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
            Engineering Foundation & Live Diagnostic Interface
          </p>
        </div>

        {/* Global Status Controls */}
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
            {isLoading ? 'Probing...' : 'Recheck Status'}
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
            Auto Poll (5s)
          </label>
        </div>
      </header>

      {/* Main Runtime Health Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          marginBottom: '28px',
          borderLeft: `5px solid ${
            !isBackendConnected
              ? 'var(--status-red)'
              : !isRuntimeReady
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
                  : !isRuntimeReady
                  ? 'rgba(245, 158, 11, 0.15)'
                  : 'rgba(34, 197, 94, 0.15)',
              }}
            >
              {!isBackendConnected ? '🚨' : !isRuntimeReady ? '⚠️' : '⚡'}
            </div>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#fff' }}>
                {!isBackendConnected
                  ? 'Backend Disconnected or Unreachable'
                  : !isDatabaseConnected
                  ? 'Database Connection Degraded'
                  : !isSchemaVerified
                  ? 'Database Schema Unverified'
                  : 'Backend & Database Service Reachable'}
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '2px' }}>
                {!isBackendConnected
                  ? (fetchError || 'Unable to establish HTTP connection to API server.')
                  : !isDatabaseConnected
                  ? (readyData?.database.error || 'Database connection probe timed out or failed.')
                  : !isSchemaVerified
                  ? 'Alembic version table or required tables (sites, areas) are missing.'
                  : 'Live HTTP health probes active. Offline test acceptance tracked separately in docs/FOUNDATION_ACCEPTANCE.md.'}
              </p>
            </div>
          </div>

          <div style={{ textAlign: 'right', fontSize: '12px', color: 'var(--text-subtle)' }}>
            <div>Last Live Probe:</div>
            <div style={{ fontFamily: 'var(--font-mono)', color: isBackendConnected ? 'var(--text-muted)' : 'var(--status-red)' }}>
              {lastChecked ? lastChecked.toLocaleTimeString() : 'Never'}
            </div>
          </div>
        </div>
      </div>

      {/* Primary Status Diagnostic Grid (Live Probes) */}
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
                Live Probe: Process Liveness
              </span>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fff', marginTop: '4px' }}>
                FastAPI Server
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
              <span>Probe Endpoint:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
                /api/v1/health/live
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Data Source:</span>
              <span style={{ color: 'var(--accent-cyan)' }}>Live HTTP Probe</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Reported Service:</span>
              <span style={{ color: 'var(--text-main)' }}>
                {liveData?.service || 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: PostgreSQL Database Engine (Live Probe) */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
            <div>
              <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-subtle)', fontWeight: 600 }}>
                Live Probe: Database Engine
              </span>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fff', marginTop: '4px' }}>
                Relational Storage
              </h3>
            </div>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                background: isDatabaseConnected ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                color: isDatabaseConnected ? 'var(--status-green)' : 'var(--status-red)',
              }}
            >
              {isDatabaseConnected ? 'CONNECTED' : 'UNAVAILABLE'}
            </span>
          </div>

          <div style={{ fontSize: '13px', color: 'var(--text-muted)', display: 'grid', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Engine Version:</span>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: readyData?.database.server_version ? 'var(--text-main)' : 'var(--status-red)',
                }}
              >
                {readyData?.database.server_version || (isBackendConnected ? 'Not reported' : 'Unavailable')}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Data Source:</span>
              <span style={{ color: 'var(--accent-cyan)' }}>Live SQL query (SELECT version())</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Probe Latency:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
                {readyData?.database.latency_ms !== null && readyData?.database.latency_ms !== undefined
                  ? `${readyData.database.latency_ms} ms`
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Alembic Schema & Tables (Live Probe) */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
            <div>
              <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-subtle)', fontWeight: 600 }}>
                Live Probe: Schema State
              </span>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fff', marginTop: '4px' }}>
                Operational Schema
              </h3>
            </div>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                background: isSchemaVerified ? 'rgba(34, 197, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: isSchemaVerified ? 'var(--status-green)' : 'var(--status-amber)',
              }}
            >
              {isSchemaVerified ? 'VERIFIED' : 'UNVERIFIED'}
            </span>
          </div>

          <div style={{ fontSize: '13px', color: 'var(--text-muted)', display: 'grid', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Active Alembic Revision:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
                {readyData?.schema_status.alembic_version || 'None'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Verified Tables:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                {readyData?.schema_status.tables_present.join(', ') || 'None detected'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Data Source:</span>
              <span style={{ color: 'var(--accent-cyan)' }}>Live inspection on workplace_dev</span>
            </div>
          </div>
        </div>
      </div>

      {/* Traceability & Acceptance Register Separation */}
      <div
        className="glass-panel"
        style={{
          padding: '24px',
          background: 'rgba(15, 23, 42, 0.85)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          marginBottom: '28px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
          <div style={{ fontSize: '24px', lineHeight: 1 }}>📋</div>
          <div style={{ flex: 1 }}>
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#fff', marginBottom: '6px' }}>
              Evidence Traceability & Acceptance Separation Notice
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
              In accordance with project operating rules in <code>AGENTS.md</code>, runtime HTTP health is
              strictly decoupled from offline acceptance test results:
            </p>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                gap: '16px',
                marginTop: '16px',
                paddingTop: '16px',
                borderTop: '1px solid var(--border-subtle)',
              }}
            >
              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', textTransform: 'uppercase', fontWeight: 600 }}>
                  Automated Test Suite (Offline)
                </span>
                <div style={{ color: '#fff', fontSize: '13px', marginTop: '4px' }}>
                  7 of 7 Tests Passed (pytest backend/tests)
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Target: Dedicated isolated database <code>workplace_test</code>
                </div>
              </div>

              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', textTransform: 'uppercase', fontWeight: 600 }}>
                  Tested Code Revision
                </span>
                <div style={{ color: 'var(--accent-cyan)', fontSize: '13px', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                  Commit: 1b2e003
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Working tree clean
                </div>
              </div>

              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', textTransform: 'uppercase', fontWeight: 600 }}>
                  Catalogued Feature Coverage
                </span>
                <div style={{ color: 'var(--status-amber)', fontSize: '13px', marginTop: '4px' }}>
                  0 of 91 Verified (Stage 1 Foundation Only)
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Cameras & models intentionally unconfigured
                </div>
              </div>

              <div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', textTransform: 'uppercase', fontWeight: 600 }}>
                  Acceptance Audit Record
                </span>
                <div style={{ color: '#fff', fontSize: '13px', marginTop: '4px' }}>
                  docs/FOUNDATION_ACCEPTANCE.md
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  7 Passed, 1 Unverified (Playwright driver download 404)
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Diagnostics & Config Drawer */}
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
