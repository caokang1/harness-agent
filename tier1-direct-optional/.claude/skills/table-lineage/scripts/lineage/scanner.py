"""Method-level lineage scanner for a Java / MyBatis code base.

Builds a per-method call graph across all modules, resolves calls through injected fields,
locals, params, interface implementations and Feign clients, and attributes table effects
(read/write) from MyBatis annotation SQL, mapper XML and MyBatis-Plus builtin methods.
Outputs entry points (Kafka listeners, HTTP endpoints, scheduled jobs) with their reachable
table effects and an example call trail for each effect.
"""
import os, re, sys, json, collections, hashlib

# usage: scanner.py <project.json> <logical_tables.json> <out.json>
CFG = json.load(open(sys.argv[1], encoding='utf-8'))
ROOT = CFG['repo']
OUT = sys.argv[3]
KNOWN_TABLES = {e['table'] for e in json.load(open(sys.argv[2], encoding='utf-8'))}
SKIP_DIRS = set(CFG['scan']['skip_dirs'])
EXTERNAL_MODULES = set(CFG['modules']['external'])
SHALLOW_LEVELS = int(CFG['scan'].get('feign_shallow_levels', 3))
SHARED_MODULES = tuple(CFG['modules'].get('shared', []))
SHARED_PREFIX = CFG['modules'].get('shared_prefix') or None
# Change-data-capture conventions (optional): how the code declares which db.table a listener subscribes to.
CDC = CFG.get('cdc') or {}
CDC_TYPE = CDC.get('table_ref_type')        # class built as  Type("db", "table")  inside  List<Type> NAME = ...
CDC_REGISTRY = CDC.get('registry_class')    # class holding the shared subscription lists, referenced as Registry.NAME
CDC_CHECK = CDC.get('check_method')         # method called with a subscription list, e.g. matches(NAME)
CDC_TOPIC = CDC.get('topic_marker')         # substring of the topic expression of listeners fed directly by CDC
ROUTE_TYPE = CDC.get('route_rule_type')     # class built as  Type("db", "table", ...TOPIC...)  routing a table to an internal topic
SCHED_BASE = (CFG.get('scheduler') or {}).get('handler_base') or {}   # in-house job base class: {method, class_prefix, class_suffix}

# ---------------------------------------------------------------- lexing helpers
def strip_comments(s):
    """Remove // and /* */ comments while keeping string/char literals intact (same length not required)."""
    out = []; i = 0; n = len(s)
    while i < n:
        c = s[i]
        if c == '"' or c == "'":
            j = i + 1
            if s.startswith('"""', i):
                j = s.find('"""', i + 3); j = n if j < 0 else j + 3
                out.append(s[i:j]); i = j; continue
            while j < n and s[j] != c and s[j] != '\n':
                j += 2 if s[j] == '\\' else 1
            out.append(s[i:j + 1]); i = j + 1
        elif s.startswith('//', i):
            j = s.find('\n', i); j = n if j < 0 else j
            out.append(' ' * (j - i)); i = j
        elif s.startswith('/*', i):
            j = s.find('*/', i + 2); j = n if j < 0 else j + 2
            out.append(re.sub(r'[^\n]', ' ', s[i:j])); i = j
        else:
            out.append(c); i += 1
    return ''.join(out)

def blank_strings(s):
    """Replace string/char literal contents with spaces, preserving offsets."""
    out = list(s); i = 0; n = len(s)
    while i < n:
        c = s[i]
        if c == '"' or c == "'":
            j = i + 1
            while j < n and s[j] != c and s[j] != '\n':
                j += 2 if s[j] == '\\' else 1
            for k in range(i + 1, min(j, n)):
                if out[k] != '\n': out[k] = ' '
            i = j + 1
        else:
            i += 1
    return ''.join(out)

STR_LIT = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
def string_concat(s):
    return ' '.join(m.group(1).replace('\\"', '"').replace('\\n', ' ') for m in STR_LIT.finditer(s))

# ---------------------------------------------------------------- SQL table extraction
SQL_STOP = {'dual', 'select', 'where', 'set', 'if', 'foreach', 'trim', 'choose', 'the', 'table', 'values', 'value',
            'and', 'or', 'on', 'as', 'when', 'case', 'then', 'else', 'end', 'null', 'not', 'exists', 'in', 'into'}
WRITE_RX = re.compile(r'\b(?:insert\s+(?:ignore\s+)?into|replace\s+into|update|delete\s+from)\s+`?(\w+)`?(?:\.`?(\w+)`?)?', re.I)
DELETE_RX = re.compile(r'\bdelete\s+from\s+`?(\w+)`?(?:\.`?(\w+)`?)?', re.I)
WRITE_ONLY_RX = re.compile(r'\b(?:insert|replace|update)\b', re.I)
READ_RX = re.compile(r'\b(?:from|join)\s+`?(\w+)`?(?:\.`?(\w+)`?)?', re.I)

def sql_tables(sql):
    sql = re.sub(r'<!--.*?-->', ' ', sql, flags=re.S)
    sql = re.sub(r'on\s+duplicate\s+key\s+update', ' ', sql, flags=re.I)
    sql = re.sub(r'<[^>]+>', ' ', sql)               # dynamic SQL tags
    dyn = '${' in sql
    def norm(a, b):
        return (a, b) if b else (None, a)            # (schema, table)
    w = {norm(a, b) for a, b in WRITE_RX.findall(sql)}
    d = {norm(a, b) for a, b in DELETE_RX.findall(sql)}
    r = {norm(a, b) for a, b in READ_RX.findall(sql)}
    w = {x for x in w if x[1].lower() not in SQL_STOP}
    d = {x for x in d if x[1].lower() not in SQL_STOP}
    r = {x for x in r if x[1].lower() not in SQL_STOP} - w
    w = {('D',) + x if x in d and not (WRITE_ONLY_RX.search(sql)) else x for x in w}
    return w, r, dyn

def camel_to_snake(n):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', n).lower()

