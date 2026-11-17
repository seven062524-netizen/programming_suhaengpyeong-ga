import json  # JSON 변환을 위해 json 모듈을 불러온다
import math  # 올림·삼각함수를 위해 math 모듈을 불러온다
import random  # 무작위 선택을 위해 random 모듈을 불러온다

from pyscript import document  # PyScript에서 HTML 문서(document)에 접근하는 객체를 불러온다
from js import window  # 브라우저 전역 객체 window(Date, Audio, localStorage 등)를 불러온다
from pyodide.ffi import create_proxy  # 파이썬 함수를 자바스크립트 이벤트에 연결하는 create_proxy를 불러온다

# ───────────── 설정값 ─────────────
TIME_SCALE = 1            # 테스트용 배속 (1=실제 시간). 10초 확인 시간에는 적용되지 않음
CONFIRM_SEC = 10          # 종료 확인 제한 시간(초)
NOISES = [("sneeze", "🤧 재채기"), ("leg", "🦵 다리 떨기"), ("pencil", "✏️ 샤프"), ("paper", "📄 시험지 넘기는 소리")]  # 소음 종류(키, 버튼에 표시할 이름) 목록
NOISE_KEYS = [k for k, _ in NOISES]  # 소음 키만 뽑아 만든 목록
MIN_GAP, MAX_GAP = 12, 50  # 소음 재생 간격(초): 매번 새로 뽑고 MIN_GAP 이상 보장
PREP_ITEMS = ["수험표", "신분증", "컴퓨터용 사인펜", "샤프와 지우개", "아날로그 손목시계", "수험 시간표/규정 확인"]  # 준비물 체크리스트에 표시할 항목들
DEVICES = ["휴대폰", "태블릿", "노트북", "이어폰", "전자시계"]  # 전자기기 체크리스트에 표시할 항목들
CHEERS = ["지금까지 해 온 만큼, 오늘도 충분히 잘할 수 있어요!",  # 응원 메시지 목록 시작, 첫 번째 문구
          "긴장은 준비했다는 증거예요. 차분하게 한 문제씩!",  # 두 번째 문구
          "당신의 노력은 절대 배신하지 않아요. 파이팅!",  # 세 번째 문구
          "실전 같은 연습이 실전을 연습처럼 만들어 줘요.",  # 네 번째 문구
          "수고했어요. 오늘의 연습이 내일의 자신감이 됩니다!"]  # 다섯 번째 문구, 목록 끝
SCREENS = ["welcome", "candidate", "select", "prep", "device", "exam", "result"]  # 화면(섹션)의 id 목록


def hm(s):  # "HH:MM" 문자열을 초 단위 숫자로 바꾸는 함수
    h, m = s.split(":")  # 콜론을 기준으로 시와 분을 나눈다
    return int(h) * 3600 + int(m) * 60  # 시*3600 + 분*60 으로 하루 중 몇 초인지 계산해 돌려준다


# 시험 단위: pre=입실·예비령·준비령, start=본령, mid=종료 전 안내, end=종료령 (시각, 음성 번호, 이름)
# 음성 번호 = 실제 수능 방송 음성 파일 번호(1~31). 번호 n은 sounds/broadcast/b0nn.mp3(예: 1 → b001.mp3, 원본 파일명 001_0805_1교시_입실준비.mp3)에 대응한다.
# 음성 번호 None = 방송 음성 파일 없음(비프음 대체). 영어 본령(13:10) 방송 파일은 아직 없음
# 가장 중요한건 현재 2026 수능이 아직 안 나왔으므로, 실제 수능 음성파일이 없어서 예비용으로 2021 수능 음성파일을 사용하고 있습니다.
# 차후에 2026 수능 음성파일이 나오면, sounds/broadcast/b001~b031.mp3(b031보다 더 추가될 수도 있음)으로 교체하면 끝 
UNITS = [  # 시험 단위 목록 시작
    dict(name="국어", pre=[("08:05", 1, "입실 준비"), ("08:10", 2, "입실 완료"), ("08:25", 3, "예비령"), ("08:35", 4, "준비령")],  # 국어: 이름과 입실~준비령 방송 목록(시각, 음성 번호, 이름)
         start=("08:40", 5, "본령"), mid=[("09:50", 6, "종료 10분 전")], end=("10:00", 7, "종료령")),  # 국어: 본령, 종료 전 안내, 종료령 방송
    dict(name="수학", pre=[("10:15", 8, "입실"), ("10:20", 9, "예비령"), ("10:25", 10, "준비령")],  # 수학: 이름과 입실~준비령 방송 목록
         start=("10:30", 11, "본령"), mid=[("12:00", 12, "종료 10분 전")], end=("12:10", 13, "종료령")),  # 수학: 본령, 종료 전 안내, 종료령 방송
    dict(name="영어", pre=[("12:55", 14, "입실"), ("13:00", 15, "예비령"), ("13:05", 16, "준비령")],  # 영어: 이름과 입실~준비령 방송 목록
         start=("13:10", None, "본령"), mid=[("14:10", 17, "종료 10분 전")], end=("14:20", 18, "종료령")),  # 영어: 본령(음성 번호 None은 파일 없음), 종료 전 안내, 종료령
    dict(name="한국사", pre=[("14:35", 19, "입실"), ("14:40", 20, "예비령"), ("14:45", 21, "준비령")],  # 한국사: 이름과 입실~준비령 방송 목록
         start=("14:50", 22, "본령"), mid=[("15:15", 23, "종료 5분 전")], end=("15:20", 24, "종료령")),  # 한국사: 본령, 종료 전 안내, 종료령 방송
    dict(name="통합사회", pre=[("15:25", 25, "준비령")],  # 통합사회: 이름과 준비령 방송
         start=("15:30", 26, "본령"), mid=[("16:05", 27, "종료 5분 전")], end=("16:10", 28, "종료령")),  # 통합사회: 본령, 종료 전 안내, 종료령 방송
    dict(name="통합과학", pre=[],  # 통합과학: 이름과 사전 방송 없음
         start=("16:12", 29, "본령"), mid=[("16:47", 30, "종료 5분 전")], end=("16:52", 31, "종료령 · 시험장 종료")),  # 통합과학: 본령, 종료 전 안내, 종료령(시험장 종료)
]  # 시험 단위 목록 끝
for _u in UNITS:  # 시험 단위를 하나씩 반복한다
    _u["min"] = (hm(_u["end"][0]) - hm(_u["start"][0])) // 60  # 본령~종료령 시각 차이로 시험 시간(분)을 계산해 저장한다

HIST_KEY = "csatSimHistory"   # 시험 결과 기록(브라우저에 저장, 처음으로 돌아가도 유지)
BROADCAST_KEYS = [f"b{n:03d}" for n in range(1, 32)]  # 실제 수능 방송 음성 파일 31개(b001.mp3~b031.mp3)의 이름표(b001~b031) 목록을 만든다. b001은 08:05 1교시 입실 준비 방송, b031은 시험장 종료 방송이다
S = {}  # 프로그램 전체 상태를 담을 딕셔너리
audios, _all_audio, _active = {}, {}, {}  # 사용 가능한 오디오 목록, 전체 오디오, 비프음 발진기 목록을 담을 딕셔너리 3개
_toast = {"id": None}  # 알림 타이머 id와 오디오 컨텍스트를 보관하는 딕셔너리


def fresh_state():  # 초기 상태를 새로 만들어 돌려주는 함수
    return dict(candidate="", sel=None, order=[], events=[], ei=0, vt=0.0, last=0.0, phase="idle",  # 수험번호, 선택, 시험 순서, 방송 이벤트, 진행 위치, 시험장 시각, 단계의 초기값
                noise={k: False for k in NOISE_KEYS}, last_noise=None, next_noise=0.0,  # 소음 ON/OFF(모두 꺼짐), 직전 소음, 다음 소음 시각의 초기값
                cur=0, start_t=0.0, end_t=0.0, end_ev_t=0.0, exam_t0=None, break_total=0.0,  # 현재 단위, 시작/종료 시각, 시험 시작 기준 시각, 쉬는 시간 합계의 초기값
                deadline=0.0, cheats=[])  # 확인 마감 시각, 부정행위 기록 목록의 초기값


