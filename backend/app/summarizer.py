"""
文章摘要模組
提供 placeholder 摘要與 AI 摘要介面
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# AI API 設定（可選）
AI_API_KEY = os.getenv('AI_API_KEY', '')
AI_API_URL = os.getenv('AI_API_URL', '')


class Summarizer:
    """
    文章摘要產生器

    目前實作：
    1. Placeholder 摘要：擷取正文前 450~600 字
    2. AI 摘要介面：預留給未來 AI API 整合

    免費 AI API 選項（供未來使用）：
    -----------------------------------------
    1. Hugging Face Inference API (免費層)
       - URL: https://api-inference.huggingface.co/models/{model}
       - 模型推薦: facebook/bart-large-cnn (英文), csebuetnlp/mT5_multilingual_XLSum (多語言)
       - 免費額度: 每月有限額度，適合小量使用

    2. OpenAI API (有免費試用額度)
       - URL: https://api.openai.com/v1/chat/completions
       - 需註冊取得 API Key
       - 新帳號有 $5 USD 試用額度

    3. Google Gemini API (免費層)
       - URL: https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent
       - 免費額度: 每分鐘 60 次請求

    4. Cohere API (免費層)
       - URL: https://api.cohere.ai/v1/summarize
       - 免費額度: 每月 100 次請求

    5. 本地模型 (完全免費，但需要較好硬體)
       - Ollama + llama2 或 mistral
       - 無 API 費用，但需要 GPU 或較強 CPU
    """

    # Placeholder 摘要設定
    SUMMARY_MIN_LENGTH = 450
    SUMMARY_MAX_LENGTH = 600

    def __init__(self):
        self.ai_enabled = bool(AI_API_KEY and AI_API_URL)
        if self.ai_enabled:
            logger.info("AI 摘要已啟用")
        else:
            logger.info("使用 Placeholder 摘要（未設定 AI API）")

    def summarize(self, text: str, use_ai: bool = False) -> str:
        """
        產生文章摘要

        Args:
            text: 文章正文
            use_ai: 是否使用 AI 摘要（預設 False）

        Returns:
            摘要文字
        """
        if not text or len(text.strip()) < 20:
            return "無法取得內容摘要，請點擊標題查看原文。"

        # 清理文字
        cleaned_text = self._clean_text(text)

        # 使用 AI 摘要（如果啟用且要求）
        if use_ai and self.ai_enabled:
            ai_summary = self._summarize_with_ai(cleaned_text)
            if ai_summary:
                return ai_summary
            logger.warning("AI 摘要失敗，改用 Placeholder")

        # 使用 Placeholder 摘要
        return self._create_placeholder_summary(cleaned_text)

    def _clean_text(self, text: str) -> str:
        """
        清理文字

        移除多餘空白、特殊字元等
        """
        # 移除多餘空白和換行
        text = re.sub(r'\s+', ' ', text)

        # 移除特殊控制字元
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

        return text.strip()

    def _create_placeholder_summary(self, text: str) -> str:
        """
        建立 Placeholder 摘要

        規則：
        1. 擷取前 450~600 字
        2. 盡量在句子結尾處截斷
        3. 加上省略號表示還有後續
        """
        if len(text) <= self.SUMMARY_MAX_LENGTH:
            return text

        # 取前 600 字
        summary = text[:self.SUMMARY_MAX_LENGTH]

        # 嘗試在句子結尾處截斷
        # 尋找最後一個句號、問號、驚嘆號
        sentence_endings = [
            summary.rfind('。'),
            summary.rfind('！'),
            summary.rfind('？'),
            summary.rfind('. '),
            summary.rfind('! '),
            summary.rfind('? '),
        ]

        # 找到最後一個句子結尾（至少要有 450 字）
        best_end = -1
        for end in sentence_endings:
            if end > self.SUMMARY_MIN_LENGTH and end > best_end:
                best_end = end

        if best_end > 0:
            summary = summary[:best_end + 1]
        else:
            # 找不到句子結尾，在空格處截斷
            space_pos = summary.rfind(' ')
            if space_pos > self.SUMMARY_MIN_LENGTH:
                summary = summary[:space_pos]

        # 加上省略號
        if len(text) > len(summary):
            summary = summary.rstrip('.,;:!?。，；：！？') + '...'

        return summary

    def _summarize_with_ai(self, text: str) -> Optional[str]:
        """
        使用 AI API 產生摘要

        這是預留的介面，實際實作依據選用的 AI 服務而定

        Args:
            text: 要摘要的文字

        Returns:
            AI 產生的摘要，失敗則返回 None
        """
        if not self.ai_enabled:
            return None

        try:
            # ========================================
            # 以下是 AI API 整合的範例程式碼
            # 請依據實際使用的 API 修改
            # ========================================

            # 範例: Hugging Face Inference API
            # import requests
            #
            # headers = {"Authorization": f"Bearer {AI_API_KEY}"}
            # payload = {"inputs": text[:2000], "parameters": {"max_length": 200}}
            #
            # response = requests.post(AI_API_URL, headers=headers, json=payload)
            # if response.status_code == 200:
            #     result = response.json()
            #     return result[0].get('summary_text', '')

            # 範例: OpenAI API
            # import openai
            #
            # openai.api_key = AI_API_KEY
            # response = openai.ChatCompletion.create(
            #     model="gpt-3.5-turbo",
            #     messages=[
            #         {"role": "system", "content": "你是一個新聞摘要助手，請用繁體中文簡潔摘要以下新聞內容。"},
            #         {"role": "user", "content": text[:3000]}
            #     ],
            #     max_tokens=300
            # )
            # return response.choices[0].message.content

            # 範例: Google Gemini API
            # import google.generativeai as genai
            #
            # genai.configure(api_key=AI_API_KEY)
            # model = genai.GenerativeModel('gemini-pro')
            # response = model.generate_content(f"請簡潔摘要以下新聞:\n{text[:3000]}")
            # return response.text

            logger.warning("AI API 已設定但未實作具體呼叫邏輯")
            return None

        except Exception as e:
            logger.error(f"AI 摘要發生錯誤: {e}")
            return None


def summarize_with_ai(text: str) -> Optional[str]:
    """
    獨立的 AI 摘要函式（供外部呼叫）

    這是預留給未來整合的函式介面
    使用方式：
    1. 設定環境變數 AI_API_KEY 和 AI_API_URL
    2. 實作 _call_ai_api 函式
    3. 呼叫此函式

    Args:
        text: 要摘要的文字

    Returns:
        摘要文字，失敗返回 None
    """
    summarizer = Summarizer()
    return summarizer._summarize_with_ai(text)
