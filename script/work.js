const workPage = document.querySelector(".work-page");
const workSlug = workPage?.dataset.work;
const menuToggle = document.querySelector(".menu-toggle");
const menuLinks = document.querySelector(".work-nav-links");

const termList = document.getElementById("term-list");
const termStatus = document.getElementById("term-status");
const textToggle = document.getElementById("text-toggle");
const textReader = document.getElementById("text-reader");
const textStatus = document.getElementById("text-status");
const textContent = document.getElementById("tei-content");
const textSearch = document.getElementById("text-search");
const readerCount = document.getElementById("reader-count");
const readerDataSource = document.getElementById("reader-data-source");
const readerEmpty = document.getElementById("reader-empty");
const verseJump = document.getElementById("verse-jump");
const verseNumber = document.getElementById("verse-number");
const readerJumpStatus = document.getElementById("reader-jump-status");
const metricToggle = document.getElementById("metric-toggle");

const lexiconProfiles = {
  acarnesi: {
    workFilter: "Acarnesi",
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
let lineElements = [];
let highlightedLine = null;
let highlightTimer = null;
let metricsVisible = false;
const verseIndex = new Map();

function setMobileMenuOpen(isOpen) {
  if (!menuToggle || !menuLinks) return;

  menuLinks.classList.toggle("is-open", isOpen);
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  menuToggle.setAttribute("aria-label", isOpen ? "Chiudi il menu" : "Apri il menu");
}

menuToggle?.addEventListener("click", () => {
  setMobileMenuOpen(menuToggle.getAttribute("aria-expanded") !== "true");
});

menuLinks?.addEventListener("click", (event) => {
  if (event.target.closest("a")) setMobileMenuOpen(false);
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || menuToggle?.getAttribute("aria-expanded") !== "true") {
    return;
  }
  setMobileMenuOpen(false);
  menuToggle.focus();
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 760) setMobileMenuOpen(false);
});

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

    const workFilter = lexiconProfiles[workSlug]?.workFilter;
    if (item.hasEntry !== false && workFilter) {
      const link = document.createElement("a");
      const parameters = new URLSearchParams({
        from: workSlug,
        term: item.term,
      });
      link.className = "term-entry-link";
      link.href = `../lessico/vocaboli.html?${parameters}`;
      link.setAttribute(
        "aria-label",
        `${item.term}, ${item.frequency} occorrenze: apri la voce lessicale`
      );
      link.append(word, frequency);
      listItem.appendChild(link);
    } else {
      listItem.classList.add("is-unavailable");
      const unavailable = document.createElement("span");
      unavailable.className = "visually-hidden";
      unavailable.textContent = " Voce lessicale in preparazione.";
      listItem.append(word, frequency, unavailable);
    }
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

function normaliseLine(line) {
  if (typeof line === "string") {
    return {
      id: "",
      n: "",
      part: "",
      refs: [],
      verses: [],
      gap: false,
      metric: null,
      text: line,
    };
  }

  const verses = Array.isArray(line?.verses)
    ? line.verses.map(Number).filter(Number.isInteger)
    : [];
  return {
    id: line?.id || "",
    n: line?.n || "",
    part: line?.part || "",
    refs: Array.isArray(line?.refs) ? line.refs : [],
    verses,
    gap: Boolean(line?.gap),
    metric: normaliseMetric(line?.metric),
    text: line?.text || "",
  };
}

function normaliseMetric(metric) {
  if (!metric || typeof metric !== "object") return null;

  const normalised = {
    meter: typeof metric.meter === "string" ? metric.meter.trim() : "",
    label: typeof metric.label === "string" ? metric.label.trim() : "",
    met: typeof metric.met === "string" ? metric.met.trim() : "",
    real: typeof metric.real === "string" ? metric.real.trim() : "",
    status: typeof metric.status === "string" ? metric.status.trim() : "",
    cert: typeof metric.cert === "string" ? metric.cert.trim() : "",
    resp: typeof metric.resp === "string" ? metric.resp.trim() : "",
    sources: Array.isArray(metric.sources) ? metric.sources.filter(Boolean) : [],
  };

  return normalised.label ||
    normalised.meter ||
    normalised.met ||
    normalised.real ||
    normalised.status
    ? normalised
    : null;
}