MP_BUILTIN_WRITE = ('insert', 'update', 'delete', 'save', 'remove', 'saveOrUpdate', 'insertOrUpdate')
MP_BUILTIN = {'insert', 'insertAllColumn', 'insertBatch', 'insertOrUpdate', 'insertOrUpdateBatch', 'insertOrUpdateAllColumn',
              'deleteById', 'deleteByMap', 'delete', 'deleteBatchIds', 'updateById', 'updateAllColumnById', 'update',
              'updateBatchById', 'updateForSet', 'selectById', 'selectBatchIds', 'selectByMap', 'selectOne', 'selectCount',
              'selectList', 'selectMaps', 'selectObjs', 'selectPage', 'selectMapsPage', 'save', 'saveBatch', 'saveOrUpdate',
              'saveOrUpdateBatch', 'removeById', 'remove', 'getById', 'getOne', 'list', 'listByIds', 'count', 'page'}

# ---------------------------------------------------------------- java model
JAVA_KW = {'if', 'for', 'while', 'switch', 'catch', 'synchronized', 'try', 'else', 'do', 'return', 'new', 'throw',
           'super', 'this', 'finally', 'assert', 'case', 'instanceof'}
CLASS_DECL = re.compile(r'\b(class|interface|enum|@interface)\s+(\w+)(\s*<[^{]*?>)?([^{]*)$', re.S)
METHOD_SIG = re.compile(r'(\w+)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*(?:throws\s+[\w.,\s]+)?$', re.S)

class Cls:
    __slots__ = ('fqn', 'name', 'pkg', 'module', 'kind', 'ext', 'impl', 'ann', 'fields', 'methods', 'imports', 'path',
                 'outer', 'line')
class Meth:
    __slots__ = ('id', 'cls', 'name', 'params', 'ann', 'body', 'line', 'locals', 'calls', 'refs', 'raw_ann', 'subrefs', 'ret', 'chains')

classes = {}            # 'module|java.fqn' -> Cls
java_index = collections.defaultdict(list)   # java fqn -> [keys]

def is_shared(module):
    return module in SHARED_MODULES or bool(SHARED_PREFIX and module.startswith(SHARED_PREFIX))

def lookup(jfqn, module):
    keys = java_index.get(jfqn)
    if not keys: return None
    for k in keys:
        if classes[k].module == module: return k
    for b in SHARED_MODULES:
        for k in keys:
            if classes[k].module == b: return k
    return keys[0]
by_simple = collections.defaultdict(list)
methods = {}            # id -> Meth

def module_of(path):
    return os.path.relpath(path, ROOT).replace(os.sep, '/').split('/')[0]

def parse_java(path, text):
    mod = module_of(path)
    nc = strip_comments(text)
    bl = blank_strings(nc)
    pkg_m = re.search(r'^\s*package\s+([\w.]+)\s*;', bl, re.M)
    pkg = pkg_m.group(1) if pkg_m else ''
    imports = {}
    for imp in re.findall(r'^\s*import\s+(?:static\s+)?([\w.]+)\s*;', bl, re.M):
        imports[imp.split('.')[-1]] = imp
    line_starts = [0]
    for m in re.finditer('\n', bl): line_starts.append(m.end())
    import bisect
    def lineno(pos): return bisect.bisect_right(line_starts, pos)
    stack = []      # (type, obj, open_pos)
    seg_start = 0; paren = 0
    for i, c in enumerate(bl):
        if c == '(':
            paren += 1
        elif c == ')':
            paren = max(0, paren - 1)
        elif paren > 0:
            continue
        elif c == ';':
            if stack and stack[-1][0] == 'class':
                seg_b = bl[seg_start:i]; seg_o = nc[seg_start:i]
                mm = METHOD_SIG.search(seg_b)
                if mm and mm.group(1) not in JAVA_KW and '=' not in strip_parens(seg_b[:mm.start()]):
                    k = stack[-1][1]
                    mt = Meth(); mt.cls = k.fqn; mt.name = mm.group(1); mt.line = lineno(i)
                    mt.params = parse_params(mm.group(2)); mt.ann = seg_o[:mm.start()]; mt.raw_ann = mt.ann; mt.body = ''
                    mt.locals = {}; mt.calls = []; mt.refs = set(); mt.subrefs = set(); mt.chains = []
                    rm = RET_RX.search(seg_b[:mm.start()]); mt.ret = rm.group(1) if rm else None
                    mt.id = f'{k.fqn}#{mt.name}@{mt.line}'
                    methods[mt.id] = mt; k.methods[mt.name].append(mt.id)
                else:
                    parse_field(stack[-1][1], seg_o, seg_b)
            seg_start = i + 1
        elif c == '{':
            seg_b = bl[seg_start:i]; seg_o = nc[seg_start:i]
            cur = stack[-1] if stack else None
            cm = CLASS_DECL.search(seg_b)
            if cm and (cur is None or cur[0] in ('class', 'block', 'method')) and not re.search(r'\bnew\s+[\w.<>]+\s*\([^)]*\)\s*$', seg_b):
                k = Cls(); k.name = cm.group(2); k.kind = cm.group(1); k.pkg = pkg; k.module = mod; k.path = path
                outer = cur[1] if cur and cur[0] == 'class' else None
                k.outer = outer.fqn if outer else None
                k.fqn = (outer.fqn + '.' + k.name) if outer else (mod + '|' + (pkg + '.' + k.name if pkg else k.name))
                tail = cm.group(4)
                em = re.search(r'\bextends\s+(.+?)(?=\bimplements\b|$)', tail, re.S)
                im = re.search(r'\bimplements\s+(.+)$', tail, re.S)
                k.ext = em.group(1).strip() if em else ''
                k.impl = im.group(1).strip() if im else ''
                k.ann = seg_o[:seg_o.find(cm.group(1)) if cm.group(1) in seg_o else len(seg_o)]
                k.fields = {}; k.methods = collections.defaultdict(list); k.imports = imports; k.line = lineno(i)
                classes[k.fqn] = k; by_simple[k.name].append(k.fqn); java_index[k.fqn.split('|', 1)[1]].append(k.fqn)
                stack.append(('class', k, i))
            elif cur and cur[0] == 'class' and not re.search(r'=\s*$', seg_b) and METHOD_SIG.search(seg_b) \
                    and METHOD_SIG.search(seg_b).group(1) not in JAVA_KW:
                mm = METHOD_SIG.search(seg_b)
                m = Meth(); m.cls = cur[1].fqn; m.name = mm.group(1); m.line = lineno(i)
                m.params = parse_params(mm.group(2)); m.ann = seg_o[:mm.start()]; m.raw_ann = m.ann
                rm = RET_RX.search(seg_b[:mm.start()]); m.ret = rm.group(1) if rm else None
                m.id = f'{m.cls}#{m.name}@{m.line}'
                stack.append(('method', m, i))
            else:
                stack.append(('block', None, i))
            seg_start = i + 1
        elif c == '}':
            if stack:
                t, obj, op = stack.pop()
                if t == 'method':
                    obj.body = nc[op + 1:i]
                    analyze_method(obj, bl[op + 1:i])
                    methods[obj.id] = obj
                    classes[obj.cls].methods[obj.name].append(obj.id)
            seg_start = i + 1

