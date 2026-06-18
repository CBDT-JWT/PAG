import * as pdfjsLib from "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.min.mjs";
console.log("app.js loaded");
pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.worker.min.mjs";
const form = document.getElementById("paperForm");
const generateBtn = document.getElementById("generateBtn");
const copyBtn = document.getElementById("copyBtn");
const copySource = document.getElementById("copySource");
const statusLine = document.getElementById("statusLine");
const progressLabel = document.getElementById("progressLabel");
const progressPercent = document.getElementById("progressPercent");
const progressBar = document.getElementById("progressBar");
const progressLog = document.getElementById("progressLog");
const copyStatus = document.getElementById("copyStatus");
const iteratePrompt = document.getElementById("iteratePrompt");
const iterateBtn = document.getElementById("iterateBtn");
const iterateStatus = document.getElementById("iterateStatus");
const selectionStatus = document.getElementById("selectionStatus");
const historySelect = document.getElementById("historySelect");
const refreshHistory = document.getElementById("refreshHistory");
const imageMenu = document.getElementById("imageMenu");
const imageMenuTitle = document.getElementById("imageMenuTitle");
const localImageInput = document.getElementById("localImageInput");
const paperUrl = document.getElementById("paperUrl");
const paperPdf = document.getElementById("paperPdf");
const pdfStage = document.getElementById("pdfStage");
const pdfCanvas = document.getElementById("pdfCanvas");
const selectionBox = document.getElementById("selectionBox");
const emptyState = document.querySelector(".empty-state");
const shotModal = document.getElementById("shotModal");
const saveShot = document.getElementById("saveShot");
const generatedTitle = document.getElementById("generatedTitle");
const generatedQuestion = document.getElementById("generatedQuestion");
const generatedTitleOptions = document.getElementById("generatedTitleOptions");
const dialogModal = document.getElementById("dialogModal");
const dialogTitle = document.getElementById("dialogTitle");
const dialogMessage = document.getElementById("dialogMessage");
const dialogCancel = document.getElementById("dialogCancel");
const dialogConfirm = document.getElementById("dialogConfirm");
const presetSelect = document.getElementById("presetSelect");
const newPresetBtn = document.getElementById("newPresetBtn");
const editPresetBtn = document.getElementById("editPresetBtn");
const presetStudio = document.getElementById("presetStudio");
const studioTitle = document.getElementById("studioTitle");
const studioCancel = document.getElementById("studioCancel");
const studioSave = document.getElementById("studioSave");
const presetPreview = document.getElementById("presetPreview");
const refreshPresetPreview = document.getElementById("refreshPresetPreview");
const presetImageInput = document.getElementById("presetImageInput");
const uploadHeadImageBtn = document.getElementById("uploadHeadImageBtn");
const uploadTailImageBtn = document.getElementById("uploadTailImageBtn");

// const generateBtn = document.getElementById("generateBtn");
// const statusLine = document.getElementById("statusLine");
// const copySource = document.getElementById("copySource");

// console.log("generateBtn =", generateBtn);

// generateBtn?.addEventListener("click", () => {
//   alert("clicked");
//   console.log("generate clicked");
//   statusLine.textContent = "按钮点击成功，JS 已经生效。";
//   copySource.innerHTML = "<p>前端 JS 已经生效。</p>";
// });

// let pdfjsLib;
let pdfDoc = null;
let currentPage = 1;
let pageCount = 0;
let scale = 1.35;
let runId = "";
let articleHtml = "";
let articleMarkdown = "";
let activePlaceholder = "";
let activeTargetUrl = "";
let shotMode = false;
let dragStart = null;
let selectedRect = null;
let selectedArticleHtml = "";
let selectedArticleText = "";
let syncTimer = null;
let syncing = false;
let syncPending = false;
let hasSuccessfulGeneration = false;
let dialogResolver = null;
let presets = [];
let presetTemplate = null;
let currentPresetDraft = null;
let presetUploadTarget = "head";
const MAX_SCREENSHOT_DATA_URL_LENGTH = 250_000;
const MAX_SCREENSHOT_SIDE = 2800;

function fallbackPresetTemplate() {
  return {
    id: `preset-${Date.now()}`,
    name: "新预设",
    prompt_hint: "",
    colors: {
      primary: "#2d6cdf",
      secondary: "#8b6b4a",
      text: "#2a2f36",
      surface: "#ffffff",
      heading_bg: "#edf3ff",
      heading_text: "#2d6cdf",
      bold: "#2d6cdf",
      left_line: "#2d6cdf",
      paper_info_bg: "#f7f3eb"
    },
    images: {
      head_url: "",
      tail_url: ""
    },
    render: {
      body_align: "justify",
      heading_align: "center",
      heading_style: "card",
      paper_info_style: "card",
      body_font_size: 14,
      heading_font_size: 16,
      line_height: 26,
      show_heading_shadow: false
    }
  };
}

