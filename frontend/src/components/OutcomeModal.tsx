import React, { useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Loader2,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import { Incident, OutcomeType } from '../types/api';
import { api } from '../services/api';

interface OutcomeModalProps {
  incident: Incident;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (message: string) => void;
}

export const OutcomeModal: React.FC<OutcomeModalProps> = ({
  incident,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [outcome, setOutcome] = useState<OutcomeType>('success');
  const [resolutionAttempted, setResolutionAttempted] = useState('');
  const [engineerNotes, setEngineerNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolutionAttempted.trim()) {
      setErrorMessage('Please describe the resolution action that was attempted.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await api.recordOutcome(incident.id, {
        incident_id: incident.id,
        resolution_attempted: resolutionAttempted.trim(),
        outcome,
        engineer_notes: engineerNotes.trim() ? engineerNotes.trim() : null,
      });

      onSuccess(
        `Outcome recorded successfully (ID: ${response.outcome.id}). Retained in Hindsight bank '${response.bank_id}'!`,
      );
      onClose();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to record outcome and retain memory.',
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-850">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-950 border border-emerald-800 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Record Investigation Outcome</h3>
              <p className="text-xs text-slate-400">
                Confirm resolution for <span className="font-mono text-cyan-300">{incident.id}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMessage && (
            <div className="p-3 rounded-lg bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Outcome Toggle (Success vs Failure) */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Resolution Result *</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setOutcome('success')}
                className={`py-2.5 px-4 rounded-xl border flex items-center justify-center space-x-2 text-xs font-semibold transition-all ${
                  outcome === 'success'
                    ? 'bg-emerald-950/60 border-emerald-500 text-emerald-300 shadow-md shadow-emerald-950/50'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <ThumbsUp className="w-4 h-4" />
                <span>Fix Succeeded</span>
              </button>

              <button
                type="button"
                onClick={() => setOutcome('failure')}
                className={`py-2.5 px-4 rounded-xl border flex items-center justify-center space-x-2 text-xs font-semibold transition-all ${
                  outcome === 'failure'
                    ? 'bg-rose-950/60 border-rose-500 text-rose-300 shadow-md shadow-rose-950/50'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <ThumbsDown className="w-4 h-4" />
                <span>Fix Failed / Did Not Work</span>
              </button>
            </div>
            <p className="text-[11px] text-slate-500">
              {outcome === 'success'
                ? 'Will be stored as a verified historical fix to recommend in future incidents.'
                : 'Will be retained as a known failed fix to warn future responders.'}
            </p>
          </div>

          {/* Resolution Attempted */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">
              Resolution Action Attempted *
            </label>
            <textarea
              required
              rows={3}
              value={resolutionAttempted}
              onChange={(e) => setResolutionAttempted(e.target.value)}
              placeholder="e.g. Scaled egress pool size to 50 and refreshed cached DNS entries in the auth-service container."
              className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Engineer Notes */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">
              Engineer Notes (Optional)
            </label>
            <textarea
              rows={2}
              value={engineerNotes}
              onChange={(e) => setEngineerNotes(e.target.value)}
              placeholder="e.g. Latency normalized within 30s. Recommendation verified on production canary."
              className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Memory Notice Banner */}
          <div className="p-3 rounded-lg bg-indigo-950/30 border border-indigo-800/40 text-[11px] text-indigo-300 flex items-start space-x-2">
            <Database className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
            <span>
              This will update your local SQLite database and retain a memory in Hindsight Cloud
              bank <span className="font-mono text-cyan-300">recallops-dev</span>. It does not run
              scripts or modify production systems.
            </span>
          </div>

          {/* Footer Actions */}
          <div className="pt-2 flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-950/40 transition-all disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Retaining Memory...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Submit & Retain Memory</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
