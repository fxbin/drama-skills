"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  project: null,
  projectPath: "",
  files: [],
  selected: null,
  version: null,
  dirty: false,
  view: "preview",
  loadSequence: 0,
};

const AXIS_LABELS = {
  build_state: "构建",
  validation_state: "验证",
  creator_acceptance: "创作者确认",
  independent_review: "独立审查",
  delivery_gate: "交付",
};

const STATE_LABELS = {
  materialized: "已生成",
  validated: "已验证",
  accepted: "已确认",
  approved: "已通过",
  approve: "通过",
  approve_with_notes: "附注通过",
  pass: "通过",
  pass_with_warnings: "有提醒",
  ready: "可交付",
  delivered: "已交付",
  complete: "完成",
  in_progress: "进行中",
  not_run: "未运行",
  not_requested: "未发起",
  not_evaluated: "未评估",
  absent: "暂无",
  pending: "待确认",
  provisional: "临时结论",
  blocked: "阻塞",
  rejected: "已拒绝",
  revise: "待修改",
  failed: "失败",
  stale: "已过期",
};

const CHECKPOINT_LABELS = {
  "promo-generation": "宣发生成",
  "demo-ready": "演示就绪",
  development: "项目开发",
  writing: "剧本创作",
  storyboard: "分镜制作",
  review: "项目审查",
  delivery: "交付准备",
};

const PATH_SEGMENT_LABELS = {
  development: "项目开发",
  bible: "设定集",
  episodes: "剧集",
  publicity: "宣发",
  "creator-decisions": "创作者决策",
  reviews: "审查",
  inputs: "输入",
  delivery: "交付",
  storyboard: "分镜",
  assets: "资产",
  media: "媒体",
};

const FILE_LABELS = {
  "readme.md": "项目说明.md",
  "short-drama.json": "项目清单.json",
  "creative-brief.md": "创作简报.md",
  "story-engine.md": "故事引擎.md",
  "episode-map.jsonl": "分集地图.jsonl",
  "characters.jsonl": "角色.jsonl",
  "looks.jsonl": "造型.jsonl",
  "locations.jsonl": "场景.jsonl",
  "location-views.jsonl": "场景视图.jsonl",
  "props.jsonl": "道具.jsonl",
  "prop-states.jsonl": "道具状态.jsonl",
  "episode-card.json": "分集卡.json",
  "screenplay.md": "剧本.md",
  "shots.jsonl": "镜头表.jsonl",
  "keyframe-prompts.md": "关键帧提示词.md",
  "campaign.md": "宣发方案.md",
  "generation-jobs.jsonl": "生成记录.jsonl",
  "previs-review.md": "动态预演验收.md",
  "teaser-15s-review.md": "上一版15秒审核.md",
  "teaser-15s-final-review.md": "15秒音画演示验收.md",
  "video-prompt.md": "视频提示词.md",
  "video-qc-checklist.md": "视频验收清单.md",
  "subtitle-review.md": "字幕校对记录.md",
};

function displaySegment(segment, isFile = false) {
  const key = segment.toLowerCase();
  return (isFile ? FILE_LABELS[key] : null) || PATH_SEGMENT_LABELS[key] || segment;
}

function displayPath(path) {
  const parts = path.split("/");
  return parts
    .map((part, index) => displaySegment(part, index === parts.length - 1))
    .join("/");
}

function domainOf(path, type) {
  if (/(^|\/)(references?|inputs?|research|参考|输入)(\/|$)/i.test(path)) {
    return "reference";
  }
  if (
    type === "media" ||
    /(^|\/)(promo|marketing|publicity|delivery|宣发|交付)(\/|$)/i.test(path)
  ) {
    return "promo";
  }
  return "text";
}

