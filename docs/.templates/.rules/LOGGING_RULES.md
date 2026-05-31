---
paths:
  - "Src/**/*.cs"
---

# Service Logging Rule (v1.0)

> ApiGateway, Loader, Master, PublisherHub logging rules are merged here as the shared service logging baseline.
> Service-specific documents remain as historical detail, but new implementation should prefer this document and `Mirero.PCC.XLab.Shared.LogExtension`.

---

## 1. Scope

### 1.1 Included services
- `Src/Mirero.PCC.XLab/App/APIGateway/**`
- `Src/Mirero.PCC.XLab/Application/ApiGateway/**`
- `Src/Mirero.PCC.XLab/Infrastructure/ApiGateway/**`
- `Src/Mirero.PCC.XLab/App/Loader/**`
- `Src/Mirero.PCC.XLab/Application/Loader/**`
- `Src/Mirero.PCC.XLab/Infrastructure/Loader/**`
- `Src/Mirero.PCC.XLab/App/Master/**`
- `Src/Mirero.PCC.XLab/Application/Master/**`
- `Src/Mirero.PCC.XLab/Infrastructure/Master/**`
- `Src/Mirero.PCC.XLab/App/PublisherHub/**`
- `Src/Mirero.PCC.XLab/Application/PublisherHub/**`
- `Src/Mirero.PCC.XLab/Infrastructure/PublisherHub/**`

### 1.2 Shared implementation
- Common extension project:
  - `Src/Mirero.PCC.XLab/Shared/LogExetension/Mirero.PCC.XLab.Shared.LogExtension`
- Common namespace:
  - `Mirero.PCC.XLab.Shared.LogExtension`
- Logger type:
  - `Mirero.Asset.LogWizard.ILogger`

### 1.3 Excluded by default
- Framework logs from ASP.NET Core, YARP, NLog internals.
- Common infrastructure logs already emitted by shared RabbitMQ/WebSocket modules, unless a service explicitly owns the external I/O boundary.
- DB I/O. Current service logging rules treat DB as out of scope for `[TX]` / `[RX]`.

---

## 2. Core Principles

1. Service entry and completion are logged as `[START]` / `[END]`.
2. External I/O boundaries are logged as `[TX]` / `[RX]`.
3. Payload bodies are Debug only and must be masked and UTF-8 safe truncated.
4. Info logs should reconstruct the operational timeline without requiring Debug.
5. Debug logs hold payload, branch details, retry calculation, and other process-level detail.
6. Error logs must pass the exception object to `ILogger` so NLog can render stack traces.

Master applies a stricter process/result split: process logs such as "querying", "waiting", "retry entering" should be Debug unless they represent a result or state transition.

---

## 3. Tags

All target classes use a simple tag without brackets:

```csharp
private readonly string _tag = nameof(ClassName);
```

Do not store brackets in `_tag`. Formatting helpers add brackets.

Looping/background service classes may pass `nameof(ClassName)` to the base class and reuse the inherited tag.

---

## 4. START / END

### 4.1 Target methods

Use `[START]` / `[END]` for service/controller/handler entry points:
- Controller action methods with business logic.
- Message handler `HandleAsync`.
- `LoopingBackgroundService` entry points: `BeforeExecuteAsync`, `ApplyAsync`, `AfterExecuteAsync`.
- `BackgroundService.ExecuteAsync` tick-level work.
- Service-specific callback entry points such as PublisherHub config/heartbeat callbacks.
- ApiGateway WebSocket session lifecycle methods such as key creation, accept, remove.

Internal helpers, pure selectors, serializers, registry push/pull helpers, retry wrappers, and small mapping methods do not get their own `[START]` / `[END]`.

### 4.2 Level

`[START]` and `[END]` are Info.

### 4.3 Format