function metricTitle(metric) {
  if (metric.label) return metric.label;

  const meter = metric.meter.toLocaleLowerCase("it");
  const labels = {
    "3ia": "Trimetro giambico",
    "ia3": "Trimetro giambico",
    "iambic-trimeter": "Trimetro giambico",
    "iambic trimeter": "Trimetro giambico",
    "ia1-hypercat": "Monometro giambico ipercatalettico",
    "iambic-monometer-hypercatalectic":
      "Monometro giambico ipercatalettico",
  };

  return labels[meter] || metric.meter || "Schema metrico";
}

function metricStatusLabel(metric) {
  const status = metric.status.toLocaleLowerCase("it");
  if (["verified", "reviewed", "verificata", "verificato"].includes(status)) {
    return "verificata";
  }
  if (["unscannable", "non scansionabile"].includes(status)) {
    return "non scansionabile";
  }
  if (status === "proposed" && metric.cert.toLocaleLowerCase("it") === "low") {
    return "da verificare";
  }
  if (
    [
      "uncertain",
      "review-needed",
      "to-review",
      "da verificare",
    ].includes(status)
  ) {
    return "da verificare";
  }
  return "proposta";
}

function metricVisibleLabel(metric) {
  const status = metricStatusLabel(metric);
  const meter = metric.meter.toLocaleLowerCase("it");
  const standardMeters = new Set([
    "3ia",
    "ia3",
    "iambic-trimeter",
    "iambic trimeter",
  ]);

  if (status === "da verificare") {
    return standardMeters.has(meter)
      ? status
      : `${metricTitle(metric)} · ${status}`;
  }
  if (status === "non scansionabile") return status;
  return standardMeters.has(meter)
    ? status
    : `${metricTitle(metric)} · ${status}`;
}

function metricAccessibleNotation(value) {
  const spokenTokens = {
    "||": ", cesura, ",
    "|": ", fine di piede, ",
    "-": " lunga ",
    u: " breve ",
    x: " anceps ",
  };

  return (value.match(/\|\||\||-|u|x|[^|\-ux]+/g) || [])
    .map((token) => spokenTokens[token] || token)
    .join("")
    .replace(/\s+/g, " ")
    .replace(/\s+,/g, ",")
    .replace(/,\s*$/, "")
    .trim();
}

function createMetricNotation(value) {
  const notation = document.createElement("span");
  notation.className = "tei-metric-notation";
  notation.setAttribute("aria-hidden", "true");

  const tokens = value.match(/\|\||\||-|u|x|[^|\-ux]+/g) || [];
  const symbols = {
    "-": ["–", "is-long"],
    u: ["⏑", "is-short"],
    x: ["×", "is-anceps"],
    "|": ["│", "is-foot-boundary"],
    "||": ["‖", "is-caesura"],
  };

  tokens.forEach((token) => {
    const symbol = symbols[token];
    if (!symbol) {
      notation.append(document.createTextNode(token));
      return;
    }
    const element = document.createElement("span");
    element.className = `tei-metric-symbol ${symbol[1]}`;
    element.textContent = symbol[0];
    notation.appendChild(element);
  });

  return notation;
}

function createMetricElement(metric) {
  const metricElement = document.createElement("span");
  metricElement.className = "tei-line-metric";
  metricElement.lang = "it";
  metricElement.setAttribute("role", "note");

  const title = metricTitle(metric);
  const status = metricStatusLabel(metric);
  const visibleLabel = metricVisibleLabel(metric);
  if (visibleLabel) {
    const label = document.createElement("span");
    label.className = "tei-metric-label";
    label.setAttribute("aria-hidden", "true");
    label.textContent = visibleLabel;
    metricElement.appendChild(label);
  }

  if (metric.real) {
    metricElement.dataset.real = metric.real.replace(/\s+/g, "");
    metricElement.appendChild(createMetricNotation(metric.real));
  } else if (metric.met) {
    metricElement.appendChild(createMetricNotation(metric.met));
  }

  const accessible = document.createElement("span");
  accessible.className = "visually-hidden tei-metric-description";
  const accessibleStatus = `, ${status}`;
  if (metric.real) {
    accessible.textContent = `Scansione metrica: ${title}${accessibleStatus}. ${metricAccessibleNotation(metric.real)}.`;
  } else if (metric.met) {
    const reviewNote = status === "da verificare"
      ? "; scansione da verificare"
      : "";
    accessible.textContent = `Schema metrico di riferimento: ${title}${reviewNote}. ${metricAccessibleNotation(metric.met)}.`;
  } else {
    accessible.textContent = `Indicazione metrica: ${title}${accessibleStatus}.`;
  }
  metricElement.appendChild(accessible);

  return metricElement;
}

