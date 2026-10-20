// Reads the text you're typing and the conversation you're replying to (Gmail, the demo pages, or any page).

export type Editable = HTMLTextAreaElement | HTMLElement;

const isGmail = () => location.hostname === 'mail.google.com';

export function isEditable(el: EventTarget | null): el is Editable {
  if (!(el instanceof HTMLElement)) return false;
  if (el.closest('whoknows-panel, whoknows-nudge')) return false;
  return el instanceof HTMLTextAreaElement || el.isContentEditable;
}

/** For contenteditable, events can target a nested node; use the editing host. */
export function editableRoot(el: HTMLElement): Editable {
  let node = el;
  while (node.parentElement?.isContentEditable) node = node.parentElement;
  return node;
}

/** What the user wrote themselves, without Gmail's quoted thread or signature. */
export function ownText(el: Editable): string {
  if (el instanceof HTMLTextAreaElement) return el.value;
  if (!isGmail()) return el.innerText;
  const clone = el.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('.gmail_quote, .gmail_signature, blockquote, [data-smartmail]').forEach((n) => n.remove());
  return clone.innerText;
}

function visible(el: HTMLElement) {
  return el.offsetParent !== null || el.getClientRects().length > 0;
}

function gmailContext(field: Element | null): string {
  const parts: string[] = [];
  const subject = document.querySelector<HTMLElement>('h2.hP')?.innerText;
  if (subject) parts.push(subject);
  // Opened messages in the thread (.a3s is Gmail's message body), excluding compose windows.
  const bodies = [...document.querySelectorAll<HTMLElement>('.a3s')].filter((b) => visible(b) && !b.closest('[contenteditable="true"]'));
  parts.push(...bodies.slice(-2).map((b) => b.innerText));
  // New message: use the subject line of the compose window.
  const compose = field?.closest('form, [role="dialog"], .M9');
  const subjectBox = compose?.querySelector<HTMLInputElement>('input[name="subjectbox"]')?.value;
  if (subjectBox) parts.push(subjectBox);
  return parts.join('\n').slice(-2000);
}

function genericContext(field: Element | null): string {
  let node = field?.parentElement ?? null;
  while (node && node !== document.body) {
    const text = node.innerText.replace(field instanceof HTMLElement ? field.innerText : '', '');
    if (text.trim().length > 80) break;
    node = node.parentElement;
  }
  return (node ?? document.body).innerText.slice(-2000);
}

/** The message you're replying to. */
export function replyContext(field: Element | null): string {
  return isGmail() ? gmailContext(field) : genericContext(field);
}

function sentences(text: string): string[] {
  return text.split(/(?<=[.!?])\s+|\n+/).map((s) => s.trim()).filter((s) => s.length > 3);
}

/** Best guess at the question being answered: the last question in the thread, else the last sentence typed. */
export function suggestQuestion(context: string, own: string): string {
  const asked = sentences(context).filter((s) => s.endsWith('?'));
  if (asked.length) return asked[asked.length - 1] ?? '';
  const typed = sentences(own);
  return typed[typed.length - 1] ?? '';
}
