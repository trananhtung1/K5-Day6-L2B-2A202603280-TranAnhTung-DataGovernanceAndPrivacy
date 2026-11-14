# Group Report — Day 06 Data Lab (Field-to-Release PoC)

> Điền đầy đủ, cụ thể, không viết chung chung. Mọi con số phải lấy từ file do script sinh ra
> (`reports/metrics_*.json`, `reports/table1_baseline_vs_poc.md`) — không gõ tay, không làm tròn mất đơn vị.
> 3–5 trang (hoặc README + report.md tương đương).

## 00 · Header

| Mục | Giá trị |
|---|---|
| Group ID | G05 |
| Challenge | T02 · Raw QC Triage |
| Thành viên (1) + vai trò | Tran Anh Tung — Lead/Integrator, data & fixtures, core algorithm, QA/metric, human review, report + demo. Làm một mình do không tham dự buổi lab; khai báo minh bạch thay vì tạo thành viên giả. |
| Git URL | https://github.com/trananhtung1/K5-Day6-L2B-2A202603280-TranAnhTung-DataGovernanceAndPrivacy |
| Tag `demo-180m` (commit) | **Tạo sau khi demo freeze** |
| Tag `final-24h` (commit) | **Tạo ngay trước khi nộp** |
| Deadline (giờ VN) | 14:00, 15/11/2026 (suy ra từ mốc 14:00 ngày 14/11 +24h; cần đối chiếu thông báo lớp nếu có). |

## 01 · Problem statement

- Ai bị ảnh hưởng / ai chịu hậu quả khi hệ thống sai? Người gán nhãn và đội thu thập dữ liệu: bỏ sót ảnh lỗi làm giảm chất lượng model; false alarm làm tốn ngân sách review/recapture.
- Điểm nghẽn cụ thể: chỉ có budget B=20 cho 96 ảnh, cần ưu tiên ảnh có khả năng mờ, quá tối, chói cục bộ hoặc nén mạnh.
- Đầu vào → đầu ra: `images.csv` + JPG → feature QC → `ranked_review.csv` + top-20 review queue → reviewer override/audit → quyết định KEEP/RECAPTURE.
- Tiêu chí GO / HOLD / REWORK (chốt trước khi chạy eval): chưa có review thì HOLD; có ảnh được reviewer xác nhận cần chụp lại thì RECAPTURE; chỉ KEEP khi review hoàn tất và không còn ảnh RECAPTURE.
- Giả định của nhóm (cần DPO/legal/domain owner xác nhận): fixture là ảnh synthetic CC0; tín hiệu không thay thế đánh giá chất lượng miền thực tế và reviewer là người ký cuối.

## 02 · Data & provenance

| Split | N | Nguồn / link | License | Synthetic? |
|---|---|---|---|---|
| dev | 56 | `fixtures/t02_raw_qc/` | CC0-1.0 | Có |
| eval / heldout | 40 | `fixtures/t02_raw_qc/` | CC0-1.0 | Có |

- Schema & class mapping: `image_id, path, camera_id, light, split`; prediction thêm `score`, `pred_defect_type ∈ {none, blur, dark, glare, compression}`, `pred_action ∈ {KEEP, RECAPTURE}`.
- Seed: 42 · Cách chia split: theo 24 cảnh gốc (không trộn biến thể của cùng cảnh giữa dev/eval).
- `manifest.csv` verified (sha256): có — lệnh `make preflight` đã PASS ngày 2026-11-15.
- Dữ liệu thật dùng (nếu có) và cách xây GT cho nó: không dùng; lab chỉ dùng fixture synthetic.

## 03 · Research & design

