import requests
import time
import os

def request_with_retry(url: str, headers: dict = None, retries: int = 3, allow_redirects: bool = True):
    for i in range(retries + 1):
        try:
            res = requests.get(url, headers=headers, allow_redirects=allow_redirects, timeout=30)
            if res.status_code < 400:
                return res
        except Exception as e:
            if i == retries:
                raise e
        time.sleep(2 ** i)
    raise Exception("Unreachable")

def download_file_pro(url: str, output_path: str, expected_size: int = None) -> str:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    res = request_with_retry(url, headers=headers, allow_redirects=True)
    with open(output_path, 'wb') as f:
        f.write(res.content)
    if expected_size and os.path.getsize(output_path) != expected_size:
        raise Exception(f"Size mismatch: {os.path.getsize(output_path)}/{expected_size}")
    return output_path
