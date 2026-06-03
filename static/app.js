import * as pdfjsLib from "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.min.mjs";
alert("app.js loaded");
console.log("app.js loaded");
pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.worker.min.mjs";
const form = document.getElementById("paperForm");
const generateBtn = document.getElementById("generateBtn");
const copyBtn = document.getElementById("copyBtn");
const copySource = document.getElementById("copySource");
const statusLine = document.getElementById("statusLine");
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

async function loadPdfJs() {
  if (pdfjsLib) return pdfjsLib;
  pdfjsLib = await import("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.min.mjs");
  pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.worker.min.mjs";
  return pdfjsLib;
}

function setStatus(text) {
  statusLine.textContent = text;
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
  const html = copySource.innerHTML;
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
  saveShot.disabled = width < 12 || height < 12;
}

function cropSelection() {
  const ratioX = pdfCanvas.width / pdfCanvas.getBoundingClientRect().width;
  const ratioY = pdfCanvas.height / pdfCanvas.getBoundingClientRect().height;
  const crop = document.createElement("canvas");
  crop.width = Math.round(selectedRect.width * ratioX);
  crop.height = Math.round(selectedRect.height * ratioY);
  crop.getContext("2d").drawImage(
    pdfCanvas,
    Math.round(selectedRect.x * ratioX),
    Math.round(selectedRect.y * ratioY),
    crop.width,
    crop.height,
    0,
    0,
    crop.width,
    crop.height
  );
  return crop.toDataURL("image/png");
}

form.addEventListener("change", syncSourceMode);
syncSourceMode();

generateBtn.addEventListener("click", async () => {
  generateBtn.disabled = true;
  copyBtn.disabled = true;
  copySource.innerHTML = "";
  setStatus("正在创建项目目录、下载/保存论文并调用大模型...");
  const body = new FormData(form);
  try {
    const response = await fetch("/api/generate", { method: "POST", body });
    const data = await response.json();
    console.log("data =", data);
    console.log("article_html length =", data.article_html?.length);
    console.log("article_html head =", data.article_html?.slice(0, 500));
    console.log("metadata =", data.metadata);
    console.log("ai_error =", data.metadata?.ai_error);
    if (!response.ok) throw new Error(data.error || "生成失败");
    runId = data.run_id;
    articleHtml = data.article_html || "";
    setMeta(data.metadata || {});
    copySource.innerHTML = renderPlaceholders(articleHtml);
    copyBtn.disabled = false;
    await renderPdf(data.pdf_url);
    setStatus(data.metadata?.ai_error ? `已生成，但 AI 有降级：${data.metadata.ai_error}` : `已生成，本次资料目录：public/runs/${runId}`);
    copyStatus.textContent = "可点击红色图片占位符补图，或直接复制";
  } catch (error) {
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
});

document.getElementById("cancelShot").addEventListener("click", () => {
  shotModal.hidden = true;
  shotMode = false;
  selectionBox.style.display = "none";
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
  const image = cropSelection();
  articleHtml = restoreArticleHtml();
  const response = await fetch(`/api/runs/${runId}/screenshots`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image, placeholder: activePlaceholder, article_html: articleHtml })
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
});
