"""Generate the lineage page in one command.

  python run.py --workspace W --meta-csv W/inputs/2026-11-01            # metadata from a CSV folder (e.g. a GUI client export)
  python run.py --workspace W --meta-mysql W/config/db.cnf --label 测试库  # metadata dumped live through the mysql CLI
  python run.py --workspace W --meta-csv ... --repo /tmp/other-checkout  # scan another checkout with the same config

The workspace holds everything project-specific: config/project.json, knowledge/, inputs/, runs/.
Each run writes runs/<timestamp>/ with the page, data, evaluation and a change report,
and compares itself with the previous run.
"""
import argparse, datetime, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
# Fixed hash seed: set iteration order (and therefore example call trails) must be identical between runs.
if os.environ.get('PYTHONHASHSEED') != '0':
    env = dict(os.environ, PYTHONHASHSEED='0')
    sys.exit(subprocess.run([sys.executable, '-P'] + sys.argv, env=env).returncode)
sys.path.insert(0, HERE)
from lineage import metadata, build, evaluate, checks  # noqa: E402


def load_json(p, default=None):
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


def load_knowledge(kdir):
    cards = {k: v for k, v in load_json(os.path.join(kdir, 'cards.json'), {}).items() if not k.startswith('_')}
    domains = load_json(os.path.join(kdir, 'domains.json'), {'domains': {}})
    glossary = load_json(os.path.join(kdir, 'glossary.json'), {'terms': [], 'inline': []})
    notes = load_json(os.path.join(kdir, 'accuracy_notes.json'), {}).get('notes', [])
    truth = []
    tdir = os.path.join(kdir, 'truth')
    for f in sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []:
        if f.endswith('.json'):
            truth.append((f[:-5], load_json(os.path.join(tdir, f))))
    return cards, domains, glossary, notes, truth


def diff_runs(prev, cur, prev_label):
    """Table-level differences between two page datasets."""
    if not prev: return None
    def sig(t, S, E):
        writers = sorted({E[w[0]]['n'] for w in t['w'] if E[w[0]]['kind'] != 'kafka_off'})
        src = sorted(s[0] for s in t['src'] if s[1] in ('canal', 'forward', 'sql'))
        return writers, src
    pt = {t['k']: t for t in prev['tables']}; ct = {t['k']: t for t in cur['tables']}
    added = sorted(set(ct) - set(pt)); removed = sorted(set(pt) - set(ct))
    changed, status, schema = [], [], []
    for k in sorted(set(ct) & set(pt)):
        a, b = pt[k], ct[k]
        ca, cb = [c[0] for c in a['cols']], [c[0] for c in b['cols']]
        if ca != cb:
            schema.append([k, [c for c in cb if c not in ca], [c for c in ca if c not in cb]])
        if a['kind'] in ('报表', '中间表') or b['kind'] in ('报表', '中间表'):
            if sig(a, prev['S'], prev['entries']) != sig(b, cur['S'], cur['entries']): changed.append(k)
        if a.get('st', '') != b.get('st', ''): status.append([k, a.get('st', ''), b.get('st', '')])
    return {'prev_label': prev_label, 'added': added, 'removed': removed, 'changed': changed, 'status': status, 'schema': schema}


def example_table(data):
    """Overview example: the reviewed report table with the most upstream tables, else any report table."""
    rep = [t for t in data['tables'] if t['kind'] in ('报表', '中间表')]
    confirmed_risk = lambda t: any(r[1] for r in t.get('card', {}).get('risks', []))
    best = sorted(rep, key=lambda t: (not t.get('card'), confirmed_risk(t), -len(t['src']), t['k']))
    return best[0]['k'] if best else (data['tables'][0]['k'] if data['tables'] else '')