function newPresetId() {
  return `preset-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function freshPresetDraft() {
  const draft = deepClone(presetTemplate || fallbackPresetTemplate());
  draft.id = newPresetId();
  draft.name = "新预设";
  draft.prompt_hint = "";
  return draft;
}

const presetFields = {
  name: document.getElementById("presetName"),
  prompt_hint: document.getElementById("presetPromptHint"),
  primary: document.getElementById("presetPrimary"),
  secondary: document.getElementById("presetSecondary"),
  text: document.getElementById("presetText"),
  surface: document.getElementById("presetSurface"),
  heading_bg: document.getElementById("presetHeadingBg"),
  heading_text: document.getElementById("presetHeadingText"),
  bold: document.getElementById("presetBold"),
  left_line: document.getElementById("presetLeftLine"),
  paper_info_bg: document.getElementById("presetPaperInfoBg"),
  body_align: document.getElementById("presetBodyAlign"),
  heading_align: document.getElementById("presetHeadingAlign"),
  heading_style: document.getElementById("presetHeadingStyle"),
  paper_info_style: document.getElementById("presetPaperInfoStyle"),
  body_font_size: document.getElementById("presetBodyFontSize"),
  heading_font_size: document.getElementById("presetHeadingFontSize"),
  line_height: document.getElementById("presetLineHeight"),
  head_url: document.getElementById("presetHeadUrl"),
  tail_url: document.getElementById("presetTailUrl")
};

async function loadPdfJs() {
  if (pdfjsLib) return pdfjsLib;
  pdfjsLib = await import("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.min.mjs");
  pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.worker.min.mjs";
  return pdfjsLib;
}

function setStatus(text) {
  statusLine.textContent = text;
}

function setProgress(percent, message) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  progressBar.style.width = `${value}%`;
  progressPercent.textContent = `${value}%`;
  progressLabel.textContent = message || "处理中";
  setStatus(message || "处理中");
}

function resetProgress() {
  setProgress(0, "开始生成");
  progressLog.innerHTML = "";
}

function appendProgress(message, detail = "") {
  const item = document.createElement("p");
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  item.textContent = detail ? `${time} ${message}：${detail}` : `${time} ${message}`;
  progressLog.appendChild(item);
  progressLog.scrollTop = progressLog.scrollHeight;
}

function normalizePublicUrls(value) {
  return (value || "").replace(/https?:\/\/[^"'()\s]+\/public\//g, "/public/");
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function buildLocalPresetPreview(preset) {
  const colors = preset?.colors || {};
  const render = preset?.render || {};
  const headUrl = preset?.images?.head_url || "";
  const tailUrl = preset?.images?.tail_url || "";
  const bodyAlign = render.body_align || "justify";
  const headingAlign = render.heading_align || "center";
  const headingStyle = render.heading_style || "card";
  const paperInfoStyle = render.paper_info_style || "card";
  const bodyFontSize = Number(render.body_font_size) || 14;
  const headingFontSize = Number(render.heading_font_size) || 16;
  const lineHeight = Number(render.line_height) || 26;
  const textColor = colors.text || "#2a2f36";
  const primary = colors.primary || "#2d6cdf";
  const secondary = colors.secondary || "#8b6b4a";
  const surface = colors.surface || "#ffffff";
  const headingBg = colors.heading_bg || "#edf3ff";
  const headingText = colors.heading_text || primary;
  const boldColor = colors.bold || primary;
  const leftLine = colors.left_line || primary;
  const paperInfoBg = colors.paper_info_bg || "#f7f3eb";
  const baseTextStyle = `margin:0 10px 12px 10px;font-size:${bodyFontSize}px;line-height:${lineHeight}px;text-align:${bodyAlign};letter-spacing:.3px;color:${textColor};`;

  const headBlock = headUrl
    ? `<section style="text-align:center;margin:0 10px 12px 10px;"><img src="${headUrl}" style="display:block;margin:0 auto;max-width:90%;width:90%;height:auto;"></section>`
    : `<button class="image-placeholder" type="button">[示例头图占位]</button>`;

  const tailBlock = tailUrl
    ? `<section style="text-align:center;margin:18px 10px 0 10px;"><img src="${tailUrl}" style="display:block;margin:0 auto;max-width:90%;width:90%;height:auto;"></section>`
    : `<button class="image-placeholder" type="button">[示例尾图占位]</button>`;

  const headingBlock = (() => {
    const title = "标题样式会改变阅读节奏";
    if (headingStyle === "left-line") {
      return `<section style="margin:0 10px 12px 10px;"><p style="margin:0;padding-left:12px;border-left:4px solid ${leftLine};font-size:${headingFontSize}px;line-height:${lineHeight}px;text-align:${headingAlign};color:${headingText};font-weight:700;">${title}</p></section>`;
    }
    if (headingStyle === "plain") {
      return `<p style="margin:0 10px 12px 10px;font-size:${headingFontSize}px;line-height:${lineHeight}px;text-align:${headingAlign};color:${headingText};font-weight:700;">${title}</p>`;
    }
    return `<section style="margin:0 10px 12px 10px;"><p style="margin:0;padding:8px 14px;border-radius:12px;background:${headingBg};font-size:${headingFontSize}px;line-height:${lineHeight}px;text-align:${headingAlign};color:${headingText};font-weight:700;">${title}</p></section>`;
  })();

  const paperInfoBlock = (() => {
    const list = `
      <ul style="margin:0;padding-left:20px;list-style:disc;">
        <li style="margin-bottom:8px;"><strong>论文标题</strong><br>PreviewMA: Theme Presets for WeChat Articles</li>
        <li style="margin-bottom:8px;"><strong>项目地址</strong><br>https://example.com/project</li>
        <li><strong>论文地址</strong><br>https://arxiv.org/abs/2501.01234</li>
      </ul>
    `;
    if (paperInfoStyle === "list") {
      return `<section style="margin:0 10px 12px 10px;color:${secondary};font-size:${bodyFontSize}px;line-height:${lineHeight}px;">${list}</section>`;
    }
    return `<section style="margin:0 10px 12px 10px;padding:12px 10px;border-radius:12px;background:${paperInfoBg};color:${secondary};font-size:${bodyFontSize}px;line-height:${lineHeight}px;">${list}</section>`;
  })();

  return `
    <div class="rich_media_content js_underline_content defaultNoSetting">
      <section style="background:${surface};padding-top:4px;">
        ${headBlock}
        <p style="${baseTextStyle}">写公众号文章时，版式并不只是“把字摆上去”。一套稳定的 <strong style="color:${boldColor};">主题预设</strong>，会决定这篇内容看起来更像实验记录、像研究笔记，还是像成熟的科技媒体解读。</p>
        ${paperInfoBlock}
        <p style="${baseTextStyle}">预设不仅影响颜色，也会影响标题的节奏、强调信息的方式，以及读者第一眼看到内容时的心理预期。</p>
        ${headingBlock}
        <p style="${baseTextStyle}">如果标题更像卡片，读者会更容易把每一节当成一个明确段落来吸收。如果标题是左侧竖线或纯文字，整篇文章会更克制，也更像连续叙事。</p>
        <button class="image-placeholder" type="button">[示例配图 Figure 3 系统结构图]</button>
        <p style="${baseTextStyle}">同一句话里，<strong style="color:${boldColor};">重点术语</strong>、<strong style="color:${boldColor};">模型名称</strong>、<strong style="color:${boldColor};">实验结论</strong> 的强调方式不同，读者的视线落点也会不同。</p>
        <section style="margin:28px 10px 0 10px;padding:16px 14px;border-radius:12px;background:${paperInfoBg};">
          <p style="margin:0 0 8px 0;font-size:13px;line-height:22px;color:${secondary};font-weight:700;">留给读者的问题</p>
          <p style="margin:0;font-size:${bodyFontSize}px;line-height:${lineHeight}px;text-align:${bodyAlign};color:${textColor};">如果你经常发布技术内容，你会更偏好强风格主题，还是尽量让样式退到内容背后？</p>
        </section>
        ${tailBlock}
      </section>
    </div>
  `;
}

function applyGenerateResult(data) {
  console.log("data =", data);
  console.log("article_html length =", data.article_html?.length);
  console.log("article_html head =", data.article_html?.slice(0, 500));
  console.log("metadata =", data.metadata);
  console.log("ai_error =", data.metadata?.ai_error);
  runId = data.run_id;
  articleHtml = normalizePublicUrls(data.article_html);
  articleMarkdown = normalizePublicUrls(data.article_markdown);
  setMeta(data.metadata || {});
  if (data.metadata?.preset_id) presetSelect.value = data.metadata.preset_id;
  copySource.innerHTML = renderPlaceholders(articleHtml);
  copyBtn.disabled = false;
  iterateBtn.disabled = false;
  hasSuccessfulGeneration = true;
  generateBtn.textContent = "重新生成";
  copyStatus.textContent = "可点击红色图片占位符补图，或直接复制";
}

function currentPreset() {
  return presets.find((preset) => preset.id === presetSelect.value) || presets[0] || null;
}

function populatePresetSelect() {
  const selected = presetSelect.value;
  presetSelect.innerHTML = "";
  for (const preset of presets) {
    const option = document.createElement("option");
    option.value = preset.id;
    option.textContent = preset.name;
    presetSelect.appendChild(option);
  }
  presetSelect.value = selected && presets.some((preset) => preset.id === selected)
    ? selected
    : (presets[0]?.id || "");
}

async function loadPresets() {
  const response = await fetch("/api/runs/presets");
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "预设加载失败");
  presets = data.presets || [];
  presetTemplate = data.template || fallbackPresetTemplate();
  if (!presets.length && presetTemplate) {
    presets = [deepClone(presetTemplate)];
  }
  populatePresetSelect();
}

function fillPresetForm(preset) {
  const value = preset || presetTemplate;
  if (!value) return;
  presetFields.name.value = value.name || "";
  presetFields.prompt_hint.value = value.prompt_hint || "";
  presetFields.primary.value = value.colors?.primary || "#2d6cdf";
  presetFields.secondary.value = value.colors?.secondary || "#8b6b4a";
  presetFields.text.value = value.colors?.text || "#2a2f36";
  presetFields.surface.value = value.colors?.surface || "#ffffff";
  presetFields.heading_bg.value = value.colors?.heading_bg || "#edf3ff";
  presetFields.heading_text.value = value.colors?.heading_text || "#2d6cdf";
  presetFields.bold.value = value.colors?.bold || "#2d6cdf";
  presetFields.left_line.value = value.colors?.left_line || "#2d6cdf";
  presetFields.paper_info_bg.value = value.colors?.paper_info_bg || "#f7f3eb";
  presetFields.body_align.value = value.render?.body_align || "justify";
  presetFields.heading_align.value = value.render?.heading_align || "center";
  presetFields.heading_style.value = value.render?.heading_style || "card";
  presetFields.paper_info_style.value = value.render?.paper_info_style || "card";
  presetFields.body_font_size.value = String(value.render?.body_font_size || 14);
  presetFields.heading_font_size.value = String(value.render?.heading_font_size || 16);
  presetFields.line_height.value = String(value.render?.line_height || 26);
  presetFields.head_url.value = value.images?.head_url || "";
  presetFields.tail_url.value = value.images?.tail_url || "";
}

function collectPresetForm() {
  return {
    id: currentPresetDraft?.id || presetTemplate?.id,
    name: presetFields.name.value.trim() || "未命名预设",
    prompt_hint: presetFields.prompt_hint.value.trim(),
    colors: {
      primary: presetFields.primary.value,
      secondary: presetFields.secondary.value,
      text: presetFields.text.value,
      surface: presetFields.surface.value,
      heading_bg: presetFields.heading_bg.value,
      heading_text: presetFields.heading_text.value,
      bold: presetFields.bold.value,
      left_line: presetFields.left_line.value,
      paper_info_bg: presetFields.paper_info_bg.value
    },
    images: {
      head_url: presetFields.head_url.value.trim(),
      tail_url: presetFields.tail_url.value.trim()
    },
    render: {
      body_align: presetFields.body_align.value,
      heading_align: presetFields.heading_align.value,
      heading_style: presetFields.heading_style.value,
      paper_info_style: presetFields.paper_info_style.value,
      body_font_size: Number(presetFields.body_font_size.value) || 14,
      heading_font_size: Number(presetFields.heading_font_size.value) || 16,
      line_height: Number(presetFields.line_height.value) || 26,
      show_heading_shadow: false
    }
  };
}

async function refreshPresetPreviewHtml() {
  currentPresetDraft = collectPresetForm();
  try {
    const response = await fetch("/api/runs/presets/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentPresetDraft)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "预设预览失败");
    const html = data.html || "";
    presetPreview.innerHTML = html ? renderPlaceholders(html) : buildLocalPresetPreview(currentPresetDraft);
  } catch (error) {
    presetPreview.innerHTML = buildLocalPresetPreview(currentPresetDraft);
    setStatus(error.message || "预设预览失败，已切换到本地示例预览");
  }
}

async function openPresetStudio(mode) {
  const existing = currentPreset();
  currentPresetDraft = mode === "new" ? freshPresetDraft() : deepClone(existing || freshPresetDraft());
  if (!currentPresetDraft) return;
  studioTitle.textContent = mode === "new" || !existing ? "新建主题预设" : `修改预设：${currentPresetDraft.name}`;
  fillPresetForm(currentPresetDraft);
  presetStudio.hidden = false;
  await refreshPresetPreviewHtml();
}

async function savePresetFromStudio() {
  const body = collectPresetForm();
  const response = await fetch("/api/runs/presets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "预设保存失败");
  const savedId = data.preset?.id || body.id;
  await loadPresets();
  presetSelect.value = savedId || presetSelect.value;
  presetStudio.hidden = true;
  currentPresetDraft = null;
  setStatus(`预设已保存：${data.preset?.name || body.name}`);
  if (runId) {
    await applyPresetToRun(savedId);
  }
}

async function persistCurrentPresetDraft() {
  if (!currentPresetDraft?.id) return null;
  const body = collectPresetForm();
  const response = await fetch("/api/runs/presets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "预设自动保存失败");
  currentPresetDraft = data.preset || body;
  await loadPresets();
  presetSelect.value = currentPresetDraft.id || presetSelect.value;
  return currentPresetDraft;
}

async function uploadPresetImage(kind) {
  presetUploadTarget = kind;
  presetImageInput.click();
}

async function applyPresetToRun(presetId) {
  if (!runId || !presetId) return;
  const response = await fetch(`/api/runs/${runId}/preset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preset_id: presetId })
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "切换预设失败");
  articleHtml = data.article_html || articleHtml;
  articleMarkdown = data.article_markdown || articleMarkdown;
  if (data.metadata) setMeta(data.metadata);
  copySource.innerHTML = renderPlaceholders(articleHtml);
  copyStatus.textContent = "已切换主题预设";
  setStatus(`已切换预设：${data.metadata?.preset_name || presetId}`);
}

