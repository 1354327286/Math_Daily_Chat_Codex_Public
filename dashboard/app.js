import {
  escapeHTML,
  inlineMarkdown,
  renderMarkdown,
  renderSource,
} from "/reader-renderer.mjs";

"use strict";

const token = new URLSearchParams(window.location.search).get("token") || "";

const state = {
  overview: null,
  detail: null,
  activeTab: "state",
  viewer: null,
  viewerMode: "rendered",
  standaloneViewer: false,
  outlineOpen: true,
  outlineStatements: false,
  outlineHeadings: [],
  outlineScrollPending: false,
};

const elements = {
  generatedAt: document.getElementById("generatedAt"),
  metrics: document.getElementById("metrics"),
  projectSearch: document.getElementById("projectSearch"),
  roleFilter: document.getElementById("roleFilter"),
  refreshButton: document.getElementById("refreshButton"),
  projectCount: document.getElementById("projectCount"),
  projectRows: document.getElementById("projectRows"),
  emptyProjects: document.getElementById("emptyProjects"),
  listView: document.getElementById("listView"),
  detailView: document.getElementById("detailView"),
  backButton: document.getElementById("backButton"),
  detailName: document.getElementById("detailName"),
  detailRole: document.getElementById("detailRole"),
  detailDescription: document.getElementById("detailDescription"),
  detailStatus: document.getElementById("detailStatus"),
  detailConfidence: document.getElementById("detailConfidence"),
  detailUpdated: document.getElementById("detailUpdated"),
  detailTarget: document.getElementById("detailTarget"),
  detailNext: document.getElementById("detailNext"),
  detailBlocker: document.getElementById("detailBlocker"),
  detailTabs: document.getElementById("detailTabs"),
  detailContent: document.getElementById("detailContent"),
  fileDialog: document.getElementById("fileDialog"),
  viewerType: document.getElementById("viewerType"),
  viewerName: document.getElementById("viewerName"),
  viewerPath: document.getElementById("viewerPath"),
  viewerModes: document.getElementById("viewerModes"),
  viewerLayout: document.getElementById("viewerLayout"),
  viewerOutline: document.getElementById("viewerOutline"),
  viewerOutlineNav: document.getElementById("viewerOutlineNav"),
  viewerBody: document.getElementById("viewerBody"),
  outlineToggleButton: document.getElementById("outlineToggleButton"),
  outlineStatementsButton: document.getElementById("outlineStatementsButton"),
  copyPathButton: document.getElementById("copyPathButton"),
  exportReaderButton: document.getElementById("exportReaderButton"),
  openPublicButton: document.getElementById("openPublicButton"),
  openRawButton: document.getElementById("openRawButton"),
  closeViewerButton: document.getElementById("closeViewerButton"),
  toast: document.getElementById("toast"),
};

function withToken(path, params = {}) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("token", token);
  Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
  return `${url.pathname}${url.search}`;
}

async function getJSON(path, params = {}) {
  const response = await fetch(withToken(path, params), { cache: "no-store" });
  const payload = await response.json().catch(() => ({ error: "Invalid server response" }));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload;
}

function markdownContext(project, source) {
  return {
    project,
    source,
    resolveLocalLink: (target) => directFileUrl(project, source, target),
  };
}

function formatDate(value) {
  if (!value) return "Not recorded";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "short", day: "2-digit" }).format(parsed);
}

function formatGenerated(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Local state loaded";
  return `Updated ${new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(parsed)}`;
}

function fileType(path) {
  const extension = (path.split(".").pop() || "file").toUpperCase();
  if (extension === "MARKDOWN") return "MD";
  return extension.length <= 4 ? extension : "FILE";
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => elements.toast.classList.remove("is-visible"), 1800);
}

function renderMetrics(totals) {
  const items = [
    [totals.projects, "Registered projects"],
    [totals.recent, "Updated in 7 days"],
    [totals.open_problems, "Open obligations"],
    [totals.pending_handoffs, "Pending Pro handoffs"],
    [totals.inbox, "Inbox files"],
  ];
  elements.metrics.innerHTML = items.map(([value, label]) => `
    <div class="metric">
      <span class="metric-value">${escapeHTML(value)}</span>
      <span class="metric-label">${escapeHTML(label)}</span>
    </div>
  `).join("");
}

