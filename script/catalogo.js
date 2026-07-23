const menuToggle = document.querySelector(".menu-toggle");
const mainMenu = document.getElementById("menu-principale");
const grid = document.getElementById("catalogue-grid");
const searchInput = document.getElementById("catalogue-search");
const sortSelect = document.getElementById("catalogue-sort");
const filterChips = [...document.querySelectorAll(".filter-chip")];
const resultsCount = document.getElementById("results-count");
const activeFilterLabel = document.getElementById("active-filter-label");
const resetButton = document.getElementById("reset-catalogue");
const emptyResetButton = document.getElementById("empty-reset");
const emptyState = document.getElementById("empty-state");
const filtersToggle = document.getElementById("filters-toggle");
const controls = document.getElementById("catalogue-controls");
const controlsClose = document.getElementById("controls-close");
const controlsBackdrop = document.getElementById("controls-backdrop");

const filterLabels = {
  all: "Catalogo completo",
  lenaiche: "Opere rappresentate alle Lenee",
  dionisiache: "Opere rappresentate alle Dionisie",
  vincitrici: "Opere vincitrici",
  digitale: "Testi digitali disponibili"
};

let activeFilter = "all";
let cards = grid ? [...grid.querySelectorAll(".catalogue-card")] : [];

cards.forEach((card, index) => {
  card.dataset.originalIndex = String(index);
});

function normalise(value) {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase("it")
    .trim();
}

function formatYear(year) {
  return Number(year) < 0 ? `${Math.abs(Number(year))} a.C.` : String(year);
}

function categoriesFor(card) {
  return new Set((card.dataset.categories || "").split(/\s+/).filter(Boolean));
}

function compareCards(first, second, order) {
  const firstTitle = first.dataset.title || "";
  const secondTitle = second.dataset.title || "";
  const firstYear = Number(first.dataset.year || 0);
  const secondYear = Number(second.dataset.year || 0);
  let comparison = 0;

  if (order === "title-asc" || order === "title-desc") {
    comparison = firstTitle.localeCompare(secondTitle, "it", { sensitivity: "base" });
    if (order === "title-desc") comparison *= -1;
  } else {
    comparison = firstYear - secondYear;
    if (order === "date-desc") comparison *= -1;
  }

  if (comparison === 0) {
    return Number(first.dataset.originalIndex) - Number(second.dataset.originalIndex);
  }

  return comparison;
}

function renderCatalogue() {
  if (!grid) return;

  const query = normalise(searchInput?.value || "");
  const sortOrder = sortSelect?.value || "date-asc";
  let visibleCount = 0;

  cards
    .sort((first, second) => compareCards(first, second, sortOrder))
    .forEach((card) => {
      const categories = categoriesFor(card);
      const searchText = normalise([
        card.dataset.title,
        card.dataset.year,
        card.textContent
      ].join(" "));
      const matchesFilter = activeFilter === "all" || categories.has(activeFilter);
      const matchesSearch = !query || searchText.includes(query);
      const isVisible = matchesFilter && matchesSearch;

      card.hidden = !isVisible;
      if (isVisible) visibleCount += 1;
      grid.appendChild(card);
    });

  if (resultsCount) {
    resultsCount.textContent = `${visibleCount} ${visibleCount === 1 ? "opera" : "opere"}`;
  }

  if (activeFilterLabel) {
    activeFilterLabel.textContent = query
      ? `${filterLabels[activeFilter]} · ricerca “${searchInput.value.trim()}”`
      : filterLabels[activeFilter];
  }

  if (emptyState) {
    emptyState.hidden = visibleCount !== 0;
  }
}

function setActiveFilter(filter) {
  activeFilter = filter;
  filterChips.forEach((chip) => {
    const isActive = chip.dataset.filter === filter;
    chip.classList.toggle("is-active", isActive);
    chip.setAttribute("aria-pressed", String(isActive));
  });
  renderCatalogue();
}

