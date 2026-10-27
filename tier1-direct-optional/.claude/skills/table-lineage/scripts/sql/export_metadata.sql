-- Metadata export used by table-lineage.
-- Run each query and save the result as CSV (UTF-8, with header) under one folder,
-- using the file name given above each query. The run.py --meta-mysql mode runs
-- these same queries automatically.

-- tables.csv
SELECT table_schema, table_name, table_comment, table_rows, create_time, update_time
FROM information_schema.tables
WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
ORDER BY table_schema, table_name;

-- columns.csv
SELECT table_schema, table_name, ordinal_position, column_name, column_type,
       is_nullable, column_key, column_default, column_comment
FROM information_schema.columns
WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
ORDER BY table_schema, table_name, ordinal_position;

-- indexes.csv
SELECT table_schema, table_name, index_name, non_unique, seq_in_index, column_name
FROM information_schema.statistics
WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
ORDER BY table_schema, table_name, index_name, seq_in_index;

-- xxl_jobs.csv  (optional; skip if the xxl-job database is not reachable)
SELECT id, job_desc, executor_handler, executor_param, schedule_conf, trigger_status
FROM xxl_job.xxl_job_info;
