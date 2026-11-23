# Server (tầng ứng dụng và dữ liệu)

`server/` mô tả phần xử lý dữ liệu, nghiệp vụ và điều phối của ứng dụng
desktop SkillProof. Đây **không** phải web server; dự án hiện chạy trực tiếp
trên máy người dùng bằng `python main.py`.

## Ánh xạ với mã nguồn hiện tại

| Thư mục | Vai trò dự kiến | Module hiện đang thực thi |
|---|---|---|
| `database/` | Kết nối SQLite, schema và migration | `app/database/connection.py`, `app/database/schema.py` |
| `models/` | Các đối tượng dữ liệu/DTO | `app/models/user_model.py`; một số model nghiệp vụ hiện khai báo trong `app/services/` |
| `services/` | Nghiệp vụ ứng dụng và truy cập dữ liệu | Xác thực, hồ sơ ứng viên, đăng ký: `server/services/` |
| `controllers/` | Điều phối luồng giữa giao diện và services | Xác thực, hồ sơ ứng viên, đăng ký: `server/controllers/`; điều hướng màn hình vẫn ở `app/ui/main_window.py` |

`main.py` khởi tạo logging, gọi `create_all_tables()` từ `app.database`, sau
đó tạo `QApplication` và `MainWindow`. Các service xác thực, hồ sơ ứng viên,
đăng ký người dùng và controller tương ứng được triển khai tại `server/`.
Các module cùng tên trong `app/services/` chỉ re-export các symbol mới để giữ
tương thích với import hiện hành; không có hai bản triển khai nghiệp vụ.

## Phạm vi

- Không thêm HTTP listener, API web hay tiến trình server riêng.
- Không tạo module Python placeholder; thư mục chưa có mã thực thi được giữ
  trong Git bằng `.gitkeep`.
- SQLite và luồng khởi động không thay đổi.
- `LoginScreen`, `RegisterScreen` và `CandidateProfileScreen` hiện vẫn gọi
  service trực tiếp qua adapter `app/services/`. Tích hợp UI sang
  `AuthController`, `UserController` và `CandidateProfileController` cần được
  phối hợp riêng; thay đổi UI nằm ngoài phạm vi triển khai này.
- Chưa có màn hình hoặc quy tắc phân quyền quản trị danh sách tài khoản, tìm
  kiếm/lọc hay đổi trạng thái người dùng; các nghiệp vụ đó chưa được thêm.
