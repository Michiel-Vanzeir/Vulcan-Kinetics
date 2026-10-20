// Side panel and doubt "nudge" injected into the page. Both live in a shadow root so page CSS
// can't touch them. All content is built with textContent (never innerHTML) so backend data
// can't inject markup, which also keeps Gmail's Trusted Types policy happy.

import type { AnalyzeResponse, Expert, FeedbackResponse, TopicResult, TriggerReason, TrustSignals } from '@/utils/messages';
import { createLogo } from '@/utils/logo';

type Child = Node | string | null | false | undefined;

function h(tag: string, attrs: Record<string, string> = {}, ...children: Child[]): HTMLElement {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const c of children) if (c) el.append(c);
  return el;
}

const FONT = '"Bricolage Grotesque", system-ui, -apple-system, "Segoe UI", sans-serif';

const STYLE = `
:host { all: initial; }
* { box-sizing: border-box; }
.panel {
  position: fixed; top: 12px; right: 12px; bottom: 12px; width: 380px; z-index: 2147483647;
  display: flex; flex-direction: column; overflow: hidden;
  background: #fff; color: #1B2A4E; border-radius: 16px;
  box-shadow: 0 12px 40px rgba(27,42,78,.28), 0 0 0 1px rgba(27,42,78,.08);
  font: 14px/1.45 ${FONT};
  transform: translateX(calc(100% + 24px)); transition: transform .35s cubic-bezier(.2,.8,.2,1);
}
.panel.open { transform: none; }
header { background: #1B2A4E; color: #fff; padding: 14px 16px; display: flex; align-items: center; gap: 10px; }
header svg { width: 34px; height: 34px; flex: none; }
.wordmark { font-weight: 800; font-size: 20px; letter-spacing: -.02em; }
.tagline { font-size: 11.5px; color: #A0ACC8; }
.close { margin-left: auto; background: none; border: 0; color: #A0ACC8; font-size: 22px; cursor: pointer; line-height: 1; padding: 4px; }
.close:hover { color: #fff; }
.reason { padding: 8px 16px; font-size: 12.5px; background: #FFF6D6; color: #5c4a00; border-bottom: 1px solid #f3e3a6; }
.reason:empty { display: none; }
.ask-box { display: flex; gap: 6px; padding: 10px 14px; border-bottom: 1px solid #eef0f5; }
.ask-box input { flex: 1; min-width: 0; padding: 8px 11px; border: 1px solid #d5dae6; border-radius: 9px; font: inherit; font-size: 13.5px; color: #1B2A4E; outline: none; }
.ask-box input:focus { border-color: #1B2A4E; box-shadow: 0 0 0 3px rgba(255,210,63,.45); }
.ask-box button { padding: 0 12px; border: 0; border-radius: 9px; background: #FFD23F; color: #1B2A4E; font: inherit; font-weight: 700; cursor: pointer; }
.body { overflow-y: auto; padding: 4px 14px 16px; flex: 1; }
.topic { margin: 12px 2px 8px; font-size: 11.5px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: #6b7797; }
.card { border: 1px solid #e3e7f0; border-radius: 12px; padding: 10px 12px; margin-bottom: 8px; animation: in .4s both; }
.card:nth-of-type(2) { animation-delay: .06s; } .card:nth-of-type(3) { animation-delay: .12s; }
@keyframes in { from { opacity: 0; transform: translateY(6px); } }
.card.top { border-color: #FFD23F; box-shadow: 0 0 0 1px #FFD23F inset; }
.who { display: flex; gap: 10px; align-items: center; }
.avatar { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; flex: none; background: #1B2A4E; color: #FFD23F; }
.card.stale .avatar { background: #d5dae6; color: #6b7797; }
.name { font-weight: 700; font-size: 15px; }
.role { font-size: 12.5px; color: #6b7797; }
.badge { margin-left: auto; font-size: 11px; font-weight: 700; background: #FFD23F; color: #1B2A4E; padding: 2px 8px; border-radius: 99px; }
.evidence { margin: 7px 0; font-size: 13px; color: #34405e; }
.evidence b { font-weight: 600; }
.signals { display: flex; flex-wrap: wrap; gap: 5px; }
.chip { font-size: 11.5px; padding: 2px 8px; border-radius: 99px; background: #eef1f7; color: #34405e; white-space: nowrap; }
.chip.fresh { background: #dcf5e6; color: #11663a; }
.chip.old { background: #f1f2f5; color: #7a8299; }
.warn { margin-top: 8px; font-size: 12.5px; color: #9a5b00; }
.btn { margin-top: 8px; width: 100%; padding: 6px; border: 0; border-radius: 9px; background: #1B2A4E; color: #fff; font: inherit; font-weight: 600; cursor: pointer; }
.btn:hover { background: #26396a; }
.btn.ghost { background: #eef1f7; color: #1B2A4E; }
.sent { margin-top: 8px; padding: 7px 10px; border-radius: 9px; background: #dcf5e6; color: #11663a; font-weight: 600; font-size: 13px; }
.compose { margin-top: 8px; }
.compose textarea { width: 100%; min-height: 76px; padding: 8px 10px; border: 1px solid #d5dae6; border-radius: 9px; font: inherit; font-size: 13px; color: #1B2A4E; resize: vertical; outline: none; }
.compose textarea:focus { border-color: #1B2A4E; box-shadow: 0 0 0 3px rgba(255,210,63,.45); }
.compose .row { display: flex; gap: 6px; }
.compose .row .btn { margin-top: 4px; }
.thread { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.bubble { padding: 7px 10px; border-radius: 12px; font-size: 13px; max-width: 92%; white-space: pre-wrap; }
.bubble.me { align-self: flex-end; background: #1B2A4E; color: #fff; border-bottom-right-radius: 4px; }
.bubble.them { background: #FFF3C4; color: #1B2A4E; border-bottom-left-radius: 4px; animation: in .35s both; }
.reply { display: flex; gap: 6px; align-items: flex-end; }
.mini { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; flex: none; background: #1B2A4E; color: #FFD23F; font-size: 10px; font-weight: 700; }
.status { display: flex; gap: 4px; align-items: center; font-size: 12px; color: #6b7797; }
.status .dot { width: 5px; height: 5px; }
.votebox { margin-top: 4px; padding: 8px 10px; border-radius: 10px; background: #f4f6fb; }
.votebox .q { font-size: 12.5px; font-weight: 600; margin-bottom: 6px; }
.votebox .row { display: flex; gap: 6px; }
.vote { flex: 1; padding: 6px; border: 1px solid #d5dae6; border-radius: 8px; background: #fff; color: #1B2A4E; font: inherit; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.vote:hover { border-color: #1B2A4E; }
.vote[disabled] { opacity: .5; cursor: default; }
.voted { font-size: 12.5px; padding: 7px 10px; border-radius: 9px; animation: in .3s both; }
.voted.up { background: #dcf5e6; color: #11663a; }
.voted.down { background: #f1f2f5; color: #4b5675; }
.chip.bump { background: #FFD23F; color: #1B2A4E; transition: background .3s; }
.gap { border: 1.5px dashed #c3cadb; border-radius: 12px; padding: 12px; margin-bottom: 10px; background: #f8f9fc; }
.gap b { display: block; font-size: 14px; margin-bottom: 2px; }
.gap p { margin: 0; font-size: 13px; color: #4b5675; }
.muted { color: #6b7797; font-size: 13px; padding: 16px 4px; }
.loading { display: flex; gap: 6px; padding: 24px 4px; align-items: center; color: #6b7797; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #1B2A4E; animation: blink 1s infinite; }
.dot:nth-child(2) { animation-delay: .15s; } .dot:nth-child(3) { animation-delay: .3s; background: #FFD23F; }
@keyframes blink { 50% { opacity: .25; } }
footer { padding: 8px 16px; font-size: 11.5px; color: #8a93ad; border-top: 1px solid #eef0f5; }

.nudge {
  position: fixed; right: 20px; bottom: 20px; z-index: 2147483646;
  display: flex; align-items: center; gap: 10px; padding: 8px 14px 8px 8px; max-width: 360px;
  background: #1B2A4E; color: #fff; border: 0; border-radius: 99px; cursor: pointer;
  font: 13.5px/1.3 ${FONT}; text-align: left;
  box-shadow: 0 8px 28px rgba(27,42,78,.35), 0 0 0 3px #FFD23F;
  animation: pop .45s cubic-bezier(.2,1.4,.4,1) both;
}
.nudge svg { width: 30px; height: 30px; flex: none; }
.nudge b { color: #FFD23F; }
.nudge small { display: block; color: #A0ACC8; font-size: 11.5px; }
@keyframes pop { from { opacity: 0; transform: translateY(12px) scale(.9); } }
`;