function openDialog({ title = "提示", message = "", confirmText = "确定", cancelText = "取消", hideCancel = false }) {
  dialogTitle.textContent = title;
  dialogMessage.textContent = message;
  dialogConfirm.textContent = confirmText;
  dialogCancel.textContent = cancelText;
  dialogCancel.hidden = hideCancel;
  dialogModal.hidden = false;
  return new Promise((resolve) => {
    dialogResolver = resolve;
  });
}

function closeDialog(result) {
  dialogModal.hidden = true;
  if (dialogResolver) {
    const resolve = dialogResolver;
    dialogResolver = null;
    resolve(result);
  }
}

function countUnreplacedImages() {
  return copySource.querySelectorAll(".image-placeholder").length;
}

function renderTitleOptions(titles = [], activeTitle = "") {
  generatedTitleOptions.innerHTML = "";
  const normalized = [];
  for (const value of titles || []) {
    const text = String(value || "").trim();
    if (text && !normalized.includes(text)) normalized.push(text);
  }
  if (activeTitle && !normalized.includes(activeTitle)) normalized.unshift(activeTitle);
  normalized
    .filter((title) => title !== activeTitle)
    .forEach((title) => {
      const item = document.createElement("span");
      item.className = "title-option";
      item.textContent = title;
      generatedTitleOptions.appendChild(item);
    });
}

