# Day27 HITL PR Review Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Thực hiện trong phiên hiện tại theo checkpoint; chỉ dùng subagent nếu người dùng lựa chọn cách đó.

**Goal:** Hoàn thiện đủ 5 bài, chứng minh HITL/routing/audit/khôi phục phiên bằng kiểm thử và demo thật, rồi đóng gói bằng chứng có thể tái lập để tối đa hóa chất lượng bài nộp.

**Architecture:** Giữ 4 bài Python độc lập theo tiến trình học. Dùng graph có audit của bài 4 làm backend cho Streamlit. Checkpoint lưu trạng thái thực thi; bảng `audit_events` lưu quyết định có thể truy vấn. UI khôi phục trạng thái từ checkpoint bằng cùng `thread_id`.

**Tech Stack:** Python >=3.11, uv, LangGraph, langchain-openai, Pydantic, aiosqlite, AsyncSqliteSaver, Streamlit, Rich; kiểm thử hành vi bằng unittest và Streamlit AppTest nếu phiên bản cài đặt hỗ trợ.

**Spec:** `README.md`, đặc biệt các phần Lab assignment, The 5 exercises, How the assignment maps to files, Bonus challenges. Snapshot đọc ngày 15/10/2026, HEAD `25159a3`.

## Tiến độ kiểm chứng ngày 15/10/2026

**Chốt phạm vi bàn giao:** người dùng chọn không đăng bình luận GitHub. Hoàn tất triển khai
và báo cáo cục bộ; không chờ quyền xuất bản. Kiểm chứng POST thật, bonus và nộp bài không
được tính là đã hoàn thành. Báo cáo bàn giao: `docs/LAB27_REPORT.md`.

- Task 1–6: đã triển khai và kiểm thử; shared `common/` + `audit/` được bảo toàn.
- Provider đã chuyển sang `gpt-6-luna` theo yêu cầu; sáu test runtime xác nhận chọn đúng key/endpoint và không fallback OpenRouter khi thiếu endpoint.
- Task 7: đã có report/setup/demo, tám fixture scenarios, ảnh browser, live GitHub/model và hai PR khác nhánh trong mẫu thành công mới nhất. Xem evidence/verification.json cho kết quả test cuối.
- Kết quả live lấy từ các lần thành công riêng, giữ cả lỗi server và sự dao động confidence; PR #1 không ổn định ở nhánh approval.
- Chưa kiểm chứng riêng resilience với câu trả lời reviewer mâu thuẫn; test lỗi post hiện dùng timeout, chưa có case HTTP 403 riêng.
- Bonus và xuất bản GitHub/commit/push/nộp bài chưa thực hiện. Các checkbox chưa đánh dấu ở Task 7 gồm việc tùy chọn hoặc cần quyền xuất bản; trạng thái chi tiết trong LAB27_REPORT.md.

## Global Constraints

- Python `>=3.11` theo `pyproject.toml`.
- `common/`: "shared utilities — provided, don't modify". Không sửa tiện ích chung trong phần triển khai chuẩn; nếu có lỗi chặn thật, ghi bằng chứng và đề xuất ngoại lệ riêng trước khi sửa.
- Dùng `AUTO_APPROVE_THRESHOLD = 0.73`, `ESCALATE_THRESHOLD = 0.58` từ `common/schemas.py`.
- Quy tắc chính xác: `c >= 0.73` tự đăng; `0.58 <= c < 0.73` chờ duyệt; `c < 0.58` hỏi thêm. Không làm tròn confidence trước khi route.
- SQLite là đường triển khai chuẩn được README giải thích rõ. PostgreSQL chỉ là phần mở rộng nếu rubric ngoài repo bắt buộc hoặc còn thời gian sau khi phần chuẩn đạt.
- Không đổi threshold để làm bằng chứng demo trông đúng. Nếu dùng confidence giả lập để kiểm tra nhánh, gắn nhãn fixture và tách khỏi kết quả LLM thật.
- Không ép confidence tăng sau Q&A. Phân tích mới phải phản ánh bằng chứng mới; rủi ro thật có thể vẫn tồn tại.
- Không commit `.env`, token, database/checkpoint thô hoặc log có dữ liệu nhạy cảm. Không yêu cầu người dùng gửi key trong chat.
- Lập kế hoạch không bao gồm quyền đăng comment thật, push, tạo PR hay nộp bài. Khi thực hiện tới những bước đó, cần quyền đã có trong phiên hoặc xác nhận đúng hành động và đích đến.

