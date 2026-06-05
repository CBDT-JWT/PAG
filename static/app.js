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
const MAX_SCREENSHOT_DATA_URL_LENGTH = 250_000;
const MAX_SCREENSHOT_SIDE = 2800;

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
  copySource.innerHTML = renderPlaceholders(articleHtml);
  copyBtn.disabled = false;
  iterateBtn.disabled = false;
  copyStatus.textContent = "可点击红色图片占位符补图，或直接复制";
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
  document.getElementById("metaTitle").textContent = meta.paper_title || "-";
  const project = document.getElementById("metaProject");
  const paper = document.getElementById("metaPaper");
  project.textContent = meta.project_url || "-";
  project.href = meta.project_url || "#";
  paper.textContent = meta.paper_url || "-";
  paper.href = meta.paper_url || "#";
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
    node.style.color = "rgb(67, 117, 185)";
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

refreshHistory.addEventListener("click", () => loadHistory().catch((error) => setStatus(error.message)));
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

generateBtn.addEventListener("click", async () => {
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
  } finally {
    generateBtn.disabled = false;
  }
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