```text
[{tag}][START] method={method}
[{tag}][START] method={method} ctx={ctx}
[{tag}][END]   method={method} result={Ok|Fail|Canceled}
[{tag}][END]   method={method} result={Ok|Fail|Canceled} elapsedMs={n}
[{tag}][END]   method={method} result={Ok|Fail|Canceled} elapsedMs={n} {summary}
```

`[END]` keeps three spaces after the token for alignment.

Summary format should be machine-readable:

```text
key1=value1 key2=value2 reason=...
```

### 4.4 Elapsed time

`elapsedMs` measures the actual work block only. Exclude `Task.Delay`, idle polling waits, retry backoff sleeps, and "next tick" waits.

Use the shared helpers:

```csharp
var startedAt = ServiceLoggerExtensions.StartElapsed();
var elapsedMs = ServiceLoggerExtensions.ElapsedMs(startedAt);
```

### 4.5 Exceptions and cancellation

Canonical pattern:

```csharp
logger.LogStart(_tag, nameof(ApplyAsync));
var startedAt = ServiceLoggerExtensions.StartElapsed();
var result = LogResult.Ok;

try
{
    // work
}
catch (OperationCanceledException)
{
    result = LogResult.Canceled;
    throw;
}
catch (Exception ex)
{
    result = LogResult.Fail;
    logger.Error(ex, $"[{_tag}] >> {nameof(ApplyAsync)} exception");
    throw;
}
finally
{
    logger.LogEnd(_tag, nameof(ApplyAsync), result, ServiceLoggerExtensions.ElapsedMs(startedAt));
}
```

Business rejection such as invalid token, invalid request, or unsupported version is not an exception. Return normally with `result=Fail` and include `reason=...`.

---

## 5. TX / RX

### 5.1 Target boundaries

Log `[TX]` / `[RX]` at external I/O boundaries:
- RabbitMQ publish / consume.
- HTTP outbound.
- WebSocket send / receive.
- TCP or other external protocol boundaries.

Do not use `[TX]` / `[RX]` for in-process calls or DB I/O.

### 5.2 Level and split

Summary is Info:

```text
[{tag}][TX] type={type} messageId={messageId|-} size={size} target={target}
[{tag}][RX] type={type} messageId={messageId|-} size={size} source={source}
```

Payload is Debug:

```text
[{tag}][TX][Payload] {masked-and-truncated-payload}
[{tag}][RX][Payload] {masked-and-truncated-payload}
```

### 5.3 Field rules

| Field | Rule |
|---|---|
| `type` | DTO class name or stable operation name. Avoid spaces. |
| `messageId` | Message identifier. Use `-` when unavailable. |
| `size` | UTF-8 byte length of the original payload. |
| `target` | TX destination: URL, queue, exchange/routingKey, endpoint. |
| `source` | RX origin: URL, queue, endpoint. |
| `extra` | Optional machine-readable suffix such as `status=200 reason=ok`. |

### 5.4 Payload limit

Payload logs are capped at 8192 bytes and must be cut at a safe UTF-8 boundary:

```text
...(truncated N bytes)
```

`N` is the number of bytes actually removed after safe-boundary adjustment.

### 5.5 Sensitive data

Never log raw secrets. Shared masking covers common JSON fields and header-like values:
- `Authorization`
- `Token`
- `Password`
- `Pwd`
- `DepTicket`
- `Jwt`
- `AccessToken`
- `RefreshToken`
- `ExternalAppSecret`
- `SessionId`
- `Cookie`

Mask payload before truncation. Log size should still represent the original payload byte size.

### 5.6 Payload readability post-processing

Payload bodies are frequently long single-line JSON. Readability post-processing such as per-array-item line breaks is allowed, but **must preserve JSON validity** so the line can still be copy-pasted into a parser.

- Object delimiters split lines without dropping braces:
  - `},{` → `},\n{`
  - `[{` → `[\n{`
  - `}]` → `}\n]`