function lineReferenceLabel(line) {
  if (line.refs.length) return line.refs.join(" · ");
  if (line.n) return line.n;
  return "";
}

function indexLineByVerse(lineElement, line) {
  line.verses.forEach((verse) => {
    if (!verseIndex.has(verse)) verseIndex.set(verse, []);
    verseIndex.get(verse).push(lineElement);
  });
}

function markSharedVerseFragments() {
  const groups = new Map();
  const offsetNames = ["start", "quarter", "half", "three-quarter", "full"];

  lineElements.forEach((lineElement) => {
    const verse = lineElement.dataset.verse;
    if (!verse || !lineElement.dataset.part) return;
    if (!groups.has(verse)) groups.set(verse, []);
    groups.get(verse).push(lineElement);
  });

  groups.forEach((fragments) => {
    const speeches = new Set(
      fragments.map((fragment) => fragment.closest(".tei-speech"))
    );
    if (speeches.size < 2) return;

    fragments.forEach((fragment, index) => {
      const progress = index / (fragments.length - 1);
      const offsetIndex = Math.round(progress * (offsetNames.length - 1));
      fragment.classList.add("is-shared-verse");
      fragment.dataset.sharedOffset = offsetNames[offsetIndex];

      const metricElement = fragment.querySelector(".tei-line-metric");
      if (!metricElement) return;
      metricElement.classList.add(
        index === 0 ? "is-shared-start" : "is-shared-continuation"
      );
      if (index > 0) {
        let label = metricElement.querySelector(".tei-metric-label");
        const retainsDoubt = label?.textContent.includes("da verificare");
        if (!label) {
          label = document.createElement("span");
          label.className = "tei-metric-label";
          label.setAttribute("aria-hidden", "true");
          metricElement.prepend(label);
        }
        label.textContent = retainsDoubt
          ? "continua · da verificare"
          : "continua";
        const description = metricElement.querySelector(
          ".tei-metric-description"
        );
        if (description) {
          description.textContent = `Continuazione del verso condiviso. ${description.textContent}`;
        }
      }
    });
  });
}

function setMetricsVisible(isVisible) {
  const hasMetrics = lineElements.some((line) => line.dataset.hasMetric);
  metricsVisible = Boolean(isVisible && hasMetrics);
  textContent?.classList.toggle("has-visible-metrics", metricsVisible);
  metricToggle?.setAttribute("aria-pressed", String(metricsVisible));
  metricToggle?.setAttribute(
    "aria-label",
    metricsVisible ? "Nascondi metrica" : "Mostra metrica"
  );
}