function firstName(name: string) {
  return name.split(' ')[0] ?? name;
}

/** Stop keystrokes in our UI from reaching page shortcuts (Gmail uses single-key shortcuts). */
function isolateKeys(host: HTMLElement) {
  for (const type of ['keydown', 'keyup', 'keypress', 'input'] as const) {
    host.addEventListener(type, (e) => {
      if (e.type === 'keydown' && (e as KeyboardEvent).key === 'Escape') return;
      e.stopPropagation();
    });
  }
}

const REPLY_DELAY_MS = 10000;

type TopicInfo = TopicResult['topic'];

interface Conversation {
  message: string;
  status: 'waiting' | 'typing' | 'replied';
  reply: string;
  vote?: 'up' | 'down';
}

interface CardSlot {
  slot: HTMLElement;
  vouchChip: HTMLElement;
  expert: Expert;
  topic: TopicInfo;
  best: Expert | undefined;
}

function vouchLabel(t: TrustSignals) {
  const up = t.vouches ? `👍 ${t.vouches} colleague${t.vouches === 1 ? '' : 's'} vouch` : 'no vouches yet';
  return t.unhelpful ? `${up} · 👎 ${t.unhelpful}` : up;
}

function expertReply(expert: Expert, topic: TopicInfo, best: Expert | undefined): string {
  if (expert.trust.stale) {
    const pointer = best && best.name !== expert.name
      ? `${firstName(best.name)} is much more up to date, I'd ask them.`
      : 'Please double-check before you answer the client.';
    return `Honestly, I haven't worked on this since ${expert.trust.stale_since}, so what I remember may be outdated. ${pointer}`;
  }
  return topic.answer ? `Hi! ${topic.answer}` : "Hi! Good question, let me look into it and I'll get back to you today.";
}

