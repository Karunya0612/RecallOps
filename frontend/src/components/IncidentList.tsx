import React, { useState } from 'react';
import { Clock, Filter, Inbox, Layers, Search } from 'lucide-react';
import { Incident, SeverityLevel } from '../types/api';

interface IncidentListProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  onSelectIncident: (id: string) => void;
  isLoading: boolean;
  onOpenCreate: () => void;
}

const severityConfig: Record<
  SeverityLevel,
  { bg: string; text: string; border: string; label: string }
> = {
  critical: {
    bg: 'bg-rose-950/40',
    text: 'text-rose-400',
    border: 'border-rose-800/60',
    label: 'Critical',
  },
  high: {
    bg: 'bg-amber-950/40',
    text: 'text-amber-400',
    border: 'border-amber-800/60',
    label: 'High',
  },
  medium: {
    bg: 'bg-yellow-950/40',
    text: 'text-yellow-400',
    border: 'border-yellow-800/60',
    label: 'Medium',
  },
  low: {
    bg: 'bg-sky-950/40',
    text: 'text-sky-400',
    border: 'border-sky-800/60',
    label: 'Low',
  },
};

export const IncidentList: React.FC<IncidentListProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  isLoading,
  onOpenCreate,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  const filteredIncidents = incidents.filter((inc) => {
    const matchesSearch =
      inc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.affected_service.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSeverity = severityFilter === 'all' || inc.severity === severityFilter;
    return matchesSearch && matchesSeverity;
  });

  return (
    <div className="flex flex-col h-full bg-slate-900 border-r border-slate-800">
      {/* Header & Filter Controls */}
      <div className="p-4 border-b border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-slate-200">Incident Registry</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
              {incidents.length}
            </span>
          </div>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search service, title, or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>

        {/* Severity Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
          <Filter className="w-3.5 h-3.5 text-slate-500 shrink-0 mr-1" />
          {['all', 'critical', 'high', 'medium', 'low'].map((level) => (
            <button
              key={level}
              onClick={() => setSeverityFilter(level)}
              className={`px-2 py-0.5 rounded-md capitalize transition-all ${
                severityFilter === level
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-700/60 font-medium'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      {/* Incident Cards List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse space-y-2 p-3 rounded-lg bg-slate-800/40">
                <div className="h-4 bg-slate-700/50 rounded w-3/4"></div>
                <div className="h-3 bg-slate-700/40 rounded w-1/2"></div>
                <div className="h-2 bg-slate-700/30 rounded w-1/4"></div>
              </div>
            ))}
          </div>
        ) : filteredIncidents.length === 0 ? (
          <div className="p-8 text-center space-y-3">
            <div className="w-12 h-12 mx-auto rounded-full bg-slate-800/60 flex items-center justify-center text-slate-500">
              <Inbox className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-300">No incidents match</p>
              <p className="text-xs text-slate-500 mt-1">
                {incidents.length === 0
                  ? 'Get started by creating your first incident.'
                  : 'Try adjusting your search query or filters.'}
              </p>
            </div>
            {incidents.length === 0 && (
              <button
                onClick={onOpenCreate}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-600/80 hover:bg-cyan-500 text-white text-xs font-medium transition-all"
              >
                <span>Report Incident</span>
              </button>
            )}
          </div>
        ) : (
          filteredIncidents.map((incident) => {
            const isSelected = incident.id === selectedIncidentId;
            const sev = severityConfig[incident.severity] || severityConfig.medium;
            const timeAgo = new Date(incident.created_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            });

            return (
              <div
                key={incident.id}
                onClick={() => onSelectIncident(incident.id)}
                className={`p-3.5 cursor-pointer transition-all border-l-2 ${
                  isSelected
                    ? 'bg-slate-800/70 border-cyan-400'
                    : 'hover:bg-slate-850/50 border-transparent'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span
                    className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border ${sev.bg} ${sev.text} ${sev.border}`}
                  >
                    {sev.label}
                  </span>
                  <span className="text-[11px] font-mono text-slate-500 flex items-center space-x-1">
                    <Clock className="w-3 h-3 inline mr-0.5 text-slate-600" />
                    <span>{timeAgo}</span>
                  </span>
                </div>

                <h3 className="text-xs font-semibold text-slate-200 mt-1.5 line-clamp-1">
                  {incident.title}
                </h3>

                <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-2 leading-relaxed">
                  {incident.description}
                </p>

                <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="font-mono text-slate-400 bg-slate-950/60 px-1.5 py-0.5 rounded border border-slate-800">
                    {incident.affected_service}
                  </span>
                  <span className="text-[10px] font-mono text-slate-600">{incident.id}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
