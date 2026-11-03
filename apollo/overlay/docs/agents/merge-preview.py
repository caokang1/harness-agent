#!/usr/bin/env python3
"""
Preview merging a feature branch into an integration branch and sort the conflicts.

  python3 docs/agents/merge-preview.py [feature] [integration] [--base origin/master_xx]

  feature      default: current branch
  integration  default: origin/{{AP_INTEGRATION_BRANCH}}
  --base       default: whichever of origin/{{AP_MAIN_BRANCH}}, origin/{{AP_SUBLINE_BRANCH}}, origin/master_<cc> is nearest

Conflicts are split into:
  pre-existing  the base branch alone already conflicts with the integration branch on that file
                (e.g. country commits not yet in the integration branch); not caused by this change
  introduced    only appear because of the feature's own commits; read these carefully
For every conflict hunk it also reports whether one side already contains every line of the other,
which is when "take that side" loses nothing. Nothing is written: no checkout, no merge, no push.
"""
import argparse
import re
import subprocess
import sys


def git(*args, check=True):
    r = subprocess.run(['git', *args], capture_output=True, text=True)
    if check and r.returncode not in (0, 1):
        sys.exit(f"✗ git {' '.join(args)}: {r.stderr.strip()}")
    return r


def conflicts(ours, theirs):
    r = git('merge-tree', '--write-tree', '--name-only', ours, theirs)
    lines = r.stdout.splitlines()
    tree = lines[0] if lines else ''
    files = []
    for line in lines[1:]:
        if not line.strip():
            break
        files.append(line.strip())
    return tree, files


def nearest_base(feature):
    refs = git('for-each-ref', '--format=%(refname:short)', 'refs/remotes/origin/').stdout.split()
    cands = [r for r in refs if re.fullmatch(r'origin/master_(multi|{{AP_SUBLINE}}|[a-z]{2}\d?)', r)]
    best = min(cands, key=lambda r: int(git('rev-list', '--count', f'{r}..{feature}').stdout.strip() or 1 << 30))
    return best


def hunk_report(tree, path, integration):
    text = git('show', f'{tree}:{path}').stdout.replace('\r', '')
    integ = {x.strip() for x in git('show', f'{integration}:{path}').stdout.replace('\r', '').split('\n')}
    out, ours, theirs, state = [], [], [], None
    for line in text.split('\n'):
        if line.startswith('<<<<<<< '):
            ours, theirs, state = [], [], 'ours'
        elif line.startswith('=======') and state == 'ours':
            state = 'theirs'
        elif line.startswith('>>>>>>> ') and state == 'theirs':
            o, t = {x.strip() for x in ours if x.strip()}, {x.strip() for x in theirs if x.strip()}
            if t <= o or t <= integ:
                verdict = 'integration side already has every line of the incoming side → take integration side'
            elif o <= t:
                verdict = 'incoming side already has every line of the integration side → take incoming side'
            else:
                verdict = 'both sides have their own lines → merge by hand'
            out.append(f"      hunk {len(out) + 1}: {len(ours)} vs {len(theirs)} lines; {verdict}")
            state = None
        elif state == 'ours':
            ours.append(line)
        elif state == 'theirs':
            theirs.append(line)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('feature', nargs='?')
    ap.add_argument('integration', nargs='?', default='origin/{{AP_INTEGRATION_BRANCH}}')
    ap.add_argument('--base')
    a = ap.parse_args()
    feature = a.feature or git('rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
    git('fetch', '-q', 'origin', check=False)
    base = a.base or nearest_base(feature)
    print(f"feature {feature} → {a.integration} (base {base})")

    tree, feat_conf = conflicts(a.integration, feature)
    _, base_conf = conflicts(a.integration, base)
    if not feat_conf:
        print("✓ no conflicts")
        return
    pre = [f for f in feat_conf if f in base_conf]
    own = [f for f in feat_conf if f not in base_conf]
    if own:
        print(f"\n⚠ introduced by {feature} ({len(own)}):")
        for f in own:
            print(f"  {f}")
            print('\n'.join(hunk_report(tree, f, a.integration)))
    if pre:
        print(f"\nℹ pre-existing between {base} and {a.integration} ({len(pre)}), not caused by this change:")
        for f in pre:
            last = git('log', '-1', '--format=%h %s', f'{a.integration}..{base}', '--', f).stdout.strip()
            print(f"  {f}   (last base-only commit: {last or '-'})")
            print('\n'.join(hunk_report(tree, f, a.integration)))
    sys.exit(2 if own else 0)


if __name__ == '__main__':
    main()
