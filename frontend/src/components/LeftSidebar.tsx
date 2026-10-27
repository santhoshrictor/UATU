import React from 'react';
import {
  Video,
  AlertTriangle,
  Settings,
  ChevronRight,
  HardHat,
} from 'lucide-react';
import { UATULogo } from './UATULogo';

export type NavTabId =
  | 'live'
  | 'incidents'
  | 'settings'
  | 'access'
  | 'vehicles'
  | 'safety'
  | 'analytics'
  | 'reports'
  | 'cameras';

interface LeftSidebarProps {
  activeTab: NavTabId;
  onSelectTab: (tab: NavTabId) => void;
  systemOnline?: boolean;
  incidentCount?: number;
  onSystemStatusClick?: () => void;
}

interface NavItemConfig {
  id: NavTabId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: number;
}

import { Button } from './ui/button';

export const LeftSidebar: React.FC<LeftSidebarProps> = ({
  activeTab,
  onSelectTab,
  systemOnline = true,
  incidentCount = 0,
  onSystemStatusClick,
}) => {
  const navItems: NavItemConfig[] = [
    { id: 'live', label: 'Live View', icon: Video },
    { id: 'safety', label: 'Safety & PPE', icon: HardHat },
    { id: 'incidents', label: 'Incidents', icon: AlertTriangle, badge: incidentCount },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-[#080f22] border-r border-[#162347] flex flex-col justify-between shrink-0 h-screen sticky top-0 p-5 select-none z-30">
      {/* Top Branding */}
      <div className="flex flex-col">
        <div className="pb-6 border-b border-[#162347]/80">
          <UATULogo />
        </div>

        {/* Navigation Menu */}
        <nav className="mt-5 flex flex-col gap-2" aria-label="Main Navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <Button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                variant={isActive ? 'default' : 'ghost'}
                className={`w-full justify-between px-3.5 py-2.5 h-auto rounded-xl text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-[0_0_16px_rgba(37,99,235,0.35)]'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-[#0e1838]'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>

                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                      isActive
                        ? 'bg-white text-blue-600'
                        : 'bg-red-500/20 text-red-400 border border-red-500/30'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </Button>
            );
          })}
        </nav>
      </div>

      {/* Bottom System Status & Version Card */}
      <div className="pt-4 flex flex-col gap-3">
        <div
          onClick={onSystemStatusClick}
          className="bg-[#0b132b] hover:bg-[#0e1838] border border-[#162347] rounded-xl p-3 flex items-center justify-between transition-colors cursor-pointer group"
          title="System infrastructure status (Click to probe backend & DB)"
        >
          <div className="flex items-center gap-2.5">
            <span
              className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                systemOnline ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : 'bg-red-500'
              }`}
            />
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-slate-100 leading-tight">
                {systemOnline ? 'System Online' : 'System Degraded'}
              </span>
              <span className="text-[11px] text-slate-400 leading-tight mt-0.5">
                {systemOnline ? 'All systems operational' : 'Investigate backend'}
              </span>
            </div>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-slate-300 transition-colors" />
        </div>

        <div className="px-1 text-xs text-slate-500 font-medium">
          UATU <span className="text-slate-600">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
};

export default LeftSidebar;
