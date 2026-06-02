import urllib.request
import json

def test_api():
    url = "http://127.0.0.1:8000/api/v1/discovery/vertex-ai/sync"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            data = json.loads(res_body)
            print(f"API Sync Response: {data}")
    except Exception as e:
        print(f"Failed to call API: {e}")

if __name__ == "__main__":
    test_api()
