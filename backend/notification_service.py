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

# ==============================================================================
# User-Specific In-App Notification Service (PostgreSQL Database)
# Ensures notifications are delivered strictly to the user who triggered the task
# ==============================================================================

def ensure_notifications_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_notifications (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            type VARCHAR(50) DEFAULT 'info',
            icon VARCHAR(50) DEFAULT '🔔',
            action_view VARCHAR(100),
            action_payload JSONB,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_user_notifications_user ON user_notifications(username, is_read, created_at DESC);
    """)

def send_user_notification(username: str, title: str, message: str, noti_type: str = 'info', icon: str = '🔔', action_view: str = None, action_payload: dict = None) -> bool:
    """Send and persist notification exclusively for the specified user."""
    if not username:
        logger.warning("send_user_notification called without username; skipping notification.")
        return False
    try:
        import json
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        ensure_notifications_table(cursor)
        cursor.execute("""
            INSERT INTO user_notifications (username, title, message, type, icon, action_view, action_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
        """, (username, title, message, noti_type, icon, action_view, json.dumps(action_payload or {})))
        inserted_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"User notification #{inserted_id} created for '{username}': {title}")
        return True
    except Exception as e:
        logger.error(f"Failed to send user notification to '{username}': {e}", exc_info=True)
        return False

def get_user_notifications(username: str, limit: int = 50) -> dict:
    """Retrieve notifications strictly belonging to this user."""
    if not username:
        return {"notifications": [], "unread_count": 0}
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        ensure_notifications_table(cursor)
        cursor.execute("""
            SELECT id, title, message, type, icon, action_view, action_payload, is_read, created_at
            FROM user_notifications
            WHERE username = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (username, limit))
        rows = cursor.fetchall()
        
        cursor.execute("""
            SELECT COUNT(*) FROM user_notifications
            WHERE username = %s AND is_read = FALSE
        """, (username,))
        unread_count = cursor.fetchone()[0] or 0
        
        cursor.close()
        conn.close()
        
        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "title": r[1],
                "message": r[2],
                "type": r[3] or "info",
                "icon": r[4] or "🔔",
                "actionView": r[5],
                "actionPayload": r[6] if isinstance(r[6], dict) else {},
                "read": bool(r[7]),
                "created_at": r[8].isoformat() if r[8] else None,
                "time": r[8].strftime("%d/%m/%Y %H:%M") if r[8] else "เมื่อสักครู่"
            })
        return {"notifications": items, "unread_count": unread_count}
    except Exception as e:
        logger.error(f"Failed to fetch user notifications for '{username}': {e}", exc_info=True)
        return {"notifications": [], "unread_count": 0}

def mark_user_notification_read(username: str, noti_id: int = None) -> bool:
    """Mark one or all notifications as read for this user."""
    if not username:
        return False
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        ensure_notifications_table(cursor)
        if noti_id:
            cursor.execute("UPDATE user_notifications SET is_read = TRUE WHERE username = %s AND id = %s", (username, noti_id))
        else:
            cursor.execute("UPDATE user_notifications SET is_read = TRUE WHERE username = %s", (username,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to mark notification read for '{username}': {e}")
        return False

def delete_user_notification(username: str, noti_id: int) -> bool:
    """Delete a single notification belonging to this user."""
    if not username or not noti_id:
        return False
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        ensure_notifications_table(cursor)
        cursor.execute("DELETE FROM user_notifications WHERE username = %s AND id = %s", (username, noti_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to delete notification {noti_id} for '{username}': {e}")
        return False

def clear_user_notifications(username: str) -> bool:
    """Clear all notifications belonging to this user."""
    if not username:
        return False
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        ensure_notifications_table(cursor)
        cursor.execute("DELETE FROM user_notifications WHERE username = %s", (username,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to clear notifications for '{username}': {e}")
        return False

