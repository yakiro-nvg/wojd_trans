# Cài bản dịch

1. Tải **VI_PATCH.zip** từ [Releases](https://github.com/yakiro-nvg/wojd_trans/releases/latest). Đây là một gói production đầy đủ, gồm hook, bản dịch, font Việt và sửa UI; không phải bản dump/debug.
2. Giải nén vào thư mục riêng. Thoát game bình thường. Nếu còn PAK dịch legacy `~VI_PATCH*`/`~VI_QFONT*`, chuyển chúng ra ngoài `Content/Paks`.
3. Chạy `install.bat`, nhập thư mục Game, ZhuxianClient hoặc Binaries\Win64. Không cần Python, compiler hoặc quyền quản trị.
4. Mở qua launcher như thường lệ. Nếu hộp thoại yêu cầu mở lại sau khi cập nhật địa chỉ, thoát rồi mở lại game.

Cập nhật bằng `install.bat` của gói mới khi game đã đóng. `verify.bat` kiểm tra file; `uninstall.bat` gỡ và phục hồi DLL có sẵn trước đó. `rollback.bat` nhận mã giao dịch được in lúc cài/gỡ để phục hồi chính giao dịch ấy. Cache, thiết lập, log và backup giữ lại trong thư mục `wojd`.

BAT gọi PowerShell có sẵn trong Windows; execution policy chỉ áp dụng cho tiến trình ấy. Có thể đọc source bộ cài trước khi chạy. Bộ cài không tải thêm code, không tự mở/đóng game và giữ nguyên file đã bị mod khác thay đổi. Đường dẫn cài không phụ thuộc máy người phát triển.

Kiểm tra checksum, source revision và workflow của release. Bộ cài không dùng hash/timestamp/kích thước EXE để chặn phiên bản; code hook vẫn được xác minh khi chạy. [Các lỗi còn lại](known-issues.txt) gồm câu cũ chưa review, nội dung còn CN và bố cục chưa thử trên mọi tỉ lệ UI. LIM/QFONT cũ không cần cài kèm.

Native DLL có rủi ro tương thích và nhà phát hành/anti-cheat; không bảo đảm ổn định hay an toàn tài khoản. Khi báo lỗi, ghi revision, thông báo và cách tái hiện; kiểm tra thông tin riêng tư trước khi chia sẻ log.
