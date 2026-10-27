---
name: table-lineage
description: 从 Java / Spring / MyBatis 微服务代码加 MySQL 元数据，生成可交互的库表血缘页面。页面回答每张表由谁写、从哪些表取数、谁在读、属于哪个业务域，并附口径卡片、问题清单和 ER 图。准确率不靠假设：每个项目都用人工核对的标准答案实测，代码或数据库变化后重跑会标出过期的结论。凡是想弄清"这张报表怎么来的""底表是什么""表之间什么关系""哪些报表没人用"，或要做数据血缘、数据字典、报表盘点、ER 图，或要在代码或库变化后更新已有血缘页面，都使用本 skill，即使用户没说"血缘"二字。Use for table/data lineage, report provenance, data dictionary or ER diagrams of Java microservice + MySQL systems.
---

# 库表血缘页面

把一个 Java 微服务项目的"表从哪来、到哪去"做成一个可交互页面。页面有七个视图：总览、表目录、接口与任务、问题清单、ER 图、术语、方法与准确率。

**这个 skill 的核心是准确率可证明，而不是扫描本身。**静态扫描在任何新项目上都会有盲区，所以每个项目都要：
1. 用独立的人工核对建立标准答案；
2. 每次运行自动打分；
3. 代码变了，就把相关的人工结论标为待复核。

做不到第 1 步时，页面会明确显示"准确率未经测量"。汇报时也必须照实说，不要声称准确。

## 适用范围

**能处理：**
- Java 代码，Spring MVC，OpenFeign。
- MyBatis 注解 SQL、Mapper XML，MyBatis-Plus（BaseMapper、ServiceImpl、@TableName）。
- 入口：Kafka 监听、xxl-job 或 @Scheduled、自研调度基类（可配置）。
- binlog 订阅：可选，写法可配置。
- MySQL 的 information_schema。

**不处理：**
- JPA/Hibernate 的实体关系；
- MongoDB、Redis、ES 的读写；
- RestTemplate 或拼 URL 的 HTTP 调用；
- 非 Java 代码。

开始前先粗看项目（有没有 Mapper XML、`@TableName`，还是 `@Entity`）。如果主要是 JPA，先告诉用户扫描器看不到这类写入，再问要不要继续，或按 [references/extending.md](references/extending.md) 扩展扫描器。

运行环境：Python 3.11 及以上，只用标准库。直连导出元数据时还需要 `mysql` 命令行客户端。

## 工作目录

每个项目一个工作目录，放在**代码仓库外面**，不要往用户的仓库里写任何文件：

```
<workspace>/
  config/project.json   项目相关的全部假设（第 2 步生成并确认）
  config/db.cnf         直连账号（可选，只放本机，不提交、不外发）
  knowledge/            人工知识：cards.json、domains.json、glossary.json、accuracy_notes.json、truth/*.json
  inputs/<日期>/        元数据 CSV
  runs/<时间戳>/        每次运行的输出；runs/LATEST 指向正式基线
  survey.md             第 2 步的勘察报告
```

先复制 `assets/knowledge-skeleton/` 到 `<workspace>/knowledge/`。下文的 `S` 指本 skill 的 `scripts/` 目录。

## 流程

### 1. 元数据

两种方式产出完全相同的格式，任选一种：

- **CSV**：用户在任意客户端执行 `S/sql/export_metadata.sql` 里的 4 条查询，各存成一个 CSV（UTF-8，带表头），放进 `<workspace>/inputs/<日期>/`。`xxl_jobs.csv` 可选。
- **直连**：复制 `assets/db.cnf.example` 为 `<workspace>/config/db.cnf`，让用户自己填写。

账号密码只能写在 .cnf 里，**不要让用户把密码发到对话里，也不要写进命令行**。建议用只读账号，工具只查 `information_schema` 和 `xxl_job.xxl_job_info`。如果调度库不叫 xxl_job，改 SQL 里的库名。

### 2. 勘察并确认配置

```bash
python S/tools/survey.py --repo <仓库> --meta-csv <元数据目录> --workspace <workspace> --project <项目名>
```

这一步生成 `config/project.json` 草稿和 `survey.md`。草稿里每一项都是猜测，**确认后才能进入第 3 步**。

- 读一下 `survey.md`，每个标着"请确认"的地方都打开对应代码核实。
- 只有用户知道答案的，用一次提问问清楚：
  - 哪些库是报表库？
  - 哪些模块是给后台页面或外部调用方用的？
  - 测试库和线上有什么差别？
