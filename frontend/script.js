/**
 * 每日新聞自動摘要系統 - 前端腳本
 */

// API 端點設定
// Docker 環境：透過 Nginx 反向代理，使用相對路徑
// 本機開發：直接連接後端，使用 http://localhost:8000
const API_BASE_URL = window.location.port === '5600' ? '' : 'http://localhost:8000';

// DOM 元素
const newsForm = document.getElementById('newsForm');
const submitBtn = document.getElementById('submitBtn');
const btnText = submitBtn.querySelector('.btn-text');
const btnLoading = submitBtn.querySelector('.btn-loading');
const dateRangeGroup = document.getElementById('dateRangeGroup');
const statusSection = document.getElementById('statusSection');
const statusCard = document.getElementById('statusCard');
const statusIcon = document.getElementById('statusIcon');
const statusMessage = document.getElementById('statusMessage');
const statusDetails = document.getElementById('statusDetails');
const resultsSection = document.getElementById('resultsSection');
const resultsSummary = document.getElementById('resultsSummary');
const articlesList = document.getElementById('articlesList');

// 日期模式切換
document.querySelectorAll('input[name="dateMode"]').forEach(radio => {
    radio.addEventListener('change', function() {
        if (this.value === 'custom') {
            dateRangeGroup.style.display = 'block';
            // 設定預設日期為今天
            const today = getTaipeiDate();
            document.getElementById('startDate').value = today;
            document.getElementById('endDate').value = today;
        } else {
            dateRangeGroup.style.display = 'none';
        }
    });
});

// 取得台北時區今日日期 (YYYY-MM-DD)
function getTaipeiDate() {
    const now = new Date();
    const taipeiTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
    const year = taipeiTime.getFullYear();
    const month = String(taipeiTime.getMonth() + 1).padStart(2, '0');
    const day = String(taipeiTime.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// 表單送出
newsForm.addEventListener('submit', async function(e) {
    e.preventDefault();

    // 收集表單資料
    const formData = {
        language: document.getElementById('language').value,
        keyword: document.getElementById('keyword').value.trim(),
        count: parseInt(document.getElementById('count').value),
        date_mode: document.querySelector('input[name="dateMode"]:checked').value,
        email: document.getElementById('email').value.trim(),
        search_mode: document.querySelector('input[name="searchMode"]:checked').value
    };

    // 如果是自訂日期範圍
    if (formData.date_mode === 'custom') {
        formData.start_date = document.getElementById('startDate').value;
        formData.end_date = document.getElementById('endDate').value;

        // 驗證日期
        if (!formData.start_date || !formData.end_date) {
            showStatus('error', '❌', '請填寫完整的日期範圍');
            return;
        }

        if (formData.start_date > formData.end_date) {
            showStatus('error', '❌', '開始日期不能晚於結束日期');
            return;
        }
    }

    // 驗證關鍵字
    if (!formData.keyword) {
        showStatus('error', '❌', '請輸入搜尋關鍵字');
        return;
    }

    // 驗證 Email
    if (!validateEmail(formData.email)) {
        showStatus('error', '❌', '請輸入有效的 Email 地址');
        return;
    }

    // 開始處理
    setLoading(true);
    showStatus('loading', '⏳', '正在搜尋並處理新聞...', '這可能需要 30 秒至 2 分鐘，請耐心等待');
    hideResults();

    try {
        const response = await fetch(`${API_BASE_URL}/api/run`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || result.message || '伺服器錯誤');
        }

        // 處理成功
        handleSuccess(result, formData);

    } catch (error) {
        console.error('Error:', error);
        showStatus('error', '❌', '處理失敗', error.message);
    } finally {
        setLoading(false);
    }
});

// Email 驗證
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// 設定 Loading 狀態
function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    btnText.style.display = isLoading ? 'none' : 'inline';
    btnLoading.style.display = isLoading ? 'inline' : 'none';
}

// 顯示狀態
function showStatus(type, icon, message, details = '') {
    statusSection.style.display = 'block';
    statusCard.className = 'status-card';

    if (type === 'success') {
        statusCard.classList.add('success');
    } else if (type === 'error') {
        statusCard.classList.add('error');
    } else if (type === 'warning') {
        statusCard.classList.add('warning');
    }

    statusIcon.textContent = icon;
    statusMessage.textContent = message;
    statusDetails.textContent = details;
}

