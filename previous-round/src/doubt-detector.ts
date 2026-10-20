// doubt-detector.ts  (runs in the content script, fully local, no network)

export interface DoubtContext {
  recentText: string;        // text before the caret (tail)
  abandonedDrafts: string[]; // what the sentence looked like right before each deletion burst
  score: number;
}

export interface DoubtOptions {
  onDoubt: (ctx: DoubtContext) => void;
  windowMs?: number;    // rolling window for scoring
  threshold?: number;   // 0..1
  cooldownMs?: number;  // min time between triggers
  pauseMs?: number;     // idle time that counts as a hesitation
}

type Ev = { t: number; type: 'insert' | 'delete' | 'pause' | 'hedge' | 'strong'; len: number };

// Words that signal "I'm not sure" (English + Dutch). Matched right after the phrase is typed.
const HEDGE = /\b(i think|i guess|i believe|i suppose|maybe|perhaps|probably|not sure|i'm not sure|kind of|sort of|somehow|ik denk|denk ik|misschien|volgens mij|ik weet niet|waarschijnlijk)[\s,.]$/i;
// Strong "help!" signals: ?? or ?! or !?
const STRONG = /(\?\?|\?!|!\?)$/;

const TAIL_CHARS = 600;
const BURST_GAP_MS = 1500;

export class DoubtDetector {
  private o: Required<DoubtOptions>;
  private events: Ev[] = [];
  private drafts: string[] = [];
  private lastTrigger = 0;
  private pauseTimer?: number;
  private burstTimer?: number;
  private inBurst = false;
  private target?: HTMLElement;

  constructor(opts: DoubtOptions) {
    this.o = { windowMs: 75_000, threshold: 0.55, cooldownMs: 300_000, pauseMs: 6_000, ...opts };
  }

  start() {
    document.addEventListener('beforeinput', this.onBeforeInput, true);
  }
  stop() {
    document.removeEventListener('beforeinput', this.onBeforeInput, true);
    clearTimeout(this.pauseTimer);
    clearTimeout(this.burstTimer);
  }

  // ---------- event capture ----------
  private onBeforeInput = (e: InputEvent) => {
    const el = e.composedPath()[0] as HTMLElement;
    if (!isEditable(el)) return;
    this.target = el;
    const now = performance.now();

    if (e.inputType.startsWith('delete') || e.inputType === 'historyUndo') {
      if (!this.inBurst) {
        // first delete of a burst: snapshot the sentence as it stood before it gets erased
        this.inBurst = true;
        const tail = lastSentence(textBeforeCaret(el));
        if (tail.length > 10) this.drafts = [...this.drafts, tail].slice(-5);
      }
      clearTimeout(this.burstTimer);
      this.burstTimer = window.setTimeout(() => (this.inBurst = false), BURST_GAP_MS);
      this.events.push({ t: now, type: 'delete', len: deletedLength(e, el) });
    } else if (e.inputType.startsWith('insert')) {
      this.events.push({ t: now, type: 'insert', len: e.data?.length ?? 1 });
      const justTyped = textBeforeCaret(el).slice(-60) + (e.data ?? '');
      if (STRONG.test(justTyped)) this.events.push({ t: now, type: 'strong', len: 0 });
      else if (HEDGE.test(justTyped)) this.events.push({ t: now, type: 'hedge', len: 0 });
    } else return;

    this.armPauseTimer();
    this.evaluate(now);
  };

  private armPauseTimer() {
    clearTimeout(this.pauseTimer);
    this.pauseTimer = window.setTimeout(() => {
      if (!this.target) return;
      const text = textBeforeCaret(this.target).trimEnd();
      // a pause at a sentence end is normal thinking; mid-clause is hesitation
      if (text && !/[.!?…]["')\]]?$/.test(text)) {
        const now = performance.now();
        this.events.push({ t: now, type: 'pause', len: 0 });
        this.evaluate(now);
      }
    }, this.o.pauseMs);
  }

  // ---------- scoring ----------
  private evaluate(now: number) {
    this.events = this.events.filter(e => now - e.t <= this.o.windowMs);
    if (now - this.lastTrigger < this.o.cooldownMs || !this.target) return;

    const score = this.score();
    if (score >= this.o.threshold) {
      this.lastTrigger = now;
      const ctx: DoubtContext = {
        recentText: textBeforeCaret(this.target).slice(-TAIL_CHARS),
        abandonedDrafts: this.drafts,
        score,
      };
      this.drafts = [];
      this.events = [];
      this.o.onDoubt(ctx);
    }
  }

  private score(): number {
    let typed = 0, deleted = 0, pauses = 0, bursts = 0, hedges = 0, strong = 0, lastDel = -Infinity;
    for (const e of this.events) {
      if (e.type === 'insert') typed += e.len;
      else if (e.type === 'pause') pauses++;
      else if (e.type === 'hedge') hedges++;
      else if (e.type === 'strong') strong++;
      else {
        deleted += e.len;
        if (e.t - lastDel > BURST_GAP_MS) bursts++;
        lastDel = e.t;
      }
    }
    if (strong > 0) return 1; // "??" = instant trigger

    let behaviour = 0;
    if (typed + deleted >= 40) { // need enough typing to judge behaviour
      const ratio = deleted / (typed + deleted);
      behaviour =
        0.4 * Math.min(ratio / 0.5, 1) +   // heavy deleting
        0.3 * Math.min(bursts / 4, 1) +    // repeated rewrite attempts
        0.3 * Math.min(pauses / 3, 1);     // mid-sentence stalls
    }
    return Math.min(1, behaviour + 0.25 * hedges); // each "I think"/"maybe" adds 0.25
  }
}

// ---------- DOM helpers ----------
function isEditable(el: HTMLElement | null): boolean {
  if (!el) return false;
  if (el instanceof HTMLInputElement) {
    return ['text', 'search', ''].includes(el.type) && el.autocomplete !== 'off-sensitive'; // skips password etc.
  }
  return el instanceof HTMLTextAreaElement || el.isContentEditable;
}

export function textBeforeCaret(el: HTMLElement): string {
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
    return el.value.slice(0, el.selectionStart ?? el.value.length);
  }
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return '';
  const r = document.createRange();
  r.selectNodeContents(el);
  r.setEnd(sel.getRangeAt(0).startContainer, sel.getRangeAt(0).startOffset);
  return r.toString();
}

function deletedLength(e: InputEvent, el: HTMLElement): number {
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
    const s = el.selectionStart ?? 0, n = el.selectionEnd ?? 0;
    if (n > s) return n - s;
    if (e.inputType === 'deleteWordBackward') return Math.max(1, (/\S+\s*$/.exec(el.value.slice(0, s))?.[0].length ?? 1));
    return 1;
  }
  const r = e.getTargetRanges?.()[0];
  if (r) {
    const range = document.createRange();
    range.setStart(r.startContainer, r.startOffset);
    range.setEnd(r.endContainer, r.endOffset);
    return Math.max(1, range.toString().length);
  }
  return 1;
}

export function lastSentence(text: string): string {
  const seg = [...new Intl.Segmenter(undefined, { granularity: 'sentence' }).segment(text)];
  return (seg.at(-1)?.segment ?? '').trim();
}
