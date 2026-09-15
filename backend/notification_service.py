import os
import logging
import requests

logger = logging.getLogger("notification_service")

class MultiChannelNotifier:
    """
    Multi-channel notification dispatcher supporting Slack, Telegram, LINE Notify, and Teams
    """
    
    @staticmethod
    def send_slack(webhook_url: str, message: str, title: str = "Spectra QA Notification") -> bool:
        if not webhook_url:
            return False
        payload = {
            "text": f"*{title}*\n{message}"
        }
        try:
            res = requests.post(webhook_url, json=payload, timeout=5)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    @staticmethod
    def send_teams(webhook_url: str, message: str, title: str = "Spectra QA Notification") -> bool:
        if not webhook_url:
            return False
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "8B5CF6",
            "summary": title,
            "sections": [{
                "activityTitle": f"🤖 {title}",
                "text": message
            }]
        }
        try:
            res = requests.post(webhook_url, json=payload, timeout=5)
            return res.status_code in [200, 202]
        except Exception as e:
            logger.error(f"Failed to send Teams notification: {e}")
            return False

    @staticmethod
    def send_line_notify(token: str, message: str) -> bool:
        if not token:
            return False
        headers = {
            "Authorization": f"Bearer {token}"
        }
        data = {
            "message": f"\n[Spectra QA Alert]\n{message}"
        }
        try:
            res = requests.post("https://notify-api.line.me/api/notify", headers=headers, data=data, timeout=5)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send LINE Notify: {e}")
            return False

    @staticmethod
    def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
        if not bot_token or not chat_id:
            return False
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": f"🤖 *Spectra QA Notification*\n\n{message}",
            "parse_mode": "Markdown"
        }
        try:
            res = requests.post(url, json=payload, timeout=5)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    @classmethod
    def dispatch_all(cls, channels: dict, message: str, title: str = "Spectra QA Notification") -> dict:
        results = {}
        if "slack" in channels and channels["slack"].get("webhook_url"):
            results["slack"] = cls.send_slack(channels["slack"]["webhook_url"], message, title)
        
        if "teams" in channels and channels["teams"].get("webhook_url"):
            results["teams"] = cls.send_teams(channels["teams"]["webhook_url"], message, title)
            
        if "line" in channels and channels["line"].get("token"):
            results["line"] = cls.send_line_notify(channels["line"]["token"], message)
            
        if "telegram" in channels and channels["telegram"].get("bot_token") and channels["telegram"].get("chat_id"):
            results["telegram"] = cls.send_telegram(channels["telegram"]["bot_token"], channels["telegram"]["chat_id"], message)
            
        return results
