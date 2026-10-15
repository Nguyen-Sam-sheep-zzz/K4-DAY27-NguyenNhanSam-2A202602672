# Chạy Lab27 trên Windows

Chạy PowerShell tại thư mục gốc repository. Cần Python >=3.11 và `uv`.
Môi trường đã kiểm tra dùng Python 3.12.14, uv 0.13.1; phiên bản dependency nằm trong `uv.lock`.

```powershell
$env:PYTHONUTF8 = '1'
uv sync --locked
Copy-Item .env.example .env   # Chỉ dùng khi CHƯA có .env
```

Nếu `uv` chưa có trong PATH, checkout đã có bản cục bộ ở `.tools\bin\uv.exe`.
Sau khi đồng bộ dependency có thể dùng `.\.venv\Scripts\python.exe -X utf8` thay cho `uv run python`.

## Cấu hình riêng tư

Tự sửa `.env`, không đưa credential vào chat hoặc Git:

```dotenv
LLM_PROVIDER=openai_compatible
OPENAI_API_KEY=<key cục bộ>
OPENAI_BASE_URL=<Base URL đầy đủ do provider cung cấp>
LLM_MODEL=gpt-6-luna
LLM_BASE_URL=
GITHUB_TOKEN=<GitHub PAT cục bộ>
GITHUB_USER=Nguyen-Sam-sheep-zzz
```

`LLM_BASE_URL` có giá trị sẽ được ưu tiên; để trống để dùng `OPENAI_BASE_URL`.
Provider phải hỗ trợ Chat Completions và structured output của `PRAnalysis`.
Tên model được gửi nguyên vẹn cho provider; kết nối DevQuota được kiểm chứng bằng kết quả thực,
không suy ra từ danh mục model của một dịch vụ khác.

`exercises/runtime.py` đọc cấu hình cho CLI/UI. Ở chế độ compatible, key trong `.env`
được ưu tiên hơn key kế thừa từ desktop. Adapter chỉ ánh xạ key sang tên legacy mà
`common.llm` cần trong bộ nhớ của tiến trình; không sửa tiện ích `common/` hay tự ghi key vào file.
Ở chế độ `openrouter`, dùng `OPENROUTER_API_KEY`, model và Base URL riêng của OpenRouter.

Provider/model và nhóm endpoint cục bộ được nạp cùng key; khi cả hai field endpoint không có
trong file mới dùng endpoint kế thừa. Thiếu endpoint compatible sẽ báo lỗi, tránh dùng mặc định
OpenRouter cho credential khác. Các biến khác (ví dụ HITL_DB_PATH) ưu tiên giá trị trong tiến trình.
Khởi động lại Streamlit
sau khi đổi provider/model/Base URL để tránh dùng cấu hình cũ trong tiến trình đang chạy.

## Kiểm tra không đăng comment

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m scripts.offline_demo
uv run python -m scripts.live_preflight
uv run python -m scripts.live_review_preview
```

Hai lệnh cuối gọi mạng và model có tính phí theo tài khoản của bạn. Chúng đọc hai PR mẫu,
lưu kết quả vào `evidence/` và không có bước đăng GitHub. Script live tắt LangSmith tracing.
`live_review_preview` chạy graph bài 1: các terminal chỉ trả trạng thái, kể cả nhánh auto.

## Chạy bài tập và giao diện

```powershell
uv run python -m exercises.exercise_1_confidence --pr https://github.com/VinUni-AI20k/PR-Demo/pull/1
uv run streamlit run app.py --browser.gatherUsageStats false
```

Mở URL do Streamlit hiển thị. Nhập PR → Run review. Bài 2–4 và UI là luồng có đăng
comment thật: nếu confidence >=0.73, có thể đăng ngay; approve ở nhánh giữa và xác nhận
cuối sau escalation trong UI cũng đăng comment. Chỉ dùng các luồng này khi đã được phép
đăng vào PR đích. Comment là thảo luận ở cấp PR, không phải formal GitHub review.

SQLite mặc định: `hitl_audit.db`. Đổi bằng `HITL_DB_PATH`.

```powershell
$env:HITL_DB_PATH = 'hitl_audit.db'
uv run python -m exercises.exercise_4_audit --pr <PR_URL_DA_DUOC_PHEP>
uv run python -m exercises.exercise_4_audit --pr <CUNG_PR_URL> --thread <THREAD_ID>
uv run python -m audit.replay --thread <THREAD_ID>
uv run python -m audit.replay --list
```

CLI bài 3/4 theo luồng đề gốc: Q&A → synthesis → đăng. UI thêm xác nhận cuối.
CLI bài 2/3 dùng MemorySaver nên checkpoint chỉ tồn tại trong tiến trình; bài 4/UI dùng SQLite.
URL `?thread=<THREAD_ID>` của UI phục hồi checkpoint sau refresh hoặc mở trình duyệt mới.

## Xử lý lỗi thường gặp

- `AuthenticationError`: kiểm tra đúng key/provider, field `OPENAI_API_KEY` và Base URL.
- Không import được `exercises`: chạy lại `uv sync --locked` để cài package đã cập nhật.
- PowerShell lỗi Unicode khi Rich in ký hiệu: đặt `PYTHONUTF8=1` hoặc chạy Python với `-X utf8`.
- Lỗi provider sau Q&A: UI tải lại checkpoint và hiện Retry operation; câu trả lời đã lưu được dùng lại.
- Timeout khi đăng: trạng thái `commit_failed`/`auto_commit_failed`; kiểm tra PR trước thao tác tiếp để tránh trùng.
- `audit.replay --list` là tiện ích provided dùng `MAX(risk_level)` trên chuỗi; worst-risk ở danh sách CLI
  có thể sai thứ tự. UI dùng truy vấn CASE đúng thứ tự high > med > low. Timeline từng event vẫn giữ risk gốc.

DB chứa diff và câu trả lời reviewer; giữ cục bộ. `.env`, SQLite, `.venv`, `.tools` và `.cache` được Git bỏ qua.
