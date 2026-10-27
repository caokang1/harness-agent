"""Database metadata: load from a CSV folder or dump through the mysql CLI, then merge
physical shard tables into logical tables.

Both sources produce the same normalized folder layout:
    tables.csv, columns.csv, indexes.csv, [xxl_jobs.csv], source.json
"""
import csv, json, os, re, shlex, subprocess, datetime, collections

FILES = {
    'tables': ['table_schema', 'table_name', 'table_comment', 'table_rows', 'create_time', 'update_time'],
    'columns': ['table_schema', 'table_name', 'ordinal_position', 'column_name', 'column_type', 'is_nullable',
                'column_key', 'column_default', 'column_comment'],
    'indexes': ['table_schema', 'table_name', 'index_name', 'non_unique', 'seq_in_index', 'column_name'],
    'xxl_jobs': ['id', 'job_desc', 'executor_handler', 'executor_param', 'schedule_conf', 'trigger_status'],
}
OPTIONAL = {'xxl_jobs'}
SQL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sql', 'export_metadata.sql')


class MetadataError(Exception):
    pass


CR, LF = chr(13), chr(10)


def norm_header(h):
    """Header names are matched case-insensitively: GUI exports (Navicat/DBeaver) write TABLE_SCHEMA etc."""
    return h.replace(chr(0xFEFF), '').strip().lower() if isinstance(h, str) else h


def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return [{norm_header(k): (v or '').replace(CR + LF, LF).replace(CR, LF) for k, v in r.items()} for r in csv.DictReader(f)]


def write_csv(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in header})


def load_folder(src_dir):
    """Validate a CSV folder and return {name: rows}. Missing required files or columns raise."""
    data = {}
    for name, header in FILES.items():
        path = os.path.join(src_dir, name + '.csv')
        if not os.path.exists(path):
            if name in OPTIONAL:
                data[name] = []
                continue
            raise MetadataError(f'缺少 {name}.csv：{path}')
        rows = read_csv(path)
        missing = [h for h in header if rows and h not in rows[0]]
        if missing:
            raise MetadataError(f'{name}.csv 缺少列 {missing}，请按 sql/export_metadata.sql 导出')
        if not rows and name not in OPTIONAL:
            raise MetadataError(f'{name}.csv 是空的')
        data[name] = rows
    return data


