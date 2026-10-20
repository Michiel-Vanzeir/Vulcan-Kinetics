// keywords.ts
// Turns a DoubtContext into weighted keywords. The LLM call itself must happen on
// your backend (never ship an API key in the extension), so it's injected as `callLLM`.

import { DoubtContext, DoubtDetector } from './doubt-detector';

export interface WeightedKeyword {
  term: string;   // lowercase, normalised
  weight: number; // 0..1, highest = most relevant to what the writer is stuck on
}

type CallLLM = (system: string, user: string) => Promise<string>;

const MAX_KEYWORDS = 8;
const MIN_WEIGHT = 0.2;

function lastSentences(text: string, n = 3): string {
  const seg = [...new Intl.Segmenter(undefined, { granularity: 'sentence' }).segment(text)];
  return seg.slice(-n).map(s => s.segment.trim()).join(' ');
}

const SYSTEM = `You extract topic keywords from a person's unfinished writing so that an expert on the topic can be found.
The writer seems unsure about what they are writing. Return ONLY JSON, no prose, no code fences:
{"keywords":[{"term":"...","weight":0.0}]}
Rules:
- At most ${MAX_KEYWORDS} keywords. Prefer specific nouns / noun phrases / technical terms over generic words.
- weight is 0..1: how central the term is to what the writer is struggling with.
- If a vocabulary list is given, use those exact terms whenever one fits; only invent a term if nothing fits.
- Hedging phrases ("I think", "maybe", "not sure", "??") mark the uncertain part: weight the topic of that sentence higher.
- Ignore names of the writer, greetings, and filler.`;

export function buildPrompt(ctx: DoubtContext, vocabulary?: string[]): string {
  return [
    `Current text (last sentences):\n${lastSentences(ctx.recentText)}`,
    ctx.abandonedDrafts.length
      ? `Versions the writer deleted (they reveal what they are unsure about):\n- ${ctx.abandonedDrafts.join('\n- ')}`
      : '',
    vocabulary?.length ? `Vocabulary:\n${vocabulary.join(', ')}` : '',
  ].filter(Boolean).join('\n\n');
}

export function parseKeywords(raw: string): WeightedKeyword[] {
  try {
    const json = JSON.parse(raw.replace(/```json|```/g, '').trim());
    return (json.keywords ?? [])
      .filter((k: any) => typeof k?.term === 'string')
      .map((k: any) => ({
        term: k.term.toLowerCase().trim(),
        weight: Math.min(1, Math.max(0, Number(k.weight) || 0)),
      }));
  } catch {
    return [];
  }
}

// Combine the LLM's weight with signals the LLM can't see well.
function reweight(kws: WeightedKeyword[], ctx: DoubtContext): WeightedKeyword[] {
  const deleted = ctx.abandonedDrafts.join(' ').toLowerCase();
  const recent = lastSentences(ctx.recentText, 1).toLowerCase();
  const merged = new Map<string, number>();

  for (const k of kws) {
    let w = k.weight;
    if (deleted.includes(k.term)) w *= 1.25; // they rewrote around this term
    if (recent.includes(k.term)) w *= 1.1;   // it's in the sentence they're on right now
    merged.set(k.term, Math.max(merged.get(k.term) ?? 0, w)); // dedupe
  }

  const max = Math.max(...merged.values(), 0.0001);
  return [...merged]
    .map(([term, w]) => ({ term, weight: +(w / max).toFixed(2) })) // normalise so top = 1
    .filter(k => k.weight >= MIN_WEIGHT)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, MAX_KEYWORDS);
}

export async function extractKeywords(
  ctx: DoubtContext,
  callLLM: CallLLM,
  vocabulary?: string[],
): Promise<WeightedKeyword[]> {
  const raw = await callLLM(SYSTEM, buildPrompt(ctx, vocabulary));
  return reweight(parseKeywords(raw), ctx);
}

// ---------- wiring (content script) ----------
// `handOff` is whatever the database person exposes, e.g. POST /match with the keywords.
export function init(
  callLLM: CallLLM,
  handOff: (kws: WeightedKeyword[]) => Promise<void>,
  vocabulary?: string[],
) {
  const detector = new DoubtDetector({
    onDoubt: async ctx => {
      const keywords = await extractKeywords(ctx, callLLM, vocabulary);
      if (keywords.length) await handOff(keywords); // e.g. [{term:"rollback strategy",weight:1},{term:"kubernetes",weight:0.7}]
    },
  });
  detector.start();
  return detector;
}
