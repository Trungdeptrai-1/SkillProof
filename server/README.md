# Server (tầng ứng dụng và dữ liệu)

`server/` mô tả phần xử lý dữ liệu, nghiệp vụ và điều phối của ứng dụng
desktop SkillProof. Đây **không** phải web server; dự án hiện chạy trực tiếp
trên máy người dùng bằng `python main.py`.

## Ánh xạ với mã nguồn hiện tại

| Thư mục | Vai trò dự kiến | Module hiện đang thực thi |
|---|---|---|
| `database/` | Kết nối SQLite, schema và migration | `app/database/connection.py`, `app/database/schema.py` |
| `models/` | Các đối tượng dữ liệu/DTO | `app/models/user_model.py`; một số model nghiệp vụ hiện khai báo trong `app/services/` |
| `services/` | Nghiệp vụ ứng dụng và truy cập dữ liệu | Auth/setup: `server/services/`; user/profile/search/contract/task: `app/services/` |
| `controllers/` | Điều phối luồng giữa giao diện và services | `server/controllers/`: auth, registration, setup, profile, collaboration |

`main.py` khởi tạo logging, gọi `create_all_tables()` từ `app.database`, sau
đó tạo `QApplication` và `MainWindow`. `AuthService` cùng `AuthController` đã
được triển khai cho luồng xác thực; `AdminSetupService`/`SetupController`
điều phối thiết lập Admin lần đầu. Các View hiện tại trong `app/ui/screens/`
gọi controller cho đăng nhập, đăng ký, hồ sơ, tìm chuyên gia, hợp đồng và task.
Service hiện có vẫn giữ các kiểm tra quyền theo role; controller không sao
chép nghiệp vụ. `app/services/auth_service.py` chỉ re-export các symbol từ
service canonical để giữ tương thích import; không có hai bản auth logic.

## Phạm vi

- Không thêm HTTP listener, API web hay tiến trình server riêng.
- Không tạo module Python placeholder; thư mục chưa có mã thực thi được giữ
  trong Git bằng `.gitkeep`.
- SQLite và migration hiện hữu không bị di chuyển hoặc viết lại.
- `server/database/` và `server/models/` vẫn là ranh giới kiến trúc; runtime
  tương ứng hiện nằm trong `app/`.
- Dashboard Admin và các menu placeholder chưa có nghiệp vụ quản trị users,
  skills hay settings.
