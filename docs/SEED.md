---
doc_kind: explanation
status: canonical
version: 2026-06-21_v1.2
canonical_path: self
---

# RightSeat — SEED (의도 정본)

> 이 프로젝트가 *무엇을 위한 것인가*의 단일 정본. 표류하면 여기로 돌아온다.
> 2026-06-20 wiw로 박음. 의도가 바뀌면 이 파일을 in-place로 refine하고 변경 한 줄을 남긴다.
>
> 변경 로그:
> - 2026-06-20 v1: 최초 박제.
> - 2026-06-20 v1.1: 검사관 머리(파싱·흐름·외부대조) 운반 독립 완성. "다음=tmux attach 배선"은
>   버린 길로의 회귀라 폐기 → "다음=Sidabari 몸 통합". workdir는 PTY 소유면 자명(tmux 감지 금지) 명시.
> - 2026-06-21 v1.2: 실측으로 3건 확정. ① 몸=**sidabari4loop**(원본 아님 — 원본은 비보북 빌드
>   지옥[rust 4버전 실패·release exe 없음]=실행 불가, 4loop은 깔끔). ② 검사관=**단순 프롬프트**
>   (seed+증거→맞나/교정 한 줄, claude·codex 교체 실측) — completion_gate 복잡 파이프라인 폐기.
>   ③ 구조=**비보북 GUI + elitedesk worker(ssh)**, worker는 claude 외(codex 등)도 — auto_start
>   끄면 셸에서 임의 worker 직접. (이번 세션 반복 실수: 정본·구조를 1회 안 떠올리고 즉흥 반사로
>   움직임 → 빈 동작. 정본은 rules 1.6.1, 여기 박지 않음.)

## 중심 의도 (한 줄)

**어떤 작업이든 수동·자동으로 돌리는 범용 루프.** 외부·불가시 검사관이 의도(seed) 정합성을 지킨다. 수동↔자동은 검사관을 끄는 게 아니라 **운전대 주인만 바꾸는 다이얼**이다. 양산은 그 안의 한 칸(하위 응용).

## 목적 (왜)

- 어떤 작업이든(코딩·문서·분석·무엇이든) 사람이 직접 운전하든(수동) 맡기고 떠나든(자동) 그 사이 어디든 굴릴 수 있는 시스템.
- 근본 동기: 5개월+ ralph·ooo를 써봤으나 결과가 개판이었고, 근본 원인이 **채점자가 내부에 있어 self-judge가 봐주고 환각**하는 것임을 발견. 그래서 핵심은 "외부·보이지 않는 채점자".

## 수단 (어떻게)

- **몸 = sidabari4loop 그대로.** 공장(PTY 소유·GUI·자율 루프 골격·증거 캡처)을 베이스로 쓰고 "검사 자리" 한 곳만 개조. 처음부터 다시 안 만든다. (원본 sidabari 아님 — 실측 확정: 원본은 비보북에서 빌드 지옥[rust 1.95/1.85/1.90 + cargo update 4번 다 다른 crate가 깨짐]이고 release exe도 없어 실행 불가. 4loop은 깔끔히 빌드[rust 1.95 + RUST_MIN_STACK], 비보북에 빌드 완료. 4loop은 README상 "자율 루프를 깨끗하게" 하려 만들어져 우리 목적과 정확히 일치.)
- **구조 = ooo 그대로.** 의도→체크리스트(rubric)→생성→진화 루프는 ooo가 이미 한다. **딱 한 곳, 점검(평가)만 외부로 뺀다.**
- **머리 = RightSeat(외부 검사관, Python).** worker가 못 보는 곳에서, seed에서 뽑은 측정 가능한 기준에 결과물 증거를 **TRUE/FALSE로 대조만** 한다. 판단이 아니라 대조라 멍청해도 된다(jd 철학: AI 임의판단 금지, 결정론 교차대조). 구현은 **단순 프롬프트**(seed + 결과물 증거 → "맞나 / 교정 한 줄") — claude·codex 교체 가능, 실측 완료. completion_gate식 복잡 검증 파이프라인은 폐기(2026-06-21).
- **증거 = 이미 가진 도구로.** 코드=test/typecheck, worker 행동=Sidabari Hook·PTY, UI=browse, 변경=diff/codex.
- **연결 = 프로세스 경계.** Sidabari가 turn 경계에서 RightSeat(Python 검사관)를 호출. TS로 재구현하지 않는다.
- **수동/자동 = 같은 시스템의 두 모드.** mode tier(paused/suggest/confirm/auto)가 다이얼. 검사관은 항상 켜져 있고, 바뀌는 건 "사람이 직접 입력하느냐"뿐. 매끄러운 전환은 양방향 공유 상태에 의존 — 떠날 때 seed(방향), 돌아올 때 ledger(주행기록).

## 성공기준 (됐다의 정의)

