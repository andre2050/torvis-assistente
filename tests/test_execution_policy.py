import unittest
from core.execution_policy import ExecutionPolicy, call_signature

class ExecutionPolicyTests(unittest.TestCase):
    def test_signature_is_stable_across_argument_order(self):
        self.assertEqual(call_signature('x', {'a': 1, 'b': 2}), call_signature('x', {'b': 2, 'a': 1}))

    def test_loop_guard_trips_after_repeated_requests(self):
        p = ExecutionPolicy(max_duplicate_requests=3)
        for _ in range(3): p.observe('search', {'q': 'same'})
        self.assertTrue(p.stalled('search', {'q': 'same'}))

if __name__ == '__main__': unittest.main()
