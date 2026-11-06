"""Worker prompts must not carry the task id (SUBMISSION FAQ: ids map to public issue trackers)."""
import os

from p2o import prompts
from p2o.types import Stage

ROOT = os.path.dirname(os.path.dirname(__file__))


def test_stage_prompts_do_not_contain_task_id():
    tid = "someproj/arvo_123456"
    for stage in (Stage.RCA, Stage.POC, Stage.PATCH):
        text = prompts.render_stage(os.path.join(ROOT, "p2o/stages"), stage, task_id=tid, src_path="/src",
                                    workspace="/p2o/work/x/1", facts="(none)", last_reason="no_sanitizer_report")
        assert "arvo_123456" not in text and tid not in text
        assert "{" + "task_id" + "}" not in text