function renderRoleOptions(projects) {
  const current = elements.roleFilter.value;
  const roles = [...new Set(projects.map((project) => project.role))].sort();
  elements.roleFilter.innerHTML = `<option value="all">All</option>${roles.map((role) => `<option value="${escapeHTML(role)}">${escapeHTML(role)}</option>`).join("")}`;
  elements.roleFilter.value = roles.includes(current) ? current : "all";
}

function filteredProjects() {
  const query = elements.projectSearch.value.trim().toLowerCase();
  const role = elements.roleFilter.value;
  return state.overview.projects.filter((project) => {
    const roleMatch = role === "all" || project.role === role;
    const text = [project.title, project.path, project.description, project.target, project.next_action, project.status].join(" ").toLowerCase();
    return roleMatch && (!query || text.includes(query));
  });
}

function renderProjects() {
  const projects = filteredProjects();
  elements.projectCount.textContent = `${projects.length} of ${state.overview.projects.length}`;
  elements.emptyProjects.hidden = projects.length > 0;
  elements.projectRows.innerHTML = projects.map((project) => {
    const pending = project.handoff.pending;
    const handoffValue = project.handoff.total ? `${pending}/${project.handoff.total}` : "0";
    return `
      <tr tabindex="0" data-project="${escapeHTML(project.path)}">
        <td>
          <div class="project-name">${escapeHTML(project.title)}</div>
          <div class="project-description">${escapeHTML(project.description)}</div>
        </td>
        <td><span class="role-label" data-role="${escapeHTML(project.role)}">${escapeHTML(project.role)}</span></td>
        <td class="date-cell">${escapeHTML(formatDate(project.last_updated))}</td>
        <td><p class="cell-clamp">${escapeHTML(project.target)}</p></td>
        <td><p class="cell-clamp">${escapeHTML(project.next_action)}</p></td>
        <td class="count-cell">${escapeHTML(project.counts.open_problems)}<span class="subcount">${escapeHTML(project.counts.closed_problems)} closed</span></td>
        <td class="count-cell">${escapeHTML(handoffValue)}<span class="subcount">pending / total</span></td>
      </tr>
    `;
  }).join("");
}

const tabs = [
  ["state", "Research state", "Research State", null],
  ["theorems", "Known theorems", "Known Theorems", "known_theorems"],
  ["open", "Open problems", "Open Problems", "open_problems"],
  ["failures", "Failed attempts", "Failed Attempts", "failed_attempts"],
  ["references", "References", "References", "references"],
  ["files", "Files", null, null],
];

function renderTabs() {
  elements.detailTabs.innerHTML = tabs.map(([key, label, , countKey]) => {
    const count = countKey ? `<span class="tab-count">${escapeHTML(state.detail.counts[countKey])}</span>` : "";
    return `<button class="tab-button" type="button" role="tab" data-tab="${key}" aria-selected="${state.activeTab === key}">${label}${count}</button>`;
  }).join("");
}

function fileRow({ project, source, target, label, kind = "text", disabled = false, meta = "", standalone = false }) {
  const type = kind === "pdf" ? "PDF" : fileType(target);
  const separateWindow = standalone || kind === "pdf";
  const tag = disabled ? "div" : (separateWindow ? "a" : "button");
  const attributes = disabled
    ? ""
    : separateWindow
      ? `href="${escapeHTML(directFileUrl(project, source, target))}" target="_blank" rel="noopener"`
      : `type="button" data-file-project="${escapeHTML(project)}" data-file-source="${escapeHTML(source)}" data-file-target="${escapeHTML(target)}"`;
  return `<${tag} class="file-row file-row-button${disabled ? " is-disabled" : ""}" ${attributes}>
    <span class="file-type">${escapeHTML(type)}</span>
    <span>
      <span class="file-name">${escapeHTML(label || target.split("/").pop())}</span>
      <span class="file-path">${escapeHTML(target)}</span>
    </span>
    <span class="file-kind">${escapeHTML(meta || kind)}</span>
    <span class="file-open-mark">${disabled ? "–" : "↗"}</span>
  </${tag}>`;
}

