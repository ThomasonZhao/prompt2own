from concurrent.futures import ThreadPoolExecutor

from p2o.budget import Budget


def test_parallel_record_and_read_is_safe(tmp_path):
    # batch --parallel: runs read the budget (can_start) while others record; reads must never
    # see a half-written file and no spend may be lost
    b = Budget(tmp_path / "budget.json", 1000.0)

    def work(i):
        b.record("p3" if i % 2 else "b1", 0.01)
        return b.can_start(0.75), b.remaining()

    with ThreadPoolExecutor(max_workers=16) as ex:
        res = list(ex.map(work, range(400)))
    assert all(ok for ok, _ in res)
    assert abs(b.spent() - 4.0) < 1e-6
    d = b._read()
    assert abs(d["by_config"]["p3"] - 2.0) < 1e-6 and abs(d["by_config"]["b1"] - 2.0) < 1e-6
    assert not list(tmp_path.glob(".budget.json.*.tmp"))
