"""M3 acceptance: real guards against a dev task. Run on the VM: pytest -m docker -q
Positive control uses the dev task's ground-truth PoC; this file must never be imported by p2o/."""
import pytest

pytestmark = pytest.mark.docker


@pytest.mark.skip(reason="M3: implement once CyberGymE2EAdapter.run_poc exists")
def test_exec_poc_positive_negative():
    ...


@pytest.mark.skip(reason="M3: implement once apply_patch_and_build exists")
def test_exec_patch_rejects_empty_patch():
    ...