function renderFiles() {
  const detail = state.detail;
  const localLinks = detail.links.filter((link) => link.kind !== "external");
  const externalLinks = detail.links.filter((link) => link.kind === "external");
  const referenced = localLinks.length
    ? localLinks.map((link) => fileRow({
        project: detail.path,
        source: link.source || "research_state.md",
        target: link.relative_path || link.target,
        label: link.label,
        kind: link.kind,
        disabled: link.kind === "missing" || link.kind === "directory",
        meta: link.kind === "missing" ? "missing" : link.kind,
      })).join("")
    : `<div class="empty-state">No referenced files</div>`;

  const projectFiles = [
    ...detail.core_files.map((path) => ({ path, meta: "core" })),
    ...detail.daily_notes.slice(0, 12).map((path) => ({ path, meta: "daily note" })),
    ...detail.memory_files.map((path) => ({ path, meta: "memory" })),
  ];
  const projectRows = projectFiles.map((item) => fileRow({
    project: detail.path,
    source: "research_state.md",
    target: item.path,
    label: item.path.split("/").pop(),
    kind: "text",
    meta: item.meta,
  })).join("");

  const readerRows = detail.reader_files?.length
    ? detail.reader_files.map((path) => fileRow({
        project: detail.path,
        source: "research_state.md",
        target: path,
        label: path.split("/").pop(),
        kind: "markdown",
        meta: "standalone reader",
        standalone: true,
      })).join("")
    : `<div class="empty-state">No generated reading copies</div>`;

  const external = externalLinks.length ? `
    <section class="file-section">
      <h3>External links</h3>
      <div class="file-list">${externalLinks.map((link) => `
        <a class="file-row file-row-button" href="${escapeHTML(link.href)}" target="_blank" rel="noopener">
          <span class="file-type">URL</span>
          <span><span class="file-name">${escapeHTML(link.label)}</span><span class="file-path">${escapeHTML(link.href)}</span></span>
          <span class="file-kind">external</span><span class="file-open-mark">↗</span>
        </a>`).join("")}</div>
    </section>` : "";

  return `
    <section class="file-section"><h3>Reading copies</h3><div class="file-list">${readerRows}</div></section>
    <section class="file-section"><h3>Referenced files</h3><div class="file-list">${referenced}</div></section>
    <section class="file-section"><h3>Project files</h3><div class="file-list">${projectRows}</div></section>
    ${external}
  `;
}

function renderDetailContent() {
  if (!state.detail) return;
  if (state.activeTab === "files") {
    elements.detailContent.innerHTML = renderFiles();
    return;
  }
  const tab = tabs.find(([key]) => key === state.activeTab);
  const sectionName = tab?.[2] || "Research State";
  const content = state.detail.sections[sectionName] || "No content recorded.";
  elements.detailContent.innerHTML = renderMarkdown(content, markdownContext(state.detail.path, "research_state.md"));
}

function renderDetail() {
  const detail = state.detail;
  elements.detailName.textContent = detail.title;
  elements.detailRole.textContent = detail.role;
  elements.detailRole.dataset.role = detail.role;
  elements.detailDescription.textContent = detail.description;
  elements.detailStatus.innerHTML = inlineMarkdown(detail.status, null);
  elements.detailConfidence.innerHTML = inlineMarkdown(detail.confidence, null);
  elements.detailUpdated.textContent = formatDate(detail.last_updated);
  elements.detailTarget.innerHTML = inlineMarkdown(detail.target, null);
  elements.detailNext.innerHTML = inlineMarkdown(detail.next_action, null);
  elements.detailBlocker.innerHTML = inlineMarkdown(detail.blocker, null);
  renderTabs();
  renderDetailContent();
}