## 0. Kết quả khảo sát và điểm chưa chắc chắn

Đã đọc toàn bộ README, bốn bài trong `exercises/`, `app.py`, model/schema, GitHub client, LLM factory, database writer và replay.

- Cả bốn bài còn phần chưa triển khai; `app.py` còn invocation, nút duyệt, Q&A và sidebar.
- `streamlit>=1.40.0` đã nằm trong dependencies; không cần thêm lại chỉ vì README còn yêu cầu thao tác đó.
- Chưa có thư mục kiểm thử, báo cáo hoặc bằng chứng chạy trong checkout được khảo sát. Chưa chạy dependency sync hay thử GitHub/LLM.
- Trong shell hiện tại, chưa tìm được `uv`, `python`, `py` trên PATH; đây là bước thiết lập cần xác minh, không phải kết luận máy chưa cài Python.
- Có `.env` cục bộ; chưa đọc giá trị và chưa xác nhận cấu hình có dùng được.
- Không tìm thấy rubric định lượng hoặc hướng dẫn nộp riêng trong repo. Không thể cam kết mức điểm số cụ thể.

Các điểm dễ gây sai khi làm theo mã mẫu:

1. Comment của bài 1 còn ngưỡng `0.85/0.60`; bài 3 còn nhắc 60%. Hằng số đang dùng mới là `0.73/0.58`.
2. Hàm `node_commit` hiện chỉ xử lý approve; chọn edit sẽ rơi vào reject. Auto-edit là bonus được README nêu riêng; cần mô tả hành vi rõ ràng.
3. Bài 5 yêu cầu xem review đã tổng hợp và xác nhận cuối sau escalation, nhưng bài 4 đang nối thẳng `synthesize -> commit`.
4. Tham số CLI `--thread` hiện vẫn đưa input mới vào `ainvoke`; phải kiểm tra checkpoint và resume thật khi khôi phục.
5. `st.session_state` giữ dữ liệu qua rerun, nhưng không đủ cho hard refresh/browser session mới. Cần nạp checkpoint qua sidebar hoặc `thread_id` trên URL.
6. Node chứa `interrupt()` chạy lại từ đầu sau resume; ghi pending audit trước interrupt có thể bị lặp.
7. UI dùng `action.startswith('auto')` sẽ coi `auto_commit_failed` là thành công; phải phân loại trạng thái chính xác.
8. `audit.replay.list_threads()` in bảng Rich và trả `None`; sidebar cần truy vấn dữ liệu tương đương. `MAX(risk_level)` trên chuỗi không tính đúng mức rủi ro cao nhất.
9. GitHub helper đăng comment thảo luận ở PR. Tên node `commit` không có nghĩa git commit, merge PR hay formal GitHub Approve.

## 1. Bản đồ yêu cầu → kết quả nghiệm thu