S.update(fresh_state())  # 상태 딕셔너리 S에 초기 상태를 채운다


def el(i):  # id로 HTML 요소를 찾는 도우미 함수
    return document.getElementById(i)  # document에서 해당 id의 요소를 돌려준다


def on(i, ev, fn):  # 요소에 이벤트 핸들러를 연결하는 도우미 함수
    el(i).addEventListener(ev, create_proxy(fn))  # 파이썬 함수를 프록시로 감싸 이벤트 리스너로 등록한다


def now_ms():  # 현재 시각(밀리초)을 돌려주는 함수
    return window.Date.now()  # 자바스크립트 Date.now() 값을 돌려준다


def hms(sec):  # 초를 "n시간 m분 s초" 문자열로 바꾸는 함수
    sec = int(sec)  # 초를 정수로 바꾼다
    h, m, s = sec // 3600, sec // 60 % 60, sec % 60  # 시, 분, 초를 각각 계산한다
    return (f"{h}시간 " if h else "") + f"{m}분 {s:02d}초"  # 시간이 있을 때만 "시간"을 붙여 문자열을 조립해 돌려준다


def mmss(sec):  # 초를 "MM:SS" 문자열로 바꾸는 함수
    s = math.ceil(max(0, sec))  # 음수는 0으로 막고 올림한 초를 구한다
    return f"{s // 60:02d}:{s % 60:02d}"  # 분과 초를 두 자리로 맞춰 돌려준다


def clock_text(sec):  # 초를 "HH:MM:SS" 시각 문자열로 바꾸는 함수
    sec = int(sec) % 86400  # 하루(86400초) 안의 값으로 맞춘다
    return f"{sec // 3600:02d}:{sec // 60 % 60:02d}:{sec % 60:02d}"  # 시, 분, 초를 두 자리로 맞춰 돌려준다


# ───────────── 화면 구성 ─────────────
# 화면 스타일(CSS) 문자열 시작 (줄 끝 주석을 문자열 안에 넣으면 CSS에 섞이므로 윗줄에 설명)
CSS = """
:root { --bg:#f3f6fb; --panel:#fff; --fg:#172033; --muted:#68758b; --border:#dce3ee; --face:#f8fafc; --accent:#2563eb; --danger:#dc4242; --ok:#1f9d55; --shadow:0 18px 50px rgba(26,45,80,.09); } /* 라이트 모드 색상 변수 정의 */
:root[data-theme="dark"] { --bg:#0b1220; --panel:#141f31; --fg:#edf3ff; --muted:#9aa9c0; --border:#2b3a52; --face:#101a2a; --accent:#6b9cff; --danger:#ff7373; --ok:#4cd388; --shadow:0 18px 50px rgba(0,0,0,.24); } /* 다크 모드 색상 변수 정의 */
* { box-sizing:border-box; } /* 모든 요소의 크기 계산을 border-box로 통일 */
body { margin:0; background:var(--bg); color:var(--fg); font-family:Inter,"Noto Sans KR",Arial,sans-serif; } /* 본문 여백, 배경색, 글자색, 글꼴 지정 */
button,input { font:inherit; } /* 버튼과 입력창이 주변 글꼴을 그대로 쓰게 함 */
button { border:1px solid var(--border); border-radius:12px; padding:11px 16px; color:var(--fg); background:var(--panel); cursor:pointer; transition:.18s ease; } /* 버튼 기본 모양(테두리, 둥근 모서리, 여백, 전환 효과) */
button:hover:not(:disabled) { transform:translateY(-1px); border-color:var(--accent); } /* 활성 버튼에 마우스를 올리면 살짝 떠오르고 테두리 강조 */
button:disabled { opacity:.45; cursor:not-allowed; } /* 비활성 버튼은 흐리게 하고 클릭 금지 커서 표시 */
[hidden] { display:none !important; } /* hidden 속성이 있는 요소는 확실히 숨김 */
.topbar { max-width:1100px; margin:auto; padding:20px 24px; display:flex; justify-content:space-between; align-items:center; } /* 상단 바 배치(좌우 양끝 정렬) */
.brand { font-weight:800; letter-spacing:-.04em; } #themeBtn { border-radius:999px; } /* 로고 글자 스타일, 테마 버튼 둥근 모양 */
.wrap { max-width:1000px; margin:20px auto 60px; padding:0 20px; } /* 콘텐츠 영역의 최대 폭과 바깥 여백 */
.hero { border-radius:28px; padding:clamp(30px,7vw,70px); background:linear-gradient(130deg,#101d35,#1b3d70 62%,#2857a0); color:#fff; box-shadow:var(--shadow); } /* 시작 화면 히어로 박스(그라데이션 배경, 그림자) */
.hero h1 { font-size:clamp(32px,6vw,56px); line-height:1.15; letter-spacing:-.05em; margin:14px 0; } /* 히어로 제목 글자 크기(화면 폭에 따라 조절) */
.hero p { color:#d6e3fa; line-height:1.8; max-width:560px; } /* 히어로 설명 글자 색과 줄 간격 */
.eyebrow { color:var(--accent); font-size:12px; font-weight:800; letter-spacing:.16em; } .hero .eyebrow { color:#bcd3ff; } /* 작은 라벨(eyebrow) 색과 히어로 안 라벨 색 */
.primary { background:var(--accent); color:#fff; border-color:var(--accent); font-weight:800; padding:14px 22px; } /* 주요(primary) 버튼 색상과 굵기 */
.hero .primary { background:#fff; color:#17345f; border-color:#fff; } /* 히어로 안의 주요 버튼은 흰색으로 */
.card { max-width:600px; margin:30px auto; padding:clamp(22px,5vw,38px); background:var(--panel); border:1px solid var(--border); border-radius:22px; box-shadow:var(--shadow); text-align:center; } /* 카드 박스 스타일(여백, 테두리, 둥근 모서리, 가운데 정렬) */
.card.left { text-align:left; } .card h2 { margin-top:0; } /* 왼쪽 정렬 카드와 카드 제목 위 여백 제거 */
.muted { color:var(--muted); font-size:14px; line-height:1.6; } /* 보조 설명 글자 스타일 */
.field { width:100%; padding:15px; margin:12px 0 8px; border:1px solid var(--border); border-radius:12px; color:var(--fg); background:var(--bg); outline:none; } /* 입력칸 스타일 */
.row { display:flex; flex-wrap:wrap; justify-content:center; gap:10px; margin:14px 0; } /* 버튼 한 줄 정렬(줄바꿈 허용, 가운데, 간격) */
.subj { min-width:100px; font-weight:750; } .subj small { display:block; color:var(--muted); margin-top:4px; } /* 과목 버튼 최소 폭과 작은 글씨(분 표시) */
.subj.sel { border-color:var(--accent); background:rgba(37,99,235,.12); } /* 선택된 과목 버튼 강조 */
.nz { min-width:120px; opacity:.7; } .nz.on { opacity:1; border-color:var(--ok); color:var(--ok); font-weight:800; background:rgba(31,157,85,.10); } /* 소음 버튼 기본(흐림)과 ON 상태(초록 강조) 스타일 */
.chk { display:flex; align-items:center; gap:12px; padding:13px 6px; border-bottom:1px solid var(--border); cursor:pointer; } /* 체크리스트 한 줄 스타일 */
.chk input { width:20px; height:20px; accent-color:var(--accent); } /* 체크박스 크기와 색 */
#clock svg { width:min(100%,290px); height:auto; }
.digital { font-size:clamp(42px,8vw,64px); font-weight:850; font-variant-numeric:tabular-nums; letter-spacing:.04em; } /* 디지털 시간의 큰 글자 스타일 */
.digital.warn { color:var(--danger); } .danger { color:var(--danger); } .ok { color:var(--ok); } /* 1분 이하 경고색, 위험색, 성공색 글자 스타일 */
.res { text-align:left; line-height:1.9; } .res li { margin:4px 0; } /* 결과 목록의 정렬·줄 간격과 항목 간격 */
.cheer { font-weight:800; font-size:18px; margin:18px 0; } /* 응원 메시지 글자 스타일 */
#overlay { position:fixed; inset:0; z-index:20; background:rgba(5,10,20,.72); display:flex; align-items:center; justify-content:center; padding:20px; }
#overlay .card { margin:0; } #cdown { font-size:60px; font-weight:900; color:var(--danger); }
#toast { position:fixed; z-index:30; top:18px; left:50%; transform:translateX(-50%); padding:12px 18px; border-radius:12px; background:#18263d; color:#fff; opacity:0; pointer-events:none; transition:opacity .2s; max-width:92vw; }
#toast.show { opacity:1; }
@media(max-width:700px) { .wrap { padding:0 12px; } .subj { min-width:calc(50% - 6px); } .nz { flex:1 1 100%; } } /* 폭 700px 이하(휴대폰)에서 여백과 버튼 배치를 조정 */
"""  # CSS 문자열 끝

