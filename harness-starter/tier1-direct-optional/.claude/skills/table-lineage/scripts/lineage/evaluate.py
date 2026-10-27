"""Score a run against the curated ground-truth sets (knowledge/truth/*.json).

Writer / job / external-reader / internal-reader facts are scored on the raw scanner output;
upstream tables are scored on the page dataset, i.e. exactly what users see.
Truth entries whose code fingerprint changed since they were reviewed are excluded and listed."""
import collections
from .build import code_changes


def _facts_index(scan, external):
    service_api = set()
    for e in scan['entries']:
        if e['module'] in external:
            for fg in e['feign']: service_api.add(fg['target'])
    by_table = collections.defaultdict(list)
    for e in scan['entries']:
        for t in {x['table'] for x in e['tables']} | {s.split('.')[-1] for s in e['subs']}:
            by_table[t].append(e)
    return service_api, by_table


def facts(t, by_table, service_api, external):
    f = {'rt': [], 'jobs': set(), 'ext': set(), 'int': []}
    for e in by_table.get(t, []):
        ws = [x for x in e['tables'] if x['table'] == t and x['op'] == 'W' and x['via'] == 'local']
        rs = [x for x in e['tables'] if x['table'] == t and x['op'] == 'R']
        if ws:
            if e['kind'] == 'kafka': f['rt'].append(e['name'])
            elif e['kind'] == 'http': f['jobs'].add(e['path'])
            elif e['kind'] == 'sched': f['jobs'].add(e.get('handler') or e['name'])
        if rs and e['module'] in external and e['kind'] == 'http':
            f['ext'].add(e['path'])
        any_w = any(x['table'] == t and x['op'] == 'W' for x in e['tables'])
        sid = f"{e['module']}:{e['name']}:{e['line']}"
        if (rs and not any_w and e['module'] not in external and sid not in service_api) or \
                (e['kind'] == 'kafka' and any(s.split('.')[-1] == t for s in e['subs'])):
            f['int'].append(e['name'])
    return f


def _sfx(found, want):
    return any(p.lower().endswith(want.lower()) for p in found)


def evaluate(cfg, scan, data, truth_sets, fingerprints):
    external = set(cfg['modules']['external'])
    service_api, by_table = _facts_index(scan, external)
    page = collections.defaultdict(list)
    for t in data['tables']:
        page[t['t']].append(t)
    keys_by_name = collections.defaultdict(list)
    for k in fingerprints:
        keys_by_name[k.split('.', 1)[1]].append(k)
    results = []
    for name, ts in truth_sets:
        meta = ts.get('_meta', {})
        excl = meta.get('src_exclude', {})
        c = collections.Counter(); stale = []; misses = []
        for t, g in ts.items():
            if t.startswith('_'): continue
            cand = [x for x in page.get(t, []) if x['kind'] in ('报表', '中间表')] or page.get(t, [])
            key = cand[0]['k'] if cand else (keys_by_name.get(t) or [None])[0]
            if g.get('fp') and key and code_changes(g['fp'], fingerprints.get(key, {})):
                stale.append(t); continue
            c['n'] += 1
            f = facts(t, by_table, service_api, external)
            c['rt_ok'] += bool(f['rt']) == g['rt']
            c['int_ok'] += bool(f['int']) == g['int']
            jh = [j for j in g['jobs'] if _sfx(f['jobs'], j)]
            c['jobs_hit'] += len(jh); c['jobs_all'] += len(g['jobs'])
            eh = [p for p in g['ext'] if _sfx(f['ext'], p)]
            c['ext_hit'] += len(eh); c['ext_all'] += len(g['ext'])
            src = [s for s in g['src'] if s not in excl.get(t, [])]
            src_f = [s for s in g.get('src_feign', []) if s not in excl.get(t, [])]   # upstream read through another service
            direct = feign = set()
            if cand:
                x = cand[0]
                direct = {s[0].split('.', 1)[1] for s in x['src'] if s[1] in ('canal', 'forward', 'sql')}
                feign = {s[0].split('.', 1)[1] for s in x['src'] if s[1] == 'feign'}
            c['src_all'] += len(src); c['src_any_all'] += len(src) + len(src_f)
            c['src_direct'] += sum(1 for s in src if s in direct)
            c['src_any'] += sum(1 for s in src + src_f if s in direct | feign)
            extra = []
            if (src or src_f) and (meta.get('precision') or g.get('src_complete')):
                extra = sorted(direct - set(src) - set(src_f))
                c['p_found'] += len(direct); c['p_extra'] += len(extra)
            miss = {'table': t}
            if bool(f['rt']) != g['rt']: miss['rt'] = g['rt']
            if bool(f['int']) != g['int']: miss['int'] = g['int']
            if len(jh) < len(g['jobs']): miss['jobs'] = [j for j in g['jobs'] if j not in jh]
            if len(eh) < len(g['ext']): miss['ext'] = [p for p in g['ext'] if p not in eh]
            lost = [s for s in src + src_f if s not in direct | feign]
            if lost: miss['src'] = lost
            via_feign = [s for s in src if s not in direct and s in feign]
            if via_feign: miss['src_found_via_feign'] = via_feign
            if extra: miss['src_extra'] = extra
            if len(miss) > 1: misses.append(miss)
        results.append({'set': name, 'label': meta.get('label', name), 'kind': meta.get('kind', ''), 'commit': meta.get('commit', ''),
                        'counts': dict(c), 'stale': stale, 'misses': misses})
    return results


