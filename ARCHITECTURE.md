# SkillProof — Tài liệu Kiến trúc

> **Phiên bản:** 1.2.0 — Giai đoạn 01.1  
> **Cập nhật:** 2026-11-08  
> **Trạng thái:** Xác thực ổn định, PBKDF2 per-user salt, first-run setup, 133 tests PASS

---

## 1. Tổng quan hệ thống

**SkillProof** là ứng dụng Desktop quản lý và chứng nhận kỹ năng chuyên nghiệp.

| Thuộc tính      | Giá trị                              |
|-----------------|--------------------------------------|
| Loại ứng dụng   | Desktop App (standalone)             |
| Ngôn ngữ        | Python 3.13                          |
| GUI Framework   | PySide6 6.12.0 (Qt6)                 |
| Database        | SQLite 3 (tích hợp Python)           |
| IDE             | Kiro                                 |
| Repository      | https://github.com/Trungdeptrai-1/SkillProof |
| Điểm vào        | `python main.py`                     |

---

## 2. Cấu trúc thư mục thực tế

```
SkillProof_New/
├── main.py                         ✅ Điểm vào
├── requirements.txt                ✅ PySide6 + pytest
├── README.md                       ✅ Cập nhật Giai đoạn 01.1
├── ARCHITECTURE.md                 ✅ Tài liệu này
├── pytest.ini                      ✅ Cấu hình test suite
├── git_setup.ps1                   (có thể xóa)
├── .gitignore
│
├── app/
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py           ✅ Singleton, WAL, FK ON
│   │   └── schema.py               ✅ DDL + MIG-001/002/003, is_first_run()
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── user_model.py           ✅ UserModel DTO, không có field password
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── auth_service.py         ✅ PBKDF2 verify, dummy hash, lazy rehash
│   │
│   ├── ui/
│   │   ├── main_window.py          ✅ route_initial → FirstRun/Welcome
│   │   └── screens/
│   │       ├── welcome_screen.py   ✅ Màn hình chào mừng
│   │       ├── login_screen.py     ✅ Đăng nhập
│   │       ├── first_run_screen.py ✅ Thiết lập admin lần đầu (Giai đoạn 01.1)
│   │       └── dashboard_screen.py ✅ Placeholder 6 roles
│   │
│   └── utils/
│       ├── constants.py            ✅ Design tokens
│       ├── styles.py               ✅ QSS tập trung
│       └── helpers.py              ✅ PBKDF2-SHA256, backward compat legacy
│
├── tests/                          ✅ 133 tests PASS (Giai đoạn 01.1)
│   ├── conftest.py                 # Fixtures: fresh_db, legacy_db, auth, session_mgr
│   ├── test_auth_service.py        # 40 tests: login, logout, session, roles, injection
│   ├── test_migration.py           # 25 tests: MIG-001/002/003, rollback, FK
│   ├── test_password_hashing.py    # 17 tests: PBKDF2, backward compat, timing
│   ├── test_session.py             # 9 tests: SessionManager singleton, states
│   └── test_regression_phase00_01.py # 42 tests: regression full stack
│
├── assets/icons/ & images/         (chưa có file)
└── data/                           🔒 KHÔNG commit Git
    ├── skillproof.db
    └── logs/
```

---

## 3. Kiến trúc phân tầng

```
┌─────────────────────────────────────────────────────┐
│                  PRESENTATION LAYER                  │
│  main_window.py  │  screens/  │  components/        │
│  welcome_screen  │  login_screen  │  dashboard_screen│
│  (QStackedWidget navigation — Welcome→Login→Dashboard│
├─────────────────────────────────────────────────────┤
│                  BUSINESS LOGIC LAYER                │
│  services/auth_service.py                           │
│  AuthService · SessionManager · LoginResult         │
├─────────────────────────────────────────────────────┤
│                  DATA ACCESS LAYER                   │
│  models/user_model.py  (UserModel DTO)              │
│  database/connection.py  +  schema.py               │
├─────────────────────────────────────────────────────┤
│                  INFRASTRUCTURE                      │
│  utils/constants.py  │  utils/styles.py             │
│  utils/helpers.py    │  SQLite WAL                  │
└─────────────────────────────────────────────────────┘
```

### 3.1 Nguyên tắc thiết kế