function formatBytes(size) {
  if (!Number.isFinite(size)) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 ** 2).toFixed(1)} MB`;
}

function pathParts(path) {
  const parts = path.split("/");
  const name = parts.pop();
  return {
    name: displaySegment(name, true),
    parent: parts.map((part) => displaySegment(part)).join("/") || "项目根目录",
    group: displaySegment(parts[0] || "项目根目录"),
  };
}

function toneFor(states) {
  const names = Object.keys(states || {});
  if (names.some((name) => ["blocked", "rejected"].includes(name))) return "danger";
  if (names.some((name) => ["pending", "provisional", "not_run", "stale"].includes(name))) {
    return "warning";
  }
  return "success";
}

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function flatten(nodes, out = []) {
  for (const node of nodes) {
    if (node.type === "directory") {
      flatten(node.children || [], out);
    } else {
      out.push(node);
    }
  }
  return out;
}

function warnLeave() {
  return !state.dirty || confirm("当前文件有未保存更改，确认放弃吗？");
}

function setMessage(text, tone = "neutral") {
  $("message").textContent = text;
  $("message").dataset.tone = tone;
}

function setDirty(value) {
  state.dirty = value;
  $("save").disabled = !value || !state.selected?.writable;
  $("save").textContent = value ? "保存更改" : "已保存";
  document.title = `${value ? "● " : ""}短剧项目控制台`;
  updateFileMeta();
}

function updateFileMeta(extra = "") {
  const file = state.selected;
  if (!file) {
    $("fileMeta").textContent = "";
    return;
  }
  const facts = [formatBytes(file.size)];
  if (file.oversize) facts.push("超过预览限制");
  if (file.type !== "media") facts.push(file.writable ? "可编辑" : "只读");
  if (state.dirty) facts.push("未保存");
  if (extra) facts.push(extra);
  $("fileMeta").textContent = facts.filter(Boolean).join(" · ");
}

function cleanupMedia() {
  const video = $("media").querySelector("video");
  if (video) {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
  const image = $("media").querySelector("img");
  if (image) image.removeAttribute("src");
  $("media").replaceChildren();
}

function renderDomainCounts() {
  const counts = { text: 0, promo: 0, reference: 0 };
  for (const file of state.files) counts[domainOf(file.path, file.type)] += 1;
  $("textCount").textContent = counts.text;
  $("promoCount").textContent = counts.promo;
  $("referenceCount").textContent = counts.reference;
}

function fileIcon(file) {
  if (file.type === "media") {
    return /\.(mp4|webm|mov)$/i.test(file.path) ? "▶" : "◆";
  }
  if (/\.jsonl?$/i.test(file.path)) return "{}";
  if (/\.md$/i.test(file.path)) return "¶";
  return "≡";
}

function renderFiles() {
  const domain = document.querySelector(".domain.active").dataset.domain;
  const term = $("search").value.trim().toLowerCase();
  const filtered = state.files.filter(
    (file) =>
      domainOf(file.path, file.type) === domain &&
      `${file.path} ${displayPath(file.path)}`.toLowerCase().includes(term),
  );
  const groups = new Map();
  for (const file of filtered) {
    const group = pathParts(file.path).group;
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(file);
  }
  const content = [];
  for (const [group, files] of groups) {
    const heading = document.createElement("div");
    heading.className = "file-group";
    const groupName = document.createElement("span");
    const groupCount = document.createElement("b");
    groupName.textContent = group;
    groupCount.textContent = files.length;
    heading.append(groupName, groupCount);
    content.push(heading);

    for (const file of files) {
      const parts = pathParts(file.path);
      const button = document.createElement("button");
      button.className = "file";
      button.title = file.path;
      button.dataset.path = file.path;
      if (state.selected?.path === file.path) {
        button.classList.add("selected");
        button.setAttribute("aria-current", "true");
      }
      const icon = document.createElement("span");
      const labels = document.createElement("span");
      const name = document.createElement("strong");
      const detail = document.createElement("small");
      icon.className = "file-icon";
      labels.className = "file-labels";
      icon.textContent = fileIcon(file);
      name.textContent = parts.name;
      detail.textContent = `${parts.parent} · ${file.oversize ? "过大" : formatBytes(file.size)}`;
      labels.append(name, detail);
      button.append(icon, labels);
      button.onclick = () => openFile(file);
      content.push(button);
    }
  }
  if (!content.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = term ? "没有匹配的文件" : "这个分区还没有文件";
    content.push(empty);
  }
  $("resultCount").textContent = filtered.length;
  $("resultLabel").textContent = term ? `“${$("search").value.trim()}”` : "文件";
  $("tree").replaceChildren(...content);
}

function appendInlineText(element, text) {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  for (const token of tokens) {
    if (token.startsWith("`") && token.endsWith("`")) {
      const code = document.createElement("code");
      code.textContent = token.slice(1, -1);
      element.append(code);
    } else if (token.startsWith("**") && token.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      element.append(strong);
    } else {
      element.append(document.createTextNode(token));
    }
  }
}

function renderMarkdown(content) {
  const fragment = document.createDocumentFragment();
  let list = null;
  let listType = "";
  let codeLines = null;

  function closeList() {
    list = null;
    listType = "";
  }

  for (const line of content.split("\n")) {
    if (line.startsWith("```")) {
      closeList();
      if (codeLines === null) {
        codeLines = [];
      } else {
        const pre = document.createElement("pre");
        const code = document.createElement("code");
        code.textContent = codeLines.join("\n");
        pre.append(code);
        fragment.append(pre);
        codeLines = null;
      }
      continue;
    }
    if (codeLines !== null) {
      codeLines.push(line);
      continue;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      closeList();
      const element = document.createElement(`h${heading[1].length}`);
      appendInlineText(element, heading[2]);
      fragment.append(element);
      continue;
    }
    const unordered = /^[-*]\s+(.+)$/.exec(line);
    const ordered = /^(\d+)\.\s+(.+)$/.exec(line);
    if (unordered || ordered) {
      const wanted = unordered ? "ul" : "ol";
      if (!list || listType !== wanted) {
        list = document.createElement(wanted);
        listType = wanted;
        fragment.append(list);
      }
      const item = document.createElement("li");
      appendInlineText(item, unordered ? unordered[1] : ordered[2]);
      if (ordered) item.value = Number(ordered[1]);
      list.append(item);
      continue;
    }
    closeList();
    if (!line.trim()) continue;
    const quote = /^>\s?(.*)$/.exec(line);
    const element = document.createElement(quote ? "blockquote" : "p");
    appendInlineText(element, quote ? quote[1] : line);
    fragment.append(element);
  }
  if (codeLines !== null) {
    const pre = document.createElement("pre");
    pre.textContent = codeLines.join("\n");
    fragment.append(pre);
  }
  return fragment;
}

