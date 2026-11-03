---
name: env-config
description: 测试环境配置与数据操作：查 / 改测试库（默认只读）、改 Nacos 配置（带备份和 CAS）、建 / 启停 xxl-job 任务、按国家发测试环境。用户说"连测试库查一下""自测""改 Nacos""配 xxl-job""加定时任务""发测试环境"时使用。
---

# 测试环境配置与数据

所有凭据只放在用户目录（`chmod 600`），不进仓库、不写进命令行参数、不在回复里复述：

| 用途 | 文件 |
|---|---|
| 测试库 | `~/.config/apollo-db/<env>.properties`（`host` `user` `password`），如 `{{AP_CC}}-test` |
| Nacos | `~/.config/apollo-env/nacos.json`（每个 env 一项：`url` `namespace` `group`，有鉴权时加 `username` `password`） |
| Jenkins | `~/.config/jenkins-deploy/config.json`（jenkins-deploy skill） |

文件不存在时问用户要，拿到后替用户写入并 `chmod 600`。

**留痕**：对共享环境的每次写操作（库表、Nacos）都会自动追加到 `~/.cache/apollo-env/ops.log`（时间、环境、对象、改动量、备份位置）。回复里也要写清改了什么、原值是什么、怎么回滚。

## 查库 / 自测：`scripts/db.sh`

```bash
S=.claude/skills/env-config/scripts
$S/db.sh {{AP_CC}}-test {{AP_DB_LOAN}} "select count(1) from {{AP_TABLE_ORDER}}_4 where status = '21'"
$S/db.sh {{AP_CC}}-test {{AP_DB_STAT}} -f check.sql                       # 多条，用 ";换行" 分隔
$S/db.sh {{AP_CC}}-test {{AP_DB_STAT}} --write --confirm "delete ..."      # 写操作
```

- **默认只读**：非 `select/show/desc/explain` 语句直接拒绝。写操作必须 `--write --confirm`，并且只能在用户同意**这条具体语句**之后执行；执行前先 `select` 确认目标库和影响行数。
- **本机到测试库的链路走 Clash TUN，返回几十行以上就可能断**：读操作会自动换新连接重试，结果默认最多 200 行（`--max-rows`）。要统计就在 SQL 里 `count/sum/group by` 好再返回，不要把明细拉回来算。
- `{{AP_TABLE_ORDER}}` 等分表要自己 `union all` 各分表（`{{AP_TABLE_ORDER}}_0`~`_11`），本地没有 ShardingSphere。
- 测试数据一律带 `__agent_verify_` 前缀，测完在同一轮里删掉并确认剩余为 0。
- 根治断连：让用户在 Clash 规则里把测试库 IP（见 `~/.config/apollo-db/<env>.properties` 的 `host`）设为 `DIRECT`。

## 改 Nacos：`scripts/nacos.py`

```bash
$S/nacos.py get {{AP_CC}}-test {{AP_SVC_LOAN}}-dev.yml -o /tmp/<会话临时目录>/loan.yml   # 1. 读
# 2. 只在副本里插入 / 修改需要的行，不重排、不格式化
$S/nacos.py set {{AP_CC}}-test {{AP_SVC_LOAN}}-dev.yml --file <副本>                      # 3. 只看 diff（退出码 3）
$S/nacos.py set {{AP_CC}}-test {{AP_SVC_LOAN}}-dev.yml --file <副本> --confirm            # 4. 用户同意 diff 后发布
```

- 发布前自动备份原文到 `~/.cache/apollo-env/nacos-backups/`，用读取时内容的 MD5 做 CAS：期间有人改过会被拒绝，重新读再改。
- 发布后读回比对，不一致会报错并给出备份位置。
- 值里有 `:`、`+`、时间等可能被 YAML 解析成别的类型的，加引号。
- 改的是开关类配置（如 `enabled`）时，先告诉用户打开后**现有**规则的影响，再改。
- {{AP_CC_UPPER}} 测试：dataId 为 `<服务>-dev.yml`，group `{{AP_NS}}-{{AP_CC}}`，`common.yml` 为共享配置。

## xxl-job

xxl-job 的任务存在测试库的 `xxl_job` 库里（用上面的 `db.sh`）。管理台能做的优先让用户在管理台做；需要 Agent 做时：

- **建任务**：复制一个调用同一服务的现有任务，只改描述、cron、参数，新任务先建成**停用**（`trigger_status = 0`），接口发到环境后再启用：

  ```sql
  insert into xxl_job.xxl_job_info (job_group, job_desc, add_time, update_time, author, alarm_email, schedule_type, schedule_conf,
    misfire_strategy, executor_route_strategy, executor_handler, executor_param, executor_block_strategy, executor_timeout,
    executor_fail_retry_count, glue_type, glue_source, glue_remark, glue_updatetime, child_jobid, trigger_status, trigger_last_time, trigger_next_time)
  select job_group, '<English description (#禅道号)>', now(), now(), '<作者>', alarm_email, 'CRON', '<cron>', misfire_strategy,
    executor_route_strategy, executor_handler, 'http://<service>/<path>', executor_block_strategy, executor_timeout,
    executor_fail_retry_count, glue_type, glue_source, glue_remark, now(), child_jobid, 0, 0, 0
  from xxl_job.xxl_job_info where id = <模板任务 id>;
  ```

  {{AP_SVC_TABLE}} 的模板：{{AP_CC_UPPER}} 测试{{AP_XXL_TEMPLATE_JOB}}（GLUE_GROOVY，`executor_param` 是 `http://{{AP_SVC_TABLE}}/<path>`，通过注册中心调用）。建之前先查 `executor_param` 防重复。
- **启用**：`update ... set trigger_status = 1, trigger_last_time = 0, trigger_next_time = <下一次触发的毫秒时间戳> where id = ? and trigger_status = 0`。
- **结果**：`select trigger_time, trigger_code, handle_code, left(handle_msg, 200) from xxl_job.xxl_job_log where job_id = ? order by id desc limit 5`（`handle_code = 200` 为成功）。
- 描述用英文。

## 发测试环境

用 jenkins-deploy skill。仓库根目录 `.jenkins-deploy.json` 记了发版任务（`{{AP_NS}}-{{AP_JENKINS_FOLDER_SUFFIX}}/{{AP_NS}}-{{AP_JENKINS_JOB_SUFFIX}}`，所有国家都用它）、默认参数和各国 `NAMESPACE`：

```bash
python3 .claude/skills/jenkins-deploy/scripts/jenkins_deploy.py --dry-run --country {{AP_CC}} --params '{"PROJECT_NAME":"{{AP_SVC_LOAN}},{{AP_SVC_TABLE}}"}'
```

照常把 dry-run 结果给用户确认后再 `--trigger`。

## 不要做

- 不经用户同意写库、发布 Nacos、启停 xxl-job 任务。
- 用 root 账号做批量写或 DDL 时不先确认目标库（`select database(), @@hostname`）。
- 把凭据写进项目文件、命令行参数或回复。
