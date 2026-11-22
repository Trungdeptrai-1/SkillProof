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
hình. Các màn hình gọi services trong `app/services/`; phần giao diện và
nghiệp vụ vẫn được giữ nguyên vị trí hiện tại trong nhiệm vụ này.

Các thư mục trong `client/` chỉ xác lập ranh giới kiến trúc cho công việc
tiếp theo. Không có mã nguồn nào được di chuyển hoặc sao chép; thư mục trống
được Git theo dõi bằng `.gitkeep`.