| Yêu cầu từ README | Thành phần | Bằng chứng cần có |
|---|---|---|
| Đọc PR và đề xuất review có cấu trúc | Bài 1 | Metadata/head SHA, summary, comments, reasoning, confidence hợp lệ |
| Ba nhánh confidence | Bài 1 và graph cuối | Kiểm thử các biên 0/0.5799/0.58/0.72/0.7299/0.73/1; demo từng nhánh |
| Pause/resume có người duyệt | Bài 2 | Chưa duyệt chưa đăng; approve đăng một lần; reject không đăng |
| Hỏi câu hỏi cụ thể rồi phân tích lại | Bài 3 | Câu hỏi bám diff; câu trả lời đi vào prompt; review mới có bằng chứng |
| Audit có cấu trúc và replay | Bài 4 | Event theo thread, đủ trường, reviewer, timing, truy vấn và timeline |
| Khôi phục sau dừng tiến trình | Bài 4 và UI | Mở lại cùng thread, vẫn ở interrupt cũ, không fetch/analyze/post lại ngoài ý muốn |
| Streamlit đủ ba trải nghiệm | Bài 5 | Auto result; approve/reject/edit; escalation form và final confirm |
| Recent sessions | Bài 5 | Danh sách từ DB, mở được phiên cũ, risk hiển thị đúng |
| Bài dễ chấm và tái lập | Tài liệu/bằng chứng | Hướng dẫn PowerShell, lệnh chạy, test log, ảnh UI, link comment đã được phép đăng |

## 2. Bản đồ file và giao diện

### File hiện có cần sửa

- `exercises/exercise_1_confidence.py`: structured analysis, route, graph wiring; sửa comment threshold lỗi thời trong chính file bài tập.
- `exercises/exercise_2_hitl.py`: approval interrupt, MemorySaver, Command resume; chuẩn hóa lựa chọn.
- `exercises/exercise_3_escalation.py`: prompt câu hỏi, escalation, synthesis và edges.
- `exercises/exercise_4_audit.py`: audit đầy đủ, durable resume, trạng thái post, lựa chọn graph phù hợp CLI/UI.
- `app.py`: dùng graph bài 4, UI, khôi phục phiên, recent sessions, thông báo lỗi.
- `pyproject.toml`/`uv.lock`: chỉ thay đổi nếu kiểm thử hoặc runtime thực sự cần dependency bổ sung; Streamlit đã có.
- `.gitignore`: bổ sung SQLite `*.db-wal`, `*.db-shm`, `*.db-journal` và cache/artifact cục bộ nếu phát sinh.

### File dự kiến tạo

- `tests/test_confidence_routing.py`: kiểm tra biên và ba nhánh graph.
- `tests/test_hitl_flow.py`: interrupt/resume, approve/reject/edit, escalation và confirm.
- `tests/test_audit_resume.py`: event, replay, lỗi post, khôi phục bằng graph/checkpointer mới.
- `tests/test_streamlit_app.py`: AppTest cho form, session recovery, error/result cards.
- `docs/LAB27_REPORT.md`: mục tiêu, kiến trúc, quyết định, kết quả và giới hạn.
- `docs/DEMO_SCRIPT.md`: thao tác demo 5–7 phút và dữ liệu cần chuẩn bị.
- `evidence/README.md`: mục lục bằng chứng, phân biệt fixture với live.
- `evidence/screenshots/`, `evidence/logs/`: chỉ chứa kết quả được rà soát và ảnh đã che thông tin nhạy cảm.
- `evidence/scenario_matrix.csv`: scenario, input type, thread, branch, human action, final action, kết quả và đường dẫn evidence.

### Giao diện giữ thống nhất

```python
# Có sẵn trong bài 4, giữ tương thích với caller hiện tại.
async def audit(state, entry: AuditEntry) -> None: ...

# Dự kiến bổ sung keyword để UI đòi xác nhận cuối mà CLI bài 4 vẫn theo đề gốc.
def build_graph(checkpointer, *, confirm_after_escalation: bool = False): ...

# Có sẵn trong app.py; fresh input và resume chỉ dùng đúng một nhánh mỗi lần gọi.
async def run_graph(pr_url: str, thread_id: str, resume_value=None): ...
```

Các dấu `...` trên chỉ mô tả chữ ký, không phải nội dung implementation.

## Task 1 — Thiết lập runtime và baseline (20–40 phút)

**Files:** `.env` cục bộ nếu cần; tài liệu hướng dẫn; không sửa `common/`.

**Consumes:** README, cấu hình provider hiện có. **Produces:** runtime có thể import dependency và chạy bài theo module.

