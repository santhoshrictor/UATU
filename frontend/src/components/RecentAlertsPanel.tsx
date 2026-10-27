import React from 'react';
import {
  ShieldAlert,
  HardHat,
  Flame,
  UserX,
  Car,
  AlertTriangle,
  Info,
  ChevronRight,
  RotateCcw,
  CheckCircle2,
  Camera,
} from 'lucide-react';
import type { IncidentAlert } from './IncidentQueue';
import { Button } from './ui/button';

interface RecentAlertsPanelProps {
  alerts: IncidentAlert[];
  unacknowledgedCount?: number;
  onViewAllClick?: () => void;
  onAlertClick?: (alert: IncidentAlert) => void;
  onResetAlerts?: () => void;
  onOpenEvidence?: (alert: IncidentAlert) => void;
  onOpenEvidenceGallery?: () => void;
}

export const RecentAlertsPanel: React.FC<RecentAlertsPanelProps> = ({
  alerts,
  unacknowledgedCount = 0,
  onViewAllClick,
  onAlertClick,
  onResetAlerts,
  onOpenEvidence,
  onOpenEvidenceGallery,
}) => {
  // Helper to choose a fitting category icon based on alert text
  const getAlertIcon = (alert: IncidentAlert) => {
    const text = (alert.type + ' ' + alert.detail).toLowerCase();
    const effectiveSev = (alert.severity || alert.level || 'INFO').toUpperCase();
    const isCrit = effectiveSev === 'CRITICAL';
    const isWarn = effectiveSev === 'WARNING';

    let Icon = AlertTriangle;
    let iconColor = isCrit ? 'text-red-400' : isWarn ? 'text-amber-400' : 'text-blue-400';
    let bgColor = isCrit ? 'bg-red-500/10' : isWarn ? 'bg-amber-500/10' : 'bg-blue-500/10';

    if (text.includes('ppe') || text.includes('helmet') || text.includes('vest')) {
      Icon = HardHat;
      iconColor = 'text-amber-400';
      bgColor = 'bg-amber-500/10';
    } else if (text.includes('fire') || text.includes('smoke')) {
      Icon = Flame;
      iconColor = 'text-amber-400';
      bgColor = 'bg-amber-500/10';
    } else if (text.includes('vehicle') || text.includes('car') || text.includes('gate')) {
      Icon = Car;
      iconColor = 'text-blue-400';
      bgColor = 'bg-blue-500/10';
    } else if (text.includes('intrusion') || text.includes('unauthorized') || text.includes('fall')) {
      Icon = ShieldAlert;
      iconColor = 'text-red-400';
      bgColor = 'bg-red-500/10';
    } else if (text.includes('tailgating') || text.includes('mismatch')) {
      Icon = UserX;
      iconColor = isCrit ? 'text-red-400' : 'text-amber-400';
      bgColor = isCrit ? 'bg-red-500/10' : 'bg-amber-500/10';
    } else if (!isCrit && !isWarn) {
      Icon = Info;
      iconColor = 'text-blue-400';
      bgColor = 'bg-blue-500/10';
    }

    return (
      <div className={`w-8 h-8 rounded-full ${bgColor} flex items-center justify-center shrink-0`}>
        <Icon className={`w-4 h-4 ${iconColor}`} />
      </div>
    );
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
            Critical
          </span>
        );
      case 'WARNING':
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Warning
          </span>
        );
      case 'INFO':
      default:
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Info
          </span>
        );
    }
  };

  return (
    <aside className="w-80 bg-[#080f22] border-l border-[#162347] flex flex-col shrink-0 h-screen sticky top-0 p-5 overflow-hidden z-20">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-4 border-b border-[#162347]">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-bold text-white tracking-tight">Recent Alerts</h2>
          {unacknowledgedCount > 0 && (
            <span className="text-[11px] font-bold px-1.5 py-0.2 rounded-full bg-red-500 text-white">
              {unacknowledgedCount}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {onOpenEvidenceGallery && (
            <Button
              onClick={onOpenEvidenceGallery}
              variant="ghost"
              size="sm"
              className="text-xs font-mono text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10 flex items-center gap-1.5 h-7 px-2 rounded-lg border border-emerald-500/20"
              title="Open Forensic Snapshot Evidence Gallery"
            >
              <Camera className="w-3.5 h-3.5" />
              <span>Evidence</span>
            </Button>
          )}

          <Button
            onClick={onViewAllClick}
            variant="ghost"
            size="sm"
            className="text-xs font-medium text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 flex items-center gap-1 h-7 px-2.5 rounded-lg"
          >
            <span>View All</span>
            <span aria-hidden="true">&rarr;</span>
          </Button>
        </div>
      </div>

      {/* Alert Cards List */}
      <div className="flex-1 overflow-y-auto divide-y divide-[#162347]/50 -mx-2 px-2 mt-2">
        {alerts.length === 0 ? (
          <div className="py-16 text-center flex flex-col items-center justify-center">
            <CheckCircle2 className="w-8 h-8 text-emerald-400/80 mb-2" />
            <span className="text-xs font-semibold text-slate-300">All Systems Nominal</span>
            <span className="text-[11px] text-slate-500 mt-1 max-w-[200px]">
              No active security incidents or safety violations reported.
            </span>
          </div>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              onClick={() => onAlertClick?.(alert)}
              className="py-3 px-2 rounded-xl hover:bg-[#0b132b] cursor-pointer transition-colors group flex items-center justify-between gap-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                {getAlertIcon(alert)}

                <div className="flex flex-col min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-slate-100 truncate group-hover:text-blue-400 transition-colors">
                      {alert.type}
                    </span>
                    {getSeverityBadge(alert.severity || alert.level || 'INFO')}
                  </div>

                  <span className="text-[11px] text-slate-400 truncate mt-0.5">
                    {alert.camera ? `${alert.camera} · ` : ''}
                    {alert.zone}
                  </span>

                  <span className="text-[10px] font-mono text-slate-500 mt-0.5">
                    {alert.timestamp || alert.time}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1">
                {(alert.snapshot_url || (alert.severity || alert.level) === 'CRITICAL' || onOpenEvidence) && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenEvidence?.(alert);
                    }}
                    className="p-1 rounded-md text-slate-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                    title="Inspect Evidence Snapshot"
                  >
                    <Camera className="w-3.5 h-3.5" />
                  </button>
                )}
                <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-300 transition-colors shrink-0" />
              </div>
            </div>
          ))
        )}
      </div>

      {/* Bottom Actions */}
      {alerts.length > 0 && onResetAlerts && (
        <div className="pt-3 border-t border-[#162347] flex justify-end">
          <Button
            onClick={onResetAlerts}
            variant="ghost"
            size="sm"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 h-7 px-2.5 rounded-lg"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset Alert Queue</span>
          </Button>
        </div>
      )}
    </aside>
  );
};

export default RecentAlertsPanel;
