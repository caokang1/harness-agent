# 改造点清单（CUSTOMIZE）

> 跑完 `init.sh` 后，这是**第二把工**——逐条 checklist 走 5~10 个项目特异字段。预计 15~20 分钟。

---

## 改造点优先级图例

- 🔴 **必改**：不改装上去会直接报错或语义错误
- 🟡 **选改**：当前能跑，但建议按项目情况调整
- 🟢 **可不改**：默认值通常 OK，特殊场景才动

---

## 一、AGENTS.md 改造点

| 优先级 | 字段 | 默认占位 | 改成什么 |
|------|------|---------|---------|
| 🔴 | 项目简介段 | `> {{PROJECT_DESC}}` 等首段 | 写清"是什么、给谁用、当前状态" |
| 🔴 | 模块拓扑与依赖 | 见 `BACKEND_RULES.md` 占位 | 改成你项目的实际分层与合法依赖（AGENTS 已瘦身，拓扑只维护在后端规则里）|
| 🔴 | 技术栈段 | `{{TECH_STACK}}` 首段 | 按实际版本改 |
| 🟡 | 规则变更日志 | 仅 1 条示例 | 留空，让团队自己往里加 |
| 🟢 | 项目缩写 | `mg`（MCP Gateway 缩写） | 通常用项目首字母 |

> 旧版模板曾带一段"起步包同步纪律"——用于 starter 与主项目同仓库时强制 `diff -r` 校验。**starter 独立仓库化后这段已移除**，因为你装完 starter 后那些文件就是你的，不再与上游有强耦合。如果你从旧版 starter 升级上来，可以直接删掉对应 AGENTS.md 段落。

## 二、BACKEND_RULES.md 改造点

| 优先级 | 字段 | 默认 | 改成什么 |
|------|------|------|---------|
| 🔴 | 模块依赖方向段的"业务模块"列表 | `market, skills` | 改成你项目的业务模块名 |
| 🔴 | 模块依赖方向段的"基础模块"列表 | `common, auth, admin` | 改成你项目的基础设施模块名 |
| 🔴 | DTO 命名约定（包路径） | `com.example.{module}.dto` | 改成你的实际包名 |
| 🟡 | 异常基类 | `BusinessException(BizErrorCode)` | 如果你已有自定义异常体系，改名 |
| 🟢 | 时间类型约定 | `LocalDateTime / DateTimeFormatter` | 通常不动 |

## 三、FRONTEND_RULES.md 改造点

| 优先级 | 字段 | 默认 | 改成什么 |
|------|------|------|---------|
| 🔴 | views 目录约定（每个 domain 一个子目录）| `src/views/{market,skills,admin,common}` | 按你前端实际域改 |
| 🔴 | 跨域 import 检测的 domain 列表 | 同上 | 同上 |
| 🟡 | 共享组件路径 | `src/components/`、`src/composables/` | 按你前端结构 |
| 🟢 | 组件命名约定 | PascalCase | 通常不动 |

## 四、`dev.sh` 改造点

⚠️ **这是改造工作量最大的文件**，预计占用 8~12 分钟。

| 优先级 | 字段 | 默认 | 改成什么 |
|------|------|------|---------|
| 🔴 | 第 18-22 行 docker 服务名 | `mcp-gateway-dev`、`mcp-gateway-ui-dev` | 改成 `<your-project>-dev` |
| 🔴 | `run_arch_check` 的 6 类规则的模块路径列表 | `mcp-gateway-{common,auth,...}/src/main/java` | 改成你项目的模块路径 |
| 🔴 | `cmd_logs` 里"启动成功"日志关键字 | `Started McpGatewayApplication` | 改成你 Spring Boot 的应用类名 |
| 🟡 | `cmd_verify_snapshot` 的关键业务表清单 | 13 张 mcp-gateway 业务表（占位） | 改成你项目的关键业务表（5~15 张为宜） |
| 🟡 | `cmd_test` 的 gradle 任务名 | `gradle test --tests <pattern>` | 如果用 Maven：改成 `mvn test -Dtest=<pattern>` |
| 🟢 | 6 类规则本身 | 后端 6 条 + 前端 1 条 | 起步建议**全部保留**，跑出基线再看哪条不适用 |

**自写指南：怎么从事故反推新 grep 规则**

1. 出了一次事故 → 写进 `.learnings/LEARNINGS-correction.md`
2. 同 tag 累积 ≥ 3 次（或单次重大）→ 触发晋升
3. 晋升流程：
   - 在 `BACKEND_RULES.md` 加一条文字规则
   - 在 `dev.sh` 的 `run_arch_check` 加一个 `_check` 块（grep 实现）
   - 两边互相留锚点：`# --- xxx（BACKEND_RULES.md §xxx）---`
