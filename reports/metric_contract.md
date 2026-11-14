# Metric contract (khai báo bắt buộc — chốt ở phút 30, trước khi chạy eval)

> Các metric chuẩn đã được cài trong `src/metrics/tracks.py`. File này là nơi nhóm **cam kết** cách dùng chúng.
> Không đổi testset, threshold hay trọng số sau khi đã thấy kết quả eval.

| Mục | Khai báo của nhóm |
|---|---|
| Track | `t02` (Raw QC Triage: ảnh mờ, lóa và thiếu sáng) |
| Primary metric (tên đúng như evaluator in ra) | `Defect Recall@B` |
| Tăng tốt hay giảm tốt? | `higher` |
| Đơn vị đánh giá (image / region / pair / release / batch / case …) | `image` (từng ảnh camera tĩnh $320 \times 180$) |
| Công thức + numerator / denominator | $\text{Defect Recall@B} = \frac{\text{hits}}{\|Pos\|}$<br>• Numerator: `hits` (số ảnh có $is\_defect == 1$ nằm trong top B dự đoán)<br>• Denominator: $\|Pos\|$ (tổng số ảnh có $is\_defect == 1$ trong tập eval)<br>• Kèm theo: $\text{Precision@B} = \frac{\text{hits}}{B}$ |
| Cách ghép prediction ↔ GT (IoU? id? tolerance?) | Khớp định danh chính xác 1-1 qua `image_id` (chuỗi); sắp xếp theo `score` giảm dần (thuật toán mergesort ổn định) |
| Candidate pool cố định | 96 ảnh synthetic từ 24 cảnh gốc (`fixtures/t02_raw_qc/images.csv`), phân rã theo scene-level split |
| Review budget B / K | $B = 20$ ảnh |
| Seed | `42` (cố định cho mọi hàm tạo mẫu, xáo trộn và trích chọn) |
| Threshold policy (chọn trên dev như thế nào) | Tính kỳ vọng $\mu$ và độ lệch chuẩn $\sigma$ của 4 đặc trưng trên 56 ảnh tập `dev` theo từng cặp `(camera_id, light)`. Đóng băng ngưỡng cảnh báo rủi ro sơ bộ khi điểm lệch chuẩn $Z_{\text{composite}} > 1.2$. Tuyệt đối không dò ngưỡng trên tập `eval`. |
| Eval split (không dùng để tune) | `eval` (gồm 40 ảnh thuộc 10 cảnh độc lập hoàn toàn với tập `dev`) |
| Chỉ số lỗi xấu (miss / false alarm / false reject) | • **Critical Miss (FN)**: Ảnh lỗi thật bị bỏ sót ngoài Top-B ($is\_defect == 1 \land rank > B$).<br>• **False Alarm (FP)**: Ảnh sạch bị đưa nhầm vào Top-B ($is\_defect == 0 \land rank \le B$). Tỷ lệ: $\frac{\text{FP}}{\text{Tổng ảnh sạch trong eval}}$. |
| Slices sẽ báo cáo (≥2) | 1. **Slice `light`**: `day`, `dusk`, `night` (báo cáo Recall và False Alarm riêng từng lát cắt)<br>2. **Slice `defect_type`**: `blur`, `glare`, `dark`, `compression`<br>3. **Slice `camera_id`**: `cam_A` (nét cao) vs `cam_B` (quang học mềm) |
| Cách báo độ bất định khi N nhỏ (Wilson CI / bootstrap) | Báo cáo khoảng tin cậy 95% **Wilson Score Interval** cho tỷ lệ nhị thức của Recall@B; dùng **Bootstrap BCa 1,000 resamples** (seed 42) để ước lượng khoảng tin cậy cho mức tăng trưởng $\Delta(\text{PoC} - \text{Baseline})$. |
| Ngày giờ chốt + người chốt | 2026-11-14 14:55 GMT+7 · Nguyen Ba Duy (Data Lead / Owner) |

Nếu baseline = 0 thì ghi rõ "baseline = 0" thay vì phần trăm cải thiện.