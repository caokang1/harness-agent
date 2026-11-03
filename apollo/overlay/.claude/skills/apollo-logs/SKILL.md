---
name: apollo-logs
description: Query and analyze {{AP_PROJECT}} production error/business logs from Alibaba Cloud SLS via the aliyun-observability MCP server. Use when the user wants to inspect online logs, diagnose production errors, find noisy log sources, drill into a specific exception/traceId, or analyze error trends for any country (th/id/mm/in/mx/{{AP_CC2}}/...).
---

# {{AP_PROJECT}} 线上日志分析 (SLS)

通过 `aliyun-observability` MCP 读取 {{AP_PROJECT}} 各国生产日志（阿里云 SLS）。**只读**，AK 走环境变量，不在本文件出现。

## 团队接入（每位成员一次性配置）
MCP 已注册在项目根 `.mcp.json`（共享，无密钥）。命令与 AK 均通过环境变量引用，每人各自配置：
1. 下载官方二进制 `aliyun/alibabacloud-observability-mcp-server`（按 OS 选 darwin/linux），`chmod +x`，macOS 需 `xattr -d com.apple.quarantine <bin>`。
2. 申请**只读** RAM 子账号 AK（策略 `AliyunLogReadOnlyAccess`），在 `~/.zshrc` / `~/.bashrc` 里配 3 个环境变量：
   ```bash
   export ALIYUN_OBSERVABILITY_MCP_BIN=/你的路径/alibabacloud-observability-mcp-server
   export ALIBABA_CLOUD_ACCESS_KEY_ID=只读AK_ID
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET=只读AK_SECRET
   ```
3. `source` 后重启 Claude Code；首次会提示信任项目 `.mcp.json`，同意即可。

## 前置检查
1. MCP 已连接：`claude mcp list` 应显示 `aliyun-observability` = connected。
   - 若 fail：多为上面 3 个环境变量没配/没生效（在已 source 的终端里重启 Claude Code），或权限不足，见文末「排障」。
2. 需要的工具（按需用 ToolSearch 加载 schema）：
   `mcp__aliyun-observability__sls_execute_sql`（主力，跑 SLS SQL 聚合）、
   `sls_list_logstores`、`sls_list_projects`、`sls_get_context_logs`（看某条日志上下文）、
   `sls_log_explore`（自动聚类概览）。

## 国家 → SLS 坐标登记表
查询三要素：`regionId` + `project` + `logStore`。**业务应用日志**统一是 `{{AP_NS}}-<cc>-all-{{AP_LOG_SUFFIX}}`（含 logback JSON 字段）。
其它 logstore：`-ngxlog`(nginx) / `-tracking-{{AP_LOG_SUFFIX}}`(内部接口访问日志，见下节) / `-xxl-job`(定时任务) / `-messages`(k8s) / `-nacos`。

坐标表不入库（属于生产基础设施信息），放在本 skill 目录下的 `references/sls-coordinates.md`：

- 安装时如果本地已有就保留；没有就从 `references/sls-coordinates.example.md` 复制一份。
- 表里查不到的国家按下一条的方法查出来，补进本地这张表。

> 补新国家：知道 region 就用 `sls_list_projects(regionId=...)` 找 project，再 `sls_list_logstores(project, regionId)` 找 `*-all-{{AP_LOG_SUFFIX}}`，把结果填进本表。
> 常见国际区域：新加坡 `ap-southeast-1`、香港 `cn-hongkong`、雅加达 `ap-southeast-5`。

## 日志字段 ({{AP_NS}}-*-all-{{AP_LOG_SUFFIX}})
`appName`（服务名）、`class`（类）、`method`（方法）、`level`（INFO/WARN/ERROR）、
`message`、`stack_trace`、`traceId`、`spanId`、`thread`、`time`。

## 接口访问日志 ({{AP_NS}}-*-tracking-{{AP_LOG_SUFFIX}})
同 project 下的 `{{AP_NS}}-<cc>-tracking-{{AP_LOG_SUFFIX}}` 记录各服务 **HTTP 请求进站流水**（覆盖 gateway、
{{AP_SVC_OPEN}} 等对外入口，也包括服务间 Feign 调用），字段：
`AppName`（被调服务）、`RequestUrl`、`Postdata`（**完整入参**）、`ResponseBody`（响应体，含错误码）、
`TraceId`、`IP`（**调用来源 IP**：内部调用为对方 pod IP，外部请求为客户端/接入层 IP）、
`CostTime`(ms)、`UserAgent`（`Java/1.8.x` = 内部 Feign 调用，其它为外部客户端）、`Date`。
**核心用途——反查"孤儿 ERROR"**：{{AP_LOG_SUFFIX}} 里接口报错常只有一行（`api.around` 只打方法签名，
不带入参；调用方可能全程无日志），拿 traceId 来本库查即可拿到 {{AP_LOG_SUFFIX}} 缺的入参和调用来源：
```
<traceId值>        ← 直接全文检索即可，无需字段名
```
来源 IP 对应哪个服务：用出错时刻前后 {{AP_LOG_SUFFIX}} 里任意日志的 `__tag__:_container_ip_` 比对。
注意：同一 TraceId 出现多条不同耗时/不同目标实例的记录 = 负载均衡层重试，若最后一条是 200，
说明调用已自愈（常见于新单创建后 1 秒内被 canal 消费者反查的读写竞态）。

