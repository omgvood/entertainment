import { describe, it, expect } from "vitest";
import { eventTimeStatus, isAvailable } from "./eventTiming";

const TODAY = "2026-09-22";

const ev = (overrides: Partial<Parameters<typeof eventTimeStatus>[0]> = {}) => ({
  date: TODAY,
  timeStart: "18:00",
  timeEnd: undefined as string | undefined,
  source: "vk-posts",
  ...overrides,
});

describe("eventTimeStatus", () => {
  it("для события не сегодня меток нет", () => {
    expect(eventTimeStatus(ev({ date: "2026-09-23" }), TODAY, 19 * 60)).toEqual({
      kind: "none",
    });
  });

  it("для постоянной площадки (date='always') меток нет", () => {
    expect(eventTimeStatus(ev({ date: "always" }), TODAY, 19 * 60)).toEqual({
      kind: "none",
    });
  });

  it("без time_start меток нет", () => {
    expect(
      eventTimeStatus(ev({ timeStart: undefined }), TODAY, 19 * 60),
    ).toEqual({ kind: "none" });
  });

  it("надёжный time_end и текущий момент внутри интервала — «идёт сейчас»", () => {
    const status = eventTimeStatus(
      ev({ timeStart: "18:00", timeEnd: "20:00" }),
      TODAY,
      19 * 60,
    );
    expect(status).toEqual({ kind: "live" });
  });

  it("time_end источника generic:filarmonia.online не считается надёжным (тикет 11)", () => {
    const status = eventTimeStatus(
      ev({
        timeStart: "19:00",
        timeEnd: "22:00",
        source: "generic:filarmonia.online",
      }),
      TODAY,
      19 * 60 + 30,
    );
    expect(status).not.toEqual({ kind: "live" });
  });

  it("событие ещё не началось — «через N ч»", () => {
    const status = eventTimeStatus(
      ev({ timeStart: "21:00" }),
      TODAY,
      19 * 60,
    );
    expect(status).toEqual({ kind: "upcoming", label: "через 2 ч" });
  });

  it("началось меньше 3 ч назад — «началось в HH:MM», не устарело", () => {
    const status = eventTimeStatus(
      ev({ timeStart: "18:00" }),
      TODAY,
      19 * 60 + 30,
    );
    expect(status).toEqual({ kind: "started", label: "началось в 18:00", stale: false });
  });

  it("началось 3 ч назад и больше — «началось N ч назад», устарело", () => {
    const status = eventTimeStatus(
      ev({ timeStart: "15:00" }),
      TODAY,
      19 * 60,
    );
    expect(status).toEqual({ kind: "started", label: "началось 4 ч назад", stale: true });
  });
});

describe("isAvailable", () => {
  it("событие без time_start доступно (нечем оценить)", () => {
    expect(isAvailable(ev({ timeStart: undefined }), TODAY, 19 * 60)).toBe(true);
  });

  it("событие, начавшееся меньше 3 ч назад, доступно", () => {
    expect(isAvailable(ev({ timeStart: "18:00" }), TODAY, 19 * 60 + 30)).toBe(true);
  });

  it("событие, начавшееся 3 ч назад и больше, недоступно (счётчики его не считают)", () => {
    expect(isAvailable(ev({ timeStart: "15:00" }), TODAY, 19 * 60)).toBe(false);
  });

  it("событие другого дня доступно (порог применяется только к сегодняшним)", () => {
    expect(
      isAvailable(ev({ date: "2026-09-20", timeStart: "10:00" }), TODAY, 19 * 60),
    ).toBe(true);
  });
});
