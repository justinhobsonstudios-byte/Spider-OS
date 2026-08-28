"use strict";

(() => {
  let token = "";
  let platform = null;
  const modeLabels = {
    "default": "The Web",
    "studio": "Studio",
    "security-lab": "Kali Bay",
  };

  document.addEventListener("DOMContentLoaded", () => {
    initialize().catch((error) => renderFailure(error));
  });

  async function initialize() {
    const bootstrap = await request("/api/bootstrap");
    token = bootstrap.csrf_token || "";
    platform = bootstrap.platform || (await request("/api/platform")).platform;
    renderStrip();
  }

  async function request(path, options = {}) {
    const settings = {
      method: options.method || "GET",
      headers: {"Accept": "application/json"},
    };
    if (options.body !== undefined) {
      settings.headers["Content-Type"] = "application/json";
      settings.body = JSON.stringify(options.body);
    }
    if (settings.method !== "GET") {
      settings.headers["X-Spider-Token"] = token;
    }
    const response = await fetch(path, settings);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || "Spider platform request failed");
    return payload;
  }

  async function refreshPlatform() {
    platform = (await request("/api/platform")).platform;
    renderStrip();
    return platform;
  }

  function renderStrip() {
    const strip = document.getElementById("platformStrip");
    if (!strip || !platform) return;
    strip.replaceChildren();

    const assembly = platform.assembly || {};
    const resident = platform.resident || {};
    const mode = platform.mode || {mode: "default"};

    strip.appendChild(statusChip(
      "WEB ASSEMBLY",
      assembly.status || "not-run",
      assembly.status === "ready" ? "ready" : "warning",
    ));
    strip.appendChild(statusChip(
      "WEBBIE",
      resident.active ? "resident" : "offline",
      resident.active ? "ready" : "warning",
    ));

    const modeGroup = element("div", "platform-mode-group");
    Object.entries(modeLabels).forEach(([name, label]) => {
      const button = element("button", "platform-mode-button");
      button.type = "button";
      button.textContent = label;
      button.classList.toggle("active", mode.mode === name);
      button.addEventListener("click", () => setMode(name, button));
      modeGroup.appendChild(button);
    });
    strip.appendChild(modeGroup);

    const control = element("button", "platform-control-button");
    control.type = "button";
    control.textContent = "Spider Control Center";
    control.addEventListener("click", openControlCenter);
    strip.appendChild(control);
  }

  function statusChip(label, value, status) {
    const chip = element("div", "platform-status-chip " + status);
    chip.appendChild(text("span", label));
    chip.appendChild(text("strong", value));
    return chip;
  }

  async function setMode(name, button) {
    const buttons = document.querySelectorAll(".platform-mode-button");
    buttons.forEach((item) => item.disabled = true);
    try {
      const result = await request("/api/mode", {method: "POST", body: {mode: name}});
      platform.mode = result.mode;
      renderStrip();
      announce("Workspace switched to " + modeLabels[name]);
    } catch (error) {
      announce(error.message, true);
      button.disabled = false;
    }
  }

  async function openControlCenter() {
    let dialog = document.getElementById("platformControlDialog");
    if (!dialog) {
      dialog = element("dialog", "modal wide-modal platform-control-dialog");
      dialog.id = "platformControlDialog";
      document.body.appendChild(dialog);
    }
    dialog.replaceChildren();

    const heading = element("div", "modal-heading");
    const titleWrap = element("div");
    titleWrap.appendChild(text("span", "SPIDER OS"));
    titleWrap.appendChild(text("h2", "Spider Control Center"));
    heading.appendChild(titleWrap);
    const close = element("button", "icon-button");
    close.type = "button";
    close.textContent = "×";
    close.setAttribute("aria-label", "Close Spider Control Center");
    close.addEventListener("click", () => dialog.close());
    heading.appendChild(close);
    dialog.appendChild(heading);

    const loading = text("p", "Reading atomic system and Device Web state…", "platform-loading");
    dialog.appendChild(loading);
    dialog.showModal();

    try {
      const [systemResponse, deviceResponse, platformResponse] = await Promise.all([
        request("/api/system"),
        request("/api/devices"),
        request("/api/platform"),
      ]);
      platform = platformResponse.platform;
      loading.remove();
      dialog.appendChild(renderControlGrid(systemResponse.system, deviceResponse.devices));
      dialog.appendChild(renderSystemActions());
      renderStrip();
    } catch (error) {
      loading.textContent = "Control Center could not read system state: " + error.message;
      loading.classList.add("error");
    }
  }

  function renderControlGrid(system, devices) {
    const grid = element("div", "platform-control-grid");

    const assemblyCard = controlCard("Web Assembly", platform.assembly?.status || "not-run");
    assemblyCard.appendChild(detailRow("Desktop", platform.desktop || "The Web"));
    assemblyCard.appendChild(detailRow("Resident AI", platform.resident_ai || "Webbie"));
    assemblyCard.appendChild(detailRow("Workspace", modeLabels[platform.mode?.mode] || platform.mode?.mode || "The Web"));
    assemblyCard.appendChild(detailRow("Setup", platform.setup?.complete ? "complete" : "needs attention"));
    grid.appendChild(assemblyCard);

    const updateCard = controlCard("Atomic system", system?.deployment?.provider || "provider unavailable");
    updateCard.appendChild(detailRow("Deployment", system?.deployment?.ready ? "ready" : "unavailable"));
    updateCard.appendChild(detailRow("Channel", system?.updates?.default_channel || "stable"));
    updateCard.appendChild(detailRow("Rollback", system?.recovery?.atomic_rollback ? "available" : "unavailable"));
    updateCard.appendChild(detailRow("Auto reboot", system?.updates?.automatic_reboot ? "enabled" : "disabled"));
    grid.appendChild(updateCard);

    const deviceCard = controlCard("Device Web", devices?.captured_at ? "scanned" : "not scanned");
    deviceCard.appendChild(detailRow("PCI devices", count(devices?.pci)));
    deviceCard.appendChild(detailRow("USB devices", count(devices?.usb)));
    deviceCard.appendChild(detailRow("Network", count(devices?.network)));
    deviceCard.appendChild(detailRow("Displays", count(devices?.displays)));
    deviceCard.appendChild(detailRow("Bluetooth", count(devices?.bluetooth?.devices)));
    const refresh = element("button", "button-secondary platform-refresh-button");
    refresh.type = "button";
    refresh.textContent = "Refresh Device Web";
    refresh.addEventListener("click", () => refreshDevices(refresh, deviceCard));
    deviceCard.appendChild(refresh);
    grid.appendChild(deviceCard);

    const webbieCard = controlCard("Webbie", platform.resident?.active ? "resident" : "offline");
    webbieCard.appendChild(detailRow("Wake phrases", (platform.resident?.wake_phrases || []).join(", ") || "not loaded"));
    webbieCard.appendChild(detailRow("Screen awareness", platform.resident?.screen_awareness ? "local + active" : "off"));
    webbieCard.appendChild(detailRow("Proactive", platform.resident?.proactive_enabled ? "enabled" : "off"));
    webbieCard.appendChild(detailRow("Authority", platform.resident?.authority_model || platform.setup?.authority || "graduated"));
    grid.appendChild(webbieCard);

    return grid;
  }

  function renderSystemActions() {
    const panel = element("section", "platform-actions-panel");
    panel.appendChild(text("span", "CONTROLLED SYSTEM ACTIONS", "eyebrow"));
    panel.appendChild(text("h3", "Updates and recovery"));
    panel.appendChild(text(
      "p",
      "Webbie can prepare these operations, but Spider OS keeps privileged execution behind explicit approval.",
    ));

    const actions = element("div", "platform-action-buttons");
    [
      ["update", "Plan update"],
      ["rollback", "Plan rollback"],
      ["reboot", "Plan reboot"],
    ].forEach(([action, label]) => {
      const button = element("button", "button-secondary");
      button.type = "button";
      button.textContent = label;
      button.addEventListener("click", () => showActionPlan(action, panel));
      actions.appendChild(button);
    });
    panel.appendChild(actions);
    return panel;
  }

  async function showActionPlan(action, panel) {
    panel.querySelector(".platform-action-plan")?.remove();
    const result = await request("/api/system/plan", {method: "POST", body: {action}});
    const plan = result.plan;
    const view = element("div", "platform-action-plan");
    view.appendChild(text("strong", plan.action.toUpperCase() + " · " + plan.tier));
    view.appendChild(text("span", "Approval required: " + (plan.requires_approval ? "yes" : "no")));
    view.appendChild(text("code", (plan.command || []).join(" ")));
    view.appendChild(text("small", "This screen prepares the operation only. No privileged command has been executed."));
    panel.appendChild(view);
  }

  async function refreshDevices(button, card) {
    button.disabled = true;
    button.textContent = "Scanning…";
    try {
      const response = await request("/api/devices?refresh=1");
      const devices = response.devices;
      platform.devices = devices;
      const rows = card.querySelectorAll(".platform-detail-row strong");
      const values = [count(devices.pci), count(devices.usb), count(devices.network), count(devices.displays), count(devices.bluetooth?.devices)];
      rows.forEach((row, index) => { if (values[index] !== undefined) row.textContent = String(values[index]); });
      button.textContent = "Device Web refreshed";
    } catch (error) {
      button.textContent = "Refresh failed";
      announce(error.message, true);
    } finally {
      window.setTimeout(() => {
        button.disabled = false;
        button.textContent = "Refresh Device Web";
      }, 1400);
    }
  }

  function controlCard(title, status) {
    const card = element("article", "platform-control-card");
    const head = element("div", "platform-control-card-heading");
    head.appendChild(text("h3", title));
    head.appendChild(text("span", status));
    card.appendChild(head);
    return card;
  }

  function detailRow(label, value) {
    const row = element("div", "platform-detail-row");
    row.appendChild(text("span", label));
    row.appendChild(text("strong", String(value ?? "unknown")));
    return row;
  }

  function count(value) {
    return Array.isArray(value) ? value.length : 0;
  }

  function renderFailure(error) {
    const strip = document.getElementById("platformStrip");
    if (!strip) return;
    strip.replaceChildren(statusChip("SPIDER PLATFORM", "degraded", "warning"));
    strip.title = error.message;
  }

  function announce(message, error = false) {
    let toast = document.getElementById("platformToast");
    if (!toast) {
      toast = element("div", "toast platform-toast");
      toast.id = "platformToast";
      toast.setAttribute("role", "status");
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.toggle("error", error);
    toast.classList.add("visible");
    window.setTimeout(() => toast.classList.remove("visible"), 2400);
  }

  function element(tag, className) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    return item;
  }

  function text(tag, value, className) {
    const item = element(tag, className);
    item.textContent = value;
    return item;
  }
})();
