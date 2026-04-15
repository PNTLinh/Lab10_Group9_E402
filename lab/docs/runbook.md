# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

> Agent trả lời sai chính sách (VD: "hoàn tiền trong 14 ngày" thay vì 7 ngày, hoặc "10 ngày phép năm" thay vì 12 ngày).  
> Có thể kèm dấu hiệu: câu trả lời không nhất quán giữa các lần hỏi, hoặc metadata `effective_date` không đúng version mới nhất.

---

## Detection

| Nguồn phát hiện | Tín hiệu | Ý nghĩa |
|-----------------|----------|---------|
| `freshness_check` | `FAIL freshness_sla_exceeded` | Data trong vector store cũ hơn SLA (mặc định 24 h) |
| `freshness_check` | `WARN no_timestamp_in_manifest` | Manifest thiếu trường thời gian — không thể xác nhận độ tươi |
| Expectation suite | `expectation[refund_no_stale_14d_window] FAIL` | Chunk hoàn tiền 14 ngày vẫn còn trong cleaned data |
| Expectation suite | `expectation[no_bom_in_cleaned_chunks] FAIL` | BOM/zero-width chars lọt vào cleaned data (rule quarantine bị bypass/lỗi)|
| Eval retrieval | `hits_forbidden > 0` | Top-k trả về chunk bị cấm (stale version) |

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/*.json` | Tìm manifest mới nhất; đọc `latest_exported_at` và `run_timestamp` |
| 2 | Chạy lệnh freshness (xem bên dưới) | In ra `PASS`, `WARN`, hoặc `FAIL` kèm `age_hours` |
| 3 | Mở `artifacts/quarantine/*.csv` | Xem dòng bị loại; kiểm tra cột `reason` (ví dụ: `duplicate_chunk_text`, `stale_hr_policy_effective_date`, `bom_or_invisible_chars`) |
| 4 | Chạy `python eval_retrieval.py` | `hits_forbidden=0` là bình thường; > 0 → vector store còn chunk cũ |

### Lệnh kiểm tra freshness

```bash
python etl_pipeline.py freshness --manifest artifacts/manifests/<tên_file>.json
```

Ví dụ output:

```
PASS {"latest_exported_at": "2026-04-15T07:00:00+00:00", "age_hours": 1.25, "sla_hours": 24.0}
WARN {"reason": "no_timestamp_in_manifest", "manifest": {...}}
FAIL {"latest_exported_at": "2026-04-12T06:00:00+00:00", "age_hours": 73.5, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

#### Giải thích PASS / WARN / FAIL

| Status | Điều kiện | Ý nghĩa thực tế | Hành động |
|--------|-----------|-----------------|-----------|
| **PASS** | `age_hours ≤ sla_hours` (mặc định 24 h) | Data đủ tươi — `latest_exported_at` trong manifest không cũ hơn SLA. Vector store đang phục vụ version hợp lệ. | Không cần làm gì. Ghi log để audit. |
| **WARN** | Manifest tồn tại nhưng **không có** trường `latest_exported_at` lẫn `run_timestamp`, hoặc giá trị không parse được thành ISO datetime. | Không thể xác định độ tươi — pipeline có thể đã chạy thiếu bước ghi metadata. Data vẫn có thể dùng nhưng rủi ro ẩn. | Kiểm tra log run tương ứng trong `artifacts/logs/`; rerun pipeline để sinh manifest đúng. |
| **FAIL** | `age_hours > sla_hours` | Data cũ hơn SLA — có nguy cơ chunk stale trong vector store. | Xem mục Mitigation bên dưới. |

> **Biến môi trường:** `FRESHNESS_SLA_HOURS` ghi đè ngưỡng mặc định 24 h.  
> Ví dụ PowerShell: `$env:FRESHNESS_SLA_HOURS=48; python etl_pipeline.py freshness --manifest ...`

> **Exit code:** lệnh trả về `0` khi PASS hoặc WARN; trả về `1` khi FAIL — tích hợp được vào CI/CD pipeline.

---

## Mitigation

### Khi FAIL — `freshness_sla_exceeded`

```bash
# 1. Rerun pipeline với data mới
python etl_pipeline.py run

# 2. Xác nhận freshness sau rerun
python etl_pipeline.py freshness --manifest artifacts/manifests/<manifest_mới>.json
```

### Khi FAIL — `manifest_missing`

```bash
# Manifest không có → chạy lại pipeline từ đầu
python etl_pipeline.py run --run-id recovery-2026-04-15T09-30Z
```

### Tạm thời (nếu chưa thể rerun ngay)

- Thêm banner trong UI agent: _"Dữ liệu chính sách đang được cập nhật — vui lòng kiểm tra lại sau."_
- Tăng retrieval confidence threshold hoặc bật chế độ "không đủ bằng chứng thì từ chối trả lời".

---

## Prevention

| Biện pháp | Cách làm |
|-----------|----------|
| **Alert tự động** | Thêm `FRESHNESS_SLA_HOURS=24` vào `.env`; tích hợp `cmd_freshness` vào CI — build fail khi exit code = 1 |
| **Expectation bổ sung** | E3 (`refund_no_stale_14d_window`) + E7 (`no_bom_in_cleaned_chunks`) đã có; thêm expectation kiểm tra `effective_date ≥ cutoff` nếu cần |
| **Owner rõ ràng** | Ghi `owner` vào manifest JSON — biết ai chịu trách nhiệm khi freshness FAIL |
| **Guardrail Day 11** | Nối sang Day 11: thêm watermark DB làm nguồn `latest_exported_at` thay vì dựa vào timestamp chạy pipeline |
