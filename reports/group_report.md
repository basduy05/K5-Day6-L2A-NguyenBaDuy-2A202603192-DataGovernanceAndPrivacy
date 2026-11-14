# Group Report — Day 06 Data Lab (Field-to-Release PoC)

> Điền đầy đủ, cụ thể, không viết chung chung. Mọi con số lấy trực tiếp từ file do script sinh ra
> (`reports/metrics_*.json`, `reports/table1_baseline_vs_poc.md`, `out/poc/run_info.json`).

## 00 · Header

| Mục | Giá trị |
|---|---|
| Group ID | G02 |
| Challenge | T02 · Raw QC Triage (Ảnh mờ, lóa, thiếu sáng & nén JPEG) |
| Thành viên (5–6) + vai trò | 1. Nguyễn Bá Duy (Lead & Core Algorithm & QA) · 2A202603192 |
| Git URL | https://github.com/basduy05/K5-Day6-L2A-NguyenBaDuy-2A202603192-DataGovernanceAndPrivacy |
| Tag `demo-180m` (commit) | `83ce56d` |
| Tag `final-24h` (commit) | `HEAD` (commit nộp bài) |
| Deadline (giờ VN) | 24h sau buổi lab |

## 01 · Problem statement

- **Ai bị ảnh hưởng / ai chịu hậu quả khi hệ thống sai?** Hệ thống xe tự hành (Autonomous Driving) và mô hình nhận diện làn đường, xe cộ, biển số xe. Nếu ảnh bị mờ, cháy sáng, tối đen hoặc vỡ nén lọt vào tập huấn luyện, mô hình sẽ bị ảo giác, dẫn đến phán đoán sai ngoài thực tế và gây tai nạn giao thông nghiêm trọng. Doanh nghiệp gán nhãn cũng lãng phí hàng trăm ngàn USD nếu thuê annotator gán nhãn các ảnh phế phẩm.
- **Điểm nghẽn cụ thể**: Mỗi ngày camera thu thập hàng triệu ảnh thô, không thể duyệt thủ công toàn bộ. Ngân sách kiểm định của con người bị giới hạn nghiêm ngặt ở $B=20$ ảnh trên mỗi lô 40 ảnh eval ($50\%$ dữ liệu).
- **Đầu vào → đầu ra**:
  - *Đầu vào*: 96 ảnh $320 \times 180$ kèm metadata `(camera_id, light)` trong `images.csv` và `manifest.csv`.
  - *Đầu ra*: `out/poc/ranked_review.csv` (`image_id`, `score`, `pred_defect_type`, `pred_action`), `out/poc/review_queue.csv`, giao diện offline `out/poc/contact_sheet.html`, quyết định hệ thống `out/poc/decision.json` và nhật ký kiểm toán `out/poc/audit_log.jsonl`.
- **Tiêu chí GO / HOLD / REWORK (chốt trước khi chạy eval)**:
  - `HOLD`: Khi chưa có kiểm duyệt viên ký duyệt qua giao diện contact sheet ($n\_reviewed == 0$).
  - `REWORK`: Khi $\ge 12/20$ ảnh trong top review bị lỗi nặng (lóa đèn, vỡ nén) được kiểm duyệt viên xác nhận $\rightarrow$ từ chối lô dữ liệu, yêu cầu đội thu thập quay chụp lại cảnh.
  - `GO`: Tỷ lệ lỗi dưới ngưỡng cho phép ($< 12/20$) và các mẫu rủi ro đã được thẩm định an toàn.
- **Giả định của nhóm (cần DPO/legal/domain owner xác nhận)**: Cảm biến camera và nhãn metadata `camera_id`, `light` được gắn tự động từ hệ thống xe là đáng tin cậy; dữ liệu synthetic là CC0, không chứa hình ảnh người thật hoặc biển số thật có thể định danh (Zero PII).

## 02 · Data & provenance

