"use strict";

const state = {
  bootstrap: null,
  csrf: "",
  currentSpace: "today",
  items: [],
  conversationId: null,
  searchTimer: null,
};

const elements = {};

document.addEventListener("DOMContentLoaded", async () => {
  bindElements();
  bindEvents();
  updateClock();
  window.setInterval(updateClock, 1000);
  const coldBoot = window.sessionStorage.getItem("spider-os-booted") !== "1";
  const minimumBoot = wait(coldBoot ? 2200 : 320);
  try {
    await Promise.all([refreshBootstrap(), minimumBoot]);
    const boot = document.getElementById("bootScreen");
    boot.classList.add("boot-exit");
    await wait(coldBoot ? 260 : 80);
    boot.hidden = true;
    document.getElementById("appShell").hidden = false;
    window.sessionStorage.setItem("spider-os-booted", "1");
    renderNavigation();
    populateSpaceSelect();
    await openSpace("today");
  } catch (error) {
    const bootStatus = document.querySelector(".boot-identity span");
    if (bootStatus) bootStatus.textContent = "CORE DID NOT ANSWER · " + error.message;
  }
});

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function bindElements() {
  [
    "spaceNav", "workspace", "pageTitle", "pageEyebrow", "systemDot",
    "systemStatus", "aiStatus", "searchInput", "newItemButton", "itemDialog",
    "itemForm", "itemSpace", "itemKind", "itemSensitivity", "itemTitle",
    "itemBody", "itemDue", "itemPriority", "assistantForm", "assistantInput",
    "assistantFeed", "quickPrompts", "menuButton", "sidebar", "toast",
    "auditDialog", "auditList", "openAudit", "closeAudit", "webEdgeOrb",
  ].forEach((id) => {
    elements[id] = document.getElementById(id);
  });
}

function bindEvents() {
  elements.newItemButton.addEventListener("click", () => openItemDialog());
  elements.itemForm.addEventListener("submit", saveItem);
  elements.assistantForm.addEventListener("submit", sendAssistantMessage);
  elements.quickPrompts.addEventListener("click", (event) => {
    const button = event.target.closest("[data-prompt]");
    if (button) {
      elements.assistantInput.value = button.dataset.prompt;
      sendAssistantMessage(new Event("submit"));
    }
  });
  elements.searchInput.addEventListener("input", () => {
    window.clearTimeout(state.searchTimer);
    state.searchTimer = window.setTimeout(runSearch, 240);
  });
  elements.menuButton.addEventListener("click", () => {
    elements.sidebar.classList.toggle("open");
  });
  elements.openAudit.addEventListener("click", openAuditLog);
  elements.webEdgeOrb.addEventListener("click", () => elements.assistantInput.focus());
  elements.closeAudit.addEventListener("click", () => elements.auditDialog.close());
  elements.assistantInput.addEventListener("input", () => {
    elements.assistantInput.style.height = "auto";
    elements.assistantInput.style.height =
      Math.min(elements.assistantInput.scrollHeight, 130) + "px";
  });
  elements.assistantInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.assistantForm.requestSubmit();
    }
  });
}

async function api(path, options = {}) {
  const settings = {
    method: options.method || "GET",
    headers: {"Accept": "application/json"},
  };
  if (options.body !== undefined) {
    settings.headers["Content-Type"] = "application/json";
    settings.body = JSON.stringify(options.body);
  }
  if (settings.method !== "GET") {
    settings.headers["X-Spider-Token"] = state.csrf;
  }
  const response = await fetch(path, settings);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "Spider OS request failed.");
  }
  return payload;
}

async function refreshBootstrap() {
  state.bootstrap = await api("/api/bootstrap");
  state.csrf = state.bootstrap.csrf_token;
  const ai = state.bootstrap.ai;
  elements.systemDot.classList.toggle("warning", !ai.available);
  const resident = state.bootstrap.resident || {};
  const residentLabel = resident.active ? "Webbie resident · " : "Webbie offline · ";
  elements.aiStatus.textContent = ai.available
    ? residentLabel + ai.model
    : residentLabel + "model offline";
  elements.webEdgeOrb?.classList.toggle("active", Boolean(resident.active));
  elements.webEdgeOrb?.classList.toggle("screen-aware", Boolean(resident.screen_awareness));
  elements.systemStatus.textContent = "Core online";
  renderPendingProposals(state.bootstrap.proposals || []);
}

