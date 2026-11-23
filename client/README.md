# Client (giao diện desktop)

`client/` là phần giao diện PySide6 chạy trong cùng tiến trình ứng dụng
desktop SkillProof. Đây không phải web client và không giao tiếp với web
server.

## Mã nguồn giao diện

| Thư mục | Vai trò dự kiến | Module hiện đang thực thi |
|---|---|---|
| `views/` | Các màn hình PySide6 | `client/views/` |
| `components/` | Widget và thành phần giao diện tái sử dụng | `client/components/` |
| `assets/` | Icon, hình ảnh và tài nguyên giao diện | `assets/icons/`, `assets/images/`; style hiện ở `app/utils/styles.py` |

Welcome, đăng nhập và đăng ký hiện được triển khai trong `client/views/`.
Các module cùng tên dưới `app/ui/screens/` là lớp chuyển tiếp để giữ nguyên
các import hiện có. `MainWindow` tiếp tục điều hướng bằng `QStackedWidget`
và callback; các màn hình gọi services trong `app/services/`.

`PasswordField` trong `client/components/` được dùng chung bởi các màn hình
đăng nhập, đăng ký và thiết lập lần đầu. Các màn hình nghiệp vụ khác vẫn ở
`app/ui/screens/` và không bị thay đổi trong lần chuyển này.
