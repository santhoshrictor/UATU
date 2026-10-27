import React from 'react';
import {
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  Check,
  Camera,
} from 'lucide-react';
import { Button } from './ui/button';

export type AlertSeverity = 'CRITICAL' | 'WARNING' | 'INFO';

export interface IncidentAlert {
  id: string;
  timestamp: string;
  time?: string;
  zone: string;
  camera?: string;
  type: string;
  severity: AlertSeverity;
  level?: AlertSeverity;
  detail: string;
  snapshot_url?: string;
  confidence_pct?: number;
  acknowledged: boolean;
  acknowledgedAt?: string;
  eventRef?: string;
}

export interface IncidentQueueProps {
  alerts: IncidentAlert[];
  unacknowledgedCount: number;
  alertFilter: 'ALL' | 'UNACKNOWLEDGED';
  onFilterChange: (filter: 'ALL' | 'UNACKNOWLEDGED') => void;
  onToggleAcknowledge: (id: string) => void;
  onResetAlerts: () => void;
  onOpenEvidence?: (alert: IncidentAlert) => void;
  onOpenEvidenceGallery?: () => void;
}

export const IncidentQueue: React.FC<IncidentQueueProps> = ({
  alerts,
  unacknowledgedCount,
  alertFilter,
  onFilterChange,
  onToggleAcknowledge,
  onResetAlerts,
  onOpenEvidence,
  onOpenEvidenceGallery,
}) => {
  const filteredAlerts = React.useMemo(() => {
    if (alertFilter === 'UNACKNOWLEDGED') {
      return alerts.filter((a) => !a.acknowledged);
    }
    return alerts;
  }, [alerts, alertFilter]);

  return (
    <div className="bg-[#0f172a] rounded-lg border border-[#1e293b] shadow-xl flex flex-col h-full overflow-hidden">
      {/* Header with Active Unacknowledged Count & Reset Action */}
      <div className="p-4 bg-slate-900/90 border-b border-[#1e293b] flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          <div>
            <h2 className="font-mono text-sm sm:text-base font-bold text-slate-100 tracking-wide uppercase">
              Incident Dispatch Queue
            </h2>
            <p className="text-[11px] text-slate-400 font-sans">
              Priority-coded real-time security events
            </p>
          </div>
        </div>

        {/* Action Controls: Evidence Gallery, Reset Alerts & Active Count Pill */}
        <div className="flex items-center gap-2">
          {onOpenEvidenceGallery && (
            <Button
              onClick={onOpenEvidenceGallery}
              variant="ghost"
              size="sm"
              className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg bg-emerald-950/40 hover:bg-emerald-900/50 text-emerald-300 border border-emerald-500/30 transition-all font-mono text-xs shadow-sm cursor-pointer"
              title="Open Forensic Snapshot Evidence Gallery"
            >
              <Camera className="w-3.5 h-3.5" />
              <span>Evidence Gallery</span>
            </Button>
          )}

          <Button
            id="btn-reset-alerts"
            onClick={onResetAlerts}
            variant="ghost"
            size="sm"
            className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white transition-all font-mono text-xs shadow-sm cursor-pointer border border-slate-700/80"
            title="Clear visible incident queue in frontend view (backend logs preserved for IRIS)"
          >
            <RotateCcw className="w-3 h-3 text-slate-400 group-hover:text-amber-400 transition-colors" />
            <span>Reset Alerts</span>
          </Button>

          <div
            className={`px-2.5 py-1 rounded-full font-mono text-xs font-bold border ${
              unacknowledgedCount > 0
                ? 'bg-red-950/40 text-red-400 border-red-500/40 animate-pulse'
                : 'bg-emerald-950/40 text-emerald-400 border-emerald-500/40'
            }`}
          >
            {unacknowledgedCount} ACTIVE
          </div>
        </div>
      </div>

      {/* Filter Sub-Bar */}
      <div className="px-4 py-2 bg-slate-950/70 border-b border-slate-800 flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-2 text-slate-400">
          <span>FILTER:</span>
          <Button
            onClick={() => onFilterChange('ALL')}
            variant={alertFilter === 'ALL' ? 'default' : 'ghost'}
            size="sm"
            className={`h-6 px-2.5 rounded text-xs font-mono transition-all ${
              alertFilter === 'ALL'
                ? 'bg-blue-600 hover:bg-blue-500 text-white font-semibold'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            ALL ({alerts.length})
          </Button>
          <Button
            onClick={() => onFilterChange('UNACKNOWLEDGED')}
            variant={alertFilter === 'UNACKNOWLEDGED' ? 'default' : 'ghost'}
            size="sm"
            className={`h-6 px-2.5 rounded text-xs font-mono transition-all ${
              alertFilter === 'UNACKNOWLEDGED'
                ? 'bg-blue-600 hover:bg-blue-500 text-white font-semibold'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            UNACK ({unacknowledgedCount})
          </Button>
        </div>

        <span className="text-[10px] text-slate-500 uppercase tracking-wider">
          AUTO-DISPATCH ON
        </span>
      </div>

      {/* Scrollable Incident Cards List */}
      <div className="p-4 flex-1 overflow-y-auto space-y-3.5 max-h-[750px]">
        {filteredAlerts.length === 0 ? (
          <div className="text-center py-12 text-slate-500 font-mono text-xs">
            <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-slate-600" />
            NO INCIDENTS IN CURRENT VIEW
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const isCrit = alert.severity === 'CRITICAL';
            const isWarn = alert.severity === 'WARNING';

            return (
              <div
                key={alert.id}
                className={`rounded-lg border p-3.5 transition-all duration-200 ${
                  alert.acknowledged
                    ? 'bg-slate-950/40 border-slate-800/60 opacity-60'
                    : isCrit
                    ? 'bg-red-950/20 border-red-900/50 hover:border-red-700/60 shadow-lg shadow-red-950/10'
                    : isWarn
                    ? 'bg-amber-950/20 border-amber-900/50 hover:border-amber-700/60 shadow-lg shadow-amber-950/10'
                    : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                }`}
              >
                {/* Top Row: Severity, Event ID, Timestamp */}
                <div className="flex items-center justify-between gap-2 mb-2 font-mono text-xs">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${
                        isCrit
                          ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                          : isWarn
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          : 'bg-slate-800 text-slate-300 border border-slate-700'
                      }`}
                    >
                      {alert.severity}
                    </span>
                    <span className="font-semibold text-slate-300">{alert.id}</span>
                  </div>
                  <span className="text-[11px] text-slate-400">{alert.timestamp || alert.time}</span>
                </div>

                {/* Zone Identifier */}
                <div className="text-[11px] font-mono text-emerald-400/90 mb-1 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>{alert.camera ? `${alert.camera} • ${alert.zone}` : alert.zone}</span>
                </div>

                {/* Alert Type Heading */}
                <div className="text-xs sm:text-sm font-semibold text-slate-100 mb-1.5 font-mono">
                  {alert.type}
                </div>

                {/* Detail Message */}
                <p className="text-xs text-slate-300 leading-relaxed font-sans mb-3">
                  {alert.detail}
                </p>

                {/* Card Footer: Acknowledge Action Button */}
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
                  <span className="text-[10px] text-slate-500">
                    {alert.eventRef ? `REF: ${alert.eventRef}` : 'DISPATCH PROTOCOL'}
                  </span>

                  <div className="flex items-center gap-2">
                    {onOpenEvidence && (
                      <Button
                        onClick={() => onOpenEvidence(alert)}
                        variant="ghost"
                        size="sm"
                        className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-xs font-mono text-blue-400 hover:text-white bg-blue-950/40 hover:bg-blue-900/50 border border-blue-500/30 transition-all cursor-pointer"
                        title="View frame snapshot & forensic metadata"
                      >
                        <Camera className="w-3.5 h-3.5" />
                        <span>Evidence</span>
                      </Button>
                    )}

                    <Button
                      onClick={() => onToggleAcknowledge(alert.id)}
                      variant={alert.acknowledged ? 'secondary' : 'default'}
                      size="sm"
                      className={`flex items-center gap-1.5 h-7 px-3 rounded-lg text-xs font-mono font-medium transition-all ${
                        alert.acknowledged
                          ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-500/30 hover:bg-slate-800'
                          : 'bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 hover:border-slate-500'
                      }`}
                    >
                      {alert.acknowledged ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Acknowledged</span>
                        </>
                      ) : (
                        <>
                          <Check className="w-3.5 h-3.5 text-slate-400" />
                          <span>Acknowledge</span>
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default IncidentQueue;
