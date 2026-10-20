import type { AnalyzeResponse, Message, TriggerReason } from '@/utils/messages';
import { Nudge, Panel, type PanelContext } from '@/utils/panel';
import { type Editable, editableRoot, isEditable, ownText, replyContext, suggestQuestion } from '@/utils/context';

// Doubt detection: every signal adds points; at DOUBT_SCORE we flag it.
const PAUSE_MS = 2500; // short pause after typing
const LONG_PAUSE_MS = 6000; // long pause after typing
const DELETE_WINDOW_MS = 15000; // deleting this soon after a pause = rewriting
const DELETE_SETTLE_MS = 700; // wait until the deleting stops
const BURST_CHARS = 12; // deleting this many chars in one go
const DOUBT_SCORE = 2;
const MIN_TEXT = 15;
const MIN_GAP_MS = 4000; // between automatic backend calls
const NUDGE_GAP_MS = 20000; // between nudges

const HEDGES = [
  'i believe', 'i think', 'not sure', 'not 100% sure', 'not certain', 'probably', 'i guess', 'i assume', 'i suppose',
  'maybe', 'perhaps', "if i'm not mistaken", 'if i remember correctly', 'as far as i know', 'afaik', 'iirc',
  'i would say', "i'd say", 'should be', 'might be', 'could be', 'normally', 'in principle', 'let me check',
  "i'll check", 'i need to check', 'double-check', 'not entirely', 'unclear', 'hmm',
  'denk ik', 'ik denk', 'niet zeker', 'volgens mij', 'misschien', 'waarschijnlijk', 'ik vermoed', 'normaal gezien',
  'in principe', 'als ik me niet vergis', 'moet ik nakijken', 'ik check', 'twijfel',
];

function hedgesIn(text: string): string[] {
  const tail = ` ${text.toLowerCase().replace(/[’‘]/g, "'").slice(-250)} `;
  return HEDGES.filter((h) => new RegExp(`[^a-z]${h.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^a-z]`).test(tail));
}

