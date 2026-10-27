"""Self-checks: catch configuration that no longer matches the repo or the metadata
before they silently produce a wrong page."""
import os, subprocess


def check_config(cfg, logical):
    warnings = []
    repo = cfg['repo']
    if not os.path.isdir(repo):
        return [f'代码仓库不存在：{repo}']
    dbs = {e['schema'] for e in logical}
    keys = {f"{e['schema']}.{e['table']}" for e in logical}
    dbc = cfg['databases']
    for name in cfg['modules']['external']:
        if not os.path.isdir(os.path.join(repo, name)):
            warnings.append(f'配置的外部模块 {name} 在仓库里不存在')
    for db in dbc['report']:
        if db not in dbs:
            warnings.append(f'配置的报表库 {db} 不在元数据里（换库了？报表会被当成业务表）')
    for label, mapping in (('mapper_package_db', dbc.get('mapper_package_db', {})), ('module_db', dbc.get('module_db', {}))):
        missing = sorted({db for db in mapping.values() if db not in dbs})
        if missing:
            warnings.append(f'{label} 里引用的库不在元数据里：{", ".join(missing)}（同名表的库归属可能判错）')
    for k in dbc.get('report_tables_outside', []) + dbc.get('report_exclude', []) + dbc.get('verify_log_tables', []) + cfg.get('er', {}).get('core_tables', []):
        if k not in keys:
            warnings.append(f'配置里的表 {k} 在元数据里不存在')
    for module in dbc.get('module_db', {}):
        if not os.path.isdir(os.path.join(repo, module)):
            warnings.append(f'module_db 里的模块 {module} 在仓库里不存在')
    return warnings


def check_scan(scan, logical, prev_stats=None):
    """Sanity of the scanner output itself: sudden drops usually mean a parsing break."""
    warnings = []
    st = scan.get('stats', {})
    kinds = {}
    for e in scan['entries']:
        kinds[e['kind']] = kinds.get(e['kind'], 0) + 1
    if not kinds.get('kafka') and not kinds.get('http'):
        warnings.append('扫描结果里没有任何 Kafka 监听或 HTTP 入口，扫描很可能失败了')
    known = {e['table'] for e in logical}
    referenced = {x['table'] for e in scan['entries'] for x in e['tables']}
    if referenced:
        hit = len(referenced & known) / len(referenced)
        if hit < 0.6:
            warnings.append(f'代码里引用的表只有 {hit:.0%} 能在元数据里找到（元数据是不是导错库了？）')
    if st.get('cdc_configured') and not st.get('cdc_lists'):
        warnings.append('配置了 cdc.table_ref_type，但代码里没有找到任何订阅清单（类型名写错了？）')
    elif st.get('cdc_configured') and not st.get('cdc_listeners'):
        warnings.append('找到了订阅清单，但没有任何 Kafka 监听解析出订阅表（检查 cdc.registry_class 是否是声明清单的类名、check_method 是否正确）')
    if prev_stats:
        for k in ('classes', 'methods'):
            if prev_stats.get(k) and st.get(k, 0) < prev_stats[k] * 0.8:
                warnings.append(f'解析到的 {k} 数量从 {prev_stats[k]} 降到 {st.get(k, 0)}，降幅超过 20%')
    return warnings


def git_info(repo):
    def run(*args):
        try:
            return subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:
            return ''
    return {'commit': run('rev-parse', '--short', 'HEAD') or 'unknown',
            'branch': run('rev-parse', '--abbrev-ref', 'HEAD') or 'unknown',
            'dirty': bool(run('status', '--porcelain', '--untracked-files=no'))}