function renderNavigation() {
  clear(elements.spaceNav);
  const spaces = state.bootstrap.spaces;
  spaces.filter((space) => !space.parent_id).forEach((space) => {
    elements.spaceNav.appendChild(spaceButton(space, false));
    spaces.filter((child) => child.parent_id === space.id).forEach((child) => {
      elements.spaceNav.appendChild(spaceButton(child, true));
    });
  });
}

function spaceButton(space, child) {
  const button = node("button", "space-button" + (child ? " child" : ""));
  button.type = "button";
  button.dataset.spaceId = space.id;
  button.style.setProperty("--space-color", space.color);
  button.appendChild(node("span", "space-dot"));
  button.appendChild(textNode("span", space.name));
  button.addEventListener("click", () => openSpace(space.id));
  return button;
}

function populateSpaceSelect() {
  clear(elements.itemSpace);
  state.bootstrap.spaces
    .filter((space) => space.id !== "today")
    .forEach((space) => {
      const option = document.createElement("option");
      option.value = space.id;
      option.textContent = (space.parent_id ? "↳ " : "") + space.name;
      elements.itemSpace.appendChild(option);
    });
}

async function openSpace(spaceId) {
  state.currentSpace = spaceId;
  const space = findSpace(spaceId) || findSpace("today");
  elements.pageTitle.textContent = space.name;
  elements.pageEyebrow.textContent =
    spaceId === "today" ? "YOUR LIFE, IN VIEW" : "ANCHOR";
  document.querySelectorAll(".space-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.spaceId === spaceId);
  });
  elements.sidebar.classList.remove("open");
  elements.workspace.setAttribute("aria-busy", "true");
  const query = spaceId === "today" ? "" : "?space_id=" + encodeURIComponent(spaceId);
  const payload = await api("/api/items" + query);
  state.items = payload.items;
  if (spaceId === "today") {
    await refreshBootstrap();
    renderDashboard();
  } else {
    renderSpace(space);
  }
  elements.workspace.removeAttribute("aria-busy");
}

function renderDashboard() {
  clear(elements.workspace);
  const summary = state.bootstrap.today;
  const hero = node("section", "hero");
  const heroText = node("div");
  heroText.appendChild(textNode("span", "WHOLE-LIFE COMMAND CENTER", "eyebrow"));
  heroText.appendChild(textNode("h2", getGreeting() + ", Cory."));
  heroText.appendChild(textNode(
    "p",
    summary.open_count
      ? "You have " + summary.open_count + " open threads across your life. We will choose what deserves attention instead of allowing everything to shout at once."
      : "Nothing is demanding your attention yet. Enjoy the statistical anomaly or add the first thread."
  ));
  hero.appendChild(heroText);
  const add = textNode("button", "Add a thread", "hero-action");
  add.type = "button";
  add.addEventListener("click", () => openItemDialog());
  hero.appendChild(add);
  elements.workspace.appendChild(hero);

  const metrics = node("section", "metrics");
  [
    ["Open threads", summary.open_count, "Across every anchor"],
    ["Active focus", summary.active_count, "In motion now"],
    ["Scheduled", summary.scheduled_count, "With a due date"],
    ["Approvals", summary.pending_approval_count, "Waiting on you"],
  ].forEach(([label, value, detail]) => {
    const card = node("article", "metric");
    card.appendChild(textNode("span", label));
    card.appendChild(textNode("strong", String(value)));
    card.appendChild(textNode("small", detail));
    metrics.appendChild(card);
  });
  elements.workspace.appendChild(metrics);

  const columns = node("section", "dashboard-columns");
  columns.appendChild(itemsPanel(
    "Current focus",
    "The next useful moves",
    summary.focus || [],
  ));
  const lifePanel = node("article", "panel");
  lifePanel.appendChild(panelHeading("Your anchors", "Open a thread"));
  const grid = node("div", "space-grid");
  state.bootstrap.spaces
    .filter((space) => !space.parent_id && !["today"].includes(space.id))
    .slice(0, 8)
    .forEach((space) => {
      const card = node("button", "space-card");
      card.type = "button";
      card.style.setProperty("--space-color", space.color);
      card.appendChild(node("span", "space-dot"));
      card.appendChild(textNode("strong", space.name));
      const count = state.items.filter((item) => item.space_id === space.id).length;
      card.appendChild(textNode("span", count + " direct thread" + (count === 1 ? "" : "s")));
      card.addEventListener("click", () => openSpace(space.id));
      grid.appendChild(card);
    });
  lifePanel.appendChild(grid);
  columns.appendChild(lifePanel);
  elements.workspace.appendChild(columns);

  const findings = state.bootstrap.research?.findings || [];
  const alerts = [
    ...(state.bootstrap.proactive?.important || []),
    ...(state.bootstrap.proactive?.worth_knowing || []),
  ];
  if (findings.length || alerts.length) {
    const intelligence = node("section", "panel webbie-findings");
    intelligence.appendChild(panelHeading("Webbie found something", "Research + proactive awareness"));
    const list = node("div", "finding-list");
    findings.slice(0, 4).forEach((finding) => {
      const card = node("article", "finding-card " + finding.urgency);
      card.appendChild(textNode("span", finding.urgency.replaceAll("-", " ").toUpperCase(), "eyebrow"));
      card.appendChild(textNode("strong", finding.title));
      card.appendChild(textNode("p", finding.summary));
      card.appendChild(textNode("small", Math.round(Number(finding.confidence || 0) * 100) + "% confidence · sourced research"));
      list.appendChild(card);
    });
    alerts.slice(0, 3).forEach((alert) => {
      const card = node("article", "finding-card alert " + alert.urgency);
      card.appendChild(textNode("span", "WEBBIE NOTICE", "eyebrow"));
      card.appendChild(textNode("strong", alert.title));
      if (alert.body) card.appendChild(textNode("p", alert.body));
      list.appendChild(card);
    });
    intelligence.appendChild(list);
    elements.workspace.appendChild(intelligence);
  }
}

