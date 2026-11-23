# Server (tầng ứng dụng và dữ liệu)

`server/` mô tả phần xử lý dữ liệu, nghiệp vụ và điều phối của ứng dụng
desktop SkillProof. Đây **không** phải web server; dự án hiện chạy trực tiếp
trên máy người dùng bằng `python main.py`.

## Ánh xạ với mã nguồn hiện tại

| Thư mục | Vai trò dự kiến | Module hiện đang thực thi |
|---|---|---|
| `database/` | Kết nối SQLite, schema và migration | `app/database/connection.py`, `app/database/schema.py` |
| `models/` | Các đối tượng dữ liệu/DTO | `app/models/user_model.py`; một số model nghiệp vụ hiện khai báo trong `app/services/` |
| `services/` | Nghiệp vụ ứng dụng và truy cập dữ liệu | Xác thực: `server/services/auth_service.py`; các nghiệp vụ khác hiện ở `app/services/` |
| `controllers/` | Điều phối luồng giữa giao diện và services | Xác thực: `server/controllers/auth_controller.py`; điều hướng màn hình vẫn ở `app/ui/main_window.py` |

`main.py` khởi tạo logging, gọi `create_all_tables()` từ `app.database`, sau
đó tạo `QApplication` và `MainWindow`. `AuthService` cùng `AuthController` đã
được triển khai cho luồng xác thực. `app/services/auth_service.py` chỉ re-export
các symbol từ service mới để giữ tương thích với các import hiện hành; không
có hai bản triển khai nghiệp vụ.

## Phạm vi

- Không thêm HTTP listener, API web hay tiến trình server riêng.
- Không tạo module Python placeholder; thư mục chưa có mã thực thi được giữ
  trong Git bằng `.gitkeep`.
- SQLite và luồng khởi động không thay đổi.
- `LoginScreen` hiện vẫn gọi `app.services.auth_service.auth_service` trực tiếp.
  Khi tích hợp controller, UI cần được phối hợp để gọi `AuthController.login()`;
  thay đổi UI nằm ngoài phạm vi triển khai này.
