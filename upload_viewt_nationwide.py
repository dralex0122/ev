import os, subprocess, glob, time

nas_password = os.environ.get('NAS_PASSWORD')
env = os.environ.copy(); env['PASSWD'] = nas_password

region_kor = {
    'seoul':'서울','busan':'부산','daegu':'대구','incheon':'인천','gwangju':'광주',
    'daejeon':'대전','ulsan':'울산','sejong':'세종','gyeonggi':'경기','gangwon':'강원',
    'chungbuk':'충북','chungnam':'충남','jeonbuk':'전북','jeonnam':'전남',
    'gyeongbuk':'경북','gyeongnam':'경남','jeju':'제주',
}

files = sorted(glob.glob('viewt_percentile_speed_nationwide_labeled/*.csv'))
groups = {}
for path in files:
    fname = os.path.basename(path)
    parts = fname.split('_')
    yymm, region_en = parts[0], parts[1]
    year = '20' + yymm[:2]
    groups.setdefault((year, region_en), []).append((path, fname))

print(f"총 {len(files)}개 파일, {len(groups)}개 (연도,지역) 그룹")

ok_groups = 0
fail_groups = []
for i, ((year, region_en), flist) in enumerate(sorted(groups.items()), start=1):
    region = region_kor[region_en]
    cmds = [f'cd "View-T/월 데이터"', f'mkdir "{year}"', f'cd "{year}"', f'mkdir "{region}"', f'cd "{region}"']
    for path, fname in flist:
        cmds.append(f'put "{path}" "{fname}"')
    cmd_str = '; '.join(cmds)

    success = False
    for attempt in range(3):
        r = subprocess.run(['smbclient', '//163.180.10.191/cowork', '-U', 'dralex01', '-c', cmd_str],
                            env=env, capture_output=True, text=True)
        out = r.stdout + r.stderr
        bad = [l for l in out.splitlines() if 'NT_STATUS' in l and 'NAME_COLLISION' not in l]
        if r.returncode == 0 and not bad:
            success = True
            break
        time.sleep(3)
    if success:
        ok_groups += 1
    else:
        fail_groups.append((year, region_en))
    print(f"[{i}/{len(groups)}] {year}/{region} ({len(flist)}개 파일) {'완료' if success else '실패'}")

print(f"=== 그룹 완료: {ok_groups}/{len(groups)} ===")
if fail_groups:
    print("실패:", fail_groups)