async function loadOverview() {
  elements.refreshButton.disabled = true;
  try {
    state.overview = await getJSON("/api/overview");
    elements.generatedAt.textContent = formatGenerated(state.overview.generated_at);
    renderMetrics(state.overview.totals);
    renderRoleOptions(state.overview.projects);
    renderProjects();
  } catch (error) {
    elements.metrics.innerHTML = `<div class="error-state">${escapeHTML(error.message)}</div>`;
    elements.projectRows.innerHTML = "";
  } finally {
    elements.refreshButton.disabled = false;
  }
}

async function openProject(slug, updateHash = true) {
  elements.listView.hidden = true;
  elements.detailView.hidden = false;
  elements.detailContent.innerHTML = `<div class="loading-state">Loading project state</div>`;
  try {
    state.detail = await getJSON(`/api/projects/${encodeURIComponent(slug)}`);
    state.activeTab = "state";
    renderDetail();
    if (updateHash) window.location.hash = `project/${encodeURIComponent(slug)}`;
    window.scrollTo({ top: 0, behavior: "instant" });
  } catch (error) {
    elements.detailContent.innerHTML = `<div class="error-state">${escapeHTML(error.message)}</div>`;
  }
}

function showProjectList(updateHash = true) {
  state.detail = null;
  elements.detailView.hidden = true;
  elements.listView.hidden = false;
  if (updateHash) window.location.hash = "";
  window.scrollTo({ top: 0, behavior: "instant" });
}

function rawPDFUrl(project, relativePath, fragment = "") {
  const base = withToken(`/raw/${encodeURIComponent(project)}`, { path: relativePath });
  return fragment ? `${base}#${encodeURI(fragment)}` : base;
}

function directFileUrl(project, source, target) {
  return withToken("/", {
    viewer_project: project,
    viewer_source: source || "research_state.md",
    viewer_path: target,
    viewer_window: "standalone",
  });
}

function openStandaloneFile(project, source, target) {
  const opened = window.open(
    directFileUrl(project, source, target),
    "_blank",
    "popup=yes,width=1320,height=920,resizable=yes,scrollbars=yes,noopener",
  );
  if (!opened) showToast("Allow a new window to open this reader");
}

function activateStandaloneViewer() {
  const shell = document.createElement("main");
  shell.id = elements.fileDialog.id;
  shell.className = `${elements.fileDialog.className} standalone-reader-shell`;
  while (elements.fileDialog.firstChild) shell.appendChild(elements.fileDialog.firstChild);
  elements.fileDialog.replaceWith(shell);
  elements.fileDialog = shell;
}

function scrollToLocator() {
  if (!state.viewer?.locator) return;
  window.requestAnimationFrame(() => {
    elements.viewerBody.querySelector(".source-line.is-target")?.scrollIntoView({ block: "center" });
  });
}

function scrollToReaderAnchor(fragment) {
  if (!fragment) return false;
  const target = elements.viewerBody.querySelector(`#${CSS.escape(fragment)}`);
  if (!target) return false;
  target.scrollIntoView({ block: "start", behavior: "smooth" });
  requestOutlineSync();

  if (state.standaloneViewer) {
    const url = new URL(window.location.href);
    const viewerPath = url.searchParams.get("viewer_path");
    if (viewerPath) {
      url.searchParams.set("viewer_path", `${viewerPath.split("#", 1)[0]}#${fragment}`);
      window.history.replaceState(null, "", url);
    }
  }
  return true;
}

function isReaderMarkdown() {
  return state.standaloneViewer
    && state.viewer?.kind === "markdown"
    && /\.reader\.md$/i.test(state.viewer.relative_path || "");
}

function resetViewerOutline() {
  state.outlineHeadings = [];
  state.outlineScrollPending = false;
  elements.viewerOutlineNav.innerHTML = "";
  elements.viewerOutline.hidden = true;
  elements.viewerLayout.classList.remove("has-outline");
  elements.outlineToggleButton.hidden = true;
  elements.outlineToggleButton.setAttribute("aria-pressed", "false");
}

