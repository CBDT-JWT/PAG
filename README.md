# 公众号论文写作工具

把论文 URL 或 PDF 转成可直接粘贴到微信公众号后台的中文富文本。工具会下载/展示 PDF，调用 OpenAI 兼容接口生成论文解读文章，并支持在 PDF 上框选高清截图替换正文图片占位符。

<img width="1512" height="836" alt="image" src="https://github.com/user-attachments/assets/74930148-472e-4b6b-acc8-3304cc6e500e" />

## 功能亮点

- 三栏工作台：左侧输入与进度，中间 PDF，右侧微信富文本预览。
- 支持论文 URL、arXiv `abs` 链接、直接 PDF 链接和本地 PDF 上传。
- 通过 OpenAI 兼容接口生成公众号风格论文解读。
- Agent 可按需使用联网工具检索项目地址、开源仓库、作者和相关网页。
- SSE 流式生成进度：最终富文本阶段按预计 5000 字估算进度。
- 图片占位符可点击，然后在 PDF 当前页框选高清截图替换。
- 复制按钮同时写入 `text/html` 和 `text/plain`，适合粘贴到微信公众平台。
- 每次生成结果会落盘到 `public/runs/<run_id>/`，便于回看和补图。

## 快速开始

```bash
cd /Users/weitaojiang/Documents/projects/vibe-wechat
python3.12 -m venv .venv-flask
.venv-flask/bin/pip install -r requirements.txt
.venv-flask/bin/python app.py
```

打开浏览器：

```text
http://127.0.0.1:5001
```

## 环境配置

在项目根目录创建 `.env`：

```text
API_KEY="你的 API Key"
API_URL="https://api.deepseek.com"
MODEL="deepseek-v4-pro"
```

也兼容 OpenAI 风格变量：

```text
OPENAI_API_KEY="你的 API Key"
OPENAI_BASE_URL="https://api.example.com/v1"
OPENAI_MODEL="deepseek-v4-pro"
```

如果希望复制到微信后台后的图片能被其他机器访问，建议配置公网或局域网地址：

```text
PUBLIC_BASE_URL="http://你的公网IP或局域网IP:5001"
```

未配置时，应用会尽量推断本机局域网地址。

## 可选依赖

PDF 文本提取优先使用 `pdftotext`。macOS 可安装 Poppler：

```bash
brew install poppler
```

未安装时应用仍可下载和展示 PDF，但模型主要依赖论文 URL、联网检索结果和可用上下文生成文章。

## 使用流程

1. 输入论文 URL，或切换到 PDF 上传模式。
2. 可选上传头图、尾图，并填写重点关注作者。
3. 点击「开始生成」，左侧会显示阶段日志和进度条。
4. 生成完成后，在右侧预览富文本。
5. 点击红色图片占位符，在中间 PDF 上拖拽框选图片区域。
6. 点击「保存截图」，截图会保存并替换到富文本中。
7. 点击「复制」，粘贴到微信公众号后台。

## 项目结构

```text
.
├── app.py                         # Flask 入口
├── templates/index.html           # 三栏工作台页面
├── static/app.js                  # 前端交互、SSE、PDF 渲染、截图
├── static/app.css                 # 页面样式
├── assets/head-banner.png         # 默认头图
├── public/runs/                   # 每次生成的输出目录
└── wechat_writer/
    ├── __init__.py                # create_app
    ├── agent.py                   # Agent、prompt、工具调用、流式生成
    ├── config.py                  # 路径、端口、环境变量
    ├── files.py                   # PDF 下载、文本提取、公开 URL
    ├── generation.py              # 生成流程编排
    ├── http_client.py             # HTTP / JSON / SSE 客户端
    ├── routes.py                  # Flask 路由
    └── wechat_html.py             # 微信富文本 HTML 渲染
```

## 输出文件

每次生成会写入：

```text
public/runs/<run_id>/
├── paper.pdf
├── paper_text.txt
├── metadata.json
├── article.html
├── head...
├── tail...
└── screenshot-...
```

## 说明

- 正文中的 `**加粗**` 会渲染为蓝色 `rgb(67, 117, 185)`。
- Markdown 二级标题会保持黑色。
- `[[PAPER_INFO]]` 下方会固定插入一张「论文开头部分截图」占位图。
- 截图会映射到高倍率 PDF 渲染画布上裁剪，以提升清晰度。
