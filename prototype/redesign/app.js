/* ============================================================
   Афиша — редизайн, интерактивный макет
   Демонстрирует логику нового UI на vanilla JS (без сборки):
   поиск с debounce, чипы типов + «Ещё», группировка по дате,
   тумблер «Только с датой», бейдж «Бесплатно», теги, заглушки.
   Это макет: данные захардкожены, даты считаются от «сегодня».
   ============================================================ */

// ---------- Конфиг типов (цвета/эмодзи из EventCard.tsx) ----------
const TYPES = {
  quiz:       { label: "Квиз",      emoji: "🧠", bg: "#ede7ff", fg: "#5a3eee", grad: ["#ede7ff", "#c8b6ff"], priority: true },
  standup:    { label: "Стендап",   emoji: "🎤", bg: "#ffe7ee", fg: "#d63672", grad: ["#ffe7ee", "#ffb3c1"], priority: true },
  concert:    { label: "Концерт",   emoji: "🎵", bg: "#e7ecff", fg: "#3b5bdb", grad: ["#e7ecff", "#b3c5ff"], priority: true },
  theater:    { label: "Спектакль", emoji: "🎭", bg: "#f3e8ff", fg: "#7e22ce", grad: ["#f3e8ff", "#d8b4fe"], priority: true },
  exhibition: { label: "Выставка",  emoji: "🖼️", bg: "#fff0e7", fg: "#c2410c", grad: ["#fff0e7", "#ffc9a8"], priority: true },
  kids:       { label: "Детям",     emoji: "🧸", bg: "#fff1e7", fg: "#ea580c", grad: ["#fff1e7", "#ffd2b0"], priority: true },
  bowling:    { label: "Боулинг",   emoji: "🎳", bg: "#e7f5ff", fg: "#1971c2", grad: ["#e7f5ff", "#a5d8ff"] },
  billiards:  { label: "Бильярд",   emoji: "🎱", bg: "#e7f9ec", fg: "#2b8a3e", grad: ["#e7f9ec", "#b2f2bb"] },
  karting:    { label: "Картинг",   emoji: "🏎️", bg: "#fff4e0", fg: "#d97706", grad: ["#fff4e0", "#ffd8a8"] },
  festival:   { label: "Фестиваль", emoji: "🎉", bg: "#ffe9f0", fg: "#db2777", grad: ["#ffe9f0", "#fbb6ce"] },
  quest:      { label: "Квест",     emoji: "🗝️", bg: "#e7fbf5", fg: "#0d9488", grad: ["#e7fbf5", "#99f6e4"] },
  cinema:     { label: "Кино",      emoji: "🎬", bg: "#e7eefc", fg: "#2b4ec2", grad: ["#e7eefc", "#a9c2f5"] },
  art:        { label: "Искусство", emoji: "🎨", bg: "#fdeef7", fg: "#a21caf", grad: ["#fdeef7", "#f5c2e7"] },
  education:  { label: "Лекция",    emoji: "🎓", bg: "#eef2ff", fg: "#4f46e5", grad: ["#eef2ff", "#c7d2fe"] },
  trip:       { label: "Экскурсия", emoji: "🧳", bg: "#e7f7f4", fg: "#0f766e", grad: ["#e7f7f4", "#a3e6db"] },
};

