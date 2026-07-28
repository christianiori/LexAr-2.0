const workPage = document.querySelector(".work-page");
const workSlug = workPage?.dataset.work;

const termList = document.getElementById("term-list");
const termStatus = document.getElementById("term-status");
const textToggle = document.getElementById("text-toggle");
const textReader = document.getElementById("text-reader");
const textStatus = document.getElementById("text-status");
const textContent = document.getElementById("tei-content");
const textSearch = document.getElementById("text-search");
const readerCount = document.getElementById("reader-count");
const readerEmpty = document.getElementById("reader-empty");

const lexiconProfiles = {
  acarnesi: {
    terms: [
      { term: "πόλις", frequency: 19 },
      { term: "χοῖρος", frequency: 19 },
      { term: "σπονδή", frequency: 15 },
      { term: "εἰρήνη", frequency: 10 },
      { term: "ἀγορά", frequency: 9 },
      { term: "ἀσπίς", frequency: 9 },
      { term: "πόλεμος", frequency: 9 },
      { term: "πρεσβευτής", frequency: 9 },
      { term: "δραχμή", frequency: 9 },
    ],
  },
};

let textLoaded = false;
let textLoading = false;
let speechElements = [];

const normaliseSearchText = (value) =>
  value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("el")
    .trim();

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Richiesta non riuscita: ${response.status}`);
  }
  return response.json();
}

function renderTerms(terms) {
  if (!termList || !termStatus) return;

  termList.replaceChildren();
  const maximum = Math.max(...terms.map((item) => item.frequency), 1);
  const fragment = document.createDocumentFragment();

  terms.forEach((item) => {
    const listItem = document.createElement("li");
    listItem.className = "term-item";
    const relativeFrequency = Math.sqrt(item.frequency / maximum);
    listItem.style.setProperty(
      "--bubble-size",
      `${Math.max(92, Math.round(relativeFrequency * 150))}px`
    );
    listItem.style.setProperty(
      "--bubble-size-mobile",
      `${Math.max(84, Math.round(relativeFrequency * 126))}px`
    );

    const word = document.createElement("span");
    word.className = "term-word";
    const letterCount = normaliseSearchText(item.term).length;
    if (letterCount >= 10) {
      word.classList.add("is-very-long");
    } else if (letterCount >= 8) {
      word.classList.add("is-long");
    }
    word.lang = "grc";
    word.textContent = item.term;

    const frequency = document.createElement("span");
    frequency.className = "term-frequency";
    frequency.textContent = item.frequency;

    const frequencyLabel = document.createElement("span");
    frequencyLabel.className = "visually-hidden";
    frequencyLabel.textContent = " occorrenze";
    frequency.appendChild(frequencyLabel);

    listItem.append(word, frequency);
    fragment.appendChild(listItem);
  });

  termList.appendChild(fragment);
  termStatus.hidden = true;
}

function loadTerms() {
  if (!workSlug || !termList || !termStatus) return;

  const terms = lexiconProfiles[workSlug]?.terms;
  if (!terms?.length) {
    termStatus.classList.add("is-error");
    termStatus.textContent =
      "Il lessico curato non è disponibile in questo momento.";
    return;
  }

  renderTerms(terms);
}

function sectionTitle(value) {
  if (!value) return "Sezione non indicata";
  return value.startsWith("Coro") ? value : `Scena ${value}`;
}

function createSpeechElement(speech) {
  const article = document.createElement("article");
  article.className = "tei-speech";
  if (speech.id) article.id = speech.id;
  if (speech.section_id) article.dataset.section = speech.section_id;
  if (speech.speaker_ref) {
    article.dataset.speaker = speech.speaker_ref.replace(/^#/, "");
  }

  const speaker = document.createElement("strong");
  speaker.className = "tei-speaker";
  speaker.textContent = speech.speaker || "Voce non indicata";

  const lines = document.createElement("div");
  lines.className = "tei-lines";

  speech.lines.forEach((lineText) => {
    const line = document.createElement("p");
    line.className = "tei-line";
    line.textContent = lineText;
    lines.appendChild(line);
  });

  article.dataset.search = normaliseSearchText(
    `${speech.speaker || ""} ${speech.lines.join(" ")}`
  );
  article.append(speaker, lines);
  return article;
}

function renderText(speeches) {
  if (!textContent || !textStatus) return;

  const fragment = document.createDocumentFragment();
  let currentSectionKey = null;
  let sectionElement = null;
  speechElements = [];

  speeches.forEach((speech) => {
    const sectionKey = speech.section_id || speech.scene;
    if (!sectionElement || sectionKey !== currentSectionKey) {
      currentSectionKey = sectionKey;
      sectionElement = document.createElement("section");
      sectionElement.className = "tei-scene";
      if (speech.section_id) sectionElement.id = speech.section_id;

      const heading = document.createElement("h3");
      heading.className = "scene-heading";
      heading.textContent = sectionTitle(speech.scene);
      sectionElement.appendChild(heading);
      fragment.appendChild(sectionElement);
    }

    const speechElement = createSpeechElement(speech);
    speechElements.push(speechElement);
    sectionElement.appendChild(speechElement);
  });

  textContent.replaceChildren(fragment);
  textStatus.hidden = true;
  updateReaderCount(speechElements.length);
}

function updateReaderCount(visibleCount) {
  if (!readerCount) return;
  const label = visibleCount === 1 ? "intervento" : "interventi";
  readerCount.textContent = `${visibleCount} ${label}`;
}

function filterText() {
  const query = normaliseSearchText(textSearch?.value || "");
  let visibleCount = 0;

  speechElements.forEach((speech) => {
    const matches = !query || speech.dataset.search.includes(query);
    speech.hidden = !matches;
    if (matches) visibleCount += 1;
  });

  document.querySelectorAll(".tei-scene").forEach((section) => {
    const hasVisibleSpeech = [...section.querySelectorAll(".tei-speech")].some(
      (speech) => !speech.hidden
    );
    section.hidden = !hasVisibleSpeech;
  });

  if (readerEmpty) readerEmpty.hidden = visibleCount !== 0;
  updateReaderCount(visibleCount);
}

async function loadText() {
  if (textLoaded || textLoading || !workSlug || !textStatus) return;

  textLoading = true;
  textStatus.hidden = false;
  textStatus.classList.remove("is-error");
  textStatus.textContent = "Caricamento del testo greco…";

  try {
    const fallbackSpeeches =
      globalThis.LEXAR_WORK_DATA?.[workSlug]?.speeches;
    let speeches = fallbackSpeeches;

    if (window.location.protocol !== "file:") {
      try {
        const payload = await fetchJson(
          `/api/works/${encodeURIComponent(workSlug)}/speeches`
        );
        if (payload.speeches?.length) {
          speeches = payload.speeches;
        }
      } catch (apiError) {
        if (!fallbackSpeeches?.length) {
          throw apiError;
        }
      }
    }

    if (!speeches?.length) {
      throw new Error("Nessun intervento disponibile");
    }
    renderText(speeches);
    textLoaded = true;
  } catch (error) {
    textStatus.classList.add("is-error");
    textStatus.textContent =
      "Non è stato possibile caricare il testo. Puoi comunque consultare il file XML/TEI tra le risorse dell’opera.";
    console.error("Errore nel caricamento del testo:", error);
  } finally {
    textLoading = false;
  }
}

function setReaderOpen(isOpen) {
  if (!textToggle || !textReader) return;

  textReader.hidden = !isOpen;
  textToggle.setAttribute("aria-expanded", String(isOpen));
  const label = textToggle.querySelector("span");
  if (label) {
    label.textContent = isOpen ? "Chiudi il testo" : "Apri il testo completo";
  }

  if (isOpen) {
    loadText();
  }
}

textToggle?.addEventListener("click", () => {
  setReaderOpen(textToggle.getAttribute("aria-expanded") !== "true");
});

textSearch?.addEventListener("input", filterText);

loadTerms();
