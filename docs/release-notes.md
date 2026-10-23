Bản Việt hóa dành cho người chơi, gồm bản dịch kỹ năng/boss, font tiếng Việt, các sửa giao diện và lỗi Quỳnh Các. Đợt này ưu tiên sửa 230 lỗi chữ hiển nhiên; phần soát nghĩa còn lại tiếp tục sau phát hành.

**Tải VI_PATCH.zip**. Chỉ có một gói cài đặt; không cài kèm LIM/QFONT cũ.

> **Đọc kỹ rủi ro trước khi cài:** bản dịch nạp thêm DLL để thay chữ khi game đang chạy. Có thể gây lỗi mở game, văng game hoặc bị hệ thống chống gian lận cảnh báo/chặn. Chưa có xác nhận chấp thuận từ nhà phát hành; **không thể cam kết an toàn tài khoản hay bảo đảm game luôn ổn định**.

Game dùng đường nạp chữ riêng, nhiều phần không đi qua hệ thống ngôn ngữ chuẩn của Unreal. Cách cũ chỉ thay tệp ngôn ngữ không dịch được những phần đó, trong khi dữ liệu gốc được game kiểm tra chữ ký. Vì vậy, bản hiện tại giữ nguyên các tệp dữ liệu gốc và thay chuỗi sau khi game đọc lên. Giới hạn này là lý do phải dùng cách can thiệp trên; nó không loại bỏ rủi ro.

Thoát game, giải nén và chạy **install.bat** rồi dán đường dẫn thư mục game. Nếu từng dùng bản cũ, chuyển file bắt đầu bằng `~VI_PATCH`/`~VI_QFONT` ra ngoài Content\Paks. Nếu game nằm trong Program Files hoặc Windows không cho ghi vào thư mục cài, có thể cần **Run as administrator**. Khi bản dịch yêu cầu mở lại game, thoát rồi mở lại qua launcher.

`verify.bat` kiểm tra bản đã cài; `uninstall.bat` gỡ; `rollback.bat` khôi phục một lần cài/gỡ bằng mã giao dịch được bộ cài in ra. Xem README trong ZIP để biết chi tiết.

Còn nội dung chưa dịch, câu cũ chưa soát hết và bố cục chưa kiểm tra ở mọi tỉ lệ giao diện. Khi báo lỗi, gửi tên bản phát hành, ảnh và cách tái hiện; kiểm tra thông tin riêng tư trước khi chia sẻ log.

DLL production được build từ source trong CI, tắt thu thập chuỗi và chức năng kiểm thử. Gói có checksum, bản kê file và chứng thực CI; không kèm DLL/EXE gốc của game.
