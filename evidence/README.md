# Bằng chứng Lab27

Đọc `docs/LAB27_REPORT.md` để xem đối chiếu yêu cầu và giới hạn. Không có credential trong evidence.

| File | Chứng minh | Giới hạn |
|---|---|---|
| `verification.json`, `logs/full-tests.log` | Kết quả kiểm tra cuối và lệnh test | Không suy ra điểm chấm ẩn |
| `provided_files_sha256.json` | SHA256 các file provided để đối chiếu bảo toàn | Hash riêng không chứng minh hành vi đúng |
| `offline_demo.json`, `scenario_matrix.csv` | Tám tình huống chạy graph/audit/SQLite thật | Fetch/LLM/post được thay bằng fixture |
| `logs/fixture-*-audit.json` | Timeline request/response/route/commit của từng case | `committed` trong fixture là post giả lập |
| `screenshots/fixture-approval.png` | UI approval có review và edit | Dữ liệu fixture |
| `screenshots/fixture-escalation.png` | UI escalation có risk và câu hỏi | Dữ liệu fixture |
| `live_preflight.json` | GitHub identity + fetch PR + structured output synthetic qua model thật | Chưa kiểm chứng đăng comment |
| `live_review_before_prompt_calibration.json` | Lần live đầu: tự tin cao dù còn thiếu ngữ cảnh | Giữ để giải thích thay đổi prompt, không dùng làm kết quả cuối |
| `live_review_preview.json` | Phân tích/routing hai PR thật, head SHA, model, confidence, reasoning | Graph bài 1 chỉ xem trước, không publish |
| `live_review_transient_failure.json`, `live_review_retry_failure.json`, `live_pr2_diagnostic.json` | Lịch sử lỗi server PR #2 và lần thử lại thành công | JSON tổng hợp lấy lần thành công gần nhất của từng PR, không phải cùng một lượt chạy |
| `previews/pr-1-review.md`, `previews/pr-2-review.md` | Nội dung review cụ thể để kiểm tra trước xuất bản | Chưa đăng GitHub |

Ngày giờ trong JSON dùng UTC. `execution_time_ms` trong audit là thời gian xử lý node;
ở response node không đại diện toàn bộ thời gian con người suy nghĩ.

Tái lập: `python -m unittest discover -s tests -v`, `python -m scripts.offline_demo`,
`python -m scripts.live_preflight`, `python -m scripts.live_review_preview`.
Chạy lại các script sẽ thay bằng chứng hiện tại và tạo thread fixture mới. Hai lệnh live
cần cấu hình riêng tư và mạng; confidence có thể thay đổi giữa các lần chạy.

Trạng thái xuất bản: chưa đăng review comment, chưa commit/push, chưa nộp VLearn.
Người dùng đã chọn không đăng bình luận GitHub ngày 15/10/2026. Các preview được giữ
cục bộ; không có bước chờ chấp thuận xuất bản trong lần bàn giao này.
