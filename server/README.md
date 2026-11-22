# Server (tầng ứng dụng và dữ liệu)

`server/` mô tả phần xử lý dữ liệu, nghiệp vụ và điều phối của ứng dụng
desktop SkillProof. Đây **không** phải web server; dự án hiện chạy trực tiếp
trên máy người dùng bằng `python main.py`.

## Ánh xạ với mã nguồn hiện tại

| Thư mục | Vai trò dự kiến | Module hiện đang thực thi |
|---|---|---|
| `database/` | Kết nối SQLite, schema và migration | `app/database/connection.py`, `app/database/schema.py` |
| `models/` | Các đối tượng dữ liệu/DTO | `app/models/user_model.py`; một số model nghiệp vụ hiện khai báo trong `app/services/` |
| `services/` | Nghiệp vụ ứng dụng và truy cập dữ liệu | `app/services/` |
| `controllers/` | Điều phối luồng giữa giao diện và services | Hiện chưa có package controller riêng; `app/ui/main_window.py` điều phối màn hình và callback |

`main.py` khởi tạo logging, gọi `create_all_tables()` từ `app.database`, sau
đó tạo `QApplication` và `MainWindow`. Giao diện hiện gọi service trực tiếp
ở một số màn hình. Các thư mục trong `server/` chỉ là ranh giới kiến trúc và
điểm đặt mã nguồn trong tương lai; mã hiện tại vẫn nằm trong `app/` và không
được di chuyển hay sao chép trong nhiệm vụ này.

## Phạm vi

- Không thêm HTTP listener, API web hay tiến trình server riêng.
- Không tạo module Python placeholder; thư mục chưa có mã thực thi được giữ
  trong Git bằng `.gitkeep`.
- Khi triển khai thay đổi tiếp theo, giữ nguyên SQLite, luồng khởi động và
  hành vi hiện có; bổ sung kiểm thử hồi quy tương ứng.
