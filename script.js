const menu = document.getElementById("menu");
const button = document.getElementById("menuBtn");
const icon = document.getElementById("menuIcon");
const label = document.getElementById("menuLabel");

function setMenuOpen(open) {
  menu.classList.toggle("open", open);
  menu.inert = !open;
  menu.setAttribute("aria-hidden", String(!open));
  button.setAttribute("aria-expanded", String(open));
  icon.textContent = open ? "✕" : "☰";
  label.textContent = open ? "CLOSE" : "MENU";
  document.body.classList.toggle("menu-open", open);
  if (!open) button.focus();
}

button.addEventListener("click", () => {
  setMenuOpen(button.getAttribute("aria-expanded") !== "true");
});
menu.querySelectorAll("a").forEach(link => {
  link.addEventListener("click", () => setMenuOpen(false));
});
menu.addEventListener("click", event => {
  if (event.target === menu) setMenuOpen(false);
});
document.addEventListener("keydown", event => {
  if (button.getAttribute("aria-expanded") !== "true") return;
  if (event.key === "Escape") setMenuOpen(false);
  if (event.key !== "Tab") return;
  const focusable = [button, ...menu.querySelectorAll("a[href]")]
    .filter(element => element.getClientRects().length > 0);
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
});
