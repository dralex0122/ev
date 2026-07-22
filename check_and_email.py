"""
매일 아침 9시(KST)에 전날(00시~23시) 7개 도시 가용률 수집이 정상적으로
완료됐는지 점검하고, 결과를 이메일로 보내는 스크립트. cron으로 매일 실행.

- 도시별 기대 구/군 개수는 district_availability_snapshot.py의
  KNOWN_DISTRICTS를 그대로 가져와서 사용 (이중 관리 방지)
- 인천광역시처럼 KNOWN_DISTRICTS에 없는 도시는 폴더 존재 여부만 확인
- 2026-07-22부터 수집 간격이 1시간 -> 10분으로 바뀌면서 저장 구조도
  "<도시>/HH시/*.json" -> "<도시>/HH시/MM분/*.json"(시간 폴더 아래 분 단위
  하위 폴더)으로 바뀜. 두 형식이 섞인 날짜(전환일)도 정상 처리하도록,
  HH시 폴더 밑에 json이 직접 있으면 레거시로, 없으면 10분 단위 6개
  하위 폴더로 판단
- Gmail SMTP(앱 비밀번호) 사용. EMAIL_FROM/EMAIL_TO/EMAIL_APP_PASSWORD
  환경변수에서 읽음 (하드코딩하지 않음)
"""

import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from district_availability_snapshot import CITIES, KNOWN_DISTRICTS

KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MINUTE_SLOTS = list(range(0, 60, 10))


def check_hour(date_folder, hour):
    """해당 시간(0~23)에 대해 문제 있는 도시 목록과 파일 수를 반환.
    레거시(HH시 폴더에 json 직접) 방식과 신규(HH시/MM분 하위 폴더) 방식을 모두 지원."""
    hour_label = f"{hour:02d}시"
    minute_labels = [f"{m:02d}분" for m in MINUTE_SLOTS]

    bad_cities = []
    found = 0
    expected = 0

    for city_name, _ in CITIES:
        exp = len(KNOWN_DISTRICTS[city_name]) if city_name in KNOWN_DISTRICTS else None
        hour_dir = os.path.join(BASE_DIR, date_folder, city_name, hour_label)

        if not os.path.isdir(hour_dir):
            bad_cities.append(city_name)
            continue

        direct_files = [f for f in os.listdir(hour_dir) if f.endswith(".json")]
        if direct_files:
            found += len(direct_files)
            expected += exp if exp is not None else len(direct_files)
            if exp is not None and len(direct_files) < exp:
                bad_cities.append(city_name)
            continue

        slot_ok = True
        for ml in minute_labels:
            d = os.path.join(hour_dir, ml)
            if not os.path.isdir(d):
                slot_ok = False
                continue
            files = [f for f in os.listdir(d) if f.endswith(".json")]
            found += len(files)
            expected += exp if exp is not None else len(files)
            if exp is not None and len(files) < exp:
                slot_ok = False
        if not slot_ok:
            bad_cities.append(city_name)

    return bad_cities, found, expected


def check_anomalies_file(date_folder, hour):
    hour_label = f"{hour:02d}시"
    legacy_path = os.path.join(BASE_DIR, date_folder, f"anomalies_{hour_label}.json")
    if os.path.isfile(legacy_path):
        return True
    hour_dir = os.path.join(BASE_DIR, date_folder, hour_label)
    return all(
        os.path.isfile(os.path.join(hour_dir, f"anomalies_{m:02d}분.json"))
        for m in MINUTE_SLOTS
    )


def check_date(date_folder):
    total_found = 0
    total_expected = 0
    bad_hours_by_city = {city_name: [] for city_name, _ in CITIES}
    anomalies_missing_hours = []

    for hour in range(24):
        hour_label = f"{hour:02d}시"
        bad_cities, found, expected = check_hour(date_folder, hour)
        total_found += found
        total_expected += expected
        for city_name in bad_cities:
            bad_hours_by_city[city_name].append(hour_label)

        if not check_anomalies_file(date_folder, hour):
            anomalies_missing_hours.append(hour_label)

    bad_hours_by_city = {c: h for c, h in bad_hours_by_city.items() if h}
    return total_expected, total_found, bad_hours_by_city, anomalies_missing_hours


def send_email(subject, body):
    from_addr = os.environ.get("EMAIL_FROM")
    to_addr = os.environ.get("EMAIL_TO")
    app_password_raw = os.environ.get("EMAIL_APP_PASSWORD")
    # Gmail 앱 비밀번호 표시상의 공백(줄바꿈 없는 공백 포함) 제거
    app_password = "".join(app_password_raw.split()) if app_password_raw else None
    if not (from_addr and to_addr and app_password):
        print("이메일 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(from_addr, app_password)
        server.sendmail(from_addr, [to_addr], msg.as_string())


def main():
    now_kst = datetime.now(KST)
    yesterday = now_kst - timedelta(days=1)
    date_folder = yesterday.strftime("%y%m%d")
    date_str = yesterday.strftime("%Y-%m-%d")

    total_expected, total_found, bad_hours_by_city, anomalies_missing_hours = check_date(date_folder)

    if not bad_hours_by_city and not anomalies_missing_hours:
        subject = f"[EV충전소] {date_str} 가용률 수집"
        body = "이상 없습니다."
    else:
        subject = f"[EV충전소] {date_str} 가용률 수집 이상 발견"
        lines = []
        for city_name, _ in CITIES:
            hours = bad_hours_by_city.get(city_name)
            if hours:
                lines.append(f"{city_name}: {', '.join(hours)} 이상")
        if anomalies_missing_hours:
            lines.append(f"anomalies 파일 없음: {', '.join(anomalies_missing_hours)}")
        body = "\n".join(lines)

    print(subject)
    print(body)
    send_email(subject, body)
    print("이메일 발송 완료")


if __name__ == "__main__":
    main()