async function loadHistory() {
  const response = await fetch("/api/runs/history");
  const data = await response.json();
  const current = runId;
  historySelect.innerHTML = '<option value="">选择历史记录</option>';
  for (const item of data.runs || []) {
    const option = document.createElement("option");
    option.value = item.run_id;
    option.textContent = `${item.created_at} · ${item.paper_title}`;
    option.title = item.paper_title;
    historySelect.appendChild(option);
  }
  historySelect.value = current;
}

async function loadRun(selectedRunId) {
  const response = await fetch(`/api/runs/${selectedRunId}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "历史记录加载失败");
  applyGenerateResult(data);
  clearArticleSelection();
  if (data.pdf_url) {
    await renderPdf(data.pdf_url);
  } else {
    pdfDoc = null;
    pdfCanvas.style.display = "none";
    emptyState.style.display = "block";
    document.getElementById("pageNum").textContent = "0";
    document.getElementById("pageCount").textContent = "0";
  }
  setProgress(100, `已加载历史记录：${data.metadata?.paper_title || selectedRunId}`);
}

async function readProgressStream(response) {
  if (!response.body) {
    throw new Error("当前浏览器不支持流式读取");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalData = null;

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split(/\n\n+/);
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const dataLines = rawEvent
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim());
      if (!dataLines.length) continue;
      const payload = dataLines.join("\n");
      if (payload === "[DONE]") continue;
      handleStreamEvent(JSON.parse(payload));
    }

    if (done) break;
  }

  const trailing = buffer.trim();
  if (trailing) {
    const payload = trailing
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("\n");
    if (payload && payload !== "[DONE]") {
      handleStreamEvent(JSON.parse(payload));
    }
  }

  if (!finalData) {
    throw new Error("生成结束但没有收到结果");
  }
  return finalData;

  function handleStreamEvent(event) {
    if (event.type === "progress") {
      setProgress(event.percent, event.message);
      appendProgress(event.message, event.detail || "");
      if (event.metadata) setMeta(event.metadata);
    } else if (event.type === "heartbeat") {
      appendProgress(event.message || "仍在处理中");
    } else if (event.type === "done") {
      finalData = event.data;
    } else if (event.type === "error") {
      throw new Error(event.message || "生成失败");
    }
  }
}

function syncSourceMode() {
  const mode = new FormData(form).get("source_type");
  paperUrl.style.display = mode === "url" ? "block" : "none";
  paperPdf.style.display = mode === "pdf" ? "block" : "none";
}

function setMeta(meta) {
  const titleRow = document.getElementById("metaTitleRow");
  const projectRow = document.getElementById("metaProjectRow");
  const paperRow = document.getElementById("metaPaperRow");
  document.getElementById("metaTitle").textContent = meta.paper_title || "";
  const project = document.getElementById("metaProject");
  const paper = document.getElementById("metaPaper");
  project.textContent = meta.project_url || "";
  project.href = meta.project_url || "#";
  paper.textContent = meta.paper_url || "";
  paper.href = meta.paper_url || "#";
  titleRow.hidden = !meta.paper_title;
  projectRow.hidden = !meta.project_url;
  paperRow.hidden = !meta.paper_url;
  generatedTitle.textContent = meta.article_title || "未生成独立标题";
  generatedQuestion.textContent = meta.reader_question || "未生成结尾提问";
  renderTitleOptions(meta.article_titles || [], meta.article_title || "");
}

function renderPlaceholders(rawHtml) {
  return rawHtml.replace(/\[\[IMAGE:([^\]]+)\]\]/g, (full, label) => {
    const escapedFull = full.replace(/"/g, "&quot;");
    return `<button class="image-placeholder" type="button" data-placeholder="${escapedFull}">[${label.trim()}]</button>`;
  });
}

function restoreArticleHtml() {
  const clone = copySource.cloneNode(true);
  clone.querySelectorAll(".iteration-selection").forEach((mark) => mark.replaceWith(...mark.childNodes));
  let html = clone.innerHTML;
  html = html.replace(/<button[^>]*class="[^"]*image-placeholder[^"]*"[^>]*data-placeholder="([^"]+)"[^>]*>.*?<\/button>/gims, (_, token) => {
    return token.replace(/&quot;/g, '"').replace(/&amp;/g, "&");
  });
  return html;
}

function inlineMarkdown(node) {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent || "";
  if (node.nodeType !== Node.ELEMENT_NODE) return "";
  if (node.classList.contains("iteration-selection")) {
    return Array.from(node.childNodes).map(inlineMarkdown).join("");
  }
  if (node.dataset.generatedQuestion === "true") return "";
  if (node.matches(".image-placeholder")) return node.dataset.placeholder || "";
  if (node.tagName === "IMG") {
    const src = node.getAttribute("src") || node.getAttribute("data-src") || "";
    return `![图片](${src})`;
  }
  if (node.tagName === "BR") return "\n";
  const content = Array.from(node.childNodes).map(inlineMarkdown).join("");
  if (node.tagName === "STRONG" || node.tagName === "B") return content.trim() ? `**${content}**` : "";
  return content;
}

function markdownFromPreview() {
  const lines = [];
  const walk = (node) => {
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    if (node.dataset.generatedQuestion === "true") return;
    if (node.dataset.markdownToken) {
      lines.push(node.dataset.markdownToken);
      return;
    }
    if (node.matches(".image-placeholder") || node.tagName === "IMG") {
      lines.push(inlineMarkdown(node));
      return;
    }
    if (/^H[1-6]$/.test(node.tagName) || node.dataset.markdownHeading) {
      lines.push(`## ${(node.textContent || "").trim()}`);
      return;
    }
    if (node.tagName === "P" || node.tagName === "LI") {
      const value = inlineMarkdown(node).trim();
      if (value) lines.push(node.tagName === "LI" ? `- ${value}` : value);
      return;
    }
    for (const child of node.children) walk(child);
  };
  for (const child of copySource.children) walk(child);
  return lines.filter(Boolean).join("\n\n");
}

