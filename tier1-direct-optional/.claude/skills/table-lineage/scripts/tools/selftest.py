"""Self-test for the tool itself. Run after changing any code under lineage/ or web/:

    python tools/selftest.py                                   # on the bundled demo project
    python tools/selftest.py --workspace W --meta-csv M        # on a real project workspace (compares with W/runs/LATEST)

Checks:
  1. mysql --batch unescaping
  2. determinism: two runs on the same inputs produce byte-identical page data
  3. no regression: accuracy on every ground-truth set is not lower than the baseline
  4. direct-mysql mode (through a fake mysql client) produces exactly the same metadata and page data as CSV mode
     and CSV headers are case-insensitive (UPPERCASE GUI exports give the same page data)
  5. (demo only) a code change on a reviewed table marks its card and ground truth as stale
"""
import argparse, csv, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(os.path.dirname(HERE), 'assets', 'demo')
sys.path.insert(0, HERE)
from lineage.metadata import unescape_batch  # noqa: E402
from lineage.evaluate import PAIRS, rate  # noqa: E402


def run(ws, tmp, name, *extra, env=None):
    cmd = [sys.executable, '-P', os.path.join(HERE, 'run.py'), '--workspace', ws, '--runs', tmp, '--name', name, '--no-latest', *extra]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        print(p.stdout[-3000:], p.stderr[-3000:])
        raise SystemExit(f'运行 {name} 失败')
    return os.path.join(tmp, name)


def core(d):
    data = json.load(open(os.path.join(d, 'data.json'), encoding='utf-8'))
    data.pop('meta', None); data.pop('run', None)
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def unescape_ok():
    bs = chr(92)
    cases = [('a' + bs + 'nb', 'a\nb'), ('x' + bs + bs + 'ty', 'x' + bs + 'ty'), ('tab' + bs + 't', 'tab\t'), ('plain', 'plain')]
    return all(unescape_batch(a) == b for a, b in cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', default=os.path.join(DEMO, 'workspace'))
    ap.add_argument('--meta-csv', default=os.path.join(DEMO, 'metadata'))
    args = ap.parse_args()
    ws = os.path.abspath(args.workspace)
    demo = os.path.normcase(ws) == os.path.normcase(os.path.abspath(os.path.join(DEMO, 'workspace')))
    tmp = tempfile.mkdtemp(prefix='lineage-selftest-')
    results = []
    results.append(('mysql 批量输出反转义', unescape_ok(), ''))

    a = run(ws, tmp, 's1', '--meta-csv', args.meta_csv, '--label', 'selftest')
    b = run(ws, tmp, 's2', '--meta-csv', args.meta_csv, '--label', 'selftest')
    results.append(('两次运行结果逐字节一致', core(a) == core(b), ''))

    latest = os.path.join(ws, 'runs', 'LATEST')
    if demo:
        base, base_name = json.load(open(os.path.join(DEMO, 'expected_evaluation.json'), encoding='utf-8')), '示例项目的预期成绩'
    elif os.path.exists(latest):
        name = open(latest, encoding='utf-8').read().strip()
        base, base_name = json.load(open(os.path.join(ws, 'runs', name, 'evaluation.json'), encoding='utf-8')), f'正式运行 {name}'
    else:
        base, base_name = [], '（没有基线，跳过）'
    cur = {r['set']: r['counts'] for r in json.load(open(os.path.join(a, 'evaluation.json'), encoding='utf-8'))}
    drops = []
    for r in base:
        c = cur.get(r['set'], {})
        for x, y in PAIRS:
            if rate(c, x, y) < rate(r['counts'], x, y) - 1e-9:
                drops.append(f"{r.get('label', r['set'])} {x}: {rate(r['counts'], x, y):.1%} → {rate(c, x, y):.1%}")
    results.append((f'准确率不低于{base_name}', not drops, '; '.join(drops)))

    cnf = os.path.join(tmp, 'fake.cnf')
    open(cnf, 'w').write('[client]\nhost=fake-host\nuser=x\npassword=y\n')
    env = dict(os.environ, FAKE_MYSQL_DIR=os.path.abspath(args.meta_csv))
    fake = f'"{sys.executable}" -P "{os.path.join(HERE, "tools", "fake_mysql.py")}"'
    m = run(ws, tmp, 's3', '--meta-mysql', cnf, '--mysql-bin', fake, '--label', 'selftest', env=env)
    same_meta = all(list(csv.reader(open(os.path.join(a, 'metadata', n + '.csv'), encoding='utf-8', newline=''))) ==
                    list(csv.reader(open(os.path.join(m, 'metadata', n + '.csv'), encoding='utf-8', newline='')))
                    for n in ('tables', 'columns', 'indexes', 'xxl_jobs'))
    results.append(('直连模式与 CSV 模式元数据一致', same_meta, ''))
    results.append(('直连模式与 CSV 模式页面数据一致', core(a) == core(m), ''))

    # GUI exports (Navicat/DBeaver) of sql/export_metadata.sql write UPPERCASE headers, often with a BOM
    upper = os.path.join(tmp, 'meta-upper')
    shutil.copytree(args.meta_csv, upper)
    for n in os.listdir(upper):
        if n.endswith('.csv'):
            p = os.path.join(upper, n)
            head, sep, rest = open(p, encoding='utf-8-sig', newline='').read().partition('\n')
            open(p, 'w', encoding='utf-8-sig', newline='').write(head.upper() + sep + rest)
    u = run(ws, tmp, 's5', '--meta-csv', upper, '--label', 'selftest')
    results.append(('大写表头的 CSV 与小写表头结果一致', core(a) == core(u), ''))

    if demo:
        repo2 = os.path.join(tmp, 'repo-changed')
        shutil.copytree(os.path.join(DEMO, 'repo'), repo2)
        svc = os.path.join(repo2, 'report-service', 'src', 'main', 'java', 'com', 'example', 'shop', 'report', 'service', 'DailySalesService.java')
        text = open(svc, encoding='utf-8').read()
        open(svc, 'w', encoding='utf-8', newline='\n').write(text.replace('i.getPrice() * i.getQty()', 'i.getPrice()'))
        c = run(ws, tmp, 's4', '--meta-csv', args.meta_csv, '--repo', repo2, '--code-label', 'changed x')
        d = json.load(open(os.path.join(c, 'data.json'), encoding='utf-8'))
        stale = sorted(t['t'] for t in d['tables'] if t.get('card', {}).get('stale'))
        ev = json.load(open(os.path.join(c, 'evaluation.json'), encoding='utf-8'))
        ok = stale == ['daily_sales'] and ev[0]['stale'] == ['daily_sales']
        results.append(('改动写入代码后，对应卡片和标准答案被标为待复核', ok, f'卡片 {stale}，标准答案 {ev[0]["stale"]}'))

    ok = True
    for name, passed, detail in results:
        print(('PASS ' if passed else 'FAIL ') + name + (f'  {detail}' if detail and not passed else ''))
        ok &= passed
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
