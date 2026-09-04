"""
cowork 공유의 View-T 폴더 전체(월 데이터 + 도로망 네트워크, 약 1,804개 파일/51GB)를
별도 최상위 공유인 data로 이동. SGIS 격자데이터 이전과 동일한 방식:
smbclient로 cowork에서 서버 로컬로 recursive get -> data 공유로 recursive put
-> 개수 확인 -> cowork 원본 삭제.
"""
import os
import subprocess

NAS_PASSWORD = os.environ.get("NAS_PASSWORD")
ENV = os.environ.copy()
ENV["PASSWD"] = NAS_PASSWORD

LOCAL_TMP = "/tmp/viewt_migrate"


def run_smb(share, cmd_str):
    r = subprocess.run(
        ["smbclient", f"//{os.environ.get('NAS_HOST')}/{share}", "-U", "dralex01", "-c", cmd_str],
        env=ENV, capture_output=True, text=True,
    )
    return r


def main():
    os.makedirs(LOCAL_TMP, exist_ok=True)

    print("=== 1) cowork에서 View-T 전체 다운로드 ===")
    cmd = f'recurse ON; prompt OFF; lcd {LOCAL_TMP}; cd "View-T"; mget *'
    r = run_smb("cowork", cmd)
    print(r.stdout[-1500:])
    if r.stderr.strip():
        print("STDERR:", r.stderr[-1000:])

    total_files = sum(len(files) for _, _, files in os.walk(LOCAL_TMP))
    print(f"로컬 다운로드 완료: {total_files}개 파일")

    print("=== 2) data 공유로 업로드 ===")
    # smbclient recurse+mput은 로컬 하위 폴더까지 그대로 원격에 만들어가며 올려줌
    cmd = f'recurse ON; prompt OFF; lcd {LOCAL_TMP}; mkdir "View-T"; cd "View-T"; mput *'
    r = run_smb("data", cmd)
    print(r.stdout[-1500:])
    if r.stderr.strip():
        print("STDERR:", r.stderr[-1000:])

    print("=== 3) 결과 확인 ===")
    r = run_smb("data", 'cd "View-T"; ls')
    print(r.stdout)


if __name__ == "__main__":
    main()
