/**
 * TypeScript API type definitions mirroring the RecallOps FastAPI backend schemas.
 */

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

export interface Incident {
  id: string;
  title: string;
  description: string;
  affected_service: string;
  severity: SeverityLevel;
  logs?: string | null;
  status: string;
  created_at: string;
  updated_at?: string | null;
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  limit: number;
  offset: number;
}

export interface IncidentCreatePayload {
  title: string;
  description: string;
  affected_service: string;
  severity: SeverityLevel;
  logs?: string | null;
}

export interface ExtractedSymptoms {
  affected_service: string;
  severity: string;
  indicators: string[];
  recall_query: string;
}

export interface MemoryResult {
  id: string;
  text: string;
  type?: string | null;
  entities?: string[] | null;
  context?: string | null;
  mentioned_at?: string | null;
}

export interface AnalysisSuggestion {
  category: 'historical_resolution' | 'historical_observation' | 'diagnostic_step' | 'precaution' | string;
  suggestion: string;
  evidence_source?: string | null;
}

export interface IncidentAnalysisResponse {
  incident_id: string;
  analyzed_at: string;
  bank_id: string;
  incident_title: string;
  extracted_symptoms: ExtractedSymptoms;
  recalled_memories: MemoryResult[];
  suggestions: AnalysisSuggestion[];
  has_historical_matches: boolean;
}

export interface AnalysisRequestPayload {
  query_override?: string | null;
  max_tokens?: number | null;
}

export type OutcomeType = 'success' | 'failure';

export interface IncidentOutcomeRecord {
  id: string;
  incident_id: string;
  resolution_attempted: string;
  outcome: OutcomeType;
  engineer_notes?: string | null;
  created_at: string;
}

export interface IncidentOutcomeResponse {
  outcome: IncidentOutcomeRecord;
  hindsight_retained: boolean;
  bank_id: string;
}

export interface IncidentOutcomePayload {
  incident_id?: string | null;
  resolution_attempted: string;
  outcome: OutcomeType;
  engineer_notes?: string | null;
}

export interface HealthCheckResponse {
  status: string;
  service: string;
}

export interface DefaultBankResponse {
  default_bank_id: string;
}