def strip_parens(s):
    prev = None
    while prev != s:
        prev = s; s = re.sub(r'\([^()]*\)', '', s)
    return s

def parse_params(s):
    out = {}
    depth = 0; cur = ''
    parts = []
    for ch in s:
        if ch == '<': depth += 1
        elif ch == '>': depth -= 1
        if ch == ',' and depth == 0: parts.append(cur); cur = ''
        else: cur += ch
    parts.append(cur)
    for p in parts:
        p = re.sub(r'@\w+(?:\([^)]*\))?', ' ', p).replace('final ', ' ').strip()
        m = re.match(r'([\w.]+)(?:<.*>)?(?:\[\])?(?:\.\.\.)?\s+(\w+)$', p, re.S)
        if m: out[m.group(2)] = m.group(1)
    return out

FIELD_RX = re.compile(r'(?:^|\s)([\w.]+)(?:\s*<[^;=]*>)?(?:\[\])?\s+(\w+)\s*(?:=[\s\S]*)?$')
def parse_field(k, seg_o, seg_b):
    b = re.sub(r'@[\w.]+(?:\s*\([^)]*\))?', ' ', seg_b)
    b = re.sub(r'\b(private|protected|public|static|final|transient|volatile)\b', ' ', b).strip()
    if '(' in b.split('=')[0]: return
    m = FIELD_RX.search(b.split('=')[0] + ('=' if '=' in b else ''))
    if m and m.group(1) not in JAVA_KW and m.group(1) not in ('return', 'package', 'import'):
        k.fields[m.group(2)] = m.group(1)

LOCAL_RX = re.compile(r'\b([A-Z][\w.]*)(?:\s*<[^;=(){}]*>)?(?:\[\])?\s+(\w+)\s*(?=[=;:,)])')
RET_RX = re.compile(r'([A-Z][\w.]*)\s*(?:<[^()]*>)?(?:\[\])?\s*$')
CHAIN_RX = re.compile(r'\b(\w+)\s*\.\s*(\w+)\s*\([^()]*\)\s*\.\s*(\w+)\s*\(')
CALL_RX = re.compile(r'(?:\bthis\s*\.\s*)?\b(\w+)\s*\.\s*(\w+)\s*\(')
BARE_RX = re.compile(r'(?<![\w.$])(\w+)\s*\(')
MREF_RX = re.compile(r'\b(\w+)\s*::\s*(\w+)')
CONST_RX = re.compile(r'\b([A-Z]\w*)\.([A-Z][A-Z0-9_]+)\b')
def analyze_method(m, body_b):
    m.locals = dict(m.params)
    for t, v in LOCAL_RX.findall(body_b):
        if t not in JAVA_KW: m.locals.setdefault(v, t)
    calls = []
    for r, n in CALL_RX.findall(body_b):
        calls.append((r, n))
    for r, n in MREF_RX.findall(body_b):
        calls.append((r, n))
    for n in BARE_RX.findall(body_b):
        if n not in JAVA_KW: calls.append(('', n))
    m.calls = calls
    m.chains = CHAIN_RX.findall(body_b)
    m.refs = set(CONST_RX.findall(body_b))
    m.subrefs = set(re.findall(re.escape(CDC_CHECK) + r'\(\s*(?:\w+\.)?(\w+)', body_b)) if CDC_CHECK else set()

# ---------------------------------------------------------------- resolution
def resolve_type(simple, k):
    if not simple: return None
    simple = simple.split('<')[0]
    if '.' in simple and lookup(simple, k.module): return lookup(simple, k.module)
    if simple in k.imports and lookup(k.imports[simple], k.module): return lookup(k.imports[simple], k.module)
    if k.outer and (k.outer + '.' + simple) in classes: return k.outer + '.' + simple
    if (k.fqn + '.' + simple) in classes: return k.fqn + '.' + simple
    cand = (k.pkg + '.' + simple) if k.pkg else simple
    if lookup(cand, k.module): return lookup(cand, k.module)
    c = by_simple.get(simple, [])
    same = [x for x in c if classes[x].module == k.module]
    if len(same) >= 1: return same[0]
    base = [x for x in c if is_shared(classes[x].module)]
    if base: return base[0]
    if c: return c[0]
    return None

def supertypes(fqn, seen=None):
    seen = seen or set()
    k = classes.get(fqn)
    if not k or fqn in seen: return []
    seen.add(fqn)
    out = []
    for part in split_types(k.ext) + split_types(k.impl):
        t = resolve_type(part, k)
        if t: out.append(t); out += supertypes(t, seen)
    return out

def split_types(s):
    res = []; depth = 0; cur = ''
    for ch in s:
        if ch == '<': depth += 1
        elif ch == '>': depth -= 1
        if ch == ',' and depth == 0: res.append(cur.strip()); cur = ''
        else: cur += ch
    if cur.strip(): res.append(cur.strip())
    return [r.split('<')[0].strip() for r in res if r]

implementors = collections.defaultdict(set)
def build_implementors():
    for fqn, k in classes.items():
        for st in supertypes(fqn):
            implementors[st].add(fqn)

def is_feign(fqn):
    k = classes.get(fqn)
    return bool(k and '@FeignClient' in (k.ann or ''))