function normalizeEditorFormatting() {
  copySource.querySelectorAll("b, strong").forEach((node) => {
    node.style.boxSizing = "border-box";
  });
}

function scheduleArticleSync() {
  if (!runId) return;
  syncPending = true;
  clearTimeout(syncTimer);
  copyStatus.textContent = "编辑待同步...";
  syncTimer = setTimeout(syncArticle, 700);
}

async function syncArticle() {
  if (!runId || syncing) return;
  syncing = true;
  syncPending = false;
  articleHtml = restoreArticleHtml();
  articleMarkdown = markdownFromPreview();
  try {
    const response = await fetch(`/api/runs/${runId}/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ article_html: articleHtml, article_markdown: articleMarkdown })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "同步失败");
    copyStatus.textContent = "编辑已自动同步";
  } catch (error) {
    copyStatus.textContent = error.message || "自动同步失败";
  } finally {
    syncing = false;
    if (syncPending) scheduleArticleSync();
  }
}

async function renderPdf(url) {
  const lib = await loadPdfJs();
  pdfDoc = await lib.getDocument(url).promise;
  pageCount = pdfDoc.numPages;
  currentPage = 1;
  document.getElementById("pageCount").textContent = String(pageCount);
  await renderPage();
}

async function renderPage() {
  if (!pdfDoc) return;
  const page = await pdfDoc.getPage(currentPage);
  const viewport = page.getViewport({ scale });
  const context = pdfCanvas.getContext("2d");
  pdfCanvas.width = viewport.width;
  pdfCanvas.height = viewport.height;
  pdfCanvas.style.display = "block";
  emptyState.style.display = "none";
  await page.render({ canvasContext: context, viewport }).promise;
  document.getElementById("pageNum").textContent = String(currentPage);
}

async function copyRichText() {
  const pendingImages = countUnreplacedImages();
  if (pendingImages > 0) {
    await openDialog({
      title: "还有图片未替换",
      message: `当前还有 ${pendingImages} 张图片没有替换，补图后再复制会更完整。`,
      confirmText: "我知道了",
      hideCancel: true
    });
    return;
  }
  const html = getCopyHtml();
  const text = copySource.innerText;
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/html": new Blob([html], { type: "text/html" }),
          "text/plain": new Blob([text], { type: "text/plain" })
        })
      ]);
    } else {
      const range = document.createRange();
      range.selectNodeContents(copySource);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand("copy");
    }
    copyStatus.textContent = "已复制，可粘贴到微信公众平台";
  } catch (error) {
    const range = document.createRange();
    range.selectNodeContents(copySource);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    copyStatus.textContent = "浏览器限制复制，正文已选中，请按 Cmd+C";
  }
}

function absoluteUrl(value) {
  if (!value || value.startsWith("data:")) return value;
  try {
    return new URL(value, window.location.origin).href;
  } catch (error) {
    return value;
  }
}

function getCopyHtml() {
  const clone = copySource.cloneNode(true);
  clone.querySelectorAll(".iteration-selection").forEach((mark) => mark.replaceWith(...mark.childNodes));
  clone.querySelectorAll("img").forEach((img) => {
    const src = absoluteUrl(img.getAttribute("src") || img.getAttribute("data-src") || "");
    if (src) {
      img.setAttribute("src", src);
      img.setAttribute("data-src", src);
    }
  });
  clone.querySelectorAll("a[href]").forEach((link) => {
    link.setAttribute("href", absoluteUrl(link.getAttribute("href")));
  });
  return clone.innerHTML;
}

function getSelectionHtml(range) {
  const fragment = range.cloneContents();
  const container = document.createElement("div");
  container.appendChild(fragment);
  return container.innerHTML;
}

function clearArticleSelection() {
  copySource.querySelectorAll(".iteration-selection").forEach((mark) => mark.replaceWith(...mark.childNodes));
  selectedArticleHtml = "";
  selectedArticleText = "";
  selectionStatus.textContent = "未选择局部";
}

function updateArticleSelection() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
    return;
  }
  const range = selection.getRangeAt(0);
  if (!copySource.contains(range.commonAncestorContainer)) {
    return;
  }
  selectedArticleHtml = getSelectionHtml(range);
  selectedArticleText = selection.toString();
  const size = selectedArticleText.trim().length;
  selectionStatus.textContent = size ? `已选择 ${size} 字` : "未选择局部";
  if (size) {
    const mark = document.createElement("mark");
    mark.className = "iteration-selection";
    mark.appendChild(range.extractContents());
    range.insertNode(mark);
    const activeRange = document.createRange();
    activeRange.selectNodeContents(mark);
    selection.removeAllRanges();
    selection.addRange(activeRange);
  }
}

function canvasPointFromEvent(event) {
  const canvasRect = pdfCanvas.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(event.clientX - canvasRect.left, canvasRect.width)),
    y: Math.max(0, Math.min(event.clientY - canvasRect.top, canvasRect.height)),
    canvasLeft: canvasRect.left,
    canvasTop: canvasRect.top
  };
}

function drawSelection(a, b) {
  const stageRect = pdfStage.getBoundingClientRect();
  const left = Math.min(a.x, b.x) + a.canvasLeft - stageRect.left + pdfStage.scrollLeft;
  const top = Math.min(a.y, b.y) + a.canvasTop - stageRect.top + pdfStage.scrollTop;
  const width = Math.abs(a.x - b.x);
  const height = Math.abs(a.y - b.y);
  selectionBox.style.display = "block";
  selectionBox.style.left = `${left}px`;
  selectionBox.style.top = `${top}px`;
  selectionBox.style.width = `${width}px`;
  selectionBox.style.height = `${height}px`;
  selectedRect = { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), width, height };
  saveShot.disabled = width <= 0 || height <= 0;
}

async function cropSelection() {
  const page = await pdfDoc.getPage(currentPage);
  const displayRect = pdfCanvas.getBoundingClientRect();
  const exportScale = Math.max(3, scale * 3);
  const exportViewport = page.getViewport({ scale: exportScale });
  const sourceCanvas = document.createElement("canvas");
  sourceCanvas.width = Math.ceil(exportViewport.width);
  sourceCanvas.height = Math.ceil(exportViewport.height);
  await page.render({
    canvasContext: sourceCanvas.getContext("2d"),
    viewport: exportViewport
  }).promise;

  const ratioX = sourceCanvas.width / displayRect.width;
  const ratioY = sourceCanvas.height / displayRect.height;
  const sourceX = Math.round(selectedRect.x * ratioX);
  const sourceY = Math.round(selectedRect.y * ratioY);
  const sourceWidth = Math.round(selectedRect.width * ratioX);
  const sourceHeight = Math.round(selectedRect.height * ratioY);
  const crop = document.createElement("canvas");
  crop.width = sourceWidth;
  crop.height = sourceHeight;
  crop.getContext("2d").drawImage(
    sourceCanvas,
    sourceX,
    sourceY,
    sourceWidth,
    sourceHeight,
    0,
    0,
    sourceWidth,
    sourceHeight
  );
  return canvasToCompressedImage(crop);
}

function canvasToCompressedImage(canvas) {
  let maxSide = MAX_SCREENSHOT_SIDE;
  let bestDataUrl = "";

  while (maxSide >= 240) {
    const candidate = downscaleCanvas(canvas, maxSide);
    for (const quality of [.85, .75, .65, .55, .45, .35, .28, .22, .16]) {
      const dataUrl = candidate.toDataURL("image/jpeg", quality);
      if (dataUrl.length <= MAX_SCREENSHOT_DATA_URL_LENGTH) {
        return dataUrl;
      }
      bestDataUrl = dataUrl;
    }
    maxSide = Math.floor(maxSide * .72);
  }

  return bestDataUrl;
}

function downscaleCanvas(canvas, maxSide) {
  const largestSide = Math.max(canvas.width, canvas.height);
  if (largestSide <= maxSide) return canvas;

  const ratio = maxSide / largestSide;
  const target = document.createElement("canvas");
  target.width = Math.max(1, Math.round(canvas.width * ratio));
  target.height = Math.max(1, Math.round(canvas.height * ratio));
  const context = target.getContext("2d");
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(canvas, 0, 0, target.width, target.height);
  return target;
}

form.addEventListener("change", syncSourceMode);
syncSourceMode();
loadHistory().catch(() => {});
loadPresets().catch((error) => {
  presetTemplate = fallbackPresetTemplate();
  presets = [deepClone(presetTemplate)];
  populatePresetSelect();
  setStatus(error.message || "预设加载失败，已使用本地默认模板");
});

dialogCancel.addEventListener("click", () => closeDialog(false));
dialogConfirm.addEventListener("click", () => closeDialog(true));
dialogModal.addEventListener("click", (event) => {
  if (event.target === dialogModal) closeDialog(false);
});

refreshHistory.addEventListener("click", () => loadHistory().catch((error) => setStatus(error.message)));
newPresetBtn.addEventListener("click", () => openPresetStudio("new").catch((error) => setStatus(error.message)));
editPresetBtn.addEventListener("click", () => openPresetStudio("edit").catch((error) => setStatus(error.message)));
studioCancel.addEventListener("click", () => {
  presetStudio.hidden = true;
  currentPresetDraft = null;
});
studioSave.addEventListener("click", () => savePresetFromStudio().catch((error) => setStatus(error.message)));
refreshPresetPreview.addEventListener("click", () => refreshPresetPreviewHtml().catch((error) => setStatus(error.message)));
Object.values(presetFields).forEach((element) => {
  element.addEventListener("input", () => {
    if (!presetStudio.hidden) refreshPresetPreviewHtml().catch(() => {});
  });
});
uploadHeadImageBtn.addEventListener("click", () => uploadPresetImage("head"));
uploadTailImageBtn.addEventListener("click", () => uploadPresetImage("tail"));
presetImageInput.addEventListener("change", async () => {
  const file = presetImageInput.files?.[0];
  if (!file) return;
  const body = new FormData();
  body.append("image", file);
  body.append("prefix", presetUploadTarget);
  try {
    const response = await fetch("/api/runs/presets/assets", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "预设图片上传失败");
    if (presetUploadTarget === "head") presetFields.head_url.value = data.url || "";
    if (presetUploadTarget === "tail") presetFields.tail_url.value = data.url || "";
    currentPresetDraft = collectPresetForm();
    await persistCurrentPresetDraft();
    await refreshPresetPreviewHtml();
    if (runId && presetSelect.value) {
      await applyPresetToRun(presetSelect.value);
    }
    setStatus(presetUploadTarget === "head" ? "文首图已上传并保存到当前预设" : "文末图已上传并保存到当前预设");
  } catch (error) {
    setStatus(error.message || "预设图片上传失败");
  } finally {
    presetImageInput.value = "";
  }
});
presetSelect.addEventListener("change", async () => {
  if (!runId) return;
  try {
    await applyPresetToRun(presetSelect.value);
  } catch (error) {
    setStatus(error.message || "切换预设失败");
  }
});
historySelect.addEventListener("change", async () => {
  if (!historySelect.value) return;
  try {
    await loadRun(historySelect.value);
  } catch (error) {
    setStatus(error.message || "历史记录加载失败");
  }
});

copySource.addEventListener("input", scheduleArticleSync);
document.querySelectorAll(".editor-tools button").forEach((button) => {
  button.addEventListener("mousedown", (event) => event.preventDefault());
  button.addEventListener("click", () => {
    copySource.focus();
    if (button.dataset.action === "image") {
      const token = `[[IMAGE:新增图片-${Date.now()}]]`;
      document.execCommand(
        "insertHTML",
        false,
        `<button class="image-placeholder" type="button" data-placeholder="${token}">[新增图片]</button>`
      );
      activePlaceholder = token;
      activeTargetUrl = "";
      articleMarkdown = markdownFromPreview();
      imageMenuTitle.textContent = "添加图片";
      imageMenu.hidden = false;
    } else if (button.dataset.command) {
      document.execCommand(button.dataset.command, false);
      normalizeEditorFormatting();
    } else if (button.dataset.block) {
      document.execCommand("formatBlock", false, button.dataset.block);
    }
    scheduleArticleSync();
  });
});

async function runGeneration() {
  generateBtn.disabled = true;
  copyBtn.disabled = true;
  iterateBtn.disabled = true;
  copySource.innerHTML = "";
  selectedArticleHtml = "";
  selectedArticleText = "";
  selectionStatus.textContent = "未选择局部";
  resetProgress();
  appendProgress("正在提交生成请求");
  const body = new FormData(form);
  try {
    const response = await fetch("/api/generate/stream", { method: "POST", body });
    if (!response.ok) throw new Error("生成请求失败");
    const data = await readProgressStream(response);
    applyGenerateResult(data);
    await renderPdf(data.pdf_url);
    await loadHistory();
    const doneMessage = data.metadata?.ai_error ? `已生成，但 AI 有降级：${data.metadata.ai_error}` : `已生成，本次资料目录：public/runs/${runId}`;
    setProgress(100, doneMessage);
    appendProgress("预览加载完成");
  } catch (error) {
    setProgress(0, "生成失败");
    appendProgress("生成失败", error.message);
    setStatus(error.message);
    const shouldRetry = await openDialog({
      title: "生成失败",
      message: `生成失败，报错内容为：${error.message || "未知错误"}\n疑似模型输出内容有误，点击重新生成。`,
      confirmText: "重新生成",
      cancelText: "取消"
    });
    if (shouldRetry) {
      runGeneration();
    }
  } finally {
    generateBtn.disabled = false;
  }
}

generateBtn.addEventListener("click", async () => {
  if (hasSuccessfulGeneration) {
    const confirmed = await openDialog({
      title: "是否确定重新生成",
      message: "重新生成后无法找回上一次生成内容。",
      confirmText: "重新生成",
      cancelText: "取消"
    });
    if (!confirmed) return;
  }
  runGeneration();
});

copyBtn.addEventListener("click", copyRichText);
copySource.addEventListener("mousedown", clearArticleSelection);
copySource.addEventListener("mouseup", updateArticleSelection);
copySource.addEventListener("keyup", updateArticleSelection);

iterateBtn.addEventListener("click", async () => {
  const prompt = iteratePrompt.value.trim();
  if (!prompt || !runId) return;

  iterateBtn.disabled = true;
  iterateStatus.textContent = selectedArticleText ? "正在按选区局部修改..." : "正在按要求迭代全文...";
  try {
    const response = await fetch(`/api/runs/${runId}/iterate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        article_markdown: articleMarkdown,
        selected_text: selectedArticleText
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "迭代修改失败");
    articleHtml = data.article_html || "";
    articleMarkdown = data.article_markdown || "";
    if (data.metadata) setMeta(data.metadata);
    copySource.innerHTML = renderPlaceholders(articleHtml);
    selectedArticleHtml = "";
    selectedArticleText = "";
    selectionStatus.textContent = "未选择局部";
    iterateStatus.textContent = "已应用修改";
    copyStatus.textContent = "迭代修改已更新，可继续编辑或复制";
  } catch (error) {
    iterateStatus.textContent = error.message || "迭代修改失败";
  } finally {
    iterateBtn.disabled = !runId;
  }
});