- Never replace an opening or closing brace with bare whitespace. Round-trip parse is the acceptance criterion: take the payload line, strip newlines, and `JsonDocument.Parse` must succeed.
- Apply masking (5.5) and truncation (5.4) **before** line breaking. Truncation tail (`...(truncated N bytes)`) is appended after the formatting pass.
- Format functions in the shared extension project should be covered by unit tests — payload corruption is invisible at compile time and only surfaces in operations.

### 5.7 Route / channel category

When a publisher emits to multiple channels or routing keys in a single cycle, each `[TX]` line must make the channel category identifiable at a glance.

`target` field convention:

| Boundary | `target` format |
|---|---|
| RabbitMQ direct/topic | `{exchange}/{routingKey}` |
| RabbitMQ fanout | `{exchange}/(fanout)` |
| WebSocket | `ws://{host}:{port}{path}` or stable endpoint id |
| HTTP outbound | absolute URL |

For sites that mix categories within one logical cycle, add a category tag through the existing `extra` parameter — no signature change:

```text
[{tag}][TX] type={type} messageId={m} size={n} target={t} route={category}
```

Recommended categories: `monitoring`, `temp-fanout`, `broadcast`, `unicast`, `heartbeat`. The category names are operational vocabulary, not enum values — keep them short and stable per service area.

### 5.8 Change-driven publishes — reason exposure

Services that publish based on snapshot diff or state change detection (e.g. ProcessGathering) must record **what changed and why this cycle published**. Counts alone are not enough.

- Detectors expose a per-item human-readable `reason` string alongside each change entry, not just the changed key. The Info-level cycle summary then prints them.
- Recommended reason format:
  - field-level: `{FIELD} {prev}→{next}` joined by `, ` (only fields that actually changed)
  - lifecycle: `(new entry)`, `(unmapped)`, `(restored)`
  - null transitions: render as the literal token `null` on either side
- Cycle summary layout (Info):
  ```text
  [{tag}] >> 발행 요약 — Port {n}건, Carrier {n}건, Lot {n}건
  [{tag}] >>   Port    {key}: {reason}
  [{tag}] >>   Carrier {key}: {reason}
  ```
- If the count exceeds 20, print the first 20 reason lines and append `... +M more`. The 20-item ceiling protects log volume while keeping the typical change cycle fully visible.

### 5.9 Multi-message cycles

When one business event fans out into multiple message types (e.g. monitoring + temp double-publish), the log must let a reader identify the channel split without inspecting payloads.

- Each `[TX]` carries `route=...` per 5.7.
- The cycle summary (5.8) groups counts by route category, e.g.:
  ```text
  [{tag}] >> 발행 요약 — monitoring=3 (WorkOrderFlag, MaterialWorkStatus, Lot) / temp-fanout=3 (ToolInfos, MWSInfos, LotInfos)
  ```
- Preserve message ordering in the log: if a cycle publishes in the order A → B → C, do not reorder the `[TX]` lines via async fire-and-forget. If async dispatch is required, mark the line with `(async)` per 7.1.

---

## 6. State and Queue Events

### 6.1 State transitions

ApiGateway and other stateful services may log state transitions:

```text
[{tag}][STATE] endpoint={endpoint} {from}->{to} result={Ok|Skipped|Failed|Forced} reason={reason}
```

Use Info. State transitions are operational timeline events.

### 6.2 Queue dequeue

Queue pull immediately after successful in-process dequeue may be logged as Debug:

```text
[{tag}][DEQUEUE] type={type} messageId={messageId|-} size={size} source={registry}
```

This is not external I/O and must not replace `[RX]`.

---

## 7. Service-Specific Rules

### 7.1 ApiGateway

ApiGateway keeps additional rules for WebSocket sessions, heartbeat, health checks, response awaiting, broadcast/unicast, and endpoint state transitions.

Use:
- `[STATE]` for endpoint lifecycle transitions.
- `[DEQUEUE]` for internal message registries.
- `(async)` or an equivalent prefix for fire-and-forget work when it must be distinguished from the request flow.