def generic_args(k, base):
    m = re.search(base + r'\s*<\s*([\w.]+)\s*(?:,\s*([\w.]+)\s*)?>', k.ext + ' ' + k.impl)
    return m.groups() if m else (None, None)

def entity_table(efqn):
    e = classes.get(efqn)
    if not e: return None
    m = re.search(r'@TableName\(\s*(?:value\s*=\s*)?"(\w+)"', e.ann or '')
    return m.group(1) if m else camel_to_snake(e.name)

def mapper_entity(fqn):
    """Entity table for a BaseMapper<E> interface (walks super interfaces)."""
    k = classes.get(fqn)
    if not k: return None
    a, _ = generic_args(k, 'BaseMapper')
    if a: return entity_table(resolve_type(a, k))
    for st in supertypes(fqn):
        sk = classes.get(st)
        if sk:
            a, _ = generic_args(sk, 'BaseMapper')
            if a: return entity_table(resolve_type(a, sk))
    return None

def is_mapper(fqn):
    k = classes.get(fqn)
    if not k or k.kind != 'interface': return False
    return k.name.endswith(('Mapper', 'Dao')) or 'BaseMapper' in k.ext or '@Mapper' in (k.ann or '')

# ---------------------------------------------------------------- XML statements
xml_stmts = collections.defaultdict(dict)
xml_raw = collections.defaultdict(dict)    # namespace fqn -> id -> (w, r, dyn)
def parse_xml(path, text):
    m = re.search(r'<mapper[^>]*namespace="([\w.]+)"', text)
    if not m: return
    ns = m.group(1)
    frags = dict(re.findall(r'<sql\s+id="(\w+)"[^>]*>(.*?)</sql>', text, re.S))
    for kind, sid, body in re.findall(r'<(select|insert|update|delete)\s+[^>]*?id="(\w+)"[^>]*>(.*?)</\1>', text, re.S):
        body = re.sub(r'<include\s+refid="(\w+)"\s*/>', lambda mm: frags.get(mm.group(1), ''), body)
        w, r, dyn = sql_tables(body)
        sql_corpus.append((body, os.path.relpath(path, ROOT).replace(os.sep, '/') + '#' + sid))
        if kind == 'select': r |= w; w = set()
        xml_stmts[module_of(path) + '|' + ns][sid] = (w, r, dyn)
        xml_raw[module_of(path) + '|' + ns][sid] = xml_raw[module_of(path) + '|' + ns].get(sid, '') + body

sql_corpus = []        # (sql_text, location)
JOIN_ALIAS = re.compile(r'\b(?:from|join)\s+`?(?:\w+\.)?`?(\w+)`?\s+(?:as\s+)?(?!(?:on|where|left|right|inner|join|group|order|limit|union|set|and|or)\b)(\w+)', re.I)
EQ_RX = re.compile(r'\b(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)\b')
def sql_joins(sql):
    sql = re.sub(r'<[^>]+>', ' ', sql)
    alias = {}
    for t, a in JOIN_ALIAS.findall(sql):
        alias[a] = t; alias[t] = t
    out = set()
    for a1, c1, a2, c2 in EQ_RX.findall(sql):
        t1, t2 = alias.get(a1), alias.get(a2)
        if t1 and t2 and t1 != t2:
            out.add(tuple(sorted([(t1, c1), (t2, c2)])))
    return out

ANN_HEAD = re.compile(r'@(Select|Insert|Update|Delete)\s*\(')
def ann_sql_blocks(ann):
    """Yield (kind, raw annotation argument) using balanced parentheses, skipping string literals."""
    for m in ANN_HEAD.finditer(ann):
        i = m.end(); depth = 1; n = len(ann)
        while i < n and depth:
            c = ann[i]
            if c == '"':
                i += 1
                while i < n and ann[i] != '"':
                    i += 2 if ann[i] == chr(92) else 1
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            i += 1
        yield m.group(1), ann[m.end():i - 1]

def method_sql(mid):
    m = methods[mid]
    out = []
    for kind, sql in ann_sql_blocks(m.ann or ''):
        w, r, dyn = sql_tables(string_concat(sql))
        sql_corpus.append((string_concat(sql), mid))
        if kind == 'Select': r |= w; w = set()
        out.append((w, r, dyn))
    return out

# ---------------------------------------------------------------- effect computation
memo = {}
def resolve_call(m, recv, name):
    """Return list of (target method id, via) for a call inside method m."""
    k = classes[m.cls]
    targets = []
    if recv in ('', 'this'):
        owner = [m.cls] + supertypes(m.cls)
        if is_mapper(m.cls) and ((name in classes[m.cls].methods and not any(methods[x].body for x in classes[m.cls].methods[name]))
                                 or (name not in classes[m.cls].methods and name in MP_BUILTIN)):
            return [(m.cls, name)], 'type'
        for o in owner:
            if name in classes[o].methods if o in classes else False:
                targets += [(x, 'local') for x in classes[o].methods[name]]
                break
        if not targets and k.outer and name in classes[k.outer].methods:
            targets += [(x, 'local') for x in classes[k.outer].methods[name]]
        if not targets and name in MP_BUILTIN:
            mk = service_impl_mapper(m.cls)
            if mk: return [(mk, name)], 'type'
        return targets, None
    if recv == 'baseMapper':
        mk = service_impl_mapper(m.cls)
        return ([(mk, name)], 'type') if mk else ([], None)
    if recv == 'super':
        for o in supertypes(m.cls):
            if o in classes and name in classes[o].methods:
                return [(x, 'local') for x in classes[o].methods[name]], None
        return [], None
    tname = m.locals.get(recv) or k.fields.get(recv)
    if not tname:
        # field inherited from super class / outer class
        for o in supertypes(m.cls) + ([k.outer] if k.outer else []):
            if o in classes and recv in classes[o].fields:
                tname = classes[o].fields[recv]; k = classes[o]; break
    if not tname: return [], None
    tf = resolve_type(tname, k)
    if not tf: return [], None
    return [(tf, name)], 'type'

