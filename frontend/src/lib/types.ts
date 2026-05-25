// PolicyLens AI — TypeScript type definitions
// Mirrors backend Pydantic schemas

export type QueryTier = 'fast_info' | 'grounded_qa' | 'verified';
export type ConfidenceLevel = 'high' | 'medium' | 'low';
export type ReadingLevel = 'simple' | 'standard' | 'expert';

export interface SourceClause {
  section_title: string;
  page_number: number;
  text: string;
  relevance_score: number;
}

export interface ConfidenceScore {
  retrieval_score: number;
  coverage_score: number;
  llm_confidence: number;
  overall: number;
  level: ConfidenceLevel;
}

// ─── Policy ─────────────────────────────────────────────────

export interface PolicyInfo {
  policy_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  uploaded_at: string;
  summary: string;
}

export interface PolicyUploadResponse {
  policy_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  summary: string;
  status: string;
}

export interface PolicyDetail extends PolicyInfo {
  has_index: boolean;
  summary_data?: {
    policy_type?: string;
    provider?: string;
    key_coverage?: string[];
    key_exclusions?: string[];
    premium_info?: string;
    waiting_periods?: string[];
    claim_process_summary?: string;
    important_notes?: string[];
    one_line_summary?: string;
  };
}

// ─── Query ──────────────────────────────────────────────────

export interface AmbiguityInfo {
  found: boolean;
  details: string[];
  risk_level: string;
}

export interface ContradictionInfo {
  found: boolean;
  details: string[];
}

export interface QueryResponse {
  answer: string;
  tier: QueryTier;
  confidence: ConfidenceScore;
  sources: SourceClause[];
  ambiguity?: AmbiguityInfo;
  contradiction?: ContradictionInfo;
  verification_status?: string;
  reading_level: ReadingLevel;
  language: string;
  latency_ms: number;
}

// ─── Eligibility ────────────────────────────────────────────

export interface EligibilityResponse {
  eligible: boolean | null;
  explanation: string;
  conditions: string[];
  waiting_period: string;
  confidence: ConfidenceScore;
  sources: SourceClause[];
  disclaimer: string;
}

// ─── Exclusions ─────────────────────────────────────────────

export interface ExclusionItem {
  title: string;
  description: string;
  section: string;
  page: number;
  risk_note: string;
}

export interface ExclusionsResponse {
  exclusions: ExclusionItem[];
  total: number;
  confidence: ConfidenceScore;
  sources: SourceClause[];
}

// ─── Comparison ─────────────────────────────────────────────

export interface ComparisonAspect {
  aspect: string;
  policies: Record<string, string>;
  recommendation: string;
}

export interface CompareResponse {
  comparisons: ComparisonAspect[];
  overall_recommendation: string;
  confidence: ConfidenceScore;
  sources: Record<string, SourceClause[]>;
}

// ─── Chat ───────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  response?: QueryResponse;
  isLoading?: boolean;
}

// ─── Health ─────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  gemini_connected: boolean;
  policies_loaded: number;
  embedding_model: string;
}