PAIRS = [('rt_ok', 'n'), ('jobs_hit', 'jobs_all'), ('src_direct', 'src_all'), ('src_any', 'src_any_all'), ('ext_hit', 'ext_all'), ('int_ok', 'n')]


def acc_table(results):
    """Rows for the page's accuracy table, computed from this run's evaluation."""
    fr = lambda a, b: f'{a}/{b}' if b else '—'
    cols = [f"{r['label']}<br><span class=\"faint\">{'调教集' if r['kind'] == 'tuned' else '独立核对'}{'，' + str(len(r['stale'])) + ' 张因代码变更未计' if r['stale'] else ''}</span>" for r in results]
    rows = [
        ['是否有实时写入方'] + [fr(r['counts'].get('rt_ok', 0), r['counts'].get('n', 0)) for r in results],
        ['Job / 接口写入入口'] + [fr(r['counts'].get('jobs_hit', 0), r['counts'].get('jobs_all', 0)) for r in results],
        ['直接上游（召回）'] + [fr(r['counts'].get('src_direct', 0), r['counts'].get('src_all', 0)) for r in results],
        ['直接上游（精确率）'] + [(f"{1 - r['counts']['p_extra'] / r['counts']['p_found']:.0%}" if r['counts'].get('p_found') else '—') for r in results],
        ['直接 + 经 Feign 接口上游（召回）'] + [fr(r['counts'].get('src_any', 0), any_den(r['counts'])) for r in results],
        ['外部查询接口'] + [fr(r['counts'].get('ext_hit', 0), r['counts'].get('ext_all', 0)) for r in results],
        ['内部读取方'] + [fr(r['counts'].get('int_ok', 0), r['counts'].get('n', 0)) for r in results],
    ]
    return cols, rows


def any_den(c):
    # older evaluations have no src_any_all: their truth had no src_feign, so the denominator was src_all
    return c.get('src_any_all', c.get('src_all', 0))


def rate(c, a, b):
    return c.get(a, 0) / max(1, any_den(c) if b == 'src_any_all' else c.get(b, 0))


def compare(prev, cur):
    """Metric deltas versus the previous run (same set names)."""
    if not prev: return []
    pm = {r['set']: r['counts'] for r in prev}
    out = []
    pairs = PAIRS
    labels = {'rt_ok': '实时写入方', 'jobs_hit': 'Job 入口', 'src_direct': '直接上游', 'src_any': '直接+Feign 上游', 'ext_hit': '外部接口', 'int_ok': '内部读取方'}
    for r in cur:
        p = pm.get(r['set'])
        if not p: continue
        for a, b in pairs:
            new, old = rate(r['counts'], a, b), rate(p, a, b)
            if new < old - 0.005:
                out.append(f"{r['label']}：{labels[a]} 从 {old:.1%} 降到 {new:.1%}")
    return out