document.getElementById("prevPage").addEventListener("click", async () => {
  if (pdfDoc && currentPage > 1) {
    currentPage -= 1;
    await renderPage();
  }
});

document.getElementById("nextPage").addEventListener("click", async () => {
  if (pdfDoc && currentPage < pageCount) {
    currentPage += 1;
    await renderPage();
  }
});

document.getElementById("zoomOut").addEventListener("click", async () => {
  scale = Math.max(.6, scale - .15);
  await renderPage();
});

document.getElementById("zoomIn").addEventListener("click", async () => {
  scale = Math.min(3, scale + .15);
  await renderPage();
});

copySource.addEventListener("click", (event) => {
  const placeholder = event.target.closest(".image-placeholder");
  const image = event.target.closest("img");
  if (!placeholder && !image) return;
  event.preventDefault();
  activePlaceholder = placeholder?.dataset.placeholder || "";
  activeTargetUrl = image?.getAttribute("src") || image?.getAttribute("data-src") || "";
  articleHtml = restoreArticleHtml();
  articleMarkdown = markdownFromPreview();
  imageMenuTitle.textContent = image ? "更换图片" : "添加图片";
  imageMenu.hidden = false;
});

document.getElementById("cancelImageMenu").addEventListener("click", () => {
  imageMenu.hidden = true;
});