- **Single Responsibility**: mỗi module có một trách nhiệm duy nhất.
- **Singleton DB**: `DatabaseConnection` đảm bảo một kết nối duy nhất trong suốt vòng đời ứng dụng.
- **Centralized Styles**: toàn bộ QSS tập trung trong `utils/styles.py`, không inline style trong widget.
- **Centralized Constants**: màu sắc, font, kích thước đều từ `utils/constants.py`.
- **Migration-safe Schema**: `create_all_tables()` + `_apply_migrations()` đảm bảo idempotent khi chạy nhiều lần.

---

## 4. Database Schema

### 4.1 Sơ đồ quan hệ (ERD đơn giản)

```
users (1) ──────────── (N) certificates
  │                           │
  │                           └── skills (1) ── (N) certificates
  │
  ├── (1) ──── (N) enrollments ──── (N) courses ── skills
  │
  ├── (1) ──── (N) assessments ──── skills
  │
  └── (1) ──── (N) courses [as instructor]
```

### 4.2 Bảng và mục đích

| Bảng           | Mục đích                                         | Hàng hiện tại |
|----------------|--------------------------------------------------|---------------|
| `users`        | Tài khoản người dùng, xác thực, phân quyền       | 1 (admin)     |
| `skills`       | Danh mục kỹ năng có thể đánh giá/chứng nhận      | 0             |
| `certificates` | Chứng chỉ đã cấp, mã duy nhất, trạng thái        | 0             |
| `courses`      | Khoá học liên kết kỹ năng và giảng viên           | 0             |
| `enrollments`  | Đăng ký khoá học, theo dõi tiến độ               | 0             |
| `assessments`  | Kết quả đánh giá kỹ năng của từng user            | 0             |
| `app_settings` | Cấu hình ứng dụng dạng key-value                  | 3             |

### 4.3 Vai trò người dùng (roles)

| Role         | Mô tả                                      |
|--------------|--------------------------------------------|
| `admin`      | Quản trị hệ thống, toàn quyền              |
| `instructor` | Giảng viên, quản lý khoá học               |
| `student`    | Học viên trong khoá học                    |
| `candidate`  | Ứng viên tìm việc (default role khi đăng ký) |
| `company`    | Doanh nghiệp đăng tuyển/xác minh chứng chỉ |
| `expert`     | Chuyên gia đánh giá kỹ năng               |

> **Lưu ý:** `candidate` là default role (`DEFAULT 'candidate'`) khi tạo user mới.

### 4.4 Ràng buộc quan trọng

```sql
-- Foreign Keys (bật qua PRAGMA foreign_keys = ON)
certificates.user_id  → users.id    ON DELETE CASCADE
certificates.skill_id → skills.id   ON DELETE CASCADE
courses.instructor_id → users.id    ON DELETE SET NULL
courses.skill_id      → skills.id   ON DELETE SET NULL
enrollments.user_id   → users.id    ON DELETE CASCADE
enrollments.course_id → courses.id  ON DELETE CASCADE
assessments.user_id   → users.id    ON DELETE CASCADE
assessments.skill_id  → skills.id   ON DELETE CASCADE

-- Unique constraints
users: username, email
skills: name
certificates: cert_code, (user_id, skill_id)
enrollments: (user_id, course_id)
app_settings: key (PRIMARY KEY)
```

### 4.5 Cấu hình database

| PRAGMA          | Giá trị | Ghi chú                                |
|-----------------|---------|----------------------------------------|
| `foreign_keys`  | `ON`    | Bật trong `connect()`, kiểm tra FK     |
| `journal_mode`  | `WAL`   | Write-Ahead Logging — hiệu năng tốt hơn |
| `page_size`     | 4096    | Mặc định SQLite                        |
| `encoding`      | UTF-8   | Hỗ trợ tiếng Việt                      |

---

## 5. Hệ thống thiết kế giao diện (Design System)

### 5.1 Bảng màu (Navy & White)

