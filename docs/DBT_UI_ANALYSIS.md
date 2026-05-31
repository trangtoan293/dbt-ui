# dbt-ui — Phân tích toàn diện

> Ngày: 2026-05-30  
> Phiên bản codebase được phân tích: branch `claude/init-9Li8C`

---

## Mục lục

1. [Multi-User Support](#1-multi-user-support)
2. [Bảo mật (Security)](#2-bảo-mật-security)
3. [So sánh với dbt-studio](#3-so-sánh-với-dbt-studio)
4. [So sánh với dbt Cloud — Tính năng còn thiếu](#4-so-sánh-với-dbt-cloud--tính-năng-còn-thiếu)
5. [Roadmap gợi ý](#5-roadmap-gợi-ý)

---

## 1. Multi-User Support

### Kết luận: Hỗ trợ một phần — không phải multi-tenant thực sự

App được thiết kế cho **single-user hoặc team nhỏ tin tưởng nhau** dùng chung 1 tài khoản. Không có user isolation.

### Cơ chế đã có

| Cơ chế | File | Mô tả |
|--------|------|-------|
| Per-worktree lock | `backend/utils/operation_lock.py` | Chỉ 1 lệnh dbt chạy cùng lúc trên 1 project path |
| Polling sync | `frontend/src/components/main/MainLayout.tsx` | Poll `/api/dbt-operation-status` mỗi 2s, phát hiện operation của user khác |
| 3-way file merge | `backend/utils/merge_utils.py` | Phát hiện và merge conflict khi 2 user cùng sửa 1 file |

### Lỗ hổng nghiêm trọng

**1. Global shared state — User A thấy output của User B**

```python
# backend/routes/dbt_routes.py, line 23
dbt_command_status: Dict[str, Dict[str, any]] = {}
```

Dict này là global, key chỉ là `project_path`. Nếu User A chạy `dbt compile` trên `/repos/project1`, User B gọi cùng endpoint với cùng path sẽ nhận được **toàn bộ output, SQL, error messages** của User A — có thể chứa thông tin nhạy cảm (database names, credentials trong stack trace).

**2. Không có user context/session**

Không có `user_id`, session token, hay định danh nào gắn với từng request. Auth system (`auth.py`) chỉ có 1 cặp username/password chung — không phân biệt được ai đang gọi.

**3. Kịch bản 2 user cùng project**

| Tình huống | Kết quả |
|-----------|---------|
| Khác project path | ✅ Hoạt động bình thường |
| Cùng project path, khác thời điểm | ⚠️ User sau đọc được output của user trước |
| Cùng project path, cùng lúc | ✅ User sau nhận 409 Conflict (lock hoạt động đúng) |

### Cần làm để hỗ trợ multi-user thực sự

- Implement JWT hoặc OAuth (GitHub/Google) — thay HTTP Basic dùng chung
- Namespace `dbt_command_status` theo `(user_id, path)` thay vì chỉ `path`
- Filter tất cả API response theo user context

---

## 2. Bảo mật (Security)

### Tốt ✅

| Hạng mục | Chi tiết |
|---------|---------|
| **Path traversal** | `file_routes.py` dùng `path.resolve().relative_to(project_path.resolve())` đúng cách, áp dụng nhất quán |
| **Command injection** | Input validation rất tốt (`input_validation.py`) — whitelist regex cho dbt selectors, branch names; subprocess dùng list-based, không `shell=True` |
| **Git credentials** | HttpOnly cookie + GIT_ASKPASS — credentials không lộ trong process list, không accessible qua JS |
| **Timing attack** | `secrets.compare_digest()` cho HTTP Basic auth |

### Rủi ro cần xử lý ⚠️

| Vấn đề | Mức độ | Chi tiết |
|--------|--------|---------|
| **Auth tắt mặc định** | 🔴 CAO | Nếu không set `DBT_UI__BACKEND_USER/PASSWORD`, toàn bộ API không cần auth |
| **Shared global state** | 🔴 CAO | `dbt_command_status` không có user isolation — xem mục 1 |
| **Không có session management** | 🔴 CAO | Không có user tracking; endpoints không biết ai đang gọi |
| **CORS quá lỏng** | 🟠 TRUNG | `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True` — CSRF risk trên production |
| **Cookie không `secure=True`** | 🟠 TRUNG | Git credentials gửi qua HTTP không mã hóa trong dev |
| **Env var exposure** | 🟠 TRUNG | `/api/scan-env-vars` trả về giá trị thực của env vars về frontend |
| **Không có rate limiting** | 🟠 TRUNG | Có thể spam compile requests để DoS |
| **Không giới hạn file size** | 🟡 THẤP | Read file không check size, có thể OOM với file lớn |

### Khuyến nghị theo thứ tự ưu tiên

1. Bắt buộc authentication — xóa bỏ "optional auth"
2. Fix shared state dict — key theo `(user_id, path)`
3. Thêm rate limiting per-user (vd: 10 compile requests/phút)
4. Giới hạn CORS — chỉ cho phép methods/headers cần thiết
5. Bật `secure=True` trên cookies khi deploy production (HTTPS)
6. Thêm audit log — ai gọi endpoint nào, lúc nào
7. Giới hạn file size trước khi đọc vào memory

---

## 3. So sánh với dbt-studio

> Repository: [rosettadb/dbt-studio](https://github.com/rosettadb/dbt-studio)

### Tổng quan dbt-studio

dbt-studio là **desktop app (Electron)**, single-user, local-first. Hai tool phục vụ use case hoàn toàn khác nhau.

| Đặc điểm | dbt-ui | dbt-studio |
|----------|--------|------------|
| Deployment | Web-based, self-hosted | Desktop (Electron) |
| User model | Team (web browser) | Single-user (local) |
| Tech stack | React + FastAPI | TypeScript + Electron |
| AI features | ❌ Không có | ✅ AI model generation |
| Git integration | ✅ Đầy đủ | ✅ Có |
| Lineage DAG | ✅ Có | Không rõ |
| Built-in Python runtime | ❌ Cần cài venv | ✅ Bundled |

### dbt-ui có, dbt-studio thiếu

- Web-based → deploy tập trung, team dùng chung
- Git operations UI đầy đủ (branch, commit, push/pull, conflict resolution)
- Lineage DAG visualization (ReactFlow)
- Virtual environment management

### dbt-studio có, dbt-ui còn thiếu

| Tính năng | Mô tả |
|-----------|-------|
| **AI model generation** | Tạo staging/intermediate/business model từ schema hoặc mô tả tự nhiên |
| **Auto-scaffold staging layer** | 1-click generate `sources.yml` + staging SQL từ raw tables |
| **SQL formatter tích hợp** | Format trực tiếp trong editor |
| **Built-in Python runtime** | Không cần cài dbt ngoài |

---

## 4. So sánh với dbt Cloud — Tính năng còn thiếu

### Trạng thái hiện tại của dbt-ui

| Tính năng | Trạng thái | Ghi chú |
|-----------|-----------|---------|
| SQL editing cơ bản | ✅ Tốt | Monaco Editor với syntax highlighting cho SQL/YAML/Python/Markdown |
| Compiled SQL preview | ✅ Tốt | 3 chế độ: Text / Rendered / Table |
| Data preview (dbt show) | ✅ Tốt | Top 10 rows, cache, confirmation dialog |
| File CRUD + Move | ✅ Tốt | Create, rename, delete, restore, drag-drop |
| Lineage DAG | ✅ Partial | Model-level, depth control, max 200 nodes |
| Metadata sidebar | ✅ Partial | Name, type, description, columns — thiếu test details |
| Git integration | ✅ Tốt | Clone, branch, stage, commit, push/pull, conflict UI |
| dbt commands | ✅ Tốt | compile, run, test, seed với selector và target |
| Multi-tab editing | ❌ Không có | Chỉ mở được 1 file tại một thời điểm |
| SQL autocomplete | ❌ Không có | Không có IntelliSense, không gợi ý `ref()`, `source()` |
| SQL linting/formatting | ❌ Không có | Không có sqlfluff, không có sqlfmt |
| Find & replace toàn project | ❌ Không có | Chỉ find trong 1 file |
| dbt docs viewer | ❌ Không có | Không có `dbt docs generate` + serve |
| Column-level lineage | ❌ Không có | Chỉ model-level |
| Test result visualization | ❌ Không có | Chỉ hiện raw log |
| Git diff viewer | ❌ Không có | Không xem được thay đổi trước khi commit |
| Job scheduling | ❌ Không có | Không có scheduler, không có run history |
| Source freshness | ❌ Không có | Không expose `dbt source freshness` |
| AI assistant | ❌ Không có | dbt Cloud có Copilot |
| RBAC / per-user permissions | ❌ Không có | Chỉ có 1 tài khoản global |

---

### Chi tiết các tính năng cần bổ sung

#### 🔴 Ưu tiên cao — ảnh hưởng trực tiếp đến năng suất hàng ngày

**Multi-tab file editing**

Khi viết SQL phức tạp, developer cần tham chiếu nhiều file cùng lúc (model + source + macro). dbt Cloud có tab system với chấm xanh cho file chưa save. Đây là tính năng bị thiếu có tác động lớn nhất.

**SQL / Jinja autocomplete**

Monaco Editor hỗ trợ completions API nhưng chưa được cấu hình. Cần thêm:
- Autocomplete cho `ref()`, `source()`, `config()` — đọc từ `manifest.json`
- Gợi ý tên model khi gõ `ref('`
- Jinja snippets: `{% macro %}`, `{% if %}`, `{{ var() }}`, `{{ env_var() }}`
- Autocomplete tên column dựa trên compiled SQL

**SQL formatting (sqlfmt / sqlfluff)**

Nút "Format" hoặc format-on-save: backend gọi `sqlfluff format` hoặc `sqlfmt`, trả về nội dung đã format. Tôn trọng file `.sqlfluff` trong project. Đây là tính năng dbt developer dùng hàng ngày.

**Find & Replace toàn project**

Tìm tất cả nơi `ref('model_name')` được dùng, rename column name trên nhiều file. Thiết yếu khi refactor. Backend có thể dùng `grep` recursive, frontend hiển thị kết quả dạng list có thể click-through.

---

#### 🟠 Ưu tiên trung bình — tăng chất lượng đáng kể

**SQL linting inline**

Tích hợp `sqlfluff lint` output vào Monaco diagnostics (gạch đỏ/vàng dưới code). Backend chạy linting async sau mỗi lần save hoặc theo trigger, trả kết quả dạng Monaco `IMarkerData`. Tương đương "Problems tab" của dbt Cloud.

**dbt docs viewer tích hợp**

Nút "Generate Docs" → chạy `dbt docs generate` → parse `catalog.json` và `manifest.json` → hiển thị documentation ngay trong UI. Hiện tại metadata sidebar đã có description và column info nhưng chưa có:
- Full markdown rendering cho descriptions
- Model-level doc tổng hợp có thể search
- Column data types từ `catalog.json`

**Column-level lineage**

Manifest.json đã có đủ thông tin trong `node.columns` và `node.depends_on`. Cần parse và visualize để thấy cột nào từ source nào, qua model nào, ra column nào ở mart. dbt Cloud gọi đây là tính năng flagship của dbt Explorer.

**Test result visualization**

Parse JSON output của `dbt test --store-failures` để hiển thị:
- Table: model name | test name | status (pass/fail) | số rows failed
- Badge trên file tree: model nào đang có test fail
- Click vào failed test → xem SQL query tạo ra failure

**Git diff viewer trước khi commit**

Hiển thị Monaco `DiffEditor` (before/after) khi user chuẩn bị stage/commit file. Giúp review thay đổi một lần nữa trước khi push lên remote.

---

#### 🟡 Ưu tiên thấp hơn — nice-to-have cho team lớn

**Job scheduling + run history**

- Schedule `dbt run` định kỳ (cron syntax)
- Lưu lịch sử run: thời gian, selector, kết quả, thời lượng từng model
- Dashboard xem model nào chậm nhất (model timing)

**Source freshness monitoring**

`dbt source freshness` đã được dbt hỗ trợ nhưng dbt-ui chưa expose. Hiển thị source nào stale, source nào fresh, với timestamp cuối cùng. Quan trọng cho data quality monitoring.

**Project health dashboard**

Tương tự "Project Recommendations" của dbt Cloud:
- % models có description
- % models có ít nhất 1 test
- Models không có owner/tag
- Models chưa được reference ở đâu (dead code)

**Keyboard shortcuts + command palette**

dbt Cloud có command palette (Cmd+K). Cần ít nhất:
- `Ctrl+S` — Save
- `Ctrl+Enter` — Compile current model
- `Ctrl+Shift+F` — Format document
- `Ctrl+Shift+R` — Run current model
- `Ctrl+P` — Quick open file

**Split pane editor**

Mở 2 file side-by-side — dùng khi tham chiếu model này khi viết model kia, hoặc so sánh compiled SQL với source SQL.

**AI model assistant**

Gợi ý SQL, generate model skeleton từ source schema, tương tự dbt Copilot. Có thể tích hợp Claude API hoặc OpenAI với context từ `manifest.json` và schema của warehouse.

---

## 5. Roadmap gợi ý

```
Phase 1 — Core IDE (1-2 tháng)
├── Multi-tab file editing
├── SQL formatting (sqlfluff/sqlfmt via backend)
├── Find & replace across project
├── Git diff viewer trước khi commit
└── Keyboard shortcuts cơ bản (Ctrl+S, Ctrl+Enter)

Phase 2 — Developer Intelligence (2-3 tháng)
├── Autocomplete cho ref(), source(), config() từ manifest.json
├── SQL linting inline (Monaco diagnostics via sqlfluff)
├── Test result visualization (parse JSON output)
├── dbt docs viewer (generate + embed trong UI)
└── Fix security: per-user auth + session isolation

Phase 3 — Team & Observability (3-4 tháng)
├── Column-level lineage
├── Source freshness monitoring
├── Run history + model timing dashboard
├── Project health dashboard
└── RBAC / per-user permissions
```

### Tóm tắt gap quan trọng nhất

Gap lớn nhất so với dbt Cloud là **editor intelligence** (autocomplete + linting) và **multi-tab editing** — hai thứ này ảnh hưởng trực tiếp đến năng suất viết SQL hàng ngày.

Về bảo mật, gap lớn nhất là **auth tắt mặc định** và **không có user isolation** — cần fix trước khi deploy cho team có nhiều người dùng.

So với dbt-studio, lợi thế của dbt-ui là web-based và git integration đầy đủ; gap chính là thiếu AI assistance và auto-scaffolding.