function renderSpace(space) {
  clear(elements.workspace);
  const children = state.bootstrap.spaces.filter((item) => item.parent_id === space.id);
  const openItems = state.items.filter((item) => !["done", "archived"].includes(item.status));
  const projects = state.items.filter((item) => item.kind === "project");

  const header = node("section", "space-header");
  const heading = node("div");
  const eyebrow = textNode("span", space.parent_id ? "CONNECTED ANCHOR" : "ANCHOR", "eyebrow");
  eyebrow.style.color = space.color;
  heading.appendChild(eyebrow);
  heading.appendChild(textNode("h2", space.name));
  heading.appendChild(textNode("p", space.description));
  header.appendChild(heading);
  const stats = node("div", "space-stats");
  stats.appendChild(spaceStat(openItems.length, "Open"));
  stats.appendChild(spaceStat(projects.length, "Projects"));
  header.appendChild(stats);
  elements.workspace.appendChild(header);

  const content = node("section", "space-content");
  content.appendChild(itemsPanel("Threads", "Tasks, notes, events, and projects", state.items, space.id));
  const side = node("div");
  const actionPanel = node("article", "panel");
  actionPanel.appendChild(panelHeading("Actions", "This anchor"));
  const actions = node("div", "child-spaces");
  const add = node("button", "child-space-button");
  add.type = "button";
  add.appendChild(node("span", "space-dot"));
  const addText = node("div");
  addText.appendChild(textNode("strong", "Add a thread"));
  addText.appendChild(textNode("span", "Task, note, project, event, or check-in"));
  add.appendChild(addText);
  add.addEventListener("click", () => openItemDialog(space.id));
  actions.appendChild(add);
  actionPanel.appendChild(actions);
  side.appendChild(actionPanel);

  if (children.length) {
    const childPanel = node("article", "panel");
    childPanel.style.marginTop = "14px";
    childPanel.appendChild(panelHeading("Connected anchors", children.length + " areas"));
    const childList = node("div", "child-spaces");
    children.forEach((child) => {
      const button = node("button", "child-space-button");
      button.type = "button";
      const dot = node("span", "space-dot");
      dot.style.setProperty("--space-color", child.color);
      button.appendChild(dot);
      const label = node("div");
      label.appendChild(textNode("strong", child.name));
      label.appendChild(textNode("span", child.description));
      button.appendChild(label);
      button.addEventListener("click", () => openSpace(child.id));
      childList.appendChild(button);
    });
    childPanel.appendChild(childList);
    side.appendChild(childPanel);
  }
  content.appendChild(side);
  elements.workspace.appendChild(content);
}

