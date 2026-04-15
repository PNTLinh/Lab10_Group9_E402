# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Thùy Linh
**Vai trò:** Cleaning
**Ngày nộp:** 15/04/2026
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

transform/cleaning_rules.py
quality/expectations.py
etl_pipeline.py

**Kết nối với thành viên khác:**

Tôi kết nối chặt chẽ với Ingestion Owner để thống nhất cấu trúc đầu vào và phối hợp với Embed Owner nhằm đảm bảo dữ liệu sau khi làm sạch không làm nhiễu kết quả retrieval của Agent. Tôi đã hiện thực hóa 3 quy tắc làm sạch mới và 2 kỳ vọng dữ liệu (expectations) để xử lý các lỗi đặc thù như sai định dạng ngày, trùng lặp nội dung và xung đột chính sách giữa các phiên bản HR 2025/2026.

**Bằng chứng (commit / comment trong code):**

_________________

---

## 2. Một quyết định kỹ thuật (100–150 từ)

> VD: chọn halt vs warn, chiến lược idempotency, cách đo freshness, format quarantine.

Tôi quyết định sử dụng chiến lược "Halt on Logical Conflict" thay vì chỉ cảnh báo đơn thuần cho quy tắc refund_no_stale_14d_window.

Cụ thể, khi phát hiện một chunk văn bản thuộc doc_id: policy_refund_v4 nhưng nội dung vẫn chứa thông tin "14 ngày hoàn tiền" (vốn là của bản v3 cũ), tôi thiết lập hệ thống phải Halt (dừng pipeline) ngay lập tức. Quyết định này dựa trên rủi ro nghiệp vụ: nếu AI Agent đọc được thông tin sai lệch về thời gian hoàn tiền, nó sẽ tư vấn sai cho khách hàng, gây thiệt hại tài chính.

Bên cạnh đó, tôi áp dụng cơ chế Manual De-duplication dựa trên chunk_text trước khi đưa vào validation. Điều này đảm bảo tính Idempotent; dù dữ liệu thô bị xuất lỗi lặp dòng nhiều lần (như ID 1 và ID 2 trong file mẫu), kết quả trong VectorDB vẫn duy nhất, giúp tối ưu hóa dung lượng lưu trữ và tốc độ truy vấn.s

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

> Mô tả triệu chứng → metric/check nào phát hiện → fix.

Trong quá trình chạy thử nghiệm với run_id=2026-04-15T08-54Z, tôi phát hiện anomaly tại record ID 10: trường effective_date bị nhập sai định dạng thành 01/02/2026 (DD/MM/YYYY) thay vì ISO chuẩn.

Triệu chứng là pipeline bị dừng ở bước expect_effective_date_iso_yyyy_mm_dd với trạng thái FAIL (halt). Tôi đã xử lý bằng cách bổ sung một rule trong Date_Standardizer_V2. Thay vì loại bỏ bản ghi, tôi dùng datetime.strptime để parse định dạng ngày Việt Nam và format lại về chuẩn ISO.

Kết quả: Metric invalid_effective_date_format giảm từ 1 xuống 0 trong các lần chạy sau, cứu sống được các record FAQ quan trọng (như IT Helpdesk FAQ) mà không làm mất thông tin hữu ích của người dùng cuối.

---

## 4. Bằng chứng trước / sau (80–120 từ)

> Dán ngắn 2 dòng từ `before_after_eval.csv` hoặc tương đương; ghi rõ `run_id`.

| question_id | question | doc_id | chunk_text | is_relevant | is_correct | reason | metric_impact |
|-------------|----------|--------|------------|-------------|------------|--------|---------------|
| q_refund_window | Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn? | policy_refund_v4 | Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng. | yes | no | | 3 |
| q_p1_sla | SLA phản hồi đầu tiên cho ticket P1 là bao lâu? | sla_p1_2026 | Ticket P1 có SLA phản hồi ban đầu 15 phút và resolution trong 4 giờ. | yes | no | | 3 |    

---

## 5. Cải tiến tiếp theo (40–80 từ)

> Nếu có thêm 2 giờ — một việc cụ thể (không chung chung).

Nếu có thêm 2 giờ, tôi sẽ xây dựng Automated Schema Evolution. Hiện tại, nếu file CSV đầu vào thêm cột mới, pipeline có thể bị lỗi. Tôi muốn viết một rule tự động map các trường không xác định vào metadata của ChromaDB thay vì bỏ qua chúng. Điều này giúp tăng tính linh hoạt cho pipeline khi các hệ thống nguồn (Legacy API) thay đổi cấu trúc xuất dữ liệu mà không cần can thiệp code thủ công.
