"""Isolated Yukon experiments. Config, prompts and raw output remain ignored."""
import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'rtx2080/experiments/iq1m-current'))
import campaign as c

c.R = ROOT / 'runtime/yukon-three-20261101'
c.BASE = json.loads((c.R / 'production-config.json').read_text())
c.CANDIDATE = ROOT / 'build/yukon-three/strata'
c.ARM_ENV = {'baseline': {}, 'candidate-off': {},
             'commit': {'STRATA_YUKON_COMMIT': '1', 'STRATA_YUKON_COMMIT_SPLIT': '1'},
             'projections': {'STRATA_YUKON_PROJECTIONS': '1'},
             'head-layout': {'STRATA_YUKON_HEAD_LAYOUT': '1'},
             'head': {'STRATA_YUKON_HEAD': '1'}}


def protected():
    for name, expected in json.loads((c.R / 'protected.json').read_text()).items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['profile', 'speed', 'edit', 'needle', 'smoke', 'agents', 'longagent'])
    p.add_argument('--arm', default='baseline', choices=list(c.ARM_ENV))
    p.add_argument('--label', required=True)
    a = p.parse_args()
    protected()
    if a.arm == 'baseline':
        c.CANDIDATE = ROOT / 'runtime/bin/strata'
    c.dump(c.R / (a.label + '.source.json'), {
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'tracked_diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff', 'HEAD'], cwd=ROOT)).hexdigest(),
        'profile_sha256': hashlib.sha256((ROOT / 'rtx2080/profile.json').read_bytes()).hexdigest(),
        'instrumented': a.mode == 'profile',
    })
    if a.mode in ('agents', 'longagent'):
        import agents
        sys.argv = ['agents.py', a.arm, '--prefix', a.label] + (['--long'] if a.mode == 'longagent' else [])
        agents.main()
        protected()
        return
    extra = {}
    if a.mode == 'profile':
        extra = {'STRATA_VERIFY_PROFILE': '1', 'STRATA_PREFILL_TIMING': '1',
                 'STRATA_COMMIT_TIMING': '1', 'STRATA_DECODE_TIMING': '1'}
    import harness
    done = threading.Event()
    worker = threading.Thread(target=harness.telemetry, args=(done,), daemon=True)
    worker.start()
    try:
        run_request_suite(a, extra)
    finally:
        done.set()
        worker.join(timeout=10)
    protected()
    c.dump(c.R / (a.label + '.complete.json'), {'complete': True})


def run_request_suite(a, extra):
    with c.server(a.label, a.arm, extra=extra):
        if a.mode == 'smoke':
            smoke(a.label, a.arm)
        elif a.mode == 'speed':
            c.speed(a.label)
        elif a.mode == 'edit':
            assert c.edit(a.label, arm=a.arm)
        elif a.mode == 'needle':
            c.needle(a.label, arm=a.arm)
        else:
            body = json.loads(gzip.decompress((c.R / 'fixtures/edit-task.json.gz').read_bytes()))
            sys.path.insert(0, str(ROOT / 'tools'))
            import strata_bench as bench
            b = bench.Suite('http://127.0.0.1:8087', '', 131072, 1, True)
            b.calibrate()
            for size in (32768, 122451):
                request = copy.deepcopy(body)
                if size == 32768:
                    request['messages'] = b.prompt_for(size, 0)
                request['messages'].append({'role': 'user', 'content':
                    'Write a detailed Python implementation of an LRU cache with TTL, thread safety, '
                    'unit tests, and an explanation of correctness. Include complete code.'})
                request.pop('reasoning_effort', None)
                request['chat_template_kwargs'] = {'enable_thinking': True}
                request.update(max_tokens=1536, temperature=0)
                c.sample(f'{a.label}-{size}', request, arm=a.arm, phase='cold-profile')
                c.sample(f'{a.label}-{size}-warm', request, arm=a.arm, phase='warm-profile')


def smoke(label, arm):
    base = {'model': 'local-model', 'temperature': 0, 'seed': 42, 'max_tokens': 64,
            'chat_template_kwargs': {'enable_thinking': False},
            'messages': [{'role': 'user', 'content': 'What is 6 times 7? Reply with only the integer.'}]}
    for phase in ('greedy', 'sampled-logprobs', 'penalized', 'greedy-again'):
        body = copy.deepcopy(base)
        if phase == 'sampled-logprobs':
            body.update(temperature=0.7, logprobs=True, top_logprobs=3)
        if phase == 'penalized':
            body.update(temperature=0.7, presence_penalty=0.2, frequency_penalty=0.2)
        text, row = c.sample(label + '-' + phase, body, arm=arm, phase=phase)
        assert '42' in text, (phase, text)
        if phase == 'sampled-logprobs':
            chunks = json.loads((c.R / (label + '-' + phase + '.response.json')).read_text())
            probs = [v for chunk in chunks for choice in chunk.get('choices', [])
                     for v in (choice.get('logprobs') or {}).get('content', [])]
            assert probs and all(math.isfinite(v['logprob']) for v in probs), probs
        c.record(event='smoke_correctness', label=label, arm=arm, phase=phase, passed=True)
    body = copy.deepcopy(base)
    body.update(max_tokens=256, tools=[{'type': 'function', 'function': {
        'name': 'report_status', 'description': 'Report the supplied status value.',
        'parameters': {'type': 'object', 'properties': {'value': {'type': 'string'}}, 'required': ['value']}}}],
        tool_choice={'type': 'function', 'function': {'name': 'report_status'}},
        messages=[{'role': 'user', 'content': 'Call report_status with value CONFIG_OK.'}])
    c.sample(label + '-tool', body, arm=arm, phase='forced-tool')
    chunks = json.loads((c.R / (label + '-tool.response.json')).read_text())
    calls = {}
    for chunk in chunks:
        for choice in chunk.get('choices', []):
            for call in choice.get('delta', {}).get('tool_calls', []):
                out = calls.setdefault(call['index'], {'name': '', 'arguments': ''})
                for key in out:
                    out[key] += call.get('function', {}).get(key) or ''
    assert any(v['name'] == 'report_status' and json.loads(v['arguments']) == {'value': 'CONFIG_OK'}
               for v in calls.values()), calls
    c.record(event='smoke_correctness', label=label, arm=arm, phase='forced-tool', passed=True)


if __name__ == '__main__':
    main()
