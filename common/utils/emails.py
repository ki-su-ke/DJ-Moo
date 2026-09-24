from typing import Literal
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


EmailFormat = Literal["both", "html", "text"]
"""
送信するメールのフォーマットを規定するリテラル

- "both"・・・htmlとtextメールの両方　規定値  
- "html"・・・htmlメールのみ  
- "text"・・・textメールのみ  
"""

def send_templated_email(
    subject: str,
    template_prefix: str,
    context: dict,
    recipient_list: list[str],
    fmt: EmailFormat = "both",
    from_email: str | None = None,
) -> bool:
    """
    テンプレートを使用した共通メール送信関数

    args:
        subject: 件名
        template_prefix: テンプレートのパスプレフィックス(例: 'emails/welcome')
        context: テンプレートに渡すコンテキスト
        recipient_list: 送信先アドレスのリスト
        fmt: 送信フォーマット("both" or "text" or "html")
        from_email: 送信元(省略時は settings.DEFAULT_FROM_EMAIL)
    
    returns:
        送信成功時 True, 失敗時 False
    """
    from_email = from_email or settings.DEFAULT_FROM_EMAIL

    try:
        # textメールのみの場合
        if fmt == "text":
            text_content = render_to_string(f"{template_prefix}.txt", context)
            msg = EmailMessage(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=recipient_list,
            )

        # htmlメールのみの場合
        elif fmt == "html":
            html_content = render_to_string(f"{template_prefix}.html", context)
            msg = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=from_email,
                to=recipient_list,
            )
            msg.content_subtype = "html"  # メインのコンテンツタイプをHTMLにセット
            
        # 両方の場合
        else:
            text_content = render_to_string(f"{template_prefix}.txt", context)
            html_content = render_to_string(f"{template_prefix}.html", context)
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=recipient_list,
            )
            msg.attach_alternative(html_content, "text/html")
        
        msg.send(fail_silently=False)
        return True

    except Exception as e:
        logger.error(f"メール送信エラー ({template_prefix}): {e}", exc_info=True)
        return False
