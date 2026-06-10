/**
 * Доменные типы.
 * Источник истины для данных — план §5 (Модель данных).
 * Когда подключим Postgres (Спринт 1b), эти же типы маппятся на таблицу events.
 */

export type EventType =
  // Узкая ниша MVP-1 (Пермь + Сочи)
  | 'quiz'
  | 'standup'
  | 'bowling'
  | 'billiards'
  | 'karting'
  // Широкая афиша MVP-2 — Timepad (тип по категории), оба города
  | 'concert'
  | 'theater'
  | 'exhibition'
  | 'festival'
  | 'quest'
  | 'party'
  | 'cinema'
  | 'sport'
  | 'education'
  | 'business'
  | 'art'
  | 'kids'
  | 'food'
  | 'trip'
  | 'hobby'
  | 'science'
  | 'other';

export type City = 'perm' | 'sochi';

export const CITY_CONFIG: Record<City, { label: string; path: string; metaTitle: string; metaDescription: string; description: string }> = {
  perm: {
    label: 'Пермь',
    path: '/perm/',
    metaTitle: 'Афиша Пермь — куда сходить сегодня и на выходных',
    metaDescription: 'Афиша Перми: концерты, спектакли, выставки, квизы, стендапы, кино, боулинг и картинг. Расписание, цены, адреса.',
    description: 'Пермь — крупный культурный центр России. Ищете, куда сходить в Перми? Здесь собрана афиша города: концерты, спектакли, выставки, кино, лекции и экскурсии, а также квизы (QuizPlease, Мозгобойня), стендап-шоу, боулинг, бильярд и картинг — с актуальным расписанием, ценами и адресами.',
  },
  sochi: {
    label: 'Сочи',
    path: '/sochi/',
    metaTitle: 'Афиша Сочи — куда сходить сегодня и на выходных',
    metaDescription: 'Афиша Сочи: концерты, спектакли, выставки, квизы, стендапы, кино, боулинг и картинг. Расписание, цены, адреса.',
    description: 'Сочи — курортная столица России на Чёрном море с активной культурной жизнью круглый год: концерты, спектакли, выставки, кино, экскурсии, а также квизы, стендап-вечера, боулинг и картинг. Если ищете, куда сходить в Сочи, — здесь полная афиша с ценами и адресами.',
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
  concert: 'Концерт',
  theater: 'Спектакль',
  exhibition: 'Выставка',
  festival: 'Фестиваль',
  quest: 'Квест',
  party: 'Вечеринка',
  cinema: 'Кино',
  sport: 'Спорт',
  education: 'Образование',
  business: 'Бизнес',
  art: 'Искусство',
  kids: 'Детям',
  food: 'Еда',
  trip: 'Экскурсии',
  hobby: 'Хобби',
  science: 'Наука',
  other: 'Другое',
};
