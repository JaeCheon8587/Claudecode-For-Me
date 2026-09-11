---
allowed-tools: Bash(git status:*), Bash(git add:*), Bash(git diff:*), Bash(git commit:*), Bash(git reset:*), Read, AskUserQuestion
description: 변경사항 분석 후 배포 여부 확인 + 구분자 선택하여 커밋 생성
---

# 커밋 분석 및 생성

## 현재 변경사항
!`git status --short`

## Staged 변경사항
!`git diff --cached --stat`

## Unstaged 변경사항
!`git diff --stat`

## 구분자 목록

| 구분자 | 설명 |
|--------|------|
| `[ADD]` | 새로운 기능/파일 추가 |
| `[MOD]` | 기존 코드 수정/개선 |
| `[FIX]` | 버그 수정 |

## 배포 여부 선택 (AskUserQuestion)

커밋 메시지를 확정하기 전에 **반드시** AskUserQuestion으로 물음. 텍스트로만 묻고 넘어가지 말 것 — 명시 선택을 받아야 커밋 진행.

- 질문: "이번 커밋, 푸쉬하면 배포까지 나가나요?"
- 옵션:
  - **배포 없음** — 기존 규칙대로 `[구분자] <설명>` 한 줄만 작성
  - **배포 포함** — 푸쉬 시 CD 파이프라인 동작. 커밋 메시지 본문에 `[Deploy]` 추가
- 이 커맨드는 어느 쪽을 골라도 **push를 실행하지 않는다**. 커밋까지만 수행하고 push는 사용자가 직접 한다.

## 규칙

1. **커밋 메시지 형식**: `[구분자] <설명>` 형태로 작성
2. **제외 파일**: `.md` 파일은 커밋에 포함하지 않음
3. **제외 문구**: "Claude Code가 커밋했습니다", "Generated with Claude Code", "Co-Authored-By" 등의 문구 제외
4. **분석 기반**: 실제 변경된 코드를 분석하여 의미있는 한글 메시지 작성
5. **배포 마커**: "배포 포함"을 선택한 경우에만 커밋 메시지 **본문(body)** 첫 줄에 `[Deploy]`를 넣는다. 제목 줄은 `[구분자] <설명>` 형식을 그대로 유지한다. "배포 없음"이면 본문 없이 제목 한 줄로 끝낸다.

## 작업 흐름

1. 위의 변경사항을 분석하여 주요 변경 내용 파악
2. **배포 여부 선택** — AskUserQuestion으로 "배포 없음 / 배포 포함" 확인
3. `.md` 파일은 제외하고 코드 파일만 스테이징
4. 변경 내용을 분석하여 적절한 구분자를 스스로 판단하여 선택
   - `[ADD]`: 새로운 기능, 파일, 클래스 등 추가
   - `[MOD]`: 기존 코드 수정, 리팩토링, 개선
   - `[FIX]`: 버그 수정, 오류 해결
5. 선택한 구분자와 함께 커밋 메시지 작성 후 커밋 수행 — 2단계에서 "배포 포함"이면 본문에 `[Deploy]` 포함

## MD 파일 제외 방법

```bash
# 모든 파일 add 후 md 파일만 unstage
git add --all
git reset -- "*.md"

# 또는 특정 확장자만 add
git add "*.cs" "*.xaml" "*.csproj" "*.json" "*.config"
```

## 커밋 메시지 예시

배포 없음 (제목 한 줄):

- `[ADD] 사용자 인증 모듈 추가`
- `[MOD] ApiGateway WebSocket 연결 로직 개선`
- `[FIX] 메모리 누수 버그 수정`

배포 포함 (본문에 `[Deploy]`):

```text
[MOD] ApiGateway WebSocket 연결 로직 개선

[Deploy]
```

실행 명령:

```bash
git commit -m "[MOD] ApiGateway WebSocket 연결 로직 개선" -m "[Deploy]"
```
