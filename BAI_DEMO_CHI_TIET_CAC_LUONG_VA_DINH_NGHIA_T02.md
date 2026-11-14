# BÀI DEMO CHI TIẾT CÁC LUỒNG HỆ THỐNG & TỔNG QUAN ĐỊNH NGHĨA
## Track T02 · Raw QC Triage (Field-to-Release PoC)
**Tác giả:** Nguyễn Bá Duy (Data Lead) — Nhóm G02

---

## PHẦN 1: BẢNG TRA CỨU ĐỊNH NGHĨA & THUẬT NGỮ CỐT LÕI (GLOSSARY)

| Thuật ngữ | Định nghĩa kỹ thuật | Ý nghĩa trong bài toán T02 |
|---|---|---|
| **Raw QC Triage** | Quy trình sàng lọc và phân loại sơ bộ chất lượng dữ liệu thô ở tầng cửa ngõ (gatekeeper) trước khi đưa vào gán nhãn hoặc huấn luyện. | Phân loại 96 ảnh camera hành trình, chọn ra 20 ảnh nghi ngờ lỗi nhất đưa vào hàng đợi kiểm duyệt. |
| **Data Provenance** | Hồ sơ ghi lại nguồn gốc, xuất xứ, bản quyền và tính toàn vẹn (mã băm sha256) của dữ liệu qua từng bước xử lý. | Đảm bảo ảnh đến từ nguồn giả lập CC0 hợp pháp, không bị sửa đổi trái phép bằng cách đối chiếu với `manifest.csv`. |
| **Offline Guard** | Chốt chặn an toàn phần mềm ngắt toàn bộ socket và kết nối mạng ra ngoài Internet trong quá trình thực thi. | Ngăn rò rỉ dữ liệu nhạy cảm ra ngoài và đảm bảo hệ thống tự lực cánh sinh, không phụ thuộc vào cloud API. |
| **Ground Truth (GT) Guard** | Cơ chế phần mềm chặn tuyệt đối pipeline của học viên đọc dữ liệu nhãn ẩn trong `fixtures/*/gt/`. | Chống gian lận (Data Snooping), buộc thuật toán phải hoạt động dựa trên đặc trưng ảnh thật sự chứ không học vẹt nhãn. |
| **Laplacian Variance** | Phương sai của ảnh sau khi nhân chập với toán tử vi phân đạo hàm bậc hai Laplace $\Delta I$. | Độ đo độ sắc nét khách quan: ảnh nét có viền cạnh rõ $\rightarrow$ phương sai cao; ảnh mờ nhòe $\rightarrow$ phương sai tiệm cận 0. |
| **Central ROI** | Vùng quan tâm trung tâm (Region of Interest) chiếm $50\%$ diện tích chính giữa khung hình. | Tập trung kiểm tra nơi xe cộ, làn đường và biển số xuất hiện, bỏ qua hiện tượng mờ nhẹ ở 4 góc rìa ống kính góc rộng. |
| **Highlight Clipping (Glare)** | Hiện tượng điểm ảnh bị bão hòa ánh sáng vượt ngưỡng cực đại ($> 245$ trên thang 255), mất hoàn toàn chi tiết kết cấu. | Phát hiện vệt đèn pha xe đối diện rọi thẳng làm cháy trắng biển số xe. |
| **JPEG Blockiness** | Bước nhảy gradient nhân tạo xuất hiện trên ranh giới các khối $8 \times 8$ pixel do thuật toán nén JPEG gây ra. | Đo lường mức độ vỡ hình do nén ảnh quá mức hoặc truyền tải mạng băng thông thấp. |
| **Adaptive Z-Score Conditioning** | Phép chuẩn hóa độ lệch chuẩn có điều kiện: $Z = \frac{X - \mu_{(c,l)}}{\sigma_{(c,l)}}$ theo từng cặp camera và ánh sáng. | Giúp đánh giá công bằng: ảnh chỉ bị xem là lỗi khi nó bất thường so với chính các ảnh chụp cùng camera và cùng điều kiện đó. |
| **Non-compensatory Aggregation** | Hàm tổng hợp rủi ro phi bù trừ sử dụng toán tử $\max$: $\text{Score} = \max(Z_k)$. | Nguyên lý an toàn tối cao: một lỗi nghiêm trọng (cháy lóa) sẽ làm hỏng ảnh, không một đặc trưng tốt nào khác (ảnh nét) có thể bù đắp được. |
| **Human-in-the-Loop (HITL)** | Cơ chế tích hợp chuyên gia con người vào vòng lặp ra quyết định của AI tại các điểm rủi ro cao. | Con người mở `contact_sheet.html`, thẩm định 20 ảnh nghi ngờ, duyệt (`approve`) lỗi thật và bác bỏ (`reject`) báo động giả. |
| **Audit Log (Append-only)** | Nhật ký kiểm toán bất biến chỉ cho phép ghi nối tiếp (JSONL), ghi lại ai đã sửa gì, vào lúc nào, với lý do gì. | Đáp ứng yêu cầu giải trình pháp lý và tiêu chuẩn kiểm định MLOps công nghiệp. |
| **Quyết định GO / HOLD / REWORK** | Ba trạng thái phát hành dữ liệu cấp hệ thống: **GO** (đủ chuẩn xuất xưởng), **HOLD** (tạm giữ chờ thẩm định), **REWORK** (từ chối lô, yêu cầu thu thập lại). | Đảm bảo tính tự chủ có kiểm soát của hệ thống dữ liệu tự động. |

