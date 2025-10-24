import os
import requests

# Thay đổi theo thực tế nếu bạn có token để tăng hạn mức truy cập
token = "github_token"

headers = {"Accept": "application/vnd.github+json"}
if token:
    headers["Authorization"] = f"Bearer {token}"

url = "https://api.github.com/repos/modin-project/modin/releases/tags/0.30.0"
resp = requests.get(url, headers=headers)
resp.raise_for_status()

data = resp.json()
body_markdown = data.get("body", "")
# print(f'keys = {data.keys()}')
print(body_markdown)
