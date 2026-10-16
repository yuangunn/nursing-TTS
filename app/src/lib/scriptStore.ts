import { Patient } from "./api";

/** A script spec: everything needed to reproduce one script exactly as it was read (template, form, patient,
 *  datetime, register, seed) plus the user's hand edits. */
export interface ScriptHandoff {
  template: string;
  form: Record<string, unknown>;
  patient: Patient;
  datetime: string;
  style: string;
  seed: number | null;
  text_override?: string | null;
}

/** 대본 바구니 (2026-10-17 split): 대본 생성 fills it, 녹음 만들기 reads it. Kept in localStorage so it survives
 *  tab changes and app restarts; the recording page only needs the spec, the text is kept for display. */
export interface BasketItem extends ScriptHandoff {
  id: string;
  record_kind: string;
  spoken_text: string;
  issues: string[];
  added: number;
}

const BASKET = "nursing-tts.script-basket";

export function getBasket(): BasketItem[] {
  try {
    const raw = localStorage.getItem(BASKET);
    return raw ? (JSON.parse(raw) as BasketItem[]) : [];
  } catch {
    return [];
  }
}

function save(items: BasketItem[]): void {
  try { localStorage.setItem(BASKET, JSON.stringify(items)); } catch { /* ignore */ }
}

/** Add a script; the same script (template + seed + register + text) replaces its earlier copy. */
export function addToBasket(item: Omit<BasketItem, "id" | "added">): BasketItem[] {
  const items = getBasket().filter((x) => !(x.template === item.template && x.seed === item.seed && x.style === item.style && (x.text_override ?? "") === (item.text_override ?? "")));
  const it: BasketItem = { ...item, id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, added: Date.now() };
  items.push(it);
  save(items);
  return items;
}

export function removeFromBasket(id: string): BasketItem[] {
  const items = getBasket().filter((x) => x.id !== id);
  save(items);
  return items;
}

export function clearBasket(): void {
  save([]);
}

export function updateBasketText(id: string, text: string | null): BasketItem[] {
  const items = getBasket().map((x) => x.id === id ? { ...x, text_override: text, spoken_text: text ?? x.spoken_text } : x);
  save(items);
  return items;
}
