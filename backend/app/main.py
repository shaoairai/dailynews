"""
每日新聞自動摘要系統 - FastAPI 主程式
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, List
from datetime import datetime
import pytz

from app.news_fetcher import NewsFetcher
from app.content_extractor import ContentExtractor
from app.summarizer import Summarizer
from app.email_sender import EmailSender

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 建立 FastAPI app
app = FastAPI(
    title="每日新聞自動摘要系統",
    description="自動抓取、摘要、寄送新聞的 API",
    version="1.0.0"
)

# CORS 設定 - 允許前端跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境應限制來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 請求/回應模型 =====

class NewsRequest(BaseModel):
    """新聞搜尋請求"""
    language: str = Field(..., description="語言: zh-TW, en-US, both")
    keyword: str = Field(..., min_length=1, max_length=200, description="搜尋關鍵字")
    count: int = Field(default=5, ge=1, le=20, description="抓取篇數 (1-20)")
    date_mode: str = Field(default="today", description="日期模式: today 或 custom")
    start_date: Optional[str] = Field(default=None, description="開始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="結束日期 YYYY-MM-DD")
    email: EmailStr = Field(..., description="收件人 Email")

    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        valid = ['zh-TW', 'en-US', 'both']
        if v not in valid:
            raise ValueError(f'語言必須是 {valid} 之一')
        return v

    @field_validator('date_mode')
    @classmethod
    def validate_date_mode(cls, v):
        if v not in ['today', 'custom']:
            raise ValueError('日期模式必須是 today 或 custom')
        return v

    @field_validator('keyword')
    @classmethod
    def validate_keyword(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('關鍵字不能為空')
        return v


class ArticleResponse(BaseModel):
    """文章回應"""
    title: str
    url: str
    source: Optional[str] = None
    published: Optional[str] = None
    language: Optional[str] = None
    content: Optional[str] = None  # 完整抓取內容
    summary: Optional[str] = None  # 摘要
    has_full_content: bool = True
    extract_method: Optional[str] = None  # 抽取方法


class EmailStatus(BaseModel):
    """Email 寄送狀態"""
    success: bool
    error: Optional[str] = None


class NewsResponse(BaseModel):
    """API 回應"""
    success: bool
    message: str
    articles: List[ArticleResponse] = []
    email_status: Optional[EmailStatus] = None
    note: Optional[str] = None
    search_params: Optional[dict] = None


# ===== API 端點 =====

@app.get("/")
async def root():
    """首頁"""
    return {
        "message": "每日新聞自動摘要系統 API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """健康檢查"""
    return {"status": "healthy"}


@app.post("/api/run", response_model=NewsResponse)
async def run_news_summary(request: NewsRequest):
    """
    執行新聞搜尋、摘要、寄信的主要 API
    """
    logger.info(f"收到請求: keyword={request.keyword}, language={request.language}, "
                f"count={request.count}, date_mode={request.date_mode}")

    taipei_tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(taipei_tz)

    # 解析日期範圍
    try:
        if request.date_mode == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        else:
            if not request.start_date or not request.end_date:
                raise HTTPException(
                    status_code=400,
                    detail="自訂日期模式必須提供 start_date 和 end_date"
                )
            start_date = taipei_tz.localize(
                datetime.strptime(request.start_date, '%Y-%m-%d')
            )
            end_date = taipei_tz.localize(
                datetime.strptime(request.end_date, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59
                )
            )

            if start_date > end_date:
                raise HTTPException(
                    status_code=400,
                    detail="開始日期不能晚於結束日期"
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"日期格式錯誤: {str(e)}")

    # 初始化各模組
    fetcher = NewsFetcher()
    extractor = ContentExtractor()
    summarizer = Summarizer()
    email_sender = EmailSender()

    articles = []
    note = None

    try:
        # Step 1: 從 Google News RSS 取得文章列表
        logger.info("Step 1: 抓取 Google News RSS...")
        raw_articles = await fetcher.fetch_news(
            keyword=request.keyword,
            language=request.language,
            start_date=start_date,
            end_date=end_date,
            max_count=request.count * 3  # 多抓一些以防過濾後不足
        )

        if not raw_articles:
            logger.warning("未找到任何新聞")
            return NewsResponse(
                success=True,
                message="未找到符合條件的新聞",
                articles=[],
                note="請嘗試調整關鍵字或放寬日期範圍"
            )

        logger.info(f"找到 {len(raw_articles)} 篇原始新聞")

        # Step 2: 去重
        logger.info("Step 2: URL 去重...")
        unique_articles = fetcher.deduplicate_articles(raw_articles)
        logger.info(f"去重後剩餘 {len(unique_articles)} 篇")

        # 取前 N 篇
        selected_articles = unique_articles[:request.count]

        if len(selected_articles) < request.count:
            note = f"符合條件的新聞僅 {len(selected_articles)} 篇，少於要求的 {request.count} 篇"
            logger.info(note)

        # Step 3: 抓取正文並產生摘要
        logger.info("Step 3: 抓取正文並產生摘要...")
        for i, article in enumerate(selected_articles):
            logger.info(f"處理第 {i+1}/{len(selected_articles)} 篇: {article['title'][:50]}...")

            # 抓取正文
            content_result = await extractor.extract_content(
                url=article['url'],
                fallback_summary=article.get('summary', '')
            )

            # 產生摘要
            summary = summarizer.summarize(
                text=content_result['content'],
                use_ai=False  # 先用 placeholder，未來可改為 True
            )

            articles.append(ArticleResponse(
                title=article['title'],
                url=article['url'],
                source=article.get('source'),
                published=article.get('published'),
                language=article.get('language'),
                content=content_result['content'],  # 完整內容
                summary=summary,
                has_full_content=content_result['has_full_content'],
                extract_method=content_result.get('method')
            ))

        # Step 4: 寄送 Email
        logger.info("Step 4: 寄送 Email...")
        email_result = email_sender.send_news_email(
            to_email=request.email,
            articles=[a.model_dump() for a in articles],
            search_params={
                'keyword': request.keyword,
                'language': request.language,
                'date_mode': request.date_mode,
                'start_date': request.start_date or start_date.strftime('%Y-%m-%d'),
                'end_date': request.end_date or end_date.strftime('%Y-%m-%d'),
                'count': request.count
            }
        )

        email_status = EmailStatus(
            success=email_result['success'],
            error=email_result.get('error')
        )

        logger.info(f"處理完成！共 {len(articles)} 篇新聞，Email 發送: {email_status.success}")

        return NewsResponse(
            success=True,
            message=f"成功處理 {len(articles)} 篇新聞",
            articles=articles,
            email_status=email_status,
            note=note,
            search_params={
                'keyword': request.keyword,
                'language': request.language,
                'date_range': f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
            }
        )

    except Exception as e:
        logger.error(f"處理過程發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"處理過程發生錯誤: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