def acc_md(cols, rows, n_sets):
    if not n_sets: return ['还没有标准答案，准确率未经测量（见 references/ground-truth.md）。']
    head = [c.replace('<br>', ' ').replace('<span class="faint">', '（').replace('</span>', '）') for c in cols]
    return ['| 指标 | ' + ' | '.join(head) + ' |', '|---' * (len(cols) + 1) + '|'] + ['| ' + ' | '.join(r) + ' |' for r in rows]


def core_candidates(data, n=20):
    kind = {t['k']: t['kind'] for t in data['tables']}
    c = {}
    for t in data['tables']:
        if t['kind'] in ('报表', '中间表'):
            for s in t['src']:
                if s[1] != 'feign_deep' and kind.get(s[0]) == '业务底表': c[s[0]] = c.get(s[0], 0) + 1
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def render(template, data, title, out):
    acc = data.pop('_acc')
    html = open(template, encoding='utf-8').read()
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = html.replace('__DATA__', payload).replace('__ACC__', json.dumps(acc, ensure_ascii=False)).replace('__TITLE__', title)
    open(out, 'w', encoding='utf-8').write(html)
    return len(html)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--meta-csv', help='元数据 CSV 文件夹（tables/columns/indexes/xxl_jobs.csv）')
    src.add_argument('--meta-mysql', help='mysql 连接配置文件（.cnf），直接连库导出元数据')
    ap.add_argument('--mysql-bin', default=os.environ.get('MYSQL_BIN', 'mysql'), help='mysql 客户端路径')
    ap.add_argument('--label', help='元数据来源的显示名，如“测试库”“生产只读库”')
    ap.add_argument('--workspace', default=os.getcwd(), help='项目工作目录（含 config/、knowledge/、runs/），默认当前目录')
    ap.add_argument('--config', help='默认 <workspace>/config/project.json')
    ap.add_argument('--knowledge', help='默认 <workspace>/knowledge')
    ap.add_argument('--repo', help='覆盖配置里的代码仓库路径（扫描另一个检出目录）')
    ap.add_argument('--code-label', help='代码不是 git 仓库时（如 git archive 导出），用来显示分支/commit，例如 "release-1.2 a1b2c3d"')
    ap.add_argument('--runs', help='默认 <workspace>/runs')
    ap.add_argument('--name', help='本次运行的目录名，默认用时间戳')
    ap.add_argument('--compare-to', help='和指定的运行目录比较，默认是 runs/LATEST（最近一次不带 --no-latest 的正式运行）')
    ap.add_argument('--no-latest', action='store_true', help='不把本次结果登记为“最新一次运行”（用于试验）')
    args = ap.parse_args()

    t0 = time.time()
    ws = os.path.abspath(args.workspace)
    args.config = args.config or os.path.join(ws, 'config', 'project.json')
    args.knowledge = args.knowledge or os.path.join(ws, 'knowledge')
    args.runs = args.runs or os.path.join(ws, 'runs')
    if not os.path.exists(args.config):
        sys.exit(f'找不到项目配置 {args.config}。新项目先运行 tools/survey.py 生成配置草稿。')
    cfg = load_json(args.config)
    if args.repo: cfg['repo'] = args.repo
    if not os.path.isabs(cfg['repo']):   # relative to the workspace, so a workspace can travel with its repo
        cfg['repo'] = os.path.normpath(os.path.join(ws, cfg['repo'])).replace(os.sep, '/')
    run_name = args.name or datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    rd = os.path.join(args.runs, run_name)
    os.makedirs(rd, exist_ok=True)
    latest_file = os.path.join(args.runs, 'LATEST')
    prev_name = args.compare_to or (open(latest_file, encoding='utf-8').read().strip() if os.path.exists(latest_file) else None)
    prev_dir = os.path.join(args.runs, prev_name) if prev_name else None
    print(f'== 运行 {run_name}，对比 {prev_name or "（无）"}')

    print('1/7 元数据')
    mdir = os.path.join(rd, 'metadata')
    if args.meta_csv:
        src_meta = metadata.copy_folder(args.meta_csv, mdir, args.label)
    else:
        src_meta = metadata.dump_mysql(args.meta_mysql, mdir, args.mysql_bin, args.label)
    meta = metadata.load_folder(mdir)
    logical = metadata.merge_logical(meta['tables'], cfg.get('metadata', {}))
    json.dump(logical, open(os.path.join(rd, 'logical_tables.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'   {len(meta["tables"])} 张物理表 → {len(logical)} 张逻辑表，来源：{src_meta["label"]}')

    print('2/7 配置自检')
    warnings = checks.check_config(cfg, logical)
    for w in warnings: print('   [警告]', w)
    gi = checks.git_info(cfg['repo'])
    if args.code_label:
        parts = args.code_label.split()
        gi = {'branch': parts[0], 'commit': parts[-1] if len(parts) > 1 else '', 'dirty': False}

    print('3/7 扫描代码', cfg['repo'], gi['branch'], gi['commit'])
    run_cfg = os.path.join(rd, 'project.json')
    json.dump(cfg, open(run_cfg, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    scan_out = os.path.join(rd, 'scan.json')
    proc = subprocess.run([sys.executable, '-P', os.path.join(HERE, 'lineage', 'scanner.py'), run_cfg,
                           os.path.join(rd, 'logical_tables.json'), scan_out], capture_output=True, text=True,
                          env=dict(os.environ, PYTHONHASHSEED='0'))
    if proc.returncode != 0:
        print(proc.stdout[-2000:], proc.stderr[-4000:]); sys.exit('扫描失败')
    print('  ', proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else '')
    scan = load_json(scan_out)
    prev_scan_stats = (load_json(os.path.join(prev_dir, 'scan_stats.json')) if prev_dir else None)
    warnings += checks.check_scan(scan, logical, prev_scan_stats)
    json.dump(scan.get('stats', {}), open(os.path.join(rd, 'scan_stats.json'), 'w'), indent=1)

    print('4/7 构建页面数据')
    cards, domains, glossary, notes, truth = load_knowledge(args.knowledge)
    page_text = load_json(os.path.join(args.knowledge, 'accuracy_notes.json'), {})
    data, fps, diag = build.build(cfg, meta, logical, scan, domains, cards)
    json.dump(fps, open(os.path.join(rd, 'fingerprints.json'), 'w', encoding='utf-8'), ensure_ascii=False)

    print('5/7 评测（标准答案）')
    results = evaluate.evaluate(cfg, scan, data, truth, fps)
    prev_eval = load_json(os.path.join(prev_dir, 'evaluation.json')) if prev_dir else None
    drops = evaluate.compare(prev_eval, results)
    json.dump(results, open(os.path.join(rd, 'evaluation.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for r in results:
        c = r['counts']
        print(f"   {r['label']}: 写入方 {c.get('rt_ok',0)}/{c.get('n',0)} Job {c.get('jobs_hit',0)}/{c.get('jobs_all',0)} "
              f"直接上游 {c.get('src_direct',0)}/{c.get('src_all',0)} 外部接口 {c.get('ext_hit',0)}/{c.get('ext_all',0)} "
              f"内部读取 {c.get('int_ok',0)}/{c.get('n',0)}" + (f"  （{len(r['stale'])} 张因代码变更未计）" if r['stale'] else ''))
    for d in drops: print('   [下降]', d)

    print('6/7 对比上次运行')
    prev_data = load_json(os.path.join(prev_dir, 'data.json')) if prev_dir else None
    diff = diff_runs(prev_data, data, prev_name)
    if diff:
        print(f"   新增 {len(diff['added'])} 张、消失 {len(diff['removed'])} 张、写入/上游变化 {len(diff['changed'])} 张、状态变化 {len(diff['status'])} 张、字段变化 {len(diff['schema'])} 张")

    print('7/7 生成页面')
    cols, rows = evaluate.acc_table(results)
    page_cfg = cfg.get('page', {})
    data['meta'] = {'title': page_cfg.get('title') or (cfg.get('project', '') + ' 库表血缘').strip(), 'repo': cfg['repo'], **gi,
                    'source': src_meta['label'], 'source_mode': src_meta['mode'], 'exported_at': src_meta['exported_at'],
                    'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'n_db': len({r['table_schema'] for r in meta['tables']}), 'n_phys': len(meta['tables']),
                    'example': page_cfg.get('example_table') or example_table(data), 'cdc_topic': cfg.get('cdc', {}).get('topic_marker') or ''}
    data['kb'] = {'domains': domains.get('descriptions', []), 'glossary': glossary}
    data['run'] = {'warnings': warnings, 'acc_drops': drops, 'diff': diff, 'unresolved': diag['unresolved_tables'][:20]}
    json.dump(data, open(os.path.join(rd, 'data.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    data['_acc'] = {'cols': cols, 'rows': rows, 'notes': notes, 'n_sets': len(truth),
                    'scan_notes': page_text.get('scan_notes', []), 'blind_spots': page_text.get('blind_spots', [])}
    page = os.path.join(rd, 'lineage.html')
    size = render(os.path.join(HERE, 'web', 'template.html'), data, data['meta']['title'], page)

    report = [f'# 运行 {run_name}', '', f"- 代码：{cfg['repo']} {gi['branch']} {gi['commit']}{'（有未提交改动）' if gi['dirty'] else ''}",
              f"- 元数据：{src_meta['label']}（{src_meta['mode']}，{src_meta['exported_at']}）", f'- 页面：{page}（{size / 1e6:.1f} MB）', '',
              '## 自检', *(f'- {w}' for w in warnings or ['无']), '', '## 准确率', *acc_md(cols, rows, len(truth)), '', *(f'- {d}' for d in drops or ['与上次相比没有下降']), '',
              '## 代码里出现、但元数据里找不到的表', *([f'- {t}（{n} 处）' for t, n in diag['unresolved_tables'][:20]] or ['- 无']), '',
              '## 待复核的口径卡片', *(f'- {k}' for k in diag['stale_cards'] or ['无']), '',
              '## 业务域为推测的报表', *(f'- {k}' for k in diag['auto_domain'] or ['无']),
              '', '## ER 核心表候选（报表最常直接取数的业务表，供挑选 er.core_tables）',
              *(f'- {k}：{n} 张报表' + ('（已在 ER 图里）' if k in cfg.get('er', {}).get('core_tables', []) else '') for k, n in core_candidates(data))]
    if diff:
        report += ['', f'## 与 {prev_name} 相比', f"- 新增：{', '.join(diff['added']) or '无'}", f"- 消失：{', '.join(diff['removed']) or '无'}",
                   f"- 写入方或直接上游变化：{', '.join(diff['changed']) or '无'}",
                   f"- 状态变化：{', '.join(f'{k}（{a or chr(8212)}→{b or chr(8212)}）' for k, a, b in diff['status']) or '无'}",
                   f"- 字段变化：{'; '.join(f'{k}（新增 {chr(44).join(ad) or chr(8212)}；删除 {chr(44).join(rm) or chr(8212)}）' for k, ad, rm in diff['schema']) or '无'}"]
    open(os.path.join(rd, 'report.md'), 'w', encoding='utf-8').write('\n'.join(report) + '\n')
    if not args.no_latest:
        open(latest_file, 'w', encoding='utf-8').write(run_name)
    print(f'完成，用时 {time.time() - t0:.0f} 秒。页面：{page}')
    print(f'报告：{os.path.join(rd, "report.md")}')
    if warnings or drops: print(f'注意：{len(warnings)} 条自检警告，{len(drops)} 项准确率下降，详见报告。')


if __name__ == '__main__':
    try:
        main()
    except metadata.MetadataError as e:
        sys.exit(f'元数据错误：{e}')
