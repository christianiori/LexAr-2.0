const worksContainer = document.getElementById("home-works");
const menuToggle = document.querySelector(".menu-toggle");
const mainMenu = document.getElementById("menu-principale");

if (menuToggle && mainMenu) {
  const setMenuOpen = (isOpen) => {
    mainMenu.classList.toggle("is-open", isOpen);
    menuToggle.setAttribute("aria-expanded", String(isOpen));
    menuToggle.setAttribute(
      "aria-label",
      isOpen ? "Chiudi il menu" : "Apri il menu"
    );
  };

  menuToggle.addEventListener("click", () => {
    setMenuOpen(!mainMenu.classList.contains("is-open"));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setMenuOpen(false);
      menuToggle.focus();
    }
  });
}

function formatYear(year) {
  return year < 0 ? `${Math.abs(year)} a.C.` : String(year);
}

function renderWorks(works) {
  worksContainer.replaceChildren();

  [...works]
    .sort((first, second) => first.year - second.year)
    .slice(0, 3)
    .forEach((work) => {
      const card = document.createElement("a");
      card.className = `work-card ${work.has_tei ? "is-digital" : ""}`;
      card.href = work.page;

      const year = document.createElement("span");
      year.className = "work-year";
      year.textContent = formatYear(work.year);

      const title = document.createElement("h3");
      title.textContent = work.title;

      const status = document.createElement("span");
      status.className = `work-status ${work.has_tei ? "is-available" : ""}`;
      status.textContent = work.has_tei ? "Testo digitale disponibile" : "Scheda dell’opera";

      const arrow = document.createElement("span");
      arrow.className = "work-arrow";
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "→";

      card.append(year, title, status, arrow);
      worksContainer.appendChild(card);
    });
}

if (worksContainer) {
  fetch("/api/works")
    .then((response) => {
      if (!response.ok) throw new Error("Catalogo non disponibile");
      return response.json();
    })
    .then(({ works }) => renderWorks(works))
    .catch(() => {
      // Le tre card presenti nell'HTML restano disponibili come fallback statico.
    });
}