4. 跑一次 `bash dev.sh check --arch` 确认基线 0
5. 在 `.learnings/` 原条目末尾追加 `→ PROMOTED to BACKEND_RULES.md + dev.sh on YYYY-MM-DD`

## 五、`docker-compose.dev.yml` 改造点

| 优先级 | 字段 | 默认 | 改成什么 |
|------|------|------|---------|
| 🔴 | services 的服务名 | `mcp-gateway-dev`、`mcp-gateway-ui-dev` | 改成 `<your-project>-dev` |
| 🔴 | 后端镜像 | `eclipse-temurin:17-jre` | 按你 JDK 版本 |
| 🔴 | 后端启动命令 | 引用 `mcp-gateway-start` 模块 | 改成你的 main 模块 + 启动类 |
| 🟡 | 端口映射 | 后端 `<后端端口>:<后端端口>`（并设 `SERVER_PORT`）、前端 `5173:5173` | 按需改 |
| 🟡 | 数据库依赖 | 默认无（连外部 DB）| 如需本地 DB，加 `services.mysql/postgres` |
| 🟢 | 网络 | `bridge` 默认 | 通常不动 |

## 六、harness-orchestrator/SKILL.md 改造点

这个 skill 是 Tier 2 唯一一个项目特异 skill，包含两处占位符：

| 优先级 | 占位符 | 含义 | 改成什么 |
|------|------|------|---------|
| 🔴 | `{{PROJECT_NAME}}` | 项目名 | 跟 AGENTS.md 一致 |
| 🟡 | `{{ENTRY_HOOK}}` 段 | 项目入口判定逻辑 | 按你项目"什么场景该走 harness 全流程"的判断改写 |

---

## 自写指南：非 Java / Vue 栈如何改造

如果你用的不是 Spring Boot + Vue，下面是改造**思路**而不是模板。

### Node + TypeScript（Express / NestJS）

`dev.sh` 的核心改造（按段）：

| 段 | mcp-gateway 原版 | Node 改造 |
|---|----------------|----------|
| 编译 | `gradle compileJava` | `tsc --noEmit` 或 `npm run build` |
| 测试 | `gradle test` | `jest` 或 `vitest` |
| reload | Spring DevTools 触发 | `nodemon` / `tsx watch` |
| 日志关键字 | `Started McpGatewayApplication` | `Server listening on port` |
| `@Autowired` 规则 | grep `@Autowired` | grep `@Inject()` 或 `useState/useContext` 误用模式 |
| `RuntimeException` 规则 | grep `throw new RuntimeException` | grep `throw new Error('` |
| 时间 API 规则 | grep `new Date\(\)|SimpleDateFormat` | grep `new Date\(\)` 而无时区参数 |

### Python（FastAPI / Django）

| 段 | mcp-gateway 原版 | Python 改造 |
|---|----------------|------------|
| 编译 | `gradle compileJava` | `python -m py_compile` 或 `mypy` |
| 测试 | `gradle test` | `pytest` |
| reload | DevTools 触发 | `uvicorn --reload` 或 `flask run --reload` |
| 日志关键字 | `Started McpGatewayApplication` | `Uvicorn running on` 或 `Application startup complete` |
| 字段注入规则 | grep `@Autowired` | grep 全局可变状态 / 单例滥用模式 |
| `RuntimeException` 规则 | grep `throw new RuntimeException` | grep 裸 `raise Exception(` |

### Go

| 段 | mcp-gateway 原版 | Go 改造 |
|---|----------------|---------|
| 编译 | `gradle compileJava` | `go build ./...` |
| 测试 | `gradle test` | `go test ./...` |
| reload | DevTools 触发 | `air` 或 `reflex` |
| 日志关键字 | `Started McpGatewayApplication` | 按你 main 里的 `log.Println` 改 |
| 字段注入规则 | grep `@Autowired` | grep 大写公开字段误用、循环依赖等 |

**通用建议**：6 类 grep 规则的"反模式"思路在哪个语言都成立——只是**反模式的表达式不同**。把"项目最近 3-6 个月最容易踩的坑"列出来，逐条 grep 化即可。

---

## §D：可选 skill（前端/UI 设计、库表血缘）

本起步包的 `tier1-direct-optional/.claude/skills/` 下有 3 个可选 skill，按开关分两组安装：