document.getElementById("chooseScreenshot").addEventListener("click", () => {
  if (!pdfDoc) {
    copyStatus.textContent = "当前历史记录没有可截图的 PDF，请选择本地上传";
    imageMenu.hidden = true;
    return;
  }
  imageMenu.hidden = true;
  shotModal.hidden = false;
  shotMode = true;
  selectedRect = null;
  saveShot.disabled = true;
  selectionBox.style.display = "none";
  copyStatus.textContent = "请在中间 PDF 当前页拖拽截图区域";
});

document.getElementById("chooseUpload").addEventListener("click", () => {
  imageMenu.hidden = true;
  localImageInput.click();
});

localImageInput.addEventListener("change", async () => {
  const file = localImageInput.files?.[0];
  if (!file || !runId) return;
  const body = new FormData();
  body.append("image", file);
  body.append("placeholder", activePlaceholder);
  body.append("target_url", activeTargetUrl);
  body.append("article_html", restoreArticleHtml());
  body.append("article_markdown", articleMarkdown);
  copyStatus.textContent = "正在上传并替换图片...";
  try {
    const response = await fetch(`/api/runs/${runId}/images`, { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "图片上传失败");
    articleHtml = data.article_html || "";
    articleMarkdown = data.article_markdown || articleMarkdown;
    copySource.innerHTML = renderPlaceholders(articleHtml);
    copyStatus.textContent = "图片已上传并替换";
  } catch (error) {
    copyStatus.textContent = error.message || "图片上传失败";
  } finally {
    localImageInput.value = "";
  }
});

document.getElementById("cancelShot").addEventListener("click", () => {
  shotModal.hidden = true;
  shotMode = false;
  selectionBox.style.display = "none";
  copyStatus.textContent = "已取消截图";
});

pdfStage.addEventListener("mousedown", (event) => {
  if (!shotMode || !pdfDoc) return;
  dragStart = canvasPointFromEvent(event);
  drawSelection(dragStart, dragStart);
});

pdfStage.addEventListener("mousemove", (event) => {
  if (!shotMode || !dragStart) return;
  drawSelection(dragStart, canvasPointFromEvent(event));
});

window.addEventListener("mouseup", () => {
  dragStart = null;
});

saveShot.addEventListener("click", async () => {
  if (!selectedRect || !runId) return;
  saveShot.disabled = true;
  try {
    copyStatus.textContent = "正在生成并压缩截图到 250KB 以内...";
    const image = await cropSelection();
    const response = await fetch(`/api/runs/${runId}/screenshots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image,
        placeholder: activePlaceholder,
        target_url: activeTargetUrl,
        article_html: restoreArticleHtml(),
        article_markdown: articleMarkdown
      })
    });
    const data = await response.json();
    if (response.ok) {
      articleHtml = data.article_html;
      articleMarkdown = data.article_markdown || articleMarkdown;
      copySource.innerHTML = renderPlaceholders(articleHtml);
      shotModal.hidden = true;
      shotMode = false;
      selectionBox.style.display = "none";
      copyStatus.textContent = "截图已保存并替换到富文本";
    } else {
      copyStatus.textContent = data.error || "截图保存失败";
      saveShot.disabled = false;
    }
  } catch (error) {
    copyStatus.textContent = error.message || "截图保存失败";
    saveShot.disabled = false;
  }
});
