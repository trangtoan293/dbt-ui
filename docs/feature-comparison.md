# So sánh tính năng: dbt-studio vs dbt-ui

> Mục đích: Xác định các tính năng dbt-studio có mà dbt-ui chưa có (và ngược lại), để lên kế hoạch bổ sung.

---

## 1. Tổng quan kiến trúc

| Khía cạnh | dbt-studio | dbt-ui |
|-----------|-----------|--------|
| Frontend | Next.js 15 (React 19) | React + Vite |
| Backend | FastAPI (dbt-runner) | FastAPI |
| Database | Supabase (PostgreSQL) | Không có (file-based) |
| Cache/Lock | Redis | In-memory mutex |
| Auth | Supabase Auth + MFA | Keycloak JWT |
| Storage | Supabase Storage | Filesystem |
| Deployment | Docker Compose + deploy.sh | Docker Compose + Nginx |

---

## 2. Tính năng dbt-studio CÓ mà dbt-ui CHƯA CÓ

### 2.1 AI Integration (Ưu tiên cao)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| AI Chat Assistant | Chat với AI để hỏi về dbt, SQL | Có (vLLM) | **Chưa có** |
| Natural Language to SQL | Tạo SQL từ mô tả tự nhiên | Có (ai-adapter edge function) | **Chưa có** |
| dbt-specific AI | AI hiểu context dbt project | Có (dbt-adapter edge function) | **Chưa có** |

### 2.2 Column-level Lineage (Ưu tiên cao)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| Table-level Lineage | DAG ở mức table | Có | Có |
| Column-level Lineage | Theo dõi dependency từng column | Có (sqlglot) | **Chưa có** |
| Column Click Highlight | Click column để highlight upstream/downstream | Có | **Chưa có** |

### 2.3 dbt Docs Integration (Ưu tiên trung bình)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| dbt docs generate | Tạo documentation | Có | **Chưa có** |
| dbt docs serve | Serve docs server | Có | **Chưa có** |
| Docs Viewer | Xem docs trong UI | Có | **Chưa có** |

### 2.4 SQL Editor Enhancement (Ưu tiên cao)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| dbt IntelliSense | Autocomplete `ref()`, `source()`, `config()` | Có | **Chưa có** |
| SQL Keyword Autocomplete | Gợi ý SQL keywords | Có | **Chưa có** |
| SQL Formatting (Jinja-safe) | Format SQL giữ nguyên Jinja blocks | Có | **Chưa có** |
| Keyboard Shortcuts | Phím tắt VS Code-like | Có | **Chưa có** |

### 2.5 File Operations Nâng cao (Ưu tiên trung bình)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| File Search | Tìm kiếm file theo tên | Có | **Chưa có** |
| File Copy | Copy file | Có | **Chưa có** |
| File Duplicate | Duplicate với _copy suffix | Có | **Chưa có** |
| File Move | Di chuyển file (drag-drop) | Có | Có (drag-drop) |
| Content Search | Tìm kiếm trong nội dung file | Có | **Chưa có** |

### 2.6 Git Nâng cao (Ưu tiên trung bình)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| Commit History | Xem lịch sử commit | Có | **Chưa có** |
| Git Fetch | Fetch từ remote | Có | **Chưa có** |
| Git Init | Khởi tạo repo mới | Có | **Chưa có** |
| Remote Management | Thêm/xóa remote | Có | **Chưa có** |
| Git Config | Cấu hình user.name, user.email | Có | Có (cookie-based) |
| File Discard | Discard thay đổi của file | Có | Có (restore-file) |

### 2.7 Connection Management Nâng cao (Ưu tiên trung bình)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| PostgreSQL Adapter | Kết nối PostgreSQL | Có | **Chưa có** |
| Snowflake Adapter | Kết nối Snowflake | Có | **Chưa có** |
| BigQuery Adapter | Kết nối BigQuery | Có | **Chưa có** |
| Redshift Adapter | Kết nối Redshift | Có | **Chưa có** |
| Schema Extraction | Trích xuất schema từ connection | Có | **Chưa có** |
| Connection Usage | Xem project nào đang dùng connection | Có | **Chưa có** |