function itemsPanel(title, subtitle, items, defaultSpace) {
  const panel = node("article", "panel");
  panel.appendChild(panelHeading(title, subtitle));
  const list = node("div", "item-list");
  if (!items.length) {
    const empty = node("div", "empty-state");
    empty.appendChild(textNode("strong", "No threads here yet"));
    empty.appendChild(textNode("span", "A clean page. Suspicious, but useful."));
    list.appendChild(empty);
  } else {
    items.slice(0, 30).forEach((item) => list.appendChild(itemRow(item)));
  }
  panel.appendChild(list);
  if (defaultSpace && !items.length) {
    panel.addEventListener("dblclick", () => openItemDialog(defaultSpace));
  }
  return panel;
}

function itemRow(item) {
  const row = node("div", "item-row" + (item.status === "done" ? " done" : ""));
  const complete = node("button", "complete-button");
  complete.type = "button";
  complete.title = item.status === "done" ? "Reopen" : "Mark complete";
  complete.addEventListener("click", async () => {
    await api("/api/items/" + item.id + "/status", {
      method: "POST",
      body: {status: item.status === "done" ? "open" : "done"},
    });
    toast(item.status === "done" ? "Thread reopened" : "Thread completed");
    await openSpace(state.currentSpace);
  });
  row.appendChild(complete);
  const content = node("div");
  content.appendChild(textNode("span", item.title, "item-title"));
  const meta = node("div", "item-meta");
  meta.appendChild(textNode("span", item.kind, "item-kind"));
  const space = findSpace(item.space_id);
  if (space) meta.appendChild(textNode("span", space.name));
  if (item.due_at) meta.appendChild(textNode("span", formatDate(item.due_at)));
  if (item.sensitivity !== "standard") meta.appendChild(textNode("span", item.sensitivity));
  content.appendChild(meta);
  row.appendChild(content);
  row.appendChild(node("span", "priority-mark" + (item.priority >= 3 ? " high" : "")));
  return row;
}

async function saveItem(event) {
  event.preventDefault();
  const due = elements.itemDue.value
    ? new Date(elements.itemDue.value).toISOString()
    : null;
  await api("/api/items", {
    method: "POST",
    body: {
      space_id: elements.itemSpace.value,
      kind: elements.itemKind.value,
      title: elements.itemTitle.value,
      body: elements.itemBody.value,
      due_at: due,
      priority: Number(elements.itemPriority.value),
      sensitivity: elements.itemSensitivity.value,
    },
  });
  elements.itemDialog.close();
  elements.itemForm.reset();
  toast("Thread added");
  await openSpace(state.currentSpace);
}

function openItemDialog(spaceId) {
  const fallback = state.currentSpace !== "today" ? state.currentSpace : "personal";
  elements.itemSpace.value = spaceId || fallback;
  elements.itemDialog.showModal();
  window.setTimeout(() => elements.itemTitle.focus(), 50);
}

async function sendAssistantMessage(event) {
  event.preventDefault();
  const message = elements.assistantInput.value.trim();
  if (!message) return;
  elements.assistantInput.value = "";
  elements.assistantInput.style.height = "auto";
  addChatMessage("user", message);
  const waiting = addChatMessage("assistant", "Thinking across the threads…", true);
  try {
    const result = await api("/api/chat", {
      method: "POST",
      body: {message, conversation_id: state.conversationId},
    });
    state.conversationId = result.conversation_id;
    waiting.querySelector("p").textContent = result.message;
    waiting.classList.remove("waiting");
    (result.proposals || []).forEach((proposal) => {
      elements.assistantFeed.appendChild(proposalCard(proposal));
    });
    elements.assistantFeed.scrollTop = elements.assistantFeed.scrollHeight;
  } catch (error) {
    waiting.querySelector("p").textContent = error.message;
    waiting.classList.remove("waiting");
  }
}

