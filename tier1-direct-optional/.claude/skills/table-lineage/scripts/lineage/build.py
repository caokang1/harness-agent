"""Merge DB metadata, scanner lineage, xxl-job schedules and curated knowledge
(domains, review cards) into the compact dataset rendered by the page."""
import re, collections

STATUS_ORDER = ['在用', '写而不读', '无实时写入·调度未启用', '无生效写入方']


def build(cfg, meta, logical, scan, domains, cards):
    """meta: {'tables','columns','indexes','xxl_jobs'} row lists; logical: merged tables; scan: scanner output.
    Returns (data, fingerprints) where fingerprints maps table key -> {code element: hash}."""
    dbc = cfg['databases']
    INFRA = set(dbc['infra'])
    REPORT_DBS = set(dbc['report'])
    REPORT_OUTSIDE = set(dbc.get('report_tables_outside', []))
    REPORT_EXCLUDE = set(dbc.get('report_exclude', []))   # config / dimension copies living in a report db
    VERIFY = set(dbc.get('verify_log_tables', []))
    EXTERNAL = set(cfg['modules']['external'])
    PKG_DB = dbc.get('mapper_package_db', {})
    MOD_DB = dbc.get('module_db', {})
    CAP = int(cfg.get('page', {}).get('readers_cap', 40))

    STR = []; SIDX = {}
    def si(s):
        if s not in SIDX: SIDX[s] = len(STR); STR.append(s)
        return SIDX[s]
    def trail(tr): return [si(x) for x in tr]

    # ---------------- tables
    tables = {}; phys2log = {}
    for e in logical:
        key = f"{e['schema']}.{e['table']}"
        tables[key] = {'db': e['schema'], 't': e['table'], 'n': e['shards'], 'c': e['comment'], 'rows': e['rows'],
                       'phys': e['names'], 'backup': e['backup']}
        for p in e['names']: phys2log[(e['schema'], p)] = key
    by_name = collections.defaultdict(list)
    for k, v in tables.items(): by_name[v['t']].append(k)

    want = {(v['db'], v['phys'][0]): k for k, v in tables.items()}
    cols = collections.defaultdict(list); idx = collections.defaultdict(dict)
    for r in meta['columns']:
        k = want.get((r['table_schema'], r['table_name']))
        if k: cols[k].append([r['column_name'], r['column_type'], 1 if r['is_nullable'] == 'YES' else 0, r['column_key'], r['column_default'] or '', r['column_comment']])
    for r in meta['indexes']:
        k = want.get((r['table_schema'], r['table_name']))
        if not k: continue
        d = idx[k].setdefault(r['index_name'], [1 if r['non_unique'] == '0' else 0, []])
        d[1].append(r['column_name'])

    def resolve_table(t, schema, tr, module):
        if schema and f'{schema}.{t}' in tables: return f'{schema}.{t}'
        if schema and (schema, t) in phys2log: return phys2log[(schema, t)]
        cands = by_name.get(t, [])
        if len(cands) == 1: return cands[0]
        db = None
        last = tr[-1] if tr else ''
        if last == 'dynamic-table' and len(tr) > 1: last = tr[-2]
        if '|' in last:
            pkg = last.split('|', 1)[1].split('.')
            for seg in reversed(pkg[:-2]):
                if seg in PKG_DB: db = PKG_DB[seg]; break
        if not db:
            mod = last.split(':')[0].split('|')[0] if last else module
            db = MOD_DB.get(mod)
        if db and f'{db}.{t}' in tables: return f'{db}.{t}'
        cands = [c for c in cands if c.split('.')[0] not in INFRA]
        return cands[0] if cands else None

    def resolve_sub(s):
        db, t = s.split('.', 1)
        if f'{db}.{t}' in tables: return f'{db}.{t}'
        if (db, t) in phys2log: return phys2log[(db, t)]
        c = by_name.get(t)
        return c[0] if c else None

    # ---------------- xxl-job
    xxl_by = collections.defaultdict(list); xxl_all = []; xxl_by_handler = collections.defaultdict(list)
    for x in meta.get('xxl_jobs', []):
        urls = re.findall(r'https?://([\w.-]+)(?::\d+)?(/[^,\s?]*)', x['executor_param'] or '')
        rec = {'id': x['id'], 'desc': x['job_desc'], 'handler': x['executor_handler'], 'cron': x['schedule_conf'],
               'on': x['trigger_status'] == '1', 'urls': [f'{h}{p}' for h, p in urls]}
        xxl_all.append(rec)
        if x['executor_handler']: xxl_by_handler[x['executor_handler']].append(len(xxl_all) - 1)
        for host, path in urls:
            xxl_by[(host, path.rstrip('/'))].append(len(xxl_all) - 1)

    def xxl_of(e):
        """xxl-job tasks that trigger an entry: by URL for HTTP entries, by handler name for @XxlJob methods."""
        if e['kind'] == 'http': return xxl_by.get((e['module'], (e.get('path') or '').rstrip('/')), [])
        if e['kind'] == 'sched' and e.get('handler'): return xxl_by_handler.get(e['handler'], [])
        return []

    # ---------------- entries
    ents = []
    unresolved = collections.Counter()
    for e in scan['entries']:
        eff = []
        for x in e['tables']:
            key = resolve_table(x['table'], x['schema'], x['trail'], e['module'])
            if key: eff.append((x['op'], key, x['via'], x['trail']))
            else: unresolved[x['table']] += 1
        ents.append({'raw': e, 'eff': eff, 'subs': {resolve_sub(s) for s in e['subs']} - {None},
                     'fwd': {resolve_sub(s) for s in e.get('subs_forwarded', [])} - {None}})

    service_api = set()
    for x in ents:
        if x['raw']['module'] in EXTERNAL:
            for f in x['raw']['feign']: service_api.add(f['target'])
    def sid(e): return f"{e['module']}:{e['name']}:{e['line']}"

    used_entries = {}
    def eref(i):
        if i not in used_entries: used_entries[i] = len(used_entries)
        return used_entries[i]

    def feign_hop(tr, module):
        for t in tr:
            if ':' in t and '|' not in t and t.split(':')[0] != module:
                return t
        return None

    RANK = {'canal': 0, 'forward': 1, 'sql': 2, 'feign': 3, 'feign_deep': 4}
    def put_src(d, k, rec):
        if k not in d or RANK[rec[0]] < RANK[d[k][0]]: d[k] = rec
    info = {k: {'w': [], 'clean': [], 'src': {}, 'down': set(), 'ext': {}, 'int': {}, 'verify': {}} for k in tables}
    def is_verify(x):
        e = x['raw']
        w = {k for op, k, via, tr in x['eff'] if op == 'W'}
        return bool(re.search(r'(?i)verify|check', e['name'] + ' ' + (e.get('path') or ''))) or (w and w <= VERIFY)
    feign_paths = {}
    for x in ents:
        for f in x['raw']['feign']: feign_paths[f['target']] = (f['path'], f['module'])

    for i, x in enumerate(ents):
        e = x['raw']; kind = e['kind']
        W = {k for op, k, via, tr in x['eff'] if op == 'W' and via == 'local'}
        Wany = {k for op, k, via, tr in x['eff'] if op in ('W', 'D')}
        D = {k for op, k, via, tr in x['eff'] if op == 'D' and via == 'local'} - W
        R_local = {k for op, k, via, tr in x['eff'] if op == 'R' and via == 'local'}
        for key in D:
            info[key]['clean'].append(i)
        for key in W:
            tr = next(tr for op, k2, via, tr in x['eff'] if op == 'W' and k2 == key and via == 'local')
            info[key]['w'].append((i, tr))
            if kind == 'kafka_off': continue
            for s in x['subs']:
                if s != key: put_src(info[key]['src'], s, ('forward' if s in x['fwd'] else 'canal', i, None, []))
            shallow_all = set().union(*e.get('feign_shallow', {}).values()) if e.get('feign_shallow') else set()
            on_path = {v.split('|')[0] for v in e.get('psrc', {}).get(key.split('.', 1)[1], [])}
            for op, k2, via, tr2 in x['eff']:
                if op != 'R' or k2 == key or k2 in VERIFY: continue
                if k2 in W and k2.split('.', 1)[1] not in on_path: continue
                if via == 'local':
                    put_src(info[key]['src'], k2, ('sql', i, None, tr2))
                else:
                    hop = feign_hop(tr2, e['module'])
                    api = feign_paths.get(hop, ('', ''))[0] if hop else ''
                    tier = 'feign' if k2.split('.', 1)[1] in shallow_all else 'feign_deep'
                    put_src(info[key]['src'], k2, (tier, i, (hop.split(':')[0] if hop else '') + ' ' + (api or ''), tr2))
            if key not in VERIFY:
                for s in (x['subs'] | R_local) - {key}:
                    info[s]['down'].add(key)
        if kind == 'kafka_off': continue
        for op, key, via, tr in x['eff']:
            if op != 'R' or key in Wany: continue
            if e['module'] in EXTERNAL and kind == 'http':
                info[key]['ext'].setdefault(i, tr)
            elif sid(e) not in service_api:
                (info[key]['verify'] if is_verify(x) else info[key]['int']).setdefault(i, tr)
        for s in x['subs']:
            if s not in Wany: info[s]['int'].setdefault(i, [])

    # ---------------- code fingerprints per table (everything on its live write paths)
    fpm = scan.get('fp', {})
    def elem_key(s):
        return s if '|' in s else s.rsplit(':', 1)[0]
    dw = scan.get('direct_writers', {})
    fingerprints = {}
    for key in tables:
        d = {}
        names = set(dw.get(tables[key]['t'], []))
        for j, tr in info[key]['w']:
            if ents[j]['raw']['kind'] != 'kafka_off': names.add(tr[0])
        for s in names:
            k2 = elem_key(s)
            if k2 in fpm: d[k2] = fpm[k2]
        fingerprints[key] = d

    # ---------------- classification and domains
    t2dom = {t: d for d, ts in domains['domains'].items() for t in ts}
    t2grp = {t: g for g, ts in domains.get('reviewed_groups', {}).items() for t in ts}
    rules = [(re.compile(rx, re.I), d) for rx, d in domains.get('rules', [])]
    code = scan['code']
    kinds = {}
    for key, v in tables.items():
        i = info[key]
        tc = code.get(v['t'], {'entities': [], 'mappers': []})
        has_ref = bool(tc['entities'] or tc['mappers'] or i['w'] or i['ext'] or i['int'])
        if v['db'] in INFRA: kind = '基础设施'
        elif v['backup']: kind = '备份/临时'
        elif (v['db'] in REPORT_DBS or key in REPORT_OUTSIDE) and key not in REPORT_EXCLUDE:
            stat_down = [d for d in i['down'] if d.split('.')[0] in REPORT_DBS and d not in VERIFY]
            kind = '中间表' if stat_down else '报表'
        elif not has_ref: kind = '代码无引用'
        else: kind = '业务底表'
        kinds[key] = kind

    def auto_domain(key):
        """Domain guess for a report table missing from domains.json: neighbours first, then name rules."""
        votes = collections.Counter()
        for s in list(info[key]['src']) + sorted(info[key]['down']):
            t = tables.get(s, {}).get('t')
            if t in t2dom and t2dom[t] != '未归类': votes[t2dom[t]] += 1
        if votes: return votes.most_common(1)[0][0]
        for rx, d in rules:
            if rx.search(tables[key]['t']) or rx.search(tables[key]['c'] or ''): return d
        return '未归类'

    out = []
    stale_cards = []
    for key, v in tables.items():
        i = info[key]; kind = kinds[key]
        ent_kind = lambda j: ents[j]['raw']['kind']
        live_rt = [j for j, _ in i['w'] if ent_kind(j) == 'kafka']
        jobs = [j for j, _ in i['w'] if ent_kind(j) in ('http', 'sched')]
        tc = code.get(v['t'], {'entities': [], 'mappers': []})
        status = ''
        if kind in ('报表', '中间表'):
            sched_on = any(xxl_all[n]['on'] for j in jobs for n in xxl_of(ents[j]['raw']))
            readers = bool(i['ext'] or i['int'] or i['down'])
            if all(ent_kind(j) == 'kafka_off' for j, _ in i['w']): status = '无生效写入方'
            elif not live_rt and not sched_on: status = '无实时写入·调度未启用'
            elif not readers: status = '写而不读'
            else: status = '在用'
        dom_auto = False
        if kind in ('报表', '中间表'):
            domain = t2dom.get(v['t'])
            if not domain: domain = auto_domain(key); dom_auto = True
        else:
            domain = dbc.get('business_db_labels', {}).get(v['db'], '基础设施' if v['db'] in INFRA else v['db'])
        if kind in ('代码无引用', '备份/临时') and v['db'] in REPORT_DBS: domain = t2dom.get(v['t'], '未归类')
        ext_items = sorted(i['ext'].items())[:CAP]; int_items = sorted(i['int'].items())[:CAP]
        rec = {'k': key, 'db': v['db'], 't': v['t'], 'n': v['n'], 'c': v['c'], 'rows': v['rows'], 'kind': kind, 'st': status,
               'dom': domain or '未归类', 'grp': t2grp.get(v['t'], '') if kind in ('报表', '中间表') else '',
               'cols': cols.get(key, []), 'idx': idx.get(key, {}),
               'w': [[eref(j), trail(tr)] for j, tr in i['w']],
               'clean': [eref(j) for j in i['clean']][:CAP],
               'src': [[k2, s[0], eref(s[1]), s[2] or '', trail(s[3][:8])] for k2, s in sorted(i['src'].items())],
               'down': sorted(i['down']),
               'ext': [[eref(j), trail(tr)] for j, tr in ext_items], 'next': len(i['ext']),
               'int': [[eref(j), trail(tr)] for j, tr in int_items], 'nint': len(i['int']),
               'ver': [eref(j) for j in sorted(i['verify'])[:CAP]],
               'code': {'e': tc['entities'][:6], 'm': [[m['mapper'], m['method'], m['op'], m['loc']] for m in tc['mappers'][:30]], 'nm': len(tc['mappers'])}}
        if dom_auto: rec['dom_auto'] = 1
        card = cards.get(v['t'])
        if card and kind in ('报表', '中间表'):
            c = {k2: card[k2] for k2 in ('role', 'grain', 'metric', 'use', 'risks')}
            changed = code_changes(card.get('fp'), fingerprints[key])
            if changed:
                c['stale'] = changed
                stale_cards.append(key)
            if card.get('reviewed_at'): c['at'] = card['reviewed_at']
            rec['card'] = c
        out.append(rec)

    # ---------------- ER: core business tables, joins from code + naming inference
    erc = cfg.get('er', {})
    CORE = [c for c in erc.get('core_tables', []) if c in tables]
    core_names = {tables[c]['t']: c for c in CORE}
    colset = {k: {c[0] for c in cols.get(k, [])} for k in CORE}
    indexed = {k: {cs[0] for cs in [v[1] for v in idx.get(k, {}).values()]} for k in CORE}
    rels = {}
    for j in scan['joins']:
        (ta, ca), (tb, cb) = j['a'], j['b']
        if ta in core_names and tb in core_names:
            a, b = core_names[ta], core_names[tb]
            if ca in colset[a] and cb in colset[b]:
                rels[(a, ca, b, cb)] = {'kind': 'code', 'ev': j['evidence'], 'n': j['n']}
    ALIAS = erc.get('column_alias', {}); MCOL = erc.get('tenant_column'); MTAB = erc.get('tenant_table')
    for a in CORE:
        for c in colset[a]:
            target = ALIAS.get(c)
            if not target and c.endswith('_id'): target = c[:-3]
            if MCOL and c == MCOL and tables[a]['t'] != MTAB: target = MTAB
            if not target or target not in core_names: continue
            b = core_names[target]
            if b == a: continue
            tcol = MCOL if c == MCOL else 'id'
            if tcol not in colset[b]: continue
            if any((x[0], x[2]) in ((a, b), (b, a)) and (x[1] == c or x[3] == c) for x in rels): continue
            rels[(a, c, b, tcol)] = {'kind': 'name', 'idx': c in indexed[a]}
    er = {'tables': [{'k': k, 'cols': [c[:2] + [c[3], c[5]] for c in cols.get(k, [])]} for k in CORE],
          'rels': [{'a': a, 'ca': ca, 'b': b, 'cb': cb, **v} for (a, ca, b, cb), v in rels.items()],
          'db_order': erc.get('db_order', []), 'tenant_column': MCOL or ''}

    # ---------------- endpoint -> tables read, job -> tables written
    eps = collections.defaultdict(set); jobs_ix = collections.defaultdict(set)
    for i, x in enumerate(ents):
        e = x['raw']
        if e['kind'] == 'kafka_off': continue
        W = {k for op, k, via, tr in x['eff'] if op in ('W', 'D')}
        if e['module'] in EXTERNAL and e['kind'] == 'http':
            R = {k for op, k, via, tr in x['eff'] if op == 'R'} - W
            if R: eps[i] |= R
        Wl = {k for op, k, via, tr in x['eff'] if op == 'W' and via == 'local'}
        if Wl and e['kind'] in ('http', 'sched') and e['module'] not in EXTERNAL:
            jobs_ix[i] |= Wl
    EPS = [[eref(i), sorted(v)] for i, v in eps.items()]
    JOBS = [[eref(i), sorted(v)] for i, v in jobs_ix.items()]
    E = [None] * len(used_entries)
    for i, pos in used_entries.items():
        e = ents[i]['raw']
        xx = [xxl_all[n] for n in xxl_of(e)]
        E[pos] = {'kind': e['kind'], 'm': e['module'], 'n': e['name'], 'loc': f"{e['file']}:{e['line']}",
                  'g': e.get('group', ''), 'p': e.get('path') or e.get('handler') or '', 'topic': e.get('topic_res', ''),
                  'cond': e.get('cond') or [], 'xxl': [[q['id'], q['desc'], q['cron'], q['on']] for q in xx]}
    known_http = {(x['raw']['module'], (x['raw'].get('path') or '').rstrip('/')) for x in ents}
    known_handlers = {x['raw'].get('handler') for x in ents if x['raw']['kind'] == 'sched'} - {None, ''}
    xxl_unmatched = [q for q in xxl_all if q['handler'] not in known_handlers and not any(
        (u.split('/')[0], '/' + u.split('/', 1)[1].rstrip('/') if '/' in u else '') in known_http for u in q['urls'])][:80]
    # ---------------- overview flow: which modules write business / report tables, derived from the scan
    writers = collections.defaultdict(collections.Counter)
    for x in ents:
        e = x['raw']
        if e['kind'] == 'kafka_off': continue
        for op, key, via, tr in x['eff']:
            if op != 'W' or via != 'local': continue
            if kinds[key] in ('报表', '中间表'): writers['rt' if e['kind'] == 'kafka' else 'job'][e['module']] += 1
            elif kinds[key] == '业务底表': writers['biz'][e['module']] += 1
    biz_db = collections.Counter(v['db'] for k, v in tables.items() if kinds[k] == '业务底表')
    top = lambda c, n: [k for k, _ in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]
    flow = {'biz': top(writers['biz'], 6), 'biz_db': top(biz_db, 4), 'rt': top(writers['rt'], 4), 'job': top(writers['job'], 4),
            'report_db': sorted(REPORT_DBS), 'ext': sorted(EXTERNAL), 'xxl': bool(xxl_all),
            'cdc': any(s[1] in ('canal', 'forward') for r in out for s in r['src'])}
    data = {'tables': out, 'entries': E, 'eps': EPS, 'jobs': JOBS, 'S': STR, 'er': er, 'xxl_unmatched': xxl_unmatched, 'flow': flow}
    diag = {'unresolved_tables': unresolved.most_common(30), 'stale_cards': stale_cards,
            'auto_domain': [r['k'] for r in out if r.get('dom_auto')]}
    return data, fingerprints, diag


def code_changes(old, new):
    """List of human-readable code changes between a stored fingerprint and the current one.
    None old means the card predates fingerprinting: nothing to compare."""
    if not old: return []
    out = []
    for k in sorted(set(old) | set(new)):
        if k not in new: out.append(['删除', k])
        elif k not in old: out.append(['新增', k])
        elif old[k] != new[k]: out.append(['修改', k])
    return out