def service_impl_mapper(cls_key):
    for c in [cls_key] + supertypes(cls_key):
        ck = classes.get(c)
        if not ck: continue
        a, _ = generic_args(ck, 'ServiceImpl')
        if a: return resolve_type(a, ck)
    return None

def type_targets(tf, name, from_module):
    """Expand a call on type tf to concrete method ids with via-kind."""
    res = []
    if is_mapper(tf):
        return [('MAPPER', tf, name)]
    cands = [tf] + sorted(implementors.get(tf, []))
    feign = is_feign(tf)
    for c in cands:
        ck = classes.get(c)
        if not ck: continue
        if feign and c != tf:
            via = 'feign'
        else:
            if c != tf and ck.module != from_module: continue
            via = 'local'
        found = False
        for o in [c] + supertypes(c):
            ok = classes.get(o)
            if ok and name in ok.methods:
                bodies = [x for x in ok.methods[name] if methods[x].body]
                if bodies:
                    res += [('METHOD', x, via) for x in bodies]; found = True; break
        if not found and ck.kind == 'class':
            a, b = generic_args(ck, 'ServiceImpl')
            if a and name in MP_BUILTIN:
                res.append(('MAPPER', resolve_type(a, ck), name))
    return res

def mapper_effects(mfqn, name):
    eff = set(); notes = set()
    k = classes.get(mfqn)
    declared = [x for x in (k.methods.get(name, []) if k else [])]
    hit = False
    for mid in declared:
        for w, r, dyn in method_sql(mid):
            hit = True
            eff |= {('W',) + t for t in w}; eff |= {('R',) + t for t in r}
            if dyn: notes.add('dyn:W' if w else 'dyn:R')
    if mfqn in xml_stmts and name in xml_stmts[mfqn]:
        w, r, dyn = xml_stmts[mfqn][name]; hit = True
        eff |= {('W',) + t for t in w}; eff |= {('R',) + t for t in r}
        if dyn: notes.add('dyn:W' if w else 'dyn:R')
    eff = {(('D',) + x[2:]) if len(x) == 4 else x for x in eff}
    if not hit and name in MP_BUILTIN:
        t = mapper_entity(mfqn)
        if t:
            op = 'D' if name.startswith(('delete', 'remove')) else 'W' if name.startswith(MP_BUILTIN_WRITE) else 'R'
            eff.add((op, None, t))
    return eff, notes

def local_info(mid):
    """Direct table effects of one method, plus outgoing edges (target mid, via)."""
    m = methods[mid]
    out = {}; edges = []
    def add(e, trail):
        if e not in out: out[e] = trail
    mod = classes[m.cls].module
    for cname, const in m.refs:
        if cname == CDC_REGISTRY:
            add(('SUB', mod, const, 'local'), [mid])
    for name in m.subrefs:
        add(('SUB', classes[m.cls].path, name, 'local'), [mid])
    for expr in re.findall(r'\.send\(\s*([\w."]+(?:\s*\+\s*[\w."]+)*)\s*,', m.body or ''):
        topic = resolve_expr(expr, classes[m.cls].path)
        if topic and not topic.startswith('{'):
            add(('PUB', None, topic.split('{')[0], 'local'), [mid])
    chain_items = []
    for recv, n1, n2 in m.chains:
        t1, k1 = resolve_call(m, recv, n1)
        firsts = []
        if k1 == 'type':
            for tf, nm in t1: firsts += [x[1] for x in type_targets(tf, nm, mod) if x[0] == 'METHOD']
        else:
            firsts = [x for x, v in t1]
        for fid in firsts:
            fm = methods[fid]
            if not fm.ret: continue
            rt = resolve_type(fm.ret, classes[fm.cls])
            if rt: chain_items += type_targets(rt, n2, mod)
    for recv, name in m.calls + [('__chain__', i) for i in range(len(chain_items))]:
        if recv == '__chain__':
            exp = [chain_items[name]]
        else:
            targets, kind = resolve_call(m, recv, name)
            if kind == 'type':
                exp = []
                for tf, nm in targets: exp += type_targets(tf, nm, mod)
            else:
                exp = [('METHOD', x, v) for x, v in targets if methods[x].body]
        for item in exp:
            if item[0] == 'MAPPER':
                if not item[1]: continue
                mk = classes.get(item[1])
                bodies = [x for x in (mk.methods.get(item[2], []) if mk else []) if methods[x].body]
                if bodies:
                    edges += [(b, 'local') for b in bodies]
                    continue
                eff, notes = mapper_effects(item[1], item[2])
                for op, sch, t in eff:
                    add((op, sch, t, 'local'), [mid, f'{item[1]}.{item[2]}'])
                for note in notes:
                    for lit in set(re.findall(r'"(\w+)"', m.body or '')) & KNOWN_TABLES:
                        add((note[-1], None, lit, 'local'), [mid, f'{item[1]}.{item[2]}', 'dynamic-table'])
            else:
                _, tid, via = item
                if tid != mid: edges.append((tid, via))
    return out, edges

_local = {}
def get_local(mid):
    if mid not in _local: _local[mid] = local_info(mid)
    return _local[mid]

def merge_edge(out, src_mid, tid, via, sub):
    for e, tr in sub.items():
        v = 'feign' if (via == 'feign' or e[3] == 'feign') else 'local'
        if e[0] == 'SUB' and v == 'feign': continue
        key = (e[0], e[1], e[2], v)
        if key not in out: out[key] = [src_mid] + tr
    if via == 'feign':
        key = ('FEIGN', None, tid, 'feign')
        if key not in out: out[key] = [src_mid, tid]