### 2.8 Project Management (Ưu tiên trung bình)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| Soft Delete Project | Xóa mềm, có thể khôi phục | Có | **Chưa có** |
| Restore Project | Khôi phục project đã xóa | Có | **Chưa có** |
| Project Settings Dialog | Cấu hình tên, git URL, branch | Có | Có (workspace settings) |

### 2.9 Authentication & Security (Ưu tiên thấp - đã dùng Keycloak)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| MFA (TOTP) | Two-factor authentication | Có | **Chưa có** (dùng Keycloak) |
| SSO/OAuth | OAuth providers | Có | **Chưa có** (dùng Keycloak) |
| User Settings Page | Đổi mật khẩu, profile | Có | **Chưa có** (dùng Keycloak) |

### 2.10 Real-time Features (Ưu tiên trung bình)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| WebSocket Terminal | Terminal output real-time | Có | **Chưa có** (polling) |
| File Watcher | Theo dõi thay đổi file real-time | Có | **Chưa có** |

### 2.11 File Storage (Ưu tiên thấp)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| File Upload | Upload file lên storage | Có (Supabase) | **Chưa có** |
| File Download | Download file | Có | **Chưa có** |
| Shareable URLs | Tạo link chia sẻ file | Có | **Chưa có** |
| Cross-device Sync | Sync project giữa các thiết bị | Có | **Chưa có** |

### 2.12 DuckDB Corruption Detection (Ưu tiên thấp)
| Tính năng | Mô tả | dbt-studio | dbt-ui |
|-----------|-------|-----------|--------|
| Auto-detect corrupted DuckDB | Phát hiện file DuckDB bị lỗi | Có | **Chưa có** |
| Auto-fix suggestion | Gợi ý cách sửa | Có | **Chưa có** |

---

## 3. Tính năng dbt-ui CÓ mà dbt-studio CHƯA CÓ

### 3.1 MetaDV Data Vault Modeling
| Tính năng | Mô tả |
|-----------|-------|
| Visual Data Vault Editor | UI kéo thả để mô hình hóa Data Vault 2.0 |
| Source-to-Target Mapping | Ánh xạ column từ source đến entity |
| Hub/Link/Sat Generation | Tự động sinh SQL models |
| automate_dv/datavault4dbt | Hỗ trợ 2 package phổ biến |

### 3.2 Multi-User Worktree Isolation
| Tính năng | Mô tả |
|-----------|-------|
| Per-user Git worktree | Mỗi user có worktree riêng |
| Worktree provisioning | Tự động tạo worktree từ Catalog |
| Merge to main | Maintainer merge branch vào main |

### 3.3 Production Engine (Dremio) Integration
| Tính năng | Mô tả |
|-----------|-------|
| Token Exchange | Đổi Keycloak token lấy Dremio token |
| Role-based gate | Chỉ maintainer mới chạy được Production Engine |
| Runtime credentials | Credentials không lưu, cấp lúc runtime |

### 3.4 Project Catalog
| Tính năng | Mô tả |
|-----------|-------|
| Centralized catalog | Quản lý danh sách project tập trung |
| Admin-only mutations | Chỉ admin mới thêm/xóa được project |

### 3.5 Environment Variables Management
| Tính năng | Mô tả |
|-----------|-------|
| env_var() scanning | Quét SQL/YML tìm env_var() |
| HttpOnly cookie storage | Lưu env vars an toàn trong cookie |
| Per-project env vars | Mỗi project có env vars riêng |

### 3.6 Conflict Resolution
| Tính năng | Mô tả |
|-----------|-------|
| 3-way merge | Tự động merge khi conflict |
| Conflict modal UI | UI giải quyết conflict |
| Original content tracking | Theo dõi nội dung gốc |

