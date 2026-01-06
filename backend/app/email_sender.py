"""
Email 寄送模組
使用 SMTP 發送 HTML 格式的新聞摘要郵件
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List
import pytz

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Email 寄送器

    使用 SMTP 發送 HTML 格式郵件
    支援 Gmail SMTP (需要 App Password)
    """

    def __init__(self):
        # 從環境變數讀取 SMTP 設定
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_pass = os.getenv('SMTP_PASS', '')

        # 檢查設定
        self.is_configured = bool(self.smtp_user and self.smtp_pass)

        if not self.is_configured:
            logger.warning("SMTP 未設定，郵件功能將無法使用")
            logger.warning("請設定環境變數: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS")

    def send_news_email(
        self,
        to_email: str,
        articles: List[Dict],
        search_params: Dict
    ) -> Dict:
        """
        發送新聞摘要郵件

        Args:
            to_email: 收件人 Email
            articles: 文章列表
            search_params: 搜尋參數

        Returns:
            {
                'success': bool,
                'error': str or None
            }
        """
        if not self.is_configured:
            return {
                'success': False,
                'error': 'SMTP 未設定，請檢查環境變數 SMTP_USER 和 SMTP_PASS'
            }

        if not articles:
            return {
                'success': False,
                'error': '沒有文章可寄送'
            }

        try:
            # 產生郵件內容
            subject = self._generate_subject(search_params)
            html_body = self._generate_html_body(articles, search_params)

            # 建立郵件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_user
            msg['To'] = to_email

            # 加入 HTML 內容
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)

            # 發送郵件
            logger.info(f"正在發送郵件到 {to_email}...")

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            logger.info(f"郵件發送成功: {to_email}")
            return {'success': True, 'error': None}

        except smtplib.SMTPAuthenticationError as e:
            error_msg = 'SMTP 認證失敗，請檢查帳號密碼（Gmail 需使用 App Password）'
            logger.error(f"{error_msg}: {e}")
            return {'success': False, 'error': error_msg}

        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f'收件人地址被拒絕: {to_email}'
            logger.error(f"{error_msg}: {e}")
            return {'success': False, 'error': error_msg}

        except smtplib.SMTPException as e:
            error_msg = f'SMTP 錯誤: {str(e)}'
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f'發送郵件時發生未知錯誤: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'error': error_msg}

    def _generate_subject(self, search_params: Dict) -> str:
        """
        產生郵件主旨
        """
        taipei_tz = pytz.timezone('Asia/Taipei')
        now = datetime.now(taipei_tz)
        date_str = now.strftime('%Y/%m/%d')

        keyword = search_params.get('keyword', '新聞')
        return f"📰 每日新聞摘要 - {keyword} ({date_str})"

    def _generate_html_body(
        self,
        articles: List[Dict],
        search_params: Dict
    ) -> str:
        """
        產生 HTML 郵件內容
        """
        taipei_tz = pytz.timezone('Asia/Taipei')
        now = datetime.now(taipei_tz)
        generated_time = now.strftime('%Y-%m-%d %H:%M:%S')

        # 語言文字對應
        lang_text = {
            'zh-TW': '中文',
            'en-US': '英文',
            'both': '中英文'
        }

        language = lang_text.get(search_params.get('language', ''), '未知')
        keyword = search_params.get('keyword', '')
        date_mode = search_params.get('date_mode', 'today')

        if date_mode == 'today':
            date_range = '當日'
        else:
            start = search_params.get('start_date', '')
            end = search_params.get('end_date', '')
            date_range = f"{start} ~ {end}"

        # 產生文章列表 HTML
        articles_html = ''
        for i, article in enumerate(articles, 1):
            title = self._escape_html(article.get('title', '無標題'))
            url = article.get('url', '#')
            source = self._escape_html(article.get('source', '未知來源'))
            summary = self._escape_html(article.get('summary', '無摘要'))
            has_full = article.get('has_full_content', True)

            # 處理時間
            published = article.get('published', '')
            if published:
                try:
                    dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
                    published = dt.astimezone(taipei_tz).strftime('%Y-%m-%d %H:%M')
                except:
                    pass

            # 摘要樣式
            summary_style = ''
            summary_note = ''
            if not has_full:
                summary_style = 'background-color: #fff3cd; padding: 10px; border-radius: 4px;'
                summary_note = '<span style="color: #856404; font-size: 12px;">(無法取得全文，使用索引摘要)</span><br>'

            articles_html += f'''
            <div style="margin-bottom: 25px; padding: 20px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid #667eea;">
                <h3 style="margin: 0 0 10px 0; font-size: 16px;">
                    <a href="{url}" style="color: #2c3e50; text-decoration: none;" target="_blank">
                        {i}. {title}
                    </a>
                </h3>
                <div style="color: #888; font-size: 13px; margin-bottom: 12px;">
                    📰 {source} &nbsp;|&nbsp; 🕐 {published or '未知時間'}
                </div>
                <div style="{summary_style}">
                    {summary_note}
                    <p style="color: #444; font-size: 14px; line-height: 1.7; margin: 0;">
                        {summary}
                    </p>
                </div>
            </div>
            '''

        # 完整 HTML
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans TC', sans-serif; background-color: #f0f2f5; margin: 0; padding: 20px;">
            <div style="max-width: 700px; margin: 0 auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">

                <!-- Header -->
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">📰 每日新聞摘要</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 14px;">自動抓取 · 智能摘要 · 定時推送</p>
                </div>

                <!-- Search Info -->
                <div style="padding: 20px 30px; background-color: #f8f9fa; border-bottom: 1px solid #eee;">
                    <table style="width: 100%; font-size: 14px; color: #555;">
                        <tr>
                            <td style="padding: 5px 0;"><strong>搜尋關鍵字:</strong></td>
                            <td style="padding: 5px 0;">{self._escape_html(keyword)}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>語言:</strong></td>
                            <td style="padding: 5px 0;">{language}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>日期範圍:</strong></td>
                            <td style="padding: 5px 0;">{date_range}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>產生時間:</strong></td>
                            <td style="padding: 5px 0;">{generated_time} (Asia/Taipei)</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>文章數量:</strong></td>
                            <td style="padding: 5px 0;">{len(articles)} 篇</td>
                        </tr>
                    </table>
                </div>

                <!-- Articles -->
                <div style="padding: 30px;">
                    <h2 style="color: #333; font-size: 18px; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #667eea;">
                        📋 文章列表
                    </h2>
                    {articles_html}
                </div>

                <!-- Footer -->
                <div style="padding: 20px 30px; background-color: #f8f9fa; text-align: center; color: #888; font-size: 12px;">
                    <p style="margin: 0;">此郵件由「每日新聞自動摘要系統」自動產生</p>
                    <p style="margin: 5px 0 0 0;">Powered by FastAPI + Google News RSS</p>
                </div>

            </div>
        </body>
        </html>
        '''

        return html

    def _escape_html(self, text: str) -> str:
        """
        跳脫 HTML 特殊字元
        """
        if not text:
            return ''
        return (
            text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;')
        )
