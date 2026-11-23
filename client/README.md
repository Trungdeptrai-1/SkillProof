# Client (giao diện desktop)

`client/` là phần giao diện PySide6 chạy trong cùng tiến trình ứng dụng
desktop SkillProof. Đây không phải web client và không giao tiếp với web
server.

## Ánh xạ với mã nguồn hiện tại

| Thư mục | Vai trò dự kiến | Module hiện đang thực thi |
|---|---|---|
| `views/` | Các màn hình và cửa sổ PySide6 | `app/ui/screens/`, `app/ui/main_window.py` |
| `components/` | Widget và thành phần giao diện tái sử dụng | `app/ui/components/`, `app/ui/dialogs/` |
| `assets/` | Icon, hình ảnh và tài nguyên giao diện | `assets/icons/`, `assets/images/`; style hiện ở `app/utils/styles.py` |

`main.py` tạo `QApplication`, áp dụng stylesheet rồi hiển thị `MainWindow`.
`MainWindow` hiện dùng `QStackedWidget` và callback để điều hướng các màn
hình. Các màn hình gọi controllers trong `server/controllers/`; controller
điều phối đến các services mà không lặp lại nghiệp vụ hay kiểm tra quyền.
SessionManager vẫn được đọc để hiển thị role và thông tin người dùng.

Mã UI PySide6 thực thi vẫn ở `app/ui/`, stylesheet ở `app/utils/styles.py`,
và tài nguyên ở `assets/`. `client/views`, `client/components` và
`client/assets` là ranh giới kiến trúc, chưa phải package runtime riêng;
không có mã nguồn nào bị di chuyển trong lần tích hợp này.
