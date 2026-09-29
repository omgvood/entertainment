import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { CITY_CONFIG } from "@/lib/types";

export const metadata: Metadata = { title: "Страница не найдена" };

export default function NotFound() {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-2xl px-4 pt-12 pb-12 flex-1 w-full">
        <h1 className="text-2xl sm:text-[28px] font-extrabold leading-tight mb-3">Страница не найдена</h1>
        <p className="text-[15px] text-muted mb-6">Возможно, её удалили или в адресе опечатка. Афиша городов:</p>
        <div className="flex gap-3 flex-wrap">
          <a href={CITY_CONFIG.perm.path} className="px-[22px] py-[11px] bg-accent text-bg rounded-[10px] font-bold text-[13.5px] hover:bg-accent-hover transition-colors">
            Афиша Перми
          </a>
          <a href={CITY_CONFIG.sochi.path} className="px-[22px] py-[11px] bg-accent text-bg rounded-[10px] font-bold text-[13.5px] hover:bg-accent-hover transition-colors">
            Афиша Сочи
          </a>
        </div>
      </main>
    </>
  );
}
