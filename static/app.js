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
let activePlaceholder = "";
let shotMode = false;
let dragStart = null;
let selectedRect = null;
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

function applyGenerateResult(data) {
  console.log("data =", data);
  console.log("article_html length =", data.article_html?.length);
  console.log("article_html head =", data.article_html?.slice(0, 500));
  console.log("metadata =", data.metadata);
  console.log("ai_error =", data.metadata?.ai_error);
  runId = data.run_id;
  articleHtml = data.article_html || "";
  setMeta(data.metadata || {});
  copySource.innerHTML = renderPlaceholders(articleHtml);
  copyBtn.disabled = false;
  copyStatus.textContent = "可点击红色图片占位符补图，或直接复制";
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
  let html = copySource.innerHTML;
  html = html.replace(/<button[^>]*class="[^"]*image-placeholder[^"]*"[^>]*data-placeholder="([^"]+)"[^>]*>.*?<\/button>/gims, (_, token) => {
    return token.replace(/&quot;/g, '"').replace(/&amp;/g, "&");
  });
  return html;
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

generateBtn.addEventListener("click", async () => {
  generateBtn.disabled = true;
  copyBtn.disabled = true;
  copySource.innerHTML = "";
  resetProgress();
  appendProgress("正在提交生成请求");
  const body = new FormData(form);
  try {
    const response = await fetch("/api/generate/stream", { method: "POST", body });
    if (!response.ok) throw new Error("生成请求失败");
    const data = await readProgressStream(response);
    applyGenerateResult(data);
    await renderPdf(data.pdf_url);
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
  const target = event.target.closest(".image-placeholder");
  if (!target) return;
  activePlaceholder = target.dataset.placeholder;
  shotModal.hidden = false;
  shotMode = true;
  selectedRect = null;
  saveShot.disabled = true;
  selectionBox.style.display = "none";
  copyStatus.textContent = "请在中间 PDF 当前页拖拽截图区域";
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
      body: JSON.stringify({ image, placeholder: activePlaceholder })
    });
    const data = await response.json();
    if (response.ok) {
      articleHtml = data.article_html;
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
