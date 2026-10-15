# Demo 5–7 phút

## Chuẩn bị

Chạy `uv run python -m scripts.offline_demo`, sau đó mở `evidence/offline_demo.json`
để lấy thread ID mới và `evidence/scenario_matrix.csv` để xem đủ tám tình huống.
Tất cả outcome của script này dùng fixture, không gọi GitHub/LLM thật.

```powershell
$env:PYTHONUTF8 = '1'
$env:HITL_DB_PATH = '.cache/demo.db'
uv run streamlit run app.py --browser.gatherUsageStats false
```

Các fixture pending chỉ dùng để xem layout và refresh; không bấm Approve/Submit answers
trong phiên browser này vì script tạo fixture không còn patch network sau khi thoát.
Demo thao tác có kiểm soát dùng AppTest; demo live tương tác dùng PR được phép đăng và DB riêng.

## Trình bày

| Thời gian | Nội dung | Bằng chứng |
|---|---|---|
| 0:00–0:45 | Bài toán: tự động phân luồng, hỏi người khi thiếu ngữ cảnh, ghi audit | Báo cáo, policy 0.73/0.58 |
| 0:45–1:30 | Chạy graph bài 1 với dữ liệu thật, chỉ xem trước; chỉ rõ head SHA/model/confidence | `live_review_preview.json`, `previews/` |
| 1:30–2:30 | Mở `?thread=<preview_threads.approval>`; xem diff, reasoning, review text; refresh vẫn đúng phiên | Browser + fixture banner |
| 2:30–3:15 | Cho thấy approve/reject/edit: edit chưa đăng, phải approve lần hai; reject không đăng | `test_streamlit_app.py` và audit fixture |
| 3:15–4:15 | Mở thread escalation; xem risk + câu hỏi; trình bày Q&A → synthesis → final confirm | Ảnh UI + test escalation/reject final |
| 4:15–5:15 | Chứng minh pause/approve/inspect qua ba tiến trình riêng biệt | `test_process_recovery.py`, log test |
| 5:15–6:15 | Replay timeline: pending request → response → quyết định; lỗi post không thành success | JSON audit + lệnh bên dưới |
| 6:15–7:00 | Nêu giới hạn confidence, exactly-once và trạng thái live/publish | Báo cáo và evidence index |

```powershell
# Chọn một thread trong offline_demo.json, giữ HITL_DB_PATH=.cache/demo.db
uv run python -m audit.replay --thread <THREAD_ID>
uv run python -m unittest tests.test_process_recovery -v
uv run python -m unittest tests.test_streamlit_app -v
```

Khi cần demo đăng thật: dùng `hitl_audit.db` riêng, kiểm tra quyền và PR đích trước khi
chạy bài 2–4/UI. Sau khi đăng, ghi link comment thật; không dùng link PR để giả làm link comment.
Các bản review trong `evidence/previews/` là nội dung có thể xem xét trước khi cho phép xuất bản.

## Câu trả lời bảo vệ bài

- **Audit khác checkpoint thế nào?** Audit là cột SQL giải thích ai/quyết định/lý do/thời gian;
  checkpoint lưu state/task để thực thi tiếp. Cả hai dùng SQLite nhưng mục đích khác nhau.
- **Vì sao không ghi request trước interrupt ngay trong cùng node?** Node có interrupt chạy lại
  từ đầu khi resume. Tách request node ở trước giúp tránh lặp pending event trong resume thông thường.
- **Refresh có review lại không?** URL giữ thread, `aget_state` tải checkpoint; completed session
  chỉ được hiển thị, không invoke input mới.
- **Confidence có phải accuracy không?** Không; đó là tự đánh giá của model và cần calibration độc lập.
  Một model có thể rất chắc mình tìm đúng lỗi nhưng vẫn thiếu ngữ cảnh cho toàn bộ review.
- **Đã exactly-once chưa?** Chưa. Có thể trùng nếu GitHub nhận POST rồi process chết trước checkpoint.
  Bản này không tự retry timeout và không tuyên bố khắc phục cửa sổ đó.
- **Bonus nào đã làm?** Chưa triển khai riêng time-travel/fan-out/calibration thống kê/LLM auto-edit.
  Manual edit, durable recovery và kiểm thử lỗi là phần hoàn thiện yêu cầu chính.
