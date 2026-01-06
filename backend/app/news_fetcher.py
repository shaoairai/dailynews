"""
新聞抓取模組 - 使用 Google News RSS
"""

import logging
import asyncio
import aiohttp
import feedparser
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
import pytz
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class NewsFetcher:
    """
    Google News RSS 新聞抓取器
    """

    # Google News RSS 基礎 URL
    GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"

    # 語言設定對應
    LANGUAGE_CONFIG = {
        'zh-TW': {
            'hl': 'zh-TW',
            'gl': 'TW',
            'ceid': 'TW:zh-Hant'
        },
        'en-US': {
            'hl': 'en-US',
            'gl': 'US',
            'ceid': 'US:en'
        }
    }

    # 要移除的 tracking 參數
    TRACKING_PARAMS = [
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'msclkid', 'ref', 'source', 'mc_cid', 'mc_eid'
    ]

    def __init__(self):
        self.taipei_tz = pytz.timezone('Asia/Taipei')

    async def fetch_news(
        self,
        keyword: str,
        language: str,
        start_date: datetime,
        end_date: datetime,
        max_count: int = 30
    ) -> List[Dict]:
        """
        抓取新聞列表

        Args:
            keyword: 搜尋關鍵字
            language: 語言 (zh-TW, en-US, both)
            start_date: 開始日期 (含時區)
            end_date: 結束日期 (含時區)
            max_count: 最大抓取數量

        Returns:
            新聞列表
        """
        articles = []

        if language == 'both':
            # 同時抓中英文
            tasks = [
                self._fetch_rss(keyword, 'zh-TW'),
                self._fetch_rss(keyword, 'en-US')
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for lang, result in zip(['zh-TW', 'en-US'], results):
                if isinstance(result, Exception):
                    logger.error(f"抓取 {lang} RSS 失敗: {result}")
                else:
                    for article in result:
                        article['language'] = lang
                    articles.extend(result)
        else:
            # 單一語言
            result = await self._fetch_rss(keyword, language)
            for article in result:
                article['language'] = language
            articles.extend(result)

        # 過濾日期範圍
        filtered_articles = self._filter_by_date(articles, start_date, end_date)

        # 依時間排序（新到舊）
        sorted_articles = self._sort_by_time(filtered_articles)

        # 限制數量
        return sorted_articles[:max_count]

    async def _fetch_rss(self, keyword: str, language: str) -> List[Dict]:
        """
        從 Google News RSS 抓取新聞

        Args:
            keyword: 搜尋關鍵字
            language: 語言代碼

        Returns:
            解析後的新聞列表
        """
        config = self.LANGUAGE_CONFIG.get(language, self.LANGUAGE_CONFIG['en-US'])

        # 建構 RSS URL
        # Google News RSS 搜尋格式：/rss/search?q=關鍵字&hl=語言&gl=地區&ceid=地區:語言
        params = {
            'q': keyword,
            'hl': config['hl'],
            'gl': config['gl'],
            'ceid': config['ceid']
        }

        url = f"{self.GOOGLE_NEWS_RSS_BASE}?{urlencode(params)}"
        logger.info(f"抓取 RSS: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        logger.error(f"RSS 請求失敗: {response.status}")
                        return []

                    content = await response.text()

            # 解析 RSS
            feed = feedparser.parse(content)

            if feed.bozo:
                logger.warning(f"RSS 解析有警告: {feed.bozo_exception}")

            articles = []
            for entry in feed.entries:
                article = self._parse_entry(entry)
                if article:
                    articles.append(article)

            logger.info(f"從 {language} RSS 解析到 {len(articles)} 篇文章")
            return articles

        except asyncio.TimeoutError:
            logger.error(f"RSS 請求超時: {url}")
            return []
        except Exception as e:
            logger.error(f"抓取 RSS 發生錯誤: {e}")
            return []

    def _parse_entry(self, entry) -> Optional[Dict]:
        """
        解析單一 RSS entry

        Args:
            entry: feedparser entry 物件

        Returns:
            解析後的文章資訊
        """
        try:
            # 標題
            title = entry.get('title', '').strip()
            if not title:
                return None

            # 連結 - Google News RSS 的連結通常是 Google 轉址
            link = entry.get('link', '')
            if not link:
                return None

            # 嘗試從 Google 轉址取得原始 URL
            original_url = self._extract_original_url(link)

            # 來源 - Google News RSS 通常在標題後有來源
            source = ''
            if ' - ' in title:
                parts = title.rsplit(' - ', 1)
                if len(parts) == 2:
                    title = parts[0].strip()
                    source = parts[1].strip()

            # 也可以從 source 欄位取得
            if not source and hasattr(entry, 'source'):
                source = entry.source.get('title', '')

            # 發布時間
            published = None
            published_str = entry.get('published') or entry.get('updated')
            if published_str:
                try:
                    published = date_parser.parse(published_str)
                    # 確保有時區資訊
                    if published.tzinfo is None:
                        published = pytz.UTC.localize(published)
                except Exception as e:
                    logger.debug(f"解析時間失敗: {published_str}, {e}")

            # 摘要（RSS 自帶的）
            summary = ''
            if hasattr(entry, 'summary'):
                summary = self._clean_html(entry.summary)

            return {
                'title': title,
                'url': original_url or link,
                'google_url': link,
                'source': source,
                'published': published.isoformat() if published else None,
                'published_dt': published,
                'summary': summary
            }

        except Exception as e:
            logger.error(f"解析 entry 失敗: {e}")
            return None

    def _extract_original_url(self, google_url: str) -> Optional[str]:
        """
        從 Google News 轉址 URL 提取原始文章 URL

        Google News URL 格式通常是:
        https://news.google.com/rss/articles/...
        或
        https://news.google.com/articles/...?...&url=原始URL

        Args:
            google_url: Google News 的 URL

        Returns:
            原始文章 URL 或 None
        """
        # Google News RSS 的連結通常就是原始連結
        # 但有時會經過 Google 轉址，這裡做基本處理
        if 'news.google.com' not in google_url:
            return google_url

        # 嘗試從 URL 參數中提取
        parsed = urlparse(google_url)
        query_params = parse_qs(parsed.query)

        if 'url' in query_params:
            return query_params['url'][0]

        # 返回 None，讓呼叫者使用原始 Google URL
        return None

    def _clean_html(self, html_text: str) -> str:
        """
        清理 HTML 標籤，只保留純文字
        """
        import re
        # 移除 HTML 標籤
        clean = re.sub(r'<[^>]+>', '', html_text)
        # 清理多餘空白
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _filter_by_date(
        self,
        articles: List[Dict],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        依日期範圍過濾文章

        Args:
            articles: 文章列表
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            過濾後的文章列表
        """
        filtered = []

        for article in articles:
            pub_dt = article.get('published_dt')

            if pub_dt is None:
                # 如果沒有時間，預設包含（放寬條件）
                # TODO: 可以改成排除沒有時間的文章
                filtered.append(article)
                continue

            # 轉換到台北時區比較
            pub_taipei = pub_dt.astimezone(self.taipei_tz)
            start_taipei = start_date.astimezone(self.taipei_tz) if start_date.tzinfo else self.taipei_tz.localize(start_date)
            end_taipei = end_date.astimezone(self.taipei_tz) if end_date.tzinfo else self.taipei_tz.localize(end_date)

            if start_taipei <= pub_taipei <= end_taipei:
                filtered.append(article)

        logger.info(f"日期過濾: {len(articles)} -> {len(filtered)} 篇")
        return filtered

    def _sort_by_time(self, articles: List[Dict]) -> List[Dict]:
        """
        依時間排序（新到舊）

        對於沒有時間的文章，排在有時間的文章後面

        Args:
            articles: 文章列表

        Returns:
            排序後的文章列表
        """
        def sort_key(article):
            pub_dt = article.get('published_dt')
            if pub_dt is None:
                # 沒有時間的排在最後
                return datetime.min.replace(tzinfo=pytz.UTC)
            return pub_dt

        return sorted(articles, key=sort_key, reverse=True)

    def deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        文章去重

        目前實作 URL 去重，標題相似度去重為 TODO

        Args:
            articles: 文章列表

        Returns:
            去重後的文章列表
        """
        seen_urls = set()
        unique_articles = []

        for article in articles:
            # 正規化 URL
            normalized_url = self._normalize_url(article['url'])

            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_articles.append(article)

        # TODO: 標題相似度去重
        # 可使用 difflib.SequenceMatcher 或更進階的文字相似度演算法
        # 例如：
        # from difflib import SequenceMatcher
        # def similar(a, b):
        #     return SequenceMatcher(None, a, b).ratio()
        # 若兩篇文章標題相似度 > 0.8，視為重複

        logger.info(f"URL 去重: {len(articles)} -> {len(unique_articles)} 篇")
        return unique_articles

    def _normalize_url(self, url: str) -> str:
        """
        正規化 URL，移除 tracking 參數

        Args:
            url: 原始 URL

        Returns:
            正規化後的 URL
        """
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)

            # 移除 tracking 參數
            cleaned_params = {
                k: v for k, v in query_params.items()
                if k.lower() not in self.TRACKING_PARAMS
            }

            # 重建 URL
            cleaned_query = urlencode(cleaned_params, doseq=True) if cleaned_params else ''
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path.rstrip('/'),
                parsed.params,
                cleaned_query,
                ''  # 移除 fragment
            ))

            return normalized

        except Exception as e:
            logger.debug(f"URL 正規化失敗: {url}, {e}")
            return url.lower()
