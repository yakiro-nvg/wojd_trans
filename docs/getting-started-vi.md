# Cài bản Việt hóa

**[Tải VI_PATCH.zip](https://github.com/yakiro-nvg/wojd_trans/releases/latest/download/VI_PATCH.zip)**. Chỉ cần chọn gói này; không cài kèm LIM/QFONT cũ.

> **Rủi ro:** bản dịch nạp thêm DLL để thay chữ khi game đang chạy. Có thể gặp lỗi mở game, văng game hoặc bị hệ thống chống gian lận cảnh báo/chặn. Chưa có xác nhận chấp thuận từ nhà phát hành; không thể cam kết an toàn tài khoản. Đọc [lý do phải dùng phương pháp này](../README.md#vì-sao-phải-dùng-cách-này) trước khi quyết định cài.

1. Thoát game bình thường, rồi giải nén toàn bộ ZIP vào một thư mục riêng.
2. Nếu từng dùng bản cũ, chuyển các file bắt đầu bằng `~VI_PATCH` hoặc `~VI_QFONT` ra ngoài thư mục `Content\Paks`.
3. Chạy **install.bat**. Khi được hỏi đường dẫn, mở thư mục game trong File Explorer, sao chép đường dẫn trên thanh địa chỉ rồi dán vào cửa sổ bộ cài.
4. Mở game qua launcher. Nếu bản dịch yêu cầu mở lại, thoát game rồi mở lại.

Bộ cài nhận thư mục **Game**, **ZhuxianClient** hoặc **Binaries\Win64**. Ví dụ: `D:\ZXSJclient\ZXSJ\Game`. Dùng đường dẫn thực tế trên máy bạn; không cần giống ví dụ.

**Quyền quản trị phụ thuộc thư mục cài game.** Nếu game nằm trong Program Files hoặc Windows báo không có quyền ghi, nhấp chuột phải file BAT và chọn **Run as administrator**. Các thao tác cài, cập nhật, kiểm tra, gỡ và khôi phục đều cần quyền truy cập phù hợp.

Để cập nhật, thoát game và chạy `install.bat` của gói mới. `verify.bat` kiểm tra bản đã cài; `uninstall.bat` gỡ bản dịch. Muốn khôi phục một lần cài/gỡ, chạy `rollback.bat` và nhập mã giao dịch được bộ cài in ra. Giữ lại backup cho đến khi chắc chắn không cần khôi phục.

Bộ cài không tự mở hay đóng game. Nếu file đã bị mod khác thay đổi, nó dừng và giữ nguyên để tránh ghi đè. Các tệp dữ liệu gốc có chữ ký không bị thay thế.

Một số câu còn CN hoặc chưa được soát hết; vài màn hình có thể còn tràn/cắt chữ. Khi báo lỗi, gửi tên bản phát hành, ảnh và cách tái hiện; kiểm tra thông tin riêng tư trước khi chia sẻ log.
