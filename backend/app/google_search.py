"""
Google Custom Search API 模組
免費額度：每天 100 次查詢
"""

import logging
import os
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlencode
import pytz

logger = logging.getLogger(__name__)


class GoogleSearchFetcher:
    """
    Google Custom Search API 新聞抓取器

    需要設定：
    - GOOGLE_API_KEY: Google Cloud API Key
    - GOOGLE_SEARCH_ENGINE_ID: Programmable Search Engine ID (cx)
    """

    API_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY', '')
        self.search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID', '')
        self.taipei_tz = pytz.timezone('Asia/Taipei')

        if not self.api_key or not self.search_engine_id:
            logger.warning("Google Search API 未設定，請設定 GOOGLE_API_KEY 和 GOOGLE_SEARCH_ENGINE_ID")

    def is_configured(self) -> bool:
        """檢查 API 是否已設定"""
        return bool(self.api_key and self.search_engine_id)

    async def fetch_news(
        self,
        keyword: str,
        language: str,
        start_date: datetime,
        end_date: datetime,
        max_count: int = 10
    ) -> List[Dict]:
        """
        使用 Google Custom Search API 搜尋新聞

        Args:
            keyword: 搜尋關鍵字
            language: 語言 (zh-TW, en-US, both)
            start_date: 開始日期
            end_date: 結束日期
            max_count: 最大抓取數量 (API 單次最多 10 筆)

        Returns:
            新聞列表
        """
        if not self.is_configured():
            logger.error("Google Search API 未設定")
            return []

        articles = []

        # 根據語言設定搜尋參數
        if language == 'both':
            # 同時搜尋中英文
            zh_articles = await self._search(keyword, 'zh-TW', start_date, end_date, max_count)
            en_articles = await self._search(keyword, 'en-US', start_date, end_date, max_count)
            articles.extend(zh_articles)
            articles.extend(en_articles)
        else:
            articles = await self._search(keyword, language, start_date, end_date, max_count)

        # 依時間排序
        articles = self._sort_by_time(articles)

        return articles[:max_count]

    async def _search(
        self,
        keyword: str,
        language: str,
        start_date: datetime,
        end_date: datetime,
        max_count: int
    ) -> List[Dict]:
        """
        執行單一語言搜尋
        """
        # 語言對應
        lang_map = {
            'zh-TW': {'lr': 'lang_zh-TW', 'gl': 'tw', 'hl': 'zh-TW'},
            'en-US': {'lr': 'lang_en', 'gl': 'us', 'hl': 'en'}
        }
        lang_config = lang_map.get(language, lang_map['en-US'])

        # 日期範圍格式化 (Google 使用 YYYYMMDD)
        date_restrict = self._get_date_restrict(start_date, end_date)

        # 建構查詢參數
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': f'{keyword} 新聞' if language == 'zh-TW' else f'{keyword} news',
            'num': min(max_count, 10),  # API 單次最多 10 筆
            'lr': lang_config['lr'],
            'gl': lang_config['gl'],
            'hl': lang_config['hl'],
            'sort': 'date',  # 按日期排序
            'searchType': 'undefined',  # 一般搜尋（包含新聞）
        }

        # 加入日期限制
        if date_restrict:
            params['dateRestrict'] = date_restrict

        url = f"{self.API_URL}?{urlencode(params)}"
        logger.info(f"Google Search API 查詢: {keyword} ({language})")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 403:
                        logger.error("Google Search API 配額已用完或 API Key 無效")
                        return []

                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Google Search API 錯誤: {response.status} - {error_text}")
                        return []

                    data = await response.json()

            # 解析結果
            articles = []
            items = data.get('items', [])

            for item in items:
                article = self._parse_item(item, language)
                if article:
                    articles.append(article)

            logger.info(f"Google Search 找到 {len(articles)} 篇文章 ({language})")
            return articles

        except aiohttp.ClientError as e:
            logger.error(f"Google Search API 網路錯誤: {e}")
            return []
        except Exception as e:
            logger.error(f"Google Search API 錯誤: {e}")
            return []

    def _parse_item(self, item: Dict, language: str) -> Optional[Dict]:
        """
        解析單一搜尋結果
        """
        try:
            title = item.get('title', '').strip()
            link = item.get('link', '')
            snippet = item.get('snippet', '')

            if not title or not link:
                return None

            # 嘗試取得發布時間（從 pagemap 中）
            published = None
            published_dt = None

            pagemap = item.get('pagemap', {})

            # 從 metatags 取得時間
            metatags = pagemap.get('metatags', [{}])[0] if pagemap.get('metatags') else {}
            date_str = (
                metatags.get('article:published_time') or
                metatags.get('og:updated_time') or
                metatags.get('date') or
                metatags.get('pubdate')
            )

            if date_str:
                try:
                    from dateutil import parser as date_parser
                    published_dt = date_parser.parse(date_str)
                    if published_dt.tzinfo is None:
                        published_dt = pytz.UTC.localize(published_dt)
                    published = published_dt.isoformat()
                except:
                    pass

            # 嘗試取得來源
            source = ''
            if 'newsarticle' in pagemap:
                news_article = pagemap['newsarticle'][0] if pagemap['newsarticle'] else {}
                source = news_article.get('source', '')

            if not source:
                # 從 URL 取得網域作為來源
                from urllib.parse import urlparse
                parsed = urlparse(link)
                source = parsed.netloc.replace('www.', '')

            return {
                'title': title,
                'url': link,
                'google_url': link,
                'source': source,
                'published': published,
                'published_dt': published_dt,
                'summary': snippet,
                'language': language
            }

        except Exception as e:
            logger.error(f"解析搜尋結果失敗: {e}")
            return None

    def _get_date_restrict(self, start_date: datetime, end_date: datetime) -> str:
        """
        計算日期限制參數
        Google Custom Search 使用 d[number] 格式表示過去 N 天
        """
        now = datetime.now(self.taipei_tz)

        # 計算從今天到 start_date 的天數差
        if start_date.tzinfo:
            start_taipei = start_date.astimezone(self.taipei_tz)
        else:
            start_taipei = self.taipei_tz.localize(start_date)

        days_diff = (now.date() - start_taipei.date()).days + 1

        if days_diff <= 1:
            return 'd1'  # 今天
        elif days_diff <= 7:
            return f'd{days_diff}'
        elif days_diff <= 30:
            return 'w1' if days_diff <= 7 else f'd{days_diff}'
        else:
            return 'm1'  # 一個月內

    def _sort_by_time(self, articles: List[Dict]) -> List[Dict]:
        """依時間排序（新到舊）"""
        def sort_key(article):
            pub_dt = article.get('published_dt')
            if pub_dt is None:
                return datetime.min.replace(tzinfo=pytz.UTC)
            return pub_dt

        return sorted(articles, key=sort_key, reverse=True)

    def deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """URL 去重"""
        seen_urls = set()
        unique = []

        for article in articles:
            url = article['url'].lower().rstrip('/')
            if url not in seen_urls:
                seen_urls.add(url)
                unique.append(article)

        return unique
