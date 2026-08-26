const vocabularyParameters = new URLSearchParams(window.location.search);

function normaliseVocabularyTerm(value) {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("el")
    .trim();
}

function vocabularyContextNotice(workFilter) {
  const container = document.getElementById("terms-container");
  if (!container || !workFilter) return null;

  const notice = document.createElement("aside");
  notice.className =
    "alert alert-info d-flex flex-wrap align-items-center justify-content-between gap-2";
  notice.setAttribute("aria-label", "Collegamento all’opera di provenienza");

  const message = document.createElement("span");
  message.textContent = `Lessico filtrato per ${workFilter}.`;
  notice.appendChild(message);

  if (workFilter === "Acarnesi") {
    const backLink = document.createElement("a");
    backLink.className = "btn btn-sm btn-outline-dark";
    backLink.href = "../item/acarnesi.html#testo";
    backLink.textContent = "Torna al testo degli Acarnesi";
    notice.appendChild(backLink);
  }

  container.before(notice);
  return notice;
}

document.addEventListener("DOMContentLoaded", () => {
  const sourceSlug = vocabularyParameters.get("from");
  const workFilter =
    vocabularyParameters.get("filter") ||
    ({ acarnesi: "Acarnesi" }[sourceSlug] ?? null);
  const requestedTerm = vocabularyParameters.get("term")?.trim();
  const notice = vocabularyContextNotice(workFilter);
  if (!requestedTerm) return;

  const searchFields = [
    document.getElementById("search-bar"),
    document.getElementById("search-bar-colonnasx"),
  ].filter(Boolean);
  searchFields.forEach((field) => {
    field.value = requestedTerm;
  });

  ["search-greek-main", "search-greek-side"].forEach((identifier) => {
    const checkbox = document.getElementById(identifier);
    if (checkbox) checkbox.checked = true;
  });
  searchFields[0]?.dispatchEvent(new Event("input", { bubbles: true }));

  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      const normalisedRequest = normaliseVocabularyTerm(requestedTerm);
      const match = [...document.querySelectorAll(".term")].find((term) => {
        const headword = term.querySelector("b")?.textContent || "";
        return normaliseVocabularyTerm(headword) === normalisedRequest;
      });

      if (!match) {
        const status = document.createElement("p");
        status.className = "mb-0 text-danger";
        status.setAttribute("role", "status");
        status.textContent = `La voce “${requestedTerm}” non è ancora disponibile.`;
        (notice || document.getElementById("terms-container"))?.prepend(status);
        return;
      }

      match.id = `voce-${normalisedRequest.replace(/[^a-z\p{L}\p{N}]+/gu, "-")}`;
      match.tabIndex = -1;
      match.classList.add("border", "border-info", "rounded", "p-2");
      match.scrollIntoView({ block: "center" });
      match.focus({ preventScroll: true });
    });
  });
});
