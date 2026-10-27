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
} from 'lucide-react';
import { Button } from './ui/button';

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
  onConfigureClick,
  onFocusToggle,
  onSnapshotClick,
  onStreamErrorChange,
}) => {
  const isStandby = camera.sourceType === 'STANDBY';
  const hasStream = !isStandby && camera.streamUrl.length > 0;

  // Build stream URL with optional cache-busting tick if reconnecting
  const streamSrc = hasStream
    ? reconnectTick
      ? `${camera.streamUrl}${camera.streamUrl.includes('?') ? '&' : '?'}t=${reconnectTick}`
      : camera.streamUrl
    : '';

  return (
    <div
      className={`bg-[#0b132b] border rounded-2xl flex flex-col overflow-hidden shadow-xl transition-all duration-200 group ${
        isFocused
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
          {camera.isOnline && !isStandby && (
            <span className="inline-flex items-center gap-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono px-2 py-0.5 rounded-md font-semibold shrink-0 shadow-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Persons: {camera.personCount ?? camera.occupancy ?? 0}
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

            {/* Subtle In-Feed Overlay Badges */}
            <div className="absolute top-2 left-2 pointer-events-none flex items-center gap-1.5">
              <span className="bg-slate-950/75 backdrop-blur-sm text-[10px] font-mono text-emerald-400 px-2 py-0.5 rounded border border-slate-800 flex items-center gap-1.5 shadow-sm">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                {camera.zone}
              </span>
              <span className="bg-slate-950/75 backdrop-blur-sm text-[10px] font-mono text-slate-200 px-2 py-0.5 rounded border border-slate-800 flex items-center gap-1 shadow-sm font-semibold">
                Occupancy: {camera.occupancy ?? camera.personCount ?? 0}
              </span>
            </div>
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

        {/* Action Buttons: Fullscreen & Snapshot */}
        <div className="flex items-center gap-1.5">
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
