"""Bound repeated thinking while preserving the task, sampler and total output cap."""
import threading
import unittest
from serve.server import Service, REASONING_WRAP_UP
from serve.test_reasoning_loop_recovery import Tokenizer, RecordingEngine


class ReasoningLoopClose(unittest.TestCase):
    def setUp(self):
        self.tok = Tokenizer()
        self.ids = self.tok.encode('<|im_start|>user\nFix the import.<|im_end|>\n'
                                   '<|im_start|>assistant\n<think>\n', parse_special=True)
        self.loop = 'The import must remain correct for both compilation and execution. ' * 600

    def run_case(self, script=None, cap=20000, thinking=True, mode='close', second='Fixed.'):
        engine = RecordingEngine(self.tok, [script or self.loop, second])
        svc = Service(engine, self.tok, None)
        svc.answer_room = False
        svc.reasoning_loop_recovery = mode
        sampling = {'temperature': 0, 'seed': 42, 'top_p': .9}
        events = list(svc.run(self.ids, thinking, [], cap, sampling, threading.Event()))
        return engine, svc, events, sampling

    def test_closes_without_system_effort_hint_and_keeps_prompt_and_sampler(self):
        engine, svc, events, sampling = self.run_case()
        self.assertEqual(len(engine.calls), 2)
        self.assertEqual(engine.calls[1][0][:len(self.ids)], self.ids)
        self.assertTrue(self.tok.decode(engine.calls[1][0]).endswith(REASONING_WRAP_UP))
        self.assertEqual(engine.sampling_calls, [sampling, sampling])
        content = ''.join(e.text or '' for kind, e in events if kind == 'event' and e.kind == 'content')
        self.assertEqual(content, 'Fixed.')
        self.assertEqual(events[-1][1]['finish'], 'stop')
        self.assertEqual(events[-1][1]['reasoning_recoveries'], 1)
        self.assertLess(events[-1][1]['completion_tokens'], 16000)
        added = len(engine.calls[1][0]) - len(self.ids)
        self.assertEqual(engine.calls[1][1], 20000-added)
        self.assertEqual(svc.history[-1]['reasoning_recoveries'], 1)

    def test_never_exceeds_shared_cap(self):
        engine, _, events, _ = self.run_case(cap=16000, second='A useful answer. ' * 2000)
        self.assertLessEqual(events[-1][1]['completion_tokens'], 16000)
        self.assertEqual(len(engine.calls), 2)

    def test_small_budget_does_not_restart_after_exhaustion(self):
        engine, _, events, _ = self.run_case(cap=1000)
        self.assertEqual(events[-1][1]['completion_tokens'], 1000)
        self.assertEqual(len(engine.calls), 1)

    def test_recovery_can_emit_a_tool_call(self):
        engine = RecordingEngine(self.tok, [self.loop,
            '<tool_call>\n<function=read>\n<parameter=path>index.ts</parameter>\n</function>\n</tool_call>'])
        svc = Service(engine, self.tok, None)
        svc.answer_room = False
        svc.reasoning_loop_recovery = 'close'
        tools = [{'name': 'read', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}}}]
        events = list(svc.run(self.ids, True, tools, 20000, {}, threading.Event()))
        calls = [e for kind, e in events if kind == 'event' and e.kind == 'tool_call']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].call.name, 'read')
        self.assertEqual(events[-1][1]['reasoning_recoveries'], 1)

    def test_cancellation_never_starts_a_second_generation(self):
        engine = RecordingEngine(self.tok, [self.loop, 'Unused'])
        svc = Service(engine, self.tok, None)
        svc.reasoning_loop_recovery = 'close'
        cancel = threading.Event()
        events = []
        for ev in svc.run(self.ids, True, [], 20000, {}, cancel):
            events.append(ev)
            if ev[0] == 'event': cancel.set()
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(events[-1][1]['finish'], 'cancel')

    def test_useful_nonrepeating_thinking_is_unchanged(self):
        text = ' '.join(str(i) for i in range(3000)) + '\n</think>\nDone.'
        engine, _, events, _ = self.run_case(script=text)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(events[-1][1]['reasoning_recoveries'], 0)

    def test_repeated_visible_output_is_not_treated_as_thinking(self):
        engine, _, events, _ = self.run_case(thinking=False)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(events[-1][1]['reasoning_recoveries'], 0)

    def test_disabled_remains_unchanged(self):
        engine, _, events, _ = self.run_case(mode=False)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(events[-1][1]['completion_tokens'], 20000)


if __name__ == '__main__':
    unittest.main()
