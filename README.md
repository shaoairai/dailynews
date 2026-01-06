# 📰 每日新聞自動摘要系統

自動抓取、摘要、寄送新聞到您的信箱。

## 功能特色

- ✅ 支援中文/英文/中英混合新聞搜尋
- ✅ 使用 Google News RSS 作為新聞來源（免費）
- ✅ 自動抓取文章正文並產生摘要
- ✅ 支援當日或自訂日期範圍
- ✅ Email 自動寄送（HTML 格式美觀郵件）
- ✅ 簡潔的網頁介面
- ✅ Docker 一鍵部署

## 專案結構

```
dailynews/
├── frontend/                 # 前端 (純 HTML/CSS/JS)
│   ├── index.html           # 主頁面
│   ├── styles.css           # 樣式表
│   ├── script.js            # 前端邏輯
│   ├── Dockerfile           # 前端 Docker 設定
│   └── nginx.conf           # Nginx 設定
│
├── backend/                  # 後端 (FastAPI)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI 主程式
│   │   ├── news_fetcher.py  # Google News RSS 抓取
│   │   ├── content_extractor.py  # 文章正文抽取
│   │   ├── summarizer.py    # 摘要產生器
│   │   └── email_sender.py  # Email 寄送
│   ├── requirements.txt     # Python 依賴
│   └── Dockerfile           # 後端 Docker 設定
│
├── docker-compose.yaml      # Docker Compose 設定
├── .env.example             # 環境變數範例
└── README.md                # 說明文件
```

## 快速開始

### 方式一：Docker Compose（推薦）

1. **複製環境變數設定**
   ```bash
   cp .env.example .env
   ```

2. **編輯 .env 檔案**，填入 SMTP 設定（詳見下方 Gmail 設定說明）

3. **啟動服務**
   ```bash
   docker-compose up --build
   ```

4. **開啟瀏覽器**
   - 前端介面：http://localhost:3000
   - 後端 API 文件：http://localhost:8000/docs

### 方式二：本機直接執行

#### 後端

```bash
cd backend

# 建立虛擬環境（建議）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安裝依賴
pip install -r requirements.txt

# 設定環境變數
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your-email@gmail.com
export SMTP_PASS=your-app-password

# 啟動服務
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端

前端是純靜態檔案，有多種方式可以開啟：

**方式 A：直接開啟 HTML（最簡單）**
```bash
# 直接用瀏覽器開啟 frontend/index.html
# 注意：需要先修改 script.js 中的 API_BASE_URL
```

**方式 B：使用 Python 簡易伺服器**
```bash
cd frontend
python -m http.server 3000
# 開啟 http://localhost:3000
```

**方式 C：使用 Node.js serve**
```bash
npx serve frontend -p 3000
```

## Gmail SMTP 設定

Gmail 需要使用「應用程式密碼」而非帳號密碼：

1. 前往 [Google 帳戶](https://myaccount.google.com/)
2. 選擇「安全性」
3. 在「登入 Google」區塊，開啟「兩步驟驗證」
4. 開啟後，回到「安全性」頁面
5. 在「兩步驟驗證」下方，點選「應用程式密碼」
6. 選擇應用程式：「郵件」，裝置：「其他」，輸入名稱如「每日新聞系統」
7. 點選「產生」，複製產生的 16 位密碼
8. 將此密碼填入 `.env` 的 `SMTP_PASS`

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=xxxx xxxx xxxx xxxx  # 16 位應用程式密碼
```

## API 文件

啟動後端後，可以透過以下方式查看 API 文件：

- Swagger UI：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

### 主要 API

#### POST /api/run

執行新聞搜尋、摘要、寄信。

**請求參數：**

```json
{
  "language": "zh-TW",       // zh-TW | en-US | both
  "keyword": "AI 法規",      // 搜尋關鍵字（必填）
  "count": 5,                // 抓取篇數 1-20
  "date_mode": "today",      // today | custom
  "start_date": "2024-01-01", // 自訂模式時必填
  "end_date": "2024-01-07",   // 自訂模式時必填
  "email": "user@example.com" // 收件人 Email
}
```

**回應範例：**

```json
{
  "success": true,
  "message": "成功處理 5 篇新聞",
  "articles": [
    {
      "title": "文章標題",
      "url": "https://...",
      "source": "來源媒體",
      "published": "2024-01-07T10:30:00+08:00",
      "language": "zh-TW",
      "summary": "文章摘要...",
      "has_full_content": true
    }
  ],
  "email_status": {
    "success": true,
    "error": null
  }
}
```

## 進階設定

### 啟用 Playwright（動態網頁支援）

部分新聞網站使用 JavaScript 渲染，需要 Playwright 支援：

1. 安裝 Playwright：
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. 設定環境變數：
   ```env
   ENABLE_PLAYWRIGHT=true
   ```

### AI 摘要（可選）

目前使用 placeholder 摘要（擷取正文前 450-600 字）。未來可整合 AI API：

**免費選項：**
- Hugging Face Inference API（免費層）
- Google Gemini API（免費層，60 次/分鐘）
- Cohere API（免費層，100 次/月）

設定方式：
```env
AI_API_URL=https://api-inference.huggingface.co/models/...
AI_API_KEY=your-api-key
```

## 技術架構

### 後端（FastAPI）

- **框架**：FastAPI（非同步、高效能）
- **新聞來源**：Google News RSS
- **正文抽取**：trafilatura
- **郵件發送**：smtplib

### 前端

- **純 HTML/CSS/JavaScript**（無框架）
- **響應式設計**
- **Nginx 靜態檔案服務 + API 反向代理**

### 流程

```
使用者輸入參數
     ↓
前端 POST /api/run
     ↓
後端抓取 Google News RSS
     ↓
過濾日期 + URL 去重
     ↓
逐篇抓取正文 (trafilatura)
     ↓
產生摘要 (placeholder / AI)
     ↓
發送 Email (SMTP)
     ↓
回傳結果給前端顯示
```

## 常見問題

### Q: 為什麼有些新聞無法取得全文？

A: 部分網站有防爬蟲機制或需要 JavaScript 渲染。系統會自動使用 RSS 摘要作為 fallback，並在介面上標示「無法取得全文」。

### Q: 郵件發送失敗怎麼辦？

A: 請檢查：
1. SMTP 設定是否正確
2. Gmail 是否已開啟兩步驟驗證
3. 是否使用應用程式密碼（非帳號密碼）
4. 收件人 Email 格式是否正確

### Q: 為什麼找不到今天的新聞？

A: 請確認：
1. 關鍵字是否太冷門
2. 時區是否正確（系統使用 Asia/Taipei）
3. 可嘗試放寬日期範圍

### Q: Docker 啟動失敗？

A: 請確認：
1. Docker 和 Docker Compose 已安裝
2. `.env` 檔案已建立（即使 SMTP 留空也需要檔案存在）
3. Port 3000 和 8000 未被占用

## 授權

MIT License

## 更新日誌

### v1.0.0 (2024-01)
- 初始版本
- 支援 Google News RSS
- 支援中英文搜尋
- 基本摘要功能
- Email 寄送功能
