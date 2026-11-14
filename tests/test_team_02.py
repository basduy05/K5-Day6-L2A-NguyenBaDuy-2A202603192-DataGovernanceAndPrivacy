"""Unit tests cho Pipeline Track T02 - Nhóm Nguyen Ba Duy."""
from pathlib import Path
import pandas as pd
import pytest

from src.common.context import RunContext
from src.common.review import AuditLog
from src.pipeline import decide, load, process, rank


@pytest.fixture
def run_context(tmp_path):
    input_dir = Path("fixtures/t02_raw_qc")
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    return RunContext(
        track="t02",
        input_dir=input_dir,
        output_dir=output_dir,
        config={"track": "t02", "owner": "Nguyen Ba Duy (Data Lead)", "strict_provenance": False},
        seed=42,
        rng=None,
        run_name="test_run",
        offline=True,
        audit=AuditLog(output_dir / "audit_log.jsonl"),
    )


def test_t02_pipeline_success_e2e(run_context):
    """Test 1 (Success Mode): Kiểm tra pipeline chạy trơn tru 5 bước, sinh đủ các cột bắt buộc."""
    data = load(run_context)
    assert "images" in data
    assert len(data["images"]) > 0

    scored = process(run_context, data)
    assert "score" in scored.columns
    assert "image_id" in scored.columns
    assert not scored["score"].isnull().any(), "Điểm score không được chứa giá trị NaN"

    queue = rank(run_context, scored)
    assert len(queue) == 20
    assert (run_context.output_dir / "review_queue.csv").exists()
    assert (run_context.output_dir / "contact_sheet.html").exists()

    decision = decide(run_context, scored)
    assert decision.status in ("GO", "HOLD", "REWORK")
    assert decision.owner == "Nguyen Ba Duy (Data Lead)"


def test_t02_edge_case_small_batch(run_context):
    """Test 2 (Edge/Failure Mode): Kiểm tra pipeline xử lý an toàn khi tập dữ liệu bị thu hẹp."""
    data = load(run_context)
    # Thử nghiệm với batch siêu nhỏ chỉ gồm 2 ảnh
    mini_data = {"images": data["images"].head(2).copy()}
    scored = process(run_context, mini_data)
    assert len(scored) == 2
    assert isinstance(float(scored["score"].iloc[0]), float)