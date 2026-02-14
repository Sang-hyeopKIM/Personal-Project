# 항공권 특가 알리미 ✈️

동남아/일본 지역 항공권 가격을 자동으로 모니터링하고, 설정한 기준 이하의 특가가 발견되면 알림을 보내주는 프로그램입니다.

## 주요 기능

- **다중 노선 검색**: 일본(도쿄, 오사카, 후쿠오카), 베트남(다낭, 하노이, 호치민) 등
- **기간별 검색**: 여름방학, 추석연휴 등 원하는 기간 설정
- **4인 가족 기준**: 성인 2명 + 아동 2명(10세, 6세) 왕복 검색
- **가격 알림**: 설정 금액 이하 시 이메일/텔레그램 알림
- **가격 이력 추적**: SQLite DB에 가격 변동 기록 및 최저가 추적
- **자동 실행**: 스케줄러를 통한 주기적 자동 검색

## 사전 준비

### 1. Amadeus API 키 발급 (무료)

1. [Amadeus for Developers](https://developers.amadeus.com/) 가입
2. "My Self-Service Workspace" → "Create New App" 클릭
3. API Key와 API Secret 복사
4. **무료 티어**: 월 500회 API 호출 가능

### 2. (선택) 텔레그램 봇 설정

1. 텔레그램에서 [@BotFather](https://t.me/BotFather)에게 `/newbot` 명령
2. 봇 이름 설정 후 Bot Token 복사
3. [@userinfobot](https://t.me/userinfobot)에서 본인 Chat ID 확인

### 3. (선택) Gmail 앱 비밀번호

이메일 알림을 사용하려면:
1. Google 계정 → 보안 → 2단계 인증 활성화
2. 앱 비밀번호 생성 → 16자리 비밀번호 복사

## 설치

```bash
# 저장소 클론
git clone <repository-url>
cd Personal-Project

# Python 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 설정

```bash
# 예제 설정 파일 복사
cp config.example.yaml config.yaml

# 설정 파일 편집
vi config.yaml  # 또는 선호하는 에디터
```

`config.yaml`에서 반드시 수정해야 할 항목:

```yaml
amadeus_api:
  api_key: "실제_API_KEY"
  api_secret: "실제_API_SECRET"
```

### 검색 노선 커스터마이징

```yaml
routes:
  - origin: ICN          # 출발: 인천
    destination: NRT     # 도착: 나리타
    name: "도쿄 나리타"
```

### 알림 기준 설정

```yaml
alerts:
  NRT:
    threshold_total: 2000000       # 4인 총 200만원 이하 시 알림
    threshold_per_person: 500000   # 1인 50만원 이하 시 알림
```

## 사용법

### 1회 검색

```bash
python main.py
```

### 자동 주기 검색 (6시간마다)

```bash
python main.py --schedule
```

### 최저가 목록 조회

```bash
python main.py --best-deals
```

### 설정 파일 지정

```bash
python main.py --config /path/to/my-config.yaml
```

## 주요 공항 코드 참고

| 지역 | 공항 | 코드 |
|------|------|------|
| 인천 | 인천국제공항 | ICN |
| 김포 | 김포국제공항 | GMP |
| 도쿄 | 나리타 | NRT |
| 도쿄 | 하네다 | HND |
| 오사카 | 간사이 | KIX |
| 후쿠오카 | 후쿠오카 | FUK |
| 다낭 | 다낭 | DAD |
| 하노이 | 노이바이 | HAN |
| 호치민 | 떤선녓 | SGN |
| 방콕 | 수완나품 | BKK |
| 세부 | 막탄세부 | CEB |

## 프로젝트 구조

```
Personal-Project/
├── main.py              # 메인 실행 파일 (검색/스케줄러)
├── flight_checker.py    # Amadeus API 항공권 조회
├── price_tracker.py     # SQLite 가격 이력 추적
├── notifier.py          # 알림 (이메일/텔레그램/콘솔)
├── models.py            # 데이터 모델
├── config.example.yaml  # 설정 파일 예제
├── requirements.txt     # Python 의존성
└── README.md
```

## API 호출 횟수 관리

Amadeus 무료 티어는 월 500회입니다. 효율적으로 사용하려면:

- `sample_interval_days`를 늘려 검색 간격을 넓히기 (기본 3일)
- 검색 노선 수를 필요한 것만 유지
- `max_results_per_search`를 줄이기 (기본 3)
- `schedule.interval_hours`를 늘리기 (기본 6시간)

예시: 노선 3개 × 기간 1개(10일 범위, 3일 간격=4회) × 체류 3~5일(3가지) = 약 36회/실행

## 라이선스

MIT License
