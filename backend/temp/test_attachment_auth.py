# -*- coding: utf-8 -*-
import sys
import os
import requests
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_ingestion import get_db_connection

conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT trello_api_key, trello_token FROM board_integrations WHERE project_id = '75a367d8-697f-476d-b60a-f2120f7bcccd'")
t_key, t_token = cur.fetchone()
cur.close()
conn.close()

# Let's test with api.trello.com
url1 = 'https://api.trello.com/1/cards/6aa79490004d1c2dcb1e1c5c/attachments/6aaa1239ab6df943e7ed419e'
r1 = requests.get(url1, params={'key': t_key, 'token': t_token})
print('Attachment info API status:', r1.status_code, r1.json() if r1.ok else r1.text)

# Let's test download with Authorization header
headers = {
    'Authorization': f'OAuth oauth_consumer_key="{t_key}", oauth_token="{t_token}"'
}
url_dl = 'https://trello.com/1/cards/6aa79490004d1c2dcb1e1c5c/attachments/6aaa1239ab6df943e7ed419e/previews/6aaa123aab6df943e7ed41fe/download/image.webp'
r2 = requests.get(url_dl, headers=headers, allow_redirects=True)
print('Download with OAuth header status:', r2.status_code, r2.headers.get('Content-Type'), len(r2.content))
if r2.ok:
    print('Success! Content length:', len(r2.content))
