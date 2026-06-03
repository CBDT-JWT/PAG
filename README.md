# 公众号论文写作工具

Flask Web 工具，用 `.env` 中的 OpenAI 兼容接口生成微信公众号论文解读富文本。

## 启动

```bash
cd /Users/weitaojiang/Documents/projects/vibe-wechat
python3.12 -m venv .venv-flask
.venv-flask/bin/pip install -r requirements.txt
.venv-flask/bin/python app.py
```

打开：

```text
http://127.0.0.1:5001
```

可选：为了让粘贴到微信公众平台后的图片能被其他机器访问，在 `.env` 中设置公网或局域网地址：

```text
PUBLIC_BASE_URL="http://你的公网IP或局域网IP:5001"
```

## `.env`

```text
API_KEY="..."
API_URL="https://api.deepseek.com"
MODEL="deepseek-v4-pro"
```

`MODEL` 可省略，默认使用 `deepseek-v4-pro`。

## 可选依赖

本地 PDF 文本提取会优先使用 `pdftotext`：

```bash
brew install poppler
```

未安装时仍可保存和展示 PDF，模型会基于论文 URL、联网搜索结果和可用上下文生成文章。

## 功能

- 输入论文 URL 或上传 PDF。
- 在 `public/runs/<本次项目>/` 下保存论文、头图、尾图、截图和生成结果。
- URL 输入时自动下载 PDF，支持 arXiv `abs` 链接和直接 PDF 链接。
- 左侧展示 PDF，右侧展示微信公众号富文本预览。
- 通过 OpenAI 兼容接口和 tool call 风格的联网搜索/网页读取提取标题、项目地址、论文地址。
- 生成类似示例富文本风格的公众号文章。
- 图片位置使用 `[[IMAGE:图片描述]]` 占位，前端渲染为红色可点击 `[图片描述]`。
- 点击占位符后可在左侧 PDF 当前页框选截图，图片保存到本次项目目录并替换富文本。
- 复制按钮写入 `text/html` 和 `text/plain`，可直接粘贴到微信公众平台。
