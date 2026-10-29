#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Jenkins 发布脚本

按当前 Git 仓库找到对应的 Jenkins 任务，从当前分支 / 标签推断构建参数，
先模拟运行给人确认，确认码一致后才触发构建，并可后台监控构建结果。

Jenkins 地址和凭据只来自环境变量或用户自己的配置文件，脚本里不内置任何服务器地址。
只依赖 Python 3.8+ 标准库。

改编自 ABCFed/claude-marketplace 的 jenkins-deploy（MIT License）。
"""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


# ============================================================================
# 配置常量
# ============================================================================

CONFIG_FILE = Path(os.environ.get(
    'JENKINS_DEPLOY_CONFIG', Path.home() / '.config' / 'jenkins-deploy' / 'config.json'))
CACHE_DIR = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'jenkins-deploy'
PROJECT_FILE = '.jenkins-deploy.json'   # 仓库根目录的项目配置：{"job": "team/svc-dev"}
CACHE_TTL = 24 * 3600          # 任务列表缓存 24 小时
MAX_FOLDER_DEPTH = 4           # 递归扫描 Jenkins 文件夹的最大深度

# 按参数名识别分支 / 标签 / 仓库地址参数（大小写敏感，与 Jenkins 里的参数名一致）
BRANCH_PARAMS = ['repoBranch', 'BRANCH', 'GIT_BRANCH', 'BRANCH_NAME', 'branch']
TAG_PARAMS = ['repoTag', 'TAG', 'GIT_TAG', 'tag']
REPO_PARAMS = ['repoUrl', 'REPO_URL', 'GIT_URL', 'gitUrl']
READONLY_TYPES = {'WReadonlyStringParameterDefinition'}


class DeployError(Exception):
    """可预期的错误：只打印信息，不打印堆栈"""


# ============================================================================
# 工具函数
# ============================================================================

def print_colored(message: str, color: str = 'white') -> None:
    """打印彩色输出（终端支持时）"""
    colors = {'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m', 'blue': '\033[94m'}
    if sys.stdout.isatty() and color in colors:
        print(f"{colors[color]}{message}\033[0m")
    else:
        print(message)


def run_git(args: List[str]) -> str:
    """执行 git 命令，失败返回空字符串"""
    try:
        return subprocess.check_output(['git'] + args, stderr=subprocess.DEVNULL).decode('utf-8').strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ''


def send_notification(title: str, message: str) -> None:
    """发送桌面通知；参数作为独立的 argv 传入，不拼接进脚本，避免注入"""
    try:
        if shutil.which('terminal-notifier'):
            cmd = ['terminal-notifier', '-title', title, '-message', message, '-group', 'jenkins-build']
        elif shutil.which('notify-send'):
            cmd = ['notify-send', title, message]
        elif shutil.which('osascript'):
            cmd = ['osascript',
                   '-e', 'on run argv',
                   '-e', 'display notification (item 2 of argv) with title (item 1 of argv)',
                   '-e', 'end run', title, message]
        else:
            return
        subprocess.run(cmd, check=False, capture_output=True, timeout=5)
    except Exception:
        pass  # 通知失败不影响主流程


# ============================================================================
# 配置读取
# ============================================================================

class Config:
    def __init__(self, url: str, user: str, token: str, folders: List[str]):
        self.url = url
        self.auth = (user, token)
        self.folders = folders


def load_config() -> Config:
    """
    读取 Jenkins 配置
    优先级: 环境变量 > ~/.config/jenkins-deploy/config.json
    """
    file_cfg: Dict = {}
    if CONFIG_FILE.exists():
        if os.name != 'nt' and CONFIG_FILE.stat().st_mode & 0o077:
            print_colored(f"⚠ {CONFIG_FILE} 对其他用户可读，建议执行: chmod 600 {CONFIG_FILE}", 'yellow')
        try:
            file_cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as e:
            raise DeployError(f"读取配置文件失败 {CONFIG_FILE}: {e}")

    url = os.environ.get('JENKINS_URL') or file_cfg.get('url', '')
    user = os.environ.get('JENKINS_USER') or file_cfg.get('user', '')
    token = os.environ.get('JENKINS_TOKEN') or file_cfg.get('token', '')
    folders_env = os.environ.get('JENKINS_FOLDERS')
    folders = [f.strip().strip('/') for f in folders_env.split(',')] if folders_env else file_cfg.get('folders', [])
    allow_http = os.environ.get('JENKINS_ALLOW_HTTP') == '1' or file_cfg.get('allow_http') is True

    missing = [name for name, value in (('url', url), ('user', user), ('token', token)) if not value]
    if missing:
        raise DeployError(
            f"缺少 Jenkins 配置: {', '.join(missing)}\n"
            f"在 {CONFIG_FILE} 中写入（并 chmod 600）:\n"
            '  {"url": "https://jenkins.example.com", "user": "<用户名>", "token": "<API Token>"}\n'
            "或设置环境变量 JENKINS_URL / JENKINS_USER / JENKINS_TOKEN"
        )
    if not re.match(r'^https?://', url):
        raise DeployError(f"Jenkins 地址必须以 https:// 开头: {url}")
    if url.startswith('http://') and not allow_http:
        raise DeployError(
            f"拒绝通过明文 HTTP 发送凭据: {url}\n"
            "请改用 https；确实只能用 http 的内网环境，设置 JENKINS_ALLOW_HTTP=1 或在配置文件中加 \"allow_http\": true"
        )
    return Config(url.rstrip('/') + '/', user, token, [f for f in folders if f])


def job_url(cfg: Config, full_name: str) -> str:
    """team/svc-dev -> <url>/job/team/job/svc-dev/"""
    return cfg.url + ''.join(f"job/{quote(part, safe='')}/" for part in full_name.split('/'))


class Response:
    def __init__(self, status_code: int, headers, body: bytes):
        self.status_code = status_code
        self.headers = headers
        self.text = body.decode('utf-8', errors='replace')

    def json(self):
        return json.loads(self.text)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # 不跟随跳转：带凭据的请求只发给配置的 Jenkins 地址


_opener = build_opener(_NoRedirect)


def http(cfg: Config, method: str, url: str, params: Optional[Dict] = None,
         data: Optional[Dict] = None, timeout: int = 15) -> Response:
    if params:
        url += '?' + urlencode(params)
    body = urlencode(data or {}).encode('utf-8') if method == 'POST' else None
    request = Request(url, data=body, method=method)
    token = base64.b64encode(f"{cfg.auth[0]}:{cfg.auth[1]}".encode('utf-8')).decode('ascii')
    request.add_header('Authorization', f'Basic {token}')
    if body is not None:
        request.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with _opener.open(request, timeout=timeout) as resp:
            return Response(resp.status, resp.headers, resp.read())
    except HTTPError as e:
        return Response(e.code, e.headers, e.read() or b'')
    except (URLError, OSError) as e:
        raise DeployError(f"连接 Jenkins 失败: {getattr(e, 'reason', e)}")


def jenkins_get(cfg: Config, url: str, **params) -> Response:
    response = http(cfg, 'GET', url, params=params)
    if response.status_code in (401, 403):
        raise DeployError(f"Jenkins 拒绝访问 (HTTP {response.status_code})，请检查用户名和 API Token")
    return response


# ============================================================================
# Git 信息获取
# ============================================================================

def get_git_info() -> Dict[str, str]:
    """获取当前 Git 仓库信息"""
    if not run_git(['rev-parse', '--git-dir']):
        raise DeployError("当前目录不是 Git 仓库")
    branch = run_git(['rev-parse', '--abbrev-ref', 'HEAD'])
    if branch == 'HEAD':
        branch = ''  # detached HEAD
    remote = (run_git(['config', f'branch.{branch}.remote']) if branch else '') or 'origin'
    # 只取指向当前提交的标签；不用"最近的标签"，否则可能把旧版本当成本次发布
    tags = run_git(['tag', '--points-at', 'HEAD']).splitlines()
    return {
        'branch': branch,
        'tag': tags[-1] if tags else '',
        'head': run_git(['rev-parse', 'HEAD']),
        'remote': remote,
        'remote_url': run_git(['remote', 'get-url', remote]),
        'dirty': run_git(['status', '--porcelain']),
    }


def project_default_job() -> str:
    """仓库根目录 .jenkins-deploy.json 里的默认任务，团队共用，可以提交"""
    root = run_git(['rev-parse', '--show-toplevel'])
    path = Path(root) / PROJECT_FILE if root else None
    if not path or not path.exists():
        return ''
    try:
        return str(json.loads(path.read_text(encoding='utf-8')).get('job', '')).strip()
    except (OSError, json.JSONDecodeError) as e:
        raise DeployError(f"读取 {path} 失败: {e}")


def normalize_remote(url: str) -> str:
    """把 SSH / HTTPS 形式的 Git 地址统一成 host/path，用于比较是否同一仓库"""
    url = url.strip()
    m = re.match(r'^[\w.-]+@([^:/]+):(.+)$', url)                        # git@host:group/repo.git
    if not m:
        m = re.match(r'^(?:ssh|https?|git)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$', url)
    host, path = (m.group(1), m.group(2)) if m else ('', url)
    path = re.sub(r'\.git$', '', path.strip('/'))
    return f"{host.lower()}/{path}" if host else path


# ============================================================================
# Jenkins 任务列表
# ============================================================================

def cache_file(cfg: Config) -> Path:
    # 按 Jenkins 地址区分缓存，切换服务器不会读到别家的任务
    return CACHE_DIR / f"jobs-{hashlib.sha256(cfg.url.encode()).hexdigest()[:12]}.json"


def get_jenkins_projects(cfg: Config, refresh: bool = False) -> List[Dict]:
    """获取 Jenkins 任务列表，优先读 24 小时内的缓存"""
    path = cache_file(cfg)
    if not refresh and path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if time.time() - data.get('cached_at', 0) < CACHE_TTL and data.get('folders') == cfg.folders:
                return data['projects']
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    print("正在从 Jenkins 获取任务列表...", file=sys.stderr)
    projects = fetch_projects_from_jenkins(cfg)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(CACHE_DIR, 0o700)
        path.write_text(json.dumps({'cached_at': time.time(), 'folders': cfg.folders, 'projects': projects},
                                   ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        pass
    return projects


def fetch_projects_from_jenkins(cfg: Config) -> List[Dict]:
    """递归扫描配置的文件夹（未配置时扫描整个 Jenkins），读取每个任务的参数定义"""
    full_names: List[str] = []

    def walk(folder: str, depth: int) -> None:
        url = (job_url(cfg, folder) if folder else cfg.url) + 'api/json'
        response = jenkins_get(cfg, url, tree='jobs[name,fullName,_class]')
        if response.status_code != 200:
            print_colored(f"⚠ 读取文件夹失败 {folder or '/'} (HTTP {response.status_code})", 'yellow')
            return
        for job in response.json().get('jobs', []):
            cls = job.get('_class', '')
            name = job.get('fullName') or (f"{folder}/{job['name']}" if folder else job['name'])
            if 'MultiBranch' in cls or cls.endswith('OrganizationFolder'):
                continue  # 多分支流水线不支持参数化触发
            if cls.endswith('Folder'):
                if depth < MAX_FOLDER_DEPTH:
                    walk(name, depth + 1)
            else:
                full_names.append(name)

    for folder in cfg.folders or ['']:
        walk(folder, 0)

    projects = []
    tree = ('name,fullName,property[parameterDefinitions'
            '[name,type,description,choices,defaultParameterValue[value]]]')
    for full_name in full_names:
        try:
            response = jenkins_get(cfg, job_url(cfg, full_name) + 'api/json', tree=tree)
            if response.status_code == 200:
                projects.append(parse_job_config(response.json()))
        except (DeployError, json.JSONDecodeError) as e:
            if 'HTTP 401' in str(e) or 'HTTP 403' in str(e):
                raise
            continue
    return projects


def parse_job_config(job_data: Dict) -> Dict:
    """解析 Jenkins 任务的参数定义"""
    job = {'name': job_data.get('name', ''), 'full_name': job_data.get('fullName', ''), 'git': '', 'parameters': []}
    for prop in job_data.get('property', []):
        for param_def in prop.get('parameterDefinitions', []) or []:
            default = (param_def.get('defaultParameterValue') or {}).get('value', '')
            if isinstance(default, bool):
                default = 'true' if default else 'false'
            param = {
                'name': param_def.get('name', ''),
                'description': param_def.get('description') or '',
                'type': param_def.get('type', ''),
                'default_value': '' if default is None else str(default),
                'choices': param_def.get('choices') or [],
            }
            # 识别仓库地址参数，用于按当前 Git 仓库筛选任务
            if not job['git'] and (param['name'] in REPO_PARAMS or re.search(r'\.git$', param['default_value'])):
                job['git'] = param['default_value']
            job['parameters'].append(param)
    return job


def filter_projects_by_git(projects: List[Dict], remote_url: str) -> List[Dict]:
    if not remote_url:
        return []
    target = normalize_remote(remote_url)
    return [p for p in projects if p.get('git') and normalize_remote(p['git']) == target]


def find_project(projects: List[Dict], name: str) -> Dict:
    matches = [p for p in projects if p['full_name'] == name] or [p for p in projects if p['name'] == name]
    if not matches:
        raise DeployError(f"未找到任务: {name}（可用 --list --all 查看，或加 --refresh 刷新缓存）")
    if len(matches) > 1:
        raise DeployError(f"任务名 {name} 不唯一，请用完整路径: " + ', '.join(p['full_name'] for p in matches))
    return matches[0]


# ============================================================================
# 参数推断与校验
# ============================================================================

def build_parameters(project: Dict, git_info: Dict, provided: Dict) -> Dict[str, str]:
    """
    计算最终提交给 Jenkins 的参数：用户提供 > 当前分支 / 标签 > 任务默认值
    只读参数不提交，由 Jenkins 使用默认值
    """
    result = {}
    for param in project['parameters']:
        name, choices = param['name'], param['choices']
        if param['type'] in READONLY_TYPES:
            continue
        if name in provided:
            value = provided[name]
            result[name] = ','.join(map(str, value)) if isinstance(value, list) else str(value)
        elif name in BRANCH_PARAMS and git_info.get('branch'):
            result[name] = git_info['branch']
        elif name in TAG_PARAMS and git_info.get('tag'):
            result[name] = git_info['tag']
        elif param['default_value']:
            result[name] = param['default_value']
        elif choices:
            result[name] = next((c for c in choices if c.strip()), '')
        else:
            result[name] = ''
    return result


def check_parameters(project: Dict, params: Dict[str, str], provided: Dict,
                     git_info: Dict) -> Tuple[List[str], List[str], Dict[str, str]]:
    """返回 (错误, 警告, 分支/标签参数对应的远端提交)；有错误时不允许触发"""
    errors, warnings, revisions = [], [], {}
    defs = {p['name']: p for p in project['parameters']}

    for name in provided:
        if name not in defs:
            errors.append(f"任务没有参数 {name}（拼写错误？现有参数: {', '.join(defs) or '无'}）")
        elif defs[name]['type'] in READONLY_TYPES:
            errors.append(f"参数 {name} 是只读参数，不能修改")

    for name, value in params.items():
        param = defs[name]
        if param['type'] == 'ChoiceParameterDefinition' and param['choices'] and value not in param['choices']:
            errors.append(f"参数 {name} 的值 {value!r} 不在可选项中: {param['choices']}")
        if value == '':
            warnings.append(f"参数 {name} 为空" + (f"（{param['description']}）" if param['description'] else ''))

    # 分支 / 标签是否已推送到远端：Jenkins 只能拉到远端的代码
    remote = git_info.get('remote', 'origin')
    for name, value in params.items():
        if name in BRANCH_PARAMS and value:
            remote_sha = run_git(['ls-remote', remote, f'refs/heads/{value}']).split('\t')[0]
            if not remote_sha:
                errors.append(f"远端 {remote} 上没有分支 {value}，请先 push")
                continue
            revisions[name] = remote_sha
            if value == git_info.get('branch') and remote_sha != git_info.get('head'):
                warnings.append(f"本地 {git_info['head'][:7]} 与远端 {remote_sha[:7]} 不一致，Jenkins 会构建远端版本")
        if name in TAG_PARAMS and value:
            tag_refs = run_git(['ls-remote', '--tags', remote, f'refs/tags/{value}', f'refs/tags/{value}^{{}}'])
            if not tag_refs:
                errors.append(f"远端 {remote} 上没有标签 {value}，请先 push 标签")
            else:
                # 附注标签取 ^{} 那一行，才是标签指向的提交
                revisions[name] = tag_refs.splitlines()[-1].split('\t')[0]
    if any(n in TAG_PARAMS for n in defs) and not git_info.get('tag') and not any(n in provided for n in TAG_PARAMS):
        warnings.append("当前提交上没有标签，标签参数使用的是任务默认值")
    if git_info.get('dirty'):
        warnings.append("工作区有未提交的改动，不会包含在这次构建里")
    return errors, warnings, revisions


def confirm_code(cfg: Config, project: Dict, params: Dict[str, str], revisions: Dict[str, str]) -> str:
    """任务 + 参数 + 远端提交的指纹：触发时必须与模拟运行展示给人确认的完全一致"""
    payload = json.dumps({'url': cfg.url, 'job': project['full_name'], 'params': params, 'revisions': revisions},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:8]


def print_plan(cfg: Config, project: Dict, params: Dict[str, str], revisions: Dict[str, str],
               errors: List[str], warnings: List[str], code: str) -> None:
    readonly = [p['name'] for p in project['parameters'] if p['type'] in READONLY_TYPES]
    print("=" * 60)
    print(f"任务:   {project['full_name']}")
    print(f"地址:   {job_url(cfg, project['full_name'])}")
    print("参数:")
    for name, value in params.items():
        print(f"  {name} = {value}")
    for name, sha in revisions.items():
        subject = run_git(['log', '-1', '--format=%s（%an，%cr）', sha]) or '本地没有这个提交，可先 git fetch 查看'
        print(f"提交:   {params[name]} @ {sha[:7]}  {subject}")
    if readonly:
        print(f"只读参数（使用 Jenkins 默认值）: {', '.join(readonly)}")
    for w in warnings:
        print_colored(f"⚠ {w}", 'yellow')
    for e in errors:
        print_colored(f"✗ {e}", 'red')
    if not errors:
        print(f"确认码: {code}")
    print("=" * 60)


# ============================================================================
# 构建 API
# ============================================================================

def trigger_build(cfg: Config, project: Dict, params: Dict[str, str]) -> int:
    """触发构建，返回队列 ID"""
    endpoint = 'buildWithParameters' if project['parameters'] else 'build'
    response = http(cfg, 'POST', job_url(cfg, project['full_name']) + endpoint, data=params, timeout=30)
    match = re.search(r'/queue/item/(\d+)', response.headers.get('Location') or '')
    if response.status_code in (200, 201, 302) and match:
        return int(match.group(1))
    raise DeployError(f"触发构建失败 (HTTP {response.status_code}): {response.text[:300]}")


def wait_for_build_start(cfg: Config, project: Dict, queue_id: int, timeout: int = 300) -> Optional[int]:
    """等待任务出队列，返回构建号"""
    start = time.time()
    while time.time() - start < timeout:
        response = jenkins_get(cfg, f"{cfg.url}queue/item/{queue_id}/api/json")
        if response.status_code == 200:
            data = response.json()
            if data.get('cancelled'):
                print("任务已在队列中被取消")
                return None
            if (data.get('executable') or {}).get('number'):
                return data['executable']['number']
            if data.get('why'):
                print(f"排队中: {data['why']}", flush=True)
        elif response.status_code == 404:
            # 队列项已被清理：按 queueId 精确找回构建，不按时间猜测
            response = jenkins_get(cfg, job_url(cfg, project['full_name']) + 'api/json',
                                   tree='builds[number,queueId]{0,20}')
            for build in response.json().get('builds', []) if response.status_code == 200 else []:
                if build.get('queueId') == queue_id:
                    return build['number']
        time.sleep(3)
    print("等待排队超时")
    return None


def monitor_build(cfg: Config, project: Dict, queue_id: int, timeout: int = 3600) -> str:
    """监控构建直到结束；只观察，结束监控不会停止 Jenkins 上的构建"""
    print(f"📊 开始监控: {project['full_name']} (Queue ID: {queue_id})", flush=True)
    build_number = wait_for_build_start(cfg, project, queue_id)
    if build_number is None:
        send_notification("Jenkins 构建未开始", project['name'])
        return 'NOT_STARTED'

    build_url = f"{job_url(cfg, project['full_name'])}{build_number}/"
    print(f"📦 构建号: #{build_number}  {build_url}", flush=True)
    start = time.time()
    result = 'UNKNOWN'
    while time.time() - start < timeout:
        response = jenkins_get(cfg, build_url + 'api/json', tree='result,building,estimatedDuration')
        if response.status_code == 200:
            data = response.json()
            if data.get('result'):
                result = data['result']
                break
            elapsed = int(time.time() - start)
            estimated = data.get('estimatedDuration') or 0
            if estimated > 0:
                progress = min(elapsed * 1000 / estimated, 0.99)
                bar = '█' * int(30 * progress) + '░' * (30 - int(30 * progress))
                print(f"⏳ [{bar}] {int(progress * 100)}% ({elapsed}s)", flush=True)
            else:
                print(f"⏳ 构建中 ({elapsed}s)", flush=True)
        time.sleep(5)

    icon = {'SUCCESS': '✅', 'FAILURE': '❌', 'ABORTED': '⚠️'}.get(result, '⏱️')
    print(f"\n{icon} {project['name']} #{build_number}: {result}\n构建地址: {build_url}", flush=True)
    send_notification(f"Jenkins 构建 {result}", f"{project['name']} #{build_number}")
    return result


def stop_build(cfg: Config, full_name: str, build_number: int) -> None:
    url = f"{job_url(cfg, full_name)}{build_number}/stop"
    response = http(cfg, 'POST', url)
    if response.status_code not in (200, 302):
        raise DeployError(f"停止构建失败 (HTTP {response.status_code})")
    print(f"✓ 已发送停止请求: {full_name} #{build_number}")


# ============================================================================
# 交互式模式（仅供人在终端里直接使用）
# ============================================================================

def interactive(cfg: Config, project: Dict, params: Dict[str, str], provided: Dict, git_info: Dict) -> None:
    print("\n逐项确认参数（直接回车使用当前值）:")
    for param in project['parameters']:
        name = param['name']
        if name not in params or name in provided:
            continue
        hint = f" - {param['description']}" if param['description'] else ''
        if param['choices']:
            hint += f" 可选: {'/'.join(param['choices'])}"
        value = input(f"  {name}{hint} [{params[name]}]: ").strip()
        if value:
            params[name] = value
            provided[name] = value

    errors, warnings, revisions = check_parameters(project, params, provided, git_info)
    print_plan(cfg, project, params, revisions, errors, warnings, confirm_code(cfg, project, params, revisions))
    if errors:
        raise DeployError("参数有错误，已取消")
    if input("确认触发构建？(y/n): ").strip().lower() not in ('y', 'yes', '是'):
        print("已取消")
        return
    queue_id = trigger_build(cfg, project, params)
    monitor_build(cfg, project, queue_id)


# ============================================================================
# 主函数
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description='Jenkins 发布工具')
    parser.add_argument('project', nargs='?', help='Jenkins 任务名或完整路径（如 team/svc-dev）')
    parser.add_argument('--list', '-l', action='store_true', help='列出与当前 Git 仓库相关的任务')
    parser.add_argument('--all', '-a', action='store_true', help='配合 --list 列出全部任务')
    parser.add_argument('--refresh', '-r', action='store_true', help='忽略缓存，重新从 Jenkins 读取任务')
    parser.add_argument('--params', help='JSON 格式的参数，覆盖推断值')
    parser.add_argument('--branch', help='覆盖分支参数')
    parser.add_argument('--tag', help='覆盖标签参数')
    parser.add_argument('--dry-run', action='store_true', help='只计算并展示参数和确认码，不触发')
    parser.add_argument('--trigger', metavar='CONFIRM_CODE', help='用模拟运行给出的确认码触发构建，输出 JSON')
    parser.add_argument('--monitor-only', action='store_true', help='监控已触发的构建（需 --full-name 和 --queue-id）')
    parser.add_argument('--full-name', help='任务完整路径（监控 / 停止时使用）')
    parser.add_argument('--queue-id', type=int, help='队列 ID（监控时使用）')
    parser.add_argument('--stop', type=int, metavar='BUILD_NUMBER', help='停止指定构建（需 --full-name）')
    args = parser.parse_args()

    cfg = load_config()

    if args.stop:
        if not args.full_name:
            raise DeployError("--stop 需要同时指定 --full-name <任务完整路径>")
        stop_build(cfg, args.full_name, args.stop)
        return

    if args.monitor_only:
        if not args.full_name or not args.queue_id:
            raise DeployError("--monitor-only 需要 --full-name 和 --queue-id")
        project = find_project(get_jenkins_projects(cfg), args.full_name)
        result = monitor_build(cfg, project, args.queue_id)
        sys.exit(0 if result == 'SUCCESS' else 1)

    git_info = get_git_info()
    projects = get_jenkins_projects(cfg, args.refresh)

    if args.list:
        shown = projects if args.all else filter_projects_by_git(projects, git_info['remote_url'])
        if not shown:
            print("未找到与当前 Git 仓库相关的任务" if not args.all else "未找到任何任务")
            if not args.all:
                print("提示: 加 --all 查看全部任务；任务需要有仓库地址参数（如 repoUrl）才能按仓库匹配")
            return
        for p in sorted(shown, key=lambda p: p['full_name']):
            print(f"  - {p['full_name']}")
        return

    default_job = project_default_job()
    if not args.project and default_job:
        project = find_project(projects, default_job)
    elif not args.project:
        related = filter_projects_by_git(projects, git_info['remote_url'])
        if len(related) != 1:
            names = ', '.join(p['full_name'] for p in related) or '无'
            raise DeployError(f"请指定任务名，或在仓库根目录的 {PROJECT_FILE} 里写 {{\"job\": \"<任务路径>\"}}。"
                              f"与当前仓库相关的任务: {names}")
        project = related[0]
    else:
        project = find_project(projects, args.project)

    try:
        provided = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as e:
        raise DeployError(f"--params 不是合法的 JSON: {e}")
    if not isinstance(provided, dict):
        raise DeployError("--params 必须是 JSON 对象")
    names = {p['name'] for p in project['parameters']}
    if args.branch:
        provided[next((n for n in BRANCH_PARAMS if n in names), 'repoBranch')] = args.branch
    if args.tag:
        provided[next((n for n in TAG_PARAMS if n in names), 'repoTag')] = args.tag

    params = build_parameters(project, git_info, provided)
    errors, warnings, revisions = check_parameters(project, params, provided, git_info)
    code = confirm_code(cfg, project, params, revisions)

    if args.dry_run:
        print_plan(cfg, project, params, revisions, errors, warnings, code)
        sys.exit(1 if errors else 0)

    if args.trigger:
        if errors:
            print_plan(cfg, project, params, revisions, errors, warnings, code)
            raise DeployError("参数有错误，未触发")
        if args.trigger != code:
            raise DeployError("确认码不一致：任务、参数或远端提交与确认时不同。请重新 --dry-run 并让用户确认")
        queue_id = trigger_build(cfg, project, params)
        print(json.dumps({'queue_id': queue_id, 'full_name': project['full_name'],
                          'job_url': job_url(cfg, project['full_name'])}, ensure_ascii=False))
        return

    if not sys.stdin.isatty():
        raise DeployError("非交互环境请使用 --dry-run 查看参数，确认后用 --trigger <确认码> 触发")
    interactive(cfg, project, params, provided, git_info)


if __name__ == '__main__':
    try:
        main()
    except DeployError as e:
        print_colored(f"✗ {e}", 'red')
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(130)
