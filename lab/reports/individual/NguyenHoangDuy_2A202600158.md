# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Hoàng Duy  
**Vai trò:** Monitoring / Docs Owner  
**MSSV:** 2A202600158  
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `monitoring/freshness_check.py` — đọc manifest và kiểm tra SLA freshness
- `docs/runbook.md` — viết toàn bộ quy trình phát hiện, chẩn đoán, xử lý incident
- `docs/pipeline_architecture.md` — mô tả kiến trúc và ranh giới trách nhiệm từng thành phần
- `docs/data_contract.md` — tổng hợp source map, schema cleaned, quy tắc quarantine

**Kết nối với thành viên khác:**  
Tôi nhận đầu ra từ Ingestion Owner (manifest JSON tại `artifacts/manifests/`) và Embed Owner (collection Chroma) để kiểm tra freshness và viết tài liệu vận hành. Runbook và docs của tôi phản ánh đúng số liệu thực tế từ các sprint trước (run_id, quarantine reason, expectation result) để nhóm có thể dùng khi cần xử lý incident.

**Bằng chứng:**  
- `docs/runbook.md` — hoàn chỉnh với bảng PASS/WARN/FAIL và mục Mitigation/Prevention  
- `monitoring/freshness_check.py` — hàm `check_manifest_freshness` trả về tuple `(status, detail)`

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi quyết định thiết kế freshness check trả về **3 trạng thái** (PASS / WARN / FAIL) thay vì chỉ pass/fail nhị phân.

Lý do: trường hợp manifest tồn tại nhưng thiếu trường timestamp (`latest_exported_at` và `run_timestamp` đều null) không phải lỗi pipeline nghiêm trọng — data vẫn có thể dùng được nhưng không xác nhận được độ tươi. Nếu map thẳng vào FAIL, on-call sẽ rerun pipeline không cần thiết. WARN cho phép team điều tra log trước khi quyết định.

Ngoài ra, tôi chọn để `check_manifest_freshness` nhận tham số `now` inject từ ngoài (thay vì gọi `datetime.now()` bên trong), giúp unit test kiểm soát được thời điểm so sánh mà không cần mock hệ thống. Đây là pattern dependency injection đơn giản nhưng quan trọng cho testability của monitoring code.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Khi viết runbook, tôi kiểm tra lại logic trong `freshness_check.py` và phát hiện: nếu `latest_exported_at` rỗng chuỗi (`""`), hàm `parse_iso` trả về `None`, sau đó code fallback sang `run_timestamp`. Tuy nhiên nếu cả hai đều rỗng, status trả về `WARN` với `reason: no_timestamp_in_manifest`.

Vấn đề: trong `cmd_run` của `etl_pipeline.py` (dòng 110), `latest_exported` được tính bằng `max(...)` trên danh sách `exported_at` của cleaned rows — nếu tất cả record có `exported_at` rỗng, kết quả là chuỗi rỗng `""` ghi vào manifest, dẫn đến WARN mặc dù pipeline vừa chạy xong thành công.

Tôi ghi rõ anomaly này vào runbook (mục Mitigation — WARN) và hướng dẫn: kiểm tra `artifacts/logs/run_<run_id>.log` tìm dòng `freshness_check=WARN` để phân biệt với FAIL thật sự.

---

## 4. Bằng chứng trước / sau (80–120 từ)

Dựa trên manifest từ run_id `2026-04-15T09-16Z` (run chuẩn sau khi fix):

```
freshness_check=PASS {"latest_exported_at": "2026-02-01T00:00:00+00:00",
  "age_hours": 1727.27, "sla_hours": 24.0}
```

> Lưu ý: `latest_exported_at` lấy từ trường `exported_at` trong CSV (`2026-02-01`), không phải thời điểm chạy pipeline — nên `age_hours` lớn. Đây là đặc điểm của bộ dữ liệu mẫu tĩnh (policy export ngày cố định), không phải lỗi freshness. Trong môi trường thực tế, `exported_at` sẽ là timestamp của lần export gần nhất từ DB nguồn.

Với run_id `inject-bad`, manifest có thêm `"skipped_validate": true` — dấu hiệu để runbook cảnh báo on-call kiểm tra expectation log trước khi tin vào vector store.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ thêm trường `watermark_db` vào manifest — lấy từ timestamp record mới nhất trong DB nguồn thay vì dựa vào `exported_at` trong CSV. Điều này cho phép freshness check đo đúng độ trễ thực tế từ nguồn đến vector store, không bị ảnh hưởng bởi dữ liệu mẫu tĩnh như hiện tại.
