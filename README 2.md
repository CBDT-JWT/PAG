# 公众号论文写作工具

基于 Flask 和 OpenAI 标准接口的论文公众号文章生成工具。

## 启动

推荐使用 Python 3.12：

```bash
python3.12 -m venv .venv312
.venv312/bin/pip install -r requirements.txt
PORT=5001 .venv312/bin/python app.py
```

打开：

```text
http://127.0.0.1:5001
```

`.env` 支持：

```text
API_KEY="..."
API_URL="https://api.deepseek.com"
MODEL="deepseek-v4-pro"
PUBLIC_BASE_URL="http://你的公网域名或IP:5001"
```

如果没有设置 `PUBLIC_BASE_URL`，应用会优先使用本机局域网 IP 生成图片链接，方便粘贴到微信公众平台时让图片可被其他机器访问。

## 功能

- URL 输入：自动下载论文 PDF，优先支持 arXiv `abs` 链接和直接 PDF 链接。
- PDF 输入：保存上传的 PDF 到 `public/runs/<本次项目>/`。
- 左侧渲染 PDF，右侧渲染微信公众号富文本预览。
- 调用大模型生成论文标题、项目地址、论文地址和公众号文章。
- 使用 tool call 提供联网搜索和网页抓取工具给模型。
- 图片占位符渲染为红色可点击区域，点击后可在左侧 PDF 中框选截图。
- 截图保存到本次项目目录，并自动替换富文本中的图片占位符。
- 复制按钮会写入 `text/html` 和 `text/plain`，可直接粘贴到微信公众平台。