## 查询要点（避坑）
- **指纹按 `appName + class + method` 归一，不要按 `message` 聚合** —— message 里常含 UUID/orderNo 等高基数值，会把同一个 bug 散成成百上千条"不同"消息。
- 告警侧现有过滤逻辑：`level:ERROR AND NOT stack_trace:"...NormalCodeException"`（排除业务码）；实测在 TH 近乎不减量，本质仍是数原始行数。
- `sls_execute_sql` 的 `limit` 只限**返回行数**（≤100），不限聚合范围；聚合在服务端完成，放心 GROUP BY。
- 时间：`from_time`/`to_time` 支持 `now`、`now-1h`、`now-24h` 或 Unix 秒。
- SQL 语法：`|` 前是过滤（SLS 检索语法），`|` 后是标准 SQL。字段需已建索引/开启分析。
- **字段检索要用完整值**：`class:{{AP_EXAMPLE_LISTENER}}` 可能查空，
  `class:"{{AP_GROUP}}.cash.service.kafka.{{AP_EXAMPLE_LISTENER}}"` 才命中（分词不按点切）。

## 标准诊断配方（SLS SQL，填入对应国家三要素）

**1) 级别分布（先看 ERROR 占比与量级）**
```sql
* | SELECT level, count(*) AS cnt GROUP BY level ORDER BY cnt DESC
```

**2) ERROR 按服务**
```sql
level: ERROR NOT NormalCodeException | SELECT appName, count(*) AS cnt GROUP BY appName ORDER BY cnt DESC
```

**3) 噪音源 Top50（核心：按指纹归一）**
```sql
level: ERROR NOT NormalCodeException |
SELECT appName, class, method, count(*) AS cnt
GROUP BY appName, class, method ORDER BY cnt DESC LIMIT 50
```

**4) 钻进某个指纹，看真实 message 分布（判定噪音 vs 真故障）**
```sql
level: ERROR AND appName: <服务> AND method: <方法> |
SELECT message, count(*) AS cnt GROUP BY message ORDER BY cnt DESC LIMIT 20
```

**5) 拆黑洞：某指纹里按 stack_trace 看藏了几种异常**
```sql
level: ERROR AND appName: <服务> AND class: <类> |
SELECT stack_trace, count(*) AS cnt GROUP BY stack_trace ORDER BY cnt DESC LIMIT 20
```

**6) ERROR 随时间分布（定位突刺时段）**
```sql
level: ERROR NOT NormalCodeException |
SELECT date_trunc('hour', __time__) AS hr, count(*) AS cnt GROUP BY hr ORDER BY hr
```

**7) 顺藤摸瓜：按 traceId 查一次请求全链路**
用 `sls_execute_sql`，query=`traceId: <值>`，不加聚合、`reverse=false`、`limit=100`。
或用 `sls_get_context_logs` 看某条前后文。

## 分析产出规范
- 先给量级与 Top 指纹的**占比**（如"前 3 指纹 = 88% ERROR"），再逐个判定噪音/真故障。
- 判定"真故障"要看到实际 message/stack_trace，不能只凭数量。
- 区分：噪音源（降级/白名单）、误用 ERROR 的业务失败（降 WARN）、真该修的稀有异常（长尾）。

## 排障
- `-32000 / Failed to reconnect`：多是注册的 `args` 被截断。用 `claude mcp add-json` 重注册，args 用 `["start","--stdio"]`。
- `401 Unauthorized ... log:ListProject`：只读子账号缺 SLS 读权限，挂 `AliyunLogReadOnlyAccess` 或最小只读策略（`log:ListProject/ListLogStores/GetLogStore/GetIndex/GetLogStoreLogs/GetLogStoreHistogram`）。
- 认证通过但查不到：确认 region 与 project 所在区域一致（国际服共用 `.aliyuncs.com`，只 region 不同）。