def effects(root):
    """Effects of a method including everything reachable; cycles solved via Tarjan SCC."""
    if root in memo: return memo[root]
    index = {}; low = {}; onstack = set(); st = []; counter = [0]
    work = [(root, 0)]
    while work:
        v, pi = work.pop()
        if pi == 0:
            index[v] = low[v] = counter[0]; counter[0] += 1
            st.append(v); onstack.add(v)
        _, edges = get_local(v)
        recurse = False
        for i in range(pi, len(edges)):
            w = edges[i][0]
            if w in memo: continue
            if w not in index:
                work.append((v, i + 1)); work.append((w, 0)); recurse = True; break
            elif w in onstack:
                low[v] = min(low[v], index[w])
        if recurse: continue
        if low[v] == index[v]:
            comp = []
            while True:
                w = st.pop(); onstack.discard(w); comp.append(w)
                if w == v: break
            cset = set(comp); out = {}
            for x in comp:
                d, _ = get_local(x)
                for e, tr in d.items():
                    if e not in out: out[e] = tr
            for x in comp:
                for tid, via in get_local(x)[1]:
                    if tid in cset:
                        if via == 'feign':
                            key = ('FEIGN', None, tid, 'feign')
                            if key not in out: out[key] = [x, tid]
                        continue
                    merge_edge(out, x, tid, via, memo.get(tid, {}))
            for x in comp: memo[x] = out
        if work:
            p = work[-1][0]
            if p in low and v in low: low[p] = min(low[p], low[v])
    return memo[root]

# ---------------------------------------------------------------- entry points
MAP_ANN = re.compile(r'@(Get|Post|Put|Delete|Request)Mapping\s*\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*"([^"]*)"')
MAP_ANN_EMPTY = re.compile(r'@(Get|Post|Put|Delete|Request)Mapping\b(?!\s*\()|@(Get|Post|Put|Delete|Request)Mapping\s*\(\s*(?!(?:value|path)\s*=|\{?\s*")')
def class_path(k):
    m = re.search(r'@RequestMapping\s*\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*"([^"]*)"', k.ann or '')
    if m: return m.group(1)
    m = re.search(r'@FeignClient\s*\([^)]*path\s*=\s*"([^"]*)"', k.ann or '')
    return m.group(1) if m else ''

def method_path(m):
    """Path for an HTTP handler, falling back to the implemented Feign/API interface declaration."""
    k = classes[m.cls]
    mm = MAP_ANN.search(m.ann or '')
    if mm: return join_path(class_path(k), mm.group(2))
    if MAP_ANN_EMPTY.search(m.ann or ''): return join_path(class_path(k), '')
    for st in supertypes(m.cls):
        sk = classes.get(st)
        if not sk or sk.kind != 'interface': continue
        for x in sk.methods.get(m.name, []):
            am = MAP_ANN.search(methods[x].ann or '')
            if am: return join_path(class_path(k) or class_path(sk), am.group(2))
    return None

def join_path(a, b):
    p = ('/' + a.strip('/') + '/' + b.strip('/')).replace('//', '/')
    return p.rstrip('/') or '/'

const_values = {}
const_by_path = collections.defaultdict(dict)
def collect_constants(text, path=None):
    for name, val in re.findall(r'static\s+final\s+String\s+(\w+)\s*=\s*"([^"]*)"\s*;', text):
        const_values.setdefault(name, val)
        if path: const_by_path[path][name] = val

def resolve_expr(expr, path=None):
    expr = expr.strip()
    local = const_by_path.get(path, {})
    parts = re.split(r'\s*\+\s*', expr)
    out = ''
    for p in parts:
        p = p.strip()
        if p.startswith('"'): out += p.strip('"')
        else: out += local.get(p.split('.')[-1]) or const_values.get(p.split('.')[-1], '{' + p.split('.')[-1] + '}')
    return out

subscriptions = collections.defaultdict(dict)   # module -> const -> [db.table]
def parse_table_constants(path, text):
    mod = module_of(path)
    t = re.escape(CDC_TYPE)
    # double-brace initialiser  new LinkedList<T>() {{ add(new T("db", "t")); }};  or a plain expression  Arrays.asList(new T("db", "t"));
    for m in re.finditer(r'List<(?:[\w.]*\.)?' + t + r'>\s+(\w+)\s*=\s*(new\b[^;{]*\{.*?\}\s*\}?|[^;{]*?)\s*;', text, re.S):
        subscriptions[path][m.group(1)] = [f'{a}.{b}' for a, b in re.findall(t + r'\(\s*"(\w+)"\s*,\s*"([^"]+)"', m.group(2))]
        if not (CDC_REGISTRY and re.search(r'\b(?:class|interface)\s+' + re.escape(CDC_REGISTRY) + r'\b', text)): continue
        subscriptions[mod][m.group(1)] = [f'{a}.{b}' for a, b in re.findall(t + r'\(\s*"(\w+)"\s*,\s*"([^"]+)"', m.group(2))]

def shared_subscription(const):
    """Registry list declared in a shared module (e.g. a common library) rather than the listener's own module."""
    for mod in sorted(subscriptions):
        if is_shared(mod) and const in subscriptions[mod]: return subscriptions[mod][const]
    return []

disabled = []
def find_disabled_listeners(path, raw):
    for m in re.finditer(r'^[ \t]*//[ \t]*@KafkaListener\((.*?)\)[ \t]*\n(?:[ \t]*//.*\n)*?[ \t]*(?://[ \t]*)?public\s+\w+\s+(\w+)\s*\(', raw, re.M):
        g = re.search(r'groupId\s*=\s*([^,)]+)', m.group(1))
        disabled.append({'file': os.path.relpath(path, ROOT).replace(os.sep, '/'), 'method': m.group(2),
                         'group': resolve_expr(g.group(1), path) if g else ''})

def entries():
    res = []
    for mid, m in methods.items():
        if not m.body and m.body != '': continue
        k = classes[m.cls]; ann = m.ann or ''
        cond = re.findall(r'@Conditional\(\s*(\w+)\.class', k.ann or '') + re.findall(r'@Conditional\(\s*(\w+)\.class', ann)
        if '@KafkaListener' in ann:
            g = re.search(r'groupId\s*=\s*([^,)\n]+)', ann); t = re.search(r'topics\s*=\s*(\{[^}]*\}|[^,)\n]+)', ann)
            res.append({'kind': 'kafka', 'id': mid, 'group': resolve_expr(g.group(1), k.path) if g else '',
                        'topic': t.group(1).strip() if t else '', 'cond': cond})
        elif SCHED_BASE and m.name == SCHED_BASE.get('method') and any(
                classes[s].name.startswith(SCHED_BASE.get('class_prefix', '')) and classes[s].name.endswith(SCHED_BASE.get('class_suffix', ''))
                for s in supertypes(m.cls) if s in classes):
            res.append({'kind': 'sched', 'id': mid, 'handler': k.name, 'cond': cond})
        elif '@XxlJob' in ann or '@Scheduled' in ann:
            h = re.search(r'@XxlJob\(\s*"([^"]+)"', ann)
            res.append({'kind': 'sched', 'id': mid, 'handler': h.group(1) if h else '', 'cond': cond})
        elif ('@RestController' in (k.ann or '') or '@Controller' in (k.ann or '')) and k.kind == 'class':
            p = method_path(m)
            if p:
                res.append({'kind': 'http', 'id': mid, 'path': p, 'cond': cond})
    return res