- [x] Xác minh Python >=3.11 và uv ở vị trí cài thật nếu PATH chưa có; dùng đường dẫn tuyệt đối khi cần. Không cài trùng interpreter trước khi kiểm tra.
- [x] Chạy `uv sync --locked` khi đã tìm được uv. Ghi phiên bản Python/uv và kết quả dependency resolution.
- [x] Kiểm tra biến `OPENROUTER_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `GITHUB_TOKEN`, `GITHUB_USER` bằng trạng thái set/missing; không in giá trị credential. `GITHUB_USER` được bài 4 dùng nhưng chưa có trong `.env.example`.
- [x] Giữ model/base URL cấu hình được bằng biến môi trường. Xác minh provider hỗ trợ structured output của `PRAnalysis` trước khi demo live.
- [x] Smoke import LangGraph/Streamlit/aiosqlite. Dùng `uv run python -m exercises.exercise_1_confidence --help`; nếu cần hỗ trợ lệnh chạy file trực tiếp trong README, kiểm tra riêng import path thay vì giả định.
- [x] Ghi checksum/trạng thái các tiện ích provided và baseline chưa triển khai để so sánh cuối bài.

**Đạt khi:** dependency/import/CLI help chạy; hoặc có lỗi môi trường cụ thể được ghi nhận. Không coi có `.env` là kết nối live thành công.

## Task 2 — Exercise 1: phân tích và routing (25–40 phút)

**Files:** bài 1; `tests/test_confidence_routing.py`.

**Consumes:** `get_llm`, `PRAnalysis`, hai threshold constants. **Produces:** `node_analyze` trả `analysis`, `node_route` trả `decision`, `build_graph()` chạy đủ ba terminal nodes.

- [x] Viết test hành vi trước: mock fetch/LLM, trả các confidence cụ thể, kiểm tra decision và terminal action.
- [x] Implement `get_llm().with_structured_output(PRAnalysis).invoke(...)`; prompt yêu cầu phân tích bám diff, giải thích confidence và chỉ rõ thiếu ngữ cảnh.
- [x] Implement route bằng constants, không bằng số trong comment cũ.
- [x] Wire `START -> fetch_pr -> analyze -> route`, ba conditional edges và terminal -> END.
- [x] Chạy test:

```powershell
uv run python -m unittest discover -s tests -p test_confidence_routing.py -v
```

- [x] Chuẩn bị live read-only của PR-Demo #1/#2, ghi confidence thực tế và model. Kỳ vọng khác nhánh theo README nhưng không ép kết quả LLM bằng PR number.

**Đạt khi:** đủ ba nhánh và biên chính xác bằng test; kết quả LLM thật được báo riêng, nếu đã chạy.

## Task 3 — Exercise 2: HITL thật và lựa chọn rõ ràng (30–45 phút)

**Files:** bài 2; `tests/test_hitl_flow.py`.

**Consumes:** `PRAnalysis`, `ReviewState`, MemorySaver. **Produces:** approval payload và trạng thái choice/feedback được resume bằng cùng thread.

- [x] Test graph dừng trước post, payload có summary/reasoning/comments/diff, chưa có human response thì mock GitHub chưa bị gọi.
- [x] Implement `interrupt` với `kind='approval_request'`, compile MemorySaver, resume bằng `Command(resume=answer)` và đúng config ban đầu.
- [x] Test approve gọi post đúng một lần; reject không gọi; input choice lạ không được đăng.
- [x] Chốt hành vi edit cho bản chuẩn: nhận feedback, hiện review sửa để người dùng xem rồi approve. Có thể sửa thủ công nội dung review trong UI; LLM auto-edit là bonus riêng.
- [x] Không để edit bị báo là reject khi người dùng chưa từ chối. Nếu bài 2 giữ mức tối thiểu, ghi rõ edit chưa thực thi và hoàn thiện ở graph/UI cuối.
- [x] Chạy test:

```powershell
uv run python -m unittest discover -s tests -p test_hitl_flow.py -v
```

**Đạt khi:** chứng minh pause/resume thật; reject không post; chỉ publish nội dung đã được chấp thuận theo luồng.

## Task 4 — Exercise 3: escalation và synthesis (30–45 phút)

**Files:** bài 3; bổ sung test trong `tests/test_hitl_flow.py`.

**Consumes:** initial analysis + diff. **Produces:** `escalation_answers`, refined `analysis`, comment phản ánh Q&A.

- [x] Test confidence thấp tạo escalation interrupt; fallback câu hỏi hoạt động khi LLM trả danh sách rỗng.
- [x] Prompt 2–4 câu hỏi cụ thể về file/đoạn thay đổi, dùng threshold 0.58; sửa comment 60% lỗi thời.
- [x] Implement payload có PR URL, confidence/reasoning, summary, risk factors và questions.
- [x] Implement synthesis từ diff + initial analysis + Q&A. Test prompt thật sự chứa cả ba nguồn; không chỉ kiểm tra có gọi LLM.
- [x] Wire `escalate -> synthesize -> commit` đúng bài CLI. Không giả định refined confidence luôn cao hơn hoặc câu trả lời của reviewer tự động xóa issue.
- [ ] Test Q&A rỗng/thiếu, lỗi provider và reviewer feedback mâu thuẫn với diff; không tự ghi kết quả thành công khi synthesis thất bại.

**Đạt khi:** review mới dùng đúng câu trả lời và không đăng review cũ do quên cập nhật state.

## Task 5 — Exercise 4: audit, crash resume và kết quả post (45–75 phút)

**Files:** bài 4; `tests/test_audit_resume.py`; `.gitignore` khi cần.

**Consumes:** `AuditEntry`, `write_audit_event`, `replay_events`, `AsyncSqliteSaver`. **Produces:** graph có audit theo thread và khả năng khôi phục đã kiểm tra.

- [x] Implement `audit()` bằng await `write_audit_event` với `thread_id`, `pr_url` từ state.
- [x] Ghi fetch/analyze/route/auto/commit/synthesize; pending và response cho mỗi tương tác người dùng. Dùng confidence mới ở synthesize, reviewer sau response, timing không âm.
- [x] Chọn thiết kế tránh trùng pending event: tách node ghi request sang trước node chứa interrupt, rồi ghi response sau resume. Lưu giải thích rằng đây vẫn là hai sự kiện của cùng tương tác. Phân biệt request duyệt thường với final confirm sau escalation.
- [x] Không bắt chung `Exception` quanh interrupt rồi coi GraphInterrupt là lỗi. Side effect đăng comment nằm ở node sau interrupt.
- [x] Dùng `aget_state(cfg)` để nhận diện thread mới, đang chờ, hoàn tất. `--thread` đọc lại state/interrupt cũ thay vì chạy fetch/analyze từ đầu. Kiểm tra PR URL của checkpoint khớp yêu cầu hiện tại.
- [x] Cho graph thêm lựa chọn `confirm_after_escalation=True` để UI có `synthesize -> final approval interrupt -> commit`. Khi reject xác nhận cuối, dù state đã có `escalation_answers`, tuyệt đối không post.
- [x] Chuẩn hóa action: `committed`, `auto_committed`, `rejected`, `commit_failed`, `auto_commit_failed` phải được UI/test phân biệt rõ. Audit thất bại post không ghi như đăng thành công.
- [x] Dùng tempfile DB và fake post để test: tạo graph A, pause, đóng connection; tạo graph B với cùng DB/thread, resume và kiểm tra không fetch/LLM lại. Đây là test khôi phục bằng runtime mới.
- [x] Kiểm tra audit order/fields và không trùng pending sau resume; chạy replay cho ít nhất một phiên có HITL và một phiên escalation.
- [ ] Test GitHub post lỗi 403/timeout giả lập. Phân biệt chưa đăng với trường hợp không rõ server đã nhận; không retry mù gây duplicate.
- [x] Ghi rõ giới hạn: downstream commit giúp tránh replay bình thường, chưa tự đảm bảo exactly-once nếu tiến trình chết sau GitHub nhận POST nhưng trước lưu checkpoint. Không tuyên bố giải quyết cửa sổ này nếu chưa có cơ chế reconciliation và test.

```powershell
uv run python -m unittest discover -s tests -p test_audit_resume.py -v
uv run python -m audit.replay --list
```

**Đạt khi:** full timeline truy vấn được; khôi phục giữ nguyên interrupt; reject/failed không bị ghi nhận là published.

## Task 6 — Exercise 5: Streamlit đủ ba luồng (60–90 phút)

**Files:** `app.py`; `tests/test_streamlit_app.py`.

**Consumes:** graph bài 4 với SQLite saver, `AuditEntry` history. **Produces:** UI hoàn chỉnh và khôi phục được phiên.

- [x] Import `build_graph` bài 4, dùng tùy chọn final confirm cho UI. Giữ saver trong async context trong mỗi lần thao tác để không tái sử dụng connection đã đóng qua event loop mới.
- [x] Implement start input và resume riêng biệt; giữ cùng `thread_id`, xử lý interrupt kế tiếp tới final.
- [x] Approval card: confidence, reasoning, comments, diff, Approve/Reject/Edit. Edit có ô sửa nội dung, preview và xác nhận; không giả vờ edit đã thực thi khi chỉ nhận feedback.
- [x] Escalation card: risk factors nổi bật, form từng câu hỏi và kiểm tra câu trả lời trước resume. Sau synthesize hiện review mới và final confirm theo README.
- [x] Auto result: summary, confidence, action và link tới PR comments. Helper hiện không trả comment URL/id; nếu chưa mở rộng có kiểm soát thì chỉ ghi link PR, không tạo URL comment giả.
- [x] Recent sessions: truy vấn dữ liệu tương đương `list_threads`, render thành table/selectbox. Xếp risk bằng `CASE high=3, med=2, low=1` thay vì `MAX` chuỗi.
- [x] Nạp phiên cũ bằng `aget_state`; session state chỉ làm cache UI. Gắn thread vào query params để hard refresh khôi phục được. Thread hoàn tất chỉ hiển thị kết quả, không invoke fresh input.
- [x] Không coi mọi action bắt đầu bằng `auto` là thành công. Bật success card chỉ với tập trạng thái thành công đã định nghĩa.
- [x] Test bằng AppTest cho nút/form/result/error, mock network. Browser smoke riêng cho layout và hard refresh/recent session.

```powershell
uv run python -m unittest discover -s tests -p test_streamlit_app.py -v
uv run streamlit run app.py
```

**Đạt khi:** reviewer thao tác từ trình duyệt cả ba nhánh, edit rõ nghĩa, escalation có xác nhận cuối, refresh không đăng lại.

## Task 7 — Kiểm chứng end-to-end, bonus và bài nộp (45–90 phút)

**Files:** báo cáo, demo script và evidence như bản đồ file.

- [ ] Chạy toàn bộ kiểm thử một lần sau khi hoàn thiện; ghi lệnh, timestamp, phiên bản và kết quả thực tế, không tự đặt số lượng pass dự kiến thành thành tích.

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q exercises common audit app.py
git diff --check
```

