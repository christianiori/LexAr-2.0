const worksContainer = document.getElementById("home-works");

function formatYear(year) {
  return year < 0 ? `${Math.abs(year)} a.C.` : String(year);
}

function renderWorks(works) {
  worksContainer.replaceChildren();
  works.sort((first, second) => first.year - second.year).forEach((work) => {
    const card = document.createElement("a");
    card.className = "work-card";
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
      worksContainer.innerHTML = "<p class=\"works-loading\">Il catalogo è momentaneamente non disponibile. <a href=\"catalogo/catalogo1.html\">Apri il catalogo classico</a>.</p>";
    });
}
