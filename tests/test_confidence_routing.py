import unittest
from unittest.mock import Mock, patch

from exercises import exercise_1_confidence as ex
from tests.fixtures import PR_URL, analysis, pull_request


class ConfidenceRoutingTests(unittest.TestCase):
    def test_boundary_values_route_without_rounding(self):
        cases = [(0, "escalate"), (0.5799, "escalate"), (0.58, "human_approval"),
                 (0.72, "human_approval"), (0.7299, "human_approval"),
                 (0.73, "auto_approve"), (1, "auto_approve")]
        for confidence, expected in cases:
            with self.subTest(confidence=confidence):
                self.assertEqual(ex.node_route({"analysis": analysis(confidence)})["decision"], expected)

    def test_complete_graph_reaches_each_branch_with_analysis(self):
        for confidence, expected in [(0.9, "auto_approved"), (0.65, "pending_human_approval"),
                                     (0.4, "pending_escalation")]:
            llm = Mock()
            llm.with_structured_output.return_value.invoke.return_value = analysis(confidence)
            with self.subTest(confidence=confidence), patch.object(ex, "fetch_pr", return_value=pull_request()), patch.object(ex, "get_llm", return_value=llm):
                result = ex.build_graph().invoke({"pr_url": PR_URL})
                self.assertEqual(result["final_action"], expected)
                self.assertEqual(result["analysis"].summary, "Adds task priority.")
                prompt = llm.with_structured_output.return_value.invoke.call_args.args[0]
                self.assertIn("priority = 1", prompt[-1]["content"])


if __name__ == "__main__":
    unittest.main()
