---
allowed-tools: Bash(git status:*), Bash(git add:*), Bash(git diff:*), Bash(git commit:*), Bash(git reset:*), Read
description: 변경사항 분석 후 구분자 선택하여 커밋 생성
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

## 규칙

1. **커밋 메시지 형식**: `[구분자] <설명>` 형태로 작성
2. **제외 파일**: `.md` 파일은 커밋에 포함하지 않음
3. **제외 문구**: "Claude Code가 커밋했습니다", "Generated with Claude Code", "Co-Authored-By" 등의 문구 제외
4. **분석 기반**: 실제 변경된 코드를 분석하여 의미있는 한글 메시지 작성

## 작업 흐름

1. 위의 변경사항을 분석하여 주요 변경 내용 파악
2. `.md` 파일은 제외하고 코드 파일만 스테이징
3. 변경 내용을 분석하여 적절한 구분자를 스스로 판단하여 선택
   - `[ADD]`: 새로운 기능, 파일, 클래스 등 추가
   - `[MOD]`: 기존 코드 수정, 리팩토링, 개선
   - `[FIX]`: 버그 수정, 오류 해결
4. 선택한 구분자와 함께 커밋 메시지 작성 후 커밋 수행

## MD 파일 제외 방법

```bash
# 모든 파일 add 후 md 파일만 unstage
git add --all
git reset -- "*.md"

# 또는 특정 확장자만 add
git add "*.cs" "*.xaml" "*.csproj" "*.json" "*.config"
```

## 커밋 메시지 예시

- `[ADD] 사용자 인증 모듈 추가`
- `[MOD] ApiGateway WebSocket 연결 로직 개선`
- `[FIX] 메모리 누수 버그 수정`
