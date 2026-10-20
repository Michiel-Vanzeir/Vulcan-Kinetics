import type { AnalyzeResponse, FeedbackResponse, HealthResponse, Message, TopicResult, TrustSignals } from '@/utils/messages';

const API_URL = import.meta.env.WXT_API_URL ?? 'http://127.0.0.1:8000';

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

async function analyze(text: string): Promise<AnalyzeResponse> {
  try {
    const { topics, hedges } = await post<{ topics: { id: string }[]; hedges: string[] }>('/analyze', { text });
    const results = await Promise.all(
      topics.map((t) => post<TopicResult>('/experts', { topic_id: t.id, text })),
    );
    return { ok: true, topics: results, hedges };
  } catch (err) {
    return { ok: false, error: `Can't reach the whoknows backend at ${API_URL}. Is it running?` };
  }
}

async function sendFeedback(topicId: string, ref: string, helpful: boolean): Promise<FeedbackResponse> {
  try {
    const { trust } = await post<{ trust: TrustSignals }>('/feedback', { topic_id: topicId, ref, helpful });
    return { ok: true, trust };
  } catch {
    return { ok: false };
  }
}

async function health(): Promise<HealthResponse> {
  try {
    const res = await fetch(`${API_URL}/health`);
    return { ok: res.ok, apiUrl: API_URL };
  } catch {
    return { ok: false, apiUrl: API_URL };
  }
}

export default defineBackground(() => {
  browser.runtime.onMessage.addListener((message: Message, _sender, sendResponse) => {
    // Content scripts can't call localhost themselves (page CORS), so the background does it.
    if (message.type === 'WHOKNOWS_ANALYZE') {
      analyze(message.text.slice(0, 4000)).then(sendResponse);
      return true;
    }
    if (message.type === 'WHOKNOWS_FEEDBACK') {
      sendFeedback(message.topicId, message.ref, message.helpful).then(sendResponse);
      return true;
    }
    if (message.type === 'WHOKNOWS_HEALTH') {
      health().then(sendResponse);
      return true;
    }
  });
});
