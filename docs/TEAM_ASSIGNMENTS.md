# Phân công thành viên — chuẩn hóa MVC SkillProof

`server/` và `client/` là các package MVC của ứng dụng desktop. Những luồng
xác thực/đăng ký, dashboard và Candidate profile dùng các package canonical;
một số màn hình Company/Expert và domain services vẫn nằm trong `app/` để giữ
tương thích. Controllers điều phối service hiện có thay vì sao chép nghiệp vụ.
Xem ánh xạ chi tiết trong [server/README.md](../server/README.md) và
[client/README.md](../client/README.md).

| Thành viên / GitHub | Vai trò và module phụ trách | Nhiệm vụ lập trình thực tế tiếp theo | Nhánh Git riêng | Tiêu chí nghiệm thu và kiểm thử | PR |
|---|---|---|---|---|---|
| **Nguyễn Quốc Trung**<br>`Trungdeptrai-1` | Trưởng nhóm; tích hợp MVC, quản lý GitHub, kiểm thử tích hợp. Điều phối `main.py`, `app/ui/main_window.py`, controllers và compatibility imports. | Tích hợp startup, điều hướng và controller/views; giữ tương thích import/database; duy trì regression tests và phối hợp PR. | `feature/mvc-integration-trung` | Ứng dụng khởi động; đăng ký/login/logout, điều hướng profile Candidate/Company/Expert, migrations và domain flows không hồi quy; pytest, cú pháp và imports PASS. | Một PR tích hợp riêng, liên kết các PR thành viên và có kết quả kiểm thử. |
| **Đinh Xuân Phát**<br>`dinhxuanphat909-crypto` | Database, Model, Migration. Phụ trách `server/database`, `server/models`; `app/database` và `app/models` giữ import tương thích. | Duy trì SQLite connection/schema, `UserModel` và migration; migration mới cần tương thích DB cũ, idempotent và giữ dữ liệu. | `feature/database-models-phat` | Kiểm thử model/database trên SQLite fixture tạm; migration có test nâng cấp/idempotence; không dùng DB người dùng. | Một PR riêng, mô tả module/migration và kết quả test. |
| **Huỳnh Ngọc Dũng**<br>`huynhdung123` | Controller, Services, phân quyền. Phụ trách `server/controllers`, `server/services`; một số profile/collaboration services còn ở `app/services`. | Duy trì controller auth/user/setup/profile/search/contracts/tasks; giữ việc kiểm tra quyền trong services và tương thích import cũ. | `feature/controllers-services-dung` | Test controller ↔ service; role cho phép/từ chối; session, DB lỗi và luồng nghiệp vụ liên quan; chạy pytest. | Một PR riêng, nêu rõ quy tắc phân quyền và cách kiểm thử. |
| **Nguyễn Thị Thu Thảo**<br>`thao2351220224-cmd` | Giao diện PySide6. Phụ trách `client/views`, `client/components`, `client/assets`; một số màn hình profile/domain tiếp tục ở `app/ui`. | Duy trì màn hình và widget PySide6; gọi controllers, giữ callback/navigation và stylesheet hiện có; không tạo màn hình giả. | `feature/pyside6-ui-thao-02` | Kiểm tra cú pháp/import; smoke test luồng giao diện với Qt offscreen khi phù hợp; kiểm tra navigation hồ sơ và chạy pytest. | Một PR riêng, kèm mô tả thay đổi giao diện và bước kiểm tra. |

## Quy ước phối hợp

- Mỗi thành viên làm trên nhánh riêng, commit các thay đổi thực tế của mình và
  mở PR riêng; không tạo hoặc giả lập lịch sử đóng góp.
- PR phải nêu phạm vi, ảnh hưởng tới module phụ thuộc và lệnh kiểm thử đã chạy.
- Không sửa schema/migration hoặc dữ liệu SQLite nếu không thuộc phạm vi PR
  đã được thống nhất; không commit database người dùng.
- PR tích hợp của trưởng nhóm không thay thế các PR riêng của thành viên.
