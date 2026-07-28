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
    if (
      event.key === "Escape" &&
      mainMenu.classList.contains("is-open")
    ) {
      setMenuOpen(false);
      menuToggle.focus();
    }
  });
}
