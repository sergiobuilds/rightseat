# rightseat — 지도 (MASTER-MAP)

> 이 프로젝트가 무엇이고 어디까지 왔나. 한 파일로 현재 상태를 파악하는 정본.
> (스캐폴드 스텁 — 첫 의미 있는 갱신 때 채운다.)

## 무엇
어떤 작업이든 수동·자동으로 돌리는 범용 루프 + 외부·불가시 의도 검사관. 의도 정본은 [SEED](SEED.md).

## 현재 상태·범위·진척
- 의도 확정·박제(2026-06-20, [SEED](SEED.md)): Sidabari(몸)+ooo(구조)+RightSeat(외부 검사관 머리) 결합 방향.
- 검사관 머리 완성(2026-06-20, 운반 독립, 209 테스트): seed 합격기준 파싱 + `completion_gate` 흐름 + claude/codex verifier 백엔드.
- 다음 한 걸음: **Sidabari 몸 통합** — worker를 PTY로 소유해 띄우고(폴더가 곧 workdir) turn 경계에서 `completion_gate` 호출. tmux attach 배선은 폐기(버릴 코드).
