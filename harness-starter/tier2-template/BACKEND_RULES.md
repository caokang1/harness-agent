# BACKEND_RULES.md — 后端编码规则

> 本文件是**人话版规则**，对应 `dev.sh check --arch` 里的 grep 检测。
> **改一条规则要在两个地方留痕**：本文件加段、`dev.sh` 加/改 `_check`，且互相留锚点（`# --- xxx（BACKEND_RULES.md §xxx）---`）。

---

## 强制触发规则（每次改后端代码前先过一遍）

打开你即将修改的文件，回答下列 5 个问题：

1. 这个改动会**新增模块依赖**吗？（如新增 `implementation project(':...')`）→ 看 §模块依赖方向
2. 这个改动会引入 `@Autowired` 字段注入吗？→ 看 §依赖注入与 Lombok
3. 这个改动会在业务路径抛 `RuntimeException` 吗？→ 看 §异常与响应契约
4. 这个改动会用到 `new Date()` 或 `SimpleDateFormat` 吗？→ 看 §时间类型约定
5. 这个改动会让 DTO 跨包定义吗？→ 看 §DTO 位置约定

5 个问题逐条 OK 之后再开始改代码。**不确定 = 视为命中，继续读对应段**。

---

## §模块依赖方向

### 当前合法的横向依赖

```
基础层（自下而上无环依赖）
  └─ {{BASE_MODULE_1}}        # 例：common（纯 POJO，无 Spring Web）
  └─ {{BASE_MODULE_2}}        # 例：auth   （认证基础设施）
  └─ {{BASE_MODULE_3}}        # 例：core   （核心引擎）
  └─ ...

业务层（横向无依赖）
  └─ {{BUSINESS_MODULE_1}}    # 例：market
  └─ {{BUSINESS_MODULE_2}}    # 例：skills
  └─ ...

入口层
  └─ {{ENTRY_MODULE}}         # 例：start  （应用入口 + 数据库驱动）
```

### 硬规则

| # | 规则 | dev.sh 检测 |
|---|------|-----------|
| R1 | **业务模块禁止互相依赖**：`{{BUSINESS_MODULE_1}}` ↔ `{{BUSINESS_MODULE_2}}` 不允许直接 `implementation project(':...')` | `dep-business-cross` |
| R2 | **基础模块禁止依赖业务模块**：`common/auth/...` 不能 `implementation project(':market'/'skills'/...)` | `dep-base-to-business` |
| R3 | 业务模块 → 基础模块 OK | （无检测，正向依赖）|
| R4 | 跨业务诉求走 DIP：在 `common` 加 Reader 接口，业务模块各自 implements | （无机器检测，靠 review）|

### 命中后修复方向

- R1 命中 → 提取共享数据/逻辑到 `common`，加 Reader 接口反转
- R2 命中 → 把"基础层引用业务层"的代码抽到业务层自己的模块，或反向定义接口让业务实现

---

## §依赖注入与 Lombok

### 硬规则

| # | 规则 | dev.sh 检测 |
|---|------|-----------|
| R1 | **禁止 `@Autowired` 字段注入**，所有 Spring bean 必须用构造器注入 | `autowired-field-injection` |
| R2 | 推荐 `@RequiredArgsConstructor` + `private final` 字段（Lombok 生成构造器）| （无检测，靠 review）|
| R3 | 多构造器场景才显式写 `@Autowired` 在构造器上 | （例外，无检测）|

### 修复模板

```java
// ❌ 反模式
@Service
public class FooService {
    @Autowired
    private BarRepository barRepo;  // 字段注入
}

// ✅ 正确做法
@Service
@RequiredArgsConstructor
public class FooService {
    private final BarRepository barRepo;  // 构造器注入（由 Lombok 生成构造器）
}
```

### 为什么这条这么严格？

字段注入隐藏依赖关系（看构造器看不出依赖了什么）+ 不利于单测（无法 new 出对象传 mock）+ 与 final 不兼容。这条规则在所有 Spring 项目里都是 best practice，没有例外场景。

---

## §异常与响应契约

### 硬规则