| Token                | Hex       | Dùng cho                         |
|----------------------|-----------|----------------------------------|
| `COLOR_NAVY_DARK`    | `#0A1628` | Header, sidebar nền đậm          |
| `COLOR_NAVY`         | `#0D2137` | Navy chính                       |
| `COLOR_NAVY_MID`     | `#1A3A5C` | Navy trung, scrollbar handle     |
| `COLOR_NAVY_LIGHT`   | `#1E4D7B` | Accent nhạt, button pressed      |
| `COLOR_ACCENT`       | `#2E86DE` | Button primary, highlight, focus |
| `COLOR_ACCENT_HOVER` | `#1A73C8` | Button hover state               |
| `COLOR_WHITE`        | `#FFFFFF` | Nền card, text trên navy         |
| `COLOR_OFF_WHITE`    | `#F4F7FB` | Nền màn hình chính               |
| `COLOR_LIGHT_GRAY`   | `#E8EDF4` | Border, divider                  |
| `COLOR_TEXT_DARK`    | `#0A1628` | Text chính trên nền sáng         |
| `COLOR_TEXT_MUTED`   | `#6B7F99` | Text phụ, placeholder            |
| `COLOR_SUCCESS`      | `#27AE60` | Trạng thái thành công            |
| `COLOR_WARNING`      | `#F39C12` | Cảnh báo                         |
| `COLOR_ERROR`        | `#E74C3C` | Lỗi                              |

### 5.2 Typography

| Token              | Size | Dùng cho                      |
|--------------------|------|-------------------------------|
| `FONT_SIZE_TITLE`  | 32px | Tiêu đề trang lớn             |
| `FONT_SIZE_HEADING`| 22px | Tiêu đề section               |
| `FONT_SIZE_SUBHEAD`| 16px | Tiêu đề phụ                   |
| `FONT_SIZE_BODY`   | 13px | Nội dung chính (mặc định)     |
| `FONT_SIZE_SMALL`  | 11px | Text nhỏ, caption, footer     |

Font chính: `"Segoe UI"` (Windows), fallback `"Arial"`.

### 5.3 Stylesheet components (utils/styles.py)

| Export                  | Loại    | Dùng cho                        |
|-------------------------|---------|---------------------------------|
| `GLOBAL_STYLE`          | str     | Áp dụng toàn app qua `setStyleSheet()` |
| `INPUT_STYLE`           | str     | QLineEdit, QTextEdit, QComboBox |
| `CARD_STYLE`            | str     | QFrame dạng card                |
| `STATUS_SUCCESS_STYLE`  | str     | Label thông báo thành công      |
| `STATUS_ERROR_STYLE`    | str     | Label thông báo lỗi             |
| `STATUS_WARNING_STYLE`  | str     | Label thông báo cảnh báo        |
| `primary_button_style()`| func    | Nút chính (xanh cobalt)         |
| `secondary_button_style()`| func  | Nút phụ (viền xanh)             |
| `ghost_button_style()`  | func    | Nút ghost (trên nền navy)       |

### 5.4 Kích thước cửa sổ

| Constant               | Giá trị     |
|------------------------|-------------|
| `WINDOW_MIN_WIDTH`     | 1024px      |
| `WINDOW_MIN_HEIGHT`    | 680px       |
| `WINDOW_DEFAULT_WIDTH` | 1280px      |
| `WINDOW_DEFAULT_HEIGHT`| 800px       |
| `WELCOME_WIDTH`        | 960px       |
| `WELCOME_HEIGHT`       | 620px       |

---

## 6. Điều hướng giao diện

### 6.1 Cơ chế hiện tại

`MainWindow` dùng `QStackedWidget` làm central widget. Chuyển màn hình bằng `setCurrentWidget()`.

```python
# Thêm màn hình mới (pattern chuẩn)
screen = NewScreen()
self._stack.addWidget(screen)
self._stack.setCurrentWidget(screen)
```

### 6.2 Callback pattern

Thay vì Qt Signal/Slot, màn hình dùng callable attribute:

```python
# Trong MainWindow
screen.on_action = self._handle_action

# Trong Screen
if callable(self.on_action):
    self.on_action(data)
```

> **Lý do:** Đơn giản hơn cho giai đoạn đầu. Có thể chuyển sang Signal/Slot ở giai đoạn sau khi cần type-safety.

### 6.3 Luồng điều hướng thực tế (Giai đoạn 01)

```
WelcomeScreen
    │
    ├── [Bắt đầu] ──────────────────────────► LoginScreen
    │                                              │
    │                                   [Đăng nhập thành công]
    │                                              │
    │                        ┌─────────────────────┴─────────────────────┐
    │                        ▼ (theo role từ DB)                          │
    │               DashboardScreen(user)                          [Quay lại]
    │               (sidebar + content placeholder)                       │
    │                        │                                            │
    │                   [Đăng xuất]                                       │
    │                        └──────────────────────────────► LoginScreen ◄┘
    │
    └── [Tìm hiểu thêm] → QMessageBox
```