- [ ] Chạy ma trận dưới đây, dùng fixture để bảo đảm phủ nhánh và live riêng để chứng minh tích hợp. Chỉ đăng GitHub thật khi có quyền cho đúng PR; đề nghị dùng PR của cá nhân hoặc PR-Demo được cho phép, tối thiểu comment để tránh spam.
- [ ] Lưu thread ID, PR head SHA, model ID, confidence thực tế, lựa chọn người dùng, final action, event replay, ảnh UI và link comment khi có.
- [ ] Viết báo cáo tiếng Việt: giải quyết vấn đề gì, graph, policy, audit vs checkpoint, xử lý lỗi, test và live evidence, SQLite/PostgreSQL, hạn chế confidence tự báo.
- [ ] Ghi hướng dẫn chạy PowerShell và demo 5–7 phút: routing -> approve/reject -> escalation/Q&A/final confirm -> crash recovery -> audit replay.
- [ ] Ưu tiên bonus sau phần chuẩn: (1) time-travel bằng `aget_state_history` với fake post; (2) thống kê calibration có số mẫu rõ ràng; (3) LLM auto-edit có preview. Multi-reviewer fan-out để cuối vì tăng độ phức tạp.
- [ ] Calibration dùng đúng cột audit và đơn vị phiên: bảng không có cột `human_choice`, dùng `decision`; tránh tính nhiều event một phiên thành nhiều đánh giá độc lập. Không gọi tỷ lệ approve là accuracy đã được kiểm chứng.
- [ ] Time-travel demo không tự post lại vào GitHub. Kết quả replay audit và tái thực thi checkpoint là hai việc khác nhau.
- [ ] Đối chiếu mọi requirement trong bảng mục 1 với evidence. Rà secret và file generated trước khi stage. Commit/push/nộp bài chỉ theo quyền và quy định nộp đã xác nhận.