// 隱藏結果
function hideResults() {
    resultsSection.style.display = 'none';
    articlesList.innerHTML = '';
}

// 處理成功結果
function handleSuccess(result, formData) {
    const articles = result.articles || [];
    const emailStatus = result.email_status;

    // 顯示狀態
    if (emailStatus && emailStatus.success) {
        showStatus('success', '✅', '處理完成，郵件已發送！',
            `成功抓取 ${articles.length} 篇新聞，已寄送至 ${formData.email}`);
    } else if (articles.length > 0) {
        const emailError = emailStatus ? emailStatus.error : '未知錯誤';
        showStatus('warning', '⚠️', '新聞抓取成功，但郵件發送失敗',
            `抓取 ${articles.length} 篇新聞。郵件錯誤：${emailError}`);
    } else {
        showStatus('warning', '⚠️', '未找到符合條件的新聞',
            result.message || '請嘗試調整搜尋條件或日期範圍');
    }

    // 顯示結果
    if (articles.length > 0) {
        displayResults(articles, formData, result);
    }
}

// 顯示結果
function displayResults(articles, formData, result) {
    resultsSection.style.display = 'block';

    // 摘要資訊
    const dateInfo = formData.date_mode === 'today'
        ? '當日'
        : `${formData.start_date} ~ ${formData.end_date}`;

    const langText = {
        'zh-TW': '中文',
        'en-US': '英文',
        'both': '中英文'
    };

    const searchModeText = result.search_params?.search_mode === 'google' ? 'Google Search' : 'RSS';

    resultsSummary.innerHTML = `
        <p>
            <strong>搜尋條件：</strong>
            關鍵字「${escapeHtml(formData.keyword)}」|
            語言：${langText[formData.language]} |
            日期：${dateInfo} |
            要求篇數：${formData.count} |
            模式：${searchModeText}
        </p>
        <p>
            <strong>實際結果：</strong>共找到 ${articles.length} 篇新聞
            ${result.note ? `<br><em style="color: #856404;">備註：${escapeHtml(result.note)}</em>` : ''}
        </p>
    `;

    // 文章列表
    articlesList.innerHTML = articles.map((article, index) => createArticleCard(article, index)).join('');
}

