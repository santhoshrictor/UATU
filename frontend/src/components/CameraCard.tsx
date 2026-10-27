import React from 'react';
import {
  Calendar,
  Clock,
  Maximize2,
  Minimize2,
  Camera as CameraIcon,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Coffee,
  RotateCcw,
  Flame,
  HardHat,
} from 'lucide-react';
import { Button } from './ui/button';
import type { TeaPointConfig } from './TeaPointControlModal';

export interface CameraCardData {
  id: string;
  name: string;
  zone: string;
  sourceType: string;
  streamUrl: string;
  isOnline: boolean;
  fps: number;
  resolution: string;
  entry?: number;
  exit?: number;
  occupancy?: number;
  personCount?: number;
  deviceId?: number;
}

interface CameraCardProps {
  camera: CameraCardData;
  isFocused?: boolean;
  streamError?: boolean;
  reconnectTick?: number;
  currentTimeString: string;
  currentDateString: string;
  teaPointConfig?: TeaPointConfig | null;
  teaPointCountdownSec?: number;
  teaPointDwellSec?: number;
  teaPointThresholdSec?: number;
  teaPointIsOverstay?: boolean;
  onOpenTeaPointModal?: () => void;
  onTriggerTeaPointException?: () => void;
  onResetTeaPointTimer?: () => void;
  onTriggerFireHazard?: () => void;
  onTriggerPPEViolation?: () => void;
  onConfigureClick: (camera: CameraCardData) => void;
  onFocusToggle: (camera: CameraCardData) => void;
  onSnapshotClick: (camera: CameraCardData) => void;
  onStreamErrorChange?: (camId: string, isErr: boolean) => void;
}

