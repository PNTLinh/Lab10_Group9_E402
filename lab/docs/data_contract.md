# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn                  | Phương thức ingest | Failure mode chính                                      | Metric / alert                      |
| ---------------------- | ------------------ | ------------------------------------------------------- | ----------------------------------- |
| policy_refund_v4       | Batch CSV export (`data/raw`) | Cửa sổ hoàn tiền stale 14 ngày, duplicate text | `expectation[refund_no_stale_14d_window]`, `quarantine_reason[duplicate_chunk_text]` |
| sla_p1_2026            | Batch CSV export (`data/raw`) | Giá trị SLA phút bất thường (>120), thiếu field | `quarantine_reason[sla_value_out_of_range]`, `% missing fields` |
| it_helpdesk_faq        | Batch CSV export (`data/raw`) | Ký tự BOM/zero-width, ngày không chuẩn | `quarantine_reason[bom_or_invisible_chars]`, `% invalid date` |
| hr_leave_policy        | Batch CSV export (`data/raw`) | Bản policy cũ (`effective_date < 2026-01-01`) | `quarantine_reason[stale_hr_policy_effective_date]` |


---

## 2. Schema cleaned

| Cột            | Kiểu                | Bắt buộc | Ghi chú             |
| -------------- | ------------------- | -------- | ------------------- |
| chunk_id       | string              | Có       | Sinh ổn định từ `doc_id|chunk_text|seq`; dùng làm id upsert |
| doc_id         | string              | Có       | Phải thuộc allowlist contract (`policy_refund_v4`, `sla_p1_2026`, `it_helpdesk_faq`, `hr_leave_policy`) |
| chunk_text     | string              | Có       | Min length theo contract (>= 8), không BOM/zero-width, không quá ngắn (rule < 5 từ sẽ quarantine) |
| effective_date | date (YYYY-MM-DD)   | Có       | Parse từ ISO hoặc `dd/mm/yyyy`, sau clean bắt buộc ISO |
| exported_at    | datetime (ISO 8601) | Có       | Dùng tính freshness qua `latest_exported_at` trong manifest |

---

## 3. Quy tắc quarantine vs drop

Record bị flag đi đâu?
- Mọi record fail cleaning rule được ghi vào `artifacts/quarantine/quarantine_<run_id>.csv`.
- Các record này **không** đi vào `artifacts/cleaned/cleaned_<run_id>.csv`, nên không được embed.

Rule đang quarantine trong implementation:
- `unknown_doc_id`
- `missing_effective_date`
- `invalid_effective_date_format`
- `stale_hr_policy_effective_date`
- `missing_chunk_text`
- `bom_or_invisible_chars`
- `sla_value_out_of_range`
- `too_few_words`
- `duplicate_chunk_text`

Ai approve merge lại?
- Cleaning/Quality Owner review theo `reason`, sửa dữ liệu nguồn hoặc cập nhật rule có kiểm soát.
- Sau khi fix phải rerun pipeline, expectation pass rồi mới coi là publish hợp lệ.

---

## 4. Phiên bản & canonical

Source of truth:
- `policy_refund_v4` là canonical cho chính sách hoàn tiền; expectation bắt buộc không còn câu "14 ngày làm việc" sau clean.
- `hr_leave_policy` chỉ chấp nhận bản có `effective_date >= 2026-01-01` (loại bản cũ gây conflict 10 vs 12 ngày phép).

Canonical source map (theo `contracts/data_contract.yaml`):
- `data/docs/policy_refund_v4.txt` -> `policy_refund_v4`
- `data/docs/sla_p1_2026.txt` -> `sla_p1_2026`
- `data/docs/it_helpdesk_faq.txt` -> `it_helpdesk_faq`
- `data/docs/hr_leave_policy.txt` -> `hr_leave_policy`

Freshness & SLA:
- SLA mặc định: 24 giờ (`freshness.sla_hours`).
- Freshness check đọc `latest_exported_at` (fallback `run_timestamp`) trong manifest.
- Trạng thái: `PASS` (trong SLA), `WARN` (thiếu timestamp hợp lệ), `FAIL` (quá SLA hoặc thiếu manifest).