# Client (giao diện desktop)

`client/` là giao diện PySide6 chạy trong cùng tiến trình ứng dụng SkillProof.
Đây không phải web client và không giao tiếp với web server.

## Ánh xạ với mã nguồn

| Thư mục | Trách nhiệm | Mã nguồn hiện dùng |
|---|---|---|
| `views/` | Màn hình PySide6 | `client/views/` cho welcome, đăng nhập, đăng ký, dashboard và hồ sơ Candidate |
| `components/` | Widget dùng lại | `client/components/`, gồm `PasswordField` |
| `assets/` | Icon, hình ảnh và tài nguyên | `assets/`; style dùng chung hiện ở `app/utils/styles.py` |

`app/ui/main_window.py` điều phối màn hình bằng `QStackedWidget` và callback.
Các màn hình có sẵn ngoài `client/views/` (thiết lập lần đầu, hồ sơ Company
và Expert, tìm kiếm, hợp đồng và nhiệm vụ) vẫn được triển khai trong
`app/ui/screens/`. Những module tương ứng dưới `app/ui/screens/` đối với
Welcome, đăng nhập, đăng ký, dashboard và hồ sơ Candidate là lớp tương thích
để giữ nguyên các import cũ.

## Luồng MVC

View gửi yêu cầu qua controller trong `server/controllers/`; controller gọi
service phù hợp và trả kết quả về View. `MainWindow` chịu trách nhiệm điều
hướng, còn `SessionManager` cung cấp thông tin phiên đăng nhập cho giao diện.
Các màn hình Admin chưa có nghiệp vụ quản trị vẫn được ghi nhận là placeholder.

Chạy ứng dụng từ thư mục gốc bằng `python main.py`. Chạy kiểm thử bằng
`python -m pytest -q`.