# 화면 HTML 템플릿 문자열 시작 (줄 끝 주석을 문자열 안에 넣으면 화면에 섞이므로 윗줄에 설명)
HTML = """
<style>__CSS__</style> <!-- CSS가 들어갈 자리 -->
<div class="topbar"><div class="brand">🎓 CSAT SIMULATOR</div><button id="themeBtn">🌙 다크</button></div> <!-- 상단 바: 로고와 테마 전환 버튼 -->
<div id="toast"></div> <!-- 알림(토스트)이 표시될 자리 -->

<section id="welcome" class="wrap"><div class="hero"> <!-- 시작 화면 섹션과 히어로 박스 시작 -->
  <div class="eyebrow">EXAM ENVIRONMENT TRAINING</div> <!-- 상단 작은 문구 -->
  <h1>실전처럼 준비하고,<br>실전처럼 경험하다.</h1> <!-- 큰 제목 -->
  <p>실제 수능 방송 시간표와 시험장 소음, 시험 절차를 미리 경험해 보세요.</p> <!-- 설명 문구 -->
  <button class="primary" id="enterBtn">시험 환경 시작하기 →</button> <!-- 시험 환경 시작 버튼 -->
</div> <!-- 히어로 박스 닫기 -->
<div class="card left" id="histCard" hidden> <!-- 이전 시험 기록 카드(기록이 없으면 숨김) -->
  <h3 style="margin-top:0">📒 이전 시험 기록</h3><div id="histBody" class="res"></div> <!-- 기록 제목과 기록 내용이 들어갈 자리 -->
  <button id="histClear">기록 삭제</button> <!-- 기록 삭제 버튼 -->
</div></section> <!-- 카드와 시작 화면 섹션 닫기 -->

<section id="candidate" class="wrap" hidden><div class="card left"> <!-- 수험번호 입력 화면 섹션 시작 -->
  <div class="eyebrow">STEP 01 · 수험번호</div><h2>가상 수험번호 입력</h2> <!-- 단계 라벨과 제목 -->
  <input class="field" id="candInput" inputmode="numeric" maxlength="12" placeholder="예: 12345678"> <!-- 수험번호 입력칸 -->
  <p class="muted danger" id="candError" hidden>수험번호를 입력해야 다음 단계로 이동할 수 있습니다.</p> <!-- 빈 값일 때 보여 줄 오류 문구(처음에는 숨김) -->
  <div class="row" style="justify-content:flex-start"><button id="candBack">이전</button><button class="primary" id="candNext">다음 →</button></div> <!-- 이전·다음 버튼 -->
</div></section> <!-- 수험번호 화면 닫기 -->

<section id="select" class="wrap" hidden><div class="card"> <!-- 과목 선택 화면 섹션 시작 -->
  <div class="eyebrow">STEP 02 · 시험 선택</div><h2>과목과 소음 설정</h2> <!-- 단계 라벨과 제목 -->
  <p class="muted">개별 시험은 준비령부터, 통합은 08:05 입실 방송부터 수능 시간표 그대로 진행합니다.</p> <!-- 안내 문구 -->
  <div class="row">__SUBJ__</div> <!-- 개별 과목 버튼이 들어갈 자리 -->
  <div class="row"><button class="subj" id="fullBtn">통합 진행<small>수능 전체 시간표</small></button></div> <!-- 통합 진행 버튼 -->
  <p id="selInfo" class="muted">선택된 시험이 없습니다.</p> <!-- 선택 결과를 보여 주는 안내 문구 -->
  <h3>시험장 소음 (여러 개 동시에 ON 가능)</h3> <!-- 소음 설정 제목 -->
  <div class="row">__NZ_select__</div> <!-- 소음 ON/OFF 버튼이 들어갈 자리 -->
  <button class="primary" id="selNext" disabled>다음 →</button> <!-- 다음 버튼(시험을 고르기 전에는 비활성) -->
</div></section> <!-- 과목 선택 화면 닫기 -->

<section id="prep" class="wrap" hidden><div class="card left"> <!-- 준비물 화면 섹션 시작 -->
  <div class="eyebrow">STEP 03 · 준비물</div><h2>준비물 체크리스트</h2> <!-- 단계 라벨과 제목 -->
  __PREP__ <!-- 준비물 체크 항목이 들어갈 자리 -->
  <div class="row" style="justify-content:flex-start"><button class="primary" id="prepNext" disabled>다음 단계 →</button></div> <!-- 다음 단계 버튼(모두 체크하기 전에는 비활성) -->
</div></section> <!-- 준비물 화면 닫기 -->

<section id="device" class="wrap" hidden><div class="card left"> <!-- 전자기기 화면 섹션 시작 -->
  <div class="eyebrow">STEP 04 · 전자기기</div><h2>전자기기 확인</h2> <!-- 단계 라벨과 제목 -->
  <p class="muted">하나씩 확인하고 체크하세요.</p> <!-- 안내 문구 -->
  __DEV__ <!-- 전자기기 체크 항목이 들어갈 자리 -->
  <div class="row" style="justify-content:flex-start"><button class="primary" id="devNext" disabled>시험장 입장 →</button></div> <!-- 시험장 입장 버튼(모두 체크하기 전에는 비활성) -->
</div></section> <!-- 전자기기 화면 닫기 -->

<section id="exam" class="wrap" hidden><div class="card"> <!-- 시험 화면 섹션 시작 -->
  <div id="examName" class="eyebrow"></div> <!-- 현재 과목 또는 상태 이름이 표시될 자리 -->
  <div id="clock"></div> <!-- 아날로그 시계가 그려질 자리 -->
  <div class="muted" id="roomClock"></div> <!-- 시험장 시각이 표시될 자리 -->
  <div class="digital" id="digital">00:00</div><div class="muted" id="examStatus"></div> <!-- 디지털 남은 시간과 상태 문구 자리 -->
  <div class="row">__NZ_exam__</div> <!-- 소음 ON/OFF 버튼이 들어갈 자리 -->
  <div class="row"><button id="skipNext">⏭ 다음 방송으로 스킵</button></div> <!-- 다음 방송으로 스킵하는 버튼 -->
</div></section> <!-- 시험 화면 닫기 -->

<section id="result" class="wrap" hidden><div class="card left"> <!-- 결과 화면 섹션 시작 -->
  <div class="eyebrow">RESULT</div><h2>최종 결과</h2> <!-- 라벨과 제목 -->
  <div id="resBody" class="res"></div><div class="cheer" id="cheer"></div> <!-- 결과 내용과 응원 메시지가 들어갈 자리 -->
  <button class="primary" id="homeBtn">처음으로 돌아가기</button> <!-- 처음으로 돌아가기 버튼 -->
</div></section> <!-- 결과 화면 닫기 -->

<div id="overlay" hidden><div class="card"> <!-- 10초 확인창 시작(처음에는 숨김) -->
  <h2 id="ovTitle"></h2><p class="muted" id="ovMsg"></p><div id="cdown">10</div> <!-- 확인창 제목, 설명, 카운트다운 숫자 자리 -->
  <button class="primary" id="ovBtn">확인했습니다</button> <!-- 확인 버튼 -->
</div></div> <!-- 확인창 닫기 -->
"""  # HTML 템플릿 문자열 끝


