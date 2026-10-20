// Shared message contract between content script, background and popup.

export type TriggerReason = 'hesitation' | 'question' | 'nudge';

export type Message =
  | { type: 'WHOKNOWS_ANALYZE'; text: string }
  | { type: 'WHOKNOWS_FEEDBACK'; topicId: string; ref: string; helpful: boolean }
  | { type: 'WHOKNOWS_HEALTH' };

export interface TrustSignals {
  count: number;
  last_active: string;
  last_active_label: string;
  vouches: number;
  unhelpful: number;
  stale: boolean;
  stale_since: number | null;
}

export interface Expert {
  ref: string; // opaque, server-signed reference used for feedback
  name: string;
  role: string;
  country: string;
  initials: string;
  score: number;
  highlight: string;
  authored: boolean;
  trust: TrustSignals;
}

export interface TopicResult {
  topic: { id: string; label: string; answer: string };
  knowledge_gap: boolean;
  experts: Expert[];
}

export type AnalyzeResponse =
  | { ok: true; topics: TopicResult[]; hedges: string[] }
  | { ok: false; error: string };

export type FeedbackResponse = { ok: true; trust: TrustSignals } | { ok: false };

export type HealthResponse = { ok: boolean; apiUrl: string };

