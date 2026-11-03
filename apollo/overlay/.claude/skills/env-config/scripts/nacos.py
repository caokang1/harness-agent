#!/usr/bin/env python3
"""
Nacos config helper for test environments. Standard library only.

  nacos.py get <env> <dataId> [-o file]                  print or save the current content
  nacos.py set <env> <dataId> --file new.yml             show the diff only (exit 3)
  nacos.py set <env> <dataId> --file new.yml --confirm   back up, publish with CAS, read back and verify

Environments come from ~/.config/apollo-env/nacos.json:
  {"{{AP_CC}}-test": {"url": "https://.../nacos", "namespace": "<tenant id>", "group": "{{AP_NS}}-{{AP_CC}}",
               "username": "", "password": ""}}
Backups go to ~/.cache/apollo-env/nacos-backups/, every publish is logged in ~/.cache/apollo-env/ops.log.
"""
import argparse
import difflib
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

CONF = Path.home() / '.config' / 'apollo-env' / 'nacos.json'
CACHE = Path.home() / '.cache' / 'apollo-env'


def env_conf(env):
    conf = json.loads(CONF.read_text(encoding='utf-8'))
    if env not in conf:
        sys.exit(f"✗ {CONF} has no env {env}; known: {', '.join(conf)}")
    return conf[env]


def token(c):
    if not c.get('username'):
        return ''
    body = urllib.parse.urlencode({'username': c['username'], 'password': c['password']}).encode()
    with urllib.request.urlopen(f"{c['url']}/v1/auth/login", body, timeout=20) as r:
        return json.load(r).get('accessToken', '')


def call(c, method, params):
    params = {**params, 'tenant': c['namespace'], 'group': c['group']}
    t = token(c)
    if t:
        params['accessToken'] = t
    url = f"{c['url']}/v1/cs/configs"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url + ('' if method == 'POST' else '?' + data.decode()),
                                 data=data if method == 'POST' else None, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8')


def log(line):
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(CACHE / 'ops.log', 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\tnacos\t{line}\n")


def main():
    ap = argparse.ArgumentParser(description='Nacos config helper')
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('get')
    g.add_argument('env')
    g.add_argument('data_id')
    g.add_argument('-o', '--out')
    s = sub.add_parser('set')
    s.add_argument('env')
    s.add_argument('data_id')
    s.add_argument('--file', required=True)
    s.add_argument('--confirm', action='store_true', help='publish; only after the user approved the diff')
    s.add_argument('--type', default='yaml')
    a = ap.parse_args()
    c = env_conf(a.env)
    current = call(c, 'GET', {'dataId': a.data_id})

    if a.cmd == 'get':
        if a.out:
            Path(a.out).write_text(current, encoding='utf-8')
            print(f"saved {len(current.splitlines())} lines to {a.out}")
        else:
            print(current)
        return

    new = Path(a.file).read_text(encoding='utf-8')
    diff = list(difflib.unified_diff(current.splitlines(), new.splitlines(), 'nacos', a.file, lineterm='', n=1))
    if not diff:
        print("no change")
        return
    print('\n'.join(diff))
    if not a.confirm:
        print("\n(diff only; re-run with --confirm after the user approved it)")
        sys.exit(3)
    backups = CACHE / 'nacos-backups'
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / f"{time.strftime('%Y%m%d-%H%M%S')}-{a.env}-{a.data_id}"
    backup.write_text(current, encoding='utf-8')
    backup.chmod(0o600)
    cas = hashlib.md5(current.encode('utf-8')).hexdigest()
    ok = call(c, 'POST', {'dataId': a.data_id, 'content': new, 'type': a.type, 'casMd5': cas})
    if ok.strip() != 'true':
        sys.exit(f"✗ publish rejected ({ok.strip()}): someone changed {a.data_id} since it was read; re-read and redo")
    if call(c, 'GET', {'dataId': a.data_id}) != new:
        sys.exit(f"✗ published but read-back differs; backup at {backup}")
    added = sum(1 for d in diff if d.startswith('+') and not d.startswith('+++'))
    removed = sum(1 for d in diff if d.startswith('-') and not d.startswith('---'))
    log(f"{a.env}/{a.data_id}\t+{added} -{removed}\tbackup={backup}")
    print(f"✓ published {a.data_id} (+{added} -{removed}), verified; backup {backup}")


if __name__ == '__main__':
    main()
