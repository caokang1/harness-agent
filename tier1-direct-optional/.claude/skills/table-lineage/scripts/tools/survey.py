"""First look at a new project: draft config/project.json plus a survey report with the evidence behind every guess.

    python tools/survey.py --repo /path/to/repo --meta-csv /path/to/metadata --workspace W [--project 名称]

Nothing here is trusted blindly: every value in the draft is a guess that a human (or Claude, by reading code)
confirms before the first real run. survey.md says why each guess was made.
"""
import argparse, collections, json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from lineage import metadata  # noqa: E402

SKIP = {'target', 'build', '.git', 'node_modules', '.idea', 'out', 'dist', 'test', 'tests'}
INFRA_RX = re.compile(r'nacos|xxl|canal|schedul|quartz|seata|flyway|liquibase|kafka|sys_?log|information_schema', re.I)
REPORT_RX = re.compile(r'stat|report|dw|dws|ads|bi$|^bi_|olap|analy', re.I)
VERIFY_RX = re.compile(r'(verify|check|reconcil)\w*_log|log\w*_(verify|check)', re.I)
EXT_RX = re.compile(r'admin|gateway|web|portal|console|open|bff|front', re.I)
SQL_TABLE = re.compile(r'\b(?:from|join|into|update)\s+`?(?:\w+`?\.`?)?(\w+)`?', re.I)
GENERIC_SEG = {'com', 'org', 'net', 'cn', 'io', 'mapper', 'mappers', 'dao', 'daos', 'repository', 'db', 'base', 'common',
               'java', 'main', 'src', 'impl', 'service', 'entity', 'model', 'domain', 'po', 'infra', 'persistence'}


def java_files(repo):
    for dp, dn, fn in os.walk(repo):
        dn[:] = [d for d in dn if d not in SKIP and not d.startswith('.')]
        for f in fn:
            if f.endswith(('.java', '.xml')):
                yield os.path.join(dp, f)


def module_of(repo, path):
    return os.path.relpath(path, repo).replace(os.sep, '/').split('/')[0]


def survey(repo, meta):
    mods = collections.defaultdict(collections.Counter)
    mod_tables = collections.defaultdict(collections.Counter)
    seg_tables = collections.defaultdict(collections.Counter)
    ref_types = collections.Counter(); registry = collections.Counter(); checks = collections.Counter(); topics = collections.Counter()
    bases = collections.Counter(); base_methods = {}; routes = collections.defaultdict(list)
    xml_ns_tables = {}; entity_table = {}
    files = [p for p in java_files(repo) if module_of(repo, p) != os.path.basename(p)]
    for p in files:   # pass 1: XML statements and MyBatis-Plus entities, so mapper interfaces can be resolved in pass 2
        text = open(p, encoding='utf-8', errors='ignore').read()
        if p.endswith('.xml'):
            m = re.search(r'<mapper[^>]*namespace="([\w.]+)"', text)
            if m:
                mods[module_of(repo, p)]['xml_mappers'] += 1
                xml_ns_tables[m.group(1)] = SQL_TABLE.findall(re.sub(r'<[^>]+>', ' ', text))
        else:
            m = re.search(r'@TableName\(\s*(?:value\s*=\s*)?"(\w+)"', text)
            if m: entity_table[os.path.basename(p)[:-5]] = m.group(1)
    for p in files:
        if p.endswith('.xml'): continue
        mod = module_of(repo, p)
        text = open(p, encoding='utf-8', errors='ignore').read()
        c = mods[mod]
        c['java'] += 1
        if re.search(r'@(Rest)?Controller\b', text): c['controllers'] += 1
        if '@FeignClient' in text: c['feign_clients'] += 1
        c['kafka_listeners'] += len(re.findall(r'^\s*@KafkaListener', text, re.M))
        c['xxl_jobs'] += text.count('@XxlJob')
        c['scheduled'] += text.count('@Scheduled')
        is_mapper = re.search(r'\binterface\s+\w+(Mapper|Dao)\b', text) or ('@Mapper' in text and 'interface ' in text)
        if is_mapper:
            c['mappers'] += 1
            pkg = re.search(r'^\s*package\s+([\w.]+)\s*;', text, re.M)
            fqn = (pkg.group(1) + '.' if pkg else '') + os.path.basename(p)[:-5]
            ts = SQL_TABLE.findall(' '.join(re.findall(r'"((?:[^"\\]|\\.)*)"', text)))
            ts += xml_ns_tables.get(fqn, [])
            ts += [entity_table[e] for e in re.findall(r'BaseMapper<\s*(\w+)\s*>', text) if e in entity_table]
            for t in ts:
                mod_tables[mod][t.lower()] += 1
                for seg in (pkg.group(1).split('.') if pkg else []):
                    if seg not in GENERIC_SEG: seg_tables[seg][t.lower()] += 1
        for t, body in re.findall(r'List<(\w+)>\s+\w+\s*=([^;]*(?:\{\{.*?\}\})?)', text, re.S):
            if re.search(re.escape(t) + r'\(\s*"\w+"\s*,\s*"\w+"', body):
                ref_types[t] += 1
                cm = re.search(r'\b(?:class|interface)\s+(\w+)', text)
                registry[cm.group(1) if cm else os.path.basename(p)[:-5]] += 1
        # Type("db", "table", TOPIC...) with a non-string third argument: candidate table -> topic routing rule
        for t, db in re.findall(r'new\s+(\w+)\(\s*"(\w+)"\s*,\s*"\w+"\s*,\s*(?!")', text): routes[t].append(db)
        if '@KafkaListener' in text:
            for name in re.findall(r'\.(\w+)\(\s*(?:\w+\.)?[A-Z][A-Z0-9_]{2,}\s*\)', text): checks[name] += 1
            for tp in re.findall(r'topics\s*=\s*\{?\s*"([^"]+)"', text): topics[tp] += 1
        for b in re.findall(r'\bclass\s+\w+\s+extends\s+(\w*(?:Handler|Job|Task|Processor))\b', text): bases[b] += 1
        m = re.search(r'abstract\s+class\s+(\w*(?:Handler|Job|Task|Processor))\b', text)
        if m: base_methods[m.group(1)] = re.findall(r'abstract\s+[\w<>\[\], ?]+\s+(\w+)\s*\(', text)
    return mods, mod_tables, seg_tables, ref_types, registry, checks, topics, bases, base_methods, routes


