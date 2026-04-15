# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Group 9  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Nguyễn Thị Diệu Linh | Ingestion / Raw Owner (Sprint 1) | alicinameo@gmail.com |
| Nguyễn Thùy Linh | Cleaning & Quality Owner (Sprint 2) | ntlinh@gmail.com |
| Nguyễn Hoàng Khải Minh | Embed & Idempotency Owner (Sprint 3) | 26ai.minhnhk@vinuni.edu.vn |
| Nguyễn Triệu Gia Khánh | Monitoring / Docs Owner (Sprint 4) | 26ai.khanhntg@vinuni.edu.vn |
| Nguyễn Hoàng Duy | Monitoring / Docs Support (Sprint 4) | 26ai.duynh@vinuni.eduvn |

**Ngày nộp:** 15/04/2026  
**Repo:** `C:/Users/giakh/Project/Lab10_Group9_E402`  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

Pipeline của nhóm chạy theo chuỗi ingest -> clean -> validate -> embed -> publish manifest. Nguồn raw chính là file CSV export bẩn `data/raw/policy_export_dirty.csv`, chứa các lỗi mô phỏng đúng narrative Day 10 (duplicate, sai date format, stale policy, unknown doc_id).  

Trong run chuẩn `run_id=2026-04-15T09-16Z` (`artifacts/manifests/manifest_2026-04-15T09-16Z.json`), pipeline ghi nhận `raw_records=10`, `cleaned_records=6`, `quarantine_records=4`. Dữ liệu sau clean được xuất ra `artifacts/cleaned/cleaned_2026-04-15T09-16Z.csv`; các record lỗi đi vào `artifacts/quarantine/quarantine_2026-04-15T09-16Z.csv`.  

Sau validate, bước embed ghi snapshot vào Chroma collection `day10_kb` theo cơ chế upsert `chunk_id` và prune id thừa để tránh stale chunk. Cuối run, manifest được ghi vào `artifacts/manifests/` kèm `latest_exported_at`, `run_timestamp`, đường dẫn cleaned CSV, và cờ inject (`no_refund_fix`, `skipped_validate`) để phục vụ observability.

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

`python etl_pipeline.py run ; python eval_retrieval.py --out artifacts/eval/before_after_eval.csv`

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| R6 refund_window_fix_14_to_7 (baseline quan trọng) | Chunk stale bị giữ nguyên 14 ngày | Chunk được chuẩn hóa về 7 ngày + marker cleaned | `artifacts/cleaned/cleaned_inject-bad.csv` vs `artifacts/cleaned/cleaned_2026-04-15T09-16Z.csv` |
| E3 refund_no_stale_14d_window (halt) | Có khả năng FAIL nếu còn 14 ngày trong cleaned | Run chuẩn pass; inject phải bật `--skip-validate` mới cho embed tiếp | `manifest_inject-bad.json` có `skipped_validate=true`; cleaned inject có câu 14 ngày |
| E7 no_bom_in_cleaned_chunks (halt) | Không đảm bảo nếu pipeline bỏ qua rule R7 | Run chuẩn pass, `bom_violations=0` (không có BOM trong cleaned) | `cleaned_2026-04-15T09-16Z.csv` không có ký tự BOM/zero-width |
| E8 no_doc_id_dominance (warn) | Mất cân bằng nếu 1 doc chiếm >80% | Run chuẩn pass, max ratio = 2/6 ~ 0.33 | Tính từ `cleaned_2026-04-15T09-16Z.csv` (policy_refund_v4 = 2 bản ghi) |
| Retrieval guard (`hits_forbidden`) | Trước fix/inject: có nguy cơ chunk stale lọt top-k | Sau run chuẩn: `hits_forbidden=no` cho `q_refund_window` | `artifacts/eval/after_inject_bad.csv` dòng `q_refund_window` = yes vs `before_after_eval.csv` = no |

**Rule chính (baseline + mở rộng):**

- Baseline: allowlist `doc_id`, normalize `effective_date`, quarantine stale HR policy (< 2026-01-01), bỏ record rỗng, dedupe theo normalized text, fix refund 14 -> 7.
- Rule mở rộng của nhóm: phát hiện BOM/zero-width (`bom_or_invisible_chars`), kiểm tra SLA phút vượt ngưỡng (`sla_value_out_of_range`), loại chunk quá ngắn (`too_few_words`).
- Expectation mở rộng: `no_bom_in_cleaned_chunks` (halt), `no_doc_id_dominance` (warn).