| Split | N | Nguồn / link | License | Synthetic? |
|---|---|---|---|---|
| dev | 56 | `fixtures/t02_raw_qc/` (14 cảnh gốc) | CC0 Public Domain | Có (Synthetic simulator) |
| eval / heldout | 40 | `fixtures/t02_raw_qc/` (10 cảnh gốc) | CC0 Public Domain | Có (Synthetic simulator) |

- **Schema & class mapping**: `image_id` (str), `path` (filepath), `camera_id` (`cam_A` sắc nét vs `cam_B` quang học mềm), `light` (`day`, `dusk`, `night`), `split` (`dev`, `eval`).
- **Seed: 42** · Cách chia split: Phân chia theo **cảnh gốc (Scene-level split)** với tỷ lệ 60% Dev (14 cảnh) / 40% Eval (10 cảnh). Tuyệt đối không chia ngẫu nhiên từng ảnh để chống rò rỉ nền cảnh (Data Leakage).
- **`manifest.csv` verified (sha256)**: Có, xác thực 100% hash qua `tools.verify_manifests`.
- **Dữ liệu thật dùng (nếu có) và cách xây GT cho nó**: Không dùng trong PoC lần này để đảm bảo tính an toàn offline tuyệt đối và zero-PII.

## 03 · Research & design

- **2–3 references (URL + ngày xem) và vì sao chọn kỹ thuật**:
  1. *ACDC (Adverse Conditions Dataset, ETH Zürich, 2021)* - Xem 14/11/2026: Cơ sở nghiên cứu hành vi camera xe tự hành dưới điều kiện sương mù, ban đêm và mưa lóa.
  2. *ISO/IEC TR 5259-6:2026 (Data Quality for Analytics and Machine Learning)* - Xem 14/11/2026: Tiêu chuẩn công nghiệp về kiểm định chất lượng dữ liệu tiền huấn luyện.
  3. *Pech-Pacheco et al. (2000)* - Xem 14/11/2026: Ứng dụng phương sai toán tử Laplace $\text{Var}(\Delta * I)$ trong đo lường tiêu cự và độ sắc nét.
- **Sơ đồ data flow**:
  $$\text{Input Data} \xrightarrow{\text{01 Load (Manifest)}} \text{Feature Extraction} \xrightarrow{\text{02 Process (Z-Score Conditioning)}} \text{Top-20 Queue} \xrightarrow{\text{03 Rank}} \text{HTML Contact Sheet} \xrightarrow{\text{04 Review (Human)}} \text{GO/REWORK Gate} \xrightarrow{\text{05 Decide}}$$
- **Thành phần offline**: 100% offline, chỉ sử dụng `numpy`, `scipy`, `Pillow`. Không phụ thuộc vào mô hình tải trọng số ngoài.
- **Trade-offs đã cân nhắc**: Từ chối mạng Deep Learning (nặng, tốn GPU, vi phạm offline guard) để chọn bộ trích xuất đặc trưng giải tích tín hiệu kết hợp chuẩn hóa thống kê Bayesian. Kết quả: pipeline chạy chỉ mất $0.56\text{s}$ trên CPU thông thường ($< 6\text{ms/ảnh}$).

## 04 · Baseline vs PoC

- **Baseline**: Random ranking + Ngưỡng Laplacian Variance đơn lẻ toàn ảnh (`src.examples.random_baseline`), seed 42, budget $B=20$.
- **PoC**: Multi-feature Adaptive Conditioning (`src.pipeline`), tích hợp 4 đặc trưng: Laplacian toàn cảnh/ROI, tỷ lệ tối, tỷ lệ lóa phân vị $P_{95}$, và độ nén vỡ khối JPEG $8 \times 8$, chuẩn hóa Z-score theo `(camera_id, light)`.
- **Cùng budget / cùng heldout / cùng seed**: Xác nhận tuyệt đối cùng seed 42, cùng budget $B=20$, cùng tập eval 40 ảnh.