def copy_folder(src_dir, out_dir, label=None):
    """CSV mode: validate and copy into the run folder."""
    data = load_folder(src_dir)
    os.makedirs(out_dir, exist_ok=True)
    for name, header in FILES.items():
        write_csv(os.path.join(out_dir, name + '.csv'), header, data[name])
    src_meta = {}
    p = os.path.join(src_dir, 'source.json')
    if os.path.exists(p):
        src_meta = json.load(open(p, encoding='utf-8'))
    meta = {'mode': 'csv', 'from': os.path.abspath(src_dir), 'label': label or src_meta.get('label') or os.path.basename(os.path.abspath(src_dir)),
            'exported_at': src_meta.get('exported_at') or datetime.datetime.fromtimestamp(
                os.path.getmtime(os.path.join(src_dir, 'tables.csv'))).strftime('%Y-%m-%d %H:%M')}
    json.dump(meta, open(os.path.join(out_dir, 'source.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return meta


def _split_queries():
    text = open(SQL_PATH, encoding='utf-8').read()
    out = {}
    for name, body in re.findall(r'--\s*(\w+)\.csv[^\n]*\n(.*?);', text, re.S):
        out[name] = '\n'.join(l for l in body.splitlines() if not l.strip().startswith('--')).strip()
    return out


BS = chr(92)
BATCH_ESC = {'n': LF, 't': chr(9), 'r': CR, '0': chr(0), BS: BS}


def unescape_batch(v):
    """Undo mysql --batch escaping (backslash + n, t, r, 0, backslash) so multi-line comments survive."""
    if BS not in v: return v
    out = []; i = 0
    while i < len(v):
        c = v[i]
        if c == BS and i + 1 < len(v) and v[i + 1] in BATCH_ESC:
            out.append(BATCH_ESC[v[i + 1]]); i += 2
        else:
            out.append(c); i += 1
    return ''.join(out)


def dump_mysql(cnf_path, out_dir, mysql_bin='mysql', label=None):
    """Direct mode: run the export queries through the mysql CLI using a defaults file
    (host/port/user/password live in the .cnf, never on the command line)."""
    if not os.path.exists(cnf_path):
        raise MetadataError(f'找不到连接配置文件：{cnf_path}（参考 config/db.cnf.example）')
    os.makedirs(out_dir, exist_ok=True)
    queries = _split_queries()
    for name, header in FILES.items():
        sql = queries[name]
        exe = [x[1:-1] if len(x) > 1 and x[0] == x[-1] == '"' else x for x in shlex.split(mysql_bin, posix=(os.name != 'nt'))]
        cmd = exe + [f'--defaults-extra-file={cnf_path}', '--batch', '--default-character-set=utf8mb4', '-e', sql]
        try:
            proc = subprocess.run(cmd, capture_output=True)
        except FileNotFoundError:
            raise MetadataError(f'找不到 mysql 客户端：{mysql_bin}（用 --mysql-bin 指定路径，或改用 --meta-csv）')
        if proc.returncode != 0:
            err = proc.stderr.decode('utf-8', 'replace').strip()
            if name in OPTIONAL:
                write_csv(os.path.join(out_dir, name + '.csv'), header, [])
                print(f'  [跳过] {name}：{err[:200]}')
                continue
            raise MetadataError(f'导出 {name} 失败：{err[:500]}')
        lines = proc.stdout.decode('utf-8', 'replace').split('\n')
        got = lines[0].split('\t') if lines and lines[0] else header
        rows = []
        for ln in lines[1:]:
            if not ln:
                continue
            vals = ln.split('\t')
            rows.append({norm_header(h): ('' if v == 'NULL' else unescape_batch(v).replace(CR + LF, LF).replace(CR, LF)) for h, v in zip(got, vals)})
        write_csv(os.path.join(out_dir, name + '.csv'), header, rows)
        print(f'  导出 {name}: {len(rows)} 行')
    host = ''
    for ln in open(cnf_path, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*host\s*=\s*(\S+)', ln)
        if m:
            host = m.group(1)
    meta = {'mode': 'mysql', 'from': host, 'label': label or host,
            'exported_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
    json.dump(meta, open(os.path.join(out_dir, 'source.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    load_folder(out_dir)
    return meta


# ---------------------------------------------------------------- shard merge
def merge_logical(tables, cfg):
    """Group physical tables into logical tables.
    Pass 1 strips a numeric suffix (_0.._9999 or _yyyyMM / _yyyyMMdd); a group with one member keeps its own name.
    Pass 2 folds date-partitioned groups (_yyyy_MM, _yyyy) that were themselves split into several tables.
    """
    suf = re.compile(cfg.get('shard_suffix_regex', r'^(.*?)(_(?:\d{6,8}|\d{1,4}))$'))
    groups = collections.OrderedDict()
    for r in tables:
        n = r['table_name']
        m = suf.match(n)
        key = (r['table_schema'], m.group(1) if m else n)
        g = groups.setdefault(key, {'schema': key[0], 'table': key[1], 'names': [], 'rows': 0, 'comment': '', 'update': ''})
        g['names'].append(n)
        g['rows'] += int(r['table_rows'] or 0)
        if r['table_comment'] and not g['comment']:
            g['comment'] = r['table_comment']
    first = []
    for g in groups.values():
        if len(g['names']) == 1:
            g['table'] = g['names'][0]
        first.append(g)
    date_rx = [re.compile(x) for x in cfg.get('date_partition_regex', [r'^(.*)_\d{4}_\d{2}$', r'^(.*)_\d{4}$'])]
    merged = collections.OrderedDict()
    for g in first:
        t = g['table']
        if len(g['names']) > 1:
            for rx in date_rx:
                m = rx.match(t)
                if m:
                    t = m.group(1)
        k = (g['schema'], t)
        if k in merged:
            x = merged[k]
            x['names'] += g['names']; x['rows'] += g['rows']; x['comment'] = x['comment'] or g['comment']
        else:
            merged[k] = dict(g, table=t)
    bak = re.compile(cfg.get('backup_regex', r'_(bak|backup|copy|old|tmp|temp|test)\d*$|_\d{6,8}$|^tmp_|^test_|^bak_'), re.I)
    out = []
    for g in merged.values():
        out.append({'schema': g['schema'], 'table': g['table'], 'shards': len(g['names']), 'rows': g['rows'],
                    'comment': g['comment'], 'names': g['names'],
                    'backup': bool(bak.search(g['table'])) and len(g['names']) == 1})
    return out
