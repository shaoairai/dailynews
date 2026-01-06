"""
文章正文抽取模組
優先使用 trafilatura，支援可選的 Playwright 備援
"""

import logging
import os
import asyncio
import aiohttp
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 嘗試導入 trafilatura
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("trafilatura 未安裝，將使用基礎 HTML 解析")

# 檢查 Playwright 是否啟用（透過環境變數）
ENABLE_PLAYWRIGHT = os.getenv('ENABLE_PLAYWRIGHT', 'false').lower() == 'true'

# 嘗試導入 Playwright
PLAYWRIGHT_AVAILABLE = False
if ENABLE_PLAYWRIGHT:
    try:
        from playwright.async_api import async_playwright
        PLAYWRIGHT_AVAILABLE = True
        logger.info("Playwright 已啟用")
    except ImportError:
        logger.warning("ENABLE_PLAYWRIGHT=true 但 playwright 未安裝")


class ContentExtractor:
    """
    文章正文抽取器

    抽取順序：
    1. 使用 requests + trafilatura 抽取正文
    2. 若失敗且啟用 Playwright，使用 Playwright 渲染後再抽取
    3. 若仍失敗，使用 RSS 的 summary 作為 fallback
    4. 若以上都失敗，標記為「無法取得全文」
    """

    # 最小正文長度（低於此值視為抽取失敗）
    # 降低門檻，因為很多網站有反爬蟲機制
    MIN_CONTENT_LENGTH = 150

    # HTTP 請求設定
    REQUEST_TIMEOUT = 20  # 秒
    USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    def __init__(self):
        self.headers = {
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        }

    async def extract_content(
        self,
        url: str,
        fallback_summary: str = ''
    ) -> Dict:
        """
        抽取文章正文

        Args:
            url: 文章 URL
            fallback_summary: RSS 的摘要（作為 fallback）

        Returns:
            {
                'content': 正文內容,
                'has_full_content': 是否成功取得完整正文,
                'method': 使用的抽取方法
            }
        """
        # 方法 1: 使用 requests + trafilatura
        content = await self._extract_with_trafilatura(url)

        if content and len(content) >= self.MIN_CONTENT_LENGTH:
            logger.info(f"trafilatura 成功抽取 {len(content)} 字: {url[:50]}...")
            return {
                'content': content,
                'has_full_content': True,
                'method': 'trafilatura'
            }

        # 方法 2: 使用 Playwright（如果啟用）
        if PLAYWRIGHT_AVAILABLE:
            content = await self._extract_with_playwright(url)

            if content and len(content) >= self.MIN_CONTENT_LENGTH:
                logger.info(f"Playwright 成功抽取 {len(content)} 字: {url[:50]}...")
                return {
                    'content': content,
                    'has_full_content': True,
                    'method': 'playwright'
                }

        # 方法 3: 若有部分內容（即使很短），還是使用
        if content and len(content) > 50:
            logger.info(f"使用部分內容 ({len(content)} 字): {url[:50]}...")
            return {
                'content': content,
                'has_full_content': len(content) >= self.MIN_CONTENT_LENGTH,
                'method': 'partial'
            }

        # 方法 4: 使用 RSS summary 作為 fallback
        if fallback_summary and len(fallback_summary.strip()) > 20:
            logger.info(f"使用 RSS summary 作為 fallback: {url[:50]}...")
            return {
                'content': fallback_summary.strip(),
                'has_full_content': False,
                'method': 'rss_summary'
            }

        # 完全失敗 - 但還是給個有意義的訊息
        logger.warning(f"無法取得正文: {url[:50]}...")
        return {
            'content': '此新聞來源暫時無法取得內容，請點擊標題連結查看原文。',
            'has_full_content': False,
            'method': 'failed'
        }

    async def _extract_with_trafilatura(self, url: str) -> Optional[str]:
        """
        使用 trafilatura 抽取正文
        """
        if not TRAFILATURA_AVAILABLE:
            return await self._extract_basic(url)

        try:
            # 先取得 HTML
            html = await self._fetch_html(url)
            if not html:
                return None

            # 使用 trafilatura 抽取
            content = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
                favor_precision=True
            )

            return self._clean_content(content) if content else None

        except Exception as e:
            logger.error(f"trafilatura 抽取失敗: {url[:50]}..., {e}")
            return None

    async def _extract_basic(self, url: str) -> Optional[str]:
        """
        基礎 HTML 解析（當 trafilatura 不可用時）
        使用簡單的標籤移除
        """
        try:
            html = await self._fetch_html(url)
            if not html:
                return None

            import re

            # 移除 script 和 style
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

            # 移除所有 HTML 標籤
            text = re.sub(r'<[^>]+>', ' ', html)

            # 清理空白
            text = re.sub(r'\s+', ' ', text).strip()

            # 嘗試找出主要內容（簡單啟發式）
            # 取中間較長的段落
            if len(text) > 2000:
                # 取中間 2000 字
                start = len(text) // 4
                text = text[start:start + 2000]

            return self._clean_content(text)

        except Exception as e:
            logger.error(f"基礎解析失敗: {url[:50]}..., {e}")
            return None

    async def _extract_with_playwright(self, url: str) -> Optional[str]:
        """
        使用 Playwright 渲染後抽取正文
        支援處理 Google News 跳轉連結
        """
        if not PLAYWRIGHT_AVAILABLE:
            return None

        browser = None
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu'
                    ]
                )

                context = await browser.new_context(
                    user_agent=self.USER_AGENT,
                    locale='zh-TW',
                    timezone_id='Asia/Taipei'
                )

                page = await context.new_page()

                # 檢查是否為 Google News 跳轉連結
                is_google_news = 'news.google.com' in url

                if is_google_news:
                    # Google News 連結需要特殊處理：讓它跳轉到真正的文章
                    logger.info(f"Playwright 處理 Google News 跳轉: {url[:60]}...")

                    # 使用 domcontentloaded 而非 networkidle，因為 Google News 會跳轉
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)

                    # 等待跳轉完成（最多等 10 秒）
                    for _ in range(20):
                        await asyncio.sleep(0.5)
                        current_url = page.url
                        if 'news.google.com' not in current_url:
                            logger.info(f"跳轉成功: {current_url[:60]}...")
                            break

                    # 跳轉後等待頁面載入
                    try:
                        await page.wait_for_load_state('networkidle', timeout=15000)
                    except:
                        # 如果 networkidle 超時，繼續嘗試
                        pass
                else:
                    # 一般連結直接載入
                    logger.info(f"Playwright 開始抓取: {url[:60]}...")
                    await page.goto(url, wait_until='networkidle', timeout=30000)

                # 額外等待動態內容載入
                await asyncio.sleep(1)

                # 嘗試滾動頁面以觸發懶加載
                try:
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                    await asyncio.sleep(0.5)
                except:
                    pass

                # 取得最終 URL 和 HTML
                final_url = page.url
                html = await page.content()
                await browser.close()

                logger.info(f"最終頁面 URL: {final_url[:60]}...")

                # 使用 trafilatura 抽取
                if TRAFILATURA_AVAILABLE and html:
                    content = trafilatura.extract(
                        html,
                        include_comments=False,
                        include_tables=False,
                        no_fallback=False,
                        favor_recall=True  # 優先召回更多內容
                    )
                    if content:
                        logger.info(f"Playwright + trafilatura 成功抽取內容")
                        return self._clean_content(content)

                return None

        except Exception as e:
            logger.error(f"Playwright 抽取失敗: {url[:50]}..., {e}")
            if browser:
                try:
                    await browser.close()
                except:
                    pass
            return None

    async def _fetch_html(self, url: str) -> Optional[str]:
        """
        使用 aiohttp 取得 HTML 內容
        """
        try:
            timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self.headers, allow_redirects=True) as response:
                    if response.status != 200:
                        logger.warning(f"HTTP {response.status}: {url[:50]}...")
                        return None

                    # 檢查內容類型
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                        logger.warning(f"非 HTML 內容: {content_type}")
                        return None

                    return await response.text()

        except asyncio.TimeoutError:
            logger.warning(f"請求超時: {url[:50]}...")
            return None
        except Exception as e:
            logger.error(f"HTTP 請求失敗: {url[:50]}..., {e}")
            return None

    def _clean_content(self, content: Optional[str]) -> Optional[str]:
        """
        清理正文內容
        """
        if not content:
            return None

        import re

        # 移除多餘空白
        content = re.sub(r'\s+', ' ', content)

        # 移除開頭結尾空白
        content = content.strip()

        # 移除常見的頁面元素文字
        noise_patterns = [
            r'訂閱電子報',
            r'加入會員',
            r'免費註冊',
            r'分享到',
            r'Advertisement',
            r'Sponsored',
            r'Loading\.\.\.',
            r'Please wait',
        ]

        for pattern in noise_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)

        return content.strip()
