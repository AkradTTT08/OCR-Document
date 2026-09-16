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

url = 'https://trello.com/1/cards/6aa79490004d1c2dcb1e1c5c/attachments/6aaa1239ab6df943e7ed419e/previews/6aaa123aab6df943e7ed41fe/download/image.webp'

res1 = requests.get(url, allow_redirects=True)
print('Direct fetch:', res1.status_code, res1.headers.get('Content-Type'), len(res1.content))

res2 = requests.get(url, params={'key': t_key, 'token': t_token}, allow_redirects=True)
print('Auth fetch:', res2.status_code, res2.headers.get('Content-Type'), len(res2.content))
if res2.history:
    print('Final redirect URL:', res2.url)
