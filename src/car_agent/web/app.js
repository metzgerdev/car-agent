const transcript = document.querySelector("#transcript");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const resetButton = document.querySelector("#reset-button");
const clearButton = document.querySelector("#clear-button");
const modalitySelect = document.querySelector("#modality-select");
const connectionStatus = document.querySelector("#connection-status");
const stageBadge = document.querySelector("#stage-badge");
const profile = document.querySelector("#profile");
const trace = document.querySelector("#trace");
const traceCount = document.querySelector("#trace-count");
const reviewsList = document.querySelector("#reviews-list");
const reviewCount = document.querySelector("#review-count");
const reviewDialog = document.querySelector("#review-dialog");
const reviewClose = document.querySelector("#review-close");
const reviewDialogOutlet = document.querySelector("#review-dialog-outlet");
const reviewDialogTitle = document.querySelector("#review-dialog-title");
const reviewDialogVehicle = document.querySelector("#review-dialog-vehicle");
const reviewDialogSummary = document.querySelector("#review-dialog-summary");
const reviewDialogLink = document.querySelector("#review-dialog-link");

let conversationId = newConversationId();

function newConversationId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return `ui-${window.crypto.randomUUID()}`;
  }
  return `ui-${Date.now()}`;
}

function appendMessage(role, text, extraClass = "") {
  const message = document.createElement("div");
  message.className = `message ${role === "shopper" ? "shopper-message" : "assistant-message"} ${extraClass}`.trim();
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "shopper" ? "You" : "Advisor";
  const body = document.createElement("p");
  body.textContent = text;
  message.append(label, body);
  transcript.appendChild(message);
  transcript.scrollTop = transcript.scrollHeight;
}

function resetTranscript() {
  transcript.replaceChildren();
  appendMessage("advisor", "What kind of classic or modern-classic sports car are you looking for?");
  updateEvidence({
    stage: "qualifying",
    preferences: {},
    last_vehicle_ids: [],
  }, []);
  renderReviews([]);
}

function displayValue(value, fallback) {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value).replaceAll("_", " ");
}

function updateEvidence(state, calls) {
  const preferences = state.preferences || {};
  stageBadge.textContent = displayValue(state.stage, "qualifying");
  const values = [
    ["Budget", preferences.budget_max ? `$${Number(preferences.budget_max).toLocaleString()} max` : null],
    ["Use", preferences.intended_use],
    ["Style", preferences.driving_style || preferences.body_style],
    ["Vehicle", preferences.selected_vehicle_id || (state.last_vehicle_ids || [])[0]],
  ];
  profile.replaceChildren();
  for (const [label, value] of values) {
    const wrapper = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = displayValue(value, label === "Vehicle" ? "Not selected" : "Not set");
    wrapper.append(term, detail);
    profile.appendChild(wrapper);
  }

  traceCount.textContent = `${calls.length} call${calls.length === 1 ? "" : "s"}`;
  trace.replaceChildren();
  if (!calls.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Tool calls will appear here after the advisor searches inventory or retrieves facts.";
    trace.appendChild(empty);
    return;
  }
  calls.forEach((call, index) => {
    const item = document.createElement("details");
    item.className = "trace-item";
    const summary = document.createElement("summary");
    summary.textContent = `${index + 1}. ${call.name}`;
    const details = document.createElement("pre");
    details.textContent = JSON.stringify({ arguments: call.arguments, result: call.result }, null, 2);
    item.append(summary, details);
    trace.appendChild(item);
  });
}

function renderReviews(groups) {
  const reviewTotal = groups.reduce((total, group) => total + group.reviews.length, 0);
  reviewCount.textContent = `${reviewTotal} review${reviewTotal === 1 ? "" : "s"}`;
  reviewsList.replaceChildren();
  if (!reviewTotal) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Reviews will appear when the advisor finds a vehicle.";
    reviewsList.appendChild(empty);
    return;
  }
  groups.forEach((group) => {
    if (!group.reviews.length) return;
    const section = document.createElement("div");
    section.className = "review-group";
    const vehicle = document.createElement("p");
    vehicle.className = "review-vehicle";
    vehicle.textContent = group.vehicle_name;
    section.appendChild(vehicle);
    group.reviews.forEach((review) => {
      const button = document.createElement("button");
      button.className = "review-button";
      button.type = "button";
      const outlet = document.createElement("span");
      outlet.className = "review-outlet";
      outlet.textContent = review.outlet;
      const title = document.createElement("span");
      title.className = "review-title";
      title.textContent = review.title;
      button.append(outlet, title);
      button.addEventListener("click", () => openReview(group.vehicle_name, review));
      section.appendChild(button);
    });
    reviewsList.appendChild(section);
  });
}

function openReview(vehicleName, review) {
  reviewDialogOutlet.textContent = review.outlet;
  reviewDialogTitle.textContent = review.title;
  reviewDialogVehicle.textContent = vehicleName;
  reviewDialogSummary.textContent = review.summary;
  reviewDialogLink.href = review.url;
  if (typeof reviewDialog.showModal === "function") {
    reviewDialog.showModal();
  } else {
    reviewDialog.setAttribute("open", "");
  }
}

function closeReview() {
  if (typeof reviewDialog.close === "function") reviewDialog.close();
  else reviewDialog.removeAttribute("open");
}

async function loadReviews(state) {
  const preferences = state.preferences || {};
  const ids = [...new Set([
    preferences.selected_vehicle_id,
    ...(state.last_vehicle_ids || []),
  ].filter(Boolean))].slice(0, 3);
  if (!ids.length) {
    renderReviews([]);
    return;
  }
  try {
    const responses = await Promise.all(ids.map(async (vehicleId) => {
      const response = await fetch(`/vehicles/${encodeURIComponent(vehicleId)}/reviews`);
      if (!response.ok) return null;
      return response.json();
    }));
    renderReviews(responses.filter(Boolean));
  } catch (error) {
    renderReviews([]);
  }
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("health check failed");
    connectionStatus.textContent = "API connected";
    connectionStatus.className = "status-pill connected";
  } catch (error) {
    connectionStatus.textContent = "API unavailable";
    connectionStatus.className = "status-pill offline";
  }
}

async function sendMessage(message) {
  const cleaned = message.trim();
  if (!cleaned || sendButton.disabled) return;
  appendMessage("shopper", cleaned);
  input.value = "";
  sendButton.disabled = true;
  sendButton.textContent = "Thinking…";
  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        message: cleaned,
        modality: modalitySelect.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "The advisor could not process that message.");
    appendMessage("advisor", payload.message);
    updateEvidence(payload.state, payload.trace || []);
    await loadReviews(payload.state);
  } catch (error) {
    appendMessage("advisor", error.message || "The advisor is unavailable. Check the API and try again.", "error-message");
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "Send message";
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => sendMessage(button.dataset.prompt));
});

function startNewConversation() {
  conversationId = newConversationId();
  resetTranscript();
  input.focus();
}

resetButton.addEventListener("click", startNewConversation);
clearButton.addEventListener("click", startNewConversation);
reviewClose.addEventListener("click", closeReview);
reviewDialog.addEventListener("click", (event) => {
  if (event.target === reviewDialog) closeReview();
});
checkHealth();
