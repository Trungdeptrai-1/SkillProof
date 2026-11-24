# Server (tầng ứng dụng và dữ liệu)

`server/` mô tả tầng dữ liệu, nghiệp vụ và điều phối của ứng dụng desktop
SkillProof. Đây **không** phải web server; ứng dụng chạy trực tiếp trên máy
người dùng bằng `python main.py`.

## Ánh xạ với mã nguồn

| Thư mục | Trách nhiệm | Mã nguồn hiện dùng |
|---|---|---|
| `database/` | Kết nối SQLite, schema và migration | `server/database/`; các import cũ trong `app/database/` được giữ tương thích |
| `models/` | Đối tượng dữ liệu và DTO | Các model tài khoản, tuyển dụng, bài thi, phỏng vấn và chứng chỉ trong `server/models/` |
| `services/` | Xử lý nghiệp vụ và truy cập dữ liệu | `server/services/` gồm xác thực, đăng ký, hồ sơ, quản trị Admin, tuyển dụng và bài thi |
| `controllers/` | Điều phối yêu cầu từ View tới Service | `server/controllers/` gồm auth, user, setup, profile, collaboration, admin, recruitment và exam |

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
- `RecruitmentService` và `ExamService` điều phối nghiệp vụ qua các hợp đồng
  `RecruitmentModel`/`ExamModel`. MIG-006 và các DTO tuyển dụng đã có trên
  `RecruitmentRepository` triển khai các phương thức persistence đó trên cùng
  SQLite singleton và trả record dạng Mapping. Integration tests chạy các
  Services thật trên SQLite tạm.
- `question_bank.expert_id` tiếp tục lưu đúng tác giả Expert. Repository chỉ
  tạo câu hỏi khi có `expert_id` của Expert đang có contract `active` với
  Company; không gán Company ID vào trường này. Company UI lấy danh sách
  Expert có hợp đồng đang hoạt động qua `ExamController` và yêu cầu chọn tác giả;
  Service truyền ID đã chọn tới repository, nơi quyền sở hữu được xác minh lại.
  MIG-006 có `expires_at` cho lời mời;
  Service kiểm tra hạn khi chấp nhận. Thời lượng bài thi được kiểm tra từ
  `duration_min`: Service chặn xem/sửa đáp án sau khi hết giờ, nhưng vẫn chấm
  các câu đã lưu khi ứng viên nộp bài.
- MIG-007 bổ sung nhật ký sự kiện phiên thi bất biến; test cases Coding Test
  dùng lại `question_bank.test_cases`, còn câu tự luận/mã nguồn được lưu tại
  `exam_answers.answer_text`/`answer_code`. Repository hỗ trợ lập lịch và lưu
  đánh giá phỏng vấn, cấp/xác minh/thu hồi chứng chỉ trên SQLite hiện có.
- Chạy kiểm thử bằng `python -m pytest -q`; kiểm tra cú pháp bằng
  `python -m compileall -q app client server tests`.

## Admin data models

- `UserModel` maps the existing `users` table, including `is_active` and the
  MIG-005 `is_deleted` soft-delete flag. Legacy rows without that column map
  to `is_deleted=False`; passwords are never part of the model.
- `SkillModel` maps `skills`; `AppSettingModel` maps the existing key/value
  `app_settings` table.
- `AdminStatisticsModel.from_row()` maps aggregate aliases for user, skill,
  certificate, course, enrollment, and assessment counts. Active/inactive
  user counts exclude soft-deleted users; total users includes them.
- These tables and fields already exist. No new schema migration is required;
  MIG-005 upgrades older databases with `users.is_deleted`.
