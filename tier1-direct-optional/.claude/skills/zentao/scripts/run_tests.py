#!/usr/bin/env python3
"""
zentao skill 自动化测试

在本机启动一个模拟禅道（REST API v1），覆盖配置校验、登录与令牌、读取任务 / Bug、
开始任务、钩子计时、完成任务（含按历史习惯推荐指派人）、解决 Bug 和确认码。不连接任何真实服务器。

运行：python3 scripts/run_tests.py
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / 'zentao.py'
PREFIX = '/zentao/api.php/v1'


class MockZentao(BaseHTTPRequestHandler):
    tokens = set()
    logins = 0
    posts: list = []
    task = {}
    bug = {}
    done_tasks = []

    def log_message(self, *args):
        pass

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')

    def authed(self):
        if self.headers.get('Token') in MockZentao.tokens:
            return True
        self.reply(401, {'error': 'Unauthorized'})
        return False

    def do_GET(self):
        if not self.authed():
            return
        path = self.path.replace(PREFIX, '')
        cls = MockZentao
        if path == '/tasks/123':
            return self.reply(200, cls.task)
        if path == '/stories/7':
            return self.reply(200, {'id': 7, 'title': '下单校验', 'spec': '<p>库存不足时&nbsp;禁止下单</p>',
                                    'verify': '<ul><li>库存为 0 时提示</li></ul>'})
        if path == '/bugs/45':
            return self.reply(200, cls.bug)
        if path.startswith('/executions/9/tasks?') and 'status=done' in path:
            if cls.done_tasks is None:
                return self.reply(403, {'error': 'no priv'})
            return self.reply(200, {'total': len(cls.done_tasks), 'tasks': cls.done_tasks})
        return self.reply(404, {'error': 'not found'})

    def do_POST(self):
        path = self.path.replace(PREFIX, '')
        body = self.body()
        cls = MockZentao
        if path == '/tokens':
            cls.logins += 1
            if body.get('account') == 'dev' and body.get('password') == 'pw':
                token = f'tok{cls.logins}'
                cls.tokens.add(token)
                return self.reply(201, {'token': token})
            return self.reply(400, {'error': '登录失败，请检查您的用户名或密码是否填写正确。'})
        if not self.authed():
            return
        cls.posts.append((path, body))
        if path == '/tasks/123/start':
            cls.task.update(status='doing', left=body['left'], realStarted=body['realStarted'])
            return self.reply(200, cls.task)
        if path == '/tasks/123/finish':
            cls.task.update(status='done', consumed=cls.task['consumed'] + body['currentConsumed'],
                            assignedTo=body.get('assignedTo'))
            return self.reply(200, cls.task)
        if path == '/bugs/45/resolve':
            cls.bug.update(status='resolved')
            return self.reply(200, cls.bug)
        return self.reply(404, {'error': 'not found'})


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='zentao-test-'))
    repo = tmp / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)

    MockZentao.task = {'id': 123, 'name': '实现下单库存校验', 'status': 'wait', 'type': 'devel', 'pri': 2,
                       'estimate': 4, 'consumed': 0, 'left': 0, 'story': 7, 'executionName': '10 月迭代',
                       'project': 3, 'execution': 9, 'openedBy': {'account': 'pm1', 'realname': '产品一'},
                       'assignedTo': {'account': 'dev', 'realname': '开发'}, 'realStarted': None,
                       'desc': '<p>见需求</p><p><img src="/zentao/file-read-9.png"/></p>'
                               '<table><tr><th>字段</th><th>规则</th></tr>'
                               '<tr><td><p>放款件数</p></td><td><p>统计订单数，</p><p>含展期</p></td></tr></table>',
                       'files': []}
    MockZentao.bug = {'id': 45, 'title': '库存为负', 'status': 'active', 'severity': 2, 'pri': 1, 'story': 0,
                      'steps': '<p>[步骤] 连续下单</p><p>[结果] 库存 -1</p>',
                      'openedBy': {'account': 'qa1', 'realname': '测试一'}, 'assignedTo': 'dev'}
    me = {'account': 'dev', 'realname': '开发'}
    MockZentao.done_tasks = [
        {'id': 100, 'finishedBy': me, 'assignedTo': {'account': 'qa2', 'realname': '测试二'}},
        {'id': 101, 'finishedBy': me, 'assignedTo': {'account': 'qa2', 'realname': '测试二'}},
        {'id': 102, 'finishedBy': me, 'assignedTo': 'closed'},
        {'id': 103, 'finishedBy': {'account': 'dev2', 'realname': '开发二'},
         'assignedTo': {'account': 'qa3', 'realname': '测试三'}},
    ]
    server = ThreadingHTTPServer(('127.0.0.1', 0), MockZentao)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_address[1]}/zentao/my.html'
    base_env = {'PATH': os.environ['PATH'], 'HOME': str(tmp), 'XDG_CACHE_HOME': str(tmp / 'cache'),
                'ZENTAO_URL': url, 'ZENTAO_ACCOUNT': 'dev', 'ZENTAO_PASSWORD': 'pw', 'ZENTAO_ALLOW_HTTP': '1'}

    def run(*args, env=None, stdin=''):
        e = {k: v for k, v in dict(base_env, **(env or {})).items() if v is not None}
        r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=repo, env=e, input=stdin,
                           capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout, r.stderr

    def hook(event, session='s1', prompt=''):
        return run('track', event, stdin=json.dumps({'session_id': session, 'cwd': str(repo), 'prompt': prompt}))

    def code_of(out):
        return next(line.split(':', 1)[1].strip() for line in out.splitlines() if line.startswith('确认码'))

    results = []

    def check(name, ok, detail=''):
        results.append(ok)
        print(f"{'✓' if ok else '✗'} {name}" + ('' if ok else f"\n    {str(detail)[-500:]}"))

    rc, out, err = run('show', '123', env={'ZENTAO_PASSWORD': None})
    check('缺少配置时报错并提示配置方法', rc == 1 and '缺少禅道配置: password' in err, err)

    rc, out, err = run('show', '123', env={'ZENTAO_ALLOW_HTTP': None})
    check('默认拒绝明文 HTTP', rc == 1 and '拒绝通过明文 HTTP' in err, err)

    rc, out, err = run('show', '123', env={'ZENTAO_PASSWORD': 'bad'})
    check('密码错误时显示禅道的提示', rc == 1 and '登录失败' in err, err)

    rc, out, err = run('show', 'http://zentao.example.com/zentao/task-view-123.html')
    check('读取任务：描述、关联需求、验收标准、图片链接',
          rc == 0 and '任务 #123 实现下单库存校验' in out and '库存不足时 禁止下单' in out
          and '- 库存为 0 时提示' in out and '/zentao/file-read-9.png)' in out and 'http://127.0.0.1' in out
          and '明文传输' in err, out + err)
    check('表格按行输出，单元格内的换行合并', '| 字段 | 规则 |' in out and '| 放款件数 | 统计订单数， 含展期 |' in out, out)

    token_files = list((tmp / 'cache' / 'zentao').glob('token-*'))
    mode = token_files[0].stat().st_mode & 0o777 if token_files else 0
    check('令牌缓存在用户目录且仅本人可读', len(token_files) == 1 and mode == 0o600, f'{token_files} {oct(mode)}')

    logins = MockZentao.logins
    run('show', 'T123')
    check('复用缓存的令牌，不重复登录', MockZentao.logins == logins)
    MockZentao.tokens.clear()
    rc, out, err = run('show', '#123')
    check('令牌失效时自动重新登录一次', rc == 0 and MockZentao.logins == logins + 1, err)

    for ref in ('B45', 'bug 45', 'http://x/zentao/bug-view-45.html', 'http://x/zentao/index.php?m=bug&f=view&bugID=45'):
        rc, out, err = run('show', ref)
        if not (rc == 0 and 'Bug #45 库存为负' in out):
            break
    check('识别 Bug 编号和多种链接格式', rc == 0 and '[结果] 库存 -1' in out and '测试一' in out, ref + out + err)

    rc, out, err = run('show', 'abc')
    check('无法识别的编号给出示例', rc == 1 and '示例' in err, err)

    rc, out, err = hook('begin', prompt='还没开始任务')
    rc2, out2, err2 = hook('end')
    check('没有进行中的条目时钩子不计时、不输出', rc == rc2 == 0 and out == out2 == '' and err == err2 == '')

    rc, out, err = run('track', 'begin', stdin='not json')
    check('钩子收到异常输入也静默成功', rc == 0 and out == '' and err == '', out + err)

    rc, out, err = run('start', '123')
    body = MockZentao.posts[-1] if MockZentao.posts else ('', {})
    check('开始任务：禅道标为进行中，预计剩余取预计工时',
          rc == 0 and body[0] == '/tasks/123/start' and body[1]['left'] == 4 and '已开始计时' in out, out + err)

    time.sleep(1.2)
    hook('end')                                      # 开始任务所在的这一轮结束
    hook('begin', prompt='实现库存校验并补单测')
    time.sleep(1.2)
    hook('end')
    hook('begin', session='s2', prompt='另一个会话里跑测试')
    time.sleep(1.1)
    hook('end', session='s2')
    hook('begin', prompt='这一轮没有正常结束')       # 不调用 end，下一次 begin 会丢弃它
    hook('begin', prompt='继续')
    time.sleep(1.1)
    hook('end')
    rc, out, err = run('time')
    check('按轮次累计时间，跨会话累加，未结束的轮次不计',
          rc == 0 and '共 4 段' in out and '开始任务' in out and '实现库存校验并补单测' in out
          and '另一个会话里跑测试' in out and '这一轮没有正常结束' not in out and '建议工时 0.1 小时' in out, out + err)

    posts = len(MockZentao.posts)
    rc, out, err = run('finish', '--hours', '1.5', '--comment', '完成库存校验')
    check('完成任务先预览，不提交', rc == 0 and '本次工时: 1.5 小时' in out and '确认码' in out
          and len(MockZentao.posts) == posts, out + err)
    check('没有本地历史时，按本迭代你完成的任务推荐指派人，其他人列为候选',
          '指派给: 测试二 (qa2)（本迭代你完成的任务）' in out and '测试三 (qa3)（本迭代团队习惯）' in out
          and '产品一 (pm1)（任务创建人）' in out and 'closed' not in out, out)
    code = code_of(out)

    rc, out, err = run('finish', '--hours', '1.5', '--comment', '完成库存校验', '--assign', '产品一')
    check('按姓名改指派人后确认码随之变化', rc == 0 and '指派给: 产品一 (pm1)（你指定的）' in out
          and code_of(out) != code, out + err)

    rc, out, err = run('finish', '--hours', '1.5', '--assign', '路人甲')
    check('不认识的姓名报错，提示给账号', rc == 1 and '不认识「路人甲」' in err, err)

    MockZentao.done_tasks = None
    rc, out, err = run('finish', '--hours', '1.5', '--comment', '完成库存校验')
    check('查不到迭代任务时退回任务创建人，不影响完成', rc == 0 and '指派给: 产品一 (pm1)（任务创建人）' in out, out + err)
    MockZentao.done_tasks = [{'id': 100, 'finishedBy': me, 'assignedTo': {'account': 'qa2', 'realname': '测试二'}}]

    rc, out, err = run('finish', '--hours', '2', '--comment', '完成库存校验', '--confirm', code)
    check('工时改了以后旧确认码失效', rc == 1 and '确认码不一致' in err and len(MockZentao.posts) == posts, err)

    rc, out, err = run('finish', '--hours', '1.5', '--comment', '完成库存校验', '--confirm', code)
    path, body = MockZentao.posts[-1]
    check('确认后完成任务并记录工时',
          rc == 0 and path == '/tasks/123/finish' and body['currentConsumed'] == 1.5 and body['assignedTo'] == 'qa2'
          and body['realStarted'] and body['finishedDate'] and '完成库存校验' in body['comment'], out + err + str(body))

    MockZentao.task.update(status='doing')
    rc, out, err = run('finish', '123', '--hours', '1', '--assign', 'pm1')
    run('finish', '123', '--hours', '1', '--assign', 'pm1', '--confirm', code_of(out))
    MockZentao.task.update(status='doing')
    rc, out, err = run('finish', '123', '--hours', '1')
    check('本人在同一项目的历史选择优先于迭代里的推断',
          rc == 0 and '指派给: 产品一 (pm1)（历史习惯）' in out and '测试二 (qa2)（历史习惯）' in out, out + err)
    MockZentao.task.update(status='done')

    rc, out, err = run('time', '123')
    check('完成后清除这个任务的计时记录', rc == 0 and '没有记录' in out, out)

    rc, out, err = run('finish', '123', '--hours', '1')
    check('已完成的任务不能再次完成', rc == 1 and '不能完成' in err, err)

    posts = len(MockZentao.posts)
    rc, out, err = run('start', 'bug 45')
    check('开始处理 Bug 只计时，不改禅道', rc == 0 and len(MockZentao.posts) == posts and '已开始计时' in out, out + err)

    rc, out, err = run('resolve', '--hours', '0.5', '--comment', '修复并发扣减')
    check('解决 Bug 先预览：耗时写进备注，指派回提 Bug 的人',
          rc == 0 and '耗时 0.5 小时' in out and '指派回: 测试一' in out and '主干' in out, out + err)
    code = code_of(out)

    rc, out, err = run('resolve', '45', '--hours', '0.5', '--comment', '修复并发扣减', '--confirm', code)
    path, body = MockZentao.posts[-1]
    check('确认后解决 Bug',
          rc == 0 and path == '/bugs/45/resolve' and body['resolution'] == 'fixed'
          and body['resolvedBuild'] == 'trunk' and body['assignedTo'] == 'qa1' and '耗时 0.5 小时' in body['comment'],
          out + err + str(body))

    rc, out, err = run('resolve', 'T123', '--hours', '1')
    check('任务不能用 resolve', rc == 1 and '不是 Bug' in err, err)

    rc, out, err = run('finish', '--hours', '30')
    check('工时超出范围时报错', rc == 1 and '0 到 24' in err, err)

    MockZentao.task.update(status='wait', left=0, estimate=0)
    rc, out, err = run('start', '123')
    check('任务没有预计工时时提示用 --left', rc == 1 and '--left' in err, err)

    run('pause')
    hook('begin', prompt='暂停后')
    time.sleep(1.1)
    hook('end')
    rc, out, err = run('time', 'bug 45')
    check('暂停后不再计时', rc == 0 and '暂停后' not in out, out)

    settings = repo / '.claude' / 'settings.json'
    settings.parent.mkdir()
    other = {'permissions': {'allow': ['Bash(ls)']},
             'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'echo mine'}]}]}}
    settings.write_text(json.dumps(other))
    run('hooks', 'install')
    run('hooks', 'install')
    data = json.loads(settings.read_text())
    stop_cmds = [h['command'] for g in data['hooks']['Stop'] for h in g['hooks']]
    begin_cmds = [h['command'] for g in data['hooks']['UserPromptSubmit'] for h in g['hooks']]
    check('安装钩子：保留已有配置，重复安装不重复添加',
          data['permissions'] == other['permissions'] and 'echo mine' in stop_cmds and len(stop_cmds) == 2
          and len(begin_cmds) == 1 and 'track begin' in begin_cmds[0], data)
    run('hooks', 'uninstall')
    check('移除钩子：只删自己的，其他配置原样保留', json.loads(settings.read_text()) == other, settings.read_text())
    settings.write_text('{}')
    run('hooks', 'install')
    run('hooks', 'uninstall')
    check('移除后配置文件为空时删除它', not settings.exists())
    settings.write_text('{bad json')
    rc, out, err = run('hooks', 'install')
    check('配置文件不是合法 JSON 时不改动', rc == 1 and settings.read_text() == '{bad json', err)

    server.shutdown()
    passed = sum(results)
    print(f"\n{passed}/{len(results)} 通过")
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
