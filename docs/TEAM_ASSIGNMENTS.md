# Phân công thành viên — chuẩn hóa MVC SkillProof

`server/` và `client/` xác lập ranh giới MVC cho ứng dụng desktop. Runtime
SQLite, phần lớn service, models và PySide6 views hiện vẫn ở `app/` để giữ
tương thích. Controllers điều phối các luồng hiện có mà không di chuyển hoặc
sao chép nghiệp vụ. Xem ánh xạ chi tiết trong [server/README.md](../server/README.md)
và [client/README.md](../client/README.md).

| Thành viên / GitHub | Vai trò và module phụ trách | Nhiệm vụ lập trình thực tế tiếp theo | Nhánh Git riêng | Tiêu chí nghiệm thu và kiểm thử | PR |
|---|---|---|---|---|---|
| **Nguyễn Quốc Trung**<br>`Trungdeptrai-1` | Trưởng nhóm; tích hợp MVC, quản lý GitHub, kiểm thử tích hợp. Điều phối `server/controllers` với `app/services` và `app/ui`. | Tích hợp luồng startup, controller và views; giữ tương thích import/database, kiểm thử hồi quy và phối hợp các PR. | `feature/mvc-integration-trung` | Ứng dụng khởi động; đăng ký/login, hồ sơ Candidate/Company/Expert, hợp đồng/task và migrations không hồi quy; toàn bộ pytest, cú pháp và imports đều PASS. | Một PR tích hợp riêng, liên kết các PR thành viên và có kết quả kiểm thử. |
| **Đinh Xuân Phát**<br>`dinhxuanphat909-crypto` | Database, Model, Migration. Phụ trách ranh giới `server/database`, `server/models`; runtime hiện ở `app/database` và `app/models`. | Duy trì SQLite connection/schema và `UserModel`; mọi migration mới cần tương thích DB cũ, idempotent và giữ dữ liệu. | `feature/database-models-phat` | Kiểm thử model/database trên SQLite fixture tạm; migration có test nâng cấp/idempotence; không dùng DB người dùng. | Một PR riêng, mô tả module/migration và kết quả test. |
| **Huỳnh Ngọc Dũng**<br>`huynhdung123` | Controller, Services, phân quyền. Phụ trách `server/controllers`, `server/services`; nghiệp vụ domain hiện có ở `app/services`. | Duy trì controller điều phối đăng nhập/đăng ký/setup/profile/search/contracts/tasks; giữ việc kiểm tra quyền trong services và tương thích import cũ. | `feature/controllers-services-dung` | Test controller ↔ service; role cho phép/từ chối; session, DB lỗi và luồng nghiệp vụ liên quan; chạy pytest. | Một PR riêng, nêu rõ quy tắc phân quyền và cách kiểm thử. |
| **Nguyễn Thị Thu Thảo**<br>`thao2351220224-cmd` | Giao diện PySide6. Phụ trách ranh giới `client/views`, `client/components`, `client/assets`; runtime hiện ở `app/ui` và `assets`. | Duy trì các màn hình và widget PySide6; gọi controllers, giữ callback/navigation và stylesheet hiện có. Không chuyển hoặc nhân bản view trong giai đoạn tích hợp. | `feature/pyside6-ui-thao` | Kiểm tra cú pháp/import; smoke test luồng giao diện liên quan với Qt offscreen khi phù hợp; chạy toàn bộ pytest. | Một PR riêng, kèm mô tả thay đổi giao diện và bước kiểm tra. |

## Quy ước phối hợp

- Mỗi thành viên làm trên nhánh riêng, commit các thay đổi thực tế của mình và
  mở PR riêng; không tạo hoặc giả lập lịch sử đóng góp.
- PR phải nêu phạm vi, ảnh hưởng tới module phụ thuộc và lệnh kiểm thử đã chạy.
- Không sửa schema/migration hoặc dữ liệu SQLite nếu không thuộc phạm vi PR
  đã được thống nhất; không commit database người dùng.
- PR tích hợp của trưởng nhóm không thay thế các PR riêng của thành viên.