# ---------------------------------------------------------------- main
route_rules = collections.defaultdict(set)   # topic -> {db.table}
def parse_routes(path, text):
    """Route("db", "table", ...TOPIC constants...): the arguments up to the matching close paren name the target topics."""
    for m in re.finditer(re.escape(ROUTE_TYPE) + r'\(\s*"(\w+)"\s*,\s*"(\w+)"\s*,', text):
        db, t = m.groups(); i = m.end(); depth = 1
        while i < len(text) and depth:
            depth += {'(': 1, ')': -1}.get(text[i], 0); i += 1
        body = text[m.end():i - 1]
        for const in re.findall(r'\b\w+\.(\w+)\b', body):
            if const in const_values: route_rules[const_values[const]].add(f'{db}.{t}')

route_src = []
def walk():
    xmls = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            p = os.path.join(dp, f)
            if f.endswith('.java'):
                raw = open(p, encoding='utf-8', errors='ignore').read()
                collect_constants(raw, p)
                if CDC_TYPE and CDC_TYPE + '(' in raw: parse_table_constants(p, strip_comments(raw))
                if '@KafkaListener' in raw: find_disabled_listeners(p, raw)
                if ROUTE_TYPE and ROUTE_TYPE + '(' in raw: route_src.append((p, raw))
                try: parse_java(p, raw)
                except RecursionError: pass
            elif f.endswith('.xml') and 'mapper' in open(p, encoding='utf-8', errors='ignore').read(2000).lower():
                parse_xml(p, open(p, encoding='utf-8', errors='ignore').read())