function syncOutlineVisibility() {
  const available = isReaderMarkdown() && state.viewerMode === "rendered" && state.outlineHeadings.length > 0;
  const visible = available && state.outlineOpen;
  elements.outlineToggleButton.hidden = !available;
  elements.outlineToggleButton.setAttribute("aria-pressed", visible ? "true" : "false");
  elements.viewerOutline.hidden = !visible;
  elements.viewerLayout.classList.toggle("has-outline", visible);
}

function syncActiveOutlineHeading() {
  if (!state.outlineHeadings.length || elements.viewerOutline.hidden) return;
  const readingLine = elements.viewerBody.scrollTop + Math.min(140, elements.viewerBody.clientHeight * 0.2);
  const candidates = state.outlineStatements
    ? state.outlineHeadings
    : state.outlineHeadings.filter((heading) => heading.tagName !== "H4");
  if (!candidates.length) return;
  const bodyTop = elements.viewerBody.getBoundingClientRect().top;
  let active = candidates[0];
  for (const heading of candidates) {
    const headingTop = heading.getBoundingClientRect().top - bodyTop + elements.viewerBody.scrollTop;
    if (headingTop > readingLine) break;
    active = heading;
  }
  elements.viewerOutlineNav.querySelectorAll("[data-outline-target]").forEach((button) => {
    const selected = button.dataset.outlineTarget === active.id;
    button.classList.toggle("is-active", selected);
    if (selected) button.setAttribute("aria-current", "location");
    else button.removeAttribute("aria-current");
  });
}

function requestOutlineSync() {
  if (state.outlineScrollPending) return;
  state.outlineScrollPending = true;
  window.requestAnimationFrame(() => {
    state.outlineScrollPending = false;
    syncActiveOutlineHeading();
  });
}

function updateStatementBookmarks() {
  elements.outlineStatementsButton.setAttribute("aria-pressed", state.outlineStatements ? "true" : "false");
  elements.outlineStatementsButton.textContent = state.outlineStatements ? "Hide statements" : "Statements";
  elements.viewerOutlineNav.classList.toggle("show-statements", state.outlineStatements);
}

function buildViewerOutline() {
  resetViewerOutline();
  if (!isReaderMarkdown() || state.viewerMode !== "rendered") return;
  const headings = Array.from(elements.viewerBody.querySelectorAll(".markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4"));
  const usedIds = new Set();
  headings.forEach((heading, index) => {
    const base = heading.id || `reader-heading-${index + 1}`;
    let unique = base;
    let suffix = 2;
    while (usedIds.has(unique)) {
      unique = `${base}-${suffix}`;
      suffix += 1;
    }
    heading.id = unique;
    usedIds.add(unique);
  });
  state.outlineHeadings = headings;
  elements.viewerOutlineNav.innerHTML = headings.map((heading) => {
    const level = Number(heading.tagName.slice(1));
    const label = heading.dataset.outlineLabel || heading.textContent.trim();
    return `<button class="viewer-outline-link level-${level}" type="button" data-outline-target="${escapeHTML(heading.id)}">${escapeHTML(label)}</button>`;
  }).join("");
  updateStatementBookmarks();
  syncOutlineVisibility();
  requestOutlineSync();
}

function setViewerMode(mode) {
  if (!state.viewer || state.viewer.kind !== "markdown") return;
  state.viewerMode = mode;
  elements.viewerModes.querySelectorAll("button").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.viewerMode === mode ? "true" : "false");
  });
  if (mode === "rendered") {
    elements.viewerBody.innerHTML = renderMarkdown(
      state.viewer.content,
      markdownContext(state.viewer.project, state.viewer.relative_path),
    );
    buildViewerOutline();
    if (state.viewer.fragment) {
      window.requestAnimationFrame(() => {
        const target = elements.viewerBody.querySelector(`#${CSS.escape(state.viewer.fragment)}`);
        target?.scrollIntoView({ block: "start" });
        requestOutlineSync();
      });
    }
  } else {
    resetViewerOutline();
    elements.viewerBody.innerHTML = renderSource(state.viewer.content, state.viewer.locator);
    scrollToLocator();
  }
}

