# Metric contract (khai báo bắt buộc — chốt ở phút 30, trước khi chạy eval)

> Các metric chuẩn đã được cài trong `src/metrics/tracks.py`. File này là nơi nhóm **cam kết** cách dùng chúng.
> Không đổi testset, threshold hay trọng số sau khi đã thấy kết quả eval.

| Mục | Khai báo của nhóm |
|---|---|
| Track | T02 · Raw QC Triage |
| Primary metric (tên đúng như evaluator in ra) | Defect Recall@B |
| Tăng tốt hay giảm tốt? | higher |
| Đơn vị đánh giá (image / region / pair / release / batch / case …) | image |
| Công thức + numerator / denominator | số ảnh lỗi thật nằm trong top-B / tổng ảnh lỗi thật của split eval |
| Cách ghép prediction ↔ GT (IoU? id? tolerance?) | ghép chính xác bằng `image_id`; evaluator sắp xếp `score` giảm dần |
| Candidate pool cố định | 96 ảnh trong `fixtures/t02_raw_qc/images.csv`; metric chính chỉ dùng `split=eval` |
| Review budget B / K | B=20 |
| Seed | 42 |
| Threshold policy (chọn trên dev như thế nào) | Robust median/MAD từ `dev`, ưu tiên `camera_id + light` (≥4), rồi light, camera, global; score kết hợp blur/dark/glare/compression. Ngưỡng `recapture_score=1.25` đã freeze trong `configs/lab.yaml`. |
| Eval split (không dùng để tune) | `eval`; không đọc GT trong pipeline |
| Chỉ số lỗi xấu (miss / false alarm / false reject) | defect miss ngoài top-20; Precision@20; false alarm theo `light` |
| Slices sẽ báo cáo (≥2) | `light` (day/dusk/night), `pred_defect_type`, camera_id (mô tả thủ công) |
| Cách báo độ bất định khi N nhỏ (Wilson CI / bootstrap) | Báo numerator/denominator cùng Wilson 95% CI cho Recall@20 và Precision@20; kèm từng case top-20. |
| Ngày giờ chốt + người chốt | 2026-11-15, Tran Anh Tung (cập nhật giờ/group ID trước khi nộp) |

Nếu baseline = 0 thì ghi rõ "baseline = 0" thay vì phần trăm cải thiện.