**Cơ chế tạo/hủy Dashboard:**
- Mỗi lần đăng nhập tạo `DashboardScreen` mới với `user` hiện tại.
- Dashboard cũ bị xóa bằng `removeWidget()` + `deleteLater()` trước khi tạo mới.
- `LoginScreen` được tạo một lần, `reset()` khi hiển thị lại.

### 6.4 Lộ trình màn hình dự kiến

```
WelcomeScreen
    └── [Bắt đầu] → LoginScreen
                        ├── [admin]      → AdminDashboard
                        ├── [instructor] → InstructorDashboard
                        ├── [candidate]  → CandidateDashboard
                        ├── [company]    → CompanyDashboard
                        └── [expert]     → ExpertDashboard
```

---

## 7. Quy ước phát triển

### 7.1 Đặt tên file

| Loại            | Quy ước               | Ví dụ                        |
|-----------------|-----------------------|------------------------------|
| Screen          | `*_screen.py`         | `login_screen.py`            |
| Component       | `*_widget.py`         | `nav_bar_widget.py`          |
| Dialog          | `*_dialog.py`         | `confirm_dialog.py`          |
| Service         | `*_service.py`        | `auth_service.py`            |
| Model/DTO       | `*_model.py`          | `user_model.py`              |

### 7.2 Đặt tên class

| Loại            | Quy ước               | Ví dụ                        |
|-----------------|-----------------------|------------------------------|
| Screen          | `*Screen`             | `LoginScreen`                |
| Dialog          | `*Dialog`             | `ConfirmDialog`              |
| Service         | `*Service`            | `AuthService`                |
| Model           | `*Model` hoặc `*DTO`  | `UserModel`                  |
| Private widget  | `_*`                  | `_BrandPanel`                |

### 7.3 Cấu trúc một Screen mới

```python
# app/ui/screens/example_screen.py
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout
from app.utils.constants import COLOR_OFF_WHITE
from app.utils.styles import primary_button_style

class ExampleScreen(QWidget):
    """Mô tả ngắn về màn hình."""

    # Callbacks (gán từ MainWindow)
    on_navigate_back: object = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Khởi tạo layout và widget."""
        ...
```

### 7.4 Truy vấn database

```python
# ĐÚNG — dùng parameterized query
from app.database.connection import db
user = db.fetchone("SELECT * FROM users WHERE username=?", (username,))

# SAI — không bao giờ nối chuỗi SQL
user = db.fetchone(f"SELECT * FROM users WHERE username='{username}'")
```

### 7.5 Xử lý ngoại lệ

```python
# Trong service layer
try:
    result = db.execute("INSERT INTO ...", params)
    return result
except sqlite3.IntegrityError as e:
    logger.warning("Duplicate entry: %s", e)
    raise ValueError("Dữ liệu đã tồn tại.") from e
except Exception as e:
    logger.exception("DB error: %s", e)
    raise
```

---

## 8. Bảo mật

### 8.1 Password Hashing — PBKDF2-SHA256

```
Giai đoạn 01.1+:
  Format: "pbkdf2:sha256:600000:<base64_salt>:<base64_hash>"
  Salt: 32 bytes ngẫu nhiên per-user (os.urandom)
  Iterations: 600,000 (OWASP 2023 minimum)
  Output: 32 bytes (256 bits)

Legacy (backward compat):
  Format: hex string 64 ký tự = SHA-256("skillproof_salt_2024" + password)
  verify_password() nhận biết tự động và verify đúng
  needs_rehash() = True → lazy upgrade lên PBKDF2 khi login thành công
```

### 8.2 Timing Attack Mitigation

```python
# auth_service.py — thứ tự cố định, không early return trước verify
stored_hash = row["password"] if row else _DUMMY_HASH  # dummy nếu không tìm thấy
pw_ok = verify_password(password, stored_hash)          # LUÔN chạy PBKDF2
if row is None: return USER_NOT_FOUND                   # return SAU khi đã verify
if not pw_ok:   return WRONG_PASSWORD
if inactive:    return ACCOUNT_INACTIVE                 # check active CUỐI cùng
```