### Ma trận nghiệm thu tối thiểu

| Case | Nguồn dữ liệu | Kỳ vọng |
|---|---|---|
| Boundary confidence | Fixture: 0, 0.5799, 0.58, 0.72, 0.7299, 0.73, 1 | Route đúng hằng số, không round |
| Auto branch | Fixture; live nếu tìm được PR phù hợp | Không interrupt, post một lần, trạng thái đúng |
| Approve | Fixture + live được phép | Pause trước post, approve mới post |
| Reject | Fixture; có thể live vì không post | Không gọi GitHub POST |
| Edit | Fixture + UI | Sửa/preview/confirm, nội dung sửa được dùng |
| Escalate | Fixture + live PR phù hợp | Câu hỏi cụ thể, Q&A vào synthesis, final confirm ở UI |
| Reject final confirm | Fixture | Đã có Q&A vẫn không post |
| Resume mới process | Temp SQLite + graph instance mới | Cùng thread, đúng interrupt, không analyze lại |
| UI hard refresh | Browser + checkpoint | Khôi phục trạng thái từ DB/thread URL |
| API/provider failure | Mock 403/timeout/structured output lỗi | Không success giả, có phản hồi và audit phù hợp |
| Replay | DB các phiên test/demo | Đủ request/response/decision và thứ tự hợp lý |

