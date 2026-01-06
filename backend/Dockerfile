# =============================================
# 每日新聞自動摘要系統 - 後端 Dockerfile (含 Playwright)
# =============================================
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 設定環境變數
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Taipei
ENV ENABLE_PLAYWRIGHT=true

# 安裝系統依賴（Playwright 需要的）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    # Playwright 依賴
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 複製並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 Playwright 和瀏覽器
RUN pip install playwright==1.41.0 \
    && playwright install chromium

# 複製應用程式碼
COPY . .

# 暴露端口
EXPOSE 8000

# 啟動命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
