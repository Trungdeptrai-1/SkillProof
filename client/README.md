# Client (giao diện desktop)

`client/` là giao diện PySide6 chạy trong cùng tiến trình ứng dụng SkillProof.
Đây không phải web client và không giao tiếp với web server.

## Ánh xạ với mã nguồn

| Thư mục | Trách nhiệm | Mã nguồn hiện dùng |
|---|---|---|
| `views/` | Màn hình PySide6 | `client/views/` chứa toàn bộ màn hình PySide6 đang dùng |
| `components/` | Widget dùng lại | `client/components/`, gồm `PasswordField` và `StatusBanner` |
| `assets/` | Icon, hình ảnh và tài nguyên | `assets/`; style dùng chung hiện ở `app/utils/styles.py` |

Các màn hình triển khai hiện nằm trong `client/views/`, gồm xác thực, thiết
lập lần đầu, dashboard theo vai trò, hồ sơ, tìm kiếm chuyên gia, hợp đồng,
nhiệm vụ, giao diện quản trị và các luồng tuyển dụng/thi trắc nghiệm.
`app/ui/main_window.py` điều phối chúng bằng
`QStackedWidget` và callback. Các module tương ứng dưới `app/ui/screens/` là
lớp tương thích để giữ nguyên các import cũ.

## Luồng MVC

View gửi yêu cầu qua controller trong `server/controllers/`; controller gọi
service phù hợp và trả kết quả về View. `MainWindow` chịu trách nhiệm điều
hướng, còn `SessionManager` cung cấp thông tin phiên đăng nhập cho giao diện.
Company và Expert Profile, tìm kiếm, hợp đồng, nhiệm vụ và xác thực sử dụng
Controller hiện có. Admin Dashboard không tạo số liệu giả. Giao diện quản lý
người dùng và kỹ năng được kiểm thử qua Controller mock; các thao tác thật vẫn
chờ User Management và Skill Controller tương ứng.

## Tuyển dụng và bài thi

`CompanyRecruitmentScreen` và `CandidateAssessmentScreen` định nghĩa luồng View
cho vị trí tuyển dụng, bài thi, lời mời, đáp án và kết quả. Các kiểu dữ liệu và
Protocol Controller nằm trong `client/views/recruitment_contracts.py`.
Hiện chưa có Recruitment/Candidate Assessment Controller, bảng vị trí tuyển
dụng hoặc `docs/RECRUITMENT_CONTRACT.md` (schema hiện có các bảng bài thi/phiên
thi nhưng chưa có Controller tương ứng). Các màn hình mặc định khóa tải/lưu/nộp,
không truy vấn SQLite và không hiển thị dữ liệu giả. Tích hợp backend có thể
truyền Controller tương ứng vào `MainWindow`; UI được kiểm thử tương tác bằng
mock.

Chạy ứng dụng từ thư mục gốc bằng `python main.py`. Chạy kiểm thử bằng
`python -m pytest -q`.
