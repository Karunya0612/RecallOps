import React from 'react';
import { Activity, Database, Plus, RefreshCw, Server, ShieldAlert } from 'lucide-react';

interface HeaderProps {
  backendOnline: boolean;
  defaultBank: string | null;
  onRefresh: () => void;
  onOpenCreate: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  backendOnline,
  defaultBank,
  onRefresh,
  onOpenCreate,
  isRefreshing,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30 w-full">
      <div className="w-full px-4 sm:px-5 h-16 flex items-center justify-between gap-3 sm:gap-4">
        {/* Brand */}
        <div className="flex items-center space-x-3 shrink-0">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-indigo-600 to-sky-400 p-0.5 shadow-lg shadow-cyan-950/50 flex items-center justify-center shrink-0">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Activity className="w-5 h-5 text-cyan-400" />
            </div>
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent block">
              RecallOps
            </span>
            <p className="text-xs text-slate-400 hidden sm:block">
              Memory-First AI Incident Recovery & Investigation Assistant
            </p>
          </div>
        </div>

        {/* Status Badges & Actions */}
        <div className="flex items-center space-x-2 sm:space-x-3 shrink-0">
          {/* Synthetic Demo Label */}
          <div className="hidden lg:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-amber-950/30 border border-amber-800/40 text-amber-300 text-xs font-medium shrink-0">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span className="whitespace-nowrap">Advisory Intelligence (Read-Only)</span>
          </div>

          {/* Backend Status Badge */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border text-xs font-medium shrink-0 ${
              backendOnline
                ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-300'
                : 'bg-rose-950/40 border-rose-800/50 text-rose-300'
            }`}
            title={backendOnline ? 'Backend connected (http://127.0.0.1:8000)' : 'Backend unreachable'}
          >
            <Server className="w-3 h-3" />
            <span className="whitespace-nowrap">{backendOnline ? 'Backend 200 OK' : 'Backend Offline'}</span>
          </div>

          {/* Hindsight Bank Badge */}
          <div
            className="hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-indigo-950/40 border border-indigo-800/50 text-indigo-300 text-xs font-medium shrink-0"
            title="Connected Hindsight Memory Bank"
          >
            <Database className="w-3 h-3 text-indigo-400" />
            <span className="whitespace-nowrap">Bank: {defaultBank || 'recallops-dev'}</span>
          </div>

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50 shrink-0"
            title="Refresh Incidents"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
          </button>

          {/* Report Incident CTA */}
          <button
            onClick={onOpenCreate}
            className="inline-flex items-center space-x-1.5 px-3 sm:px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-md shadow-cyan-950/40 transition-all active:scale-[0.98] shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span className="whitespace-nowrap">Intake Incident</span>
          </button>
        </div>
      </div>
    </header>
  );
};
