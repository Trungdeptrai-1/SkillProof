# Server (tầng ứng dụng và dữ liệu)

`server/` mô tả tầng dữ liệu, nghiệp vụ và điều phối của ứng dụng desktop
SkillProof. Đây **không** phải web server; ứng dụng chạy trực tiếp trên máy
người dùng bằng `python main.py`.

## Ánh xạ với mã nguồn

| Thư mục | Trách nhiệm | Mã nguồn hiện dùng |
|---|---|---|
| `database/` | Kết nối SQLite, schema và migration | `server/database/`; các import cũ trong `app/database/` được giữ tương thích |
| `models/` | Đối tượng dữ liệu và DTO | `server/models/` và một số model nghiệp vụ trong services cũ |
| `services/` | Nghiệp vụ ứng dụng và truy cập dữ liệu | Xác thực, đăng ký, thiết lập Admin, hồ sơ Candidate và quản trị Admin ở `server/services/`; một số nghiệp vụ hồ sơ Company/Expert, tìm kiếm, hợp đồng và nhiệm vụ vẫn ở `app/services/` |
| `controllers/` | Điều phối yêu cầu từ View tới service | `server/controllers/` gồm auth, user, setup, profile, collaboration và admin |

`main.py` khởi tạo logging, tạo schema rồi khởi chạy `QApplication` và
`MainWindow`. `MainWindow` điều phối điều hướng giao diện; View gọi controller,
controller chuyển tiếp tới service và không sao chép nghiệp vụ. Các module
legacy trong `app/` được giữ lại cho tương thích import; chúng không phải
những bản triển khai nghiệp vụ song song.

## Phạm vi và kiểm thử

- Không có HTTP listener hay tiến trình server riêng.
- SQLite và migration hiện hữu được giữ nguyên; kiểm thử dùng database tạm.
- `AdminController` và `AdminService` hỗ trợ tìm/lọc tài khoản, khóa/mở khóa
  tài khoản (bảo vệ Admin hoạt động cuối cùng), quản lý kỹ năng bằng trạng thái
  kích hoạt và thống kê users/profiles/skills. Cấu hình ứng dụng vẫn chưa có
  nghiệp vụ quản trị và tiếp tục là placeholder.
- Chạy kiểm thử bằng `python -m pytest -q`; kiểm tra cú pháp bằng
  `python -m compileall -q app client server tests`.