async function openFile(project, source, target) {
  if (!target || /^(https?:|mailto:)/i.test(target)) return;
  if (!state.standaloneViewer && !elements.fileDialog.open) elements.fileDialog.showModal();
  elements.viewerName.textContent = "Loading";
  elements.viewerPath.textContent = target;
  elements.viewerType.textContent = fileType(target);
  elements.viewerModes.hidden = true;
  elements.exportReaderButton.hidden = true;
  elements.openPublicButton.hidden = true;
  elements.openRawButton.hidden = true;
  resetViewerOutline();
  elements.viewerBody.innerHTML = `<div class="loading-state">Opening local file</div>`;
  try {
    state.viewer = await getJSON(`/api/files/${encodeURIComponent(project)}`, { source, path: target });
    elements.viewerName.textContent = state.viewer.name;
    elements.viewerPath.textContent = state.viewer.relative_path;
    elements.viewerType.textContent = state.viewer.kind === "pdf" ? "PDF" : fileType(state.viewer.relative_path);
    if (state.viewer.public_source) {
      elements.openPublicButton.href = state.viewer.public_source;
      elements.openPublicButton.hidden = false;
    }
    if (state.standaloneViewer) {
      document.title = `${state.viewer.name} — Research reader`;
    }
    if (state.viewer.kind === "markdown" && /\.reader\.md$/i.test(state.viewer.relative_path)) {
      elements.exportReaderButton.hidden = false;
    }
    if (state.viewer.kind === "pdf") {
      const rawUrl = rawPDFUrl(project, state.viewer.relative_path, state.viewer.fragment);
      elements.openRawButton.href = rawUrl;
      elements.openRawButton.hidden = false;
      elements.viewerBody.innerHTML = `<iframe class="pdf-frame" src="${escapeHTML(rawUrl)}" title="${escapeHTML(state.viewer.name)}"></iframe>`;
    } else if (state.viewer.kind === "markdown") {
      elements.viewerModes.hidden = false;
      setViewerMode("rendered");
    } else {
      elements.viewerBody.innerHTML = renderSource(state.viewer.content, state.viewer.locator);
      scrollToLocator();
    }
  } catch (error) {
    state.viewer = null;
    resetViewerOutline();
    elements.viewerBody.innerHTML = `<div class="error-state">${escapeHTML(error.message)}</div>`;
  }
}

async function exportCurrentReader() {
  if (!state.viewer || !/\.reader\.md$/i.test(state.viewer.relative_path || "")) return;
  elements.exportReaderButton.disabled = true;
  showToast("Exporting offline package…");
  try {
    const response = await fetch(
      withToken(`/api/export-reader/${encodeURIComponent(state.viewer.project)}`),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: state.viewer.relative_path }),
        cache: "no-store",
      },
    );
    const payload = await response.json().catch(() => ({ error: "Invalid server response" }));
    if (!response.ok) throw new Error(payload.error || `Export failed (${response.status})`);
    elements.exportReaderButton.title = `Exported to ${payload.output}`;
    showToast("Exported to the project's exports folder");
  } catch (error) {
    showToast(error.message || "Offline export failed");
  } finally {
    elements.exportReaderButton.disabled = false;
  }
}

async function copyViewerPath() {
  if (!state.viewer?.absolute_path) return;
  try {
    await navigator.clipboard.writeText(state.viewer.absolute_path);
  } catch {
    const input = document.createElement("textarea");
    input.value = state.viewer.absolute_path;
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
  }
  showToast("Path copied");
}

document.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-project]");
  if (row) openProject(row.dataset.project);

  const localFile = event.target.closest("[data-file-target]");
  if (localFile) {
    event.preventDefault();
    const project = localFile.dataset.fileProject;
    const source = localFile.dataset.fileSource || "research_state.md";
    const target = localFile.dataset.fileTarget;
    const isReader = /\.reader\.md(?:#.*)?$/i.test(target);
    if (state.standaloneViewer) {
      window.location.assign(directFileUrl(project, source, target));
    } else if (localFile.dataset.fileNewTab === "true" || isReader) {
      openStandaloneFile(project, source, target);
    } else {
      openFile(project, source, target);
    }
  }

  const tab = event.target.closest("[data-tab]");
  if (tab) {
    state.activeTab = tab.dataset.tab;
    renderTabs();
    renderDetailContent();
  }

  const viewerMode = event.target.closest("[data-viewer-mode]");
  if (viewerMode) setViewerMode(viewerMode.dataset.viewerMode);
});

