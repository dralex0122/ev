import os
import time

import requests

key = os.environ.get("EV_SERVICE_KEY")
url = (
    "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
    f"?serviceKey={key}&pageNo=1&numOfRows=5&zcode=11&dataType=JSON"
)

attempt = 0
while True:
    attempt += 1
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and "items" in r.text:
            print(f"[{ts}] [{attempt}] 복구 확인! status={r.status_code}", flush=True)
            print(r.text[:300], flush=True)
            break
        else:
            print(f"[{ts}] [{attempt}] status={r.status_code}, 아직 정상 아님", flush=True)
    except Exception as e:
        print(f"[{ts}] [{attempt}] 여전히 실패: {type(e).__name__}", flush=True)
    time.sleep(60)

print("=== 감시 종료 ===", flush=True)
