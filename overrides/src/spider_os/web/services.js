"use strict";

(() => {
  let csrf = "";

  document.addEventListener("DOMContentLoaded", () => {
    boot().catch(() => {});
  });

  async function boot() {
    const bootstrap = await api("/api/bootstrap");
    csrf = bootstrap.csrf_token || "";
    const strip = document.getElementById("platformStrip");
    if (!strip) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "platform-control-button spider-services-button";
    button.textContent = "Spider Services";
    button.addEventListener("click", openServices);
    strip.appendChild(button);
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
    if (settings.method !== "GET") settings.headers["X-Spider-Token"] = csrf;
    const response = await fetch(path, settings);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || "Spider service request failed");
    return payload;
  }

  async function openServices() {
    const dialog = ensureDialog();
    dialog.replaceChildren(header(dialog), note("Reading Spider services…"));
    if (!dialog.open) dialog.showModal();

    try {
      const [store, vault, sync, models, voice, studio] = await Promise.all([
        api("/api/store"),
        api("/api/vault"),
        api("/api/sync"),
        api("/api/models"),
        api("/api/voice"),
        api("/api/studio"),
      ]);
      dialog.replaceChildren(header(dialog));
      const grid = node("div", "spider-services-grid");
      grid.append(
        serviceCard("Spider Store", store.store?.available ? "ready" : "unavailable", [
          ["Installed", count(store.store?.installed)],
          ["Remotes", count(store.store?.remotes)],
          ["Policy", store.store?.policy?.host_packages || "image-build-only"],
        ]),
        serviceCard("Spider Vault", vault.vault?.available ? "ready" : "provider needed", [
          ["Provider", vault.vault?.provider || "none"],
          ["Secrets in DB", vault.vault?.policy?.secret_values_in_spider_database ? "yes" : "never"],
          ["Webbie memory", vault.vault?.policy?.secret_values_in_webbie_memory ? "allowed" : "blocked"],
        ]),
        serviceCard("Spider Sync", sync.sync?.enabled ? "enabled" : "off", [
          ["Provider", sync.sync?.provider || "none"],
          ["Encrypted", sync.sync?.encrypted ? "required" : "no"],
          ["Scopes", (sync.sync?.scopes || []).join(", ") || "none"],
        ]),
        serviceCard("Model Router", models.models?.local?.available ? "local ready" : "fallback mode", [
          ["Local", models.models?.local?.available ? (models.models.local.model || "available") : "offline"],
          ["Cloud", models.models?.cloud?.configured ? models.models.cloud.provider : "disabled"],
          ["Restricted", models.models?.policy?.restricted || "local-only"],
        ]),
        serviceCard("Webbie Voice", voice.voice?.wake_engine || voice.voice?.speech_to_text || voice.voice?.text_to_speech ? "capable" : "adapters needed", [
          ["Wake", voice.voice?.wake_engine || "not installed"],
          ["STT", voice.voice?.speech_to_text || "not installed"],
          ["TTS", voice.voice?.text_to_speech || "not installed"],
        ]),
        serviceCard("Spider Studio", studio.studio?.audio?.pipewire ? "PipeWire ready" : "audio unavailable", [
          ["JACK compat", studio.studio?.audio?.jack_compat ? "ready" : "not detected"],
          ["MIDI", studio.studio?.midi?.available ? "ready" : "not detected"],
          ["Creative apps", count((studio.studio?.creative_apps || []).filter((app) => app.installed))],
        ]),
      );
      dialog.append(grid, storeSearchPanel(), routingPanel(), syncPanel(sync.sync));
    } catch (error) {
      dialog.append(note(error.message, true));
    }
  }

  function ensureDialog() {
    let dialog = document.getElementById("spiderServicesDialog");
    if (!dialog) {
      dialog = node("dialog", "modal wide-modal spider-services-dialog");
      dialog.id = "spiderServicesDialog";
      document.body.appendChild(dialog);
    }
    return dialog;
  }

  function header(dialog) {
    const wrap = node("div", "modal-heading");
    const title = node("div");
    title.append(text("span", "THE WEB"), text("h2", "Spider Services"));
    const close = node("button", "icon-button");
    close.type = "button";
    close.textContent = "×";
    close.setAttribute("aria-label", "Close Spider Services");
    close.addEventListener("click", () => dialog.close());
    wrap.append(title, close);
    return wrap;
  }

  function serviceCard(title, status, rows) {
    const card = node("article", "spider-service-card");
    const head = node("div", "spider-service-heading");
    head.append(text("h3", title), text("span", status));
    card.appendChild(head);
    rows.forEach(([label, value]) => card.appendChild(detail(label, value)));
    return card;
  }

  function storeSearchPanel() {
    const panel = section("SPIDER STORE", "Search applications", "Flatpak-first discovery. Installs remain approval-gated.");
    const form = node("form", "spider-service-form");
    const input = node("input");
    input.type = "search";
    input.placeholder = "Search Flatpak apps";
    const button = text("button", "Search");
    button.type = "submit";
    button.className = "button-secondary";
    const results = node("div", "spider-service-results");
    form.append(input, button);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      results.replaceChildren(text("span", "Searching…"));
      try {
        const payload = await api("/api/store?q=" + encodeURIComponent(q));
        renderStoreResults(payload.store, results);
      } catch (error) {
        results.replaceChildren(text("span", error.message));
      }
    });
    panel.append(form, results);
    return panel;
  }

  function renderStoreResults(store, target) {
    target.replaceChildren();
    const results = store?.results || [];
    if (!results.length) {
      target.appendChild(text("span", store?.error || "No matching apps."));
      return;
    }
    results.slice(0, 10).forEach((row) => {
      const item = node("div", "spider-service-result");
      const body = node("div");
      body.append(text("strong", row[1] || row[0] || "Application"), text("span", row[0] || ""));
      const plan = text("button", "Plan install");
      plan.type = "button";
      plan.className = "button-secondary";
      plan.addEventListener("click", () => showPlan(item, "/api/store/plan", {action: "install", app_id: row[0] || ""}));
      item.append(body, plan);
      target.appendChild(item);
    });
  }

  function routingPanel() {
    const panel = section("WEBBIE MODEL ROUTER", "Privacy-aware inference", "Restricted context stays local. Private cloud fallback requires explicit permission.");
    const actions = node("div", "spider-service-actions");
    [["standard", false], ["private", false], ["restricted", false]].forEach(([sensitivity, allowed]) => {
      const button = text("button", "Test " + sensitivity);
      button.type = "button";
      button.className = "button-secondary";
      button.addEventListener("click", async () => {
        const result = await api("/api/models/route", {method: "POST", body: {sensitivity, cloud_explicitly_allowed: allowed}});
        showInline(panel, result.route.route + " · " + result.route.reason);
      });
      actions.appendChild(button);
    });
    panel.appendChild(actions);
    return panel;
  }

  function syncPanel(sync) {
    const panel = section("SPIDER SYNC", "Encrypted sync policy", "Off by default. Credentials stay in Spider Vault.");
    panel.appendChild(detail("Current provider", sync?.provider || "none"));
    panel.appendChild(detail("Enabled", sync?.enabled ? "yes" : "no"));
    const off = text("button", "Keep sync off");
    off.type = "button";
    off.className = "button-secondary";
    off.addEventListener("click", async () => {
      const result = await api("/api/sync/configure", {method: "POST", body: {enabled: false, provider: "none"}});
      showInline(panel, "Spider Sync: " + (result.sync.enabled ? "enabled" : "off"));
    });
    panel.appendChild(off);
    return panel;
  }

  async function showPlan(target, endpoint, body) {
    const result = await api(endpoint, {method: "POST", body});
    const plan = result.plan || {};
    showInline(target, (plan.command || []).join(" ") || plan.action || "Plan ready");
  }

  function showInline(target, value) {
    target.querySelector(".spider-service-inline")?.remove();
    const item = text("code", value);
    item.className = "spider-service-inline";
    target.appendChild(item);
  }

  function section(eyebrow, title, description) {
    const panel = node("section", "spider-service-panel");
    panel.append(text("span", eyebrow, "eyebrow"), text("h3", title), text("p", description));
    return panel;
  }

  function detail(label, value) {
    const row = node("div", "platform-detail-row");
    row.append(text("span", label), text("strong", String(value ?? "unknown")));
    return row;
  }

  function note(value, error = false) {
    const item = text("p", value, "platform-loading" + (error ? " error" : ""));
    return item;
  }

  function count(value) {
    return Array.isArray(value) ? value.length : 0;
  }

  function node(tag, className) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    return item;
  }

  function text(tag, value, className) {
    const item = node(tag, className);
    item.textContent = value;
    return item;
  }
})();