### 8.3 Thông báo lỗi — Không tiết lộ thông tin

| Trường hợp | Thông báo hiển thị |
|---|---|
| Email không tồn tại | "Email hoặc mật khẩu không chính xác." |
| Sai mật khẩu | "Email hoặc mật khẩu không chính xác." |
| Tài khoản bị khoá | "Tài khoản đã bị vô hiệu hóa..." |

### 8.4 Admin Setup — First-Run

- **Không có admin hardcode** từ Giai đoạn 01.1.
- Màn hình `FirstRunScreen` xuất hiện khi `setup_done != '1'`.
- Admin tự nhập email + mật khẩu mạnh → hash PBKDF2 ngay lập tức.
- `mark_setup_done()` ghi `setup_done=1` vào `app_settings`.

### 8.5 Không commit lên Git

- `data/` — database chứa mật khẩu hash
- `.venv/`, `.env*`, `secrets.*`
- `data/logs/`

---

## 9. Migrations

Schema được quản lý trong `app/database/schema.py`:

```
create_all_tables()
    ├── executescript(SCHEMA_SQL)    # CREATE TABLE IF NOT EXISTS
    ├── executescript(TRIGGERS_SQL)  # CREATE TRIGGER IF NOT EXISTS
    ├── executescript(SEED_SQL)      # INSERT OR IGNORE
    └── _apply_migrations()
            ├── MIG-001: Cập nhật admin password hash (8c6976 → 67fc4c2b)
            └── MIG-002: Recreate users table với role CHECK đầy đủ
```

**Nguyên tắc migration:**
- Luôn idempotent (chạy nhiều lần không lỗi).
- Không xóa dữ liệu hiện có.
- Log rõ ràng từng migration đã áp dụng.
- Đặt tên dạng `MIG-NNN: Mô tả`.

---

## 10. Lộ trình phát triển

### Giai đoạn 00 — Nền tảng ✅ HOÀN THÀNH
- [x] Cấu trúc thư mục, main.py, WelcomeScreen
- [x] Database singleton, schema 7 bảng, WAL
- [x] Design system: màu, font, stylesheet
- [x] Helpers: validate, logging
- [x] Sửa BUG-1 (role constraint), BUG-2 (admin hash)

### Giai đoạn 01 — Xác thực người dùng ✅ HOÀN THÀNH
- [x] UserModel DTO, AuthService, SessionManager
- [x] LoginScreen 2-panel, toggle password
- [x] DashboardScreen placeholder 6 roles
- [x] Navigation Welcome→Login→Dashboard→Logout

### Giai đoạn 01.1 — Ổn định xác thực ✅ HOÀN THÀNH
- [x] PBKDF2-SHA256 600k, per-user salt (stdlib — không cần thư viện ngoài)
- [x] Backward compat legacy hash, lazy rehash khi login
- [x] Timing attack mitigation (dummy hash, verify trước is_active)
- [x] First-Run Admin Setup — không hardcode mật khẩu
- [x] MIG-003: vô hiệu hóa admin legacy, yêu cầu reset
- [x] MIG-002 sửa: `conn.execute()` thay `executescript()`, row-count verify, rollback
- [x] Test suite: 133 tests PASS (pytest 8.3.5)

### Giai đoạn 02 — Dashboard nghiệp vụ theo vai trò
- [ ] AdminDashboard — quản lý users, skills, settings
- [ ] CandidateDashboard — hồ sơ, kỹ năng, chứng chỉ
- [ ] CompanyDashboard — tìm kiếm, xác minh
- [ ] ExpertDashboard — đánh giá, cấp chứng nhận
- [ ] InstructorDashboard — khoá học, học viên
- [ ] StudentDashboard — đăng ký, tiến độ

### Giai đoạn 03+ — Nghiệp vụ
- [ ] Quản lý kỹ năng (CRUD)
- [ ] Quản lý chứng chỉ
- [ ] Quản lý khoá học
- [ ] Đánh giá năng lực
- [ ] Báo cáo & thống kê
- [ ] Xuất PDF chứng chỉ

---

## 11. Vấn đề còn tồn tại (sau Giai đoạn 01.1)

