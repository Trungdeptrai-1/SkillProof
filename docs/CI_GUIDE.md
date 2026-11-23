# Hướng dẫn CI và Pull Request

Workflow `Python CI` tự kiểm tra dự án trên Ubuntu với Python 3.13 khi có Pull
Request hướng vào `main` hoặc khi có push trực tiếp lên `main`. Job kiểm tra
cú pháp Python rồi chạy toàn bộ pytest; `QT_QPA_PLATFORM=offscreen` được đặt
cho môi trường không có màn hình. Các test dùng fixture SQLite tạm, không dùng
database của người phát triển.

## Trước khi gửi Pull Request

Mỗi thành viên cần tự chạy kiểm tra trên máy mình trước khi yêu cầu review:

```powershell
python -m pip install -r requirements.txt
python -m compileall -q app tests main.py
python -m pytest tests/
```

Trên Windows PowerShell, nếu một test hoặc lệnh khởi tạo Qt cần nền tảng
offscreen, đặt biến môi trường cho phiên hiện tại:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
```

Sau khi kiểm tra local thành công:

1. Push nhánh công việc lên GitHub.
2. Tạo Pull Request, chọn `main` làm nhánh đích và nhánh công việc làm nhánh
   nguồn; điền mô tả thay đổi, cách kiểm thử và liên kết issue nếu có.
3. Chờ workflow `Python CI` bắt đầu và hoàn tất trước khi yêu cầu merge.

## Xem kết quả trên GitHub

Trên trang Pull Request, mở **Checks** (hoặc mục kiểm tra trong phần tổng
quan). Job cần theo dõi có tên **Python 3.13 tests (Ubuntu)**:

- **PASS**: job hoàn tất với dấu kiểm xanh; cả bước kiểm tra cú pháp và toàn
  bộ pytest đều thành công.
- **FAIL**: job có dấu X đỏ. Mở **Details** cạnh job để xem log và bước thất
  bại.
- **Đang chạy/chưa có kết quả**: biểu tượng đang chạy hoặc check chưa xuất
  hiện; chưa được xem là PASS và chưa đủ điều kiện merge.

## Đọc log và xử lý lỗi

Trong trang log của job, mở bước **Check Python syntax** hoặc **Run pytest**
đang thất bại. Với pytest, tìm tên test đầu tiên báo `FAILED`, đọc traceback
đến dòng lỗi trong mã/test, rồi đối chiếu với fixture và thông báo lỗi. Lỗi
cài dependency thường xuất hiện ở bước **Install dependencies**; lỗi cú pháp
sẽ xuất hiện ở bước kiểm tra cú pháp.

Sửa lỗi trên nhánh PR, chạy lại hai lệnh kiểm tra local ở trên, sau đó commit
và push cập nhật lên chính nhánh nguồn của PR. GitHub Actions sẽ chạy lại tự
động; kiểm tra kết quả mới nhất trước khi tiếp tục review/merge.

## Quy định merge

- Không merge khi check thất bại, còn đang chạy hoặc chưa có kết quả.
- Mỗi thành viên tự chạy kiểm tra cú pháp và toàn bộ test trước khi gửi PR;
  kết quả local không thay thế kết quả CI trên GitHub.
- Nhóm cần giữ check **Python 3.13 tests (Ubuntu)** là yêu cầu bắt buộc trong
  ruleset/branch protection của `main` nếu muốn GitHub chặn merge tự động khi
  CI chưa PASS. Workflow tự tạo check nhưng không tự thay đổi thiết lập bảo vệ
  nhánh.