// 建立文章卡片
function createArticleCard(article, index) {
    const hasContent = article.has_full_content !== false;
    const contentClass = hasContent ? '' : 'no-content';

    // 處理來源顯示
    const source = article.source || '未知來源';

    // 處理時間顯示
    let timeDisplay = '未知時間';
    if (article.published) {
        try {
            const date = new Date(article.published);
            timeDisplay = date.toLocaleString('zh-TW', {
                timeZone: 'Asia/Taipei',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            timeDisplay = article.published;
        }
    }

    // 語言標籤
    const langTag = article.language === 'zh-TW' ? '中文' :
                    article.language === 'en-US' ? '英文' : '';

    // 抽取方法標籤
    const methodTag = article.extract_method ? getMethodLabel(article.extract_method) : '';

    // 完整內容
    const contentId = `content-${index}`;
    const fullContent = article.content || '';
    const contentLength = fullContent.length;

    return `
        <div class="article-card">
            <div class="article-header">
                <h3 class="article-title">
                    <a href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer">
                        ${escapeHtml(article.title)}
                    </a>
                </h3>
                <div class="article-meta">
                    <span class="tag tag-source">📰 ${escapeHtml(source)}</span>
                    ${langTag ? `<span class="tag tag-lang">🌐 ${langTag}</span>` : ''}
                    ${methodTag ? `<span class="tag tag-method">${methodTag}</span>` : ''}
                    <span>🕐 ${timeDisplay}</span>
                    ${contentLength > 0 ? `<span class="tag tag-length">📄 ${contentLength} 字</span>` : ''}
                </div>
            </div>
            <div class="article-content ${contentClass}">
                <h4>${hasContent ? '📖 文章內容' : '⚠️ 無法取得全文'}</h4>
                <div class="content-body">
                    <p>${escapeHtml(fullContent) || '無內容'}</p>
                </div>
            </div>
        </div>
    `;
}

// 取得抽取方法的顯示標籤
function getMethodLabel(method) {
    const labels = {
        'trafilatura': '🔧 trafilatura',
        'playwright': '🎭 Playwright',
        'partial': '⚡ 部分內容',
        'rss_summary': '📡 RSS',
        'failed': '❌ 失敗'
    };
    return labels[method] || method;
}

// 展開/收合內容
function toggleContent(contentId) {
    const content = document.getElementById(contentId);
    const icon = document.getElementById('icon-' + contentId);

    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '▲';
    } else {
        content.style.display = 'none';
        icon.textContent = '▼';
    }
}

// HTML 跳脫
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 頁面載入時設定初始日期並檢查 API 狀態
document.addEventListener('DOMContentLoaded', async function() {
    const today = getTaipeiDate();
    document.getElementById('startDate').value = today;
    document.getElementById('endDate').value = today;

    // 檢查 API 設定狀態
    await checkApiStatus();
});

// 檢查 API 設定狀態
async function checkApiStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/config`);
        const config = await response.json();

        const googleApiStatus = document.getElementById('googleApiStatus');
        if (googleApiStatus) {
            if (config.google_search_available) {
                googleApiStatus.textContent = '✅ 已設定';
                googleApiStatus.className = 'api-status configured';
            } else {
                googleApiStatus.textContent = '⚠️ 未設定';
                googleApiStatus.className = 'api-status not-configured';
            }
        }
    } catch (error) {
        console.error('檢查 API 狀態失敗:', error);
    }
}

// ===== 設定管理功能 =====

// 開啟設定彈窗
async function openSettings() {
    document.getElementById('settingsModal').style.display = 'flex';

    // 載入目前設定
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings`);
        const settings = await response.json();

        // 填入目前值（密碼欄位顯示遮蔽值，不實際填入）
        document.getElementById('googleSearchEngineId').value = settings.GOOGLE_SEARCH_ENGINE_ID || '';
        document.getElementById('smtpHost').value = settings.SMTP_HOST || '';
        document.getElementById('smtpPort').value = settings.SMTP_PORT || '';
        document.getElementById('smtpUser').value = settings.SMTP_USER || '';

        // 密碼欄位：如果有值就顯示 placeholder
        if (settings.GOOGLE_API_KEY) {
            document.getElementById('googleApiKey').placeholder = '已設定 (輸入新值以覆蓋)';
        }
        if (settings.SMTP_PASS) {
            document.getElementById('smtpPass').placeholder = '已設定 (輸入新值以覆蓋)';
        }
    } catch (error) {
        console.error('載入設定失敗:', error);
    }
}

// 關閉設定彈窗
function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

// 儲存設定
async function saveSettings() {
    const settings = {};

    // Google API 設定
    const googleApiKey = document.getElementById('googleApiKey').value.trim();
    const googleSearchEngineId = document.getElementById('googleSearchEngineId').value.trim();

    if (googleApiKey) {
        settings.GOOGLE_API_KEY = googleApiKey;
    }
    if (googleSearchEngineId) {
        settings.GOOGLE_SEARCH_ENGINE_ID = googleSearchEngineId;
    }

    // SMTP 設定
    const smtpHost = document.getElementById('smtpHost').value.trim();
    const smtpPort = document.getElementById('smtpPort').value.trim();
    const smtpUser = document.getElementById('smtpUser').value.trim();
    const smtpPass = document.getElementById('smtpPass').value.trim();

    if (smtpHost) settings.SMTP_HOST = smtpHost;
    if (smtpPort) settings.SMTP_PORT = smtpPort;
    if (smtpUser) settings.SMTP_USER = smtpUser;
    if (smtpPass) settings.SMTP_PASS = smtpPass;

    if (Object.keys(settings).length === 0) {
        alert('沒有要更新的設定');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings)
        });

        const result = await response.json();

        if (result.success) {
            alert(`設定已更新！\n${result.message}`);
            closeSettings();
            // 重新檢查 API 狀態
            await checkApiStatus();
        } else {
            alert('設定更新失敗');
        }
    } catch (error) {
        console.error('儲存設定失敗:', error);
        alert('儲存設定失敗: ' + error.message);
    }
}

// 點擊背景關閉彈窗
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        closeSettings();
    }
});
