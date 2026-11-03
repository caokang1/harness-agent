# BACKEND_RULES.md — 后端编码规则

> 本文件是**人话版规则**，对应 `dev.sh check --arch` 里的 grep 检测。
> **改一条规则要在两个地方留痕**：本文件加段、`dev.sh` 加/改 `_check`，且互相留锚点（`# --- xxx（BACKEND_RULES.md §xxx）---`）。

---

## 强制触发规则（每次改后端代码前先过一遍）

打开你即将修改的文件，回答下列 5 个问题：

1. 这个改动会**新增模块依赖**吗？（如在 `pom.xml` 新增 `<dependency>`）→ 看 §模块依赖方向
2. 这个改动会引入 `@Autowired` 字段注入吗？→ 看 §依赖注入与 Lombok
3. 这个改动会在业务路径抛 `RuntimeException` 吗？→ 看 §异常与响应契约
4. 这个改动会用到 `new Date()` 或 `SimpleDateFormat` 吗？→ 看 §时间类型约定
5. 这个改动会让 DTO 跨包定义吗？→ 看 §DTO 位置约定

5 个问题逐条 OK 之后再开始改代码。**不确定 = 视为命中，继续读对应段**。

---

## §模块依赖方向

### 当前合法的横向依赖

Maven 多模块（各模块独立 `pom.xml`，父 POM 为 `{{AP_ART_FRAMEWORK}}`），依赖通过 `<dependency><artifactId>` 声明。

```
基础层（不得依赖任何业务服务）
  └─ {{AP_MOD_FRAMEWORK}}            # 父 POM（{{AP_ART_FRAMEWORK}}）
  └─ {{AP_MOD_COMMONS}}    # 公共工具（id-{{AP_MOD_COMMONS}}）
  └─ {{AP_MOD_API}}          # 各服务 Feign 接口与 DTO（id-*-api 子模块）
  └─ {{AP_MOD_MQ}}   # 事务消息组件（spring-transactional-mq）
  └─ {{AP_MOD_SCHEDULE}}   # 调度组件（spring-schedule）

业务层（13 个独立部署的服务，横向只走 Feign）
  └─ gateway / {{AP_SVC_OPEN}} / {{AP_SVC_AUTH}} / {{AP_SVC_USER}} / {{AP_SVC_LOAN}}
  └─ {{AP_SVC_PAYMENT}} / {{AP_SVC_REPAY}} / collection / {{AP_SVC_STAT}}
  └─ {{AP_SVC_TABLE}} / {{AP_SVC_ADMIN}} / {{AP_SVC_MIGRATE}} / {{AP_SVC_TOOL}}
  依赖：{{AP_MOD_API}} 的 id-*-api + base-component-*（正向，合法）
```

### 硬规则

| # | 规则 | dev.sh 检测 |
|---|------|-----------|
| R1 | **业务服务禁止直接依赖其他业务服务的 artifact**（如 `id-{{AP_SVC_LOAN}}`、`id-{{AP_SVC_REPAY}}`、`{{AP_SVC_STAT}}`），跨服务调用一律走 `{{AP_MOD_API}}` 的 Feign 接口 | `dep-business-cross` |
| R2 | **基础模块禁止依赖业务服务 artifact** | `dep-base-to-business` |
| R3 | 业务服务 → `id-*-api` / `base-component-*` OK | （无检测，正向依赖）|
| R4 | 跨服务数据访问只通过 Feign，不跨库直查其他服务的表（canal 统计类服务的既有跨库 SQL 除外） | （无机器检测，靠 review）|

### 命中后修复方向

- R1 命中 → 在被调方服务暴露 Feign 接口，接口与 DTO 放到 `{{AP_MOD_API}}` 对应的 `id-*-api` 子模块
- R2 命中 → 把"基础层引用业务层"的代码移回业务服务，或在基础层定义接口由业务服务实现

---

## §依赖注入与 Lombok

### 硬规则

| # | 规则 | dev.sh 检测 |
|---|------|-----------|
| R1 | **新增的 Java 文件禁止 `@Autowired` 字段注入**，Spring bean 用构造器注入 | `autowired-field-injection` |
| R2 | 推荐 `@RequiredArgsConstructor` + `private final` 字段（Lombok 生成构造器）| （无检测，靠 review）|
| R3 | 多构造器场景才显式写 `@Autowired` 在构造器上 | （例外，无检测）|
| R4 | 存量类里追加依赖时沿用该类已有的注入方式，不顺手改造（跨国分支合并冲突面） | （无检测，靠 review）|

