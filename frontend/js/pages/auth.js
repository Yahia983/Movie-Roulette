/**
 * Login / register page. One page, one form, toggled between two modes —
 * rather than two separate HTML pages — since the fields overlap heavily
 * and a toggle keeps a user who picked the wrong mode from a full
 * navigation round-trip.
 */

import { ApiError } from "../api.js";
import { login, register } from "../auth.js";
import { renderChrome } from "../components/navbar.js";

const els = {};
let mode = "login"; // or "register"

function getNextUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("next") || "/index.html";
}

function applyMode() {
  const isRegister = mode === "register";
  document.getElementById("auth-heading").textContent = isRegister ? "Create your account" : "Log in";
  document.getElementById("auth-subhead").textContent = isRegister
    ? "Takes about ten seconds. No credit card, obviously."
    : "Welcome back — pick up right where you left off.";
  els.usernameField.hidden = !isRegister;
  els.emailField.hidden = !isRegister;
  els.identifierField.hidden = isRegister;
  els.submitBtn.textContent = isRegister ? "Create account" : "Log in";
  document.getElementById("toggle-prompt").textContent = isRegister
    ? "Already have an account?"
    : "Don't have an account?";
  els.toggleModeBtn.textContent = isRegister ? "Log in" : "Sign up";
  clearErrors();
}

function clearErrors() {
  [els.formError, els.usernameError, els.emailError, els.passwordError].forEach((el) => {
    el.hidden = true;
    el.textContent = "";
  });
}

function showFieldError(el, message) {
  el.hidden = false;
  el.textContent = message;
}

async function handleSubmit(event) {
  event.preventDefault();
  clearErrors();
  els.submitBtn.disabled = true;

  try {
    if (mode === "register") {
      const username = els.usernameInput.value.trim();
      const email = els.emailInput.value.trim();
      const password = els.passwordInput.value;

      if (username.length < 3) {
        showFieldError(els.usernameError, "Username must be at least 3 characters.");
        return;
      }
      if (password.length < 8) {
        showFieldError(els.passwordError, "Password must be at least 8 characters.");
        return;
      }

      await register({ email, username, password });
      await login({ identifier: username, password });
    } else {
      const identifier = els.identifierInput.value.trim();
      const password = els.passwordInput.value;
      await login({ identifier, password });
    }

    window.location.href = getNextUrl();
  } catch (err) {
    if (err instanceof ApiError) {
      showFieldError(els.formError, err.message);
    } else {
      showFieldError(els.formError, "Something went wrong. Please try again.");
      console.error(err);
    }
  } finally {
    els.submitBtn.disabled = false;
  }
}

async function init() {
  await renderChrome();

  const params = new URLSearchParams(window.location.search);
  mode = params.get("mode") === "register" ? "register" : "login";

  els.usernameField = document.getElementById("username-field");
  els.usernameInput = document.getElementById("username-input");
  els.usernameError = document.getElementById("username-error");
  els.emailField = document.getElementById("email-field");
  els.emailInput = document.getElementById("email-input");
  els.emailError = document.getElementById("email-error");
  els.identifierField = document.getElementById("identifier-field");
  els.identifierInput = document.getElementById("identifier-input");
  els.passwordInput = document.getElementById("password-input");
  els.passwordError = document.getElementById("password-error");
  els.formError = document.getElementById("form-error");
  els.submitBtn = document.getElementById("submit-btn");
  els.toggleModeBtn = document.getElementById("toggle-mode-btn");

  applyMode();

  els.toggleModeBtn.addEventListener("click", () => {
    mode = mode === "login" ? "register" : "login";
    applyMode();
  });

  document.getElementById("auth-form").addEventListener("submit", handleSubmit);
}

init();
