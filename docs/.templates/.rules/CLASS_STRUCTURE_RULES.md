---
paths:
  - "Src/**/*.cs"
---

# 클래스 작성 규약

이 문서는 신규 C# 클래스의 **물리적 구조·크기·공개 표면 규약**을 정의한다. 추상 설계 원칙(SRP/OCP/DIP·함수 책임 분해)은 [`OBJECT_ORIENTED_DESIGN_RULES.md`](OBJECT_ORIENTED_DESIGN_RULES.md) 가 담당하며, 본 문서는 그 원칙을 코드 레이아웃으로 강제하는 구체 규약이다.

## 1. 클래스 크기

- 한 클래스는 **반드시 300 라인 미만**으로 유지한다.
- 300 라인 초과 = **책임 과다 신호** → **반드시** `OBJECT_ORIENTED_DESIGN_RULES.md` §1(클래스 SRP) 기준으로 책임을 분리한다.

## 2. 공개 표면 — 흐름 관장 (orchestration only)

- `public`/`protected` 함수는 **반드시** `private` 함수를 호출해 **흐름(orchestration)만 관장**한다.
- 세부 구현(외부 호출·변환·분기 결정·부수효과)을 `public`/`protected` 본문에 인라인하는 것은 **금지**한다.
- 공개 함수는 "무엇을 하는가"의 **호출 시퀀스로 읽혀야** 하고, 실제 "어떻게"는 **반드시** `private`에 둔다.
- 함수의 단일 책임 기준은 `OBJECT_ORIENTED_DESIGN_RULES.md` §4(함수 SRP) 를 따른다.

## 3. `#region` 표준 레이아웃

신규 C# 클래스는 **반드시** 아래 `#region` 레이아웃을 따른다. 해당 region 에 내용이 없으면 빈 region 을 유지하거나 삭제하되, **순서는 반드시 보존**한다.

```csharp
#region 형식
#endregion

#region 필드
#endregion

#region 속성
#endregion

#region 생성자 및 소멸자
#endregion

#region 함수
#endregion

#region 이벤트
#endregion

#region 외부 프로퍼티
#endregion

#region 외부 메서드
#endregion
```

## 4. 자기 점검 체크리스트

신규 클래스/PR 작성 시 **반드시** 통과시킨다.

- [ ] 클래스가 300 라인 미만인가
- [ ] `public`/`protected` 함수가 `private` 함수 호출로 흐름만 관장하는가 (세부 구현 인라인 금지)
- [ ] 신규 클래스가 § 3 `#region` 표준 레이아웃을 순서대로 따르는가