> **检测范围**：仅当前分支相对 `{{AP_MAIN_BRANCH}}` 新增的 `.java` 文件。存量代码约 9500 处 `@Autowired` 字段注入不追溯（项目「存量代码改造纪律」禁止顺手重构）。

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
| R1 | **新增的 Java 文件禁止 `throw new RuntimeException(...)`**——用 `ServiceException` + `ErrorMessageKey`（或 `ExceptionBuilder.build(ErrorMessageKey.X, ...)`） | `runtime-exception-in-business` |
| R2 | 错误信息取自 `ErrorMessageKey` 枚举（多语言），不写死中英文字符串 | （review 检测）|
| R3 | 真正的"程序员错误"（不可恢复）才用 `IllegalStateException` / `IllegalArgumentException` | （review 检测）|

> **检测范围**：仅当前分支相对 `{{AP_MAIN_BRANCH}}` 新增的 `.java` 文件；存量代码约 120 处不追溯。

### 修复模板

```java
// ❌ 反模式
if (loanOrder == null) {
    throw new RuntimeException("loan order not found");  // 无错误码、无多语言
}

// ✅ 正确做法
if (loanOrder == null) {
    throw ExceptionBuilder.build(ErrorMessageKey.Canal.CANAL_QUERY_ORDER_ID_ERROR, loanOrderId);
}
```

### 为什么这条这么严格？

`RuntimeException` 没有结构化错误信息（只有字符串），无法按错误码做多语言展示、重试和监控分类。项目已有 `ServiceException` + `ErrorMessageKey` 体系，新代码统一收敛到这套体系。

---

## §时间类型约定

### 硬规则

| # | 规则 | dev.sh 检测 |
|---|------|-----------|
| R1 | **新增的 Java 文件禁止 `new Date()`** —— 用 `LocalDateTime.now()` 或 `Instant.now()`（Java 8 可用） | `legacy-date-api` |
| R2 | **新增的 Java 文件禁止 `new SimpleDateFormat`** —— 用 `DateTimeFormatter`（线程安全），或项目已有的 `DateUtil` | `legacy-date-api` |
| R3 | 新建实体的时间字段可用 `LocalDateTime`；向存量实体追加字段时沿用其现有 `java.util.Date` 类型 | （review 检测）|
| R4 | 涉及时区时显式用 `ZonedDateTime` / `OffsetDateTime`，不要假设 JVM 默认时区；SQL 只做纯比较，时间界在 Java 侧按应用时钟算好传参 | （review 检测）|

> **检测范围**：仅当前分支相对 `{{AP_MAIN_BRANCH}}` 新增的 `.java` 文件；存量代码约 2800 处不追溯。

### 为什么这条这么严格？

`SimpleDateFormat` 不是线程安全的（在 Service 类里作字段 = 隐藏 bug）；`java.util.Date` API 设计差（month 从 0 开始等）；JDK 8 的 `java.time` 包是公认的现代答案。

---

## §DTO 位置约定

### 硬规则

| # | 规则 | 检测 |
|---|------|-----|
| R1 | 跨服务（Feign）的请求/响应 DTO 放在 `{{AP_MOD_API}}` 对应子模块的 `request` / `response` 包下（如 `{{AP_API_STAT}}` 的 `{{AP_PKG}}.base.cash.api.request.{{AP_EXAMPLE_DTO}}`），**不要**放在 `controller` 包内 | review |
| R2 | 服务内部 DTO 放在本服务的 `dto` 包下（如 `{{AP_SVC_STAT}}` 的 `service.biz.dto`） | review |
| R3 | 项目为 Java 8，不能用 record；DTO 一律 class + Lombok | review |

### 为什么？

DTO 放在 `controller` 包内会导致："看似只改 controller，实际 DTO 是 service 也用的，触发跨包改动"——这是 `module-coupling` 类 learning 的高发场景。

---

## §请求/响应通用契约

| 项 | 约定 |
|---|------|
| 统一响应封装 | `BaseResponse<T>`（成功 `BaseResponse.ok(data)`，调用方用 `success()` / `fail()` 判断）|
| 分页参数 | 沿用所在服务现有约定（待团队补充统一规范）|
| 时间字段序列化 | 沿用所在服务现有约定（待团队补充统一规范）|
| ID 字段 | 订单等主键为 `Long` |
| 枚举字段 | 沿用所在服务现有约定（待团队补充统一规范）|

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