Typical END summaries:
- Broadcast: `pulled=1 type={T} messageId={m} clients={n} converted={true|false} sent={n}`
- Unicast: `pulled=1 target={target|-} sent={0|1} reason={ok|target_not_found|unknown_type|send_failed}`
- Routing: `pulled={0|1} routed={0|1} to={Broadcast|Unicast|Heartbeat|Response|-} dropped={0|1}`
- Health check: `restChecked={n} restFailed={n} wsChecked={n} wsResult={Ok|Fail|Timeout}`
- Watchdog: `checked={n} stuck={n} timedOut={n}`

### 7.2 Loader

Loader logs every meaningful gathering/handler tick with `[START]` / `[END]`.

Typical END summaries:
- `items={n}`
- `pushed={n}`
- `duplicates={n}`
- `reason={...}` on failures.

Existing result/status Info logs are not mechanically downgraded during migration.

### 7.3 Master

Master enforces the strict process/result distinction.

Use Debug for process logs:

```text
[{tag}] >> querying userId=...
```

Use Info only for results, state transitions, `[START]`, `[END]`, `[TX]`, `[RX]`.

Liveness endpoints that are high-frequency and side-effect-free do not require `[START]` / `[END]`.

### 7.4 PublisherHub

PublisherHub has long-lived connections and polling loops. Pure idle ticks may omit `[START]` / `[END]`.

Log `[START]` / `[END]` when:
- a message is pulled, pushed, deserialized, or published;
- connection state changes;
- reconnect is attempted;
- heartbeat timeout, config sync retry, or health check handling occurs.

Pure idle polling may be skipped to avoid log volume.

---

## 8. Logger Names

Service logger names and file routing remain service-owned constants:
- `ApiGatewayLogger`
- `LoaderLogger`
- `MasterLogger`
- `PublisherHubLogger`

The shared extension project defines message format and helper behavior only. It does not own NLog target layout, archive policy, or service-specific logger-name constants.

---

## 9. Common API

The shared project should provide:

```csharp
enum LogResult { Ok, Fail, Canceled }
enum StateResult { Ok, Skipped, Failed, Forced }

long StartElapsed();
long ElapsedMs(long startedAt);
int Utf8Size(string payload);
string ToPayload(object value);
int MessageSize(object value);
string Mask(string value);
string MaskSecrets(string value);

void LogStart(this ILogger logger, string tag, string method, string ctx = null);
void LogEnd(this ILogger logger, string tag, string method, LogResult result, string summary = null);
void LogEnd(this ILogger logger, string tag, string method, LogResult result, long elapsedMs, string summary = null);
void LogTx(this ILogger logger, string tag, string type, string messageId, int size, string target = null, string extra = null);
void LogRx(this ILogger logger, string tag, string type, string messageId, int size, string source = null, string extra = null);
void LogTxPayload(this ILogger logger, string tag, string payload);
void LogRxPayload(this ILogger logger, string tag, string payload);
void LogStateTransition(this ILogger logger, string tag, string endpoint, string from, string to, StateResult result, string reason = null);
void LogDequeue(this ILogger logger, string tag, string type, string messageId, int size, string source = null);
```

Existing service-specific extension classes may remain as compatibility wrappers during migration.

The `extra` parameter on `LogTx` / `LogRx` is the canonical place for machine-readable suffixes such as `route={category}` (5.7), `status={code}`, or `reason={token}`. Do not introduce new helpers when an `extra` string covers the use case.

A dedicated `LogPublishSummary` helper is intentionally not provided. Cycle summaries differ per service (count layout, reason format, channel grouping per 5.8/5.9), so each call site composes its own `Info` lines.

---

## 10. Migration Strategy

1. Introduce `Mirero.PCC.XLab.Shared.LogExtension`.
2. Add references from service application projects.
3. Convert service-specific extension classes into wrappers, or replace call sites service by service.
4. Keep service-specific rules only for special behavior such as PublisherHub idle tick and ApiGateway state transitions.
5. Remove duplicated masking/truncation code after all call sites use the shared extension.