function parseJsonLines(content) {
  return content
    .split("\n")
    .map((line, index) => ({ line: index + 1, value: line.trim() }))
    .filter((record) => record.value)
    .map((record) => {
      try {
        return JSON.parse(record.value);
      } catch (error) {
        throw new Error(`JSONL 第 ${record.line} 行无效：${error.message}`);
      }
    });
}

function validateStructuredText(path, content) {
  if (/\.json$/i.test(path)) {
    try {
      JSON.parse(content);
    } catch (error) {
      throw new Error(`JSON 无效：${error.message}`);
    }
  } else if (/\.jsonl$/i.test(path)) {
    parseJsonLines(content);
  }
}

function renderPreview() {
  const preview = $("preview");
  const content = $("editor").value;
  const path = state.selected?.path || "";
  preview.replaceChildren();
  try {
    if (/\.md$/i.test(path)) {
      preview.append(renderMarkdown(content));
    } else {
      const pre = document.createElement("pre");
      pre.className = "code-block";
      if (/\.json$/i.test(path)) {
        pre.textContent = JSON.stringify(JSON.parse(content), null, 2);
      } else if (/\.jsonl$/i.test(path)) {
        pre.textContent = parseJsonLines(content)
          .map((record) => JSON.stringify(record, null, 2))
          .join("\n\n");
      } else {
        pre.textContent = content;
      }
      preview.append(pre);
    }
  } catch (error) {
    const warning = document.createElement("div");
    const raw = document.createElement("pre");
    warning.className = "preview-warning";
    warning.textContent = error.message;
    raw.className = "code-block";
    raw.textContent = content;
    preview.append(warning, raw);
  }
}

function setView(view) {
  state.view = view;
  const isMedia = state.selected?.type === "media";
  $("editor").hidden = isMedia || view !== "edit";
  $("preview").hidden = isMedia || view !== "preview";
  $("media").hidden = !isMedia;
  $("editMode").setAttribute("aria-pressed", String(view === "edit"));
  $("previewMode").setAttribute("aria-pressed", String(view === "preview"));
  if (!isMedia && view === "preview") renderPreview();
}

function mediaBadge(path, kind) {
  if (/fallback|preview|previs/i.test(path)) return ["本地预演", "warning"];
  if (/final|正式|成片/i.test(path) && kind === "video") {
    return ["正式成片", "success"];
  }
  if (/demo|演示/i.test(path) && kind === "video") return ["音画演示", "success"];
  if (kind === "video") return ["生成视频 · 待审", "warning"];
  return ["视觉资产", "info"];
}

