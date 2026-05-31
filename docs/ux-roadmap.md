# dbt-ui — UX/DX Roadmap

> Living doc để phát triển dần dần. Nguồn: `docs/feature-comparison.md` (parity với dbt-studio) + các tính năng UX net-new.
>
> **Trạng thái:** ☐ chưa làm · ◐ đang làm · ☑ xong · ⚡ nằm trong M4 plan (`docs/superpowers/plans/2026-05-31-m4-ide-productivity.md`)
>
> **Quy ước:** mỗi mục có acceptance ngắn để biết khi nào "xong". Phức tạp: Thấp / TB / Cao.
>
> Cập nhật doc này mỗi khi hoàn thành 1 mục (đổi ☐ → ☑, ghi commit/PR).

---

## Cách dùng roadmap

1. Làm theo **Tier** (0 → 3). Tier 0 = UX nền, ROI cao nhất.
2. Mỗi tính năng đủ nhỏ để thành 1 PR độc lập. Tính năng phức tạp (Cao) → tách plan riêng kiểu M4.
3. Backend đổi → TDD (pytest). Frontend → verify thủ công (chưa có FE test infra) trừ logic thuần (gợi ý vitest).
4. Trước khi bắt đầu 1 Tier, có thể chạy brainstorming để chốt scope từng mục.

---

## Tier 0 — UX nền tảng (công ít, impact lớn) — **làm ngay sau M4**

Mục tiêu: app "cảm giác" hoàn chỉnh, phản hồi rõ ràng, không nuốt lỗi.

| # | Tính năng | Phức tạp | Acceptance | TT |
|---|-----------|----------|-----------|----|
| T0.1 | **Toast notification** thống nhất (success/error/info/warning) | Thấp | Mọi async action (save, run, git, workspace) phát toast; auto-dismiss; stack; 1 component dùng chung | ☐ |
| T0.2 | **Empty states có hướng dẫn** | Thấp | Chưa có project/model/connection/manifest → hiện thông điệp + CTA hành động (không phải màn trống) | ☐ |
| T0.3 | **Error surfacing tử tế** | Thấp | Lỗi API hiện message rõ + gợi ý action; không `console.error` rồi im; secret đã scrub | ☐ |
| T0.4 | **Keyboard shortcuts** VS Code-like | Thấp | Cmd/Ctrl+S save · Cmd+Enter run · Cmd+/ comment · Cmd+P open file · Esc đóng modal; không xung đột Monaco | ☐ |
| T0.5 | **Status bar** dưới cùng | Thấp | Hiện branch · target/engine · venv status · unsaved count · lỗi compile count; click vào jump | ☐ |
| T0.6 | **Resizable/collapsible panels** + nhớ layout | TB | Kéo resize sidebar/editor/results/lineage; collapse; lưu localStorage; khôi phục khi reload | ☐ |
| T0.7 | **Confirm dialog** cho hành động phá hủy | Thấp | Delete file/project, discard, merge-to-main, đóng tab dirty → confirm; 1 component dùng chung | ☐ |
| T0.8 | **Loading skeleton/spinner** nhất quán | Thấp | Tree load, file load, run, lineage → có loading state; không nhảy layout | ☐ |

---

## Tier 1 — DX flagship (năng suất coding)

| # | Tính năng | Phức tạp | Acceptance | TT |
|---|-----------|----------|-----------|----|
| T1.1 | **Command Palette** (Cmd+K / Cmd+P) | TB | Mở: tìm file, jump model, chạy command (run/build/format/git), đổi target; fuzzy match; keyboard-only | ☐ |
| T1.2 | **File search theo tên** (fuzzy) | Thấp | Cmd+P gõ tên → list file khớp → Enter mở; scoped trong worktree | ☐ |
| T1.3 | **Content search** (grep trong project) | TB | Tìm chuỗi trong file project; list kết quả file:line; click → mở tại dòng; scoped worktree (path authority) | ☐ |
| T1.4 | **Model search** từ manifest | Thấp | Gõ tên model bất kỳ → jump tới file; nguồn = manifest hiện tại | ☐ |
| T1.5 | **Go-to-definition** `ref('x')`/`source()` | TB | Cmd+click hoặc F12 trên `ref('x')` → mở file model x (từ manifest); fallback toast nếu chưa compile | ☐ |
| T1.6 | **Results grid** xịn | TB | Sort, filter, resize column, sticky header, copy cell/row; thay grid thô hiện tại | ☐ |
| T1.7 | **Diff viewer trước commit** | TB | Side-by-side working vs HEAD; chọn file xem diff; (stretch: stage per-hunk) | ☐ |
| T1.8 | **Click node DAG → mở file** | Thấp | Click model trong lineage → mở file tương ứng trong tab | ☑ (M4: `onNodeClick={tabs.openTab}`) |
| T1.9 | **Inline lint squiggles** (sqlfluff lint) | TB | Lint `.sql` → squiggle + hover message; tách với format (T M4) | ☐ |

---

## Tier 2 — Hoàn thiện workflow