def main():
    sys.setrecursionlimit(20000)
    walk()
    for p, raw in route_src: parse_routes(p, strip_comments(raw))
    build_implementors()
    ents = entries()
    out_entries = []
    for e in ents:
        m = methods[e['id']]; k = classes[m.cls]
        eff = effects(e['id'])
        tables = []; subs = []; feigns = []; pubs = []
        for (op, sch, t, via), trail in eff.items():
            if op in ('W', 'R', 'D'):
                tables.append({'op': op, 'schema': sch, 'table': t, 'via': via, 'trail': [short(x) for x in trail]})
            elif op == 'PUB':
                pubs.append(t)
            elif op == 'SUB':
                subs += subscriptions.get(sch, {}).get(t) or shared_subscription(t)
            elif op == 'FEIGN':
                fm = methods[t]; feigns.append({'target': short(t), 'module': classes[fm.cls].module, 'path': method_path(fm)})
        e.update({'module': k.module, 'file': os.path.relpath(k.path, ROOT).replace(os.sep, '/'), 'line': m.line,
                  'name': f'{k.name}.{m.name}', 'tables': tables, 'subs': sorted(set(subs)), 'feign': feigns,
                  'pubs': sorted(set(pubs)), 'topic_res': resolve_expr(e['topic'].strip('{}'), k.path) if e['kind'] == 'kafka' and e.get('topic') else ''})
        out_entries.append(e)
    # shallow reads of each Feign target: direct SQL reads within 3 levels (controller -> service -> mapper)
    shallow_memo = {}
    def shallow_reads(root, levels=SHALLOW_LEVELS):
        if root in shallow_memo: return shallow_memo[root]
        seen = {root}; frontier = [root]; out = set()
        for depth in range(1, levels + 1):
            nxt = []
            for m in frontier:
                d, edges = get_local(m)
                if depth < levels:
                    out |= {t for (op, sch, t, via) in d if op == 'R'}
                    for tid, via in edges:
                        if via == 'local' and tid not in seen: seen.add(tid); nxt.append(tid)
            frontier = nxt
        shallow_memo[root] = out
        return out
    for e in out_entries:
        if e['kind'] == 'kafka_off': continue
        fs = {}
        for (op, sch, tid, via) in effects(e['id']):
            if op == 'FEIGN' and tid in methods:
                fs[short(tid)] = sorted(shallow_reads(tid))
        e['feign_shallow'] = fs
    # path-sensitive upstream: for each written table, reads along the write path only
    FETCH = re.compile(r'^(get|query|select|find|list|load|fetch|count|search|is|has|check|build|assemble|fill|resolve|calc|compute)(?=[A-Z0-9_]|$)')
    def reads_of(eff):
        return {(t, via) for (op, sch, t, via) in eff if op == 'R'}
    for e in out_entries:
        if e['kind'] not in ('kafka', 'http', 'sched'): continue
        root = e['id']; full = effects(root)
        psrc = {}
        for (op, sch, t, via), tr in full.items():
            if op != 'W' or via != 'local': continue
            path = [x for x in tr if x in methods]
            if not path: continue
            rs = set()
            for m in path[:-1]:
                d, edges = get_local(m)
                rs |= reads_of(d)
                for tid, evia in edges:
                    if evia == 'feign' or FETCH.match(methods[tid].name):
                        rs |= {(x, 'feign' if evia == 'feign' or v == 'feign' else v) for x, v in reads_of(effects(tid))}
            last = path[-1]
            d, edges = get_local(last)
            rs |= reads_of(d)
            for tid, evia in edges:
                sub = effects(tid)
                writes_other = any(op == 'W' and v == 'local' and tt != t for (op, sc_, tt, v) in sub)
                writes_t = any(op == 'W' and v == 'local' and tt == t for (op, sc_, tt, v) in sub)
                if writes_other and not writes_t: continue
                rs |= {(x, 'feign' if evia == 'feign' or v == 'feign' else v) for x, v in reads_of(sub)}
            psrc[t] = sorted({f'{x}|{v}' for x, v in rs if x != t})
        e['psrc'] = psrc
    # forwarded topics: a listener on an internal topic inherits the forwarder's CDC subscriptions
    for e in out_entries:
        if e['kind'] != 'kafka' or (CDC_TOPIC and CDC_TOPIC in e['topic']): continue
        topic = e['topic_res'].strip('"').strip()
        inherited = set()
        for f in out_entries:
            if f is e or f['kind'] != 'kafka': continue
            for p in f['pubs']:
                if p and (topic == p or topic.startswith(p)):
                    inherited |= set(f['subs'])
        for rt, tbls in route_rules.items():
            if topic == rt: inherited |= tbls
        if inherited:
            e['subs_forwarded'] = sorted(inherited - set(e['subs']))
            e['subs'] = sorted(set(e['subs']) | inherited)
    # disabled listeners: compute what they would write
    by_file_method = collections.defaultdict(list)
    for mid, m in methods.items():
        by_file_method[(os.path.relpath(classes[m.cls].path, ROOT).replace(os.sep, '/'), m.name)].append(mid)
    for d in disabled:
        for mid in by_file_method.get((d['file'], d['method']), []):
            if not methods[mid].body: continue
            eff = effects(mid); m = methods[mid]; k = classes[m.cls]
            out_entries.append({'kind': 'kafka_off', 'id': mid, 'group': d['group'], 'module': k.module, 'file': d['file'],
                'line': m.line, 'name': f'{k.name}.{m.name}', 'cond': [],
                'tables': [{'op': op, 'schema': sch, 'table': t, 'via': via, 'trail': [short(x) for x in tr]}
                           for (op, sch, t, via), tr in eff.items() if op in ('W', 'R', 'D')],
                'subs': sorted({x for (op, sch, t, via) in eff if op == 'SUB' for x in subscriptions.get(sch, {}).get(t, [])}),
                'feign': []})
    # table -> code (entities, mapper methods)
    code = collections.defaultdict(lambda: {'entities': [], 'mappers': []})
    for fqn, k in classes.items():
        tm = re.search(r'@TableName\(\s*(?:value\s*=\s*)?"(\w+)"', k.ann or '')
        if tm: code[tm.group(1)]['entities'].append(f"{k.module}:{os.path.relpath(k.path, ROOT).replace(os.sep, '/')}:{k.line}")
    for fqn, k in classes.items():
        if not is_mapper(fqn): continue
        ent = mapper_entity(fqn)
        rel = os.path.relpath(k.path, ROOT).replace(os.sep, '/')
        if ent: code[ent]['mappers'].append({'mapper': k.name, 'method': '(BaseMapper)', 'op': 'RW', 'loc': f'{k.module}:{rel}:{k.line}'})
        for name, mids in k.methods.items():
            eff, _ = mapper_effects(fqn, name)
            for op, sch, t in eff:
                if methods[mids[0]].body: continue
                code[t]['mappers'].append({'mapper': k.name, 'method': name, 'op': op, 'loc': f'{k.module}:{rel}:{methods[mids[0]].line}'})
    joins = collections.defaultdict(set)
    for sql, loc in sql_corpus:
        for pair in sql_joins(sql):
            joins[pair].add(short(loc) if loc in methods else loc)
    # Stable fingerprint inputs: methods that directly execute a write on a table, and the write statements.
    direct_writers = collections.defaultdict(set)
    for mid in methods:
        if not methods[mid].body: continue
        d, _ = _local.get(mid) or (None, None)
        if d is None: continue
        for (op, sch, t, via), tr in d.items():
            if op in ('W', 'D') and via == 'local':
                direct_writers[t].add(short(mid))
                if len(tr) > 1 and '|' in tr[1]: direct_writers[t].add(tr[1])
    names = set()
    for e in out_entries:
        names.add(short(e['id']))
    for v in direct_writers.values():
        names |= v
    by_short = {short(mid): mid for mid in methods}
    fp = {}
    for n in names:
        key, h = fingerprint(n, by_short)
        if key: fp[key] = h
    json.dump({'entries': out_entries, 'disabled': disabled, 'code': code, 'fp': fp,
               'direct_writers': {t: sorted(v) for t, v in direct_writers.items()},
               'joins': [{'a': list(p[0]), 'b': list(p[1]), 'evidence': sorted(v)[:5], 'n': len(v)} for p, v in joins.items()],
               'stats': {'classes': len(classes), 'methods': len(methods), 'xml_namespaces': len(xml_stmts),
                         'cdc_configured': bool(CDC_TYPE), 'cdc_lists': sum(len(v) for v in subscriptions.values()),
                         'cdc_listeners': sum(1 for e in out_entries if e['kind'] == 'kafka' and e['subs'])}},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('classes', len(classes), 'methods', len(methods), 'entries', len(out_entries),
          collections.Counter(e['kind'] for e in out_entries), 'disabled', len(disabled))

def norm_text(t):
    return re.sub(r'\s+', ' ', t or '').strip()

def fingerprint(name, by_short):
    """(stable key, hash) for a trail element: a method 'module:Class.method:line' or a mapper call 'module|fqn.method'.
    Keys drop line numbers so unrelated edits elsewhere in the file do not change them."""
    if name in by_short:
        m = methods[by_short[name]]
        key = name.rsplit(':', 1)[0]
        text = norm_text(m.raw_ann) + '\n' + norm_text(m.body)
    elif '|' in name and '.' in name:
        cls_key, meth = name.rsplit('.', 1)
        key = name
        k = classes.get(cls_key)
        parts = []
        if k:
            for mid in k.methods.get(meth, []):
                parts.append(norm_text(methods[mid].raw_ann) + norm_text(methods[mid].body))
        parts.append(norm_text(xml_raw.get(cls_key, {}).get(meth, '')))
        text = '\n'.join(parts)
    else:
        return None, None
    return key, hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]

def short(mid):
    if mid not in methods: return mid
    m = methods[mid]; k = classes[m.cls]
    return f"{k.module}:{k.name}.{m.name}:{m.line}"

if __name__ == '__main__':
    main()
