# CASCADA CP 통계 분석 및 조회 시스템 (CASCADA Analytics)

이 프로젝트는 **삼성 TV 플러스(Samsung TV Plus)**의 CP(Content Provider)용 통계 데이터인 **'CASCADA'** 지표를 효율적으로 정제하고, 로컬 DuckDB에 적재한 후 시각적으로 분석 및 조회할 수 있는 대시보드 웹 애플리케이션입니다.

---

## 📂 프로젝트 폴더 구조

```text
cascada_analysis/
├── .venv/                  # Python 가상환경
├── data/                   # 데이터 디렉토리
│   └── sample/             # 스키마 분석용 샘플 CSV 파일 위치
├── static/                 # 프론트엔드 정적 파일
│   ├── css/
│   │   └── style.css       # 미려한 다크 테마 커스텀 CSS
│   ├── js/
│   │   └── app.js          # 차트 시각화 및 API 연동 JS (Vanilla JS)
│   └── index.html          # 대시보드 SPA 메인 페이지
├── app.py                  # FastAPI 백엔드 웹 서버 및 REST API
├── import_data.py          # CSV 데이터를 DuckDB로 적재하는 ETL 스크립트
├── cascada_analytics.db    # 로컬 DuckDB 데이터베이스 파일 (자동 생성)
└── README.md               # 프로젝트 매뉴얼
```

---

## 🛠 기술 스택

* **Backend**: Python 3.12, FastAPI, Uvicorn
* **Database**: DuckDB (인메모리 기반 컬럼 지향 파일 DB로 대용량 로그 연산에 최적화)
* **Frontend**: HTML5, Vanilla JS, Vanilla CSS, FontAwesome(아이콘), Chart.js(차트 시각화)

---

## 🚀 시작 가이드

### 1. 가상환경 활성화 및 패키지 설치
프로젝트 루트 폴더에서 아래 명령을 실행하여 필수 라이브러리를 설치합니다. (설정된 `.venv`가 있는 경우 바로 사용하실 수 있습니다.)
```bash
# 가상환경 활성화 (필요한 경우)
source .venv/bin/activate

# 패키지 설치 (이미 완료됨)
pip install duckdb pandas pyarrow fastapi uvicorn
```

### 2. CSV 데이터 적재 (ETL)
`data/` 폴더 하위에 대용량 CASCADA CSV 파일들을 배치한 뒤, 아래 명령어로 DuckDB(`cascada_analytics.db`)에 데이터를 정제하여 적재합니다.
* 중복 적재 방지 기능이 기본 탑재되어 있으며, `channel_id = 'ALL'` 등의 집계 제거 필터링이 적용됩니다.

```bash
# 기본 데이터 적재 (data/ 하위 파일 대상, sample/ 폴더는 건너뜀)
python import_data.py

# 샘플 데이터까지 포함하여 적재하고자 할 경우
python import_data.py --include-samples

# 기존 적재 이력을 무시하고 전체 재적재(강제 갱신)하고자 할 경우
python import_data.py --force
```

### 3. 웹 애플리케이션 실행
데이터 적재 완료 후, 아래 명령어로 대시보드 웹 서버를 실행합니다.
```bash
python app.py
```
서버가 시작되면 웹 브라우저를 통해 **[http://127.0.0.1:8000](http://127.0.0.1:8000)** 에 접속합니다.

### 4. DuckDB CLI를 이용한 직접 조회 (선택사항)
별도의 웹 서버 구동 없이 터미널에서 직접 SQL로 데이터를 조회하고 싶다면 DuckDB CLI를 활용할 수 있습니다.
* **데이터베이스 접속 (읽기 전용 모드로 웹 서버와 동시 실행 가능)**:
  ```bash
  # duckdb가 시스템에 설치되어 있을 경우
  duckdb -readonly cascada_analytics.db
  ```
* **기본 사용법 및 쿼리 예시**:
  ```sql
  -- 테이블 목록 조회
  .tables

  -- 테이블 스키마 상세 조회
  DESCRIBE cascada_metrics;

  -- 쿼리 테스트
  SELECT platform, SUM(users) AS total_users 
  FROM cascada_metrics 
  GROUP BY platform 
  ORDER BY total_users DESC;

  -- 종료
  .exit
  ```

---

## 📊 주요 지표 정의

### 1. Users (사용자)
* **Total Users (`users`)**: 플랫폼/채널별 총 유입 사용자 수
* **Active Users (>3m) (`active_users_playback_180`)**: 3분(180초) 이상 시청한 사용자 수
* **Active Users (>15m) (`active_users_playback_900`)**: 15분(900초) 이상 시청한 사용자 수

### 2. Viewing Time (시청 시간 - 단위: Hour)
* **Total Viewing Time (`viewing_time`)**: 총 시청 시간
* **Active Viewing Time (>3m) (`active_viewing_time_180`)**: 3분 이상 시청 유저의 시청 시간 합계
* **Active Viewing Time (>15m) (`active_viewing_time_900`)**: 15분 이상 시청 유저의 시청 시간 합계
* **인당 평균 시청 시간 (Avg Viewing Time Per User)**:
  * 💡 대시보드 내 **토글 스위치**를 통해 두 가지 통계 관점으로 실시간 변환 조회할 수 있습니다.
  * **활성 사용자 기준 (Engagement - 기본값)**: 3분(또는 15분) 이상 시청하여 진입에 성공한 충성 사용자가 평균적으로 머무른 시간입니다.
    $$\text{Avg VT (Active)} = \frac{\sum \text{active\_viewing\_time\_180}}{\sum \text{active\_users\_playback\_180}}$$
  * **전체 사용자 기준 (Efficiency)**: 중도 이탈자를 포함한 전체 유입 대비 평균 시청 기여도입니다.
    $$\text{Avg VT (Total)} = \frac{\sum \text{active\_viewing\_time\_180}}{\sum \text{users}}$$

### 3. Playbacks (재생 횟수)
* **Playback Count (`playback_counts`)**: 총 영상 재생 시작 횟수
* **Active Count (>3m) (`active_playback_counts_180`)**: 3분 이상 정상 재생된 횟수
* **Active Count (>15m) (`active_playback_counts_900`)**: 15분 이상 장기 재생된 횟수

---

## 💻 주요 기능 안내

1. **KPI 오버뷰 카드**: 총 유저수, 3분이상 활성 유저수 및 비율, 총 시청 시간, 총 재생 횟수를 한눈에 확인합니다.
2. **시각화 차트**:
   * **플랫폼별 유저 점유율**: TV, 모바일, 스마트 모니터 등의 유저 비율을 분석합니다.
   * **활성 재생 필터 비율(Bounce Rate)**: 3분 미만 즉시 이탈 유저와 장기 시청 유저의 비율을 비교합니다.
3. **일별 트렌드 차트**: 지표 선택 드롭다운을 통해 유저/시청시간/재생수 추이를 라인 차트로 확인합니다.
4. **채널 랭킹 테이블**: 원하는 컬럼(유저, 시청시간 등) 정렬 필터를 사용하여 최고 성과 채널 20개를 순위로 확인합니다.
5. **DuckDB SQL 콘솔**:
   * 대시보드 화면 내에서 직접 DuckDB에 전송할 SQL을 작성하여 질의할 수 있습니다.
   * 백엔드에서 **Read-Only 연결**을 사용하여 데이터 훼손 우려 없이 실시간 분석 쿼리가 가능합니다.
