"""Test double for the mysql CLI in --batch mode (used by tests only).

Reads CSV files from the folder in env FAKE_MYSQL_DIR and prints them the way `mysql --batch`
does: tab-separated, header line, NULL for empty, and \\t \\n \\\\ escaped inside values.
"""
import csv, os, sys

sql = sys.argv[sys.argv.index('-e') + 1] if '-e' in sys.argv else ''
folder = os.environ['FAKE_MYSQL_DIR']
name = 'xxl_jobs' if 'xxl_job_info' in sql else 'indexes' if 'statistics' in sql else 'columns' if '.columns' in sql else 'tables'
path = os.path.join(folder, name + '.csv')
if not os.path.exists(path):
    sys.stderr.write(f"ERROR 1146 (42S02): Table '{name}' doesn't exist\n")
    sys.exit(1)


def esc(v):
    if v == '': return 'NULL'
    return v.replace('\\', '\\\\').replace('\t', '\\t').replace('\r', '\\r').replace('\n', '\\n')


with open(path, encoding='utf-8-sig', newline='') as f:
    rows = list(csv.reader(f))
out = sys.stdout.buffer
for r in rows:
    out.write(('\t'.join(r if r is rows[0] else [esc(v) for v in r]) + '\n').encode('utf-8'))
