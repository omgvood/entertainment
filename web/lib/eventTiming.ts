/**
 * Метка времени карточки быстрого просмотра для событий сегодняшнего дня —
 * решение тикета 06 (docs/superpowers/wayfinder/p2-data-fixes/issues/06-now-and-past-policy.md).
 */

import type { EventItem } from "./types";

export type EventTimeStatus =
  | { kind: "none" }
  | { kind: "live" }
  | { kind: "upcoming"; label: string }
  | { kind: "started"; label: string; stale: boolean };

/** Порог «начавшееся сегодня» — решение тикета 06: 3 ч от time_start. */
const STARTED_STALE_THRESHOLD_MIN = 180;

/**
 * Источники, чей time_end — шаблон разметки, а не факт (тикет 11: у всех
 * событий generic:filarmonia.online endDate = startDate + 180 мин без исключений).
 */
const UNRELIABLE_TIME_END_SOURCES = new Set(["generic:filarmonia.online"]);

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function formatHHMM(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function eventTimeStatus(
  event: Pick<EventItem, "date" | "timeStart" | "timeEnd" | "source">,
  today: string,
  nowMinutes: number,
): EventTimeStatus {
  if (event.date !== today || !event.timeStart) return { kind: "none" };

  const startMin = toMinutes(event.timeStart);
  const hasReliableEnd = event.timeEnd && !UNRELIABLE_TIME_END_SOURCES.has(event.source);
  if (hasReliableEnd) {
    const endMin = toMinutes(event.timeEnd!);
    if (nowMinutes >= startMin && nowMinutes <= endMin) return { kind: "live" };
  }

  const diff = nowMinutes - startMin;
  if (diff < 0) {
    const hoursUntil = Math.max(1, Math.round(-diff / 60));
    return { kind: "upcoming", label: `через ${hoursUntil} ч` };
  }
  if (diff < STARTED_STALE_THRESHOLD_MIN) {
    return { kind: "started", label: `началось в ${formatHHMM(startMin)}`, stale: false };
  }
  const hoursAgo = Math.round(diff / 60);
  return { kind: "started", label: `началось ${hoursAgo} ч назад`, stale: true };
}

/**
 * Считать ли событие в счётчиках чипов даты — решение тикета 06, пункт 3:
 * «доступное» = time_start неизвестен ИЛИ порог 3 ч ещё не прошёл. Событие
 * из счёта не пропадает из ленты — только из числа.
 */
export function isAvailable(
  event: Pick<EventItem, "date" | "timeStart" | "timeEnd" | "source">,
  today: string,
  nowMinutes: number,
): boolean {
  const status = eventTimeStatus(event, today, nowMinutes);
  return !(status.kind === "started" && status.stale);
}
