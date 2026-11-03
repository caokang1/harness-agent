# 国家 → SLS 坐标（本地文件，不入库）

查询三要素：`regionId` + `project` + `logStore`。业务应用日志统一是 `{{AP_NS}}-<cc>-all-{{AP_LOG_SUFFIX}}`。

| 国家 | regionId | project | 业务日志 logStore |
|---|---|---|---|
| {{AP_CC3_LABEL}} | `<regionId>` | `<project>` | `{{AP_NS}}-{{AP_CC3_ALL}}-{{AP_LOG_SUFFIX}}` |
| {{AP_CC_UPPER}} {{AP_CC_NAME}} | `<regionId>` | `<project>` | `{{AP_NS}}-{{AP_CC}}-all-{{AP_LOG_SUFFIX}}` |

查法：`sls_list_projects(regionId=...)` 找 project，再 `sls_list_logstores(project, regionId)` 找 `*-all-{{AP_LOG_SUFFIX}}`。
