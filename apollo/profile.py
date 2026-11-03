#!/usr/bin/env python3
"""Project profile: keep company-specific names out of the public kit.

The public overlay uses placeholders such as {{AP_MAIN_BRANCH}}. The real values live in a
private profile directory that is never committed:

  <profile>/profile.json   {"terms": [{"real": "...", "ph": "AP_X", "mode": "word|plain|prefix"}, ...],
                            "private_files": ["relative/path", ...]}
  <profile>/files/<path>   whole files that are too specific to publish (copied as they are)

  profile.py strip --profile P --src DIR --dst DIR [--paths-from FILE]
      maintainer: copy files from a configured project into the overlay, real -> placeholder
  profile.py apply --profile P FILE...
      installer: placeholder -> real, in place
  profile.py get --profile P AP_NAME
      print the real value of one placeholder
  profile.py check --profile P DIR
      fail when a real value or an unknown {{AP_*}} placeholder is left
  profile.py roundtrip --profile P --src DIR --paths-from FILE
      prove strip + apply gives back the original bytes
"""
import argparse
import json
import re
import sys
from pathlib import Path

PH = re.compile(r'\{\{AP_[A-Z0-9_]+\}\}')


def load(profile):
    data = json.loads((Path(profile) / 'profile.json').read_text(encoding='utf-8'))
    terms = data['terms']
    seen = {}
    for t in terms:
        if seen.setdefault(t['ph'], t['real']) != t['real']:
            sys.exit(f"placeholder {t['ph']} maps to two values")
    return terms, data.get('private_files', [])


def pattern(t):
    real = re.escape(t['real'])
    mode = t.get('mode', 'word')
    if mode == 'plain':
        return re.compile(real)
    if mode == 'prefix':  # 'apollo' followed by '-' but not one of the kept suffixes
        keep = '|'.join(map(re.escape, t.get('keep', [])))
        return re.compile(real + (rf'(?=-(?!(?:{keep})\b))' if keep else '(?=-)'))
    return re.compile(rf'(?<![A-Za-z0-9_]){real}(?![A-Za-z0-9])')


def strip_text(text, terms):
    for t in sorted(terms, key=lambda t: (t.get('mode') == 'prefix', -len(t['real']))):
        text = pattern(t).sub('{{' + t['ph'] + '}}', text)
    return text


def apply_text(text, terms):
    for t in terms:
        text = text.replace('{{' + t['ph'] + '}}', t['real'])
    return text


def read(p):
    try:
        return p.read_bytes().decode('utf-8')
    except UnicodeDecodeError:
        return None


def paths(args):
    return [l.strip() for l in Path(args.paths_from).read_text().splitlines() if l.strip()]


def cmd_strip(args):
    terms, private = load(args.profile)
    src, dst = Path(args.src), Path(args.dst)
    for rel in paths(args):
        if rel in private:
            continue
        text = read(src / rel).replace('\r\n', '\n')
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(strip_text(text, terms), encoding='utf-8')
        if (src / rel).stat().st_mode & 0o111:
            out.chmod(0o755)


def cmd_apply(args):
    terms, _ = load(args.profile)
    for f in map(Path, args.files):
        text = read(f)
        if text is not None and '{{AP_' in text:
            f.write_text(apply_text(text, terms), encoding='utf-8')


def cmd_get(args):
    terms, _ = load(args.profile)
    print(next((t['real'] for t in terms if t['ph'] == args.name), ''))


def cmd_check(args):
    terms, _ = load(args.profile)
    known = {'{{' + t['ph'] + '}}' for t in terms}
    bad = 0
    for f in sorted(p for p in Path(args.dir).rglob('*') if p.is_file()):
        text = read(f)
        if text is None:
            continue
        for t in terms:
            if t.get('mode') != 'prefix' and pattern(t).search(text):
                print(f"leak  {f}: {t['real']}")
                bad += 1
        for ph in set(PH.findall(text)) - known:
            print(f"unknown placeholder  {f}: {ph}")
            bad += 1
    sys.exit(1 if bad else 0)


def cmd_roundtrip(args):
    terms, private = load(args.profile)
    bad = 0
    for rel in paths(args):
        if rel in private:
            continue
        orig = read(Path(args.src) / rel).replace('\r\n', '\n')
        if apply_text(strip_text(orig, terms), terms) != orig:
            print(f"not reversible: {rel}")
            bad += 1
    print('roundtrip ok' if not bad else f'{bad} file(s) not reversible')
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('strip'); p.add_argument('--profile', required=True); p.add_argument('--src', required=True)
    p.add_argument('--dst', required=True); p.add_argument('--paths-from', required=True)
    p = sub.add_parser('apply'); p.add_argument('--profile', required=True); p.add_argument('files', nargs='+')
    p = sub.add_parser('get'); p.add_argument('--profile', required=True); p.add_argument('name')
    p = sub.add_parser('check'); p.add_argument('--profile', required=True); p.add_argument('dir')
    p = sub.add_parser('roundtrip'); p.add_argument('--profile', required=True); p.add_argument('--src', required=True)
    p.add_argument('--paths-from', required=True)
    args = ap.parse_args()
    {'strip': cmd_strip, 'get': cmd_get, 'apply': cmd_apply, 'check': cmd_check, 'roundtrip': cmd_roundtrip}[args.cmd](args)


if __name__ == '__main__':
    main()