const endsSentence = (text: string) => /[.!?]["')\]]?\s*$/.test(text.trimEnd());

export default defineContentScript({
  matches: ['<all_urls>'],
  runAt: 'document_idle',
  main() {
    let autoDetect = true;
    let field: Editable | null = null;
    let idleTimer: number | undefined;
    let longTimer: number | undefined;
    let deleteTimer: number | undefined;
    let pausedAt = 0;
    let deletedRun = 0;
    let rewrites = 0;
    let lastAutoAt = 0;
    let lastNudgeAt = 0;
    let lastDoubtText = '';
    let dismissedTopics = new Set<string>();
    let shownKey = '';

    browser.storage.local.get('autoDetect').then((v) => { autoDetect = v.autoDetect !== false; });
    browser.storage.onChanged.addListener((changes) => {
      if ('autoDetect' in changes) autoDetect = changes.autoDetect.newValue !== false;
    });

    let panel: Panel | null = null;
    const getPanel = () => {
      if (!panel) {
        panel = new Panel();
        panel.onClose = () => { shownKey.split(',').forEach((t) => t && dismissedTopics.add(t)); shownKey = ''; };
        panel.onQuestion = (q) => run('question', [], q, { question: q });
        panel.onVote = (topicId, ref, helpful) =>
          browser.runtime.sendMessage({ type: 'WHOKNOWS_FEEDBACK', topicId, ref, helpful } satisfies Message);
        panel.onReply = (expertName) => {
          // The panel was closed while waiting: flag the reply.
          getNudge().onClick = () => panel?.reopen();
          getNudge().show(`${expertName.split(' ')[0]} replied`, 'Click to read the answer', '💬 ');
        };
      }
      return panel;
    };
    let nudge: Nudge | null = null;
    const getNudge = () => (nudge ??= new Nudge());

    const analyze = (text: string): Promise<AnalyzeResponse> =>
      browser.runtime.sendMessage({ type: 'WHOKNOWS_ANALYZE', text } satisfies Message);

    const topicKey = (res: AnalyzeResponse) => (res.ok ? res.topics.map((t) => t.topic.id).join(',') : '');

    /** Open the panel and show results for this text. */
    async function run(reason: TriggerReason, signals: string[], text: string, ctx: PanelContext, prefetched?: AnalyzeResponse) {
      nudge?.hide();
      const p = getPanel();
      p.loading(reason, signals, ctx);
      const res = prefetched ?? await analyze(text);
      p.render(res);
      shownKey = topicKey(res);
    }

    /** Called when the typing behaviour looks like doubt. */
    async function onDoubt(signals: string[]) {
      if (!field) return;
      const own = ownText(field);
      const context = replyContext(field);
      const ctx = { question: suggestQuestion(context, own) };
      lastAutoAt = Date.now();
      const res = await analyze(`${own}\n${context}`);
      if (res.ok && res.hedges.length && !signals.some((s) => s.startsWith('hedging'))) signals.push(`hedging: “${res.hedges[0]}”`);

      const fresh = res.ok && res.topics.some((t) => !dismissedTopics.has(t.topic.id));
      if (fresh) {
        if (panel?.isOpen && topicKey(res) === shownKey) return;
        run('hesitation', signals, '', ctx, res);
        return;
      }
      // No new topic to show: flag the doubt with a small nudge instead of opening the panel.
      if (panel?.isOpen || Date.now() - lastNudgeAt < NUDGE_GAP_MS) return;
      lastNudgeAt = Date.now();
      const first = res.ok ? res.topics[0] : undefined;
      const n = first?.experts.length ?? 0;
      getNudge().onClick = () => (first ? run('nudge', signals, '', ctx, res) : getPanel().ask('nudge', signals, ctx.question));
      getNudge().show(
        first ? `${n} colleague${n === 1 ? '' : 's'} know about ${first.topic.label.toLowerCase()}` : 'Ask who can help',
        first ? 'Click to see who knows' : 'Click to type your question',
      );
    }

    function evaluate(kind: 'pause' | 'long-pause' | 'delete', afterPause = false, run = 0) {
      if (!autoDetect || !field) return;
      const text = ownText(field);
      if (text.trim().length < MIN_TEXT) return;

      const signals: string[] = [];
      let score = 0;
      const hedges = hedgesIn(text);
      if (hedges.length) { score += 2; signals.push(`hedging: “${hedges[0]}”`); }
      if (kind === 'pause' && !endsSentence(text)) { score += 1; signals.push('paused mid-sentence'); }
      if (kind === 'long-pause') { score += endsSentence(text) ? 1 : 2; signals.push('long pause'); }
      if (kind === 'delete' && afterPause) { score += 2; signals.push('paused, then deleted'); }
      if (kind === 'delete' && run >= BURST_CHARS) { score += 2; signals.push('deleted a chunk'); }
      if (rewrites >= 3) { score += 1; signals.push(`rewrote ${rewrites}×`); }

      if (score < DOUBT_SCORE) return;
      if (text === lastDoubtText || Date.now() - lastAutoAt < MIN_GAP_MS) return;
      lastDoubtText = text;
      onDoubt(signals);
    }

    document.addEventListener('focusin', (e) => {
      if (!isEditable(e.target)) return;
      const next = editableRoot(e.target);
      if (next !== field) {
        field = next;
        dismissedTopics = new Set();
        pausedAt = 0;
        rewrites = 0;
        lastDoubtText = '';
      }
    }, true);

    document.addEventListener('input', (e) => {
      if (!(e instanceof InputEvent) || !isEditable(e.target)) return;
      field = editableRoot(e.target);
      clearTimeout(idleTimer);
      clearTimeout(longTimer);

      if (e.inputType.startsWith('delete')) {
        deletedRun++;
        clearTimeout(deleteTimer);
        deleteTimer = window.setTimeout(() => {
          const afterPause = !!pausedAt && Date.now() - pausedAt < DELETE_WINDOW_MS;
          if (afterPause || deletedRun >= 4) rewrites++;
          evaluate('delete', afterPause, deletedRun);
          deletedRun = 0;
          pausedAt = 0;
        }, DELETE_SETTLE_MS);
        return;
      }

      pausedAt = 0;
      idleTimer = window.setTimeout(() => { pausedAt = Date.now(); evaluate('pause'); }, PAUSE_MS);
      longTimer = window.setTimeout(() => evaluate('long-pause'), LONG_PAUSE_MS);
    }, true);

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && panel?.isOpen) panel.close();
    }, true);
  },
});
