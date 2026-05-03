# AutoTrader — 한국투자증권 자동매매 프로그램

Python + KIS API 기반 한국·미국 주식 자동매매 프로그램입니다.  
웹 UI를 통해 전략 전환, 종목 탐색 모드 설정, 실시간 시세 확인을 제공합니다.

---

## 목차

1. [사전 준비](#1-사전-준비)
2. [설치](#2-설치)
3. [API 키 설정](#3-api-키-설정)
4. [실행 방법](#4-실행-방법)
5. [UI 화면 구성](#5-ui-화면-구성)
6. [거래 시장 설정](#6-거래-시장-설정)
7. [전략 설명](#7-전략-설명)
8. [종목 탐색 모드](#8-종목-탐색-모드)
9. [감시 종목](#9-감시-종목)
10. [리스크 관리](#10-리스크-관리)
11. [설정 파일 안내](#11-설정-파일-안내)
12. [파일 구조](#12-파일-구조)
13. [주의사항](#13-주의사항)

---

## 1. 사전 준비

| 항목 | 내용 |
|------|------|
| Python | 3.10 이상 |
| 한국투자증권 계좌 | 실전 또는 모의투자 계좌 |
| KIS Developers 가입 | https://apiportal.koreainvestment.com |
| API 키 | AppKey + SecretKey (KIS Developers에서 발급) |

---

## 2. 설치

```bash
pip install -r requirements.txt
```

---

## 3. API 키 설정

`.env.example`을 복사해 `.env` 파일을 만들고 실제 값을 입력합니다.

```bash
cp .env.example .env
```

```dotenv
KIS_ID=HTS_로그인_아이디
KIS_ACCOUNT=계좌번호-01          # 예: 50012345-01

KIS_APPKEY=발급받은_AppKey
KIS_SECRETKEY=발급받은_SecretKey

# 모의투자 사용 시 추가
KIS_VIRTUAL_APPKEY=모의투자_AppKey
KIS_VIRTUAL_SECRETKEY=모의투자_SecretKey
```

**API 키 발급 순서**

1. https://apiportal.koreainvestment.com 접속 후 로그인
2. **My Page → 앱 등록** 클릭
3. 앱 이름 입력 → 실전투자 선택 → 등록
4. 생성된 **AppKey**, **AppSecret** 복사 후 `.env`에 입력

> AppKey 유효기간은 **90일**입니다. 만료 전 KIS Developers에서 갱신하세요.

---

## 4. 실행 방법

### 방법 A — 웹 UI 포함 실행 (권장)

```bash
python app.py
```

브라우저에서 **http://localhost:5000** 접속 후 **시작하기** 버튼 클릭.

### 방법 B — 터미널 단독 실행

```bash
python main.py
```

`yes` 입력 후 시작. 로그는 터미널과 `trading.log` 파일에 동시 기록됩니다.

---

## 5. UI 화면 구성

```
┌─────────────────────────────────────────────────────────┐
│  AutoTrader   [● 실행 중]          실전투자  [중지하기]   │  헤더
├─────────────────────────────────────────────────────────┤
│  계좌 현황                                          [↺]  │
│  [현금 잔고]        [주식 평가금액]        [총 자산]       │  잔고 카드
├─────────────────────────────────────────────────────────┤
│  보유종목  (3)                                           │
│  종목코드 | 수량 | 평균단가 | 현재가 | 수익률 | 평가손익   │  보유종목 테이블
├─────────────────────────────────────────────────────────┤
│  감시 종목  (25)                                    [↺]  │
│  ─ KR 한국 주식 (15) ─────────────────────────────────  │
│  종목코드 | 현재가(원) | 등락률 | 거래량 | 스크리너       │
│  ─ US 미국 주식 (10) ─────────────────────────────────  │
│  종목코드 | 현재가($) | 등락률 | 거래량 | 스크리너        │
├─────────────────────────────────────────────────────────┤
│  전략 설정  (dark)                                       │
│  [RSI]  [이동평균 크로스]  [볼린저밴드]  [변동성 돌파]    │  전략 선택
│  실행 주기: 5분마다 | 투자 모드: 실전투자 | 종목 탐색: …   │  설정 요약
├─────────────────────────────────────────────────────────┤
│  실행 로그                                    [초기화]   │
│  10:30:01  INFO  [005930] 매수 1주 @ 72,500원           │  실시간 로그
└─────────────────────────────────────────────────────────┘
```

### 봇 시작 / 중지

- 헤더 우측 **시작하기** 클릭 → 자동매매 시작
- 실행 중에는 버튼이 **빨간색 "중지하기"** 로 변경
- 봇이 실행 중일 때는 전략 변경 및 탐색 모드 변경이 차단됩니다

### 자동 갱신 주기

| 항목 | 주기 |
|------|------|
| 봇 상태 | 3초 |
| 실행 로그 | 5초 |
| 잔고 / 보유종목 | 60초 |
| 감시 종목 시세 | 60초 |

---

## 6. 거래 시장 설정

`config.yaml`의 `market` 항목으로 거래 대상 시장을 선택합니다.

```yaml
market: BOTH   # KR: 한국만 / US: 미국만 / BOTH: 한국+미국
```

| 값 | 동작 |
|----|------|
| `KR` | 한국 주식만 거래 (KRX) |
| `US` | 미국 주식만 거래 (NASDAQ / NYSE / AMEX) |
| `BOTH` | 한국 + 미국 동시 거래 |

- 한국 장 운영 시간: **평일 09:00 ~ 15:30 KST**
- 미국 장 운영 시간: **평일 09:30 ~ 16:00 ET** (서머타임 자동 적용)
- 각 시장이 닫혀 있으면 해당 시장 매매는 자동 건너뜁니다

### 미국 종목 설정 형식

```yaml
us_screener:
  min_volume: 1000000
  max_stocks: 3
  watchlist:
    - "AAPL.NASD"    # Apple — NASDAQ
    - "MSFT.NASD"    # Microsoft
    - "NVDA.NASD"    # NVIDIA
    - "TSLA.NASD"    # Tesla
    - "META.NYSE"    # Meta — NYSE (예시)
```

거래소 코드: `NASD` (NASDAQ) · `NYSE` (뉴욕거래소) · `AMEX` (아메리칸거래소)

---

## 7. 전략 설명

전략은 UI에서 클릭 한 번으로 전환할 수 있습니다 (봇 중지 상태에서).  
한국·미국 모두 동일한 전략이 적용됩니다 (미국은 일봉 기준).

### RSI (상대강도지수)

- RSI가 **30 이하** 과매도 구간에서 반등 → 매수
- RSI가 **70 이상** 과매수 구간에서 하락 → 매도
- 횡보장에서 효과적

```yaml
rsi:
  period: 14      # RSI 계산 기간
  oversold: 30    # 매수 기준값
  overbought: 70  # 매도 기준값
```

### 이동평균 크로스오버 (MA Cross)

- 단기 이평선이 장기 이평선을 **위로 돌파** → 매수 (골든크로스)
- 단기 이평선이 장기 이평선을 **아래로 돌파** → 매도 (데드크로스)
- 추세 추종형 전략

```yaml
ma_cross:
  short_period: 5    # 단기 이동평균 기간
  long_period: 20    # 장기 이동평균 기간
```

### 볼린저밴드 (Bollinger Bands)

- 주가가 하단 밴드 이탈 후 **회복** → 매수
- 주가가 상단 밴드 이탈 후 **하락** → 매도
- 변동성이 큰 종목에 효과적

```yaml
bollinger:
  period: 20      # 기간
  std_dev: 2.0    # 표준편차 배수 (밴드 폭)
```

### 변동성 돌파 (Volatility Breakout)

- 매수가 = 당일 시가 + (전일 고가 − 전일 저가) × k
- 현재가가 매수가를 돌파하면 → 매수
- 당일 매수 후 장 마감 전 전량 매도
- 래리 윌리엄스 전략 기반, 단순하고 실전 검증된 방식

```yaml
volatility_breakout:
  k: 0.5   # 변동성 계수 (0.3 ~ 0.7 권장)
```

---

## 8. 종목 탐색 모드

봇이 매수 후보를 어디서 찾을지 결정합니다. UI의 **전략 설정** 섹션에서 클릭으로 전환합니다.

> 탐색 모드는 **한국 주식 전용** 기능입니다. 미국 주식은 항상 `us_screener.watchlist`를 사용합니다.

### 감시 목록 (기본)

`config.yaml`의 `screener.watchlist`에 등록된 종목만 검사합니다.

- 속도 빠름
- 원하는 종목을 직접 관리

### 전체 시장 자동 탐색

KIS API의 거래량 순위를 실시간으로 조회해 **시장 전체**에서 전략 조건에 맞는 종목을 자동 선정합니다.

- 거래량 상위 종목을 자동으로 가져와 스크리너 필터 적용
- 별도로 종목 목록을 관리할 필요 없음
- 감시 목록보다 사이클당 처리 시간이 더 걸릴 수 있음

```yaml
use_dynamic_universe: true   # 전체 시장 탐색 활성화

screener:
  min_universe_volume: 100000  # 유니버스 최소 거래량 (동적 탐색 시)
```

---

## 9. 감시 종목

UI의 **감시 종목** 섹션에서 `watchlist`에 등록된 종목들의 **현재 시세를 실시간으로 확인**할 수 있습니다.  
한국 주식과 미국 주식이 별도 섹션으로 분리되어 표시됩니다.

| 컬럼 | 설명 |
|------|------|
| 종목코드 / 종목명 | 종목 식별 정보 |
| 현재가 | 실시간 주가 (KR: 원화, US: 달러) |
| 등락률 | 전일 대비 등락률 (상승 초록 / 하락 빨강) |
| 거래량 | 당일 누적 거래량 |
| 스크리너 | **통과** (초록) / **거래량 부족** / **가격 범위 초과** (회색) |

- 시세 조회 불가 시에도 종목 코드와 이름은 항상 표시됩니다
- `↺` 버튼으로 즉시 새로고침, 또는 60초마다 자동 갱신

**한국 종목 설정 (`config.yaml`)**

```yaml
screener:
  watchlist:
    - "005930"   # 삼성전자
    - "000660"   # SK하이닉스
    - "035420"   # NAVER
```

**미국 종목 설정 (`config.yaml`)**

```yaml
us_screener:
  watchlist:
    - "AAPL.NASD"   # Apple
    - "MSFT.NASD"   # Microsoft
    - "NVDA.NASD"   # NVIDIA
```

---

## 10. 리스크 관리

매 사이클마다 보유 종목에 대해 손절 / 익절을 자동 체크합니다.

```yaml
risk:
  max_buy_amount: 500000        # KR 종목당 1회 최대 매수금액 (원)
  us_max_buy_amount_usd: 300    # US 종목당 1회 최대 매수금액 (USD)
  stop_loss_pct: -5.0           # -5% 손실 시 자동 손절
  take_profit_pct: 10.0         # +10% 수익 시 자동 익절
```

- `max_buy_amount` / `us_max_buy_amount_usd`를 낮게 설정할수록 분산 투자 효과
- 손절 / 익절은 한국·미국 보유 종목 모두에 적용됩니다

---

## 11. 설정 파일 안내

### config.yaml

```yaml
# 전략 선택
strategy: rsi   # rsi | ma_cross | bollinger | volatility_breakout

# 거래 시장
market: BOTH   # KR | US | BOTH

# 종목 탐색 모드 (한국 전용)
use_dynamic_universe: false   # false: 감시 목록 / true: 전체 시장

# 투자 모드
virtual: false   # true: 모의투자 / false: 실전투자

# 매매 주기 (분)
interval_minutes: 5

# 한국 스크리너 설정
screener:
  min_universe_volume: 100000  # 동적 탐색 시 유니버스 최소 거래량
  min_volume: 500000           # 스크리너 최소 거래량
  min_price: 5000              # 최소 주가 (원)
  max_price: 200000            # 최대 주가 (원)
  max_stocks: 5                # 최대 선택 종목 수
  watchlist:
    - "005930"                 # 삼성전자
    - "000660"                 # SK하이닉스
    # ...

# 미국 스크리너 설정
us_screener:
  min_volume: 1000000          # 최소 거래량
  max_stocks: 3                # 최대 선택 종목 수
  watchlist:
    - "AAPL.NASD"              # Apple
    - "MSFT.NASD"              # Microsoft
    # ...

# 리스크 관리
risk:
  max_buy_amount: 500000
  us_max_buy_amount_usd: 300
  stop_loss_pct: -5.0
  take_profit_pct: 10.0

# 전략 파라미터
rsi:
  period: 14
  oversold: 30
  overbought: 70

ma_cross:
  short_period: 5
  long_period: 20

bollinger:
  period: 20
  std_dev: 2.0

volatility_breakout:
  k: 0.5
```

---

## 12. 파일 구조

```
auto-trading/
├── .env                        ← API 키 (절대 공유 금지)
├── .env.example                ← API 키 템플릿
├── config.yaml                 ← 전략 · 시장 · 탐색 모드 · 파라미터 설정
├── requirements.txt
├── README.md
│
├── app.py                      ← Flask 웹 서버 (UI 포함 실행 진입점)
├── main.py                     ← 터미널 단독 실행 진입점
├── kis_client.py               ← KIS API 래퍼 (시세·주문·유니버스 조회)
├── screener.py                 ← 조건 검색 (감시 목록 / 동적 유니버스)
│
├── strategies/
│   ├── __init__.py             ← 전략 로더
│   ├── base.py                 ← 전략 추상 기반 클래스
│   ├── rsi.py                  ← RSI 전략
│   ├── ma_cross.py             ← 이동평균 크로스
│   ├── bollinger.py            ← 볼린저밴드
│   └── volatility_breakout.py ← 변동성 돌파
│
├── templates/
│   └── index.html              ← 웹 UI 메인 페이지
│
├── static/
│   ├── style.css               ← UI 스타일
│   └── script.js               ← 프론트엔드 로직
│
└── trading.log                 ← 매매 로그 (자동 생성)
```

---

## 13. 주의사항

> **실전투자는 실제 금전적 손실이 발생할 수 있습니다.**

- 처음 사용 시 반드시 **모의투자(`virtual: true`)** 로 테스트 후 실전투자로 전환하세요
- `max_buy_amount` / `us_max_buy_amount_usd`를 낮게 설정해 리스크를 제한하세요
- API 키는 절대 타인과 공유하거나 Git에 커밋하지 마세요 (`.gitignore`에 `.env` 포함)
- AppKey는 **90일마다 갱신** 이 필요합니다
- KIS API 호출 제한: **1초당 20건, 1일 10만 건**
- 한국 장 운영 시간(평일 09:00 ~ 15:30 KST) 외에는 한국 주식 주문이 실행되지 않습니다
- 미국 장 운영 시간(평일 09:30 ~ 16:00 ET) 외에는 미국 주식 주문이 실행되지 않습니다
- 전체 시장 탐색 모드는 많은 종목을 조회하므로 사이클당 처리 시간이 길어질 수 있습니다
- 프로그램 종료 시 봇도 함께 중지됩니다. 장시간 운용 시 서버 또는 항상 켜둔 PC에서 실행하세요