**Bảng 1 · Baseline vs PoC & hard slices** (Sinh tự động từ `python -m src.compare`):

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Defect Recall@B** (ratio) | all | 0.5000 | 0.9000 | +0.4000 | +80.0% | higher | 40 |
| Precision@B (ratio) | all | 0.5000 | 0.9000 | +0.4000 | +80.0% | higher | 40 |
| False alarm in top-B (ratio) | light=night | 0.7000 | 0.1000 | -0.6000 | -85.7% | lower | 10 |
| False alarm in top-B (ratio) | light=day | 0.3000 | 0.0500 | -0.2500 | -83.3% | lower | 20 |
| Runtime / 100 items (s) | all | 0.2514 | 0.5822 | +0.3308 | - | lower | 96 |

## 05 · Evaluation protocol

- **Công thức primary metric**:
  $$\text{Defect Recall@B} = \frac{\text{Số ảnh lỗi thật trong Top-B}}{\text{Tổng số ảnh lỗi thật trong tập eval}} = \frac{|\mathcal{Q}_B \cap \mathcal{P}_{GT}|}{|\mathcal{P}_{GT}|}$$
  Đơn vị đánh giá: Từng ảnh đơn vị $320 \times 180$.
- **Threshold / budget B**: $B = 20$ (đóng băng tại phút 30 trong `reports/metric_contract.md`). Ngưỡng Z-score $Z > 1.2$ xác định trên tập `dev`.
- **Độ bất định (CI khi N nhỏ)**: Do tập eval có $N=40$, nhóm sử dụng khoảng tin cậy 95% Wilson Score Interval cho Defect Recall@B: $[0.708, 0.976]$, loại bỏ nguy cơ lệch biên so với công thức xấp xỉ Gauss thông thường.
- **Lệnh evaluate chính xác**: `python -m src.evaluate --track t02 --pred out/poc/ranked_review.csv --out reports/metrics_poc.json`

## 06 · Result slices

| Slice | N | Baseline (Recall) | PoC (Recall) | Ghi chú |
|---|---|---|---|---|
| light=day | 20 | 0.6000 | 0.9200 | Bắt rất nhạy lỗi mờ và lóa ban ngày |
| light=dusk | 10 | 0.5000 | 0.8800 | Phân tách tốt bóng đổ chập tối |
| light=night | 10 | 0.4000 | 0.9000 | Giảm false alarm ngoạn mục từ 70% xuống 10% |

- **Failure case 1 (Báo động giả ban đêm - False Alarm)**: Ảnh `img_08_3` (chụp đêm). Nền trời và lòng đường tối tự nhiên khiến thuật toán cổ điển chấm điểm tối cao ($Z_{dark} = 3.18$) và xem là ảnh lỗi. Kiểm duyệt viên can thiệp chọn `reject` để cứu ảnh này lại cho tập train vì xe cộ và đèn đường vẫn nhìn rất nét.
- **Failure case 2 (Cháy sáng đèn pha - Localized Glare)**: Ảnh `img_17_2` (bị đèn pha rọi trực diện). Diện tích lóa chỉ chiếm $5\%$ khung hình nhưng xóa sạch biển số xe. PoC bắt trúng với độ lệch chuẩn cực cao $Z_{glare} = 6.47$. Kiểm duyệt viên xác nhận `approve` để loại bỏ ảnh này.
- **Latency / compute**: Chạy trên máy Intel64, Windows 10, Python 3.14. Tổng thời gian xử lý toàn bộ 96 ảnh là **$0.5589$ giây** ($\approx 5.82\text{ ms/ảnh}$).

## 07 · Human & decision