## 3. Thứ tự ưu tiên và cách báo cáo tiến độ

**P0 — bắt buộc:** Task 1–6 và bằng chứng tối thiểu của Task 7. Không làm bonus để bù việc thiếu UI hoặc thiếu crash resume.

**P1 — tăng chất lượng rõ nhất:** test hành vi/biên, chống success giả, audit nhất quán, demo live gắn provenance, tài liệu dễ tái lập.

**P2 — bonus sau khi ổn định:** time-travel, calibration, LLM auto-edit; PostgreSQL/multi-reviewer chỉ khi rubric và thời gian hợp lý.

Ước lượng tập trung khoảng **4–7 giờ** tùy runtime/provider và mức độ evidence; lab ghi 2 giờ phù hợp đường tối thiểu hơn là toàn bộ kiểm chứng và bonus ở đây.

Sau mỗi task, báo ngắn theo mẫu: **Đã sửa gì — Đã kiểm tra gì — Kết quả thật — Còn thiếu gì — Bước tiếp theo.** Phân biệt rõ planned / implemented / local-tested / live-verified / committed / pushed / submitted.

## 4. Tự rà soát kế hoạch

- Đủ cả 5 bài dù đoạn mở đầu README nhắc 4 bài.
- Mọi deliverable trong repo đã có task và evidence dự kiến.
- Không đặt trọng số/điểm số không có trong rubric.
- Không sửa tiện ích provided như lựa chọn mặc định.
- Không thêm lại Streamlit khi dependency đã có.
- Đã xử lý chênh lệch escalation CLI và final confirm UI.
- Đã phân biệt route theo confidence với đánh giá risk thực tế; confidence của model không phải bảo đảm an toàn hay accuracy.
- Không thực hiện code, gọi LLM, đăng comment, commit hay push trong lượt lập kế hoạch này.