// ---------- Даты от «сегодня» ----------
function ymd(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const NOW = new Date();
function offset(days) { const d = new Date(NOW); d.setDate(NOW.getDate() + days); return ymd(d); }
// ближайшая суббота (0..6 дней вперёд) и воскресенье
function nextWeekend() {
  const sat = new Date(NOW), dow = NOW.getDay();
  sat.setDate(NOW.getDate() + ((6 - dow + 7) % 7));
  const sun = new Date(sat); sun.setDate(sat.getDate() + 1);
  return [ymd(sat), ymd(sun)];
}
const [SAT, SUN] = nextWeekend();

// ---------- Тестовые данные ----------
// В макете используем встроенные заглушки (градиент+эмодзи) — самодостаточно, без сети.
// В продакшене сюда придёт реальный imageUrl из БД; код-путь для фото в cardHTML сохранён.
const IMG = (_seed) => null;
const EVENTS = [
  { type: "quiz", title: "QuizPlease «Классика» в баре Сезон", venue: "Бар «Сезон»", date: offset(0), time: "19:00",
    desc: "Лёгкий квиз на эрудицию и кругозор — 7 раундов, призы победителям. Приходите командой 4–6 человек.",
    tags: ["для компании", "интеллектуальное", "вечером"], priceMin: 800, priceMax: 800, priceText: "от 800 ₽", priceNote: "за команду", addr: "ул. Куйбышева, 14", img: IMG("quiz1") },

  { type: "standup", title: "Открытый микрофон в Standup Club Perm", venue: "Standup Club Perm", date: offset(0), time: "20:00",
    desc: "Молодые комики обкатывают новый материал. Атмосфера живая, бывает неровно — но всегда честно.",
    tags: ["вечером", "для компании"], priceMin: 0, priceMax: 0, priceText: "", addr: "ул. Газеты Звезда, 27", img: null },

  { type: "exhibition", title: "Выставка «Свет и форма» в PERMM", venue: "Музей PERMM", date: offset(0), time: "11:00",
    desc: "Современное искусство Урала: инсталляции, графика, медиа. Кураторская экскурсия по выходным.",
    tags: ["днём", "творческое", "в помещении"], priceMin: 300, priceMax: 500, priceText: "от 300 до 500 ₽", addr: "бул. Гагарина, 24", img: IMG("expo1") },

  { type: "concert", title: "Пермская филармония: вечер фортепиано", venue: "Пермская филармония", date: offset(1), time: "19:00",
    desc: "Шопен, Лист и Рахманинов в исполнении лауреата международных конкурсов. Большой зал.",
    tags: ["вечером", "для пары", "в помещении"], priceMin: 600, priceMax: 2500, priceText: "от 600 до 2 500 ₽", addr: "ул. Ленина, 51Б", img: IMG("concert1") },

  { type: "theater", title: "«Чайка» — Театр-Театр", venue: "Театр-Театр", date: offset(1), time: "18:30",
    desc: "Чеховская классика в новой постановке. Премьерный состав, длительность 2 ч 40 мин с антрактом.",
    tags: ["вечером", "для пары"], priceMin: 500, priceMax: 3000, priceText: "от 500 ₽", addr: "ул. Ленина, 53", img: IMG("theater1") },

  { type: "kids", title: "Научное шоу для детей «Опыты»", venue: "Детский центр «Кварки»", date: offset(1), time: "12:00",
    desc: "Зрелищные эксперименты с азотом, электричеством и химией. Для детей 5–12 лет с родителями.",
    tags: ["для детей", "днём", "творческое"], priceMin: 700, priceMax: 700, priceText: "700 ₽", addr: "ш. Космонавтов, 65", img: IMG("kids1") },

  { type: "festival", title: "Городской фестиваль уличной еды", venue: "Эспланада", date: SAT, time: "12:00",
    desc: "Фудкорты, бренд-шефы, музыка и маркет. Свободный вход, оплата только за еду.",
    tags: ["для компании", "на улице", "днём", "еда"], priceMin: 0, priceMax: 0, priceText: "", addr: "Эспланада, центр", img: IMG("fest1") },

  { type: "concert", title: "Indie-вечер: местные группы", venue: "Клуб «Дом музыки»", date: SAT, time: "20:00",
    desc: "Четыре пермские группы на одной сцене. Гитарный звук, новые имена сцены.",
    tags: ["вечером", "для компании"], priceMin: 500, priceMax: 800, priceText: "от 500 до 800 ₽", addr: "ул. Сибирская, 8", img: IMG("concert2") },

  { type: "trip", title: "Пешая экскурсия по старой Перми", venue: "Сбор у Театра оперы", date: SUN, time: "13:00",
    desc: "Два часа по историческому центру с краеведом: купеческие особняки, легенды и забытые улицы.",
    tags: ["днём", "на улице", "для пары"], priceMin: 400, priceMax: 400, priceText: "400 ₽", addr: "ул. Петропавловская, 25А", img: IMG("trip1") },

  { type: "cinema", title: "Кинопоказ под открытым небом", venue: "Парк Горького", date: SUN, time: "21:00",
    desc: "Классика мирового кино на большом экране. Пледы и горячий чай — берите с собой.",
    tags: ["вечером", "на улице", "для пары"], priceMin: 0, priceMax: 0, priceText: "", addr: "ул. Сибирская, 49", img: IMG("cinema1") },

  { type: "standup", title: "Денис Чужой — сольный концерт", venue: "ДК им. Солдатова", date: offset(9), time: "20:00",
    desc: "Большой сольник топового стендап-комика. Полный новый час материала.",
    tags: ["вечером", "для компании"], priceMin: 1500, priceMax: 3500, priceText: "от 1 500 до 3 500 ₽", addr: "ул. Кузбасская, 2", img: IMG("standup2") },

  { type: "education", title: "Лекция «История модернизма»", venue: "Библиотека им. Горького", date: offset(12), time: "18:00",
    desc: "Искусствовед рассказывает о ключевых направлениях XX века. Свободный вход по регистрации.",
    tags: ["интеллектуальное", "вечером", "в помещении"], priceMin: 0, priceMax: 0, priceText: "", addr: "ул. Ленина, 70", img: null },

  // --- Постоянные места (always) ---
  { type: "bowling", title: "Боулинг «Капитан»", venue: "ТРК СпешиLOVE", date: "always",
    desc: "12 дорожек, бар и зона отдыха. Бронь по телефону, дневные тарифы дешевле.",
    tags: ["для компании", "активное", "в помещении"], priceMin: 300, priceMax: 600, priceText: "от 300 до 600 ₽", priceNote: "за дорожку/час", addr: "ш. Космонавтов, 65", img: IMG("bowl1") },

  { type: "billiards", title: "Бильярдный клуб «8 шар»", venue: "Клуб «8 шар»", date: "always",
    desc: "Русский бильярд и пул, 10 столов. Работает до последнего гостя.",
    tags: ["для компании", "активное"], priceMin: 250, priceMax: 450, priceText: "от 250 до 450 ₽", priceNote: "за стол/час", addr: "ул. Революции, 13", img: IMG("bil1") },

  { type: "karting", title: "Forsage Karting", venue: "Картинг-центр Forsage", date: "always",
    desc: "Крытый трек 400 м, прокатные карты до 60 км/ч. Заезды и групповые гонки.",
    tags: ["активное", "для компании"], priceMin: 700, priceMax: 1200, priceText: "от 700 до 1 200 ₽", priceNote: "за заезд", addr: "ул. Героев Хасана, 105", img: IMG("kart1") },
];

// ---------- Состояние ----------
const state = {
  search: "",
  types: new Set(),       // пусто = показывать все
  when: "any",
  priceMin: 0,
  priceMax: 5000,
  datedOnly: false,
};

// ---------- Утилиты ----------
function plural(n) {
  const m10 = n % 10, m100 = n % 100;
  if (m100 >= 11 && m100 <= 14) return "событий";
  if (m10 === 1) return "событие";
  if (m10 >= 2 && m10 <= 4) return "события";
  return "событий";
}
const MONTHS = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
function humanDate(iso) {
  const [, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]}`;
}
function cardDate(ev) {
  if (ev.date === "always") return "ежедневно";
  return ev.time ? `${humanDate(ev.date)}, ${ev.time}` : humanDate(ev.date);
}

// debounce
function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ---------- Фильтрация ----------
function applyFilters() {
  const q = state.search.trim().toLowerCase();
  return EVENTS.filter((ev) => {
    if (state.types.size && !state.types.has(ev.type)) return false;
    if (state.datedOnly && ev.date === "always") return false;
    if (state.when !== "any") {
      if (state.when === "today" && ev.date !== offset(0)) return false;
      if (state.when === "tomorrow" && ev.date !== offset(1)) return false;
      if (state.when === "weekend" && ev.date !== SAT && ev.date !== SUN) return false;
    }
    if (ev.priceMax < state.priceMin) return false;
    if (ev.priceMin > state.priceMax) return false;
    if (q) {
      const hay = [ev.title, ev.venue, ev.addr].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

// ---------- Группировка по дате ----------
function groupByDate(list) {
  const today = offset(0), tomorrow = offset(1);
  const buckets = { today: [], tomorrow: [], weekend: [], later: [], always: [] };
  for (const ev of list) {
    if (ev.date === "always") buckets.always.push(ev);
    else if (ev.date === today) buckets.today.push(ev);
    else if (ev.date === tomorrow) buckets.tomorrow.push(ev);
    else if (ev.date === SAT || ev.date === SUN) buckets.weekend.push(ev);
    else buckets.later.push(ev);
  }
  return [
    { key: "today",    title: "Сегодня",        date: humanDate(today),     items: buckets.today },
    { key: "tomorrow", title: "Завтра",         date: humanDate(tomorrow),  items: buckets.tomorrow },
    { key: "weekend",  title: "Эти выходные",   date: `${humanDate(SAT)}–${humanDate(SUN)}`, items: buckets.weekend },
    { key: "later",    title: "Позже",          date: "",                   items: buckets.later },
    { key: "always",   title: "Всегда открыто", date: "",                   items: buckets.always },
  ].filter((s) => s.items.length);
}

// ---------- Рендер карточки ----------
function cardHTML(ev) {
  const t = TYPES[ev.type];
  const imageInner = ev.img
    ? ""
    : `<span class="emoji">${t.emoji}</span>`;
  const imageStyle = ev.img
    ? `background-image:url('${ev.img}')`
    : `background-image:linear-gradient(135deg, ${t.grad[0]}, ${t.grad[1]})`;

  const isFree = ev.priceMin === 0 && ev.priceMax === 0;
  const priceHTML = isFree
    ? `<span class="badge-free">Бесплатно</span>`
    : `<span class="card-price">${ev.priceText || `от ${ev.priceMin} ₽`}${ev.priceNote ? `<small>${ev.priceNote}</small>` : ""}</span>`;

  const shown = ev.tags.slice(0, 3);
  const extra = ev.tags.length - shown.length;
  const tagsHTML = `<div class="card-tags">${shown.map((x) => `<span class="tag">${x}</span>`).join("")}${extra > 0 ? `<span class="tag">+${extra}</span>` : ""}</div>`;

  return `
    <a class="card" href="#">
      <div class="card-image" style="${imageStyle}">${imageInner}</div>
      <div class="card-body">
        <div class="card-top">
          <span class="badge" style="background:${t.bg};color:${t.fg}">${t.label}</span>
          <span class="card-date">📅 ${cardDate(ev)}</span>
        </div>
        <h3 class="card-title">${ev.title}</h3>
        <div class="card-venue">${ev.venue}</div>
        ${ev.desc ? `<p class="card-desc">${ev.desc}</p>` : ""}
        ${tagsHTML}
        <div class="card-foot">
          ${priceHTML}
          <span class="card-addr">📍 ${ev.addr}</span>
        </div>
      </div>
    </a>`;
}

// ---------- Рендер ----------
function render() {
  const list = applyFilters();
  document.getElementById("count").textContent = list.length;
  document.getElementById("countWord").textContent = plural(list.length);

  const root = document.getElementById("sections");
  if (!list.length) {
    root.innerHTML = `
      <div class="empty">
        <div class="ico">🔍</div>
        <h3>Ничего не найдено</h3>
        <p>Попробуйте изменить фильтры, расширить диапазон цен или сбросить поиск.</p>
        <button id="reset">Сбросить фильтры</button>
      </div>`;
    document.getElementById("reset").onclick = resetFilters;
    return;
  }

  root.innerHTML = groupByDate(list).map((s) => `
    <section class="section ${s.key === "always" ? "always" : ""}">
      <div class="section-head">
        <h2 class="section-title">${s.title}</h2>
        ${s.date ? `<span class="section-date">${s.date}</span>` : ""}
        <span class="section-count">${s.items.length} ${plural(s.items.length)}</span>
      </div>
      <div class="grid">${s.items.map(cardHTML).join("")}</div>
    </section>`).join("");
}

function resetFilters() {
  state.search = ""; state.types.clear(); state.when = "any";
  state.priceMin = 0; state.priceMax = 5000; state.datedOnly = false;
  document.getElementById("search").value = "";
  document.getElementById("priceMin").value = 0;
  document.getElementById("priceMax").value = 5000;
  document.getElementById("datedOnly").checked = false;
  document.querySelectorAll(".when button").forEach((b) => b.classList.toggle("active", b.dataset.when === "any"));
  buildChips();
  render();
}

// ---------- Чипы типов + «Ещё» ----------
function toggleType(type) {
  if (state.types.has(type)) state.types.delete(type);
  else state.types.add(type);
}

function buildChips() {
  const wrap = document.getElementById("chips");
  const priority = Object.entries(TYPES).filter(([, v]) => v.priority);
  const rest = Object.entries(TYPES).filter(([, v]) => !v.priority);

  wrap.innerHTML =
    priority.map(([k, v]) =>
      `<button class="chip ${state.types.has(k) ? "active" : ""}" data-type="${k}">
         <span class="chip-emoji">${v.emoji}</span>${v.label}
       </button>`).join("") +
    `<div class="more-wrap">
       <button class="chip" id="moreBtn">Ещё ▾</button>
       <div class="more-menu" id="moreMenu">
         ${rest.map(([k, v]) =>
           `<div class="more-item ${state.types.has(k) ? "active" : ""}" data-type="${k}">
              <span class="chip-emoji">${v.emoji}</span><span>${v.label}</span>
              <span class="check">✓</span>
            </div>`).join("")}
       </div>
     </div>`;

  // приоритетные чипы
  wrap.querySelectorAll(".chip[data-type]").forEach((btn) => {
    btn.onclick = () => { toggleType(btn.dataset.type); btn.classList.toggle("active"); render(); };
  });

  // дропдаун «Ещё»
  const moreBtn = document.getElementById("moreBtn");
  const menu = document.getElementById("moreMenu");
  moreBtn.onclick = (e) => { e.stopPropagation(); menu.classList.toggle("open"); };
  // mousedown + preventDefault — пункт не закрывает меню (мультиселект подряд)
  menu.querySelectorAll(".more-item").forEach((item) => {
    item.addEventListener("mousedown", (e) => {
      e.preventDefault();
      toggleType(item.dataset.type);
      item.classList.toggle("active");
      moreBtn.classList.toggle("active", [...rest].some(([k]) => state.types.has(k)));
      render();
    });
  });
}

// клик вне меню — закрыть
document.addEventListener("click", (e) => {
  const menu = document.getElementById("moreMenu");
  if (menu && !e.target.closest(".more-wrap")) menu.classList.remove("open");
});

// ---------- Привязка контролов ----------
const debouncedSearch = debounce((v) => { state.search = v; render(); }, 300);
document.getElementById("search").addEventListener("input", (e) => debouncedSearch(e.target.value));

document.getElementById("when").addEventListener("click", (e) => {
  const btn = e.target.closest("button"); if (!btn) return;
  state.when = btn.dataset.when;
  document.querySelectorAll(".when button").forEach((b) => b.classList.toggle("active", b === btn));
  render();
});

document.getElementById("priceMin").addEventListener("input", (e) => { state.priceMin = Math.max(0, +e.target.value || 0); render(); });
document.getElementById("priceMax").addEventListener("input", (e) => { state.priceMax = Math.max(0, +e.target.value || 0); render(); });
document.getElementById("datedOnly").addEventListener("change", (e) => { state.datedOnly = e.target.checked; render(); });

// ---------- Старт ----------
buildChips();
render();