function updateMetricToggleAvailability() {
  if (!metricToggle) return;
  const hasMetrics = lineElements.some((line) => line.dataset.hasMetric);
  metricToggle.hidden = !hasMetrics;
  metricToggle.disabled = !hasMetrics;
  setMetricsVisible(metricsVisible);
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
  speaker.lang = "it";
  speaker.textContent = speech.speaker || "Voce non indicata";

  const lines = document.createElement("div");
  lines.className = "tei-lines";

  const normalisedLines = speech.lines.map(normaliseLine);
  normalisedLines.forEach((lineData) => {
    const lineElement = document.createElement("p");
    lineElement.className = "tei-line";
    lineElement.tabIndex = -1;
    if (lineData.id) lineElement.id = lineData.id;
    if (lineData.n) lineElement.dataset.verse = lineData.n;
    if (lineData.part) lineElement.dataset.part = lineData.part;
    if (lineData.verses.length) {
      lineElement.dataset.verses = lineData.verses.join(" ");
    }

    const referenceLabel = lineReferenceLabel(lineData);
    const number = document.createElement("span");
    number.className = "tei-line-number";
    number.setAttribute("aria-hidden", "true");
    number.textContent = referenceLabel;

    const accessibleReference = document.createElement("span");
    accessibleReference.className = "visually-hidden";
    accessibleReference.lang = "it";
    accessibleReference.textContent = referenceLabel
      ? `Riferimento ${referenceLabel}. `
      : "";

    const body = document.createElement("span");
    body.className = "tei-line-body";

    const text = document.createElement("span");
    text.className = "tei-line-text";
    if (lineData.gap) {
      lineElement.classList.add("is-gap");
      text.lang = "it";
      text.textContent = "Lacuna nel testo";
    } else {
      text.textContent = lineData.text;
    }

    body.appendChild(text);
    if (lineData.metric) {
      lineElement.dataset.hasMetric = "true";
      body.appendChild(createMetricElement(lineData.metric));
    }

    lineElement.append(number, accessibleReference, body);
    lineElements.push(lineElement);
    indexLineByVerse(lineElement, lineData);
    lines.appendChild(lineElement);
  });

  article.dataset.search = normaliseSearchText(
    `${speech.speaker || ""} ${normalisedLines
      .map((line) => line.text)
      .join(" ")}`
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
  lineElements = [];
  verseIndex.clear();

  speeches.forEach((speech) => {
    const sectionKey = speech.section_id || speech.scene;
    if (!sectionElement || sectionKey !== currentSectionKey) {
      currentSectionKey = sectionKey;
      sectionElement = document.createElement("section");
      sectionElement.className = "tei-scene";
      if (speech.section_id) sectionElement.id = speech.section_id;

      const heading = document.createElement("h3");
      heading.className = "scene-heading";
      heading.lang = "it";
      heading.textContent = sectionTitle(speech.scene);
      sectionElement.appendChild(heading);
      fragment.appendChild(sectionElement);
    }

    const speechElement = createSpeechElement(speech);
    speechElements.push(speechElement);
    sectionElement.appendChild(speechElement);
  });

  textContent.replaceChildren(fragment);
  markSharedVerseFragments();
  updateMetricToggleAvailability();
  textStatus.hidden = true;
  updateReaderCount(speechElements.length);
  navigateToCurrentHash();
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

function revealLine(lineElement) {
  const speech = lineElement.closest(".tei-speech");
  const section = lineElement.closest(".tei-scene");
  if (speech?.hidden || section?.hidden) {
    if (textSearch) textSearch.value = "";
    filterText();
  }
}

function setJumpStatus(message, isError = false) {
  if (!readerJumpStatus) return;
  readerJumpStatus.textContent = message;
  readerJumpStatus.classList.toggle("is-error", isError);
}

function highlightAndFocus(lineElement) {
  if (highlightTimer) window.clearTimeout(highlightTimer);
  highlightedLine?.classList.remove("is-target");
  highlightedLine = lineElement;
  lineElement.classList.add("is-target");
  lineElement.scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth",
    block: "center",
  });
  lineElement.focus({ preventScroll: true });
  highlightTimer = window.setTimeout(() => {
    lineElement.classList.remove("is-target");
    if (highlightedLine === lineElement) highlightedLine = null;
  }, 2600);
}

function updateReaderHash(identifier) {
  if (!identifier) return;
  const hash = `#${encodeURIComponent(identifier)}`;
  if (window.location.hash === hash) return;
  try {
    window.history.pushState(null, "", hash);
  } catch {
    window.location.hash = hash;
  }
}

function candidateForVerse(verse) {
  const candidates = verseIndex.get(verse) || [];
  if (!candidates.length) return null;
  return (
    candidates.find((line) => line.dataset.verse === String(verse)) ||
    candidates[0]
  );
}

function neighbouringVerseMessage(verse) {
  const available = [...verseIndex.keys()].sort((a, b) => a - b);
  const lower = available.filter((value) => value < verse).at(-1);
  const upper = available.find((value) => value > verse);
  if (lower && upper) return ` I riferimenti più vicini sono ${lower} e ${upper}.`;
  if (lower) return ` Il riferimento più vicino è ${lower}.`;
  if (upper) return ` Il riferimento più vicino è ${upper}.`;
  return "";
}