- 每个配置项的含义和核实方法见 [references/config.md](references/config.md)。

### 3. 第一次运行

```bash
python S/run.py --workspace <workspace> --meta-csv <workspace>/inputs/<日期> --label 测试库
```

如果代码不是 git 仓库，加 `--code-label "分支 commit"`。运行后读 `runs/<run>/report.md`，按顺序处理：

1. **自检警告**：配置和库或代码对不上。修好配置再跑。
2. **"代码里出现、但元数据里找不到的表"**：数量多，通常说明元数据导错了库，或者 mapper_package_db 不全。
3. **"ER 核心表候选"**：从中挑 10 到 20 张，写进 `er.core_tables`。
4. **页面抽查**：打开 `lineage.html`，看 3 张熟悉的报表，确认写入方和上游说得通。

### 4. 标准答案（决定准确率的一步）

按 [references/ground-truth.md](references/ground-truth.md) 建立至少两组标准答案：

1. **第一组是"调教集"**：用它找扫描器和配置的问题，并修复。
2. **修复完成后，另抽一组没看过的表作为"独立核对集"**。页面和汇报中引用的准确率以这一组为准。

几条原则，理由都在参考文档里：
- 核对者不能看扫描结果；
- 每条结论必须附代码出处；
- 扫描多报或漏报的条目要回代码查证后再定是谁错。标准答案自己也会错，改动要写明证据；
- **不允许为了让分数好看而改标准答案。**

改了 `S/lineage/` 或 `S/web/` 下的代码后，必须先跑两次自测，都通过才能继续：

```bash
python S/tools/selftest.py
python S/tools/selftest.py --workspace <workspace> --meta-csv <元数据目录>
```

第一次在自带的示例项目上跑，第二次在当前项目上跑，检查准确率是否低于基线。

### 5. 口径卡片、业务域、术语

- **口径卡片**：按 [references/cards.md](references/cards.md) 为报表写卡片（作用、粒度、指标口径、使用建议、风险）。风险只有回代码确认过的才能标为已确认。
- **业务域**：写进 `knowledge/domains.json`。
- **术语**：写进 `knowledge/glossary.json`。

核对完成后给结论盖章，记录当时的代码指纹：

```bash
python S/tools/rebaseline.py <workspace>/runs/<run> --workspace <workspace>
```

### 6. 正式基线与交付

去掉 `--no-latest` 再正式跑一次，这次的结果会登记为 `runs/LATEST`。向用户交付以下内容：

- 页面路径；
- 准确率表：分组列出，并注明每组是调教集还是独立核对集；
- 自检警告；
- 已知盲区。

页面里有内部表结构和代码路径。发布成可分享的链接前，先征得用户同意。

## 代码或数据库变了以后

用同一个工作目录重新运行即可。运行会自动和 `runs/LATEST` 对比。`runs/LATEST` 是最近一次不带 `--no-latest` 的正式运行；带 `--no-latest` 的试验运行不会成为对比对象。report.md 和页面顶部会列出以下变化：

| 提示 | 处理 |
|---|---|
| 自检警告：配置里的库、表或模块不存在 | 先确认是不是连错了库；如果是配置过时，就更新配置 |
| 卡片待复核 / 标准答案因代码变更未计 | 写入这张表的代码变了。重新核对后，执行 `rebaseline.py --tables 表名 --force` |
| 业务域为推测 | 新出现的报表还没人工归类，确认后写进 domains.json |
| 准确率下降 ≥0.5 个百分点 | 看 `evaluation.json` 里的 misses，判断是扫描器的问题还是代码真的变了 |
| 新增、消失的表，字段变化 | 如实转告用户 |

要扫描另一个分支，又不想动用户的工作区：先用 `git archive <分支> | tar -x -C <临时目录>` 导出代码，再用 `--repo <临时目录> --code-label "<分支> <commit>" --no-latest` 运行。

## 汇报口径

- **准确率**：只引用本项目标准答案测出来的数字。要说明哪组是独立核对集、样本有多大、有多少条因代码变更没有计分。
- **"直接上游"和"经 Feign 接口读"要分开说**：
  - 直接上游有召回率和精确率；
  - 经 Feign 读的部分偏宽，只报召回率。
- **状态**（在用、写而不读、调度未启用、无生效写入方）：说明它们取决于元数据来自哪个环境。