### 3.7 Audit & Compliance
| Tính năng | Mô tả |
|-----------|-------|
| Audit logging | Ghi log hành động user |
| Secret scrubbing | Xóa secrets khỏi log |
| Rate limiting | Giới hạn tần suất chạy dbt |

---

## 4. Ma trận ưu tiên bổ sung cho dbt-ui

### Phase 1 - Ưu tiên cao (Impact lớn, cải thiện DX)

| # | Tính năng | Độ phức tạp | Lý do |
|---|-----------|-------------|-------|
| 1 | **SQL IntelliSense** (autocomplete `ref()`, `source()`) | Trung bình | Tăng năng suất viết SQL đáng kể |
| 2 | **Column-level Lineage** (sqlglot) | Cao | Hiểu rõ data flow ở mức column |
| 3 | **SQL Formatting** (Jinja-safe) | Trung bình | Code nhất quán, dễ đọc |
| 4 | **AI Assistant** (chat + NL-to-SQL) | Cao | Xu hướng AI-first, hỗ trợ user mới |

### Phase 2 - Ưu tiên trung bình (Hoàn thiện workflow)

| # | Tính năng | Độ phức tạp | Lý do |
|---|-----------|-------------|-------|
| 5 | **dbt docs generate/serve** | Thấp | Tích hợp sẵn có của dbt |
| 6 | **File Search** (theo tên + nội dung) | Thấp | Tìm file nhanh trong project lớn |
| 7 | **Commit History** viewer | Thấp | Theo dõi lịch sử thay đổi |
| 8 | **File Copy/Duplicate** | Thấp | Thao tác file cơ bản |
| 9 | **Schema Extraction** từ connection | Trung bình | Khám phá schema không cần viết SQL |
| 10 | **WebSocket Terminal** | Trung bình | Real-time output thay vì polling |

### Phase 3 - Ưu tiên thấp (Nice-to-have)

| # | Tính năng | Độ phức tạp | Lý do |
|---|-----------|-------------|-------|
| 11 | **Thêm adapters** (PostgreSQL, Snowflake, BigQuery) | Trung bình | Mở rộng đối tượng sử dụng |
| 12 | **Soft Delete/Restore Project** | Thấp | An toàn hơn khi xóa |
| 13 | **File Storage/Upload** | Trung bình | Chia sẻ data files |
| 14 | **DuckDB Corruption Detection** | Thấp | Ổn định hơn cho dev |
| 15 | **Git Fetch/Remote Management** | Thấp | Hoàn thiện git workflow |

---

## 5. Ghi chú kỹ thuật

### SQL IntelliSense
- Cần parse `manifest.json` để lấy danh sách models, sources, macros
- Monaco Editor hỗ trợ `CompletionItemProvider` API
- Tham khảo: `dbt-studio/nextjs/src/components/CodeEditor.tsx`

### Column-level Lineage
- Dùng `sqlglot` để parse SQL và trích xuất column dependencies
- Kết hợp với `manifest.json` để map column giữa models
- Tham khảo: `dbt-studio/dbt-runner/app/lineage.py`

### AI Integration
- Có thể dùng LLM API (OpenAI, Anthropic, hoặc self-hosted vLLM)
- Cần context: dbt project structure, manifest, current file
- Tham khảo: `dbt-studio/supabase/functions/ai-adapter/`

### SQL Formatting
- Cần formatter hiểu Jinja syntax
- Tham khảo: `sqlfmt` hoặc custom formatter trong dbt-studio
- Preserve: `{% %}`, `{{ }}`, comments, string literals

---

## 6. Kết luận

**dbt-ui** mạnh về:
- Multi-user collaboration (worktree isolation)
- Enterprise features (audit, RBAC, Dremio integration)
- Data Vault modeling (MetaDV)

**dbt-studio** mạnh về:
- Developer experience (IntelliSense, formatting, column lineage)
- AI-powered features
- Broader adapter support
- Real-time features (WebSocket)

**Khuyến nghị**: Tập trung Phase 1 để cải thiện DX, sau đó bổ sung Phase 2 để hoàn thiện workflow.