export interface PanelContext {
  question: string; // what the user seems to be asking; prefilled in "Ask <name>"
}

export class Panel {
  private host: HTMLElement;
  private panel: HTMLElement;
  private reason: HTMLElement;
  private body: HTMLElement;
  private input: HTMLInputElement;
  private ctx: PanelContext = { question: '' };
  private convos = new Map<string, Conversation>();
  private slots = new Map<string, CardSlot>();
  onClose: () => void = () => {};
  onQuestion: (question: string) => void = () => {};
  onVote: (topicId: string, ref: string, helpful: boolean) => Promise<FeedbackResponse> = async () => ({ ok: false });
  onReply: (expertName: string) => void = () => {};

  constructor() {
    loadFont();
    this.host = h('whoknows-panel');
    isolateKeys(this.host);
    const root = this.host.attachShadow({ mode: 'open' });
    root.append(h('style', {}, STYLE));

    const close = h('button', { class: 'close', title: 'Close (Esc)' }, '×');
    close.addEventListener('click', () => this.close());
    const header = h('header', {}, createLogo(),
      h('div', {}, h('div', { class: 'wordmark' }, 'whoknows'), h('div', { class: 'tagline' }, 'Expertise finds you, not the other way around.')),
      close);

    this.input = h('input', { type: 'text', placeholder: 'What do you need to know?', maxlength: '500', 'aria-label': 'Your question' }) as HTMLInputElement;
    const form = h('form', { class: 'ask-box' }, this.input, h('button', { type: 'submit' }, 'Find'));
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = this.input.value.trim();
      if (q) this.onQuestion(q);
    });

    this.reason = h('div', { class: 'reason' });
    this.body = h('div', { class: 'body' });
    const footer = h('footer', {}, 'Only colleagues who opted in are shown · Esc to close');
    this.panel = h('div', { class: 'panel', role: 'complementary', 'aria-label': 'whoknows' }, header, this.reason, form, this.body, footer);
    root.append(this.panel);
  }

  get isOpen() {
    return this.panel.classList.contains('open');
  }

  private show() {
    if (!this.host.isConnected) document.documentElement.append(this.host);
    requestAnimationFrame(() => requestAnimationFrame(() => this.panel.classList.add('open')));
  }

  /** Open with a prompt to type a question (clicking the nudge when no topic was recognised). */
  ask(reason: TriggerReason, signals: string[], question: string) {
    this.setReason(reason, signals);
    this.ctx = { question };
    this.input.value = question;
    this.body.replaceChildren(h('div', { class: 'muted' }, 'Type your question above and press Enter. whoknows finds the colleagues who know.'));
    this.show();
    setTimeout(() => { this.input.focus(); this.input.select(); }, 350);
  }

  loading(reason: TriggerReason, signals: string[], ctx: PanelContext) {
    this.setReason(reason, signals);
    this.ctx = ctx;
    if (ctx.question) this.input.value = ctx.question;
    this.body.replaceChildren(h('div', { class: 'loading' }, h('span', { class: 'dot' }), h('span', { class: 'dot' }), h('span', { class: 'dot' }), ' Finding who knows…'));
    this.show();
  }

  render(response: AnalyzeResponse) {
    if (!response.ok) {
      this.body.replaceChildren(h('div', { class: 'muted' }, response.error));
      return;
    }
    if (!response.topics.length) {
      this.body.replaceChildren(h('div', { class: 'muted' }, "Couldn't tell which topic this is about. Try rephrasing your question with a few keywords, e.g. “year-end bonus PC 200”."));
      return;
    }
    this.slots.clear();
    this.body.replaceChildren(...response.topics.flatMap((t) => this.topicSection(t)));
  }

  /** Show the panel again with whatever it last displayed. */
  reopen() {
    this.show();
  }

  close() {
    this.panel.classList.remove('open');
    this.onClose();
  }

  private setReason(reason: TriggerReason, signals: string[]) {
    const text = {
      hesitation: `Looks like you're unsure · ${signals.join(' · ')}`,
      question: '',
      nudge: signals.length ? `Looks like you're unsure · ${signals.join(' · ')}` : '',
    }[reason];
    this.reason.textContent = text;
  }

  private topicSection(result: TopicResult): Node[] {
    const nodes: Node[] = [h('div', { class: 'topic' }, result.topic.label)];
    if (result.knowledge_gap) {
      nodes.push(h('div', { class: 'gap' },
        h('b', {}, '🕳 Knowledge gap'),
        h('p', {}, 'Nobody has recent expertise on this topic. Flag it so the organisation can close the gap.'),
      ));
    }
    const best = result.experts.find((e) => !e.trust.stale);
    result.experts.forEach((e, i) => nodes.push(this.expertCard(e, i === 0 && !result.knowledge_gap, result.topic, best)));
    return nodes;
  }

  private expertCard(expert: Expert, isTop: boolean, topic: TopicInfo, best: Expert | undefined): HTMLElement {
    const t = expert.trust;
    const recency = t.stale ? 'old' : new Date(t.last_active) > new Date(Date.now() - 90 * 864e5) ? 'fresh' : '';
    const vouchChip = h('span', { class: 'chip' }, vouchLabel(t));
    const slot = h('div', {});
    this.slots.set(expert.ref, { slot, vouchChip, expert, topic, best });
    this.renderAction(expert.ref);

    return h('div', { class: `card${isTop ? ' top' : ''}${t.stale ? ' stale' : ''}` },
      h('div', { class: 'who' },
        h('div', { class: 'avatar' }, expert.initials),
        h('div', {}, h('div', { class: 'name' }, expert.name), h('div', { class: 'role' }, `${expert.role} · ${expert.country}`)),
        isTop && h('span', { class: 'badge' }, 'Best match'),
      ),
      h('div', { class: 'evidence' }, h('b', {}, expert.authored ? '✎ Author: ' : 'Latest: '), expert.highlight),
      h('div', { class: 'signals' },
        h('span', { class: `chip ${recency}` }, `🕑 ${t.last_active_label}`),
        h('span', { class: 'chip' }, `↻ ${t.count}× handled`),
        vouchChip,
      ),
      t.stale && h('div', { class: 'warn' }, `⚠ Not active on this since ${t.stale_since}. Knowledge may be outdated.`),
      slot,
    );
  }

  /** The ask -> wait -> reply -> vouch flow under each expert card. State survives re-renders. */
  private renderAction(ref: string) {
    const card = this.slots.get(ref);
    if (!card) return;
    const { slot, expert } = card;
    const name = firstName(expert.name);
    const convo = this.convos.get(ref);

    if (!convo) {
      const ask = h('button', { class: 'btn' + (expert.trust.stale ? ' ghost' : '') }, `Ask ${name}`);
      ask.addEventListener('click', () => slot.replaceChildren(this.composer(ref)));
      slot.replaceChildren(ask);
      return;
    }

    const thread = h('div', { class: 'thread' }, h('div', { class: 'bubble me' }, convo.message));
    if (convo.status === 'waiting') {
      thread.append(h('div', { class: 'status' }, `✓ Sent · waiting for ${name}…`));
    } else if (convo.status === 'typing') {
      thread.append(h('div', { class: 'status' }, h('span', { class: 'dot' }), h('span', { class: 'dot' }), h('span', { class: 'dot' }), ` ${name} is typing…`));
    } else {
      thread.append(h('div', { class: 'reply' }, h('div', { class: 'mini' }, expert.initials), h('div', { class: 'bubble them' }, convo.reply)));
      thread.append(this.voteBox(ref, name, convo));
    }
    slot.replaceChildren(thread);
  }

  /** "Did they know their stuff?" A yes counts as a vouch on this topic; a no lowers their ranking. */
  private voteBox(ref: string, name: string, convo: Conversation): HTMLElement {
    if (convo.vote) {
      return h('div', { class: `voted ${convo.vote}` }, convo.vote === 'up'
        ? `✓ You vouched for ${name}. It now counts in their trust score.`
        : `Noted. ${name} will rank lower on this topic.`);
    }
    const yes = h('button', { class: 'vote' }, '👍 Yes, vouch');
    const no = h('button', { class: 'vote' }, '👎 Not really');
    const send = async (helpful: boolean) => {
      yes.setAttribute('disabled', '');
      no.setAttribute('disabled', '');
      const card = this.slots.get(ref);
      if (!card) return;
      const res = await this.onVote(card.topic.id, ref, helpful);
      if (!res.ok) {
        yes.removeAttribute('disabled');
        no.removeAttribute('disabled');
        return;
      }
      convo.vote = helpful ? 'up' : 'down';
      card.vouchChip.textContent = vouchLabel(res.trust);
      card.vouchChip.classList.add('bump');
      this.renderAction(ref);
    };
    yes.addEventListener('click', () => send(true));
    no.addEventListener('click', () => send(false));
    return h('div', { class: 'votebox' }, h('div', { class: 'q' }, `Did ${name} know their stuff?`), h('div', { class: 'row' }, yes, no));
  }

  /** Let the user write (or edit) the question before sending it to the expert. */
  private composer(ref: string): HTMLElement {
    const card = this.slots.get(ref)!;
    const name = firstName(card.expert.name);
    const q = this.ctx.question.trim();
    const textarea = h('textarea', { 'aria-label': `Message to ${name}`, maxlength: '1000' }) as HTMLTextAreaElement;
    textarea.value = `Hi ${name}, quick question about ${card.topic.label}: ${q || '…'}`;
    const send = h('button', { class: 'btn' }, `Send to ${name}`);
    const cancel = h('button', { class: 'btn ghost' }, 'Cancel');
    send.addEventListener('click', () => {
      const message = textarea.value.trim();
      if (message) this.startConversation(ref, message);
    });
    cancel.addEventListener('click', () => this.renderAction(ref));
    setTimeout(() => { textarea.focus(); textarea.setSelectionRange(textarea.value.length, textarea.value.length); }, 0);
    return h('div', { class: 'compose' }, textarea, h('div', { class: 'row' }, cancel, send));
  }

  /** The expert answer comes from the topic knowledge base and arrives after REPLY_DELAY_MS. */
  private startConversation(ref: string, message: string) {
    const { expert, topic, best } = this.slots.get(ref)!;
    const convo: Conversation = { message, status: 'waiting', reply: expertReply(expert, topic, best) };
    this.convos.set(ref, convo);
    this.renderAction(ref);
    setTimeout(() => { convo.status = 'typing'; this.renderAction(ref); }, REPLY_DELAY_MS - 3500);
    setTimeout(() => {
      convo.status = 'replied';
      this.renderAction(ref);
      const slot = this.slots.get(ref)?.slot;
      if (this.isOpen && slot?.isConnected) slot.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      else this.onReply(expert.name);
    }, REPLY_DELAY_MS);
  }
}