function renderMedia(info) {
  cleanupMedia();
  const shell = document.createElement("div");
  const stage = document.createElement("div");
  const facts = document.createElement("div");
  const badge = document.createElement("span");
  const technical = document.createElement("span");
  const [badgeText, tone] = mediaBadge(state.selected.path, info.kind);
  shell.className = "media-shell";
  stage.className = "media-stage";
  facts.className = "media-facts";
  badge.className = "media-badge";
  badge.dataset.tone = tone;
  badge.textContent = badgeText;
  technical.textContent = `${info.kind === "video" ? "视频" : "图片"} · ${formatBytes(info.size)} · 只读`;
  facts.append(badge, technical);

  const element = document.createElement(info.kind === "video" ? "video" : "img");
  element.src = info.contentUrl;
  element.setAttribute("aria-label", state.selected.path);
  if (info.kind === "video") {
    element.controls = true;
    element.preload = "metadata";
    element.playsInline = true;
    element.onloadedmetadata = () => {
      const seconds = Number.isFinite(element.duration) ? `${element.duration.toFixed(2)} 秒` : "";
      technical.textContent = [
        "视频",
        `${element.videoWidth}×${element.videoHeight}`,
        seconds,
        formatBytes(info.size),
        "只读",
      ].filter(Boolean).join(" · ");
      updateFileMeta(seconds);
    };
  } else {
    element.alt = state.selected.path;
    element.onload = () => {
      technical.textContent = `图片 · ${element.naturalWidth}×${element.naturalHeight} · ${formatBytes(info.size)} · 只读`;
    };
  }
  element.onerror = () => setMessage("媒体加载失败或超过预览限制", "danger");
  stage.append(element);
  shell.append(stage, facts);
  $("media").replaceChildren(shell);
  setMessage("媒体预览已载入。", "neutral");
}

async function openFile(file) {
  if (state.selected?.path !== file.path && !warnLeave()) return;
  const sequence = ++state.loadSequence;
  cleanupMedia();
  state.selected = file;
  state.version = null;
  setDirty(false);
  renderFiles();
  const parts = pathParts(file.path);
  $("filename").textContent = parts.name;
  $("filename").title = file.path;
  $("fileKind").textContent = file.type === "media" ? "媒体预览" : parts.parent;
  $("editMode").disabled = file.type === "media";
  $("previewMode").disabled = file.type === "media";
  setMessage("正在载入…");

  try {
    if (file.type === "media") {
      setView("preview");
      const info = await api(
        `/api/media?project=${encodeURIComponent(state.project)}&path=${encodeURIComponent(file.path)}`,
      );
      if (sequence !== state.loadSequence || state.selected?.path !== file.path) return;
      renderMedia(info);
      return;
    }

    const data = await api(
      `/api/file?project=${encodeURIComponent(state.project)}&path=${encodeURIComponent(file.path)}`,
    );
    if (sequence !== state.loadSequence || state.selected?.path !== file.path) return;
    state.version = data.version;
    $("editor").value = data.content;
    $("editor").disabled = !data.writable;
    $("editMode").disabled = !data.writable;
    setView("preview");
    setMessage(data.writable ? "已载入，可切换到编辑模式。" : "受保护文件：只读", data.writable ? "neutral" : "warning");
  } catch (error) {
    if (sequence === state.loadSequence) setMessage(error.message, "danger");
  }
}

function renderLifecycle(lifecycle) {
  const rows = Object.entries(lifecycle || {}).map(([axis, values]) => {
    const row = document.createElement("div");
    const title = document.createElement("div");
    const label = document.createElement("b");
    const dot = document.createElement("span");
    const summary = document.createElement("span");
    row.className = "lifecycle-row";
    row.dataset.tone = toneFor(values);
    title.className = "lifecycle-title";
    dot.className = "status-dot";
    label.textContent = AXIS_LABELS[axis] || axis;
    summary.textContent =
      Object.entries(values)
        .map(([name, count]) => `${STATE_LABELS[name] || name} ${count}`)
        .join(" · ") || "—";
    title.append(dot, label);
    row.append(title, summary);
    return row;
  });
  $("lifecycle").replaceChildren(...rows);
}

function summaryCard(label, value, detail, tone) {
  const card = document.createElement("div");
  const top = document.createElement("span");
  const main = document.createElement("strong");
  const note = document.createElement("small");
  card.className = "summary-card";
  card.dataset.tone = tone;
  top.textContent = label;
  main.textContent = value;
  note.textContent = detail;
  card.append(top, main, note);
  return card;
}