---

## PHẦN 2: BÀI DEMO CHI TIẾT 8 LUỒNG HOẠT ĐỘNG (SYSTEM STREAMS WALKTHROUGH)

```
[LUỒNG 1: LOAD] ──> [LUỒNG 2: PROCESS] ──> [LUỒNG 3: CONDITIONING] ──> [LUỒNG 4: RANK]
      │                     │                          │                       │
 Kiểm tra Hash          Trích xuất 4            Chuẩn hóa Z-score        Top-20 Queue &
 Manifest.csv             đặc trưng              thích ứng (cam, light)  Contact Sheet HTML
                                                                               │
[LUỒNG 8: GIT]  <── [LUỒNG 7: EVAL]  <── [LUỒNG 6: DECIDE]   <── [LUỒNG 5: REVIEW]
      │                     │                          │                       │
 Commit Tag            So sánh Table 1         Chốt chặn an toàn        Human Duyệt &
 demo-180m & 24h        Baseline vs PoC         GO / HOLD / REWORK       Audit Log JSONL
```

---

### LUỒNG 1: KIỂM SOÁT NGUỒN GỐC & TÍNH TOÀN VẸN DỮ LIỆU (DATA PROVENANCE STREAM)
* **Vị trí code**: Hàm `load(ctx)` trong [src/pipeline.py](file:///C:/Users/basduy05/Downloads/VINAI/lab/lab-day6/K5-Day6-L2A-NguyenBaDuy-2A202603192-DataGovernanceAndPrivacy/src/pipeline.py).
* **Cơ chế hoạt động**:
  1. Pipeline đọc file `manifest.csv` chứa danh sách 96 ảnh kèm mã băm SHA-256 đã đăng ký.
  2. Hàm `verify_manifest()` băm lại từng file ảnh trên đĩa và so khớp. Nếu có file bị chỉnh sửa, mã hash sẽ sai lệch và kích hoạt báo động.
  3. Sau khi xác thực, hàm đọc bảng metadata `images.csv` gồm 96 dòng.
* **LÝ DO LÀM NHƯ VẬY**:
  - *Tại sao không đọc ảnh trực tiếp mà phải qua Manifest?* Trong môi trường sản xuất, dữ liệu có thể bị tấn công đầu độc (Data Poisoning Attack) hoặc lỗi đường truyền làm file bị méo mó. Kiểm tra mã băm SHA-256 là tiêu chuẩn số 1 về liêm chính dữ liệu (Data Integrity).

---

### LUỒNG 2: TRÍCH XUẤT ĐẶC TRƯNG TÍN HIỆU QUANG HỌC (FEATURE EXTRACTION STREAM)
* **Vị trí code**: Hàm `process(ctx, data)` - Vòng lặp trích xuất ban đầu.
* **Cơ chế hoạt động**:
  Với mỗi bức ảnh, chuyển về thang xám $I_{gray}$ và tính 4 tín hiệu trực giao:
  1. **Độ sắc nét**: Nhân chập kernel Laplace $\begin{bmatrix} 0 & 1 & 0 \\ 1 & -4 & 1 \\ 0 & 1 & 0 \end{bmatrix}$ tính phương sai $\text{Var}(L)$ toàn cảnh và cắt vùng tâm $\text{ROI}$ ($50\%$ diện tích giữa).
  2. **Độ tối**: Tính tỷ lệ pixel $< 30$ qua hàm chỉ thị $\frac{1}{HW}\sum \mathbb{I}(I < 30)$.
  3. **Độ lóa**: Tính tỷ lệ pixel bão hòa $> 245$ và lấy mức sáng tại phân vị 95th ($P_{95}$).
  4. **Độ vỡ nén JPEG**: Tính tỷ số bước nhảy gradient giữa cột biên $8k$ và cột bên trong $8k-1$.
* **LÝ DO LÀM NHƯ VẬY**:
  - *Tại sao không dùng 1 mạng Deep Learning CNN/ViT?* Deep Learning là hộp đen (black-box), chạy chậm ($>50\text{ms}$), cần GPU và dễ vi phạm Offline Guard khi tải weights. Bốn chỉ số tín hiệu trên chạy thuần túy đại số tuyến tính trên CPU chỉ mất **$5.8\text{ms/ảnh}$**, cực kỳ tường minh và có thể giải thích trực tiếp cho kỹ sư phần cứng nguyên nhân vì sao hỏng.

---

### LUỒNG 3: CHUẨN HÓA THỐNG KÊ THÍCH ỨNG THEO ĐIỀU KIỆN (ADAPTIVE CONDITIONING STREAM)
* **Vị trí code**: Hàm `process(ctx, data)` - Khối chuẩn hóa Bayesian/Z-Score.
* **Cơ chế hoạt động**:
  1. Gom nhóm 56 ảnh trên tập `dev` theo 6 phân hoạch: $(\text{cam\_A}, \text{day}), (\text{cam\_A}, \text{night}), (\text{cam\_B}, \text{day})\dots$
  2. Tính $\mu$ và $\sigma$ của từng đặc trưng trong từng nhóm.
  3. Tính điểm lệch chuẩn $Z$-score cho từng ảnh.
  4. **Luật điều chỉnh đặc thù ban đêm**: Nếu `light == 'night'`, hệ thống giảm $50\%$ phạt tối ($Z_{dark} \times 0.5$) và tăng $30\%$ phạt lóa ($Z_{glare} \times 1.3$).
  5. Tính điểm rủi ro tổng hợp bằng toán tử phi bù trừ: $\text{Score} = \max(Z_{blur}, Z_{glare}, Z_{dark}, Z_{comp})$.
* **LÝ DO LÀM NHƯ VẬY**:
  - *Tại sao không dùng một ngưỡng cắt cố định (Hard threshold)?* Vì điều kiện thực tế luôn biến động: Camera B có ống kính mềm hơn Camera A; ban đêm trời tối tự nhiên nên phương sai Laplace vốn dĩ đã thấp. Dùng ngưỡng cố định sẽ xóa nhầm toàn bộ ảnh đêm sạch (False Alarm). Chuẩn hóa Z-score thích nghi giúp ảnh ban đêm được đánh giá công bằng so với chuẩn mực ban đêm.
  - *Tại sao dùng hàm Max mà không dùng Trung bình cộng?* Một bức ảnh bị đèn pha rọi cháy trắng biển số thì dù vùng nền có sắc nét đến đâu vẫn là ảnh phế phẩm. Hàm $\max$ đảm bảo không một đặc trưng tốt nào được phép bù đắp che giấu đi một lỗi nguy hiểm.

---

### LUỒNG 4: LẬP HÀNG ĐỢI ƯU TIÊN & GIAO DIỆN HTML OFFLINE (RANKING & VISUAL CONTACT SHEET STREAM)
* **Vị trí code**: Hàm `rank(ctx, scored)` trong `src/pipeline.py`.
* **Cơ chế hoạt động**:
  1. Hàm `make_review_queue()` sắp xếp 96 ảnh theo `Score` giảm dần (thuật toán mergesort ổn định).
  2. Cắt lấy đúng **Top $B=20$ ảnh** có nguy cơ cao nhất ghi vào `out/poc/review_queue.csv`.
  3. Hàm `render_contact_sheet()` nhúng ảnh dưới dạng thẻ HTML cục bộ, tạo ra file `out/poc/contact_sheet.html`.
* **LÝ DO LÀM NHƯ VẬY**:
  - *Tại sao phải sinh Contact Sheet HTML?* Con người không thể thẩm định trực quan thông qua việc đọc các con số khô khan trong file CSV. Giao diện HTML offline giúp kiểm duyệt viên mở lên trong 1 giây bằng trình duyệt, xem ngay ảnh trước/sau và thao tác chọn duyệt bằng dropdown tiện lợi.

---

### LUỒNG 5: VÒNG THẨM ĐỊNH CON NGƯỜI & NHẬT KÝ KIỂM TOÁN (HUMAN-IN-THE-LOOP & AUDIT STREAM)
* **Vị trí code**: Hàm `review(ctx, scored, queue)` trong `src/pipeline.py`.
* **Cơ chế hoạt động**:
  1. Kiểm duyệt viên (**Nguyễn Bá Duy**) mở `contact_sheet.html`, nhập tên và thẩm định:
     - Duyệt `approve` cho các ảnh lỗi thật: ví dụ `img_17_2` (cháy lóa đèn pha $Z=6.47$), `img_23_2` (vỡ hình $Z=3.62$).
     - Bác bỏ `reject` cho ảnh bị máy báo động nhầm: ví dụ `img_08_3` (ảnh chụp đêm tối tự nhiên nhưng vật thể vẫn nét).
  2. Nhấn nút **Export CSV** tải file `review_queue_reviewed.csv` và đặt vào thư mục `out/poc/`.
  3. Khi chạy lại pipeline, hàm `apply_overrides()` đọc các thay đổi, cập nhật nhãn `pred_action` và ghi nhận lịch sử vào `audit_log.jsonl` (và `decision_log.csv`).
* **LÝ DO LÀM NHƯ VẬY**:
  - *Tại sao phải có quyền `reject`?* Để con người bắt lỗi báo động giả của máy, cứu lại các mẫu huấn luyện ban đêm quý giá, không để AI tự ý loại bỏ gây mất cân bằng phân bố dữ liệu.
  - *Tại sao cần Audit Log append-only?* Để phục vụ truy vết trách nhiệm: nếu sau này mô hình AI gặp sự cố, kiểm toán viên có thể mở file log ra xem chính xác ai là người đã phê duyệt bức ảnh đó vào ngày giờ nào.

---

### LUỒNG 6: CHỐT CHẶN QUẢN TRỊ PHÁT HÀNH DỮ LIỆU (GO / HOLD / REWORK DECISION STREAM)
* **Vị trí code**: Hàm `decide(ctx, final)` trong `src/pipeline.py`.
* **Cơ chế hoạt động**:
  Đưa ra quyết định cuối cùng cấp hệ thống dựa trên 3 nấc an toàn:
  1. **Nấc 1**: Nếu chưa có ai review ($n\_reviewed == 0$) $\rightarrow$ Trả về **`HOLD`** (`AWAITING_HUMAN_REVIEW`).
  2. **Nấc 2**: Nếu số lượng ảnh lỗi nghiêm trọng trong top 20 đạt $\ge 12$ ảnh ($60\%$) $\rightarrow$ Trả về **`REWORK`** (`EXCESSIVE_DEFECT_RATE`).
  3. **Nấc 3**: Nếu tỷ lệ lỗi thấp và các mẫu rủi ro đã được xử lý $\rightarrow$ Trả về **`GO`** (`QUALITY_ASSURED`).
  Ghi nhận quyết định vào `decision.json` kèm chữ ký `owner: Nguyen Ba Duy (Data Lead)`.
* **LÝ DO LÀM NHƯ VẬY**:
  - *Tại sao ra quyết định REWORK lại là thành công?* Nếu một lô dữ liệu có tới hơn 60% ảnh bị lóa đèn và vỡ hình, việc cố ép ra quyết định `GO` là vô trách nhiệm. Quyết định `REWORK` chứng minh cơ chế chốt chặn rủi ro hoạt động chuẩn xác: dũng cảm từ chối dữ liệu bẩn và yêu cầu đội xe đi thu thập lại cảnh chụp.

---

### LUỒNG 7: ĐO LƯỜNG ĐÁNH GIÁ & SO SÁNH ĐỐI ĐẦU (EVALUATION & BENCHMARK STREAM)
* **Vị trí code**: Script `src.compare` và file cấu hình `reports/metric_contract.md`.
* **Cơ chế hoạt động**:
  1. Chạy so sánh giữa Baseline ngẫu nhiên và PoC trên cùng tập eval 40 ảnh:
     `python -m src.compare reports/metrics_baseline.json reports/metrics_poc.json --out reports/table1_baseline_vs_poc.md`
  2. Kết quả đối chiếu trên Bảng 1:
     - **Defect Recall@20**: Tăng vọt từ $50\%$ lên **$90\%$** (+80% relative improvement).
     - **False Alarm ban đêm**: Giảm ngoạn mục từ $70\%$ xuống **$10\%$** (-85.7% relative reduction).
     - **Thời gian chạy**: Chỉ mất $0.58\text{s}$ cho 100 ảnh.
* **LÝ DO LÀM NHƯ VẬY**:
  - *Tại sao phải so sánh công bằng cùng seed 42 và cùng budget?* Trong nghiên cứu khoa học, một phương pháp chỉ được công nhận là tiến bộ khi nó đánh bại baseline trên cùng một sân chơi bình đẳng.

---

### LUỒNG 8: BẢO ĐẢM TIN CẬY & ĐÓNG GÓI NỘP BÀI (RELIABILITY & GIT RELEASE STREAM)
* **Vị trí code**: Bộ test `tests/test_team_02.py`, `tests/test_cli.py` và Git Tags.
* **Cơ chế hoạt động**:
  1. Kiểm thử tự động bằng lệnh `pytest -q`: Vượt qua toàn bộ bài test với kết quả **`0 failed, 100% passed`**.
  2. Gắn tag **`demo-180m`** tại commit `83ce56d` trước phút 180 (khóa trọn vẹn **+5 điểm thưởng Bonus**).
  3. Hoàn thiện báo cáo [reports/group_report.md](file:///C:/Users/basduy05/Downloads/VINAI/lab/lab-day6/K5-Day6-L2A-NguyenBaDuy-2A202603192-DataGovernanceAndPrivacy/reports/group_report.md), phân công [reports/team_contributions.csv](file:///C:/Users/basduy05/Downloads/VINAI/lab/lab-day6/K5-Day6-L2A-NguyenBaDuy-2A202603192-DataGovernanceAndPrivacy/reports/team_contributions.csv) và gắn tag nộp bài chính thức **`final-24h`**.
  4. Đẩy (push) toàn bộ nhánh `main` và 2 tags lên GitHub Remote.
* **LÝ DO LÀM NHƯ VẬY**:
  - *Tại sao phải viết cả test kịch bản bình thường lẫn kịch bản biên?* Đảm bảo pipeline không bao giờ bị crash âm thầm khi gặp lô dữ liệu nhỏ hoặc bất thường.

---

## PHẦN 3: TỔNG KẾT BÀI HỌC KỸ TRỊ DỮ LIỆU (KEY TAKEAWAYS)

Qua toàn bộ bài làm Track T02, bạn đã chứng minh được 3 chân lý quan trọng trong kỹ thuật dữ liệu hiện đại:
1. **Thuật toán thông minh hơn mô hình cồng kềnh**: Bằng việc kết hợp xử lý tín hiệu cổ điển với chuẩn hóa thống kê thích nghi, ta đạt độ chính xác $90\%$ mà chỉ tốn $0.56$ giây trên CPU, tiết kiệm chi phí hơn hàng trăm lần so với việc chạy GPU cồng kềnh.
2. **AI cần con người làm trọng tài**: AI đề xuất cảnh báo rủi ro, nhưng con người giữ quyền phủ quyết để cứu lại dữ liệu tốt và loại bỏ dữ liệu xấu.
3. **Quản trị dữ liệu là trách nhiệm có chữ ký**: Mọi quyết định xuất xưởng hay loại bỏ dữ liệu đều được lưu vết pháp lý bất biến, đảm bảo sự an toàn tuyệt đối cho các hệ thống AI ngoài đời thực.