| # | 规则 | dev.sh 检测 |
|---|------|-----------|
| R1 | **业务路径禁止抛 `throw new RuntimeException(...)`**——必须用 `BusinessException(BizErrorCode.X, ...)` 或更具体的领域异常 | `runtime-exception-in-business` |
| R2 | `BusinessException` 必须带 `BizErrorCode` 枚举值（前端按 code 国际化）| （review 检测）|
| R3 | 真正的"程序员错误"（不可恢复）才用 `IllegalStateException` / `IllegalArgumentException` | （review 检测）|

### 修复模板

```java
// ❌ 反模式
if (user == null) {
    throw new RuntimeException("用户不存在");  // 前端拿不到 code
}

// ✅ 正确做法
if (user == null) {
    throw new BusinessException(BizErrorCode.USER_NOT_FOUND);
}
```

### 为什么这条这么严格？

`RuntimeException` 没有结构化错误信息（只有字符串），前端无法做精准国际化、无法做按 code 重试、监控无法分类。把所有业务错误收敛到 `BusinessException` + `BizErrorCode` 一组枚举，是后端可观测性的基础。

---

## §时间类型约定

### 硬规则

| # | 规则 | dev.sh 检测 |
|---|------|-----------|
| R1 | **禁止 `new Date()`** —— 用 `LocalDateTime.now()` 或 `Instant.now()` | `legacy-date-api` |
| R2 | **禁止 `SimpleDateFormat`** —— 用 `DateTimeFormatter`（线程安全）| `legacy-date-api` |
| R3 | 数据库时间字段映射用 `LocalDateTime`，不要用 `java.util.Date` | （review 检测）|
| R4 | 涉及时区时显式用 `ZonedDateTime` / `OffsetDateTime`，不要假设 JVM 默认时区 | （review 检测）|

### 为什么这条这么严格？

`SimpleDateFormat` 不是线程安全的（在 Service 类里作字段 = 隐藏 bug）；`java.util.Date` API 设计差（month 从 0 开始等）；JDK 8 的 `java.time` 包是公认的现代答案。

---

## §DTO 位置约定

### 硬规则

| # | 规则 | 检测 |
|---|------|-----|
| R1 | DTO（请求/响应/事件）放在 `{{BACKEND_PACKAGE}}.{module}.dto` 包下，**不要**放在 `controller` 包内 | review |
| R2 | 跨模块共享的 DTO 放在 `{{BASE_MODULE_1}}.dto` 包下 | review |
| R3 | 内部传递用 record（Java 17+），对外接口用 class + Lombok | review |

### 为什么？

DTO 放在 `controller` 包内会导致："看似只改 controller，实际 DTO 是 service 也用的，触发跨包改动"——这是 `module-coupling` 类 learning 的高发场景。

---

## §请求/响应通用契约

| 项 | 约定 |
|---|------|
| 统一响应封装 | `ResponseEntity<ApiResponse<T>>`（自定义 `ApiResponse` 含 `code` / `data` / `message`）|
| 分页参数 | `pageNo` / `pageSize`（不要 `page` / `size`，统一团队约定）|
| 时间字段序列化 | `yyyy-MM-dd HH:mm:ss`（Jackson 全局配置）|
| ID 字段 | 必须 `Long`（前端用 string 接收，避免 JS 精度丢失）|
| 枚举字段 | 序列化为 string，反序列化大小写不敏感 |

> **与 AGENTS 分工**：模块分层、合法依赖、箭头图**只在本文件维护**（AGENTS 已瘦身，不再重复模块树）。

---

## §Learning 晋升示范

> 当 `.learnings/` 里出现"同一 tag ≥ 3 次"或"代价极高的单次事故"时，把对应规则晋升进本文件。
> 示范条目（删除前请确认你项目里有同类事故）：

> _（暂无晋升条目。从你项目的第一次 promotion 开始填。）_

---

## §作废规则（archived）

> 规则只增不减。如某条规则因技术演进失效，**追加一行**说明原因和替代方案，**不要删除原文**。

> _（暂无作废规则。）_
