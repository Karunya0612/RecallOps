import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { IncidentList } from './components/IncidentList';
import { IncidentDetail } from './components/IncidentDetail';
import { CreateIncidentModal } from './components/CreateIncidentModal';
import { OutcomeModal } from './components/OutcomeModal';
import { Incident, IncidentAnalysisResponse } from './types/api';
import { api } from './services/api';
import { AlertCircle, CheckCircle2, Inbox } from 'lucide-react';

export const App: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [analyses, setAnalyses] = useState<Record<string, IncidentAnalysisResponse>>({});
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [defaultBank, setDefaultBank] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [isOutcomeOpen, setIsOutcomeOpen] = useState<boolean>(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 5000);
  };

  const fetchStatus = async () => {
    try {
      const health = await api.checkHealth();
      setBackendOnline(health.status === 'ok');

      const bank = await api.getDefaultBank();
      setDefaultBank(bank.default_bank_id);
    } catch {
      setBackendOnline(false);
    }
  };

  const fetchIncidents = async () => {
    try {
      const response = await api.listIncidents(50, 0);
      setIncidents(response.items);
      if (!selectedIncidentId && response.items.length > 0) {
        setSelectedIncidentId(response.items[0].id);
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to fetch incidents', 'error');
    }
  };

  const handleInitialLoad = async () => {
    setIsLoading(true);
    await Promise.all([fetchStatus(), fetchIncidents()]);
    setIsLoading(false);
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([fetchStatus(), fetchIncidents()]);
    setIsRefreshing(false);
  };

  useEffect(() => {
    handleInitialLoad();
  }, []);

  const selectedIncident = incidents.find((i) => i.id === selectedIncidentId) || null;
  const currentAnalysis = selectedIncident ? analyses[selectedIncident.id] || null : null;

  const handleIncidentCreated = (newIncident: Incident) => {
    setIncidents((prev) => [newIncident, ...prev]);
    setSelectedIncidentId(newIncident.id);
    showToast(`Incident ${newIncident.id} created successfully.`);
  };

  const handleAnalysisUpdated = (newAnalysis: IncidentAnalysisResponse) => {
    setAnalyses((prev) => ({
      ...prev,
      [newAnalysis.incident_id]: newAnalysis,
    }));
    showToast(`Analysis complete for incident ${newAnalysis.incident_id}.`);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 font-sans">
      {/* Top Navigation */}
      <Header
        backendOnline={backendOnline}
        defaultBank={defaultBank}
        onRefresh={handleRefresh}
        onOpenCreate={() => setIsCreateOpen(true)}
        isRefreshing={isRefreshing}
      />

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 animate-in slide-in-from-bottom-3 duration-200">
          <div
            className={`flex items-center space-x-2.5 px-4 py-2.5 rounded-xl shadow-2xl border text-xs font-medium ${
              toast.type === 'success'
                ? 'bg-emerald-950/90 text-emerald-300 border-emerald-700/80 shadow-emerald-950/60'
                : 'bg-rose-950/90 text-rose-300 border-rose-700/80 shadow-rose-950/60'
            }`}
          >
            {toast.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span>{toast.message}</span>
          </div>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Pane: Incident Registry (fixed width) */}
        <div className="w-80 sm:w-96 flex-shrink-0 h-full">
          <IncidentList
            incidents={incidents}
            selectedIncidentId={selectedIncidentId}
            onSelectIncident={setSelectedIncidentId}
            isLoading={isLoading}
            onOpenCreate={() => setIsCreateOpen(true)}
          />
        </div>

        {/* Right Pane: Incident Investigation Detail Workbench */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950">
          {selectedIncident ? (
            <IncidentDetail
              incident={selectedIncident}
              analysis={currentAnalysis}
              onAnalysisUpdated={handleAnalysisUpdated}
              onOpenOutcome={() => setIsOutcomeOpen(true)}
            />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
              <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-600">
                <Inbox className="w-8 h-8" />
              </div>
              <h3 className="text-base font-semibold text-slate-300">No Incident Selected</h3>
              <p className="text-xs text-slate-500 max-w-sm">
                Select an incident from the registry on the left, or intake a new incident to begin
                memory-assisted investigation.
              </p>
              <button
                onClick={() => setIsCreateOpen(true)}
                className="mt-2 inline-flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-md transition-all"
              >
                <span>Intake Incident</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <CreateIncidentModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreated={handleIncidentCreated}
      />

      {selectedIncident && (
        <OutcomeModal
          incident={selectedIncident}
          isOpen={isOutcomeOpen}
          onClose={() => setIsOutcomeOpen(false)}
          onSuccess={(msg) => showToast(msg, 'success')}
        />
      )}
    </div>
  );
};
