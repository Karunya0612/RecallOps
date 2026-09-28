import React from 'react';
import {
  AlertTriangle,
  BookOpen,
  Brain,
  CheckCircle2,
  Cpu,
  Database,
  GitFork,
  HelpCircle,
  Lightbulb,
  Search,
  Shield,
  Tag,
} from 'lucide-react';
import { IncidentAnalysisResponse } from '../types/api';

interface AnalysisViewProps {
  analysis: IncidentAnalysisResponse;
  onOpenOutcome: () => void;
}

export const AnalysisView: React.FC<AnalysisViewProps> = ({ analysis, onOpenOutcome }) => {
  const { extracted_symptoms, recalled_memories, suggestions, has_historical_matches, bank_id } =
    analysis;

  return (
    <div className="space-y-6">
      {/* Top Banner: Analysis Status */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800 shadow-sm">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-cyan-950/80 border border-cyan-800/60 flex items-center justify-center text-cyan-400">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-semibold text-white">Hindsight Cloud Memory Analysis</h3>
              <span
                className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${
                  has_historical_matches
                    ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800/80'
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}
              >
                {has_historical_matches
                  ? `${recalled_memories.length} Historical Matches Found`
                  : 'Zero Historical Matches (Cold Start)'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Target Bank: <span className="font-mono text-cyan-300">{bank_id}</span> • Generated at{' '}
              {new Date(analysis.analyzed_at).toLocaleTimeString()}
            </p>
          </div>
        </div>

        {/* Action Button: Record Outcome */}
        <button
          onClick={onOpenOutcome}
          className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-950/40 transition-all active:scale-[0.98]"
        >
          <CheckCircle2 className="w-4 h-4" />
          <span>Confirm Outcome & Train Memory</span>
        </button>
      </div>

      {/* Section 1: Deterministic Extracted Symptoms */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-5 space-y-4">
        <div className="flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-cyan-400" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
            1. Structured Symptoms & Recall Query
          </h4>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Detected Indicators */}
          <div className="space-y-2">
            <span className="text-xs text-slate-400 font-medium">Detected Technical Indicators:</span>
            <div className="flex flex-wrap gap-1.5">
              {extracted_symptoms.indicators.map((ind, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700/60 text-xs font-mono text-cyan-300"
                >
                  <Tag className="w-3 h-3 text-cyan-400/80" />
                  <span>{ind}</span>
                </span>
              ))}
            </div>
          </div>

          {/* Formulated Query */}
          <div className="space-y-2">
            <span className="text-xs text-slate-400 font-medium">Derived Hindsight Search Query:</span>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 flex items-start space-x-2">
              <Search className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
              <span className="break-all">{extracted_symptoms.recall_query}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Section 2: Recalled Memories from Hindsight Cloud */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Database className="w-4 h-4 text-indigo-400" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
              2. Hindsight Recalled Memory Evidence ({recalled_memories.length})
            </h4>
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            Bank: {bank_id}
          </span>
        </div>

        {recalled_memories.length === 0 ? (
          <div className="p-5 rounded-lg bg-slate-950/60 border border-slate-800/80 text-center space-y-2">
            <HelpCircle className="w-6 h-6 mx-auto text-slate-600" />
            <p className="text-xs text-slate-300 font-medium">
              No matching historical incidents found in memory bank '{bank_id}'
            </p>
            <p className="text-[11px] text-slate-500 max-w-lg mx-auto">
              This is common for new failure modes or fresh service deployments. Below, baseline
              diagnostic suggestions have been generated. Once you verify an outcome, submit it to
              train this memory bank for future incidents.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {recalled_memories.map((mem) => (
              <div
                key={mem.id}
                className="p-4 rounded-lg bg-slate-950 border border-indigo-900/40 hover:border-indigo-700/60 transition-colors space-y-2.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/60 font-semibold">
                      ID: {mem.id}
                    </span>
                    {mem.type && (
                      <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                        {mem.type}
                      </span>
                    )}
                    {mem.context && (
                      <span className="text-[10px] font-mono text-slate-500">
                        context: {mem.context}
                      </span>
                    )}
                  </div>
                  {mem.mentioned_at && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      {new Date(mem.mentioned_at).toLocaleDateString()}
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-200 leading-relaxed font-sans bg-slate-900/60 p-3 rounded border border-slate-800/80">
                  {mem.text}
                </p>

                {mem.entities && mem.entities.length > 0 && (
                  <div className="flex items-center space-x-1.5 text-[11px] text-slate-400 pt-1">
                    <span className="text-slate-500">Entities:</span>
                    {mem.entities.map((e, i) => (
                      <span
                        key={i}
                        className="px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 font-mono text-[10px]"
                      >
                        {e}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Section 3: Evidence-Based Suggestions & Precautions */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-5 space-y-4">
        <div className="flex items-center space-x-2">
          <Lightbulb className="w-4 h-4 text-amber-400" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
            3. Investigation Suggestions & Precautions ({suggestions.length})
          </h4>
        </div>

        <div className="space-y-3">
          {suggestions.map((sug, idx) => {
            const isResolution = sug.category === 'historical_resolution';
            const isPrecaution = sug.category === 'precaution';
            const isObservation = sug.category === 'historical_observation';
            const isCrossService = sug.category === 'cross_service_reference';
            const isGeneral = sug.category === 'general_reference';

            let badgeStyle = 'bg-slate-800 text-slate-300 border-slate-700';
            let icon = <BookOpen className="w-4 h-4 text-cyan-400 shrink-0" />;

            if (isResolution) {
              badgeStyle = 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60';
              icon = <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />;
            } else if (isCrossService) {
              badgeStyle = 'bg-purple-950/70 text-purple-300 border-purple-700/80 font-bold';
              icon = <GitFork className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />;
            } else if (isPrecaution) {
              badgeStyle = 'bg-amber-950/60 text-amber-300 border-amber-800/60';
              icon = <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />;
            } else if (isObservation) {
              badgeStyle = 'bg-indigo-950/60 text-indigo-300 border-indigo-800/60';
              icon = <BookOpen className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />;
            } else if (isGeneral) {
              badgeStyle = 'bg-sky-950/60 text-sky-300 border-sky-800/60';
              icon = <BookOpen className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />;
            }

            return (
              <div
                key={idx}
                className={`p-3.5 rounded-lg border flex items-start space-x-3 transition-colors ${
                  isResolution
                    ? 'bg-emerald-950/20 border-emerald-900/40'
                    : isCrossService
                    ? 'bg-purple-950/20 border-purple-900/50'
                    : isPrecaution
                    ? 'bg-amber-950/20 border-amber-900/40'
                    : 'bg-slate-950 border-slate-800/80'
                }`}
              >
                {icon}
                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border font-semibold ${badgeStyle}`}
                    >
                      {isCrossService ? 'CROSS-SERVICE REFERENCE' : sug.category.replace('_', ' ')}
                    </span>
                    {sug.evidence_source && (
                      <span className="text-[10px] font-mono text-slate-500">
                        source: <span className="text-slate-400 font-semibold">{sug.evidence_source}</span>
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed pt-0.5">{sug.suggestion}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Safety Notice Card */}
      <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800/80 flex items-start space-x-3 text-slate-400 text-xs leading-relaxed">
        <Shield className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
        <p>
          <strong className="text-slate-300">Safety & Engineering Guardrail:</strong> RecallOps does
          not automatically mutate production, restart infrastructure, or close incidents. All
          recommendations cite empirical memory evidence or standard triage baselines. Review and
          validate configuration parity before executing operational changes.
        </p>
      </div>
    </div>
  );
};
