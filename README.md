# 거울 OOTD 자동 기록기 (v0)

거울 옆에 둔 폰 카메라에 전신이 2초 이상 잡히면 사진을 찍어 날짜별로 저장하고, 달력으로 보여준다.
스펙: [SPEC.md](SPEC.md)

## 1. 폰 (안드로이드)

1. Play 스토어에서 **IP Webcam** 설치
2. 앱 설정
   - 연결 설정 → 로그인/비밀번호 설정 (같은 Wi-Fi의 다른 사람이 못 보게)
   - 전원 관리 → 화면 꺼짐 상태에서도 동작하도록 설정
   - 비디오 설정 → 해상도는 낮게 (예: 640×480). 사람 감지용이라 낮아도 되고 PC 부담이 줄어든다.
   - 사진 해상도 → **최대**, 품질 → **100**. 저장되는 사진은 이 설정으로 찍힌다.
3. 맨 아래 **서버 시작** → 화면에 나오는 주소(예: `http://192.168.0.10:8080`) 확인
4. 충전기를 꽂고 거울 옆에 세로로 고정. 평소 서는 자리에서 머리부터 발끝까지 보이게.
5. 폰의 배터리 최적화에서 IP Webcam을 **제외**

## 2. PC

Python 3.10 이상 필요.

```bash
pip install -r requirements.txt
cp config.example.json config.json   # Windows: copy config.example.json config.json
```

`config.json`에서 수정:

| 항목 | 설명 |
|---|---|
| `camera_url` | 사람 감지용 영상. 폰 주소 + `/shot.jpg` (예: `http://192.168.0.10:8080/shot.jpg`). 홈캠이면 `rtsp://...` 주소 |
| `photo_url` | 저장용 고화질 사진. 폰 주소 + `/photo.jpg`. 비워 두면 감지용 프레임을 저장 |
| `camera_user`, `camera_password` | IP Webcam에서 정한 로그인/비밀번호 |
| `hold_sec` | 전신이 몇 초 이어지면 찍을지 (기본 2) |
| `cooldown_min` | 찍은 뒤 몇 분 쉴지 (기본 30) |
| `day_start_hour` | 하루 시작 시각 (기본 4시) |

실행:

```bash
python main.py
```

브라우저에서 http://127.0.0.1:5000 을 열면 달력이 나온다. 처음 실행할 때 포즈 모델(약 5MB)을 자동으로 받는다.
사진은 `photos/날짜/시각.jpg`로 저장된다. 폰이 찍은 JPEG 원본을 다시 압축하지 않고 그대로 저장한다.
