# {프로젝트명} ({SYSTEM_CODE})

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다. 본 파일은 레포 루트(`/README.md`)에 배치한다. 작성 후 본 경고 줄은 삭제한다.

> {프로젝트 한 줄 요약 — 무엇을 하는 시스템인가, 누구를 위한 것인가}

[![Status](https://img.shields.io/badge/status-{Draft|Alpha|Beta|Stable}-blue)]() [![License](https://img.shields.io/badge/license-{MIT|Apache--2.0|Proprietary}-green)]()

---

## 개요

{2~4줄 요약. 제품의 목적·핵심 가치·범위. 더 깊은 컨텍스트는 [`docs/PRD.md`](docs/PRD.md) 참조.}

## 빠른 시작

### 사전 요구사항

- {언어·런타임, 예: .NET 6+ / Node 18+ / JVM 17}
- {빌드 도구, 예: dotnet CLI / npm / gradle}
- {OS 또는 컨테이너}

### 빌드·실행

```{shell}
{빌드 명령}
{서비스 실행 명령}
{클라이언트 실행 명령}
{테스트 실행 명령}
```

### 환경 변수 / 설정

| 키 | 기본값 | 설명 |
|---|---|---|
| `{KEY}` | `{기본값}` | {용도} |

## 아키텍처

{한 단락 요약. 호스트 N종 + 통신 방식 + 저장소}.

상세는 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 참조 (DDD 5-레이어·참조 매트릭스·폴더→레이어 매핑).

## 문서

| 영역 | 경로 |
|---|---|
| 문서 작성 룰 | [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) |
| 솔루션 아키텍처 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| App 요구사항 | [`docs/{SYSTEM_CODE}/{SYSTEM_CODE}-PRD.md`](docs/{SYSTEM_CODE}/{SYSTEM_CODE}-PRD.md) |
| App 기능 레지스트리 | [`docs/{SYSTEM_CODE}/{SYSTEM_CODE}-FC.md`](docs/{SYSTEM_CODE}/{SYSTEM_CODE}-FC.md) |
| App 기능별 상세 | [`docs/{SYSTEM_CODE}/FRD/`](docs/{SYSTEM_CODE}/FRD/) |
| App AI 실행용 작업 지시서 (휘발성) | [`docs/{SYSTEM_CODE}/TASK/`](docs/{SYSTEM_CODE}/TASK/) |
| App 결정 이력 | [`docs/{SYSTEM_CODE}/{SYSTEM_CODE}-ADR-CATALOG.md`](docs/{SYSTEM_CODE}/{SYSTEM_CODE}-ADR-CATALOG.md) |
| 코드 레이어 규칙 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |

> AI 에이전트(Claude Code 등)로 작업 시: 레포 루트 [`CLAUDE.md`](CLAUDE.md)를 참조한다.

## 기여

{기여 정책. 예: 신규 기능은 PRD → FC → FRD 갱신 후 구현 착수. FRD 에는 코드 상세를 쓰지 않는다. AI 실행용 코드 작업 (feature / refactor / maintenance / migration / setup / investigation) 은 TASK 양식 (휘발성 + self-contained) 으로 작성한다. 상세는 docs/DOCUMENT_GUIDE.md §2. RFD 양식은 v0.7 폐기.}

- 커밋 메시지: {conventional commits 형식 — `feat:`, `fix:`, `docs:`, `refactor:` 등}
- PR 전 체크리스트: [`docs/DOCUMENT_GUIDE.md` §9](docs/DOCUMENT_GUIDE.md) 검증 항목 통과.

## 라이선스

{MIT / Apache-2.0 / Proprietary 등 라이선스 명시}. 상세는 `LICENSE` 파일 참조.

## 연락처

- {유지보수자 이름·연락처 또는 Slack 채널·이슈 트래커 URL}
