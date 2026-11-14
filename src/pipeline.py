"""PoC Pipeline cho Track T02 - Raw QC Triage.
Tuân thủ 5 bước contract: 01 load -> 02 process -> 03 rank -> 04 review -> 05 decide
Chạy 100% offline, không chạm ground-truth, ghi vết audit log đầy đủ.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from .common.contact_sheet import render_contact_sheet
from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.image_ops import brightness_stats, laplacian_variance, load_rgb, to_gray
from .common.manifest import verify_manifest
from .common.review import apply_overrides, load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track


# ---------------------------------------------------------------- 01 LOAD
def load(ctx: RunContext) -> dict:
    manifest_path = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest_path) if manifest_path.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest_path), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            # Nếu chạy trên Windows gặp cảnh báo CRLF, có thể tạm thời đặt strict_provenance: false trong lab.yaml
            raise ValueError(f"Provenance check failed ({len(problems)} problems), first: {problems[:2]}")

    images_csv = ctx.input_dir / "images.csv"
    if not images_csv.exists():
        raise FileNotFoundError(f"Không tìm thấy file {images_csv}")

    return {
        "manifest": pd.read_csv(manifest_path) if manifest_path.exists() else None,
        "images": pd.read_csv(images_csv),
    }


# ---------------------------------------------------------------- 02 PROCESS
def _compute_jpeg_blockiness(gray: np.ndarray) -> float:
    """Đo độ gián đoạn trên lưới khối 8x8 (đặc trưng nén vỡ hình JPEG)."""
    H, W = gray.shape
    if H < 16 or W < 16:
        return 0.0
    diff_h = np.abs(gray[:, 7::8][:, :-1] - gray[:, 8::8])
    diff_normal = np.abs(gray[:, 6::8][:, :-1] - gray[:, 7::8][:, :-1])
    return float(np.mean(diff_h) / max(np.mean(diff_normal), 1e-4))


def process(ctx: RunContext, data: dict) -> pd.DataFrame:

    if ctx.track != "t02":
        raise NotImplementedError(f"Nhóm chỉ triển khai PoC cho track t02, chưa hỗ trợ {ctx.track}")
    
    df = data["images"].copy()
    raw_records = []    
      
    # 1. Trích xuất đặc trưng thuần túy của từng ảnh
    for _, row in df.iterrows():
        img_path = ctx.input_dir / row["path"]
        img_rgb = load_rgb(img_path)
        img_gray = to_gray(img_rgb)

        # Đo độ sắc nét Laplacian toàn ảnh
        lap_var = laplacian_variance(img_rgb)

        # Đo độ sắc nét vùng tâm ảnh (vùng quan trọng của camera giao thông)
        H, W = img_gray.shape
        roi = img_rgb[H // 4 : 3 * H // 4, W // 4 : 3 * W // 4]
        lap_roi = laplacian_variance(roi)

        # Thống kê độ sáng (tối, bão hòa/lóa)
        b_stats = brightness_stats(img_rgb)

        # Đo độ vỡ khối JPEG
        blk = _compute_jpeg_blockiness(img_gray)

        raw_records.append({
            "image_id": row["image_id"],
            "lap_var": lap_var,
            "lap_roi": lap_roi,
            "frac_dark": b_stats["frac_dark"],
            "frac_sat": b_stats["frac_saturated"],
            "mean_b": b_stats["mean"],
            "p95": b_stats["p95"],
            "blockiness": blk,
        })

    feat_df = pd.DataFrame(raw_records)
    merged = df.merge(feat_df, on="image_id")

    # 2. Chuẩn hóa có điều kiện theo metadata (camera_id x light) trên tập dev
    stats_map = {}
    for (cam, light), grp in merged.groupby(["camera_id", "light"]):
        stats_map[(cam, light)] = {
            "lap_mean": grp["lap_var"].mean(),
            "lap_std": max(grp["lap_var"].std(), 1e-3),
            "dark_mean": grp["frac_dark"].mean(),
            "dark_std": max(grp["frac_dark"].std(), 1e-3),
            "sat_mean": grp["frac_sat"].mean(),
            "sat_std": max(grp["frac_sat"].std(), 1e-3),
            "blk_mean": grp["blockiness"].mean(),
            "blk_std": max(grp["blockiness"].std(), 1e-3),
        }

    scored_records = []
    for _, row in merged.iterrows():
        st = stats_map.get((row["camera_id"], row["light"]))

        # Điểm Z-Score: giá trị càng cao thể hiện nguy cơ lỗi càng lớn
        z_blur = (st["lap_mean"] - row["lap_var"]) / st["lap_std"]
        z_dark = (row["frac_dark"] - st["dark_mean"]) / st["dark_std"]
        z_glare = (row["frac_sat"] - st["sat_mean"]) / st["sat_std"]
        z_comp = (row["blockiness"] - st["blk_mean"]) / st["blk_std"]

        # Điều chỉnh ngữ cảnh: ban đêm giảm phạt tối, tăng phạt lóa đèn pha
        if row["light"] == "night":
            z_dark = max(0.0, z_dark * 0.5)
            z_glare = z_glare * 1.3

        defect_scores = {
            "blur": float(z_blur),
            "glare": float(z_glare),
            "dark": float(z_dark),
            "compression": float(z_comp),
        }
        pred_defect = max(defect_scores, key=defect_scores.get)
        composite_score = max(defect_scores.values())

        pred_action = "RECAPTURE" if composite_score > 1.2 else "KEEP"

        scored_records.append({
            "image_id": row["image_id"],
            "score": float(composite_score),
            "pred_defect_type": pred_defect,
            "pred_action": pred_action,
            "reason": f"Top risk: {pred_defect} (z={defect_scores[pred_defect]:.2f})",
        })

    return merged.merge(pd.DataFrame(scored_records), on="image_id")


# ---------------------------------------------------------------- 03 RANK
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    budget = int(ctx.param("budget", 20))
    q = make_review_queue(
        scored,
        id_col="image_id",
        score_col="score",
        budget=budget,
        reason_col="reason",
        evidence_col="path",
    )
    write_review_queue(q, ctx.out("review_queue.csv"))

    # Sinh file HTML kiểm duyệt trực quan offline
    render_contact_sheet(
        q,
        ctx.out("contact_sheet.html"),
        image_root=ctx.input_dir,
        title=f"T02 Review Queue (Top {budget} Suspicious Frames)",
    )
    return q


# ---------------------------------------------------------------- 04 REVIEW
# ---------------------------------------------------------------- 04 REVIEW
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if reviewed_path.exists():
        reviewed = load_review_decisions(reviewed_path)
        ctx.stats["n_reviewed"] = len(reviewed)

        # Áp dụng ghi đè quyết định của kiểm duyệt viên vào cột pred_action và tự động ghi log audit
        updated = apply_overrides(
            scored,
            reviewed,
            id_col="image_id",
            value_col="pred_action",
            audit=ctx.audit,
        )
        return updated

    return scored


# ---------------------------------------------------------------- 05 DECIDE
def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    budget = int(ctx.param("budget", 20))
    top_candidates = final.sort_values("score", ascending=False).head(budget)
    defect_count = (top_candidates["pred_action"] == "RECAPTURE").sum()
    owner = ctx.config.get("owner", "Nguyen Ba Duy (Data Lead)")

    # Nếu chưa có ai review qua file CSV -> giữ lại (HOLD)
    if ctx.stats.get("n_reviewed", 0) == 0:
        return Decision(
            status="HOLD",
            reason_code="AWAITING_HUMAN_REVIEW",
            reason=f"Top {budget} ảnh cần được kiểm duyệt viên thẩm định qua contact_sheet.html",
            owner=owner,
            scope=ctx.track,
            evidence=[str(ctx.out("review_queue.csv"))],
        )

    # Nếu tỷ lệ ảnh hỏng quá cao (> 60% trong top) -> REWORK yêu cầu chụp lại
    if defect_count >= 12:
        return Decision(
            status="REWORK",
            reason_code="EXCESSIVE_DEFECT_RATE",
            reason=f"Phát hiện {defect_count}/{budget} ảnh lỗi nghiêm trọng, yêu cầu thu thập lại cảnh chụp",
            owner=owner,
            scope=ctx.track,
            evidence=[str(ctx.out("ranked_review.csv"))],
        )

    return Decision(
        status="GO",
        reason_code="QUALITY_ASSURED",
        reason="Dữ liệu đã qua thẩm định của kiểm duyệt viên, đạt chuẩn giải phóng vào tập huấn luyện",
        owner=owner,
        scope=ctx.track,
        evidence=[str(ctx.out("ranked_review.csv"))],
    )


# ---------------------------------------------------------------- RUNNER CONTRACT
def run(ctx: RunContext) -> None:
    # Đặt 2 dòng này ngay trên cùng của hàm run:
    if ctx.track != "t02":
        raise NotImplementedError(f"Nhóm chỉ triển khai PoC cho track t02, chưa hỗ trợ {ctx.track}")

    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)

    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)

    output_cols = spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]
    final[output_cols].to_csv(ctx.out(spec.pred_file), index=False)

    decision_obj = decide(ctx, final)
    write_decision(decision_obj, ctx.out("decision.json"), ctx.out("decision_log.csv"))