| #   | Mức độ  | Vấn đề                                              | Giai đoạn giải quyết |
|-----|---------|-----------------------------------------------------|----------------------|
| W-1 | Thấp    | Legacy hash vẫn hoạt động — lazy migrate khi login  | ✅ Tự động           |
| W-2 | Trung   | Không có UI Reset Admin (cần xóa DB thủ công)       | Giai đoạn 02         |
| W-3 | Thấp    | `git_setup.ps1` không cần sau khi Git ổn định       | Có thể xóa           |
| W-4 | Thấp    | PBKDF2 272ms/login — OK desktop, cần test máy yếu   | Theo dõi             |
| W-5 | Thấp    | Không có icon file trong `assets/`                  | Giai đoạn 02         |

---

## 12. AuthService — Chi tiết kỹ thuật (Giai đoạn 01.1)

### 12.1 Luồng xác thực

```
login(email, password)
    ├── 1. email.strip() trống → EMPTY_EMAIL
    ├── 2. password trống → EMPTY_PASSWORD
    ├── 3. is_valid_email() → INVALID_EMAIL_FORMAT
    ├── 4. DB SELECT WHERE email=? (parameterized)
    │       └── sqlite3.Error → DB_ERROR
    ├── 5. stored_hash = row["password"] IF row ELSE _DUMMY_HASH
    ├── 6. pw_ok = verify_password(password, stored_hash)  ← PBKDF2, LUÔN chạy
    ├── 7. row is None → USER_NOT_FOUND     (return SAU verify)
    ├── 8. not pw_ok → WRONG_PASSWORD
    ├── 9. not is_active → ACCOUNT_INACTIVE  (check CUỐI)
    ├── 10. needs_rehash() → _rehash_password() (lazy migrate)
    └── 11. SUCCESS → UserModel.from_row() → SessionManager.start_session()
```

### 12.2 LoginResult status codes

| Status | Thông báo hiển thị |
|--------|-------------------|
| `success` | Chuyển màn hình |
| `empty_email` | "Vui lòng nhập địa chỉ email." |
| `empty_password` | "Vui lòng nhập mật khẩu." |
| `invalid_email_format` | "Địa chỉ email không đúng định dạng." |
| `user_not_found` | "Email hoặc mật khẩu không chính xác." |
| `wrong_password` | "Email hoặc mật khẩu không chính xác." |
| `account_inactive` | "Tài khoản đã bị vô hiệu hóa..." |
| `db_error` | "Không thể kết nối cơ sở dữ liệu..." |

---

## 13. Đánh giá Roles — Báo cáo

### 13.1 Roles trong database

| Role | Mô tả | Trong 4 roles nghiệp vụ dự kiến |
|------|-------|----------------------------------|
| `admin` | Quản trị hệ thống | ✅ Có |
| `instructor` | Giảng viên khoá học | ⚠️ Không có trong 4 roles chính |
| `student` | Học viên khoá học | ⚠️ Không có trong 4 roles chính |
| `candidate` | Ứng viên tìm việc | ✅ Có (default) |
| `company` | Doanh nghiệp | ✅ Có |
| `expert` | Chuyên gia đánh giá | ✅ Có |

### 13.2 Phân tích instructor/student

- Bảng `courses.instructor_id → users.id` tạo dependency thực giữa schema và role `instructor`.
- Bảng `enrollments.user_id → users.id` phục vụ cả `student` lẫn `candidate`.
- **Khuyến nghị:** Giữ nguyên, clarify với stakeholder trước Giai đoạn 02.
- **Không xóa** — tránh FK violation và mất dữ liệu hiện có.

---

## 14. Test Suite

```
tests/ (133 tests, pytest 8.3.5)
├── conftest.py                   fresh_db, legacy_db, auth, session_mgr fixtures
├── test_auth_service.py          40 tests — login/logout/session/roles/injection/timing
├── test_migration.py             25 tests — MIG-001/002/003, rollback, FK, idempotent
├── test_password_hashing.py      17 tests — PBKDF2, backward compat, timing safety
├── test_session.py                9 tests — Singleton, states, roles
└── test_regression_phase00_01.py 42 tests — regression full stack phase 00+01
```

**Chạy:** `python -m pytest tests/ -v`  
**DB test:** tmp_path fixture — KHÔNG đụng `data/skillproof.db` thật.

---

*Tài liệu được cập nhật sau Giai đoạn 01.1 — SkillProof Authentication Hardening.*
