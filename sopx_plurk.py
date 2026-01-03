import requests
from requests_oauthlib import OAuth1

PLURK_API = "https://www.plurk.com/APP"

def sopx_post_plurk(message: str, consumer_key: str, consumer_secret: str, token: str, token_secret: str):
    auth = OAuth1(consumer_key, consumer_secret, token, token_secret)
    url = f"{PLURK_API}/Timeline/plurkAdd"
    data = {
        "content": message,
        "qualifier": "shares"
    }
    r = requests.post(url, data=data, auth=auth, timeout=30)
    r.raise_for_status()
    return r.json()