| Skill | 用途 | 建议 |
|------|------|------|
| `frontend-design` | 创建生产级前端界面（网页 / 组件 / 海报 / 仪表盘），强调独特设计语言，避免 "AI 感" | **前端占比 ≥ 30% 的项目建议启用** |
| `ui-ux-pro-max` | UI/UX 设计智能（50 种风格、21 种配色、50 种字体组合、20 种图表、9 种 stack），集成 shadcn/ui MCP 组件搜索 | **有独立 UI/UX 设计需求才启用**（会让 AI 在 UI 设计场景介入得更深）|
| `table-lineage` | 从 Java / Spring / MyBatis 代码加 MySQL 元数据生成可交互的库表血缘页面（谁写、从哪取数、谁在读、业务域、ER 图），准确率用人工标准答案实测 | **要梳理报表来源、做数据字典 / ER 图时启用**；需要 Python 3.11+，直连数据库还需 `mysql` 客户端；工作目录放在代码仓库外 |

开关：`--include-frontend-design` 装前两个，`--include-table-lineage` 装 `table-lineage`，可以同时加。

### 启用方式（两种）

**方式 1 · 安装时启用**（推荐，bootstrap / 直调都支持）：
```bash
# bootstrap 推荐路径
bash <(curl -fsSL https://.../bootstrap.sh) --include-frontend-design --include-table-lineage ...其他参数

# 或直调路径
bash .harness-starter/init.sh --include-frontend-design --include-table-lineage ...其他参数
```

**方式 2 · 事后补装**（bootstrap 场景已无 `.harness-starter/`，直接拉 optional 子目录即可）：
```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/caokang1/harness-agent.git /tmp/hs
cd /tmp/hs && git sparse-checkout set tier1-direct-optional
cp -r /tmp/hs/tier1-direct-optional/.claude/skills/* /path/to/your-project/.claude/skills/
rm -rf /tmp/hs
```

### 为什么不默认开启？

两个 skill 的 description 里包含大量触发词（"button / modal / navbar / sidebar / card / table / form / chart / landing page / dashboard" 等）。**纯后端项目启用后可能触发误介入**——用户只是说"给我加个管理 API"，AI 可能因为文案里出现 "admin panel" 就加载整个 UI/UX 设计流程。**按需启用，避免误触发**。

---

## §F：项目特异 skill（主项目有，但不在起步包内）

mcp-gateway 上游还有 2 个 skill 没进 starter：

| Skill | 为什么不进 starter |
|------|---------------------|
| `ent-mcp-operate-analysis` | mcp-gateway 特有的业务操作分析 skill（企业内 MCP 运营分析逻辑），跨项目零复用 |
| `testCaseWriting-infra-DevOps` | 项目测试基建特有的测试用例写法 skill，跟 CI 流水线 / 测试框架强绑定 |

### 你的项目也可能需要写类似的项目特异 skill

**什么场景该写一个项目特异 skill？**

满足下列**任一**：
- 项目有一类**反复出现**的分析/操作流程（比如"每次需求要先做 X / Y / Z 三个维度分析"）
- 项目有**强 DSL / 框架**的特殊场景（比如自研 DSL、专有 CI 模板、特殊的测试数据生成逻辑）
- 有一套**项目内通用但跨项目无用**的 SOP（比如你们团队特有的 release checklist）

**怎么写？** 参考 mcp-gateway 上游 `ent-mcp-operate-analysis/SKILL.md` 和 `testCaseWriting-infra-DevOps/SKILL.md` 的结构（可在 mcp-gateway 仓库 `.claude/skills/` 下找到）——通常 3 段：
1. **Frontmatter**：`name` / `description`（触发词写准）
2. **When to Use / When NOT to Use**：各 2-4 条
3. **Process / Anti-Patterns / Examples**：主体步骤 + 反面示例

**放在哪里？** `.claude/skills/<your-project-skill>/SKILL.md`，**不要**放进 `harness-starter/tier1-direct/`——starter 只收通用方法论。

### 辅助 skill：`writing-skills`

起步包里已经装了 `writing-skills` 这个 skill（在 Tier 1 必装里），它就是专门教 AI "如何写一个好 skill" 的元技能。遇到上述场景时，直接让 AI 调用 `writing-skills`，它会引导你把项目特异流程结构化成合规的 `SKILL.md`。

---

## 改造完后的自检清单

- [ ] `bash dev.sh check --arch` 能跑通（输出 ✅ 或可接受的 ❌）
- [ ] `bash dev.sh up` 能拉起容器
- [ ] `bash dev.sh logs` 能看到"启动成功"关键字
- [ ] AI 在新会话开头能正确加载 `using-superpowers` 并执行 session.md SOP（开个对话试试）
- [ ] 跑一次 `openspec` CLI 能识别 `openspec/templates/` 下的四件套
- [ ] 写一条 fake learning 到 `.learnings/LEARNINGS-correction.md` 验证 tag 索引能查到

全部勾选完，**起步包就算装完了**。