- **검사관 머리(실측 완료, 2026-06-21):** seed + 결과물 증거를 단순 프롬프트로 외부 대조 — claude·codex 둘 다 worker의 "완성" 거짓말 안 속고 drift(도메인 다름·소스 누락) 적발, 증거 없으면 FAIL, 교정 한 줄 냄. completion_gate 복잡 파이프라인은 폐기.
- **다음:** 그 머리를 4loop 몸에 연결 = worker(claude 외 codex 등)를 PTY로 소유해 띄우고(**비보북 GUI + elitedesk worker via ssh**), turn 감지를 Claude Hook → **화면 idle 감지**로 바꿔 turn 경계에서 검사관(단순 프롬프트)을 프로세스로 호출. + 수동↔자동 전환.
- **최종:** 작업 하나를 seed만 주고 돌려, 외부 채점자가 "seed에 합치"라고 통과시킨 결과물이 나온다. (양산 = 자동 모드 + 제품 작업의 한 사례로 따라옴)

## 비목표·제약 (하지 말 것)

- **양산을 의도로 착각하지 않는다.** 양산은 하위 응용이지 목적이 아니다. 시스템을 제품 빌드 전용으로 좁히지 않는다.
- 또 다른 ralph/루프 도구를 만들지 않는다(레드오션, Anthropic `/loop` 내장). 차별점은 루프가 아니라 외부 검사관.
- 채점자에게 "판단"시키지 않는다. 대조만. "LLM이 똑똑하냐"를 다시 묻지 않는다.
- 채점자를 내부에 두지 않는다(ooo가 망한 이유).
- Sidabari를 처음부터 다시 만들지 않는다. 검사 자리 한 곳만 개조.
- 판단 로직을 TS로 재구현하지 않는다(검증된 Python 유지).
- 운반/tmux 코드를 자기방어로 붙들지 않는다(버림). 단 판단 규칙은 살린다.
- 범위를 처음부터 넓히지 않는다. 토이 웹/CLI로 좁혀 시작(증거 수집이 깔끔한 범위).
- 순서: 화려한 GUI(몸) 먼저 안 만든다. **검사관(머리) 먼저.**
- **검사관을 tmux attach 루프에 꽂지 않는다(버릴 코드).** Sidabari 몸에 꽂는다.
- **workdir 등 운반 세부를 tmux에서 캐내지 않는다.** worker를 PTY로 소유하면 띄운 폴더가 곧 workdir라 감지가 필요 없다. (2026-06-20 이 착오를 한 번 범했음 — 재발 금지.)
- **원본 sidabari로 돌아가지 않는다(실측 확정).** 빌드 지옥 + release exe 없음 = 실행 불가. 베이스는 4loop. 원본에서 탐낸 ssh는 4loop PTY 명령에 `ssh elitedesk codex`를 끼우면 된다(의존성 풀세트 불필요).
- **worker를 비보북에서 찾지 않는다.** worker는 elitedesk에서 돈다(비보북=GUI). worker용 codex는 elitedesk에 이미 있다(이 세션 검사관 실측에 썼음).
- **검사관을 복잡한 검증으로 부풀리지 않는다.** seed 합치 + 교정 한 줄이면 된다. "LLM이 똑똑하냐"로 다시 새지 않는다.

## 흘러내리면 안 되는 확정 사실 (비교)

- **RightSeat 장점:** `policy_gate`(위험 fail-closed 방화벽, 실제 배선됨, attach.py:599) · `completion_check`(done 불신·증거기반, 단 미배선) · `screen_model`(화면 상태 파싱 ~5상태) · mode tier 런타임 토글 · 가시적 외부 감독석 · 자율 중에도 위험을 멈춤.
- **RightSeat 약점:** tmux 갇힘(→ Sidabari 몸으로 대체 예정) · GUI 없음 · 772줄 attach 한 메서드 집중. (검사관 머리는 2026-06-20 완성: `verifier` 백엔드 추가·`completion_check`는 `completion_gate`로 흐름 조립됨. 남은 건 tmux가 아니라 Sidabari 몸에 연결.)
- **Sidabari 장점:** PTY 소유 · bracketed paste 주입 · Windows shim · 진짜 데스크탑 GUI(Tauri+xterm+분할패널) · 자율 루프 골격(PROGRESS.md 계약) · 증거 캡처(Hook/PTY) · 완성도.
- **Sidabari 약점:** 2차 LLM 판단 0개(고정 운영프롬프트 재주입) · 위험게이트=사람 모달 · 완료=worker 자기신고(TASK_COMPLETE 정규식) 신뢰 · 자율빌드는 깊이 안 판 곁가지.
- **맥락:** cx8537(Ho-sung Choi)=1인 인프라 운영자(nullnull.co.kr LMS 운영, WinMux 제작). LLM을 안 넣은 건 무능이 아니라 철학(프로덕션은 AI 자동판단이 위험). 업계 전체가 ralph+결정론 검증을 씀 → 우리 차별점은 **외부·불가시 채점자(seed 정합성)** 하나.

## 다음 한 걸음

검사관 머리는 완성(2026-06-20, 운반 독립, 209 테스트 green). 다음은 **Sidabari 몸 통합**:
worker를 PTY로 소유해 띄우고(그 폴더가 곧 workdir — tmux 감지 불필요), turn 경계에서
`completion_gate`를 프로세스로 호출해 결과(complete/inject/escalate)대로 운전. tmux attach.py는
배선 대상이 아니다(버릴 코드).
