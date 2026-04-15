# Quality report — Lab Day 10 (nhóm)

**run_id:** 2026-04-15T09-16Z  
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước | Sau | Ghi chú |
|--------|-------|-----|---------|
| raw_records | 10 | 10 | |
| cleaned_records | 6 | 6 | |
| quarantine_records | 4 | 4 | |
| Expectation halt? | OK | OK | |

---

## 2. Before / after retrieval (bắt buộc)

> Đính kèm hoặc dẫn link tới `artifacts/eval/before_after_eval.csv` (chuẩn) và `artifacts/eval/after_inject_bad.csv` (inject-bad).

**Câu hỏi then chốt:** refund window (`q_refund_window`)

**Trước:**
question_id: q_refund_window
contains_expected: yes
hits_forbidden: no

**Sau:**
question_id: q_refund_window
contains_expected: yes
hits_forbidden: yes

**Merit:** versioning HR — `q_leave_version`

**Trước:**
contains_expected: yes
hits_forbidden: no

**Sau:**
contains_expected: yes
hits_forbidden: no

---

## 3. Freshness & monitor

freshness_check=FAIL {"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 121.294, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}

---

## 4. Corruption inject (Sprint 3)

Đã cố ý bỏ qua fix refund (dùng --no-refund-fix) và skip validate, dẫn đến chunk hoàn tiền vẫn còn giá trị cũ (14 ngày) trong vector DB. Điều này làm retrieval trả về context sai cho câu hỏi hoàn tiền, thể hiện ở cột hits_forbidden = yes.

---

## 5. Hạn chế & việc chưa làm

- Chưa kiểm thử với nhiều bộ dữ liệu khác.
- Chưa tối ưu expectation cho các trường hợp edge-case.
- Chưa tự động hoá toàn bộ pipeline.
