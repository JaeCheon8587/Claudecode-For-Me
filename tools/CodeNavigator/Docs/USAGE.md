# CodeNavigator 사용법

cmd / PowerShell 예시. `--root` 생략 시 cwd.

## 설치

```
pip install -e .
```

## status — 인덱스 통계

```
codenav status
codenav --root D:\repo status
```

## reindex — 인덱스 생성/갱신

전체:

```
codenav reindex --full
```

특정 파일:

```
codenav reindex --files src\A.cs src\B.cs
```

staged .cs만 (pre-commit용):

```
codenav reindex --changed --verbose
```

## search — 키워드 검색

```
codenav search "데이터 수집"
codenav search "이벤트" --limit 5
codenav search "주문" --scope method
codenav search "리포" --project Infra
codenav search "버스" --json
```

## delete — 파일 인덱스 삭제

dry-run (기본):

```
codenav delete --file src\Old.cs
```

실제 삭제:

```
codenav delete --file src\Old.cs --yes
```

## ui — 로컬 웹 UI

```
codenav ui
codenav ui --port 9000
```

브라우저: http://127.0.0.1:8765