| # | Tính năng | Phức tạp | Acceptance | TT |
|---|-----------|----------|-----------|----|
| T2.1 | **Query history** | TB | Lưu lệnh đã chạy (dbt show/run) per-project; click chạy lại; thời gian + trạng thái | ☐ |
| T2.2 | **Run selection** (chạy đoạn SQL bôi đen) | TB | Bôi đen SQL → Cmd+Enter chạy đoạn đó (compile + show) | ☐ |
| T2.3 | **Cancel running query/run** | TB | Nút hủy khi dbt đang chạy; backend kill subprocess + nhả lock | ☐ |
| T2.4 | **WebSocket terminal** real-time | TB | Output dbt stream real-time thay polling; màu ANSI; auto-scroll; collapse | ☐ |
| T2.5 | **Run summary** | TB | Sau run: count pass/fail/skip; click node lỗi → log của node đó | ☐ |
| T2.6 | **Run từ context menu** file/folder | TB | Chuột phải model → run/test/build (+children); build selector tự động | ☐ |
| T2.7 | **Commit history viewer** | Thấp | Xem git log; click commit → diff các file trong commit | ☐ |
| T2.8 | **dbt docs generate + serve** trong UI | Thấp | Nút generate docs; viewer/iframe xem docs; scoped worktree | ☐ |
| T2.9 | **Export kết quả** CSV/JSON/clipboard | Thấp | Từ results grid export ra file/clipboard | ☐ |
| T2.10 | **File copy/duplicate** | Thấp | Context menu duplicate (_copy suffix) + copy; path validation | ☐ |
| T2.11 | **Compiled SQL side-by-side** | Thấp | Toggle xem raw Jinja ↔ compiled cạnh nhau (dùng useCompiledSql sẵn) | ☐ |

---

## Tier 3 — Mở rộng & khác biệt hóa

| # | Tính năng | Phức tạp | Acceptance | TT |
|---|-----------|----------|-----------|----|
| T3.1 | **Column-level lineage** (sqlglot) | Cao | Parse SQL → column dependencies; map qua manifest; tách plan riêng | ☐ |
| T3.2 | **Click column → highlight upstream/downstream** | Cao | Trên column lineage, click column → highlight đường liên quan | ☐ |
| T3.3 | **Lineage controls**: focus node, search, fit, mini-map | TB | Isolate 1 node + neighbors; search node; fit-to-screen; mini-map | ☐ |
| T3.4 | **AI chat** context-aware | Cao | Chat hiểu project/manifest/file hiện tại; LLM API config được; tách plan riêng | ☐ |
| T3.5 | **NL → SQL** | Cao | Mô tả tự nhiên → SQL gợi ý chèn vào editor | ☐ |
| T3.6 | **AI generate test / docs / fix lỗi** | Cao | Gợi ý dbt test, mô tả YAML, sửa lỗi compile/run từ log | ☐ |
| T3.7 | **Thêm adapter** PostgreSQL/Snowflake/BigQuery/Redshift | TB | Cài adapter trong venv + UI form connection theo adapter | ☐ |
| T3.8 | **Schema extraction** từ connection | TB | Browse database → schema → table → column không cần viết SQL | ☐ |
| T3.9 | **Soft delete + restore project** | Thấp | Xóa mềm project/workspace; list trash; restore | ☐ |
| T3.10 | **File upload/download** (seed CSV) | TB | Upload CSV vào seeds/; download file; path validation + size limit | ☐ |
| T3.11 | **File watcher** | TB | File đổi ngoài UI → prompt reload; tránh ghi đè | ☐ |
| T3.12 | **Light/Dark theme toggle** | Thấp | Toggle theme; lưu preference; cả 2 theme đều chỉn chu (hiện hard-code dark) | ☐ |
| T3.13 | **A11y pass** | TB | Focus ring, ARIA roles, keyboard-only navigable, contrast đạt WCAG AA | ☐ |
| T3.14 | **Git fetch / remote management** | Thấp | Fetch remote; thêm/xóa remote từ UI | ☐ |

---

## Phụ thuộc & ghi chú kỹ thuật

- **Path authority:** mọi endpoint mới (search, copy, upload, docs, schema) PHẢI resolve qua `resolve_under_root(user.sub, path)` — không tin path tuyệt đối từ client. Ref: `docs/issues/03-path-authority.md`.
- **Secret scrub:** mọi output log/error trả client → `scrub()`. AI/connection đặc biệt lưu ý.
- **Lock:** run/cancel/build dùng `operation_lock.py` (1 dbt op/worktree).
- **Command Palette (T1.1)** nên là nền cho keyboard shortcuts (T0.4) — cân nhắc làm T0.4 trước, T1.1 mở rộng.
- **Results grid (T1.6)** chặn export (T2.9) và một phần query history (T2.1) — làm trước.
- **WebSocket terminal (T2.4)** thay cơ chế polling `/api/dbt-command-status` hiện tại — đổi cả FE lẫn BE, tách plan riêng.
- **Column lineage (T3.1)** + **AI (T3.4-3.6)** mỗi cái 1 plan riêng kiểu M4.
- **FE test:** chưa có runner. Logic thuần (palette filter, grid sort) → gợi ý thêm vitest; UI → verify thủ công.

## Liên kết
- Parity gốc: `docs/feature-comparison.md`
- M4 (tabs/format/autocomplete = A1-A3): `docs/superpowers/plans/2026-05-31-m4-ide-productivity.md`
- Issues: `docs/issues/`
- Glossary/decisions: `CONTEXT.md`, `docs/adr/`