export const CameraCard: React.FC<CameraCardProps> = ({
  camera,
  isFocused = false,
  streamError = false,
  reconnectTick,
  currentTimeString,
  currentDateString,
  teaPointConfig,
  teaPointCountdownSec,
  teaPointDwellSec,
  teaPointThresholdSec,
  teaPointIsOverstay,
  onOpenTeaPointModal,
  onTriggerTeaPointException,
  onResetTeaPointTimer,
  onTriggerFireHazard,
  onTriggerPPEViolation,
  onConfigureClick,
  onFocusToggle,
  onSnapshotClick,
  onStreamErrorChange,
}) => {
  const isStandby = camera.sourceType === 'STANDBY';
  const hasStream = !isStandby && camera.streamUrl.length > 0;

  // Real-time occupancy calculation - accurately reflecting detected person count
  const effectiveOccupancy =
    camera.occupancy && camera.occupancy > 0
      ? camera.occupancy
      : (camera.personCount ?? 0);

  // Real-time countdown calculation & overstay state for CAM-05
  const effectiveThreshold = teaPointThresholdSec ?? teaPointConfig?.threshold_seconds ?? 60;
  const effectiveCountdown =
    teaPointCountdownSec !== undefined
      ? teaPointCountdownSec
      : teaPointDwellSec !== undefined
      ? Math.max(0, effectiveThreshold - teaPointDwellSec)
      : Math.max(0, effectiveThreshold - (teaPointConfig?.current_dwell_seconds || 0));

  const effectiveIsOverstay =
    teaPointIsOverstay ??
    (effectiveCountdown <= 0 && effectiveOccupancy > 0);

  const countdownMins = Math.floor(effectiveCountdown / 60);
  const countdownSecs = Math.floor(effectiveCountdown % 60);
  const threshMins = Math.floor(effectiveThreshold / 60);
  const threshSecs = Math.floor(effectiveThreshold % 60);

  // Build stream URL with optional cache-busting tick if reconnecting
  const streamSrc = hasStream
    ? reconnectTick
      ? `${camera.streamUrl}${camera.streamUrl.includes('?') ? '&' : '?'}t=${reconnectTick}`
      : camera.streamUrl
    : '';

  return (
    <div
      className={`bg-[#0b132b] border rounded-2xl flex flex-col overflow-hidden shadow-xl transition-all duration-300 group ${
        effectiveIsOverstay && camera.id === 'CAM-05'
          ? 'border-red-500/80 shadow-[0_0_28px_rgba(239,68,68,0.35)]'
          : isFocused
          ? 'border-blue-500 shadow-[0_0_24px_rgba(37,99,235,0.25)]'
          : 'border-[#162347] hover:border-[#1e2f5f]'
      }`}
    >
      {/* 1. Card Header */}
      <div className="px-4 py-3 bg-[#0e1838] border-b border-[#162347] flex items-center justify-between gap-2 select-none">
        <div className="flex items-center gap-2 truncate">
          <span className="font-bold text-white text-sm shrink-0 tracking-wide">
            {camera.id}
          </span>
          <span className="text-slate-500 text-xs">|</span>
          <span className="text-slate-300 text-sm font-medium truncate">
            {camera.name}
          </span>
          {camera.id === 'CAM-05' && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onOpenTeaPointModal?.();
              }}
              className="inline-flex items-center gap-1.5 bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/35 text-[10px] font-mono px-2 py-0.5 rounded-md font-semibold cursor-pointer shadow-sm transition-colors"
              title="Click to view Tea Point schedule and compliance settings"
            >
              <Coffee className="w-3 h-3 text-amber-400" />
              <span>Tea Point // 10:00-10:10 AM</span>
            </button>
          )}
          {camera.isOnline && !isStandby && (
            <span className="inline-flex items-center gap-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono px-2 py-0.5 rounded-md font-semibold shrink-0 shadow-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Persons: {effectiveOccupancy}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {/* Live Indicator */}
          <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium">
            <span
              className={`w-2 h-2 rounded-full ${
                camera.isOnline && !isStandby && !streamError
                  ? 'bg-emerald-400 animate-pulse'
                  : streamError
                  ? 'bg-amber-400'
                  : 'bg-slate-600'
              }`}
            />
            <span className="text-xs">
              {camera.isOnline && !isStandby && !streamError
                ? 'Live'
                : streamError
                ? 'Reconnecting'
                : 'Standby'}
            </span>
          </div>

          {/* Three Dots Menu Button -> Opens Camera Config Modal */}
          <Button
            onClick={(e) => {
              e.stopPropagation();
              onConfigureClick(camera);
            }}
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800/60"
            title="Configure Camera Stream Source"
            aria-label={`Configure ${camera.id}`}
          >
            <MoreHorizontal className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* 2. Video Viewport Body */}
      <div
        onClick={() => onFocusToggle(camera)}
        className="relative w-full aspect-video bg-[#040814] flex items-center justify-center cursor-pointer overflow-hidden"
      >
        {hasStream ? (
          <>
            <img
              src={streamSrc}
              alt={`${camera.id} video feed`}
              className={`w-full h-full object-contain select-none transition-opacity duration-200 ${
                streamError ? 'opacity-30' : 'opacity-100'
              }`}
              onLoad={() => onStreamErrorChange?.(camera.id, false)}
              onError={() => onStreamErrorChange?.(camera.id, true)}
            />

            {/* Error Reconnecting Overlay */}
            {streamError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-3 text-center bg-slate-950/80 pointer-events-none">
                <RefreshCw className="w-5 h-5 text-slate-400 animate-spin mb-2" />
                <span className="text-xs font-medium text-slate-400">Connecting stream...</span>
              </div>
            )}

            {/* Subtle In-Feed Overlay Badges (Clean, No Zone Header Text) */}
            <div className="absolute top-2 left-2 pointer-events-none flex items-center gap-1.5 flex-wrap z-10">
              <span className="bg-slate-950/80 backdrop-blur-sm text-[10px] font-mono text-slate-200 px-2.5 py-0.5 rounded-md border border-slate-800 flex items-center gap-1.5 shadow-sm font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Occupancy: {effectiveOccupancy}
              </span>
            </div>

            {/* Bottom-Positioned Dwell Countdown Timer for CAM-05 */}
            {camera.id === 'CAM-05' && (
              <div className="absolute bottom-2.5 left-2.5 right-2.5 pointer-events-none flex items-center justify-between z-10 select-none">
                <div
                  className={`backdrop-blur-md px-3 py-1.5 rounded-xl border font-mono text-xs flex items-center gap-2.5 shadow-xl transition-all duration-300 ${
                    effectiveIsOverstay
                      ? 'bg-red-950/95 border-red-500/80 text-red-200 animate-pulse shadow-[0_0_20px_rgba(239,68,68,0.5)]'
                      : 'bg-[#080f22]/90 border-amber-500/40 text-amber-300 shadow-[0_0_12px_rgba(0,0,0,0.6)]'
                  }`}
                >
                  <Coffee className={`w-4 h-4 ${effectiveIsOverstay ? 'text-red-400 animate-bounce' : 'text-amber-400'}`} />
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
                      {effectiveIsOverstay ? 'Break Expired' : 'Break Countdown'}:
                    </span>
                    <span
                      className={`font-mono font-extrabold text-sm tracking-wider ${
                        effectiveIsOverstay ? 'text-red-400 animate-pulse' : 'text-emerald-400'
                      }`}
                    >
                      {countdownMins}m {countdownSecs < 10 ? `0${countdownSecs}` : countdownSecs}s
                    </span>
                    <span className="text-slate-500 text-[10px]">
                      ({threshMins > 0 ? `${threshMins}m` : ''}{threshSecs > 0 ? ` ${threshSecs}s` : ''} limit)
                    </span>
                  </div>
                  {effectiveIsOverstay && (
                    <span className="ml-1 px-1.5 py-0.5 bg-red-600 text-white text-[9px] rounded-md font-bold uppercase tracking-wider shadow">
                      EXC-05 FIRED
                    </span>
                  )}
                </div>
              </div>
            )}
          </>
        ) : (
          /* Empty / Standby Placeholder */
          <div
            onClick={(e) => {
              e.stopPropagation();
              onConfigureClick(camera);
            }}
            className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center hover:bg-slate-900/40 transition-colors group/standby"
          >
            <div className="w-10 h-10 rounded-full bg-[#0e1838] border border-[#162347] flex items-center justify-center mb-2 group-hover/standby:border-blue-500 group-hover/standby:scale-105 transition-all">
              <Plus className="w-5 h-5 text-slate-400 group-hover/standby:text-blue-400" />
            </div>
            <span className="text-xs font-medium text-slate-300">Unassigned Channel</span>
            <span className="text-[11px] text-slate-500 mt-0.5">Click to assign webcam or RTSP feed</span>
            {camera.id === 'CAM-05' && (
              <span className="inline-flex items-center gap-1 text-[10px] font-mono text-amber-400 mt-1.5 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                <Coffee className="w-3 h-3" />
                <span>Designated Tea Point (10:00 - 10:10 AM)</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* 3. Card Footer */}
      <div className="px-4 py-2.5 bg-[#0e1838] border-t border-[#162347] flex items-center justify-between text-xs text-slate-400 select-none">
        {/* Date and Live Timestamp */}
        <div className="flex items-center gap-2 font-mono text-[11px]">
          <div className="flex items-center gap-1 text-slate-400">
            <Calendar className="w-3.5 h-3.5 text-slate-500" />
            <span>{currentDateString}</span>
          </div>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1 text-slate-300 font-semibold">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>{currentTimeString}</span>
          </div>
        </div>

        {/* Action Buttons: Fullscreen, Snapshot & Tea Point Controls */}
        <div className="flex items-center gap-1.5">
          {camera.id === 'CAM-03' && onTriggerFireHazard && (
            <div className="flex items-center gap-1">
              <Button
                onClick={(e) => {
                  e.stopPropagation();
                  onTriggerFireHazard();
                }}
                variant="ghost"
                size="sm"
                className="h-7 px-2.5 bg-red-500/15 hover:bg-red-500/25 text-red-300 border border-red-500/35 text-[10px] font-mono rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors shadow-sm"
                title="Simulate Fire Hazard (Instant Snapshot & Critical Fire Alert)"
              >
                <Flame className="w-3.5 h-3.5 text-red-400 animate-pulse" />
                <span className="font-semibold">Simulate Fire Hazard</span>
              </Button>
            </div>
          )}

          {camera.id === 'CAM-05' && (
            <div className="flex items-center gap-1">
              {onResetTeaPointTimer && (
                <Button
                  onClick={(e) => {
                    e.stopPropagation();
                    onResetTeaPointTimer();
                  }}
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700 text-[10px] font-mono rounded-lg flex items-center gap-1 cursor-pointer transition-colors shadow-sm"
                  title="Reset Tea Point dwell timer to 0"
                >
                  <RotateCcw className="w-3 h-3 text-slate-400" />
                  <span>Reset</span>
                </Button>
              )}
              {onTriggerTeaPointException && (
                <Button
                  onClick={(e) => {
                    e.stopPropagation();
                    onTriggerTeaPointException();
                  }}
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-[10px] font-mono rounded-lg flex items-center gap-1 cursor-pointer transition-colors shadow-sm"
                  title="Simulate Tea Point Overstay Exception (Instant Snapshot & Alert)"
                >
                  <Coffee className="w-3 h-3 text-amber-400" />
                  <span>Simulate Overstay</span>
                </Button>
              )}
            </div>
          )}

          {onTriggerPPEViolation && (camera.id === 'CAM-04' || camera.id === 'CAM-01') && (
            <div className="flex items-center gap-1">
              <Button
                onClick={(e) => {
                  e.stopPropagation();
                  onTriggerPPEViolation();
                }}
                variant="ghost"
                size="sm"
                className="h-7 px-2.5 bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/35 text-[10px] font-mono rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors shadow-sm"
                title="Simulate PPE Compliance Violation (Missing Hardhat & Safety Vest)"
              >
                <HardHat className="w-3.5 h-3.5 text-amber-400" />
                <span className="font-semibold">Simulate PPE Alert</span>
              </Button>
            </div>
          )}

          <Button
            onClick={(e) => {
              e.stopPropagation();
              onFocusToggle(camera);
            }}
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800/60"
            title={isFocused ? 'Exit focus mode' : 'Expand full feed'}
            aria-label="Toggle focus"
          >
            {isFocused ? (
              <Minimize2 className="w-3.5 h-3.5 text-blue-400" />
            ) : (
              <Maximize2 className="w-3.5 h-3.5" />
            )}
          </Button>

          <Button
            onClick={(e) => {
              e.stopPropagation();
              onSnapshotClick(camera);
            }}
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800/60"
            title="Take evidence snapshot"
            aria-label="Take snapshot"
          >
            <CameraIcon className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default CameraCard;
