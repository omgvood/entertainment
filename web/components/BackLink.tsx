"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { City } from "@/lib/types";
import { listStateKey } from "@/lib/urlState";

/** «← Все события» с фильтрами, которые были на главной перед переходом. */
export function BackLink({ city }: { city: City }) {
  const base = `/${city}`;
  const [href, setHref] = useState(base);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(listStateKey(city));
      // eslint-disable-next-line react-hooks/set-state-in-effect -- единоразовое чтение хранилища после монтирования
      if (saved) setHref(base + saved);
    } catch {
      // Хранилище недоступно — остаётся ссылка на главную без фильтров.
    }
  }, [base, city]);

  return (
    <Link href={href} className="inline-flex items-center gap-1 text-sm text-muted hover:text-accent mb-4">
      ← Все события
    </Link>
  );
}