- 2–3 references (URL + ngày xem) và **vì sao** chọn kỹ thuật: [ACDC dataset](https://arxiv.org/abs/2104.13395), 2026-11-15 — nhắc đến điều kiện lái xe bất lợi nên báo cáo theo `light`; [ISO/IEC TR 5259-6:2026](https://www.iso.org/standard/5259-6), 2026-11-15 — dùng score + contact sheet để con người đánh giá data quality measure. Xem thêm `docs/tracks/T02.md` của lab.
- Sơ đồ data flow (input → process → rank/QC → review → decision → report): manifest/hash → ảnh + metadata → Laplacian, brightness, saturation/highlight, JPEG blockiness → robust score → top-20 HTML/CSV → override + audit JSONL → KEEP/HOLD/RECAPTURE → report.
- Thành phần offline (model/weights + checksum + license nếu có): Python, NumPy, Pillow, SciPy; không dùng model/weight/download ngoài; fixture có manifest SHA-256 và CC0-1.0.
- Trade-offs đã cân nhắc: score đa tín hiệu bao phủ glare/dark/compression tốt hơn sharpness đơn lẻ, nhưng có thể false alarm theo camera/light; chuẩn hoá median/MAD theo dev giúp giảm bias điều kiện ánh sáng, không dùng nhãn eval.

## 04 · Baseline vs PoC

- Baseline (mô tả, version/config, commit): `src.baseline_t02`; xếp theo âm của global Laplacian variance duy nhất.
- PoC (mô tả, version/config, commit): `src.pipeline`; robust dev median/MAD + 4 tín hiệu (blur, dark, glare, compression), contact sheet và override audit.
- Cùng budget / cùng heldout / cùng seed: xác nhận B=20, candidate pool cố định, seed=42. Commit SHA cần điền sau commit cuối.

**Bảng 1 · Baseline vs PoC & hard slices** — dán output của
`python -m src.compare reports/metrics_baseline.json reports/metrics_poc.json`:

| Metric (unit) | Baseline | PoC | Δ & chú thích |
|---|---|---|---|
| Primary: Defect Recall@20 | chờ hidden GT | chờ hidden GT | higher; **không tự điền số** |
| Hard-slice: light=night | chờ hidden GT | chờ hidden GT | N cần script evaluator xác nhận |
| Review@B / miss / FP | chờ hidden GT | chờ hidden GT | B=20 |
| Runtime / 100 items | lấy từ `reports/metrics_*.json` | lấy từ `reports/metrics_*.json` | CPU do script ghi |

## 05 · Evaluation protocol

- Công thức primary metric, đơn vị đánh giá, TP/FP/FN, denominator: Defect Recall@20 = số defect GT trong top-20 / tổng defect GT trên eval; xem `reports/metric_contract.md`.
- Threshold / budget B / K và lúc chốt: B=20; `recapture_score=1.25`; frozen trong `configs/lab.yaml` ngày 2026-11-15 trước hidden evaluation.
- Độ bất định (CI/bootstrap/variance) khi N nhỏ: ghi numerator/denominator và Wilson 95% CI; đính kèm toàn bộ top-20 để reviewer kiểm tra.
- Lệnh evaluate chính xác: `make eval-baseline eval-poc compare TRACK=t02` (cần instructor overlay có hidden GT).

## 06 · Result slices

| Slice | N | Baseline | PoC | Ghi chú |
|---|---|---|---|---|
| | | | | |
| | | | | |

- Failure case 1 (ảnh/metadata + root cause): ảnh night sạch có thể có score dark cao; pipeline đã fallback chuẩn hoá theo `light` từ dev khi camera-light combination không có trong split, nhưng reviewer vẫn phải kiểm tra top-B.
- Failure case 2: cam_B có optics mềm có thể bị lỗi blur false positive; cần hard-slice theo camera và tăng dev reference nếu triển khai ngoài fixture.
- Latency / compute (máy, CPU, ms/item): lấy chính xác từ `run_info.json`/`metrics_poc.json` ở lần run/tag nộp cuối, không làm tròn bằng tay.

## 07 · Human & decision

- Review queue (file, B, cách ưu tiên): `out/poc/review_queue.csv`, B=20, `score` giảm dần; `out/poc/contact_sheet.html` nhúng ảnh để review offline. **Đã review 20/20 mục.**
- Cách override + audit log (`out/audit_log.jsonl`): Trần Anh Tùng export `review_queue_reviewed.csv` từ contact sheet, chép vào `out/poc/`, rồi rerun; `reject` hạ score và `edit` nhận KEEP/RECAPTURE hoặc score số. Audit JSONL append-only đã ghi từng quyết định, lý do và giá trị trước/sau.
- Decision policy + `reason_code` + owner: kết quả run sau review là `RECAPTURE` (canonical `REWORK`), reason code `QC_DEFECTS_CONFIRMED`, owner Trần Anh Tùng. Chưa review = HOLD/`HUMAN_REVIEW_PENDING`; sạch sau review = GO/`QC_REVIEW_COMPLETE`.
- Khi nào HOLD/REWORK thay vì tự động release: thiếu reviewer, audit thiếu, hoặc reviewer xác nhận ít nhất một ảnh cần recapture. Run hiện tại thuộc trường hợp cuối.

## 08 · Reproduce & tests

```bash
make setup          # hoặc: python -m venv .venv && pip install -r requirements.txt
python -m src.main --input fixtures/<track> --config configs/lab.yaml --output out/ --offline --seed 42
python -m src.evaluate --track t__ --pred out/<file> --out reports/metrics_poc.json
pytest -q
```

- Output của `pytest -q`: PASS (2026-11-15; rerun và lưu console output ngay trước khi nộp).
- Máy / CPU / OS / Python: xem `out/poc/run_info.json` của lần run cuối · git sha: điền sau commit/tag cuối.

## 09 · Limitations & ethics

- Rủi ro pháp lý / PII / license: fixture synthetic CC0, không có PII thật; không đưa dữ liệu thật/chưa được phép lên cloud hoặc git public.
- Điều chưa biết; false alarms; nếu scale 10× thì sao: MAD calibration phải được cập nhật theo camera/ánh sáng đã duyệt; cần sampling/audit rate và queue streaming thay vì đọc hết vào RAM.
- Không tuyên bố "đạt GDPR / luật Việt Nam" từ checklist tự động; giả định cần DPO/legal xác nhận: không áp dụng kết luận pháp lý cho T02; đây chỉ là QC hỗ trợ người review.
- Kế hoạch cải tiến: thêm ROI glare (biển số/đèn), metric blockiness ổn định hơn và đánh giá gold set có annotation người thật.

## 10 · Team contribution

**Bảng 2 · Individual contribution evidence** (đối chiếu với `git shortlog -sne --all` và `reports/team_contributions.csv`)

| Học viên | Git author/email | Module / vai trò | Commit SHA / diff chứng minh | Trình bày? |
|---|---|---|---|---|
| Tran Anh Tung | Tung Tran / trananhtung11062004@gmail.com | Integration, data, algorithm, QA, review, report + demo | `2975845` (implementation); `fadc655` (contribution evidence) | Có |

## 11 · References

| URL | Ngày xem | 1–2 dòng ý nghĩa (không chép nguyên văn) |
|---|---|---|
| https://arxiv.org/abs/2104.13395 | 2026-11-15 | ACDC minh hoạ dữ liệu driving trong điều kiện bất lợi; dùng để biện minh báo cáo slice ánh sáng thay vì chỉ tổng số. |
| https://www.iso.org/standard/5259-6 | 2026-11-15 | ISO/IEC TR 5259-6 mô tả visualization cho data quality; contact sheet biến score thành bằng chứng để người review đánh giá. |

---

**Bảng 3 · Checklist chốt khi nộp**

- [ ] Link repo và tag cuối cùng trong README; input mẫu không chứa PII thật.
- [ ] Đúng 1 lệnh run, 1 lệnh evaluate, 1 lệnh tests; không cần download khi chạy.
- [ ] Có baseline/PoC metrics, ≥1 failure case, reviewer evidence, decision log.
- [ ] Có license/source provenance, data splits, seed, offline environment, GT/eval N.
- [ ] Mỗi thành viên có ≥1 commit thực chất và được nêu minh bạch trong bảng trên.