function renderStatus(status) {
  $("projectTitle").textContent = status.title || "未命名项目";
  $("projectPath").textContent = state.projectPath;
  $("axisCount").textContent = `${Object.keys(status.lifecycle || {}).length} 个状态轴`;
  const recovery = status.recovery || {};
  const blocked = status.lifecycle?.delivery_gate?.blocked || 0;
  const pending = status.lifecycle?.creator_acceptance?.pending || 0;
  $("summary").replaceChildren(
    summaryCard(
      "当前检查点",
      CHECKPOINT_LABELS[status.current_checkpoint] || status.current_checkpoint || "—",
      "工作流当前位置",
      "info",
    ),
    summaryCard(
      "项目恢复",
      recovery.needed ? "需要处理" : "状态正常",
      `${recovery.transaction_counts?.complete || 0} 个事务完成`,
      recovery.needed ? "danger" : "success",
    ),
    summaryCard(
      "交付状态",
      blocked ? `${blocked} 项阻塞` : "可以进入交付",
      pending ? `${pending} 项等待创作者确认` : "没有待确认候选",
      blocked ? "danger" : "success",
    ),
  );
  renderLifecycle(status.lifecycle);
}

async function selectProject(id, preferredPath = "") {
  if (!warnLeave()) {
    $("projects").value = state.project;
    return;
  }
  const sequence = ++state.loadSequence;
  cleanupMedia();
  state.project = id;
  state.projectPath = $("projects").selectedOptions[0]?.dataset.path || "";
  state.selected = null;
  setDirty(false);
  setMessage("正在读取项目…");
  try {
    const [tree, status] = await Promise.all([
      api(`/api/tree?project=${encodeURIComponent(id)}`),
      api(`/api/status?project=${encodeURIComponent(id)}`),
    ]);
    if (sequence !== state.loadSequence) return;
    state.files = flatten(tree.tree);
    $("warnings").textContent = tree.warnings.join("\n");
    renderDomainCounts();
    renderFiles();
    renderStatus(status);
    const selectedOption = $("projects").selectedOptions[0];
    if (selectedOption) selectedOption.textContent = status.title || state.projectPath;
    const initial =
      state.files.find((file) => file.path === preferredPath) ||
      state.files.find((file) => file.path.toLowerCase() === "readme.md") ||
      state.files.find((file) => domainOf(file.path, file.type) === "text");
    if (initial) {
      await openFile(initial);
    } else {
      setMessage("项目中没有可预览文件。", "warning");
    }
  } catch (error) {
    if (sequence === state.loadSequence) setMessage(error.message, "danger");
  }
}

async function save() {
  if (!state.dirty || !state.selected) return;
  try {
    const content = $("editor").value;
    validateStructuredText(state.selected.path, content);
    const result = await api(
      `/api/file?project=${encodeURIComponent(state.project)}&path=${encodeURIComponent(state.selected.path)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, expectedVersion: state.version }),
      },
    );
    state.version = result.version;
    state.selected.size = new TextEncoder().encode(content).length;
    setDirty(false);
    renderFiles();
    setMessage(`已保存 · ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`, "success");
  } catch (error) {
    setMessage(error.message, "danger");
  }
}

async function boot() {
  try {
    const data = await api("/api/projects");
    $("warnings").textContent = data.warnings.join("\n");
    const options = data.projects.map((project) => {
      const option = document.createElement("option");
      option.value = project.id;
      option.dataset.path = project.path;
      option.textContent = project.path;
      return option;
    });
    $("projects").replaceChildren(...options);
    if (data.projects.length) {
      await selectProject(data.projects[0].id);
    } else {
      $("projectTitle").textContent = "没有发现项目";
      setMessage("工作区内没有 short-drama.json", "warning");
    }
  } catch (error) {
    setMessage(error.message, "danger");
  }
}

$("projects").onchange = (event) => selectProject(event.target.value);
$("search").oninput = renderFiles;
$("editor").oninput = () => setDirty(true);
$("save").onclick = save;
$("refresh").onclick = () => selectProject(state.project, state.selected?.path || "");

document.querySelectorAll(".domain").forEach((button) => {
  button.onclick = () => {
    document.querySelectorAll(".domain").forEach((item) => {
      item.classList.toggle("active", item === button);
      item.setAttribute("aria-pressed", String(item === button));
    });
    renderFiles();
  };
});

$("editMode").onclick = () => setView("edit");
$("previewMode").onclick = () => setView("preview");

addEventListener("beforeunload", (event) => {
  if (state.dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});
addEventListener("pagehide", cleanupMedia);
addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  if ((event.ctrlKey || event.metaKey) && key === "s") {
    event.preventDefault();
    save();
  } else if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    $("search").focus();
  } else if (event.key === "Escape" && document.activeElement === $("search")) {
    $("search").value = "";
    renderFiles();
    $("search").blur();
  }
});

boot();
