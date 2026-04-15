# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn                  | Phương thức ingest | Failure mode chính                                      | Metric / alert                      |
| ---------------------- | ------------------ | ------------------------------------------------------- | ----------------------------------- |
| policy_refund_v4       | Batch CSV export   | Duplicate chunk, conflict version (v3 vs v4), null text | % duplicate chunk_id, conflict rate |
| sla_p1_2026            | Batch CSV export   | Thiếu metadata, sai format date                         | % missing fields                    |
| it_helpdesk_faq        | Batch CSV export   | Sai format date (dd/mm/yyyy vs yyyy-mm-dd)              | % invalid date                      |
| hr_leave_policy        | Batch CSV export   | Version conflict (2025 vs 2026)                         | version mismatch count              |
| legacy_catalog_xyz_zzz | Batch CSV export   | Noise data, không liên quan domain                      | % irrelevant docs                   |


---

## 2. Schema cleaned

| Cột            | Kiểu                | Bắt buộc | Ghi chú             |
| -------------- | ------------------- | -------- | ------------------- |
| chunk_id       | string              | Có       | Unique, không trùng |
| doc_id         | string              | Có       | Định danh tài liệu  |
| chunk_text     | string              | Có       | Không được rỗng     |
| effective_date | date (YYYY-MM-DD)   | Có       | Chuẩn hóa format    |
| exported_at    | datetime (ISO 8601) | Có       | Thời điểm export    |

---

## 3. Quy tắc quarantine vs drop

> Record bị flag đi đâu? Ai approve merge lại?  

Record bị flag đi đâu?  
 Được đưa vào quarantine dataset (ghi ra file riêng bằng write_quarantine_csv)  
 Các record không đạt yêu cầu sẽ bị loại bỏ ngay trong clean_rows() và không xuất hiện trong output

Ai approve merge lại?  
 Thực hiện bởi owner       

---

## 4. Phiên bản & canonical

> Source of truth cho policy refund: file nào / version nào?
policy_refund_v4 (effective_date = 2026-02-01)