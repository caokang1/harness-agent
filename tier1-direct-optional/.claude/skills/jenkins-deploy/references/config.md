# 配置与参数推断

## 配置项

| 配置文件字段 | 环境变量 | 说明 |
|---|---|---|
| `url` | `JENKINS_URL` | Jenkins 地址，必须是 `https://`（除非开启 `allow_http`） |
| `user` | `JENKINS_USER` | Jenkins 用户名 |
| `token` | `JENKINS_TOKEN` | API Token：Jenkins 右上角用户名 → Security → API Token |
| `folders` | `JENKINS_FOLDERS`（逗号分隔） | 只扫描这些文件夹，如 `team-a/dev`；不填扫描全部 |
| `allow_http` | `JENKINS_ALLOW_HTTP=1` | 允许 `http://` 地址（凭据会明文传输，仅限可信内网） |

- 配置文件默认位置是 `~/.config/jenkins-deploy/config.json`，可以用 `JENKINS_DEPLOY_CONFIG` 改。
- 环境变量优先于配置文件。
- 文件权限对其他用户可读时，脚本会提示你 `chmod 600`。

## 项目配置：默认任务

在业务项目的仓库根目录放一个 `.jenkins-deploy.json`，以后不带任务名也知道用哪个任务。这个文件不含凭据，可以提交给团队共用：

```json
{"job": "team-a/dev/order-service"}
```

确定任务的优先级：命令行指定 > `.jenkins-deploy.json` > 按仓库地址自动匹配。

## 任务列表缓存

- 位置：`~/.cache/jenkins-deploy/jobs-<地址哈希>.json`，目录权限 700。
- 按 Jenkins 地址区分，有效期 24 小时，修改 `folders` 后自动失效。
- 加 `--refresh` 强制重新读取。
- 缓存里只有任务名和参数定义，不包含凭据。

## 参数推断规则

| 参数 | 来源 |
|---|---|
| 分支参数：`repoBranch` `BRANCH` `GIT_BRANCH` `BRANCH_NAME` `branch` | 当前分支 |
| 标签参数：`repoTag` `TAG` `GIT_TAG` `tag` | 指向当前提交的标签；没有就用任务默认值，并给出警告 |
| 仓库参数：`repoUrl` `REPO_URL` `GIT_URL` `gitUrl`，或默认值以 `.git` 结尾的参数 | 只用来按当前仓库匹配任务 |
| 只读参数（`WReadonlyStringParameterDefinition`） | 不提交，由 Jenkins 用默认值，也不允许通过 `--params` 修改 |
| 其他参数 | 任务默认值；选项参数没有默认值时取第一个非空选项 |

优先级：`--params` / `--branch` / `--tag` > 当前分支和标签 > 任务默认值。

## 检查项

模拟运行和触发前都会检查下面这些项。✗ 表示错误，不允许触发；⚠ 表示警告，会展示给用户。

- ✗ `--params` 里有任务不存在的参数，防止参数名拼错后被 Jenkins 静默忽略。
- ✗ 修改只读参数。
- ✗ 选项参数的值不在可选项里。
- ✗ 分支或标签在远端不存在：Jenkins 拉不到代码。
- ⚠ 本地提交与远端不一致：Jenkins 构建的是远端版本。
- ⚠ 工作区有未提交的改动。
- ⚠ 参数值为空。

## 确认码

确认码是对「Jenkins 地址 + 任务 + 全部参数 + 分支 / 标签对应的远端提交」算的指纹。

- `--trigger` 时会重新计算确认码。只要任务、参数或远端提交与确认时有一处不同，就拒绝触发。
- 它只保证"触发的就是给人看过的那一份"，不能拦住一个能自己执行 dry-run 的程序。是否需要人工确认，仍然靠 SKILL.md 里的流程约束。

## 支持的任务类型

- 自由风格任务、流水线任务，带参数或不带参数都可以。
- 文件夹会递归扫描，最多 4 层。
- 多分支流水线和组织文件夹不支持，扫描时会跳过。