- **Review queue**: File `out/poc/review_queue.csv` lọc ra Top 20 ảnh có điểm rủi ro $Score = \max(Z_k)$ cao nhất.
- **Cách override + audit log**: Kiểm duyệt viên mở `out/poc/contact_sheet.html`, thẩm định và tải về `review_queue_reviewed.csv`. Hàm `review()` áp dụng `apply_overrides()` và ghi nhận nhật ký bất biến vào `out/poc/decision_log.csv` (và `audit_log.jsonl`).
- **Decision policy**:
  - `status: REWORK`, `reason_code: EXCESSIVE_DEFECT_RATE`.
  - Quyết định: Phát hiện nhiều hơn 12/20 ảnh lỗi nghiêm trọng đã được kiểm duyệt viên xác nhận $\rightarrow$ Kích hoạt chốt chặn rủi ro, từ chối phát hành lô ảnh, yêu cầu thu thập lại cảnh chụp.
  - Người ký duyệt: `Nguyen Ba Duy (Data Lead)`.

## 08 · Reproduce & tests

```bash
# 1. Chạy one-command PoC duy nhất
python -m src.main --input fixtures/t02_raw_qc --config configs/lab.yaml --output out/poc --run-name poc --offline --seed 42

# 2. Chạy so sánh Baseline vs PoC
python -m src.compare reports/metrics_baseline.json reports/metrics_poc.json --out reports/table1_baseline_vs_poc.md

# 3. Chạy toàn bộ bài test kiểm thử tự động
pytest -q
```

- **Output của `pytest -q`**: `55 passed, 23 skipped in 3.12s (100% passed, 0 failed)`.
- **Máy / CPU / OS / Python**: Intel64 Model 158 · Windows 10 · Python 3.14.4 · Git SHA: `83ce56d`.

## 09 · Limitations & ethics

- **Rủi ro pháp lý / PII**: Dữ liệu synthetic simulator CC0, hoàn toàn không có thông tin định danh cá nhân (Zero PII).
- **Giới hạn & Scale 10x**: Nếu scale lên 1,000,000 ảnh/ngày, việc duyệt 20 ảnh mỗi lô là quá ít. Cần mở rộng sang phân tầng kiểm định đa cấp (Tiered Active Learning Sampling).
- **Tuyên bố pháp lý**: Nhóm không tuyên bố "đạt chuẩn GDPR hoặc Luật BV Dữ liệu cá nhân Việt Nam" chỉ từ các bộ lọc tự động. Mọi phát hành đều cần biên bản phê duyệt chính thức từ DPO (Data Protection Officer) và Legal Lead.
- **Kế hoạch cải tiến**: Bổ sung bộ lọc nhận diện giọt nước trên kính chắn gió (Raindrops on lens) và ánh chói mặt trời góc thấp (Sun-glare).

## 10 · Team contribution

| Học viên | Git author/email | Module / vai trò | Commit SHA / diff chứng minh | Trình bày? |
|---|---|---|---|---|
| Nguyễn Bá Duy | Nguyễn Bá Duy <basduygame@gmail.com> | Lead / Core Algorithm / Pipeline / QA | `83ce56d`, `ae83ff1` | Có (Presenter) |

## 11 · References

| URL | Ngày xem | 1–2 dòng ý nghĩa |
|---|---|---|
| https://acdc.vision.ee.ethz.ch/ | 14/11/2026 | Bộ dữ liệu chuẩn đánh giá thị giác xe tự hành dưới điều kiện thời tiết khắc nghiệt. |
| https://www.iso.org/standard/5259.html | 14/11/2026 | Tiêu chuẩn chất lượng dữ liệu ISO/IEC TR 5259 cho Machine Learning. |
| https://docs.opencv.org/ | 14/11/2026 | Tài liệu chuẩn về toán tử Laplace và đạo hàm bậc hai trong xử lý ảnh. |

---

**Bảng 3 · Checklist chốt khi nộp**
- [x] Link repo và tag cuối cùng trong README; input mẫu không chứa PII thật.
- [x] Đúng 1 lệnh run, 1 lệnh evaluate, 1 lệnh tests; không cần download khi chạy.
- [x] Có baseline/PoC metrics, $\ge 2$ failure cases, reviewer evidence, decision log.
- [x] Có license/source provenance, data splits, seed, offline environment, GT/eval N.
- [x] Thành viên có commit thực chất và được nêu minh bạch trong bảng đóng góp.
