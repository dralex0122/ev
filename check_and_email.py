"""
매일 아침 9시(KST)에 전날(00시~23시) 7개 도시 가용률 수집이 정상적으로
완료됐는지 점검하고, 결과를 이메일로 보내는 스크립트. cron으로 매일 실행.

- 도시별 기대 구/군 개수는 district_availability_snapshot.py의
  KNOWN_DISTRICTS를 그대로 가져와서 사용 (이중 관리 방지)
- 인천광역시처럼 KNOWN_DISTRICTS에 없는 도시는 폴더 존재 여부만 확인
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


def check_date(date_folder):
    total_found = 0
    total_expected = 0
    missing_hours = []

    for hour in range(24):
        hour_label = f"{hour:02d}시"
        hour_ok = True
        hour_detail = []

        for city_name, _ in CITIES:
            city_dir = os.path.join(BASE_DIR, date_folder, city_name, hour_label)
            if not os.path.isdir(city_dir):
                hour_ok = False
                hour_detail.append(f"{city_name}: 폴더 없음")
                continue

            files = [f for f in os.listdir(city_dir) if f.endswith(".json")]
            total_found += len(files)

            expected = len(KNOWN_DISTRICTS[city_name]) if city_name in KNOWN_DISTRICTS else None
            if expected is not None:
                total_expected += expected
                if len(files) < expected:
                    hour_ok = False
                    hour_detail.append(f"{city_name}: {len(files)}/{expected}개")
            else:
                total_expected += len(files)

        anomalies_path = os.path.join(BASE_DIR, date_folder, f"anomalies_{hour_label}.json")
        if not os.path.isfile(anomalies_path):
            hour_ok = False
            hour_detail.append("anomalies 파일 없음")

        if not hour_ok:
            missing_hours.append((hour_label, hour_detail))

    return total_expected, total_found, missing_hours


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

    total_expected, total_found, missing_hours = check_date(date_folder)

    if not missing_hours:
        subject = f"[EV충전소] {date_str} 가용률 수집 정상 완료"
        body = (
            f"{date_str} 00시~23시, 7개 도시 전체 정상 수집 확인됐습니다.\n\n"
            f"총 수집 파일 수: {total_found}개 (기대치 {total_expected}개)"
        )
    else:
        subject = f"[EV충전소] {date_str} 가용률 수집 이상 발견 ({len(missing_hours)}개 시간대)"
        lines = [f"{date_str} 수집 점검 결과 문제가 발견됐습니다.\n"]
        for hour_label, detail in missing_hours:
            lines.append(f"- {hour_label}: {', '.join(detail)}")
        lines.append(f"\n총 수집 파일 수: {total_found}개 (기대치 {total_expected}개)")
        body = "\n".join(lines)

    print(subject)
    print(body)
    send_email(subject, body)
    print("이메일 발송 완료")


if __name__ == "__main__":
    main()
