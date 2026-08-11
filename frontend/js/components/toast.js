/**
 * A minimal toast/notification system. Every page gets a `<div
 * id="toast-region">` (added by navbar.js's shared page chrome) that this
 * module renders into — so any page can `import { showToast }` without
 * wiring up its own notification markup.
 */

function ensureRegion() {
  let region = document.getElementById("toast-region");
  if (!region) {
    region = document.createElement("div");
    region.id = "toast-region";
    region.className = "toast-region";
    region.setAttribute("role", "status");
    region.setAttribute("aria-live", "polite");
    document.body.appendChild(region);
  }
  return region;
}

/**
 * @param {string} message
 * @param {"info"|"success"|"error"} variant
 */
export function showToast(message, variant = "info") {
  const region = ensureRegion();
  const toast = document.createElement("div");
  toast.className = `toast toast--${variant}`;
  toast.textContent = message;
  region.appendChild(toast);

  window.setTimeout(() => {
    toast.remove();
  }, 4000);
}