**Ví dụ 1 lần expectation fail (nếu có) và cách xử lý:**

Nhóm chủ động tạo run lỗi `run_id=inject-bad` bằng lệnh `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`. Khi tắt refund fix, cleaned data chứa lại câu "14 ngày làm việc", khiến expectation `refund_no_stale_14d_window` thuộc loại halt không còn đạt. Để phục vụ Sprint 3 before/after, nhóm dùng `--skip-validate` để vẫn embed dữ liệu xấu và quan sát suy giảm retrieval. Sau đó nhóm rerun luồng chuẩn không cờ inject để khôi phục trạng thái sạch.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

Kịch bản inject của nhóm tập trung vào policy hoàn tiền: giữ nguyên chunk stale "14 ngày làm việc" bằng cách chạy:

`python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`

Sau đó nhóm chạy:

`python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv`

Mục tiêu của kịch bản này là chứng minh một điểm observability quan trọng: câu trả lời top-1 có thể vẫn nhìn "đúng" nhưng trong top-k context vẫn tồn tại chunk bị cấm (stale). Vì vậy metric `hits_forbidden` được ưu tiên theo dõi thay vì chỉ nhìn `top1_doc_id`.

**Kết quả định lượng (từ CSV / bảng):**

So sánh hai file eval cho thấy khác biệt rõ ở câu `q_refund_window`:

- `artifacts/eval/after_inject_bad.csv`: `contains_expected=yes` nhưng `hits_forbidden=yes`.
- `artifacts/eval/before_after_eval.csv` (sau khi chạy chuẩn): `contains_expected=yes` và `hits_forbidden=no`.

Các câu còn lại (`q_p1_sla`, `q_lockout`, `q_leave_version`) ổn định với `contains_expected=yes`; riêng `q_leave_version` vẫn đạt `top1_doc_expected=yes`.  

Từ đó nhóm kết luận: inject run làm tăng rủi ro "context contamination" cho retrieval dù top-1 chưa sai hoàn toàn. Run chuẩn đã xóa dấu hiệu stale trong top-k và phù hợp mục tiêu Day 10 là kiểm soát chất lượng dữ liệu trước khi agent truy vấn.

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

Nhóm dùng SLA mặc định 24 giờ (`FRESHNESS_SLA_HOURS=24`) và đo freshness từ trường `latest_exported_at` trong manifest.  

Với manifest `manifest_2026-04-15T09-16Z.json`, timestamp mới nhất là `2026-04-10T08:00:00`; command `python etl_pipeline.py freshness --manifest ...` trả về một trong ba trạng thái:

- `PASS`: `age_hours <= sla_hours`.
- `WARN`: manifest có nhưng timestamp thiếu/không parse được.
- `FAIL`: quá SLA (`freshness_sla_exceeded`).

Ngoài ra, nếu đường dẫn manifest sai/không tồn tại thì command trả lỗi `manifest not found` và exit code 1 (không phải PASS/WARN/FAIL). Nhóm đã phản ánh hành vi này vào runbook để tránh hiểu sai khi tích hợp CI.

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

Day 09 phụ thuộc trực tiếp vào chất lượng corpus truy vấn. Pipeline Day 10 đóng vai trò publish boundary cho dữ liệu: chỉ cleaned data hợp lệ mới được embed vào collection `day10_kb`. Nhờ cơ chế upsert + prune theo `chunk_id`, các chunk stale từ run cũ không còn tồn tại trong index, giúp agent Day 09 đọc đúng version policy và giảm nguy cơ hallucination do context lỗi thời.

---

## 6. Rủi ro còn lại & việc chưa làm

- Chưa có log file run trong `artifacts/logs/` để audit expectation theo từng lần chạy; cần bổ sung artifact này trước deadline chính thức.
- Chưa tạo inject scenario riêng cho BOM và SLA out-of-range để chứng minh đầy đủ metric_impact của R7/R8.
- Chưa cấu hình CI tự động chạy freshness check sau mỗi lần publish.
- Chưa chuẩn hóa email/domain của tất cả thành viên trong report theo một format thống nhất của lớp.
