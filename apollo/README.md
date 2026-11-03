# Apollo 项目专用 harness

这是通用 Harness Starter Kit 的项目定制版，适用的项目特征如下：

- 多国部署，每个国家一个分支；
- Java 8 Maven 多模块；
- 配置放在 Nacos；
- 用禅道管理需求，用 Jenkins 发版。

安装后的文件**只留在你本地**：安装脚本会把它们写进 `.git/info/exclude`，不进团队仓库。团队维护的 `AGENTS.md`、`CLAUDE.md`、`docs/openspec/` 一个字都不改。

## 脱敏方式

本仓库是公开的，`apollo/overlay/` 里不出现项目的真实名称：分支、模块、表、环境命名、单号都写成 `{{AP_*}}` 占位符。真实值和不能公开的整份文件放在**私有 profile 目录**里，它不进本仓库，向团队成员索取：

```
~/.config/harness-agent/apollo/        # chmod -R go-rwx
├── profile.json    # 占位符 ↔ 真实值的词表，以及私有文件清单
└── files/          # 整份私有文件（发版任务配置、经验记录、规则变更史）
```

安装时 `install.sh` 会：

1. 用 profile 把占位符还原成真实值；
2. 把 `files/` 里的私有文件一起装进项目。

装出来的效果和原项目完全一致。

## 安装

在项目仓库根目录执行：

```bash
git clone -b apollo https://github.com/caokang1/harness-agent.git /tmp/harness-agent
bash /tmp/harness-agent/apollo/install.sh --branch-owner=<你的分支前缀>   # 如 ZHANGSAN
rm -rf /tmp/harness-agent
```

可选参数：

| 参数 | 作用 |
|---|---|
| `--dry-run` | 只列出会写哪些文件，不改动项目 |
| `--update` | 升级，重新 clone 后使用。规则、skill、脚本会被覆盖；`.learnings/`、`.harness/`、本地坐标表、`.jenkins-deploy.json` 不会动 |
| `--uninstall` | 卸载，按 `.harness/apollo-manifest.txt` 删除安装过的文件 |
| `--profile=DIR` | profile 不在默认位置时，用它指定目录 |

环境要求：bash 4+、Python 3.8+、git 2.20+。

安装脚本最后会列出各项凭据文件的配置方法，包括禅道、Jenkins、测试库和 Nacos。凭据只放在 `~/.config/` 下，并 `chmod 600`。

## 装进项目的内容

Agent 启动时读取的入口是 `CLAUDE.local.md`，它会加载 `docs/agents/workflow.md`。

| 内容 | 说明 |
|---|---|
| `docs/agents/workflow.md` | 主流程，涵盖：<br>• S/M/L 规模判定<br>• 分支规则：按禅道标题的国家标签定基线、测试集成分支<br>• 主题切换<br>• 需求变更检测<br>• 回退与备份<br>• Verify 三阶段<br>• 就地完结 |
| `BACKEND_RULES.md` | 后端编码规则：模块依赖方向；存量代码只追加；SQL 只做纯比较；保持文件原有行尾 |
| `dev.sh` | 编译、测试和架构检查，详见下文 |
| `docs/agents/merge-preview.py` | 合并预演：把冲突分成「本次引起」和「基线既有」两类，并逐段给出取哪一侧的建议 |
| `docs/agents/feat.sh` | `feat new/go/ls/rm`：每个禅道需求一个 worktree 和一个会话，计时和 Maven SNAPSHOT 互不干扰 |
| `openspec/templates/` | design 模板，包含：<br>• 需求对照表：需求原文对不上的内容标「Agent 提议」<br>• 系统导读<br>• 数据示例<br>• 异常与降级 |
| `.claude/skills/` | 20 个通用方法论 skill，以及下表列出的项目 skill |

`dev.sh` 提供四个命令：`check --changed`、`check --arch`、`compile`、`test`。它会：

- 自动识别基线分支；
- 固定使用 JDK 8；
- 编译前先用当前分支的源码安装公共模块；
- 资源文件编码出错时，跳过资源再编译；
- 发现有 JUnit 5 测试却一个都没跑时，换用 surefire 2.22.2 重跑；
- `check --arch` 扫描依赖方向、字段注入、存量文件被整体改写、同一文件行尾混用。

### 项目 skill

| skill | 用途 |
|---|---|
| `zentao` | 读取禅道任务和需求，自动累计 AI 工时；完成任务前和你确认工时与指派人。`check` 命令对比需求快照，发现需求在开发中途被修改时提示 |
| `jenkins-deploy` | 触发测试环境发版。`--country <cc>` 从 `.jenkins-deploy.json` 带出该国的环境参数。每次触发前都要你确认 |
| `env-config` | 测试环境操作：<br>• 查测试库：默认只读，写操作要加 `--write --confirm`<br>• 改 Nacos：发布前备份，用 CAS 防止覆盖，发布后读回比对<br>• 建、启停 xxl-job 任务<br>写操作都会记到 `~/.cache/apollo-env/ops.log` |
| `apollo-logs` | 通过 aliyun-observability MCP 查各国 SLS 日志。坐标表只存在本地 |
| `table-lineage` | 生成库表血缘页面 |
| `finishing-a-development-branch` | 收尾：先预演合并，再在临时 worktree 里合入测试集成分支。不强推，不碰上线分支 |

## 与通用版的关系

安装时依次叠加以下几层，后面的覆盖前面的同名文件：

1. `tier1-direct/`
2. 可选 skill：`jenkins-deploy`、`zentao`、`table-lineage`
3. `apollo/overlay/`
4. profile 的 `files/`

`apollo/overlay/` 里只放和通用版不同的文件，以及本项目独有的文件。通用版有更新时，把 main 合进本分支即可。

## 维护：从本地项目同步改动

```bash
P=~/.config/harness-agent/apollo
# 1. 列出要同步的文件（相对项目根），把真实值替换成占位符写进 overlay
python3 apollo/profile.py strip --profile $P --src <项目根> --dst apollo/overlay --paths-from list.txt
# 2. 检查有没有泄漏的真实值，以及 profile 里没有的占位符
python3 apollo/profile.py check --profile $P apollo/overlay
```

- 改动里出现新的项目专有名词：先加进 `profile.json` 的 `terms`，再执行 strip。
- 个人分支前缀写成 `{{BRANCH_OWNER}}`，它不在 profile 里，安装时由 `--branch-owner` 填入。
- 提交前必须执行 `check`。
