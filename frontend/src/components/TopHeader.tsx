import React, { useState, useEffect } from 'react';
import {
  Search,
  Bell,
  Command,
  X,
} from 'lucide-react';

import { Button } from './ui/button';

interface TopHeaderProps {
  unacknowledgedAlertsCount?: number;
  occupancyCount?: number;
  personCount?: number;
  inCount?: number;
  outCount?: number;
  onNotificationClick?: () => void;
  onSearch?: (query: string) => void;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  unacknowledgedAlertsCount = 0,
  occupancyCount = 0,
  personCount = 0,
  inCount = 0,
  outCount = 0,
  onNotificationClick,
  onSearch,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);

  // Global Command-K / Ctrl-K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsSearchModalOpen((prev) => !prev);
      } else if (e.key === 'Escape' && isSearchModalOpen) {
        setIsSearchModalOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchModalOpen]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    onSearch?.(e.target.value);
  };

  const clearSearch = () => {
    setSearchQuery('');
    onSearch?.('');
  };

  return (
    <>
      <header className="h-16 px-6 bg-[#080f22]/90 backdrop-blur-md border-b border-[#162347] flex items-center justify-between gap-4 sticky top-0 z-20">
        {/* Left Side: Clean Surveillance System Status Indicator */}
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-mono font-semibold tracking-wider text-slate-300">
            INTELLIGENCE OPERATIONS LIVE
          </span>
        </div>

        {/* Right Action Cluster */}
        <div className="flex items-center gap-3.5">
          {/* Live Facility Occupancy Pill */}
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#0b132b] border border-[#162347] text-xs font-mono shadow-sm"
            title="Facility Occupancy & Person Detection Telemetry"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-400">PERSONS:</span>
            <span className="text-emerald-400 font-bold">{personCount ?? occupancyCount}</span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400">OCC:</span>
            <span className="text-slate-200 font-semibold">{occupancyCount}</span>
            <span className="text-slate-600">|</span>
            <span className="text-[11px] text-slate-400">IN {inCount} / OUT {outCount}</span>
          </div>

          {/* Notifications Bell */}
          <Button
            onClick={onNotificationClick}
            variant="outline"
            size="icon"
            className="relative h-9 w-9 rounded-xl bg-[#0b132b] hover:bg-[#0e1838] border-[#162347] text-slate-300 hover:text-white"
            title={`${unacknowledgedAlertsCount} unacknowledged alerts`}
          >
            <Bell className="w-4 h-4" />
            {unacknowledgedAlertsCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center border-2 border-[#080f22] animate-pulse">
                {unacknowledgedAlertsCount > 9 ? '9+' : unacknowledgedAlertsCount}
              </span>
            )}
          </Button>
        </div>
      </header>

      {/* Global Command-K Search Modal */}
      {isSearchModalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-start justify-center pt-24 px-4 animate-in fade-in duration-150"
          onClick={() => setIsSearchModalOpen(false)}
        >
          <div
            className="bg-[#0b132b] border border-[#162347] rounded-2xl w-full max-w-lg shadow-2xl p-4 flex flex-col gap-3 animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative flex items-center">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 pointer-events-none" />
              <input
                type="text"
                autoFocus
                value={searchQuery}
                onChange={handleSearchChange}
                placeholder="Search cameras, events, or personnel..."
                className="w-full bg-[#0e1838] border border-[#162347] focus:border-blue-500 rounded-xl pl-10 pr-16 py-2.5 text-sm text-slate-100 placeholder:text-slate-400 focus:outline-none transition-all shadow-inner"
              />
              <div className="absolute right-3 flex items-center gap-1.5">
                {searchQuery && (
                  <button
                    onClick={clearSearch}
                    className="p-1 text-slate-400 hover:text-white rounded"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
                <kbd className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] font-mono text-slate-400">
                  ESC
                </kbd>
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-400 px-1 pt-1 border-t border-[#162347]">
              <span>Filter cameras &amp; live security telemetry</span>
              <span className="flex items-center gap-1 font-mono">
                <Command className="w-3 h-3" /> K to toggle
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default TopHeader;
