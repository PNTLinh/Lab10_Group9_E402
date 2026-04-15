# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Thị Diệu Linh  
**Vai trò:** Ingestion   
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

Tôi phụ trách phần ETL pipeline ở Sprint 1, cụ thể là xử lý ingest và logging trong file etl_pipeline.py, bao gồm đọc dữ liệu raw từ data/raw/policy_export_dirty.csv, ghi log các chỉ số như raw_records, cleaned_records, quarantine_records, và tạo run_id cho mỗi lần chạy pipeline. Ngoài ra, tôi tham gia kiểm tra output CSV sau bước cleaning để đảm bảo dữ liệu được phân tách đúng giữa cleaned và quarantine.

**Kết nối với thành viên khác:**  
Phần của tôi là đầu vào cho Cleaning/Quality owner, vì dữ liệu ingest và log sẽ được sử dụng tiếp cho bước clean, validate và embed ở các sprint sau. Tôi đảm bảo dữ liệu được load đúng để các bước downstream không bị lỗi.
_________________

**Bằng chứng (commit / comment trong code):**

- Author: crimzonlilia
- Commit: `sprint 1` (acb63f4a383954df7429b56dce6867baae8bc60c)
- Commit: `add log` (f122543183b301a9bd784fb7270261948837edd5)
- Commit: `modified data contract` (cf0eac934943240a34f6cfe390d00317039fe00a)
- File liên quan: etl_pipeline.py, data_contract.yaml
_________________

---

## 2. Một quyết định kỹ thuật (100–150 từ)

> VD: chọn halt vs warn, chiến lược idempotency, cách đo freshness, format quarantine.

Trong Sprint 1, tôi không trực tiếp thiết kế pipeline mà tập trung vào việc chạy và kiểm tra hệ thống ETL có sẵn. Một quyết định kỹ thuật tôi sử dụng là chạy pipeline với run_id cụ thể để theo dõi kết quả từng lần chạy. Cụ thể, tôi dùng lệnh python etl_pipeline.py run --run-id sprint1 để tạo log riêng cho lần chạy này.

Log được ghi tại artifacts/logs/run_sprint1.log, bao gồm các chỉ số như raw_records, cleaned_records, và quarantine_records. 

Việc sử dụng run_id giúp tôi dễ dàng đối chiếu kết quả giữa các lần chạy và kiểm tra xem pipeline hoạt động đúng hay không, đặc biệt khi so sánh trước và sau khi cleaning.
_________________

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

> Mô tả triệu chứng → metric/check nào phát hiện → fix.

Trong quá trình chạy pipeline Sprint 1, tôi phát hiện số lượng quarantine_records khá cao (4/10 records), cho thấy dữ liệu raw chứa nhiều bất thường. Theo manifest:
```
"raw_records": 10,
"cleaned_records": 6,
"quarantine_records": 4
```
Điều này cho thấy gần 40% dữ liệu không đạt yêu cầu. Sau khi kiểm tra file data/raw/policy_export_dirty.csv, tôi nhận thấy một số vấn đề như duplicate nội dung policy, dòng chunk_text rỗng, và format ngày không đồng nhất. Các lỗi này khiến record bị đưa vào quarantine thay vì cleaned dataset.  
Pipeline đã xử lý anomaly bằng cách tách riêng các record lỗi vào file quarantine, đảm bảo dữ liệu dùng cho bước embedding chỉ bao gồm các record hợp lệ. Điều này giúp giảm nguy cơ agent sử dụng dữ liệu sai lệch trong quá trình truy xuất.
_________________

---

## 4. Bằng chứng trước / sau (80–120 từ)

> Dán ngắn 2 dòng từ `before_after_eval.csv` hoặc tương đương; ghi rõ `run_id`.

Trong quá trình đánh giá, tôi so sánh kết quả retrieval giữa hai lần chạy: run_id = inject-bad (dữ liệu lỗi) và run_id = 2026-04-15T09-10Z (sau khi clean). Với câu hỏi về refund window, kết quả như sau:
```
inject-bad,q_refund_window,policy_refund_v4,yes,yes
2026-04-15T09-10Z,q_refund_window,policy_refund_v4,yes,no
```
Có thể thấy ở lần inject lỗi, hits_forbidden = yes, nghĩa là vẫn tồn tại chunk sai trong top-k retrieval. Sau khi chạy pipeline chuẩn, giá trị này giảm về no, cho thấy dữ liệu đã được làm sạch và không còn ảnh hưởng bởi policy sai. Điều này chứng minh bước cleaning và validation giúp cải thiện chất lượng retrieval rõ rệt.
_________________

---

## 5. Cải tiến tiếp theo (40–80 từ)

> Nếu có thêm 2 giờ — một việc cụ thể (không chung chung).

Nếu có thêm 2 giờ, tôi sẽ bổ sung một expectation kiểm tra format ngày cho trường effective_date và exported_at (chuẩn ISO 8601), vì trong dữ liệu raw có tồn tại định dạng không đồng nhất (ví dụ 01/02/2026). Điều này giúp phát hiện sớm lỗi parsing và tránh việc record sai định dạng lọt vào cleaned dataset, ảnh hưởng đến downstream như filtering theo version hoặc freshness check.
_________________
