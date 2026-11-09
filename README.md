# SkillProof

> Hệ thống quản lý và chứng nhận kỹ năng chuyên nghiệp — Desktop App

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.12-green?logo=qt)](https://doc.qt.io/qtforpython/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-lightblue?logo=sqlite)](https://sqlite.org)

---

## Giới thiệu

**SkillProof** là ứng dụng desktop giúp tổ chức quản lý kỹ năng của nhân sự hoặc học viên, bao gồm:

- Quản lý hồ sơ kỹ năng cá nhân
- Đánh giá năng lực theo chuẩn
- Cấp và xác thực chứng chỉ
- Theo dõi lộ trình học tập
- Quản lý khoá học và giảng viên

---

## Yêu cầu hệ thống

| Thành phần | Phiên bản tối thiểu |
|------------|---------------------|
| Python     | 3.13+               |
| PySide6    | 6.12.0              |
| SQLite     | tích hợp sẵn Python |
| HĐH        | Windows 10/11, macOS 13+, Ubuntu 22+ |

---

## Cài đặt

```bash
# 1. Clone dự án
git clone <repo-url>
cd SkillProof_New

# 2. Tạo môi trường ảo
python -m venv .venv

# 3. Kích hoạt môi trường ảo
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Cài đặt thư viện
pip install -r requirements.txt
```

---

## Chạy ứng dụng

```bash
python main.py
```

**Lần đầu chạy:** Ứng dụng sẽ hiển thị màn hình **Thiết lập Admin** để tạo tài khoản quản trị viên.  
Nhập họ tên, email và mật khẩu mạnh (≥8 ký tự, có chữ hoa và số).  
Mật khẩu được mã hóa bằng **PBKDF2-SHA256** với salt ngẫu nhiên — không hardcode.

---

## Chạy kiểm thử

```bash
# Chạy toàn bộ test suite
python -m pytest tests/ -v

# Chạy nhanh không verbose
python -m pytest tests/ -q
```

---

## Cấu trúc dự án

```
SkillProof_New/
├── main.py                     # Điểm vào chính
├── requirements.txt
├── README.md
├── .gitignore
│
├── app/                        # Package ứng dụng
│   ├── ui/
│   │   ├── screens/            # Các màn hình chính
│   │   │   └── welcome_screen.py
│   │   ├── components/         # Widget tái sử dụng
│   │   ├── dialogs/            # Hộp thoại
│   │   └── main_window.py      # Cửa sổ chính
│   │
│   ├── database/
│   │   ├── connection.py       # Singleton kết nối SQLite
│   │   └── schema.py           # DDL & seed data
│   │
│   ├── models/                 # Data model / business objects
│   ├── services/               # Business logic layer
│   └── utils/
│       ├── constants.py        # Hằng số toàn cục
│       ├── styles.py           # Qt Stylesheets
│       └── helpers.py          # Hàm tiện ích
│
├── assets/
│   ├── icons/
│   └── images/
│
└── data/                       # Tạo khi chạy lần đầu
    ├── skillproof.db           # File SQLite
    └── logs/                   # Log files
```

---

## Tài khoản mặc định (dev)

> ⚠️ **Giai đoạn 01.1+:** Không còn tài khoản admin hardcode.  
> Lần đầu chạy ứng dụng, màn hình **First-Run Setup** sẽ yêu cầu tạo admin với mật khẩu mạnh.  
> Mật khẩu được mã hóa PBKDF2-SHA256 (600,000 iterations, salt ngẫu nhiên).

**Nếu nâng cấp từ Giai đoạn 01 cũ** (có admin seed `admin/admin`):  
- Admin cũ bị vô hiệu hóa tự động (MIG-003).  
- Xóa `data/skillproof.db` và chạy lại để thiết lập admin mới.  
- Hoặc dùng màn hình Reset Admin khi `setup_done=reset_required`.

---

## Schema CSDL

| Bảng          | Mô tả                              |
|---------------|------------------------------------|
| `users`       | Người dùng hệ thống                |
| `skills`      | Danh mục kỹ năng                   |
| `certificates`| Chứng chỉ được cấp                 |
| `courses`     | Khoá học                           |
| `enrollments` | Đăng ký khoá học                   |
| `assessments` | Kết quả đánh giá                   |
| `app_settings`| Cài đặt ứng dụng (key-value)       |

---

## Lộ trình phát triển

- [x] Nền tảng ứng dụng (main.py, cấu trúc thư mục)
- [x] Màn hình chào mừng
- [x] Kết nối SQLite + Schema
- [x] Màn hình đăng nhập / đăng xuất (Giai đoạn 01)
- [x] First-Run Admin Setup — không hardcode mật khẩu (Giai đoạn 01.1)
- [x] PBKDF2-SHA256 per-user salt, lazy migration hash cũ (Giai đoạn 01.1)
- [x] Test suite tự động: 133 tests — auth, session, migration, regression (Giai đoạn 01.1)
- [ ] Dashboard người dùng theo role
- [ ] Quản lý kỹ năng
- [ ] Quản lý chứng chỉ
- [ ] Quản lý khoá học
- [ ] Báo cáo & thống kê
- [ ] Xuất PDF chứng chỉ

---

## Bảo mật & An toàn dữ liệu

> Các mục sau **không được** đưa lên Git / GitHub:

| Mục            | Lý do                                              |
|----------------|----------------------------------------------------|
| `.venv/`       | Môi trường ảo — cài lại bằng `pip install -r requirements.txt` |
| `data/*.db`    | Chứa dữ liệu người dùng và hash mật khẩu          |
| `data/logs/`   | Log có thể chứa thông tin nhạy cảm                |
| `.env*`        | Biến môi trường, API key                          |
| `secrets.*`    | File chứa thông tin bí mật                        |

Tất cả các mục trên đã được cấu hình trong `.gitignore`.

---

## Đóng góp

1. Fork repository
2. Tạo branch tính năng: `git checkout -b feature/ten-tinh-nang`
3. Commit: `git commit -m "feat: mô tả thay đổi"`
4. Push: `git push origin feature/ten-tinh-nang`
5. Tạo Pull Request

---

## License

MIT © 2024 SkillProof Team
