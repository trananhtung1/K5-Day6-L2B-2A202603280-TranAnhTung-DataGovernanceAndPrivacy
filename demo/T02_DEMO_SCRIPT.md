# Kịch bản demo T02 (3-5 phút)

Mục tiêu: để người xem thấy **dữ liệu -> xử lý -> người duyệt -> chạy lại -> kết quả**.
Mỗi vai chỉ cần đọc phần của mình; thay tên người duyệt bằng tên thật khi demo.

## Chuẩn bị trước khi mở màn

```bash
make baseline-t02
make run TRACK=t02
make test
open out/poc/contact_sheet.html
```

Nếu `open` không dùng được, mở `out/poc/contact_sheet.html` bằng trình duyệt.
Đừng chạy `make eval-*` nếu chưa có overlay GT của giảng viên: đó là nhãn ẩn và không phải lỗi của nhóm.

## Sáu bước trình diễn

1. **Trưởng nhóm - bài toán (20 giây).**
   “Nhóm làm T02 Raw QC Triage. Với 96 ảnh và chỉ 20 lượt review, nhóm ưu tiên ảnh nghi mờ, tối, chói hoặc nén để quyết định KEEP hay RECAPTURE.”

2. **Phụ trách dữ liệu - một input (20 giây).**
   Mở `fixtures/t02_raw_qc/images.csv`, sau đó mở một file trong `fixtures/t02_raw_qc/images/`.
   Nêu các trường `camera_id`, `light`, `split`; dữ liệu là synthetic CC0 và pipeline kiểm SHA-256 trong `manifest.csv`.

3. **Phụ trách xử lý - baseline và PoC (45 giây).**
   Chạy `make baseline-t02`, rồi `make run TRACK=t02`.
   Nêu: baseline chỉ dùng độ nét Laplacian; PoC kết hợp blur, dark, glare, compression và chuẩn hoá bằng ảnh dev theo camera/ánh sáng. Mở `out/poc/ranked_review.csv` và `out/poc/review_queue.csv`.

4. **Người duyệt - duyệt một mục (45 giây).**
   Trong contact sheet, nhập tên reviewer, tại một card chọn `reject` hoặc `edit`, ghi lý do, rồi bấm **Export decisions CSV**.
   Chép file tải về thành `out/poc/review_queue_reviewed.csv`.

5. **Trưởng nhóm - chạy lại và chứng minh audit (45 giây).**
   Chạy lại:

   ```bash
   make run TRACK=t02
   ```

   Mở `out/poc/ranked_review.csv` để thấy mục bị `reject` có score `-1`, rồi mở `out/poc/audit_log.jsonl` để chỉ tên reviewer, lý do và thay đổi. Mở `out/poc/decision.json` để giải thích HOLD/KEEP/RECAPTURE.

6. **Phụ trách QA - hiệu quả và ca khó (30 giây).**
   Mở `reports/metric_contract.md`: primary metric là Defect Recall@20, B=20, eval không dùng để tune.
   Nêu một giới hạn: ảnh night sạch hoặc cam_B optics mềm có thể false alarm; vì thế hệ thống cần human review. Khi giảng viên cài GT overlay, chạy `make eval-baseline eval-poc compare TRACK=t02` và mở `reports/table1_baseline_vs_poc.md`.

## Chốt trước khi nộp

- Thay `G00` và xác nhận owner trong `configs/lab.yaml`.
- Có ít nhất một file `out/poc/review_queue_reviewed.csv` do người thật duyệt; rerun PoC sau đó.
- Điền thành viên và commit thực chất trong `reports/team_contributions.csv` và `reports/group_report.md`.
- Chạy `make test`, rồi tạo tag `demo-180m` và `final-24h` đúng mốc lớp.