def topic_marker(topics):
    """Shared fragment of the frequent listener topics (used at least a tenth as often as the most common one)."""
    if not topics: return None
    top = topics.most_common(1)[0][1]
    p = common_prefix([x for x, n in topics.most_common(5) if n >= top / 10]).lstrip("#{'$")
    return p or None


def common_prefix(xs):
    # cut back to the last separator: "cdc.shop_order" + "cdc.shop_member" -> "cdc."
    p = xs[0] if xs else ''
    for x in xs[1:]:
        while not x.startswith(p): p = p[:-1]
    cut = max(p.rfind(c) for c in '.-:/')
    return p[:cut + 1] if cut >= 0 and len(xs) > 1 else p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--meta-csv', required=True, help='按 sql/export_metadata.sql 导出的 CSV 文件夹')
    ap.add_argument('--workspace', required=True, help='项目工作目录：草稿写到 <workspace>/config/project.json')
    ap.add_argument('--project', default='')
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    meta = metadata.load_folder(args.meta_csv)
    cfg_meta = {}
    logical = metadata.merge_logical(meta['tables'], cfg_meta)
    dbs = collections.Counter(e['schema'] for e in logical)
    by_name = collections.defaultdict(set)
    for e in logical:
        for n in [e['table']] + e['names']: by_name[n.lower()].add(e['schema'])

    mods, mod_tables, seg_tables, ref_types, registry, checks, topics, bases, base_methods, routes = survey(repo, meta)
    out = []
    say = out.append
    say(f'# 项目勘察：{args.project or os.path.basename(repo)}\n')
    say(f'- 代码：{repo}\n- 元数据：{len(meta["tables"])} 张物理表 → {len(logical)} 张逻辑表，{len(dbs)} 个库\n')

    say('## 模块\n\n| 模块 | Java | Controller | FeignClient | Kafka 监听 | @XxlJob | @Scheduled | Mapper | XML Mapper |\n|---|---|---|---|---|---|---|---|---|')
    for m in sorted(mods):
        c = mods[m]
        say(f"| {m} | {c['java']} | {c['controllers']} | {c['feign_clients']} | {c['kafka_listeners']} | {c['xxl_jobs']} | {c['scheduled']} | {c['mappers']} | {c['xml_mappers']} |")
    entry = lambda c: c['controllers'] + c['kafka_listeners'] + c['xxl_jobs'] + c['scheduled']
    shared_name = lambda m: re.search(r'common|base|api|core|shared|framework|starter', m, re.I)
    shared = sorted(m for m, c in mods.items() if c['java'] and (
        (not entry(c) and (c['feign_clients'] or shared_name(m))) or (shared_name(m) and c['controllers'] <= 3 and not c['kafka_listeners'])))
    external = sorted(m for m, c in mods.items() if c['controllers'] and (not c['mappers'] or EXT_RX.search(m)) and m not in shared)
    say(f'\n- 猜测的共享模块（无入口、放 Feign 接口或公共代码）：{", ".join(shared) or "无"}')
    say(f'- 猜测的对外模块（有 Controller、自己不连库或名字像后台/网关）：{", ".join(external) or "无"}。**请确认**：对外模块里的 HTTP 接口会被当成“外部查询接口”。\n')

    say('## 库\n\n| 库 | 逻辑表数 | 猜测 |\n|---|---|---|')
    infra = sorted(d for d in dbs if INFRA_RX.search(d))
    report = sorted(d for d in dbs if REPORT_RX.search(d) and d not in infra)
    for d, n in sorted(dbs.items()):
        say(f"| {d} | {n} | {'基础设施' if d in infra else '报表库' if d in report else '业务库'} |")
    verify_logs = sorted(f"{e['schema']}.{e['table']}" for e in logical if e['schema'] in report and VERIFY_RX.search(e['table']))
    say(f'- 猜测的校验日志表：{", ".join(verify_logs) or "无"}。**请确认**：校验日志表不会被当成任何表的上游。')
    say('\n**请确认报表库**：报表库里的表才会被分类为“报表/中间表”并要求口径卡片。只有一个库的项目可以把报表表逐张写进 report_tables_outside。\n')

    def vote(counter):
        c = collections.Counter()
        for t, n in counter.items():
            if len(by_name.get(t, ())) == 1: c[next(iter(by_name[t]))] += n
        if not c: return None, 0, 0
        db, n = c.most_common(1)[0]
        return db, n, n / sum(c.values())
    module_db = {}
    say('## 模块 → 库（按 Mapper SQL 里只在一个库出现的表投票）\n\n| 模块 | 库 | 票数 | 纯度 |\n|---|---|---|---|')
    for m in sorted(mod_tables):
        db, n, purity = vote(mod_tables[m])
        if db:
            say(f'| {m} | {db} | {n} | {purity:.0%} |')
            if purity >= 0.6: module_db[m] = db
    pkg_db = {}
    say('\n## Mapper 包片段 → 库（同名表分属多个库时靠它判定）\n\n| 包片段 | 库 | 票数 | 纯度 |\n|---|---|---|---|')
    for seg in sorted(seg_tables):
        db, n, purity = vote(seg_tables[seg])
        if db and n >= 2 and purity >= 0.8:
            pkg_db[seg] = db
            say(f'| {seg} | {db} | {n} | {purity:.0%} |')
    dup = sorted(t for t, s in by_name.items() if len(s) > 1)
    say(f'\n同名表（在多个库里都有）：{len(dup)} 张{"，例如 " + ", ".join(dup[:8]) if dup else ""}。纯度低于 80% 的包片段没有写进草稿，请人工判断。\n')

    say('## binlog 订阅（CDC）写法\n')
    cdc = {}
    if ref_types:
        t = ref_types.most_common(1)[0][0]
        cdc = {'table_ref_type': t, 'registry_class': registry.most_common(1)[0][0] if registry else None,
               'check_method': checks.most_common(1)[0][0] if checks else None,
               'topic_marker': topic_marker(topics),
               'route_rule_type': next((r for r, ds in sorted(routes.items(), key=lambda kv: (-len(kv[1]), kv[0]))
                                        if r != t and len(ds) >= 2 and sum(d in dbs for d in ds) >= 0.8 * len(ds)), None)}
        say(f'- 订阅表清单类型候选：{dict(ref_types.most_common(3))}')
        say(f'- 声明清单最多的类（类名，不是文件名）：{dict(registry.most_common(3))}')
        say(f'- 监听里用常量当参数调用的方法：{dict(checks.most_common(5))}')
        say(f'- 监听的 topic：{dict(topics.most_common(8))}')
        say(f'- 按（库, 表, topic）构造的路由规则类候选：{ {r: len(ds) for r, ds in routes.items() if len(ds) >= 2} or "无"}')
        say('- **请读一个监听类确认**：清单类型构造参数是不是 ("库", "表")；判断订阅用哪个方法；直接接 binlog 的 topic 有什么共同片段。按表路由到内部 topic 的配置类（如果有）填 route_rule_type。\n')
    else:
        say('- 没有找到 `List<X>` + `X("库", "表")` 形式的订阅清单。如果项目用别的方式声明订阅，需要扩展扫描器（见 references/extending.md）；没有 binlog 订阅就不用管。\n')

    say('## 调度\n')
    sched_base = {}
    cand = [(b, n) for b, n in bases.most_common(5) if n >= 3]
    say(f"- @XxlJob {sum(c['xxl_jobs'] for c in mods.values())} 处，@Scheduled {sum(c['scheduled'] for c in mods.values())} 处，xxl_jobs.csv {len(meta.get('xxl_jobs', []))} 行")
    if cand:
        say(f'- 被很多类继承的调度基类候选：{cand}，抽象方法：{ {b: base_methods.get(b, []) for b, _ in cand} }')
        say('- **请确认**：如果这些基类的子类由自研调度框架按方法名触发，在 scheduler.handler_base 里填 {method, class_prefix, class_suffix}。\n')

    core = collections.Counter()
    biz = [e for e in logical if e['schema'] not in infra and e['schema'] not in report]
    names = {e['table'].lower(): e for e in biz}
    for r in meta['columns']:
        c = r['column_name'].lower()
        if c.endswith('_id') and r['table_schema'] not in infra:
            base = c[:-3]
            for cand_name in (base, base + 's', 't_' + base):
                if cand_name in names: core[f"{names[cand_name]['schema']}.{names[cand_name]['table']}"] += 1; break
    core_tables = []
    say('## ER 核心表\n')
    say('草稿里先留空。第一次运行后，report.md 会列出“报表最常直接取数的业务表”，从那里挑 10~20 张填进 er.core_tables。')
    say('参考：被最多 `xxx_id` 字段指向的业务表：' + (', '.join(f'{k}（{n}）' for k, n in core.most_common(15)) or '没有找到'))
    say('\n字段名和表名对不上的（如 order_id 指向 orders）在 er.column_alias 里补。\n')

    cfg = {'project': args.project or os.path.basename(repo), 'repo': repo.replace(os.sep, '/'),
           'scan': {'skip_dirs': sorted(SKIP | {'docs'}), 'feign_shallow_levels': 3},
           'modules': {'external': external, 'shared': shared},
           'cdc': {k: v for k, v in cdc.items() if v},
           'scheduler': {'handler_base': sched_base},
           'databases': {'infra': infra, 'report': report, 'report_tables_outside': [], 'report_exclude': [], 'verify_log_tables': verify_logs,
                         'mapper_package_db': pkg_db, 'module_db': module_db,
                         'business_db_labels': {d: f'{d}（业务库）' for d in sorted(dbs) if d not in infra and d not in report}},
           'metadata': {'shard_suffix_regex': '^(.*?)(_(?:\\d{6,8}|\\d{1,4}))$', 'date_partition_regex': ['^(.*)_\\d{4}_\\d{2}$', '^(.*)_\\d{4}$'],
                        'backup_regex': '_(bak|backup|copy|old|tmp|temp|test)\\d*$|_\\d{6,8}$|^tmp_|^test_|^bak_'},
           'er': {'core_tables': core_tables, 'column_alias': {}, 'db_order': sorted({k.split('.')[0] for k in core_tables})},
           'page': {'title': '', 'readers_cap': 40}}
    os.makedirs(os.path.join(args.workspace, 'config'), exist_ok=True)
    dst = os.path.join(args.workspace, 'config', 'project.json')
    if os.path.exists(dst):
        dst = os.path.join(args.workspace, 'config', 'project.draft.json')
    json.dump(cfg, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    rep = os.path.join(args.workspace, 'survey.md')
    open(rep, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print(f'配置草稿：{dst}\n勘察报告：{rep}')


if __name__ == '__main__':
    main()
