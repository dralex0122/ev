import os
import sys
import requests
import json
import time

def fetch_chargers_by_region(service_key, zcode, region_name):
    """
    특정 지역 코드(zcode)를 기준으로 페이지네이션을 수행하여
    해당 지역의 모든 충전기 데이터를 수집하는 헬퍼 함수
    """
    base_url = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
    page_no = 1
    num_of_rows = 500  # 서버에 무리를 주지 않는 안전한 분할 단위
    region_items = []

    print(f"📡 [{region_name}] 전기차 충전기 수집 중...")

    while True:
        full_url = (
            f"{base_url}?"
            f"serviceKey={service_key}"
            f"&pageNo={page_no}"
            f"&numOfRows={num_of_rows}"
            f"&zcode={zcode}"  # 지역코드 필터링
            f"&dataType=JSON"
        )

        max_retries = 3
        page_success = False
        items = []
        items_dict = {}
        total_count = 0

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(full_url, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    items_dict = data.get("items", {})

                    if not items_dict or "item" not in items_dict:
                        page_success = True
                        break

                    items = items_dict["item"]
                    if not items:
                        page_success = True
                        break

                    region_items.extend(items)
                    total_count = int(data.get("totalCount", 0))

                    if len(region_items) >= total_count:
                        page_success = True
                        break

                    page_success = True
                    break
                else:
                    time.sleep(3)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                time.sleep(5)
            except Exception:
                break

        if not page_success:
            print(f"  ❌ [{region_name}] {page_no}페이지 수집 실패로 다음 페이지로 건너뜁니다.")

        # 데이터가 완전히 바닥나면 루프 탈출
        if page_success and (not items_dict or "item" not in items_dict or not items or len(region_items) >= total_count):
            break

        page_no += 1
        time.sleep(0.4)  # 연속 호출 시 정부 서버 차단 방지 매너 타임

    print(f"  ✅ [{region_name}] 수집 완료 (누적 충전기 수: {len(region_items)}대)")
    return region_items


def generate_geojson_for_metropolitan_areas(service_key, output_filename="metropolitan_ev_stations.geojson"):
    """
    서울 및 6대 광역시의 데이터를 순차 수집한 뒤, 충전소 단위로 그룹화하고
    GeoJSON 포맷 파일로 변환하여 저장하는 메인 분석 함수
    """
    # 1. 가이드북 21페이지 기준 수집 대상 지역 코드 리스트 정의
    target_regions = {
        "11": "서울특별시",
        "26": "부산광역시",
        "27": "대구광역시",
        "28": "인천광역시",
        "12": "전남광주통합특별시",
        "30": "대전광역시",
        "31": "울산광역시"
    }

    all_raw_chargers = []

    # [1단계] 7대 대도시 데이터 분할 크롤링 수행
    start_time = time.time()
    for zcode, region_name in target_regions.items():
        region_data = fetch_chargers_by_region(service_key, zcode, region_name)
        all_raw_chargers.extend(region_data)
        time.sleep(1.0)  # 지역 교체 시 안정적인 리프레시 대기

    print(f"\n==================================================")
    print(f"📊 1차 데이터 수집 완료 (총 {len(all_raw_chargers)}개의 충전기 로드됨)")
    print(f"==================================================")

    # [2단계] 개별 충전기 데이터를 충전소(statId) 기준으로 그룹화 및 사양별 분류
    stations = {}

    for item in all_raw_chargers:
        stat_id = item.get('statId')
        if not stat_id:
            continue

        # 위경도 결측치 및 오류 방지 필터링
        try:
            lat = float(item.get('lat', 0.0))
            lng = float(item.get('lng', 0.0))
            if lat == 0.0 or lng == 0.0:
                continue
        except (TypeError, ValueError):
            continue  # 좌표 형식이 잘못된 충전기는 지오메트리 구성을 위해 과감히 제외

        # 충전용량 분기 (50kW 기준 완속/급속 분할)
        output_val = item.get('output')
        try:
            kw = float(output_val) if output_val else 0.0
        except ValueError:
            kw = 7.0  # 결측치 디폴트 처리

        is_slow = kw < 50.0

        if stat_id not in stations:
            stations[stat_id] = {
                'name': item.get('statNm', '이름 없음'),
                'address': item.get('addr', '주소 없음'),
                'lat': lat,
                'lng': lng,
                'slow_count': 1 if is_slow else 0,
                'fast_count': 0 if is_slow else 1,
                'total_count': 1
            }
        else:
            stations[stat_id]['total_count'] += 1
            if is_slow:
                stations[stat_id]['slow_count'] += 1
            else:
                stations[stat_id]['fast_count'] += 1

    # [3단계] 지리 공간 정보 표준인 GeoJSON 포맷으로 변환
    features = []

    for stat_id, info in stations.items():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                # ⚠️ 아주 중요: GeoJSON 좌표계의 순서는 무조건 [경도(Longitude), 위도(Latitude)] 입니다.
                "coordinates": [info['lng'], info['lat']]
            },
            "properties": {
                "station_id": stat_id,
                "station_name": info['name'],
                "address": info['address'],
                "slow_charger_count": info['slow_count'],
                "fast_charger_count": info['fast_count'],
                "total_charger_count": info['total_count']
            }
        }
        features.append(feature)

    geojson_structure = {
        "type": "FeatureCollection",
        "features": features
    }

    # [4단계] GeoJSON 파일 저장
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(geojson_structure, f, ensure_ascii=False, indent=2)

    end_time = time.time()
    elapsed_time = (end_time - start_time) / 60

    print(f"\n==================================================")
    print(f"🎉 GeoJSON 공간 마스터 데이터 생성 완료!")
    print(f" - 파일명: {output_filename}")
    print(f" - 고유 충전소 수: {len(stations)}개소 공간 매핑 완료")
    print(f" - 소요 시간: {elapsed_time:.1f}분")
    print(f"==================================================")

# ==========================================
# 하단 실행 제어부
# ==========================================
if __name__ == "__main__":
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)
    generate_geojson_for_metropolitan_areas(service_key)
