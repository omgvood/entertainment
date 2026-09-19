import Link from "next/link";
import type { EventItem } from "@/lib/types";
import { compareByDateTime, groupByDate } from "@/lib/series";
import { formatWeekdayDayMonth } from "@/lib/dateUtil";

export function OtherDates({ current, siblings }: { current: EventItem; siblings: EventItem[] }) {
  if (siblings.length === 0) return null;

  const days = groupByDate([current, ...siblings].sort(compareByDateTime), (e) => e.date);

  return (
    <section className="mt-6">
      <h2 className="text-[13px] font-semibold text-muted uppercase tracking-wider mb-2.5">
        Другие даты
      </h2>
      <ul className="flex flex-col gap-1.5 text-[14px]">
        {days.map((day) => (
          <li key={day.date} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-semibold">{formatWeekdayDayMonth(day.date)}</span>
            {day.items.map((e) =>
              e.id === current.id ? (
                <span key={e.id} className="text-accent">
                  {e.timeStart ?? "время не указано"} · эта дата
                </span>
              ) : (
                <Link
                  key={e.id}
                  href={`/${e.city}/events/${e.slug}/`}
                  className="text-muted hover:text-accent hover:underline underline-offset-2"
                >
                  {e.timeStart ?? "время не указано"}
                </Link>
              ),
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
