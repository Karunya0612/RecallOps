import React, { useState } from 'react';
import {
  AlertCircle,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Code2,
  Loader2,
  Play,
  SlidersHorizontal,
} from 'lucide-react';
import { Incident, IncidentAnalysisResponse } from '../types/api';
import { api } from '../services/api';
import { AnalysisView } from './AnalysisView';

interface IncidentDetailProps {
  incident: Incident;
  analysis: IncidentAnalysisResponse | null;
  onAnalysisUpdated: (analysis: IncidentAnalysisResponse) => void;
  onOpenOutcome: () => void;
}

export const IncidentDetail: React.FC<IncidentDetailProps> = ({
  incident,
  analysis,
  onAnalysisUpdated,
  onOpenOutcome,
}) => {
  const [showLogs, setShowLogs] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [queryOverride, setQueryOverride] = useState('');
  const [maxTokens, setMaxTokens] = useState<number | ''>('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const handleRunAnalysis = async () => {
    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      const response = await api.analyzeIncident(incident.id, {
        query_override: queryOverride.trim() ? queryOverride.trim() : null,
        max_tokens: typeof maxTokens === 'number' && maxTokens > 0 ? maxTokens : null,
      });
      onAnalysisUpdated(response);
    } catch (err) {
      setAnalysisError(
        err instanceof Error ? err.message : 'Analysis failed. Check backend and Hindsight connection.',
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-slate-950 p-6 space-y-6">
      {/* Incident Header Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1.5 flex-1">
            <div className="flex items-center space-x-2">
              <span className="font-mono text-xs text-cyan-400 bg-cyan-950/70 border border-cyan-800/80 px-2 py-0.5 rounded font-semibold">
                {incident.id}
              </span>
              <span className="text-xs font-mono text-slate-500 uppercase px-2 py-0.5 rounded bg-slate-800">
                Service: <span className="text-slate-300 font-semibold">{incident.affected_service}</span>
              </span>
              <span className="text-xs font-mono text-slate-500 px-2 py-0.5 rounded bg-slate-800 capitalize">
                Severity: <span className="text-slate-300 font-semibold">{incident.severity}</span>
              </span>
            </div>
            <h1 className="text-xl font-bold text-white tracking-tight">{incident.title}</h1>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={onOpenOutcome}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-700/60 text-xs font-semibold transition-all"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Record Outcome</span>
            </button>
          </div>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/50 p-3.5 rounded-xl border border-slate-800/80">
          {incident.description}
        </p>

        {/* Timestamps & Log Toggle */}
        <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
          <div className="flex items-center space-x-1 font-mono">
            <Clock className="w-3.5 h-3.5 text-slate-600" />
            <span>Reported: {new Date(incident.created_at).toLocaleString()}</span>
          </div>

          {incident.logs && (
            <button
              onClick={() => setShowLogs(!showLogs)}
              className="inline-flex items-center space-x-1 text-slate-400 hover:text-cyan-400 transition-colors font-mono text-[11px]"
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>{showLogs ? 'Hide Raw Logs' : 'View Raw Logs'}</span>
              {showLogs ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>

        {/* Collapsible Raw Logs */}
        {showLogs && incident.logs && (
          <div className="mt-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-300 whitespace-pre-wrap overflow-x-auto max-h-52">
            {incident.logs}
          </div>
        )}
      </div>

      {/* Analysis Control Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-0.5">
            <h2 className="text-sm font-semibold text-white flex items-center space-x-2">
              <Brain className="w-4 h-4 text-cyan-400" />
              <span>Hindsight Memory Recall & Investigation</span>
            </h2>
            <p className="text-xs text-slate-400">
              Correlates symptoms with past incidents and verified resolutions in Hindsight Cloud.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={`p-2 rounded-lg border text-xs flex items-center space-x-1.5 transition-colors ${
                showAdvanced
                  ? 'bg-slate-800 text-cyan-300 border-cyan-700/60'
                  : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
              }`}
              title="Toggle query override and token budget options"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span>Tuning</span>
            </button>

            <button
              onClick={handleRunAnalysis}
              disabled={isAnalyzing}
              className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 via-sky-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-md shadow-cyan-950/50 transition-all active:scale-[0.98] disabled:opacity-50"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Recalling Memories...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>{analysis ? 'Re-run Analysis' : 'Run Hindsight Analysis'}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Optional Advanced Query Override */}
        {showAdvanced && (
          <div className="pt-3 border-t border-slate-800/80 grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-2 space-y-1">
              <label className="text-[11px] font-medium text-slate-400">
                Custom Recall Query Override (Optional)
              </label>
              <input
                type="text"
                value={queryOverride}
                onChange={(e) => setQueryOverride(e.target.value)}
                placeholder="Leave blank to use automated symptom extraction..."
                className="w-full px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 font-mono"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-medium text-slate-400">
                Max Token Budget (Optional, 1–4000)
              </label>
              <input
                type="number"
                min={1}
                max={4000}
                value={maxTokens}
                onChange={(e) =>
                  setMaxTokens(e.target.value === '' ? '' : parseInt(e.target.value, 10))
                }
                placeholder="Default budget"
                className="w-full px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 font-mono"
              />
            </div>
          </div>
        )}

        {/* Error Banner */}
        {analysisError && (
          <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/80 text-rose-300 text-xs flex items-start space-x-2.5">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-rose-200">Analysis Request Failed</p>
              <p className="mt-0.5">{analysisError}</p>
            </div>
          </div>
        )}
      </div>

      {/* Analysis Output View */}
      {analysis && <AnalysisView analysis={analysis} onOpenOutcome={onOpenOutcome} />}

      {!analysis && !isAnalyzing && (
        <div className="p-12 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/30 space-y-3">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-slate-850 flex items-center justify-center text-slate-500 border border-slate-800">
            <Brain className="w-6 h-6 text-slate-600" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-300">No Memory Analysis Run Yet</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Click &quot;Run Hindsight Analysis&quot; above to extract deterministic symptoms and
              search the memory bank for historical incident resolutions.
            </p>
          </div>
          <button
            onClick={handleRunAnalysis}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-600/30 hover:bg-cyan-600/40 text-cyan-300 border border-cyan-700/60 text-xs font-medium transition-all"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Analyze Now</span>
          </button>
        </div>
      )}
    </div>
  );
};
