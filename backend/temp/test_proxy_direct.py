# -*- coding: utf-8 -*-
import sys
import os
import requests
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_ingestion import get_db_connection

# Test fetching attachment via the OAuth method
p_id = '75a367d8-697f-476d-b60a-f2120f7bcccd'
conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT trello_api_key, trello_token FROM board_integrations WHERE project_id = %s", (p_id,))
t_key, t_token = cur.fetchone()
cur.close()
conn.close()

url = 'https://trello.com/1/cards/6aa79490004d1c2dcb1e1c5c/attachments/6aaa1239ab6df943e7ed419e/previews/6aaa123aab6df943e7ed41fe/download/image.webp'
headers = {
    'Authorization': f'OAuth oauth_consumer_key="{t_key}", oauth_token="{t_token}"'
}
res = requests.get(url, headers=headers, timeout=15)
print('Fetch status:', res.status_code, 'Content-Type:', res.headers.get('Content-Type'), 'Bytes:', len(res.content))