function resetCatalogue() {
  if (searchInput) searchInput.value = "";
  if (sortSelect) sortSelect.value = "date-asc";
  setActiveFilter("all");
}

function setMenuOpen(isOpen) {
  if (!menuToggle || !mainMenu) return;
  mainMenu.classList.toggle("is-open", isOpen);
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  menuToggle.setAttribute("aria-label", isOpen ? "Chiudi il menu" : "Apri il menu");
}

function setControlsOpen(isOpen) {
  if (!controls || !filtersToggle || !controlsBackdrop) return;
  controls.classList.toggle("is-open", isOpen);
  filtersToggle.setAttribute("aria-expanded", String(isOpen));
  controlsBackdrop.hidden = !isOpen;
  document.body.classList.toggle("controls-open", isOpen);

  if (isOpen) {
    window.setTimeout(() => searchInput?.focus(), 280);
  } else {
    filtersToggle.focus();
  }
}

function updateCardFromApi(work) {
  const card = cards.find((item) => item.dataset.slug === work.slug);
  if (!card) return;

  const categories = categoriesFor(card);
  work.has_tei ? categories.add("digitale") : categories.delete("digitale");
  card.dataset.categories = [...categories].join(" ");
  card.dataset.title = work.title;
  card.dataset.year = String(work.year);
  card.classList.toggle("is-digital", Boolean(work.has_tei));

  const titleLink = card.querySelector("h3 a");
  const imageLink = card.querySelector(".card-image-link");
  const arrowLink = card.querySelector(".card-arrow");
  const yearBadge = card.querySelector(".year-badge");
  const availability = card.querySelector(".availability");
  const page = String(work.page || "");
  const relativePage = page.startsWith("/") || page.startsWith("../") ? page : `../${page}`;

  if (titleLink) {
    titleLink.textContent = work.title;
    titleLink.href = relativePage;
  }
  if (imageLink) {
    imageLink.href = relativePage;
    imageLink.setAttribute("aria-label", `Apri ${work.title}`);
  }
  if (arrowLink) {
    arrowLink.href = relativePage;
    arrowLink.setAttribute("aria-label", `Vai a ${work.title}`);
  }
  if (yearBadge) yearBadge.textContent = formatYear(work.year);
  if (availability) {
    availability.classList.toggle("is-available", Boolean(work.has_tei));
    availability.lastChild.textContent = work.has_tei ? "Testo digitale" : "Scheda dell’opera";
  }
}

async function synchroniseWithApi() {
  try {
    const response = await fetch("/api/works");
    if (!response.ok) throw new Error("Catalogo API non disponibile");
    const payload = await response.json();
    if (!Array.isArray(payload.works)) throw new Error("Risposta API non valida");
    payload.works.forEach(updateCardFromApi);
    renderCatalogue();
  } catch {
    // Le undici schede statiche rimangono il fallback completo del catalogo.
  }
}

menuToggle?.addEventListener("click", () => {
  setMenuOpen(!mainMenu?.classList.contains("is-open"));
});

filterChips.forEach((chip) => {
  chip.addEventListener("click", () => setActiveFilter(chip.dataset.filter || "all"));
});

searchInput?.addEventListener("input", renderCatalogue);
sortSelect?.addEventListener("change", renderCatalogue);
resetButton?.addEventListener("click", resetCatalogue);
emptyResetButton?.addEventListener("click", resetCatalogue);
filtersToggle?.addEventListener("click", () => setControlsOpen(true));
controlsClose?.addEventListener("click", () => setControlsOpen(false));
controlsBackdrop?.addEventListener("click", () => setControlsOpen(false));

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (controls?.classList.contains("is-open")) {
    setControlsOpen(false);
  } else if (mainMenu?.classList.contains("is-open")) {
    setMenuOpen(false);
    menuToggle?.focus();
  }
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 760 && controls?.classList.contains("is-open")) {
    setControlsOpen(false);
  }
});

renderCatalogue();
synchroniseWithApi();