def build_ui():  # 화면 HTML을 조립해 페이지에 넣는 함수
    subj = "".join(f'<button class="subj" id="subj-{i}">{u["name"]}<small>{u["min"]}분</small></button>'  # 과목 버튼들의 HTML 문자열을 만든다(이름과 시험 시간 표시)
                   for i, u in enumerate(UNITS))  # 시험 단위를 번호와 함께 하나씩 반복한다
    nz = lambda p: "".join(f'<button class="nz" id="nz-{p}-{k}"></button>' for k, _ in NOISES)  # 소음 버튼 HTML을 만드는 람다(p는 화면 이름)
    chk = lambda p, items, tail="": "".join(  # 체크박스 항목 HTML을 만드는 람다 시작
        f'<label class="chk"><input type="checkbox" id="{p}-{i}"> {n}{tail}</label>' for i, n in enumerate(items))  # 항목마다 체크박스가 든 label을 만든다
    html = (HTML.replace("__CSS__", CSS).replace("__SUBJ__", subj)  # 템플릿의 CSS 자리와 과목 버튼 자리를 실제 내용으로 바꾼다
            .replace("__NZ_select__", nz("select")).replace("__NZ_exam__", nz("exam"))  # 소음 버튼 자리를 시험 선택 화면용, 시험 화면용으로 바꾼다
            .replace("__PREP__", chk("prep", PREP_ITEMS))  # 준비물 체크 항목 자리를 바꾼다
            .replace("__DEV__", chk("dev", DEVICES)))  # 전자기기 체크 항목 자리를 바꿔 html을 완성한다
    el("app").innerHTML = html  # #app 요소에 완성된 HTML을 넣는다


def show(name):  # 지정한 화면만 보이게 하는 함수
    for s in SCREENS:  # 모든 화면을 하나씩 반복한다
        el(s).hidden = s != name  # 이름이 같으면 보이고 다르면 숨긴다


