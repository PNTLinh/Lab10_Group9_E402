# Kiến trúc pipeline — Lab Day 10

**Nhóm:** 09 
**Cập nhật:** 15/4/2026

---

## 1. Sơ đồ luồng (bắt buộc có 1 diagram: Mermaid / ASCII)

```mermaid
Raw CSV (`data/raw/policy_export_dirty.csv`)
  -> Ingest (`load_raw_csv`)
  -> Clean + Quarantine (`clean_rows`)
  -> Validate (`run_expectations`)
  -> Embed snapshot (`cmd_embed_internal`, Chroma upsert + prune)
  -> Publish manifest/logs (`artifacts/manifests`, `artifacts/logs`)
  -> Serving retrieval (Day 09 agent/RAG dùng collection đã publish)

Nhánh lỗi/quan sát:
  - Record lỗi clean -> `artifacts/quarantine/quarantine_<run_id>.csv`
  - Expectation halt fail -> dừng pipeline (exit 2), trừ khi dùng `--skip-validate` để demo inject
  - Freshness check đọc manifest -> PASS/WARN/FAIL theo SLA
```

Điểm đo bắt buộc:
- `run_id` được log ngay đầu run và ghi trong metadata vector.
- `freshness` đo từ `latest_exported_at` (fallback `run_timestamp`) trong manifest.
- `quarantine` ghi file riêng, có `reason` để thống kê `metric_impact`.

---

## 2. Ranh giới trách nhiệm

| Thành phần | Input | Output | Owner nhóm |
|------------|-------|--------|--------------|
| Ingest | `data/raw/*.csv` | `rows` thô + `raw_records` log | Ingestion Owner |
| Transform | `rows` thô | `cleaned_*.csv`, `quarantine_*.csv` | Cleaning/Quality Owner |
| Quality | `cleaned rows` | expectation results + quyết định halt | Cleaning/Quality Owner |
| Embed | `cleaned_*.csv` | Chroma collection đã upsert/prune | Embed Owner |
| Monitor | `manifest_*.json` | trạng thái freshness PASS/WARN/FAIL | Monitoring/Docs Owner |

---

## 3. Idempotency & rerun

- Pipeline embed theo chiến lược **idempotent snapshot publish**:
  - Upsert theo `chunk_id` (`col.upsert(ids=ids, ...)`) nên rerun không tạo bản ghi trùng cho cùng ID.
  - Trước khi upsert, pipeline đọc toàn bộ id hiện có và **xóa id không còn trong cleaned run hiện tại** (`col.delete(ids=drop)`).
- Hệ quả:
  - Chạy lại với cùng cleaned data -> số vector giữ ổn định, không duplicate.
  - Chạy lại sau khi clean thay đổi -> index phản ánh đúng snapshot mới, tránh stale chunk làm lệch top-k retrieval.

---

## 4. Liên hệ Day 09

- Day 09 cần retrieval dựa trên corpus đúng version. Day 10 bổ sung lớp dữ liệu để đảm bảo điều đó.
- Trong repo này, ETL Day 10 publish vào Chroma collection (mặc định `day10_kb`) với metadata `run_id`, `doc_id`, `effective_date`.
- Agent/RAG phía Day 09 có thể dùng collection đã publish để truy vấn; nhờ cơ chế prune, retrieval không còn tham chiếu chunk cũ sau mỗi run.
- Nguồn canonical vẫn bám theo nhóm policy/helpdesk giống narrative Day 09 (`policy_refund_v4`, `sla_p1_2026`, `it_helpdesk_faq`, `hr_leave_policy`).

---

## 5. Rủi ro đã biết

- **Bypass validate có chủ đích:** dùng `--skip-validate` có thể đẩy dữ liệu xấu vào vector store (chỉ nên dùng cho Sprint 3 evidence).
- **Sai timezone/format timestamp:** `latest_exported_at` không parse được sẽ ra WARN freshness, khó giám sát đúng SLA.
- **Mở rộng doc_id chưa cập nhật allowlist:** record mới sẽ vào quarantine (`unknown_doc_id`) nếu quên đồng bộ contract + rule.
- **Quá phụ thuộc text pattern:** rule SLA phút và refund window dựa chuỗi; nếu phrasing đổi mạnh cần cập nhật rule/expectation.