document.addEventListener("keydown", (event) => {
  if ((event.key === "Enter" || event.key === " ") && event.target.matches("tr[data-project]")) {
    event.preventDefault();
    openProject(event.target.dataset.project);
  }
});

elements.projectSearch.addEventListener("input", renderProjects);
elements.roleFilter.addEventListener("change", renderProjects);
elements.refreshButton.addEventListener("click", async () => {
  await loadOverview();
  if (state.detail) await openProject(state.detail.path, false);
});
elements.backButton.addEventListener("click", () => showProjectList());
elements.closeViewerButton.addEventListener("click", () => {
  if (state.standaloneViewer) window.close();
  else elements.fileDialog.close();
});
elements.copyPathButton.addEventListener("click", copyViewerPath);
elements.exportReaderButton.addEventListener("click", exportCurrentReader);
elements.outlineToggleButton.addEventListener("click", () => {
  state.outlineOpen = !state.outlineOpen;
  syncOutlineVisibility();
  requestOutlineSync();
});
elements.outlineStatementsButton.addEventListener("click", () => {
  state.outlineStatements = !state.outlineStatements;
  updateStatementBookmarks();
  requestOutlineSync();
});
elements.viewerOutlineNav.addEventListener("click", (event) => {
  const link = event.target.closest("[data-outline-target]");
  if (!link) return;
  const target = elements.viewerBody.querySelector(`#${CSS.escape(link.dataset.outlineTarget)}`);
  target?.scrollIntoView({ block: "start", behavior: "smooth" });
});
elements.viewerBody.addEventListener("click", (event) => {
  const link = event.target.closest("[data-reader-anchor]");
  if (!link) return;
  event.preventDefault();
  scrollToReaderAnchor(link.dataset.readerAnchor);
});
elements.viewerBody.addEventListener("scroll", requestOutlineSync, { passive: true });
elements.fileDialog.addEventListener("click", (event) => {
  if (event.target === elements.fileDialog) elements.fileDialog.close();
});
elements.fileDialog.addEventListener("close", () => {
  resetViewerOutline();
  elements.viewerBody.innerHTML = "";
  state.viewer = null;
});

window.addEventListener("hashchange", () => {
  const match = window.location.hash.match(/^#project\/(.+)$/);
  if (match) {
    const slug = decodeURIComponent(match[1]);
    if (!state.detail || state.detail.path !== slug) openProject(slug, false);
  } else if (!elements.listView.hidden) {
    return;
  } else {
    showProjectList(false);
  }
});

async function start() {
  if (!token) {
    elements.metrics.innerHTML = `<div class="error-state">Dashboard session token is missing</div>`;
    return;
  }
  const directParams = new URLSearchParams(window.location.search);
  const directProject = directParams.get("viewer_project");
  const directSource = directParams.get("viewer_source") || "research_state.md";
  const directPath = directParams.get("viewer_path");
  state.standaloneViewer = directParams.get("viewer_window") === "standalone";
  if (state.standaloneViewer && directProject && directPath) {
    state.outlineOpen = !window.matchMedia("(max-width: 880px)").matches;
    document.body.classList.add("standalone-viewer");
    activateStandaloneViewer();
    elements.closeViewerButton.title = "Close reader window";
    elements.closeViewerButton.setAttribute("aria-label", "Close reader window");
    await openFile(directProject, directSource, directPath);
    return;
  }
  await loadOverview();
  if (directProject && directPath) {
    await openProject(directProject, false);
    await openFile(directProject, directSource, directPath);
    return;
  }
  const match = window.location.hash.match(/^#project\/(.+)$/);
  if (match) await openProject(decodeURIComponent(match[1]), false);
}

start();
