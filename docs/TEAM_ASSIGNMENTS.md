# Phân công thành viên — chuẩn hóa MVC SkillProof

Các thư mục `server/` và `client/` trong nhiệm vụ 01 mới xác lập ranh giới
kiến trúc. Mã thực thi hiện vẫn ở `app/`; mỗi thành viên thực hiện thay đổi
thực tế ở các module hiện có, đồng thời phối hợp tích hợp theo ánh xạ trong
[server/README.md](../server/README.md) và [client/README.md](../client/README.md).

| Thành viên / GitHub | Vai trò và module phụ trách | Nhiệm vụ lập trình thực tế tiếp theo | Nhánh Git riêng | Tiêu chí nghiệm thu và kiểm thử | PR |
|---|---|---|---|---|---|
| **Nguyễn Quốc Trung**<br>`Trungdeptrai-1` | Trưởng nhóm; tích hợp MVC, quản lý GitHub, kiểm thử tích hợp. Điều phối tích hợp `server/controllers`, `server/services` và `client/views`. | Thiết kế và tích hợp thay đổi phân lớp mà không làm đổi luồng `main.py` → khởi tạo SQLite → `MainWindow`; rà soát import sau tích hợp và xử lý xung đột giữa các PR. | `feature/mvc-integration-trung` | Ứng dụng tiếp tục khởi động; luồng First-Run/Welcome/Login/Dashboard/Logout không hồi quy; chạy toàn bộ `python -m pytest tests/` và kiểm tra import. | Một PR tích hợp riêng, liên kết các PR thành viên và có kết quả kiểm thử. |
| **Đinh Xuân Phát**<br>`dinhxuanphat909-crypto` | Database, Model, Migration. Phụ trách `server/database`, `server/models`; hiện tương ứng chủ yếu với `app/database/` và `app/models/`. | Củng cố model/DTO và ranh giới truy cập SQLite theo schema hiện có; nếu có thay đổi schema trong công việc sau, viết migration tương thích dữ liệu cũ và kiểm thử nâng cấp/idempotence. | `feature/database-models-phat` | Kiểm thử model và database; migration chạy an toàn trên fixture SQLite tạm, giữ dữ liệu và có kiểm thử hồi quy; không dùng DB người dùng trong kiểm thử. | Một PR riêng, mô tả module và migration (nếu có), kèm kết quả test. |
| **Huỳnh Ngọc Dũng**<br>`huynhdung123` | Controller, Services, phân quyền. Phụ trách `server/controllers`, `server/services`; hiện services ở `app/services/`, còn điều phối màn hình chủ yếu trong `app/ui/main_window.py`. | Tách hoặc bổ sung điều phối controller phù hợp với callback/luồng màn hình hiện tại; tập trung kiểm tra quyền theo role cho nghiệp vụ và giữ các service hiện hữu tương thích. | `feature/controllers-services-dung` | Kiểm thử service/controller cho quyền truy cập hợp lệ và bị từ chối, xác thực/session và các luồng nghiệp vụ liên quan; chạy test suite hiện có. | Một PR riêng, nêu rõ quy tắc phân quyền và cách kiểm thử. |
| **Nguyễn Thị Thu Thảo**<br>`thao2351220224-cmd` | Giao diện PySide6. Phụ trách `client/views`, `client/components`, `client/assets`; hiện tương ứng với `app/ui/` và `assets/`. | Hoàn thiện các màn hình, widget dùng chung và tài nguyên giao diện; giữ tích hợp với callback của `MainWindow`, services và stylesheet hiện có. | `feature/pyside6-ui-thao` | Kiểm tra cú pháp/import; xác nhận màn hình và điều hướng hiện hữu không hồi quy; kiểm thử UI phù hợp môi trường (Qt offscreen nếu cần) và chạy test suite. | Một PR riêng, kèm mô tả thay đổi giao diện và bước kiểm tra. |

## Quy ước phối hợp

- Mỗi thành viên làm trên nhánh riêng, commit các thay đổi thực tế của mình và
  mở PR riêng; không tạo hoặc giả lập lịch sử đóng góp.
- PR phải nêu phạm vi, ảnh hưởng tới module phụ thuộc và lệnh kiểm thử đã chạy.
- Không sửa schema/migration hoặc dữ liệu SQLite nếu không thuộc phạm vi PR
  đã được thống nhất; không commit database người dùng.
- PR tích hợp của trưởng nhóm không thay thế các PR riêng của thành viên.
