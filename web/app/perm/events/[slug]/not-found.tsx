import { Header } from "@/components/Header";
import { CITY_CONFIG } from "@/lib/types";

export default function EventNotFound() {
  return (
    <>
      <Header city="perm" />
      <main className="mx-auto max-w-2xl px-4 pt-12 pb-12 flex-1 w-full">
        <h1 className="text-2xl sm:text-[28px] font-extrabold leading-tight mb-3">Событие не найдено</h1>
        <p className="text-[15px] text-muted mb-6">Возможно, оно уже прошло и удалено из афиши.</p>
        <a href={CITY_CONFIG.perm.path} className="inline-block px-[22px] py-[11px] bg-accent text-bg rounded-[10px] font-bold text-[13.5px] hover:bg-accent-hover transition-colors">
          Что идёт в Перми →
        </a>
      </main>
    </>
  );
}
