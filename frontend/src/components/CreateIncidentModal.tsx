import React, { useState } from 'react';
import { AlertCircle, FileText, Loader2, Sparkles, X } from 'lucide-react';
import { Incident, IncidentCreatePayload, SeverityLevel } from '../types/api';
import { api } from '../services/api';

interface CreateIncidentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (incident: Incident) => void;
}

const PRESETS: Array<{
  name: string;
  data: IncidentCreatePayload;
}> = [
  {
    name: 'Payment Gateway Timeout (HTTP 504)',
    data: {
      title: 'Payment gateway latency spike with upstream timeouts',
      affected_service: 'payment-gateway',
      severity: 'high',
      description:
        'Checkout service response times degraded above 5,000ms after the v2.4.1 release. Customers experiencing cart checkouts timing out.',
      logs: '2026-09-28T18:40:02Z [ERROR] HTTP 504 TimeoutException: Upstream payment provider socket timed out after 5000ms.\n2026-09-28T18:40:05Z [WARN] Egress connection pool exhausted (active=50, max=50).',
    },
  },
  {
    name: 'Database Pool Exhaustion',
    data: {
      title: 'PostgreSQL connection pool saturation on orders database',
      affected_service: 'orders-db',
      severity: 'critical',
      description:
        'Orders API queries failing with pool wait timeouts. Max client connections (100) reached.',
      logs: '2026-09-28T19:10:00Z [FATAL] DatabaseConnectionError: PoolExhaustion: Timeout waiting for connection from pool after 10000ms.\nActive connections: 100/100.',
    },
  },
  {
    name: 'Redis Eviction Storm',
    data: {
      title: 'Cache eviction storm leading to origin database load',
      affected_service: 'cache-cluster',
      severity: 'medium',
      description:
        'Memory watermark reached on Redis cluster node 3. Maxmemory eviction policy evicted 100k session keys unexpectedly.',
      logs: '2026-09-28T19:15:30Z [WARN] OOM command not allowed when used memory > maxmemory.\nEvicted 120,400 keys in 4.2s.',
    },
  },
];

export const CreateIncidentModal: React.FC<CreateIncidentModalProps> = ({
  isOpen,
  onClose,
  onCreated,
}) => {
  const [title, setTitle] = useState('');
  const [affectedService, setAffectedService] = useState('');
  const [severity, setSeverity] = useState<SeverityLevel>('high');
  const [description, setDescription] = useState('');
  const [logs, setLogs] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleApplyPreset = (preset: (typeof PRESETS)[0]) => {
    setTitle(preset.data.title);
    setAffectedService(preset.data.affected_service);
    setSeverity(preset.data.severity);
    setDescription(preset.data.description);
    setLogs(preset.data.logs || '');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !affectedService.trim() || !description.trim()) {
      setErrorMessage('Title, affected service, and description are required.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const newIncident = await api.createIncident({
        title: title.trim(),
        affected_service: affectedService.trim(),
        severity,
        description: description.trim(),
        logs: logs.trim() ? logs.trim() : null,
      });

      onCreated(newIncident);
      onClose();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to create incident.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-850">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-950 border border-cyan-800 flex items-center justify-center text-cyan-400">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Intake New Incident</h3>
              <p className="text-xs text-slate-400">Record an operational issue in SQLite</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Presets Bar */}
        <div className="px-6 py-2.5 bg-slate-950 border-b border-slate-800/80 flex items-center space-x-2 overflow-x-auto text-xs">
          <div className="flex items-center space-x-1 text-slate-500 shrink-0 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Quick Presets:</span>
          </div>
          {PRESETS.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleApplyPreset(p)}
              className="px-2 py-0.5 rounded bg-slate-800/80 hover:bg-slate-700/80 text-cyan-300 text-[11px] whitespace-nowrap border border-slate-700/60 transition-colors"
            >
              {p.name}
            </button>
          ))}
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          {errorMessage && (
            <div className="p-3 rounded-lg bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Title */}
            <div className="sm:col-span-2 space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Incident Title *</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Payment gateway latency spike"
                className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Severity */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Severity *</label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value as SeverityLevel)}
                className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-cyan-500 capitalize"
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          {/* Affected Service */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Affected Service *</label>
            <input
              type="text"
              required
              value={affectedService}
              onChange={(e) => setAffectedService(e.target.value)}
              placeholder="e.g. payment-gateway, auth-service, orders-db"
              className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Description *</label>
            <textarea
              required
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe symptoms, customer impact, or observed degradation..."
              className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Logs */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-300">Logs / Stack Traces (Optional)</label>
              <span className="text-[10px] text-slate-500">Auto-analyzed for status codes and exceptions</span>
            </div>
            <textarea
              rows={4}
              value={logs}
              onChange={(e) => setLogs(e.target.value)}
              placeholder="Paste raw log lines, error traces, or HTTP response headers..."
              className="w-full px-3 py-2 text-xs font-mono bg-slate-950 border border-slate-800 rounded-lg text-slate-300 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Actions */}
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
              className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-md shadow-cyan-950/40 transition-all disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Recording...</span>
                </>
              ) : (
                <span>Save Incident</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
