import requests
from requests_oauthlib import OAuth1

PLURK_API = "https://www.plurk.com/APP"

def sopx_post_plurk(message: str, consumer_key: str, consumer_secret: str, token: str, token_secret: str):
    """
    Safe Plurk post:
    - Returns JSON on success
    - Returns None on failure (and prints error)
    - Never raises to crash GitHub Actions
    """
    auth = OAuth1(consumer_key, consumer_secret, token, token_secret)
    url = f"{PLURK_API}/Timeline/plurkAdd"
    data = {"content": message, "qualifier": "shares"}

    try:
        r = requests.post(url, data=data, auth=auth, timeout=30)
        if r.status_code >= 400:
            # Print body to help debug (Plurk often returns useful message)
            print(f"[Plurk] HTTP {r.status_code}: {r.text}")
            return None
        return r.json()
    except Exception as e:
        print(f"[Plurk] Post failed: {e}")
        return None