function addChatMessage(role, message, waiting) {
  const card = node("article", role === "user" ? "user-message" : "assistant-message");
  if (waiting) card.classList.add("waiting");
  card.appendChild(textNode("span", role === "user" ? "YOU" : "WEBBIE", "message-label"));
  card.appendChild(textNode("p", message));
  elements.assistantFeed.appendChild(card);
  elements.assistantFeed.scrollTop = elements.assistantFeed.scrollHeight;
  return card;
}

function renderPendingProposals(proposals) {
  document.querySelectorAll(".proposal-card[data-pending-bootstrap]").forEach((card) => card.remove());
  proposals.forEach((proposal) => {
    const card = proposalCard(proposal);
    card.dataset.pendingBootstrap = "true";
    elements.assistantFeed.appendChild(card);
  });
}

function proposalCard(proposal) {
  const card = node("article", "proposal-card");
  card.dataset.proposalId = proposal.id;
  card.appendChild(textNode("span", "APPROVAL REQUIRED"));
  const title = proposal.arguments.title || proposal.action_name.replaceAll("_", " ");
  card.appendChild(textNode("strong", title));
  card.appendChild(textNode(
    "p",
    proposal.rationale || "Web wants to make this change."
  ));
  const actions = node("div", "proposal-actions");
  const approve = textNode("button", "Approve");
  approve.type = "button";
  approve.addEventListener("click", () => decideProposal(proposal.id, "approve", card));
  const reject = textNode("button", "Reject");
  reject.type = "button";
  reject.addEventListener("click", () => decideProposal(proposal.id, "reject", card));
  actions.append(approve, reject);
  card.appendChild(actions);
  return card;
}

async function decideProposal(id, decision, card) {
  await api("/api/proposals/" + id + "/" + decision, {method: "POST", body: {}});
  card.remove();
  toast(decision === "approve" ? "Approved and applied" : "Proposal rejected");
  await openSpace(state.currentSpace);
}

async function runSearch() {
  const query = elements.searchInput.value.trim();
  if (!query) {
    await openSpace(state.currentSpace);
    return;
  }
  const payload = await api("/api/search?q=" + encodeURIComponent(query));
  elements.pageEyebrow.textContent = "SEARCH";
  elements.pageTitle.textContent = "Results";
  clear(elements.workspace);
  const header = node("section", "space-header");
  const heading = node("div");
  heading.appendChild(textNode("span", "EVERY THREAD", "eyebrow"));
  heading.appendChild(textNode("h2", "“" + query + "”"));
  heading.appendChild(textNode("p", payload.items.length + " matching thread" + (payload.items.length === 1 ? "" : "s") + "."));
  header.appendChild(heading);
  elements.workspace.appendChild(header);
  elements.workspace.appendChild(itemsPanel("Search results", "Across all anchors", payload.items));
}

async function openAuditLog() {
  const payload = await api("/api/audit");
  clear(elements.auditList);
  if (!payload.entries.length) {
    elements.auditList.appendChild(textNode("p", "No actions recorded yet.", "empty-state"));
  } else {
    payload.entries.forEach((entry) => {
      const row = node("div", "audit-row");
      row.appendChild(textNode("span", formatDate(entry.created_at)));
      row.appendChild(textNode("strong", entry.action));
      row.appendChild(textNode("span", entry.actor));
      elements.auditList.appendChild(row);
    });
  }
  elements.auditDialog.showModal();
}

function panelHeading(title, detail) {
  const heading = node("div", "panel-heading");
  heading.appendChild(textNode("h3", title));
  heading.appendChild(textNode("span", detail));
  return heading;
}

function spaceStat(value, label) {
  const stat = node("div", "space-stat");
  stat.appendChild(textNode("strong", String(value)));
  stat.appendChild(textNode("span", label));
  return stat;
}

function findSpace(id) {
  return state.bootstrap.spaces.find((space) => space.id === id);
}

function updateClock() {
  const now = new Date();
  document.getElementById("clockTime").textContent = now.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
  document.getElementById("clockDate").textContent = now.toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function node(tag, className) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  return element;
}

function textNode(tag, text, className) {
  const element = node(tag, className);
  element.textContent = text;
  return element;
}

function clear(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

let toastTimer;
function toast(message) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  toastTimer = window.setTimeout(() => elements.toast.classList.remove("visible"), 2200);
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

