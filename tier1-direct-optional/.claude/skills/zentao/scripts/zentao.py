#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
禅道（ZenTao）任务 / Bug 助手

读取任务和 Bug 的内容，开始任务，按 AI 实际工作时间累计工时，
经用户确认后完成任务或解决 Bug。调用禅道 REST API v1（禅道 18+，已在 21.3 开源版接口上核对）。

只依赖 Python 3.8+ 标准库。禅道地址和账号只来自用户自己的配置，脚本里不内置任何服务器地址。
"""

import argparse
import hashlib
import html
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None


# ============================================================================
# 配置常量
# ============================================================================

CONFIG_FILE = Path(os.environ.get('ZENTAO_CONFIG', Path.home() / '.config' / 'zentao' / 'config.json'))
CACHE_DIR = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'zentao'
LONG_SEGMENT = 2 * 3600     # 单段超过 2 小时，大概率是没有正常结束，展示时标出来


class ZentaoError(Exception):
    """可预期的错误：只打印信息，不打印堆栈"""


def now_str() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def write_private(path: Path, text: str) -> None:
    """原子写入，并且只有本人可读"""
    tmp = path.with_suffix(path.suffix + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, path)


# ============================================================================
# 配置与认证
# ============================================================================

class Config:
    def __init__(self, url: str, account: str, password: str):
        self.url = url
        self.api = url + '/api.php/v1'
        self.account = account
        self.password = password


def load_config() -> Config:
    """优先级: 环境变量 > ~/.config/zentao/config.json"""
    file_cfg: Dict = {}
    if CONFIG_FILE.exists():
        if os.name != 'nt' and CONFIG_FILE.stat().st_mode & 0o077:
            print(f"⚠ {CONFIG_FILE} 对其他用户可读，建议执行: chmod 600 {CONFIG_FILE}", file=sys.stderr)
        try:
            file_cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as e:
            raise ZentaoError(f"读取配置文件失败 {CONFIG_FILE}: {e}")

    url = os.environ.get('ZENTAO_URL') or file_cfg.get('url', '')
    account = os.environ.get('ZENTAO_ACCOUNT') or file_cfg.get('account', '')
    password = os.environ.get('ZENTAO_PASSWORD') or file_cfg.get('password', '')
    allow_http = os.environ.get('ZENTAO_ALLOW_HTTP') == '1' or file_cfg.get('allow_http') is True

    missing = [n for n, v in (('url', url), ('account', account), ('password', password)) if not v]
    if missing:
        raise ZentaoError(
            f"缺少禅道配置: {', '.join(missing)}\n"
            f"在 {CONFIG_FILE} 中写入（并 chmod 600）:\n"
            '  {"url": "https://zentao.example.com/zentao", "account": "<账号>", "password": "<密码>"}\n'
            "或设置环境变量 ZENTAO_URL / ZENTAO_ACCOUNT / ZENTAO_PASSWORD"
        )
    url = base_url(url)
    if url.startswith('http://'):
        if not allow_http:
            raise ZentaoError(
                f"拒绝通过明文 HTTP 发送禅道密码: {url}\n"
                "请改用 https；确实只能用 http 的内网环境，在配置文件中加 \"allow_http\": true 或设置 ZENTAO_ALLOW_HTTP=1"
            )
        print("⚠ 禅道使用 http，账号密码和令牌以明文传输", file=sys.stderr)
    return Config(url, account, password)


def base_url(url: str) -> str:
    """允许直接粘贴禅道任意页面地址：http://host/zentao/my.html -> http://host/zentao"""
    url = url.strip()
    if not re.match(r'^https?://', url):
        raise ZentaoError(f"禅道地址必须以 http:// 或 https:// 开头: {url}")
    url = re.sub(r'[?#].*$', '', url)
    url = re.sub(r'/(index\.php|api\.php.*|[\w-]+\.html)$', '', url)
    return url.rstrip('/')


class Response:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self.text = body.decode('utf-8', errors='replace')

    def json(self) -> Dict:
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            raise ZentaoError(f"禅道返回的不是 JSON (HTTP {self.status}): {self.text[:200]}")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # 不跟随跳转：带令牌的请求只发给配置的禅道地址