/** Small, non-blocking flag shown when doubt is detected but the panel isn't opened automatically. */
export class Nudge {
  private host: HTMLElement;
  private button: HTMLElement;
  private title: HTMLElement;
  private sub: HTMLElement;
  private hideTimer: number | undefined;
  onClick: () => void = () => {};

  constructor() {
    loadFont();
    this.host = h('whoknows-nudge');
    isolateKeys(this.host);
    const root = this.host.attachShadow({ mode: 'open' });
    this.title = h('span', {});
    this.sub = h('small', {});
    this.button = h('button', { class: 'nudge', type: 'button' }, createLogo(), h('span', {}, this.title, this.sub));
    this.button.addEventListener('click', () => { this.hide(); this.onClick(); });
    root.append(h('style', {}, STYLE), this.button);
  }

  show(title: string, sub: string, prefix = 'Not sure? ') {
    this.title.replaceChildren(h('b', {}, prefix), title);
    this.sub.textContent = sub;
    // Re-append to replay the pop-in animation.
    this.host.remove();
    document.documentElement.append(this.host);
    clearTimeout(this.hideTimer);
    this.hideTimer = window.setTimeout(() => this.hide(), 15000);
  }

  hide() {
    this.host.remove();
  }
}

let fontLoaded = false;
function loadFont() {
  // @font-face doesn't work inside a shadow root, so the font is registered on the page.
  if (fontLoaded) return;
  fontLoaded = true;
  document.head?.append(h('link', {
    rel: 'stylesheet',
    href: 'https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;600;700;800&display=swap',
  }));
}
