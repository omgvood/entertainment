/**
 * Доменные типы.
 * Источник истины для данных — план §5 (Модель данных).
 * Когда подключим Postgres (Спринт 1b), эти же типы маппятся на таблицу events.
 */

export type EventType =
  | 'quiz'
  | 'standup'
  | 'bowling'
  | 'billiards'
  | 'karting';

export type City = 'perm' | 'sochi';

export const CITY_CONFIG: Record<City, { label: string; path: string; metaTitle: string; metaDescription: string; description: string }> = {
  perm: {
    label: 'Пермь',
    path: '/perm/',
    metaTitle: 'Афиша Пермь — куда сходить сегодня и на выходных',
    metaDescription: 'Все мероприятия в Перми: квизы, стендапы, боулинг, бильярд, картинг. Расписание, цены, адреса.',
    description: 'Пермь — крупный культурный центр России. Ищете, куда сходить в Перми? Здесь собраны квизы (QuizPlease, Мозгобойня), стендап-шоу, боулинг-клубы, бильярдные залы и картинг-центры с актуальным расписанием, ценами и адресами.',
  },
  sochi: {
    label: 'Сочи',
    path: '/sochi/',
    metaTitle: 'Афиша Сочи — куда сходить сегодня и на выходных',
    metaDescription: 'Все мероприятия в Сочи: квизы, стендапы, боулинг, бильярд, картинг. Расписание, цены, адреса.',
    description: 'Сочи — курортная столица России на Чёрном море. Активная культурная жизнь круглый год: квизы, стендап-вечера, боулинг и картинг. Если ищете, куда сходить в Сочи, — здесь найдёте полное расписание с ценами и адресами.',
  },
};

/** Дата события: либо ISO `YYYY-MM-DD`, либо маркер `always` для мест-активностей. */
export type EventDate = string | 'always';

export interface EventItem {
  id: string;
  city: City;
  slug: string;
  title: string;
  type: EventType;
  category?: string;
  date: EventDate;
  timeStart?: string; // "HH:MM"
  timeEnd?: string;
  priceMin: number;
  priceMax: number;
  /** Готовая строка для UI: «от 500 до 700 ₽» или «от 300 ₽ за дорожку/час». */
  priceText: string;
  priceNote?: string;
  address: string;
  venueName: string;
  district?: string;
  imageUrl?: string;
  description?: string;
  organizer?: string;
  sourceUrl: string;
  /** Откуда событие пришло: `quizplease` / `manual` / `llm-extract` / ... */
  source: string;
  /** ISO-timestamp последнего парсинга. */
  parsedAt: string;
  metaTitle?: string;
  metaDescription?: string;
}

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  quiz: 'Квиз',
  standup: 'Стендап',
  bowling: 'Боулинг',
  billiards: 'Бильярд',
  karting: 'Картинг',
};
