# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** [Điền tên bạn ở đây]
**Vai trò:** Cleaning & Quality Owner — Sprint 3
**Ngày nộp:** 2026-04-15
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

Tôi chịu trách nhiệm chính cho Sprint 3: kiểm thử pipeline khi cố ý inject lỗi (bỏ qua fix refund, skip validate) và đánh giá chất lượng retrieval trước/sau khi sửa. Tôi thực hiện các lệnh:
- `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`
- `python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv`
- So sánh với file eval chuẩn: `artifacts/eval/before_after_eval.csv`
Tôi kiểm tra kỹ các artifact: manifest, cleaned/quarantine CSV, file eval before/after để đảm bảo số liệu đúng, có bằng chứng rõ ràng cho báo cáo nhóm và cá nhân.

**Bằng chứng:**
- File: artifacts/eval/before_after_eval.csv, artifacts/eval/after_inject_bad.csv
- manifest_inject-bad.json, manifest_2026-04-15T09-16Z.json
- cleaned_inject-bad.csv, cleaned_2026-04-15T09-16Z.csv

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi quyết định dùng kịch bản inject-bad để kiểm tra khả năng observability của pipeline: intentionally bỏ qua fix refund và validate, sau đó so sánh retrieval. Việc này giúp chứng minh expectation và rule cleaning thực sự có tác động, không chỉ chạy cho đủ. Tôi chọn so sánh cột `hits_forbidden` và `contains_expected` trên câu hỏi `q_refund_window` và `q_leave_version` để có số liệu định lượng rõ ràng, đúng yêu cầu DoD. Quy trình này giúp nhóm dễ dàng truy vết lỗi, chứng minh chất lượng pipeline và đáp ứng tiêu chí merit.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Khi chạy inject-bad, tôi phát hiện retrieval cho `q_refund_window` trả về context sai (vẫn còn chunk hoàn tiền 14 ngày). Điều này thể hiện ở file after_inject_bad.csv: `hits_forbidden = yes` (trước đó là no). Tôi đã kiểm tra lại cleaning_rules.py và expectation, xác nhận nếu không fix refund hoặc skip validate thì pipeline không loại bỏ được chunk lỗi. Sau khi sửa lại pipeline và chạy lại, retrieval trả về đúng context, `hits_forbidden = no`. Đây là bằng chứng rõ ràng cho tác động của rule/expectation.

---

## 4. Bằng chứng artifact / log (80–120 từ)

question_id,question,top1_doc_id,top1_preview,contains_expected,hits_forbidden,top1_doc_expected,top_k_used
q_refund_window,Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?,policy_refund_v4,Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.,yes,no,,3
q_p1_sla,SLA phản hồi đầu tiên cho ticket P1 là bao lâu?,sla_p1_2026,Ticket P1 có SLA phản hồi ban đầu 15 phút và resolution trong 4 giờ.,yes,no,,3

2026-04-15T09-10Z

_________________

---

## 5. Cải tiến tiếp theo (40–80 từ)

_________________

Nếu có thêm 2 giờ, tôi sẽ tự động hóa toàn bộ quy trình kiểm thử corruption inject và so sánh retrieval bằng script Python hoặc notebook. Cụ thể, tôi sẽ viết một script chạy nhiều kịch bản inject khác nhau, tự động thu thập số liệu before/after, sinh báo cáo markdown kèm bảng so sánh. Điều này giúp tiết kiệm thời gian, giảm sai sót thủ công và dễ dàng mở rộng kiểm thử cho các rule/expectation mới trong tương lai.