function jumpToVerse(verse, { updateHash = true } = {}) {
  const lineElement = candidateForVerse(verse);
  if (!lineElement) {
    setJumpStatus(
      `Il v. ${verse} non ha una coordinata autonoma nel testo di riscontro.` +
        neighbouringVerseMessage(verse),
      true
    );
    return false;
  }

  revealLine(lineElement);
  highlightAndFocus(lineElement);
  if (updateHash) updateReaderHash(lineElement.id);

  const references = lineElement.dataset.verses
    ?.split(" ")
    .map(Number)
    .filter(Number.isInteger);
  const isGap = lineElement.classList.contains("is-gap");
  const fragmentCount = verseIndex.get(verse)?.length || 0;
  if (isGap) {
    setJumpStatus(`Il v. ${verse} è conservato come lacuna.`);
  } else if (fragmentCount > 1) {
    setJumpStatus(
      `Raggiunto il v. ${verse}, articolato in ${fragmentCount} frammenti.`
    );
  } else if (references?.length > 1) {
    setJumpStatus(
      `Raggiunto il v. ${verse}; il frammento attraversa anche ${references
        .filter((value) => value !== verse)
        .join(", ")}.`
    );
  } else {
    setJumpStatus(`Raggiunto il v. ${verse}.`);
  }
  return true;
}

function navigateToCurrentHash() {
  if (!textLoaded && !lineElements.length) return;
  const identifier = decodeURIComponent(window.location.hash.slice(1));
  if (!identifier) return;
  const target = document.getElementById(identifier);
  if (!target || !textContent?.contains(target)) return;

  if (target.classList.contains("tei-line")) {
    revealLine(target);
    highlightAndFocus(target);
    const verse = Number(target.dataset.verses?.split(" ")[0]);
    if (Number.isInteger(verse)) {
      setJumpStatus(
        target.classList.contains("is-gap")
          ? `Il v. ${verse} è conservato come lacuna.`
          : `Raggiunto il v. ${verse}.`
      );
    }
    return;
  }

  target.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
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
    let dataSource = "fallback statico";
    const requestedSource = new URLSearchParams(window.location.search).get(
      "reader-source"
    );
    const useStaticFallback = requestedSource === "fallback";

    if (window.location.protocol !== "file:" && !useStaticFallback) {
      try {
        const payload = await fetchJson(
          `/api/works/${encodeURIComponent(workSlug)}/speeches`
        );
        if (payload.speeches?.length) {
          const apiHasCoordinates = payload.speeches.some((speech) =>
            speech.lines?.some((line) => typeof line === "object" && line.id)
          );
          const fallbackHasCoordinates = fallbackSpeeches?.some((speech) =>
            speech.lines?.some((line) => typeof line === "object" && line.id)
          );
          const apiHasMetrics = payload.speeches.some((speech) =>
            speech.lines?.some(
              (line) => typeof line === "object" && line.metric
            )
          );
          const fallbackHasMetrics = fallbackSpeeches?.some((speech) =>
            speech.lines?.some(
              (line) => typeof line === "object" && line.metric
            )
          );
          const fallbackIsRicher =
            (fallbackHasCoordinates && !apiHasCoordinates) ||
            (fallbackHasMetrics && !apiHasMetrics);
          if (!fallbackIsRicher) {
            speeches = payload.speeches;
            dataSource = "API";
          }
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
    if (readerDataSource) {
      readerDataSource.textContent = `Fonte dati: ${dataSource}.`;
    }
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

verseJump?.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = Number(verseNumber?.value);
  if (!Number.isInteger(value) || value < 1 || value > 1234) {
    setJumpStatus("Inserisci un numero di verso compreso tra 1 e 1234.", true);
    verseNumber?.focus();
    return;
  }
  jumpToVerse(value);
});

metricToggle?.addEventListener("click", () => {
  setMetricsVisible(metricToggle.getAttribute("aria-pressed") !== "true");
});

window.addEventListener("hashchange", () => {
  const identifier = decodeURIComponent(window.location.hash.slice(1));
  if (!/^(ach-(?:frag|gap|sp)-)/.test(identifier)) return;
  setReaderOpen(true);
  if (textLoaded) navigateToCurrentHash();
});

loadTerms();

if (/^#ach-(?:frag|gap|sp)-/.test(window.location.hash)) {
  setReaderOpen(true);
}
