#!/usr/bin/env python3
"""
jenkins-deploy 自动化测试

在本机启动一个模拟 Jenkins，并建一个带本地远端的临时 Git 仓库，
覆盖配置校验、任务筛选、参数推断、确认码、触发、监控、停止等流程。
不连接任何真实服务器，不需要 Jenkins 账号。

运行：python3 scripts/run_tests.py
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

SCRIPT = Path(__file__).resolve().parent / 'jenkins_deploy.py'
AUTH = 'Basic ' + base64.b64encode(b'tester:secret').decode()


class MockJenkins(BaseHTTPRequestHandler):
    repo_url = ''
    posts: list = []
    queue_polls = 0
    build_polls = 0

    def log_message(self, *args):
        pass

    def reply(self, code, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else b''
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.headers.get('Authorization') != AUTH:
            return self.reply(401)
        path = urlparse(self.path).path
        cls = MockJenkins
        if path == '/api/json':
            return self.reply(200, {'jobs': [
                {'_class': 'com.cloudbees.hudson.plugins.folder.Folder', 'name': 'team', 'fullName': 'team'},
                {'_class': 'hudson.model.FreeStyleProject', 'name': 'plain', 'fullName': 'plain'},
                {'_class': 'org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject',
                 'name': 'mb', 'fullName': 'mb'},
            ]})
        if path == '/job/team/api/json':
            return self.reply(200, {'jobs': [
                {'_class': 'org.jenkinsci.plugins.workflow.job.WorkflowJob', 'name': 'svc-dev', 'fullName': 'team/svc-dev'},
            ]})
        if path == '/job/team/job/svc-dev/api/json':
            if 'builds' in self.path:
                return self.reply(200, {'builds': [{'number': 7, 'queueId': 5}]})
            return self.reply(200, {'name': 'svc-dev', 'fullName': 'team/svc-dev', 'property': [
                {'parameterDefinitions': [
                    {'name': 'repoUrl', 'type': 'WReadonlyStringParameterDefinition',
                     'defaultParameterValue': {'value': cls.repo_url}},
                    {'name': 'repoBranch', 'type': 'StringParameterDefinition', 'defaultParameterValue': {'value': 'main'}},
                    {'name': 'repoTag', 'type': 'StringParameterDefinition', 'defaultParameterValue': {'value': ''}},
                    {'name': 'deployEnv', 'type': 'ChoiceParameterDefinition', 'choices': ['dev', 'test'],
                     'defaultParameterValue': {'value': 'dev'}},
                    {'name': 'skipTests', 'type': 'BooleanParameterDefinition', 'defaultParameterValue': {'value': False}},
                ]}]})
        if path == '/job/plain/api/json':
            return self.reply(200, {'name': 'plain', 'fullName': 'plain', 'property': []})
        if path == '/queue/item/5/api/json':
            cls.queue_polls += 1
            return self.reply(200, {'why': 'waiting'} if cls.queue_polls < 2 else {'executable': {'number': 7}})
        if path == '/job/team/job/svc-dev/7/api/json':
            cls.build_polls += 1
            return self.reply(200, {'building': True, 'result': None, 'estimatedDuration': 10000}
                              if cls.build_polls < 2 else {'building': False, 'result': 'SUCCESS'})
        return self.reply(404)

    def do_POST(self):
        if self.headers.get('Authorization') != AUTH:
            return self.reply(401)
        body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
        MockJenkins.posts.append((self.path, body))
        if self.path.endswith('/buildWithParameters') or self.path.endswith('/build'):
            port = self.server.server_address[1]
            return self.reply(201, headers={'Location': f'http://127.0.0.1:{port}/queue/item/5/'})
        if self.path.endswith('/stop'):
            return self.reply(302, headers={'Location': '/'})
        return self.reply(404)


def git(cwd, *args):
    subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com', *args],
                   cwd=cwd, check=True, capture_output=True)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='jenkins-deploy-test-'))
    remote, repo = tmp / 'remote.git', tmp / 'repo'
    subprocess.run(['git', 'init', '-q', '--bare', str(remote)], check=True)
    subprocess.run(['git', 'clone', '-q', str(remote), str(repo)], check=True, capture_output=True)
    git(repo, 'commit', '-q', '--allow-empty', '-m', 'init')
    git(repo, 'push', '-q', 'origin', 'HEAD:main')
    git(repo, 'checkout', '-q', '-b', 'feature/x')
    git(repo, 'commit', '-q', '--allow-empty', '-m', 'feat')
    git(repo, 'push', '-q', '-u', 'origin', 'feature/x')

    MockJenkins.repo_url = str(remote)
    server = ThreadingHTTPServer(('127.0.0.1', 0), MockJenkins)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_env = {
        'PATH': os.environ['PATH'], 'HOME': str(tmp), 'XDG_CACHE_HOME': str(tmp / 'cache'),
        'JENKINS_URL': f'http://127.0.0.1:{server.server_address[1]}', 'JENKINS_USER': 'tester',
        'JENKINS_TOKEN': 'secret', 'JENKINS_ALLOW_HTTP': '1',
    }

    def run(*args, env=None, stdin=subprocess.DEVNULL):
        e = dict(base_env, **(env or {}))
        e = {k: v for k, v in e.items() if v is not None}
        r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=repo, env=e,
                           capture_output=True, text=True, timeout=60, stdin=stdin)
        return r.returncode, r.stdout + r.stderr

    def code_of(out):
        return next(line.split(':', 1)[1].strip() for line in out.splitlines() if line.startswith('确认码'))

    results = []

    def check(name, ok, detail=''):
        results.append(ok)
        print(f"{'✓' if ok else '✗'} {name}" + ('' if ok else f"\n    {detail[-400:]}"))

    rc, out = run('--list', env={'JENKINS_TOKEN': None})
    check('缺少凭据时报错并提示配置方法', rc == 1 and '缺少 Jenkins 配置: token' in out, out)

    rc, out = run('--list', env={'JENKINS_ALLOW_HTTP': None})
    check('默认拒绝明文 HTTP', rc == 1 and '拒绝通过明文 HTTP' in out, out)

    rc, out = run('--list', env={'JENKINS_TOKEN': 'wrong'})
    check('凭据错误时给出明确提示', rc == 1 and 'HTTP 401' in out, out)

    rc, out = run('--list')
    check('按当前仓库筛选任务', rc == 0 and 'team/svc-dev' in out and 'plain' not in out, out)

    rc, out = run('--list', '--all')
    check('列出全部任务并跳过多分支流水线', rc == 0 and 'plain' in out and ' mb' not in out, out)

    cache = list((tmp / 'cache' / 'jenkins-deploy').glob('jobs-*.json'))
    mode = (tmp / 'cache' / 'jenkins-deploy').stat().st_mode & 0o777
    check('缓存写在用户缓存目录且仅本人可读', len(cache) == 1 and mode == 0o700, f'{cache} {oct(mode)}')

    rc, out = run('svc-dev', '--dry-run')
    check('模拟运行用当前分支填参数，只读参数不提交',
          rc == 0 and 'repoBranch = feature/x' in out and 'deployEnv = dev' in out
          and 'skipTests = false' in out and 'repoUrl =' not in out and '确认码' in out, out)
    good_code = code_of(out)

    rc, out = run('svc-dev', '--dry-run', '--params', '{"deployEnv":"prod"}')
    check('选项参数取值不合法时报错', rc == 1 and '不在可选项中' in out, out)

    rc, out = run('svc-dev', '--dry-run', '--params', '{"depolyEnv":"test"}')
    check('参数名拼错时报错', rc == 1 and '任务没有参数 depolyEnv' in out, out)

    rc, out = run('svc-dev', '--dry-run', '--params', '{"repoUrl":"git@evil.example.com:x/y.git"}')
    check('不允许改只读参数', rc == 1 and '只读参数' in out, out)

    before = len(MockJenkins.posts)
    rc, out = run('svc-dev', '--trigger', 'deadbeef')
    check('确认码不一致时拒绝触发', rc == 1 and '确认码不一致' in out and len(MockJenkins.posts) == before, out)

    rc, out = run('svc-dev', '--trigger', good_code, '--params', '{"deployEnv":"test"}')
    check('参数改动后旧确认码失效', rc == 1 and '确认码不一致' in out and len(MockJenkins.posts) == before, out)

    rc, out = run('svc-dev', '--trigger', good_code)
    path, body = MockJenkins.posts[-1] if MockJenkins.posts else ('', '')
    check('确认码一致时触发，提交的参数与确认时相同',
          rc == 0 and json.loads(out.splitlines()[-1])['queue_id'] == 5
          and path == '/job/team/job/svc-dev/buildWithParameters'
          and 'repoBranch=feature%2Fx' in body and 'repoUrl' not in body, out + body)

    rc, out = run('--monitor-only', '--full-name', 'team/svc-dev', '--queue-id', '5')
    check('监控到构建成功', rc == 0 and '#7: SUCCESS' in out, out)

    rc, out = run('--stop', '7')
    check('停止构建必须指定任务', rc == 1 and '--full-name' in out, out)

    rc, out = run('--stop', '7', '--full-name', 'team/svc-dev')
    check('停止指定构建', rc == 0 and MockJenkins.posts[-1][0] == '/job/team/job/svc-dev/7/stop', out)

    git(repo, 'commit', '-q', '--allow-empty', '-m', 'local only')
    rc, out = run('svc-dev', '--dry-run')
    check('本地有未推送提交时警告', rc == 0 and 'Jenkins 会构建远端版本' in out, out)
    rc, out = run('svc-dev', '--trigger', good_code)
    check('只是本地多了提交、远端没变时确认码仍有效', rc == 0, out)
    git(repo, 'push', '-q')
    rc, out = run('svc-dev', '--trigger', good_code)
    check('远端分支有新提交后旧确认码失效', rc == 1 and '确认码不一致' in out, out)

    git(repo, 'checkout', '-q', '-b', 'not-pushed')
    rc, out = run('svc-dev', '--dry-run')
    check('分支未推送时报错', rc == 1 and '远端 origin 上没有分支 not-pushed' in out, out)
    rc, out = run('svc-dev', '--trigger', good_code)
    check('切换分支后旧确认码失效', rc == 1, out)

    git(repo, 'checkout', '-q', 'feature/x')
    git(repo, 'tag', 'v1.0.0')
    rc, out = run('svc-dev', '--dry-run')
    check('当前提交的标签未推送时报错', rc == 1 and '没有标签 v1.0.0' in out, out)
    git(repo, 'push', '-q', 'origin', 'feature/x', 'v1.0.0')
    rc, out = run('svc-dev', '--dry-run')
    check('标签参数取当前提交上的标签，并显示对应提交',
          rc == 0 and 'repoTag = v1.0.0' in out and 'v1.0.0 @' in out and 'feature/x @' in out, out)

    (repo / '.jenkins-deploy.json').write_text('{"job": "team/svc-dev"}')
    rc, out = run('--dry-run')
    check('不指定任务时使用仓库根目录 .jenkins-deploy.json 里的任务', rc == 0 and '任务:   team/svc-dev' in out, out)
    (repo / '.jenkins-deploy.json').unlink()

    fake = tmp / 'no-requests'
    fake.mkdir()
    (fake / 'requests.py').write_text('raise ImportError("requests should not be used")')
    rc, out = run('svc-dev', '--dry-run', env={'PYTHONPATH': str(fake)})
    check('只依赖标准库（屏蔽 requests 后仍可运行）', rc == 0 and '确认码' in out, out)

    rc, out = run('svc-dev')
    check('非交互环境不能走交互式触发', rc == 1 and '--dry-run' in out, out)

    server.shutdown()
    passed = sum(results)
    print(f"\n{passed}/{len(results)} 通过")
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
