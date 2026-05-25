// PolicyLens AI — API Client
// Centralized API communication with the FastAPI backend

import type {
  PolicyInfo,
  PolicyUploadResponse,
  PolicyDetail,
  QueryResponse,
  EligibilityResponse,
  ExclusionsResponse,
  CompareResponse,
  HealthResponse,
  ReadingLevel,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(error.detail || 'API request failed', res.status);
  }

  return res.json();
}

// ─── Health ─────────────────────────────────────────────────

export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health');
}

// ─── Policies ───────────────────────────────────────────────

export async function uploadPolicy(file: File): Promise<PolicyUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const url = `${API_BASE}/api/policies/upload`;
  const res = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(error.detail || 'Upload failed', res.status);
  }

  return res.json();
}

export async function listPolicies(): Promise<{ policies: PolicyInfo[]; total: number }> {
  return request('/api/policies/');
}

export async function getPolicy(policyId: string): Promise<PolicyDetail> {
  return request(`/api/policies/${policyId}`);
}

export async function deletePolicy(policyId: string): Promise<void> {
  return request(`/api/policies/${policyId}`, { method: 'DELETE' });
}

// ─── Queries ────────────────────────────────────────────────

export async function askQuestion(
  question: string,
  policyId: string,
  readingLevel: ReadingLevel = 'standard',
  language: string = 'en'
): Promise<QueryResponse> {
  return request<QueryResponse>('/api/query/ask', {
    method: 'POST',
    body: JSON.stringify({
      question,
      policy_id: policyId,
      reading_level: readingLevel,
      language,
    }),
  });
}

export async function checkEligibility(
  policyId: string,
  condition: string,
  details: string = '',
  language: string = 'en'
): Promise<EligibilityResponse> {
  return request<EligibilityResponse>('/api/query/eligibility', {
    method: 'POST',
    body: JSON.stringify({
      policy_id: policyId,
      condition,
      details,
      language,
    }),
  });
}

export async function findExclusions(policyId: string): Promise<ExclusionsResponse> {
  return request<ExclusionsResponse>(`/api/query/exclusions?policy_id=${policyId}`, {
    method: 'POST',
  });
}

// ─── Compare ────────────────────────────────────────────────

export async function comparePolicies(
  policyIds: string[],
  aspects: string[] = ['coverage', 'exclusions', 'premiums', 'waiting_period', 'claim_process'],
  language: string = 'en'
): Promise<CompareResponse> {
  return request<CompareResponse>('/api/compare/', {
    method: 'POST',
    body: JSON.stringify({
      policy_ids: policyIds,
      aspects,
      language,
    }),
  });
}
