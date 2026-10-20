// content.ts: this file runs inside every web page you visit
import { init, WeightedKeyword } from './keywords';

// Ask the "background" file to talk to the LLM for us
const callLLM = (system: string, user: string): Promise<string> =>
  chrome.runtime.sendMessage({ type: 'llm', system, user });

// This is where the keywords go once found.
// TODO: replace console.log with a call to the database person's endpoint.
async function handOff(keywords: WeightedKeyword[]) {
  console.log('[Doubt Helper] Keywords for the next person:', keywords);
}

init(callLLM, handOff);
console.log('[Doubt Helper] is watching this page');
