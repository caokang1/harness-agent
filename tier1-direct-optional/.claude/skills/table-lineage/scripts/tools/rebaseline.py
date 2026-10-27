"""Stamp code fingerprints from a run into review cards and ground-truth entries.

Run this right after a human has (re)reviewed cards or truth entries against the code of that run:
    python tools/rebaseline.py runs/<run> --workspace <ws> [--tables t1,t2] [--force] [--reviewed-at 2025-01-02]
Without --force only entries that have no fingerprint yet are stamped, so earlier baselines
(and the "code changed, needs review" signal they produce) are never silently overwritten.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--workspace', default=os.getcwd(), help='项目工作目录，默认当前目录')
    ap.add_argument('--knowledge', help='默认 <workspace>/knowledge')
    ap.add_argument('--tables', help='只给这些表盖章（逗号分隔表名）；默认全部')
    ap.add_argument('--force', action='store_true', help='覆盖已有指纹（确认已重新核对过才用）')
    ap.add_argument('--reviewed-at', help='核对日期，默认取运行的生成日期')
    args = ap.parse_args()
    args.knowledge = args.knowledge or os.path.join(os.path.abspath(args.workspace), 'knowledge')

    data = json.load(open(os.path.join(args.run_dir, 'data.json'), encoding='utf-8'))
    fps = json.load(open(os.path.join(args.run_dir, 'fingerprints.json'), encoding='utf-8'))
    commit = data.get('meta', {}).get('commit', '')
    when = args.reviewed_at or data.get('meta', {}).get('generated_at', '')[:10]
    only = set(args.tables.split(',')) if args.tables else None
    key_of = {}
    for t in data['tables']:
        if t['kind'] in ('报表', '中间表') or t['t'] not in key_of:
            key_of.setdefault(t['t'], t['k'])
            if t['kind'] in ('报表', '中间表'): key_of[t['t']] = t['k']

    def stamp(entry, name):
        if only and name not in only: return False
        if entry.get('fp') and not args.force: return False
        k = key_of.get(name)
        if not k: return False
        entry['fp'] = fps.get(k, {}); entry['commit'] = commit; entry['reviewed_at'] = when
        return True

    cp = os.path.join(args.knowledge, 'cards.json')
    cards = json.load(open(cp, encoding='utf-8'))
    n = sum(stamp(v, k) for k, v in cards.items() if not k.startswith('_'))
    json.dump(cards, open(cp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'卡片：盖章 {n} 张')
    tdir = os.path.join(args.knowledge, 'truth')
    for f in sorted(x for x in os.listdir(tdir) if x.endswith('.json') and os.path.isfile(os.path.join(tdir, x))):
        p = os.path.join(tdir, f)
        ts = json.load(open(p, encoding='utf-8'))
        n = sum(stamp(v, k) for k, v in ts.items() if not k.startswith('_'))
        json.dump(ts, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'标准答案 {f}：盖章 {n} 条')


if __name__ == '__main__':
    sys.exit(main())