_opener = build_opener(_NoRedirect)


def raw_request(method: str, url: str, body: Optional[Dict] = None, token: str = '') -> Response:
    data = json.dumps(body).encode('utf-8') if body is not None else None
    request = Request(url, data=data, method=method)
    request.add_header('Content-Type', 'application/json')
    if token:
        request.add_header('Token', token)
    try:
        with _opener.open(request, timeout=20) as resp:
            return Response(resp.status, resp.read())
    except HTTPError as e:
        return Response(e.code, e.read() or b'')
    except (URLError, OSError) as e:
        raise ZentaoError(f"连接禅道失败: {getattr(e, 'reason', e)}")


class Client:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        key = hashlib.sha256(f"{cfg.url}|{cfg.account}".encode()).hexdigest()[:12]
        self.token_file = CACHE_DIR / f"token-{key}"
        self.assignee_file = CACHE_DIR / f"assignees-{key}.json"
        self.token = self.token_file.read_text().strip() if self.token_file.exists() else ''

    def login(self) -> None:
        resp = raw_request('POST', self.cfg.api + '/tokens',
                           {'account': self.cfg.account, 'password': self.cfg.password})
        data = resp.json()
        if resp.status not in (200, 201) or not data.get('token'):
            raise ZentaoError(f"禅道登录失败: {data.get('error') or resp.text[:200]}")
        self.token = data['token']
        private_dir(CACHE_DIR)
        write_private(self.token_file, self.token)

    def call(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        if not self.token:
            self.login()
        resp = raw_request(method, self.cfg.api + path, body, self.token)
        if resp.status == 401:  # 令牌过期，重新登录一次
            self.login()
            resp = raw_request(method, self.cfg.api + path, body, self.token)
        if resp.status == 404:
            raise ZentaoError(f"禅道里找不到 {path}（编号不对，或者没有权限查看）")
        data = resp.json()
        if resp.status >= 400:
            raise ZentaoError(f"禅道拒绝了请求 {method} {path} (HTTP {resp.status}): {error_text(data)}")
        return data


def error_text(data: Dict) -> str:
    err = data.get('error') or data.get('message') or data
    if isinstance(err, dict):
        err = '；'.join(f"{k}: {''.join(v) if isinstance(v, list) else v}" for k, v in err.items())
    return str(err)


# ============================================================================
# 任务 / Bug 引用解析
# ============================================================================

def parse_ref(ref: str, default_type: str = 'task') -> Tuple[str, int]:
    """
    支持: 123  #123  T123  B45  task 123  bug 45  任务123  Bug#45
          以及禅道链接 .../task-view-123.html  .../bug-view-45.html  ...?m=bug&f=view&bugID=45
    """
    text = ref.strip()
    m = re.search(r'\b(task|bug)-view-(\d+)', text) or re.search(r'[?&]m=(task|bug)\b.*?[?&]\1ID=(\d+)', text)
    if m:
        return m.group(1), int(m.group(2))
    m = re.match(r'^(?:(task|t|任务|bug|b)\s*#?\s*)?#?(\d+)$', text, re.IGNORECASE)
    if not m:
        raise ZentaoError(f"看不懂这个编号: {ref}（示例: 123、T123、B45、bug 45、禅道任务或 Bug 的链接）")
    kind = (m.group(1) or '').lower()
    if kind in ('bug', 'b'):
        return 'bug', int(m.group(2))
    if kind in ('task', 't', '任务'):
        return 'task', int(m.group(2))
    return default_type, int(m.group(2))


def item_key(kind: str, item_id: int) -> str:
    return f"{kind}-{item_id}"


def label(kind: str, item_id: int) -> str:
    return f"{'任务' if kind == 'task' else 'Bug'} #{item_id}"


# ============================================================================
# 内容展示
# ============================================================================

class _TextExtractor(HTMLParser):
    BLOCK = {'p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'pre', 'table'}

    def __init__(self, base: str):
        super().__init__()
        self.base = base
        self.parts: List[str] = []
        self.cell_depth = 0  # 表格单元格内的换行改成空格，保证一行就是表格的一行

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.parts.append('\n|')
        elif tag in ('td', 'th'):
            self.cell_depth += 1
            self.parts.append(' ')
        elif tag in self.BLOCK:
            self.parts.append(' ' if self.cell_depth else '\n')
        if tag == 'li':
            self.parts.append('- ')
        if tag == 'img':
            src = dict(attrs).get('src') or ''
            if src and not re.match(r'^https?://', src):
                src = self.base.split('/zentao')[0] + ('' if src.startswith('/') else '/') + src
            self.parts.append(f"[图片]({src})")

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell_depth:
            self.cell_depth -= 1
            self.parts.append(' |')
        elif tag == 'table':
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(re.sub(r'\s+', ' ', data) if self.cell_depth else data)


def html_to_text(content: str, base: str) -> str:
    if not content:
        return '（空）'
    parser = _TextExtractor(base)
    parser.feed(content)
    text = html.unescape(''.join(parser.parts)).replace('\xa0', ' ')
    text = re.sub(r'(?<=\|) {2,}| {2,}(?=\|)', ' ', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip() or '（空）'


def user_name(value) -> str:
    if isinstance(value, dict):
        return value.get('realname') or value.get('account') or ''
    return value or ''


def print_files(item: Dict) -> None:
    files = item.get('files') or {}
    files = files.values() if isinstance(files, dict) else files
    names = [f.get('title') or f.get('pathname') for f in files if isinstance(f, dict)]
    if names:
        print(f"\n附件（需登录禅道查看）: {', '.join(names)}")


def show_task(client: Client, task_id: int) -> Dict:
    task = client.call('GET', f'/tasks/{task_id}')
    base = client.cfg.url
    print(f"# 任务 #{task_id} {task.get('name', '')}")
    print(f"状态: {task.get('status')}  类型: {task.get('type')}  优先级: {task.get('pri')}  "
          f"指派给: {user_name(task.get('assignedTo'))}  截止: {task.get('deadline') or '无'}")
    print(f"预计 {task.get('estimate', 0)}h / 已消耗 {task.get('consumed', 0)}h / 剩余 {task.get('left', 0)}h  "
          f"迭代: {task.get('executionName', '')}")
    print(f"链接: {base}/task-view-{task_id}.html")
    print(f"\n## 任务描述\n{html_to_text(task.get('desc', ''), base)}")
    story_id = int(task.get('story') or 0)
    if story_id:
        story = client.call('GET', f'/stories/{story_id}')
        print(f"\n## 关联需求 #{story_id} {story.get('title', '')}")
        print(f"\n### 需求描述\n{html_to_text(story.get('spec', ''), base)}")
        print(f"\n### 验收标准\n{html_to_text(story.get('verify', ''), base)}")
    print_files(task)
    return task


def show_bug(client: Client, bug_id: int) -> Dict:
    bug = client.call('GET', f'/bugs/{bug_id}')
    base = client.cfg.url
    print(f"# Bug #{bug_id} {bug.get('title', '')}")
    print(f"状态: {bug.get('status')}  严重程度: {bug.get('severity')}  优先级: {bug.get('pri')}  "
          f"由 {user_name(bug.get('openedBy'))} 创建  指派给: {user_name(bug.get('assignedTo'))}")
    print(f"链接: {base}/bug-view-{bug_id}.html")
    print(f"\n## 重现步骤\n{html_to_text(bug.get('steps', ''), base)}")
    story_id = int(bug.get('story') or 0)
    if story_id:
        story = client.call('GET', f'/stories/{story_id}')
        print(f"\n## 关联需求 #{story_id} {story.get('title', '')}\n{html_to_text(story.get('spec', ''), base)}")
    print_files(bug)
    return bug


# ============================================================================
# 计时：由 Claude Code 钩子在每轮对话开始 / 结束时调用
# ============================================================================

def repo_root(cwd: Optional[str] = None) -> str:
    try:
        out = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=cwd or None,
                                      stderr=subprocess.DEVNULL).decode().strip()
        return out or os.path.abspath(cwd or '.')
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return os.path.abspath(cwd or '.')


class TimeStore:
    """
    计时记录按项目存放在 ~/.cache/zentao/time-<项目哈希>.json，不进项目仓库。
    结构: {"active": "task-123", "titles": {...}, "segments": {"task-123": [{start, end, prompt}]},
           "open": {"<会话>": {start, item, prompt}}, "pending": {start, item}}
    """

    def __init__(self, root: str):
        key = hashlib.sha256(root.encode()).hexdigest()[:12]
        private_dir(CACHE_DIR)
        self.path = CACHE_DIR / f"time-{key}.json"
        self.lock_path = CACHE_DIR / f"time-{key}.lock"

    def __enter__(self):
        self.lock = open(self.lock_path, 'a')
        if fcntl:
            fcntl.flock(self.lock, fcntl.LOCK_EX)
        try:
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            self.data = {}
        for k, default in (('titles', {}), ('segments', {}), ('open', {})):
            self.data.setdefault(k, default)
        self.data.setdefault('active', '')
        return self.data

    def __exit__(self, exc_type, *args):
        if exc_type is None:
            write_private(self.path, json.dumps(self.data, ensure_ascii=False, indent=1))
        if fcntl:
            fcntl.flock(self.lock, fcntl.LOCK_UN)
        self.lock.close()


def add_segment(data: Dict, item: str, start: float, end: float, prompt: str) -> None:
    if item and end - start >= 1:
        data['segments'].setdefault(item, []).append({'start': start, 'end': end, 'prompt': prompt})


def track(event: str) -> None:
    """钩子入口：任何异常都吞掉，绝不影响正常对话；也不输出任何内容"""
    try:
        payload = json.loads(sys.stdin.read() or '{}')
    except (json.JSONDecodeError, OSError):
        payload = {}
    session = str(payload.get('session_id') or 'default')
    now = time.time()
    with TimeStore(repo_root(payload.get('cwd'))) as data:
        if event == 'begin':
            data['open'].pop(session, None)  # 上一轮没有正常结束的段直接丢弃，不猜时长
            if data['active']:
                prompt = re.sub(r'\s+', ' ', str(payload.get('prompt') or ''))[:60]
                data['open'][session] = {'start': now, 'item': data['active'], 'prompt': prompt}
        elif event == 'end':
            seg = data['open'].pop(session, None)
            pending = data.pop('pending', None)
            if pending:
                # 本轮中途开始了新的任务 / Bug：之前的时间归原条目，之后的时间归新条目
                if seg and seg['item'] != pending['item']:
                    add_segment(data, seg['item'], seg['start'], pending['start'], seg['prompt'])
                start = seg['start'] if seg and seg['item'] == pending['item'] else pending['start']
                add_segment(data, pending['item'], start, now, (seg or {}).get('prompt') or pending['prompt'])
            elif seg:
                add_segment(data, seg['item'], seg['start'], now, seg['prompt'])


def activate(kind: str, item_id: int, title: str, note: str) -> None:
    with TimeStore(repo_root()) as data:
        key = item_key(kind, item_id)
        data['active'] = key
        data['titles'][key] = title
        data['pending'] = {'start': time.time(), 'item': key, 'prompt': note}


def summarize(kind: str, item_id: int) -> Tuple[List[Dict], float]:
    with TimeStore(repo_root()) as data:
        segments = list(data['segments'].get(item_key(kind, item_id), []))
    return segments, sum(s['end'] - s['start'] for s in segments)


def suggest_hours(seconds: float) -> float:
    """向上取整到 0.1 小时，至少 0.1"""
    return max(0.1, math.ceil(seconds / 360) / 10)


def fmt_duration(seconds: float) -> str:
    minutes = int(round(seconds / 60))
    return f"{minutes // 60} 小时 {minutes % 60} 分" if minutes >= 60 else f"{minutes} 分"


def print_time(kind: str, item_id: int) -> float:
    segments, total = summarize(kind, item_id)
    print(f"{label(kind, item_id)} 的 AI 工作时间：")
    if not segments:
        print("  （没有记录。可能没有安装计时钩子，或者开始后还没有完整跑完一轮对话）")
    for i, s in enumerate(segments, 1):
        day = datetime.fromtimestamp(s['start']).strftime('%m-%d %H:%M')
        flag = '  ⚠ 时长异常，可能没有正常结束' if s['end'] - s['start'] > LONG_SEGMENT else ''
        print(f"  {i:>2}. {day}  {fmt_duration(s['end'] - s['start']):>10}  {s['prompt'] or '（无摘要）'}{flag}")
    print(f"共 {len(segments)} 段，累计 {fmt_duration(total)}，建议工时 {suggest_hours(total) if segments else 0} 小时")
    return total


def clear_item(kind: str, item_id: int) -> None:
    with TimeStore(repo_root()) as data:
        key = item_key(kind, item_id)
        data['segments'].pop(key, None)
        data['titles'].pop(key, None)
        if data['active'] == key:
            data['active'] = ''


HOOK_EVENTS = {'UserPromptSubmit': 'begin', 'Stop': 'end'}
HOOK_MARK = re.compile(r'zentao/scripts/zentao\.py\W*\s+track\b')  # 识别本 skill 添加的钩子


def hook_command(event: str) -> str:
    return f'python3 "$CLAUDE_PROJECT_DIR/.claude/skills/zentao/scripts/zentao.py" track {event}'


def manage_hooks(action: str, settings: Path) -> None:
    """在项目 .claude/settings.json 里添加 / 移除计时钩子，保留文件里的其他配置"""
    try:
        data = json.loads(settings.read_text(encoding='utf-8')) if settings.exists() else {}
    except json.JSONDecodeError as e:
        raise ZentaoError(f"{settings} 不是合法的 JSON，未修改: {e}")
    hooks = data.setdefault('hooks', {})
    for hook_event, track_event in HOOK_EVENTS.items():
        groups = [g for g in hooks.get(hook_event, [])
                  if not any(HOOK_MARK.search(h.get('command', '')) for h in g.get('hooks', []))]
        if action == 'install':
            groups.append({'hooks': [{'type': 'command', 'command': hook_command(track_event), 'timeout': 10}]})
        if groups:
            hooks[hook_event] = groups
        else:
            hooks.pop(hook_event, None)
    if not hooks:
        data.pop('hooks')
    if not data and action == 'uninstall':
        if settings.exists():
            settings.unlink()
        print(f"已移除计时钩子（{settings} 已空，已删除）")
        return
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{'已添加' if action == 'install' else '已移除'}计时钩子: {settings}")


# ============================================================================
# 完成任务时的指派人：优先按本人的历史习惯推荐
# ============================================================================

ASSIGNEE_HISTORY_LIMIT = 200


def person(value) -> Tuple[str, str]:
    """禅道用户字段 -> (账号, 姓名)；接口有时只给账号字符串"""
    if isinstance(value, dict):
        return value.get('account') or '', value.get('realname') or value.get('account') or ''
    return value or '', value or ''


def load_assignee_history(client: Client) -> List[Dict]:
    try:
        return json.loads(client.assignee_file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []


def record_assignee(client: Client, task: Dict, account: str, name: str) -> None:
    history = load_assignee_history(client)
    history.append({'account': account, 'name': name, 'project': task.get('project'), 'time': now_str()})
    private_dir(CACHE_DIR)
    write_private(client.assignee_file, json.dumps(history[-ASSIGNEE_HISTORY_LIMIT:], ensure_ascii=False))


def execution_done_tasks(client: Client, task: Dict) -> List[Dict]:
    """同一迭代里已完成的任务；查不到只影响推荐，不影响完成"""
    if not task.get('execution'):
        return []
    try:
        data = client.call('GET', f"/executions/{task['execution']}/tasks?status=done&limit=100")
    except ZentaoError:
        return []
    return [t for t in data.get('tasks') or [] if isinstance(t, dict)]


def by_habit(people: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """出现次数多的在前，次数相同时最近的在前"""
    counts = Counter(account for account, _ in people)
    latest = {account: i for i, (account, _) in enumerate(people)}
    names = dict(people)
    return [(a, names[a]) for a in sorted(counts, key=lambda a: (-counts[a], -latest[a]))]


def assignee_candidates(client: Client, task: Dict) -> Tuple[List[Tuple[str, str, str]], Dict[str, str]]:
    """
    候选指派人 [(账号, 姓名, 来源)]，优先级从高到低：
    本人在同一项目的历史选择 > 本人在本迭代完成的任务现在指派给谁 > 本人在其他项目的历史选择
    > 本迭代其他人完成任务后指派给谁 > 任务创建人（禅道的默认值）
    同时返回见过的人 {账号: 姓名}，用来把用户说的姓名换成账号
    """
    me = client.cfg.account
    history = load_assignee_history(client)
    done = execution_done_tasks(client, task)
    same_project = [h.get('project') == task.get('project') for h in history]
    groups = [
        ('历史习惯', [(h['account'], h['name']) for h, same in zip(history, same_project) if same]),
        ('本迭代你完成的任务', [person(t.get('assignedTo')) for t in done if person(t.get('finishedBy'))[0] == me]),
        ('其他项目的历史习惯', [(h['account'], h['name']) for h, same in zip(history, same_project) if not same]),
        ('本迭代团队习惯', [person(t.get('assignedTo')) for t in done if person(t.get('finishedBy'))[0] != me]),
        ('任务创建人', [person(task.get('openedBy'))]),
    ]
    known = {a: n for t in done + [task] for a, n in (person(t.get(f)) for f in ('openedBy', 'assignedTo', 'finishedBy'))}
    candidates, seen = [], {me, 'closed', ''}
    for source, people in groups:
        for account, name in by_habit(people):
            known.setdefault(account, name)
            if account not in seen:
                seen.add(account)
                candidates.append((account, name, source))
    return candidates, known


def pick_assignee(task: Dict, candidates: List[Tuple[str, str, str]], known: Dict[str, str],
                  wanted: Optional[str]) -> Tuple[str, str, str]:
    if not wanted:
        return candidates[0] if candidates else person(task.get('openedBy')) + ('任务创建人',)
    wanted = wanted.strip()
    for account, name in known.items():
        if wanted.lower() == account.lower() or wanted == name:
            return account, name, '你指定的'
    if re.fullmatch(r'[A-Za-z0-9_.@-]+', wanted):
        return wanted, wanted, '你指定的账号，最近的任务里没见过，请核对拼写'
    raise ZentaoError(f"不认识「{wanted}」：最近的任务里没有这个人，请直接给出他的禅道账号")


def fmt_person(account: str, name: str) -> str:
    return name if name == account else f"{name} ({account})"


# ============================================================================
# 写操作：开始任务 / 完成任务 / 解决 Bug
# ============================================================================

def start(client: Client, kind: str, item_id: int, left: Optional[float]) -> None:
    if kind == 'bug':
        bug = client.call('GET', f'/bugs/{item_id}')
        if bug.get('status') != 'active':
            raise ZentaoError(f"Bug #{item_id} 当前状态是 {bug.get('status')}，不是激活状态")
        activate('bug', item_id, bug.get('title', ''), '开始处理 Bug')
        print(f"✓ 开始处理 Bug #{item_id} {bug.get('title', '')}，已开始计时")
        return

    task = client.call('GET', f'/tasks/{item_id}')
    status = task.get('status')
    if status in ('wait', 'pause'):
        remain = left if left is not None else float(task.get('left') or 0) or float(task.get('estimate') or 0)
        if remain <= 0:
            raise ZentaoError(f"任务 #{item_id} 没有预计工时，禅道要求开始时填写预计剩余，请用 --left <小时> 指定")
        action = 'start' if status == 'wait' else 'restart'
        client.call('POST', f'/tasks/{item_id}/{action}',
                    {'consumed': float(task.get('consumed') or 0), 'left': remain, 'realStarted': now_str()})
        print(f"✓ 禅道任务 #{item_id} 已标为进行中（预计剩余 {remain}h）")
    elif status == 'doing':
        print(f"任务 #{item_id} 已经是进行中，不重复开始")
    else:
        raise ZentaoError(f"任务 #{item_id} 当前状态是 {status}，不能开始")
    activate('task', item_id, task.get('name', ''), '开始任务')
    print(f"✓ 已开始计时：任务 #{item_id} {task.get('name', '')}")


def confirm_code(client: Client, action: str, item_id: int, hours: float, comment: str) -> str:
    payload = json.dumps([client.cfg.url, action, item_id, hours, comment], ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:6]


def comment_html(lines: List[str]) -> str:
    return ''.join(f"<p>{html.escape(line)}</p>" for line in lines if line.strip())


def finish(client: Client, task_id: int, hours: float, comment: str, assign: Optional[str],
           confirm: Optional[str]) -> None:
    task = client.call('GET', f'/tasks/{task_id}')
    if task.get('status') not in ('wait', 'doing', 'pause'):
        raise ZentaoError(f"任务 #{task_id} 当前状态是 {task.get('status')}，不能完成")
    candidates, known = assignee_candidates(client, task)
    account, name, source = pick_assignee(task, candidates, known, assign)
    code = confirm_code(client, 'finish', task_id, hours, comment + '|' + account)
    if confirm is None:
        print("=" * 60)
        print(f"将完成: 任务 #{task_id} {task.get('name', '')}")
        print(f"本次工时: {hours} 小时（禅道里已消耗 {task.get('consumed', 0)}h，完成后剩余记为 0）")
        print(f"指派给: {fmt_person(account, name)}（{source}）")
        others = [c for c in candidates if c[0] != account][:3]
        if others:
            print(f"其他候选: {'、'.join(f'{fmt_person(a, n)}（{s}）' for a, n, s in others)}")
        print(f"备注: {comment or '（无）'}")
        print(f"确认码: {code}")
        print("=" * 60)
        return
    if confirm != code:
        raise ZentaoError("确认码不一致：工时、备注或指派人与确认时不同。请重新预览并让用户确认")
    real_started = task.get('realStarted') or ''
    if not real_started or real_started.startswith('0000'):
        real_started = now_str()
    client.call('POST', f'/tasks/{task_id}/finish', {
        'currentConsumed': hours, 'assignedTo': account, 'realStarted': real_started, 'finishedDate': now_str(),
        'comment': comment_html([comment]),
    })
    record_assignee(client, task, account, name)
    clear_item('task', task_id)
    print(f"✅ 任务 #{task_id} 已完成，记录工时 {hours} 小时，已指派给 {fmt_person(account, name)}  "
          f"{client.cfg.url}/task-view-{task_id}.html")


def resolve(client: Client, bug_id: int, hours: float, comment: str, build: str, confirm: Optional[str]) -> None:
    bug = client.call('GET', f'/bugs/{bug_id}')
    if bug.get('status') != 'active':
        raise ZentaoError(f"Bug #{bug_id} 当前状态是 {bug.get('status')}，不能解决")
    opener = bug.get('openedBy')
    opener = opener.get('account') if isinstance(opener, dict) else opener
    # 开源版禅道不支持在 Bug 上记工时，所以把耗时写进解决备注
    lines = [f"耗时 {hours} 小时（AI 协作计时，经本人确认）", comment]
    code = confirm_code(client, 'resolve', bug_id, hours, comment + '|' + build)
    if confirm is None:
        print("=" * 60)
        print(f"将解决: Bug #{bug_id} {bug.get('title', '')}")
        print(f"解决方案: 已解决  解决版本: {'主干' if build == 'trunk' else build}  指派回: {user_name(bug.get('openedBy'))}")
        print("备注:")
        for line in lines:
            if line.strip():
                print(f"  {line}")
        print(f"确认码: {code}")
        print("=" * 60)
        return
    if confirm != code:
        raise ZentaoError("确认码不一致：工时、备注或解决版本与确认时不同。请重新预览并让用户确认")
    client.call('POST', f'/bugs/{bug_id}/resolve', {
        'resolution': 'fixed', 'resolvedBuild': build, 'resolvedDate': now_str(),
        'assignedTo': opener or '', 'comment': comment_html(lines),
    })
    clear_item('bug', bug_id)
    print(f"✅ Bug #{bug_id} 已解决，耗时 {hours} 小时已写入备注  {client.cfg.url}/bug-view-{bug_id}.html")


# ============================================================================
# 主函数
# ============================================================================

def active_or(ref: Optional[str], default_type: str = 'task') -> Tuple[str, int]:
    if ref:
        return parse_ref(ref, default_type)
    with TimeStore(repo_root()) as data:
        active = data['active']
    if not active:
        raise ZentaoError("没有正在进行的任务或 Bug，请指定编号")
    kind, _, item_id = active.partition('-')
    return kind, int(item_id)


def main() -> None:
    parser = argparse.ArgumentParser(description='禅道任务 / Bug 助手')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('show', help='查看任务或 Bug 的内容（含关联需求）')
    p.add_argument('ref')
    p = sub.add_parser('start', help='开始任务（禅道标为进行中）或开始处理 Bug，并开始计时')
    p.add_argument('ref')
    p.add_argument('--left', type=float, help='任务没有预计工时时，指定预计剩余小时数')
    p = sub.add_parser('time', help='查看累计的 AI 工作时间')
    p.add_argument('ref', nargs='?')
    sub.add_parser('pause', help='停止计时（不改禅道），切换到别的事情时用')
    p = sub.add_parser('finish', help='完成任务并记录工时：先不带 --confirm 预览，用户确认后带确认码执行')
    p.add_argument('ref', nargs='?')
    p.add_argument('--hours', type=float, required=True)
    p.add_argument('--comment', default='')
    p.add_argument('--assign', help='完成后指派给谁（姓名或禅道账号），默认按历史习惯推荐')
    p.add_argument('--confirm')
    p = sub.add_parser('resolve', help='解决 Bug，耗时写进备注：先预览，确认后带确认码执行')
    p.add_argument('ref', nargs='?')
    p.add_argument('--hours', type=float, required=True)
    p.add_argument('--comment', default='')
    p.add_argument('--build', default='trunk', help='解决版本，默认主干 trunk')
    p.add_argument('--confirm')
    p = sub.add_parser('track', help='供 Claude Code 钩子调用')
    p.add_argument('event', choices=['begin', 'end'])
    p = sub.add_parser('hooks', help='在项目 .claude/settings.json 中安装 / 移除计时钩子')
    p.add_argument('action', choices=['install', 'uninstall'])
    p.add_argument('--settings', help='默认: <项目根>/.claude/settings.json')
    args = parser.parse_args()

    if args.cmd == 'hooks':
        manage_hooks(args.action, Path(args.settings or Path(repo_root()) / '.claude' / 'settings.json'))
        return

    if args.cmd == 'track':
        try:
            track(args.event)
        except Exception:
            pass
        return

    if args.cmd == 'pause':
        with TimeStore(repo_root()) as data:
            active, data['active'] = data['active'], ''
            data.pop('pending', None)
        print(f"已停止计时（{active or '原本没有在计时'}），已记录的时间保留")
        return

    if args.cmd == 'time':
        print_time(*active_or(args.ref))
        return

    if getattr(args, 'hours', None) is not None and not 0 < args.hours <= 24:
        raise ZentaoError("工时需要在 0 到 24 小时之间")

    client = Client(load_config())
    if args.cmd == 'show':
        kind, item_id = parse_ref(args.ref)
        (show_task if kind == 'task' else show_bug)(client, item_id)
    elif args.cmd == 'start':
        start(client, *parse_ref(args.ref), args.left)
    elif args.cmd == 'finish':
        kind, item_id = active_or(args.ref)
        if kind != 'task':
            raise ZentaoError(f"{label(kind, item_id)} 不是任务，Bug 请用 resolve")
        finish(client, item_id, args.hours, args.comment, args.assign, args.confirm)
    elif args.cmd == 'resolve':
        kind, item_id = active_or(args.ref, 'bug')
        if kind != 'bug':
            raise ZentaoError(f"{label(kind, item_id)} 不是 Bug，任务请用 finish")
        resolve(client, item_id, args.hours, args.comment, args.build, args.confirm)


if __name__ == '__main__':
    try:
        main()
    except ZentaoError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
