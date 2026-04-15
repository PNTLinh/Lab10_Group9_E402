# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Triệu Gia Khánh
**Vai trò:** Monitoring / Docs Owner (Sprint 4)
**Ngày nộp:** 15/04/2026
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `docs/pipeline_architecture.md`
- `docs/data_contract.md`
- `docs/runbook.md`
- `monitoring/freshness_check.py` (kiểm tra hành vi để viết runbook đúng implementation)
- `artifacts/manifests/*.json` và `artifacts/eval/*.csv` (lấy evidence thật cho báo cáo)

**Kết nối với thành viên khác:**

Tôi nhận đầu vào từ các bạn phụ trách Sprint 1-3 (ingestion, cleaning/quality, embed) rồi tổng hợp thành tài liệu vận hành cuối cùng. Cụ thể, tôi đối chiếu kết quả chạy pipeline với cleaned/quarantine/eval artifacts để đảm bảo tài liệu không mô tả chung chung mà bám sát dữ liệu thật của nhóm. Tôi cũng phối hợp với thành viên Sprint 4 còn lại để rà soát runbook theo ngữ cảnh Windows PowerShell, tránh các lệnh Linux-style gây lỗi khi demo.

**Bằng chứng (commit / comment trong code):**

- Run chuẩn: `artifacts/manifests/manifest_2026-04-15T09-16Z.json` (`raw_records=10`, `cleaned_records=6`, `quarantine_records=4`).
- Run inject: `artifacts/manifests/manifest_inject-bad.json` (`no_refund_fix=true`, `skipped_validate=true`).
- Chứng cứ before/after retrieval: `artifacts/eval/after_inject_bad.csv`, `artifacts/eval/before_after_eval.csv`.
- Tài liệu đã hoàn thiện: `docs/pipeline_architecture.md`, `docs/data_contract.md`, `docs/runbook.md`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

> VD: chọn halt vs warn, chiến lược idempotency, cách đo freshness, format quarantine.

Quyết định kỹ thuật quan trọng tôi thống nhất trong phần monitoring/docs là tách rõ ba nhóm trạng thái khi kiểm tra freshness: PASS/WARN/FAIL ở mức dữ liệu, và command error khi thiếu file manifest. Ban đầu runbook gộp thiếu manifest vào FAIL, nhưng khi đọc `etl_pipeline.py` và `monitoring/freshness_check.py`, tôi thấy thiếu manifest thực tế trả lỗi `manifest not found` và exit code 1 ngay từ CLI, không đi qua nhánh PASS/WARN/FAIL của hàm check.

Tách bạch hai nhóm này giúp đội vận hành debug nhanh hơn: nếu FAIL thì tập trung vào độ trễ dữ liệu (`age_hours > sla_hours`), còn nếu missing manifest thì kiểm tra path hoặc rerun pipeline để tái tạo artifact. Quyết định này làm runbook sát implementation, tránh hiểu sai khi tích hợp kiểm tra tự động trong CI.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

> Mô tả triệu chứng → metric/check nào phát hiện → fix.

Anomaly tôi xử lý nằm ở tài liệu vận hành: trong runbook cũ có hướng dẫn kiểm tra quarantine reason `stale_refund_14d` và dùng lệnh recovery `$(date ...)`. Hai điểm này làm đội vận hành dễ thao tác sai vì code hiện tại không có reason đó, và môi trường nhóm dùng PowerShell không chạy được cú pháp shell Linux.

Tôi phát hiện vấn đề bằng cách đối chiếu trực tiếp `artifacts/quarantine/quarantine_2026-04-15T09-16Z.csv` và `quarantine_inject-bad.csv` (reason thật gồm `duplicate_chunk_text`, `invalid_effective_date_format`, `stale_hr_policy_effective_date`, `unknown_doc_id`) cùng với thông tin môi trường chạy của nhóm.

Fix của tôi là cập nhật runbook theo reason thật, đổi ví dụ env var sang PowerShell (`$env:FRESHNESS_SLA_HOURS=48; ...`) và sửa command recovery thành `run-id` tĩnh hợp lệ.

---

## 4. Bằng chứng trước / sau (80–120 từ)

> Dán ngắn 2 dòng từ `before_after_eval.csv` hoặc tương đương; ghi rõ `run_id`.

Tôi dùng cặp run `inject-bad` và `2026-04-15T09-16Z` để chứng minh chất lượng retrieval trước/sau khi chạy luồng chuẩn:

- `run_id=inject-bad` (`artifacts/eval/after_inject_bad.csv`):  
  `q_refund_window,...,contains_expected=yes,hits_forbidden=yes,...`
- `run_id=2026-04-15T09-16Z` (`artifacts/eval/before_after_eval.csv`):  
  `q_refund_window,...,contains_expected=yes,hits_forbidden=no,...`

Điểm quan trọng là top-1 có thể vẫn "đúng nhìn bề ngoài", nhưng metric `hits_forbidden` cho thấy top-k vẫn bị nhiễm chunk stale ở run inject. Sau khi rerun chuẩn, dấu hiệu nhiễm này biến mất.

---

## 5. Cải tiến tiếp theo (40–80 từ)

> Nếu có thêm 2 giờ — một việc cụ thể (không chung chung).

Nếu có thêm 2 giờ, tôi sẽ thêm một script sinh `artifacts/logs/run_<run_id>.log` bắt buộc cho mọi run và cập nhật report tự động từ manifest/eval/log. Cách này giúp phần báo cáo nhóm không phải điền thủ công, giảm sai lệch số liệu giữa tài liệu và artifact, đồng thời đáp ứng yêu cầu audit rõ ràng khi giảng viên quick-check.
