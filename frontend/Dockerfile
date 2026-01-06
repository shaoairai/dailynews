# =============================================
# 每日新聞自動摘要系統 - 前端 Dockerfile
# =============================================
FROM nginx:alpine

# 複製前端檔案到 Nginx 預設目錄
COPY . /usr/share/nginx/html/

# 複製 Nginx 設定檔
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 啟動 Nginx
CMD ["nginx", "-g", "daemon off;"]