# ───────────── 아날로그 시계 (시험장 시각) ─────────────
def clock_svg(vt, frac):  # 아날로그 시계 SVG 문자열을 만드는 함수(vt: 시험장 시각, frac: 남은 비율)
    cx = cy = 150  # 시계 중심 좌표
    R = 140  # 시계 반지름

    def pt(deg, r):  # 각도와 반지름으로 좌표를 구하는 내부 함수
        a = math.radians(deg)  # 각도를 라디안으로 바꾼다
        return cx + r * math.sin(a), cy - r * math.cos(a)  # 12시 방향을 기준으로 x, y 좌표를 돌려준다

    p = ['<svg viewBox="0 0 300 300">',  # SVG 조각을 담을 리스트 시작(SVG 여는 태그)
         f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="var(--face)" stroke="var(--border)" stroke-width="6"/>']  # 시계 바탕 원을 추가한다
    if frac > 0.001:                                  # 남은 시험 시간 호
        color = "var(--danger)" if frac < 0.1 else "var(--accent)"  # 남은 비율에 따라 호 색을 고른다(10% 미만이면 빨강)
        rr = R * 0.9  # 호의 반지름
        if frac >= 0.999:  # 시간이 거의 다 남았으면
            p.append(f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" stroke="{color}" stroke-width="8"/>')  # 완전한 원으로 그린다
        else:  # 그렇지 않으면
            x, y = pt(360 * frac, rr)  # 호의 끝점 좌표를 계산한다
            p.append(f'<path d="M {cx} {cy - rr} A {rr} {rr} 0 {1 if frac > 0.5 else 0} 1 {x:.2f} {y:.2f}" '  # 호(path)를 그린다(큰 호 여부와 끝점 지정)
                     f'fill="none" stroke="{color}" stroke-width="8" stroke-linecap="round"/>')  # 호의 색, 굵기, 둥근 끝 모양을 지정한다
    for i in range(60):  # 눈금 60개를 반복한다
        big = i % 5 == 0  # 5의 배수면 굵은 눈금으로 구분한다
        x1, y1 = pt(i * 6, R * (0.72 if big else 0.76))  # 눈금 바깥쪽 시작점(굵은 눈금은 더 길게)
        x2, y2 = pt(i * 6, R * 0.80)  # 눈금 안쪽 끝점
        p.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="var(--fg)" stroke-width="{2 if big else 1}"/>')  # 눈금 선을 추가한다
    for n in range(1, 13):  # 숫자 1~12를 반복한다
        x, y = pt(n * 30, R * 0.62)  # 숫자가 놓일 위치를 계산한다
        p.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="18" font-weight="700" fill="var(--fg)">{n}</text>')  # 숫자 텍스트를 추가한다
    sec = vt % 60  # 시험장 시각에서 초를 구한다
    minute = vt / 60 % 60  # 초를 포함한 분을 구한다
    hour = vt / 3600 % 12  # 분을 포함한 시(12시간제)를 구한다
    for deg, length, w, c in [(hour * 30, .42, 6, "var(--fg)"), (minute * 6, .62, 4, "var(--fg)"), (sec * 6, .70, 2, "var(--danger)")]:  # 시침·분침·초침의 각도, 길이, 굵기, 색을 하나씩 반복한다
        x, y = pt(deg, R * length)  # 바늘 끝점 좌표를 계산한다
        p.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{c}" stroke-width="{w}" stroke-linecap="round"/>')  # 바늘 선을 추가한다
    p.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="var(--danger)"/></svg>')  # 중심 점을 그리고 SVG를 닫는다
    return "".join(p)  # 조각들을 하나의 문자열로 합쳐 돌려준다


# ───────────── 소리 (파일이 없으면 비프음) ─────────────
def tone(freq, start, dur, kind="sine", vol=0.2, key=None):  # 비프음(발진기) 하나를 만드는 함수
    if "ctx" not in _toast:  # 오디오 컨텍스트가 아직 없으면
        _toast["ctx"] = window.AudioContext.new()  # 새로 만들어 저장한다
    ctx = _toast["ctx"]  # 저장된 컨텍스트를 꺼낸다
    if ctx.state == "suspended":  # 브라우저가 소리를 일시정지시킨 상태면
        ctx.resume()  # 다시 시작한다
    o, g = ctx.createOscillator(), ctx.createGain()  # 소리 발생기와 볼륨 조절기를 만든다
    t = ctx.currentTime + start  # 재생 시작 시각을 계산한다
    o.type = kind  # 파형 종류를 지정한다
    o.frequency.value = freq  # 주파수를 지정한다
    g.gain.setValueAtTime(vol, t)  # 시작 볼륨을 지정한다
    g.gain.exponentialRampToValueAtTime(0.001, t + dur)  # 끝으로 갈수록 소리가 작아지게 한다
    o.connect(g)  # 발생기를 볼륨 조절기에 연결한다
    g.connect(ctx.destination)  # 볼륨 조절기를 스피커에 연결한다
    o.start(t)  # 지정한 시각에 소리를 시작한다
    o.stop(t + dur)  # 지정한 시각에 소리를 끝낸다
    _active.setdefault(key, []).append(o)  # 나중에 멈출 수 있도록 key별 목록에 저장한다


def beep(key):  # 소리 파일이 없을 때 쓰는 대체음 함수
    if key == "sneeze":  # 재채기 대체음
        tone(1300, 0, .08, "sawtooth", .12, key)  # 짧고 높은 톱니파 소리
        tone(450, .12, .3, "sawtooth", .16, key)  # 이어서 낮은 톱니파 소리
    elif key == "leg":  # 다리 떨기 대체음
        for i in range(8):  # 8번 반복한다
            tone(70, i * .12, .09, "sine", .25, key)  # 낮은 진동음을 일정 간격으로 낸다
    elif key == "pencil":  # 샤프 대체음
        for i in range(3):  # 3번 반복한다
            tone(1900, i * .18, .04, "square", .08, key)  # 짧은 딸깍 소리를 낸다
    elif key == "paper":  # 시험지 대체음
        tone(260, 0, .25, "sawtooth", .06, key)  # 낮은 스치는 소리
        tone(420, .12, .22, "sawtooth", .05, key)  # 이어지는 소리
    else:                                             # 방송/종소리 대체음
        for f, t in [(784, 0), (659, .55), (698, 1.1), (523, 1.65)]:  # 네 음(주파수, 시작 시간)을 차례로 반복한다
            tone(f, t, .9, key=key)  # 종소리 같은 음을 재생한다


def stop_sound(key):  # 재생 중인 소리를 즉시 멈추는 함수
    """재생 중인 소리를 즉시 멈춘다 (파일 재생 + 비프음 모두)."""  # 함수 설명(파일 재생과 비프음 모두 멈춤)
    for a in audios.get(key, []):  # 해당 key의 오디오 파일을 하나씩 반복한다
        a.pause()  # 일시정지한다
        a.currentTime = 0  # 재생 위치를 처음으로 돌린다
    for o in _active.pop(key, []):  # 비프음 발진기 목록을 꺼내며 반복한다
        try:  # 오류에 대비해 시도한다
            o.disconnect()  # 발진기 연결을 끊어 즉시 무음으로 만든다
        except Exception:  # 오류가 나면
            pass  # 무시하고 넘어간다


def stop_broadcasts():  # 재생 중인 수능 방송 음성(b001~b031)과 대체 종소리를 모두 멈추는 함수
    for key in BROADCAST_KEYS + ["bell"]:  # 수능 방송 음성 b001~b031과 대체 종소리(bell) 이름표를 하나씩 반복한다
        stop_sound(key)  # 각각 정지한다


def stop_everything():  # 재생 중인 모든 소리를 멈추는 함수
    for key in list(audios) + list(_active):  # 오디오 키와 비프음 키를 합쳐 반복한다
        stop_sound(key)  # 각각 정지한다


def safe_play(a, key):  # 오디오를 재생하고 실패하면 비프음으로 대체하는 함수
    p = a.play()  # 재생을 시도한다(결과 객체를 돌려받음)
    if p is not None:  # 결과 객체가 있으면
        p.catch(create_proxy(lambda e: beep(key)))  # 재생에 실패했을 때 비프음이 나오도록 등록한다


def play_once(key, vol=0.8):  # 소리 하나를 한 번 재생하는 함수
    files = audios.get(key)  # 해당 key의 오디오 파일 목록을 가져온다
    if not files:  # 파일이 하나도 없으면
        beep(key)  # 비프음으로 대신 재생한다
        return  # 함수를 끝낸다
    stop_sound(key)  # 같은 소리가 겹치지 않게 먼저 멈춘다
    a = random.choice(files)                          # 변형 파일 중 무작위 선택
    a.loop = False  # 반복 재생을 끈다
    a.currentTime = 0  # 처음부터 재생하도록 위치를 돌린다
    a.volume = max(0.0, min(1.0, vol))  # 볼륨을 0~1 범위로 맞춰 설정한다
    safe_play(a, key)  # 안전 재생 함수를 호출한다


def load_sounds():  # 소리 파일을 불러오는 함수
    def load(key, name, src, preload):  # 오디오 파일 하나를 불러오는 내부 함수
        a = window.Audio.new()  # 새 오디오 객체를 만든다
        a.preload = preload  # 미리 불러오기 방식을 지정한다
        _all_audio[name] = a  # 전체 오디오 목록에 보관한다

        def ok(e):  # 불러오기 성공 시 실행되는 함수
            audios.setdefault(key, []).append(a)  # 성공한 파일만 key별 목록에 추가한다

        a.addEventListener("loadedmetadata", create_proxy(ok))  # 메타데이터 로딩 완료 이벤트에 ok 함수를 연결한다
        a.src = src  # 파일 경로를 지정해 불러오기를 시작한다

    for key in NOISE_KEYS:  # 소음 키를 하나씩 반복한다
        for name in (key, f"{key}_variant_1", f"{key}_variant_2"):  # 기본, 변형 1, 변형 2 파일 이름을 반복한다
            load(key, name, f"sounds/{name}.mp3", "auto")  # 소음 파일을 불러온다
    for n in range(1, 32):                            # 방송 음성은 재생할 때 불러온다
        key = f"b{n:03d}"  # 수능 방송 음성 파일의 이름표 문자열(1 → b001, 31 → b031)을 만든다
        load(key, key, f"sounds/broadcast/{key}.mp3", "metadata")  # 실제 수능 방송 음성 파일(sounds/broadcast/b001.mp3 등)을 불러온다. 방송이 나올 때 재생하며 미리 용량은 불러오지 않는다


# ───────────── 소음 ON/OFF ─────────────
def refresh_noise_buttons():  # 소음 버튼의 글자와 색을 갱신하는 함수
    for p in ("select", "exam"):  # 시험 선택 화면과 시험 화면을 반복한다
        for k, name in NOISES:  # 소음 종류를 반복한다
            b = el(f"nz-{p}-{k}")  # 해당 버튼 요소를 가져온다
            is_on = S["noise"][k]  # 현재 켜져 있는지 확인한다
            b.textContent = f'{name} {"ON" if is_on else "OFF"}'  # 버튼 글자를 "이름 ON/OFF"로 바꾼다
            b.classList.toggle("on", is_on)  # 켜져 있으면 on 클래스를 붙이고 꺼져 있으면 뗀다


def toggle_noise(k):  # 소음 ON/OFF를 전환하는 함수
    S["noise"][k] = not S["noise"][k]  # 켜짐 상태를 반대로 바꾼다
    if not S["noise"][k]:  # 꺼진 상태가 되었다면
        stop_sound(k)                                 # OFF → 바로 멈춤
    refresh_noise_buttons()  # 버튼 표시를 갱신한다


def schedule_noise():  # 다음 소음 재생 시각을 예약하는 함수
    S["next_noise"] = now_ms() + random.uniform(MIN_GAP, MAX_GAP) * 1000  # 지금 시각에 최소~최대 사이 무작위 간격을 더해 저장한다


def fire_noise():  # 무작위 소음을 하나 재생하는 함수
    pool = [k for k in NOISE_KEYS if S["noise"][k]]  # 켜져 있는 소음만 후보로 모은다
    if len(pool) > 1 and S["last_noise"] in pool:     # 같은 소음 연속 금지
        pool.remove(S["last_noise"])  # 직전에 나온 소음은 후보에서 뺀다
    if pool:  # 후보가 있으면
        k = random.choice(pool)  # 무작위로 하나 고른다
        S["last_noise"] = k  # 직전 소음으로 기록한다
        play_once(k)  # 소음을 재생한다
    schedule_noise()  # 다음 소음 시각을 새로 뽑아 예약한다


def stop_all_noises():  # 모든 소음을 멈추는 함수
    for k in NOISE_KEYS:  # 소음 키를 하나씩 반복한다
        stop_sound(k)  # 각각 정지한다


# ───────────── 선택 / 체크리스트 ─────────────
def toast(msg, ms=3000):  # 화면 위쪽에 잠깐 알림을 띄우는 함수
    t = el("toast")  # 알림 요소를 가져온다
    t.textContent = msg  # 알림 문구를 넣는다
    t.className = "show"  # show 클래스를 붙여 보이게 한다
    if _toast["id"] is not None:  # 이전 숨김 타이머가 남아 있으면
        window.clearTimeout(_toast["id"])  # 그 타이머를 취소한다
    _toast["id"] = window.setTimeout(create_proxy(lambda *a: setattr(el("toast"), "className", "")), ms)  # ms 밀리초 뒤에 알림을 숨기는 타이머를 등록한다


def show_candidate(e=None):  # 수험번호 입력 화면을 여는 함수
    el("candInput").value = ""  # 입력칸을 비운다
    el("candError").hidden = True  # 오류 문구를 숨긴다
    show("candidate")  # 수험번호 입력 화면을 보여 준다
    el("candInput").focus()  # 입력칸에 커서를 둔다


def accept_candidate(e=None):                         # 빈 값이면 진행 차단  # 수험번호를 검사하고 저장하는 함수
    v = el("candInput").value.strip()  # 입력값의 앞뒤 공백을 제거한다
    if not v:  # 비어 있으면
        el("candError").hidden = False  # 오류 문구를 보여 준다
        el("candInput").focus()  # 입력칸에 커서를 둔다
        return  # 함수를 끝내 다음 화면으로 못 넘어가게 한다
    S["candidate"] = v  # 수험번호를 저장한다
    show("select")  # 과목 선택 화면으로 이동한다


def update_select(msg):  # 선택 화면의 안내 문구와 버튼 상태를 갱신하는 함수
    el("selInfo").textContent = msg  # 선택 안내 문구를 바꾼다
    el("selNext").disabled = not S["order"]  # 선택된 시험이 없으면 다음 버튼을 비활성화한다
    for i in range(len(UNITS)):  # 시험 단위를 번호로 반복한다
        el(f"subj-{i}").classList.toggle("sel", S["sel"] == ("single", i))  # 선택된 과목 버튼만 강조한다
    el("fullBtn").classList.toggle("sel", S["sel"] == ("full",))  # 통합 버튼 강조도 갱신한다


def pick_single(i):                                   # 개별 과목 → 그 시험 시간 설정  # 개별 과목을 선택하는 함수
    u = UNITS[i]  # 선택한 시험 단위를 가져온다
    first = u["pre"][-1] if u["pre"] else u["start"]  # 시작 방송을 정한다(준비령이 있으면 준비령, 없으면 본령)
    S["sel"], S["order"] = ("single", i), [i]  # 선택 정보와 시험 순서(한 과목)를 저장한다
    update_select(f'선택: {u["name"]} · {u["min"]}분 (시작 시각 {first[0]} {first[2]} 방송부터)')  # 과목, 시험 시간, 시작 시각을 안내 문구로 보여 준다


def pick_full(e=None):                                # 통합 → 실제 수능 순서 목록  # 통합 진행을 선택하는 함수
    S["sel"], S["order"] = ("full",), list(range(len(UNITS)))  # 통합 선택과 전체 과목 순서를 저장한다
    update_select("선택: 통합 · " + " → ".join(u["name"] for u in UNITS))  # 과목 순서를 화살표로 이어 안내 문구로 보여 준다


def check_all(prefix, n, btn):                        # 모두 체크해야 버튼 활성화  # 체크박스가 모두 체크되었는지 검사해 버튼을 켜고 끄는 함수
    el(btn).disabled = not all(el(f"{prefix}-{i}").checked for i in range(n))  # 하나라도 체크가 안 되어 있으면 버튼을 비활성화한다


# ───────────── 방송 시간표 진행 ─────────────
def build_events(order, full):  # 선택한 시험의 방송 이벤트 목록을 만드는 함수
    evs = []  # 이벤트 목록을 빈 리스트로 시작한다
    for ui in order:  # 선택한 시험 순서를 하나씩 반복한다
        u = UNITS[ui]  # 해당 시험 단위를 가져온다
        pre = u["pre"] if full else u["pre"][-1:]  # 통합이면 사전 방송 전부, 개별이면 마지막 준비령만 쓴다
        for t, no, label in pre:  # 사전 방송을 하나씩 반복한다
            evs.append(dict(t=hm(t), no=no, label=label, kind="pre", unit=ui))  # 준비 이벤트(시각, 음성 번호, 이름)를 추가한다
        t, no, label = u["start"]  # 본령 정보를 꺼낸다
        evs.append(dict(t=hm(t), no=no, label=label, kind="start", unit=ui))  # 시작 이벤트를 추가한다
        for t, no, label in u["mid"]:  # 종료 전 안내를 하나씩 반복한다
            evs.append(dict(t=hm(t), no=no, label=label, kind="info", unit=ui))  # 안내 이벤트를 추가한다
        t, no, label = u["end"]  # 종료령 정보를 꺼낸다
        evs.append(dict(t=hm(t), no=no, label=label, kind="end", unit=ui))  # 종료 이벤트를 추가한다
    return evs  # 완성된 이벤트 목록을 돌려준다


def enter_exam(e=None):  # 시험장에 입장해 시험을 시작하는 함수
    evs = build_events(S["order"], S["sel"] == ("full",))  # 이벤트 목록을 만든다
    S.update(events=evs, ei=0, vt=evs[0]["t"] - 8, last=now_ms(), phase="pre", exam_t0=None,  # 이벤트, 위치, 첫 방송 8초 전 시각, 현재 시각, 준비 단계로 상태를 초기화한다
             break_total=0.0, cheats=[], last_noise=None, cur=evs[0]["unit"])  # 쉬는 시간 합계, 부정행위 기록, 직전 소음을 비우고 현재 단위를 정한다
    show("exam")  # 시험 화면을 보여 준다


def fire(ev):  # 방송 이벤트 하나를 실행하는 함수
    stop_broadcasts()                                 # 이전 방송이 남아 있으면 끊고 새 방송만 재생
    play_once(f'b{ev["no"]:03d}' if ev["no"] else "bell", 1.0)  # 이 방송에 해당하는 실제 수능 방송 음성 파일(번호 1 → b001.mp3 등)을 재생한다. 번호가 None이면 파일이 없는 방송이라 대체 종소리를 낸다
    toast(f'📢 {clock_text(ev["t"])[:5]} · {UNITS[ev["unit"]]["name"]} {ev["label"]}', 4000)  # 화면에 방송 시각, 과목, 방송 이름을 알린다
    k = ev["kind"]  # 이벤트 종류를 꺼낸다
    if k == "pre":  # 준비 방송이면
        S["phase"] = "pre"  # 준비 단계로 바꾼다
        S["cur"] = ev["unit"]  # 현재 시험 단위를 갱신한다
    elif k == "start":                                # 본령: 시험 시작
        S["cur"], S["start_t"], S["phase"] = ev["unit"], ev["t"], "exam"  # 현재 단위, 시작 시각을 저장하고 시험 중 단계로 바꾼다
        S["end_t"] = next(e["t"] for e in S["events"][S["ei"]:] if e["kind"] == "end")  # 이 시험의 종료령 시각을 찾아 저장한다
        if S["exam_t0"] is None:  # 전체 시험에서 처음 시작하는 것이면
            S["exam_t0"] = ev["t"]  # 시험 시작 기준 시각으로 저장한다
        S["last_noise"] = None  # 직전 소음 기록을 비운다
        schedule_noise()  # 첫 소음 재생 시각을 예약한다
    elif k == "end":                                  # 종료령: 소음 정지 + 10초 확인
        S["cur"], S["end_ev_t"] = ev["unit"], ev["t"]  # 종료되는 단위와 종료령 시각을 저장한다
        stop_all_noises()  # 소음을 모두 멈춘다
        open_confirm("exam_confirm", "⏰ 종료령", f"{CONFIRM_SEC}초 안에 확인 버튼을 눌러 주세요.")  # 10초 확인창을 연다


def open_confirm(phase, title, msg):  # 10초 확인창을 여는 함수(단계, 제목, 설명)
    S["phase"] = phase  # 현재 단계를 확인 단계로 바꾼다
    S["deadline"] = now_ms() + CONFIRM_SEC * 1000  # 마감 시각을 지금부터 10초 뒤로 정한다
    el("ovTitle").textContent, el("ovMsg").textContent = title, msg  # 확인창의 제목과 설명을 채운다
    el("cdown").textContent = str(CONFIRM_SEC)  # 카운트다운 숫자를 10으로 되돌린다
    el("overlay").hidden = False  # 확인창을 보여 준다


def confirm_done(timed_out=False):  # 확인창이 끝났을 때 처리하는 함수(timed_out이 True면 시간 초과)
    phase = S["phase"]  # 현재 단계를 기억해 둔다
    if timed_out:                                     # 부정행위 기록
        step = "시험 종료 확인" if phase == "exam_confirm" else "쉬는 시간 종료 확인"  # 어떤 확인 단계였는지 이름을 정한다
        S["cheats"].append(dict(subject=UNITS[S["cur"]]["name"], step=step, at=S["vt"] - S["exam_t0"]))  # 부정행위를 기록한다(과목, 단계, 시험 시작 후 경과 시간)
        toast("⚠️ 제한 시간 내 확인하지 못해 부정행위로 기록되었습니다.", 4000)  # 부정행위로 기록되었다는 알림을 띄운다
    el("overlay").hidden = True  # 확인창을 숨긴다
    if phase == "exam_confirm":  # 시험 종료 확인이었다면
        if S["ei"] >= len(S["events"]):  # 마지막 방송이었다면
            finish_all()  # 최종 결과 처리로 넘어간다
        else:                                         # 다음 방송까지 쉬는 시간
            S["break_total"] += S["events"][S["ei"]]["t"] - S["end_ev_t"]  # 다음 방송까지의 쉬는 시간 길이를 합계에 더한다
            S["phase"] = "break"  # 쉬는 시간 단계로 바꾼다
    else:  # 쉬는 시간 종료 확인이었다면
        S["phase"] = "pre"  # 시험 준비 단계로 바꾼다


def on_confirm_click(e=None):  # 확인 버튼을 눌렀을 때 실행되는 함수
    if S["phase"] in ("exam_confirm", "break_confirm"):  # 확인창이 열려 있는 단계에서만
        confirm_done(False)  # 제시간에 확인한 것으로 처리한다


def skip_next(e=None):  # 다음 방송 시각으로 건너뛰는 함수
    """시험장 시각을 다음 방송 시각으로 옮긴다. 누를 때마다 방송이 하나씩(예비령 → 준비령 → 본령 …) 나온다."""  # 함수 설명(누를 때마다 방송이 하나씩 나옴)
    if S["phase"] in ("pre", "exam", "break") and S["ei"] < len(S["events"]):  # 건너뛸 수 있는 단계이고 다음 방송이 남아 있으면
        stop_broadcasts()                             # 재생 중이던 방송은 바로 끊는다
        S["vt"] = max(S["vt"], S["events"][S["ei"]]["t"])  # 시험장 시각을 다음 방송 시각으로 옮긴다


# ───────────── 결과 기록 (localStorage) ─────────────
def load_hist():  # 저장된 시험 기록을 읽어 오는 함수
    try:  # 오류에 대비해 시도한다
        raw = window.localStorage.getItem(HIST_KEY)  # 브라우저 localStorage에서 저장된 문자열을 읽는다
        d = json.loads(raw) if raw else []  # 문자열이 있으면 JSON을 리스트로 바꾸고 없으면 빈 리스트
        return d if isinstance(d, list) else []  # 리스트이면 돌려주고 아니면 빈 리스트를 돌려준다
    except Exception:  # 오류가 나면
        return []  # 빈 리스트를 돌려준다


def save_hist(h):  # 시험 기록을 저장하는 함수
    try:  # 오류에 대비해 시도한다
        window.localStorage.setItem(HIST_KEY, json.dumps(h, ensure_ascii=False))  # 기록을 JSON 문자열로 바꿔 localStorage에 저장한다
    except Exception:  # 오류가 나면
        pass  # 무시하고 넘어간다


def render_history():  # 시작 화면의 이전 시험 기록을 그리는 함수
    h = load_hist()  # 저장된 기록을 불러온다
    el("histCard").hidden = not h  # 기록이 없으면 기록 카드를 숨긴다
    rows = []  # 화면에 표시할 줄 목록을 만든다
    for r in h:  # 기록을 하나씩 반복한다
        c = r.get("cheats", [])  # 그 기록의 부정행위 목록을 가져온다
        if c:  # 부정행위가 있으면
            detail = "".join(f'<br>&nbsp;&nbsp;⚠️ {x["subject"]} · {x["step"]} · 시험 시작 후 {hms(x["at"])}' for x in c)  # 부정행위 상세 줄(과목, 단계, 발생 시점)을 만든다
            cheat = f'<span class="danger">부정행위 {len(c)}건</span>{detail}'  # 부정행위 건수와 상세를 합친다
        else:  # 부정행위가 없으면
            cheat = '<span class="ok">부정행위 없음</span>'  # "부정행위 없음" 문구를 만든다
        rows.append(f'<li><b>{r["date"]}</b> · 수험번호 {r["candidate"]} · {r["label"]}<br>'  # 한 줄의 앞부분(날짜, 수험번호, 시험 이름)을 만든다
                    f'시험 {hms(r["elapsed"])} · 쉬는 시간 {hms(r["breaks"])} · {cheat}</li>')  # 시험 시간, 쉬는 시간, 부정행위 요약을 이어 붙여 줄 목록에 추가한다
    el("histBody").innerHTML = "<ul>" + "".join(rows) + "</ul>"  # 줄들을 목록 HTML로 합쳐 화면에 표시한다


def clear_hist(e=None):  # 저장된 시험 기록을 지우는 함수
    if window.confirm("저장된 시험 기록을 모두 삭제할까요?"):  # 확인창에서 사용자가 동의하면
        save_hist([])  # 기록을 빈 리스트로 저장한다
        render_history()  # 화면을 갱신한다


# ───────────── 결과 / 초기화 ─────────────
def finish_all():  # 전체 시험이 끝났을 때 결과를 보여 주는 함수
    S["phase"] = "done"  # 진행 단계를 완료로 바꾼다
    if S["cheats"]:  # 부정행위가 있으면
        items = "".join(f'<li class="danger">{c["subject"]} · {c["step"]} · 시험 시작 후 {hms(c["at"])}</li>' for c in S["cheats"])  # 부정행위 항목들을 목록 HTML로 만든다
        cheat_html = f'<b class="danger">부정행위 {len(S["cheats"])}건</b><ul>{items}</ul>'  # 건수와 목록을 합쳐 표시 문구를 만든다
    else:  # 부정행위가 없으면
        cheat_html = '<b class="ok">✅ 부정행위 없음</b>'  # "부정행위 없음" 표시 문구를 만든다
    label = "통합" if S["sel"] == ("full",) else UNITS[S["order"][0]]["name"]  # 시험 이름 라벨을 정한다(통합 또는 과목 이름)
    entry = dict(date=str(window.Date.new().toLocaleString("ko-KR")), candidate=S["candidate"], label=label,  # 저장할 기록 한 건을 만든다(날짜, 수험번호, 시험 이름)
                 elapsed=S["vt"] - S["exam_t0"], breaks=S["break_total"], cheats=list(S["cheats"]))  # 소요 시간, 쉬는 시간, 부정행위 목록을 기록에 넣는다
    save_hist(([entry] + load_hist())[:10])           # 최근 10개 보관
    render_history()  # 시작 화면의 기록 표시를 갱신한다
    el("resBody").innerHTML = (  # 결과 화면 내용을 채우기 시작한다
        f'수험번호: <b>{S["candidate"]}</b><br>'  # 수험번호를 보여 준다
        f'전체 시험 종료: 시험 시작 후 <b>{hms(S["vt"] - S["exam_t0"])}</b> (시험장 시각 {clock_text(S["vt"])[:5]})<br>'  # 전체 시험 종료까지 걸린 시간과 종료 시험장 시각을 보여 준다
        f'쉬는 시간 합계: <b>{hms(S["break_total"])}</b><br>{cheat_html}')  # 쉬는 시간 합계와 부정행위 결과를 보여 준다
    el("cheer").textContent = random.choice(CHEERS)   # 한 줄만 출력
    show("result")  # 결과 화면을 보여 준다


def go_home(e=None):  # 처음으로 돌아가며 입력과 진행 상태를 초기화하는 함수
    stop_everything()  # 재생 중인 모든 소리를 멈춘다
    S.clear()  # 상태 딕셔너리를 비운다
    S.update(fresh_state())  # 초기 상태로 다시 채운다
    el("candInput").value = ""  # 수험번호 입력칸을 비운다
    el("overlay").hidden = True  # 10초 확인창을 숨긴다
    for p, items, btn in (("prep", PREP_ITEMS, "prepNext"), ("dev", DEVICES, "devNext")):  # 준비물과 전자기기 체크리스트를 하나씩 반복한다
        for i in range(len(items)):  # 각 체크 항목을 반복한다
            el(f"{p}-{i}").checked = False  # 체크를 해제한다
        el(btn).disabled = True  # 다음 버튼을 다시 비활성화한다
    update_select("선택된 시험이 없습니다.")  # 선택 안내 문구를 처음 상태로 되돌린다
    refresh_noise_buttons()  # 소음 버튼을 OFF 표시로 갱신한다
    render_history()  # 저장된 이전 시험 기록을 시작 화면에 표시한다
    show("welcome")  # 시작 화면을 보여 준다


def set_theme(t):  # 화면 테마(라이트/다크)를 적용하는 함수
    document.documentElement.setAttribute("data-theme", t)  # html 요소의 data-theme 속성을 바꿔 색상 변수를 전환한다
    el("themeBtn").textContent = "☀️ 라이트" if t == "dark" else "🌙 다크"  # 테마 버튼의 글자를 바꾼다


def toggle_theme(e=None):  # 테마를 서로 번갈아 바꾸는 함수
    set_theme("light" if document.documentElement.getAttribute("data-theme") == "dark" else "dark")  # 현재가 다크면 라이트로, 아니면 다크로 바꾼다


# ───────────── 메인 루프 ─────────────
def render():  # 현재 상태를 화면에 그리는 함수
    ph, vt, evs, ei = S["phase"], S["vt"], S["events"], S["ei"]  # 자주 쓰는 상태 값을 꺼낸다
    nxt = evs[ei] if ei < len(evs) else None  # 다음 방송 이벤트를 구한다(없으면 None)
    rem, frac, name, status = 0.0, 0.0, UNITS[S["cur"]]["name"], ""  # 남은 시간, 남은 비율, 이름, 상태 문구의 기본값을 정한다
    if ph in ("exam", "exam_confirm"):  # 시험 중이거나 종료 확인 중이면
        rem = max(0.0, S["end_t"] - vt)  # 종료령까지 남은 시간을 구한다
        frac = rem / (S["end_t"] - S["start_t"])  # 전체 시험 시간 대비 남은 비율을 구한다
        status = "진행 중" if ph == "exam" else "시험 종료"  # 상태 문구를 정한다
    elif ph == "pre":  # 시험 준비 단계이면
        start = next((e for e in evs[ei:] if e["kind"] == "start"), None)  # 다음 본령 이벤트를 찾는다
        if start:  # 본령이 있으면
            rem, name = max(0.0, start["t"] - vt), UNITS[start["unit"]]["name"]  # 본령까지 남은 시간과 과목 이름을 구한다
        status = "시험 준비 · 본령까지"  # 상태 문구를 정한다
    elif ph in ("break", "break_confirm"):  # 쉬는 시간 단계이면
        rem = max(0.0, nxt["t"] - vt) if nxt else 0.0  # 다음 방송까지 남은 시간을 구한다
        name, status = "☕ 쉬는 시간", "다음 방송까지" if ph == "break" else "쉬는 시간 종료"  # 이름과 상태 문구를 정한다
    el("examName").textContent = name  # 과목 또는 상태 이름을 화면에 표시한다
    el("roomClock").textContent = f"시험장 시각 {clock_text(vt)}"  # 시험장 시각을 화면에 표시한다
    el("digital").textContent = mmss(rem)  # 디지털 남은 시간을 화면에 표시한다
    el("digital").classList.toggle("warn", ph == "exam" and rem <= 60)  # 시험 중 1분 이하이면 경고색을 입힌다
    el("examStatus").textContent = status  # 상태 문구를 화면에 표시한다
    el("clock").innerHTML = clock_svg(vt, frac)  # 아날로그 시계를 새로 그린다


def tick(*args):  # 0.1초마다 실행되는 메인 루프 함수
    t = now_ms()  # 현재 시각을 구한다
    dt, S["last"] = (t - S["last"]) / 1000, t  # 지난 시간(초)을 계산하고 마지막 시각을 갱신한다
    ph = S["phase"]  # 현재 단계를 가져온다
    if ph in ("idle", "done"):  # 시작 전이거나 끝난 상태이면
        return  # 아무것도 하지 않고 끝낸다
    S["vt"] += dt * TIME_SCALE  # 흐른 시간만큼 시험장 시각을 증가시킨다
    while (S["phase"] in ("pre", "exam", "break") and S["ei"] < len(S["events"])  # 방송할 시각이 된 이벤트가 있는 동안 반복한다(조건 1: 진행 단계이고 이벤트가 남음)
                                    and S["vt"] >= S["events"][S["ei"]]["t"]):  # (조건 2: 시험장 시각이 이벤트 시각 이상)
        ev = S["events"][S["ei"]]  # 처리할 이벤트를 가져온다
        was_break = S["phase"] == "break"  # 직전 단계가 쉬는 시간이었는지 기억한다
        S["ei"] += 1  # 다음 이벤트 위치로 이동한다
        fire(ev)  # 방송 이벤트를 실행한다
        if was_break and ev["kind"] == "pre":         # 쉬는 시간 종료 방송 → 10초 확인
            open_confirm("break_confirm", "🔔 쉬는 시간 종료", f"{CONFIRM_SEC}초 안에 확인 버튼을 눌러 주세요.")  # 10초 확인창을 연다
    if S["phase"] == "exam" and t >= S["next_noise"]:  # 시험 중이고 소음 재생 시각이 되었으면
        fire_noise()  # 무작위 소음을 재생한다
    if S["phase"] in ("exam_confirm", "break_confirm"):  # 확인 단계이면
        left = (S["deadline"] - t) / 1000  # 확인 마감까지 남은 시간(초)을 구한다
        el("cdown").textContent = str(max(0, math.ceil(left)))  # 카운트다운 숫자를 갱신한다
        if left <= 0:  # 시간이 다 지났으면
            confirm_done(True)  # 부정행위로 처리한다
    if S["phase"] != "done":  # 종료 상태가 아니면
        render()  # 화면을 갱신한다


# ───────────── 시작 ─────────────
build_ui()  # 화면 HTML을 만들어 페이지에 넣는다
on("enterBtn", "click", show_candidate)  # 시험 환경 시작 버튼을 수험번호 화면 열기에 연결한다
on("candBack", "click", lambda e: show("welcome"))  # 수험번호 화면의 이전 버튼을 시작 화면 이동에 연결한다
on("candNext", "click", accept_candidate)  # 수험번호 화면의 다음 버튼을 입력 검사에 연결한다
on("candInput", "keydown", lambda e: accept_candidate() if e.key == "Enter" else None)  # 입력칸에서 엔터를 눌러도 다음으로 넘어가게 한다
for i in range(len(UNITS)):  # 시험 단위 번호를 하나씩 반복한다
    on(f"subj-{i}", "click", lambda e, i=i: pick_single(i))  # 과목 버튼을 누르면 해당 과목이 선택되게 연결한다
on("fullBtn", "click", pick_full)  # 통합 버튼을 통합 선택에 연결한다
for p in ("select", "exam"):  # 시험 선택 화면과 시험 화면을 반복한다
    for k in NOISE_KEYS:  # 소음 키를 하나씩 반복한다
        on(f"nz-{p}-{k}", "click", lambda e, k=k: toggle_noise(k))  # 소음 버튼을 누르면 ON/OFF가 바뀌게 연결한다
on("selNext", "click", lambda e: show("prep"))  # 시험 선택 화면의 다음 버튼을 준비물 화면 이동에 연결한다
for i in range(len(PREP_ITEMS)):  # 준비물 체크박스를 하나씩 반복한다
    on(f"prep-{i}", "change", lambda e: check_all("prep", len(PREP_ITEMS), "prepNext"))  # 체크가 바뀔 때마다 모두 체크되었는지 검사하게 연결한다
on("prepNext", "click", lambda e: show("device"))  # 준비물 화면의 다음 버튼을 전자기기 화면 이동에 연결한다
for i in range(len(DEVICES)):  # 전자기기 체크박스를 하나씩 반복한다
    on(f"dev-{i}", "change", lambda e: check_all("dev", len(DEVICES), "devNext"))  # 체크가 바뀔 때마다 모두 체크되었는지 검사하게 연결한다
on("devNext", "click", enter_exam)  # 시험장 입장 버튼을 시험 시작에 연결한다
on("skipNext", "click", skip_next)  # 스킵 버튼을 다음 방송 이동에 연결한다
on("ovBtn", "click", on_confirm_click)  # 확인창의 확인 버튼을 확인 처리에 연결한다
on("homeBtn", "click", go_home)  # 처음으로 돌아가기 버튼을 초기화에 연결한다
on("histClear", "click", clear_hist)  # 기록 삭제 버튼을 기록 삭제에 연결한다
on("themeBtn", "click", toggle_theme)  # 테마 버튼을 테마 전환에 연결한다

set_theme("dark" if window.matchMedia("(prefers-color-scheme: dark)").matches else "light")  # 시스템이 다크 모드면 다크로, 아니면 라이트로 시작한다
refresh_noise_buttons()  # 소음 버튼의 처음 표시를 만든다
render_history()  # 저장된 이전 시험 기록을 표시한다
load_sounds()  # 소리 파일 불러오기를 시작한다
show("welcome")  # 시작 화면을 보여 준다
window.setInterval(create_proxy(tick), 100)  # 0.1초마다 tick 함수를 반복 실행한다
