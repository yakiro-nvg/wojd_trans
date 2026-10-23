WOJD VIỆT HÓA

VI_PATCH.zip là trọn bộ cài đặt dành cho người chơi, gồm bản dịch, font
tiếng Việt và các sửa giao diện. Không cài kèm LIM/QFONT của bản cũ.

ĐỌC KỸ RỦI RO TRƯỚC KHI CÀI

Bản dịch nạp thêm DLL để thay chữ khi game đang chạy. Đây là can thiệp
trực tiếp vào client, có thể gây lỗi mở game, văng game hoặc bị hệ thống
chống gian lận cảnh báo/chặn. Chưa có xác nhận chấp thuận từ nhà phát hành.
Không thể cam kết an toàn tài khoản hay bảo đảm game luôn ổn định.
Chỉ cài nếu bạn chấp nhận những rủi ro này.

VÌ SAO PHẢI DÙNG CÁCH NÀY?

Game dùng đường nạp chữ riêng; nhiều nội dung như kỹ năng và boss không
đi qua hệ thống ngôn ngữ chuẩn của Unreal. Cách cũ chỉ thay tệp ngôn ngữ
nên không chèn được bản dịch vào những phần này. Dữ liệu gốc còn được
game kiểm tra chữ ký, nên không thể chỉ sửa rồi chép đè.

Vì vậy, bản hiện tại giữ nguyên các tệp dữ liệu gốc và thay chuỗi sau khi
game đọc lên: DLL tra nguyên câu trong từ điển rồi trả về tiếng Việt.
Giới hạn của game buộc phải dùng cách này để dịch những đường nạp đó;
đồng thời, nó mang theo các rủi ro đã nêu trên.

CÀI ĐẶT

1. Thoát game bình thường. Giải nén toàn bộ ZIP vào một thư mục riêng.
2. Nếu từng dùng bản cũ, chuyển các file bắt đầu bằng ~VI_PATCH hoặc
   ~VI_QFONT ra ngoài thư mục Content\Paks.
3. Chạy install.bat rồi dán đường dẫn thư mục game khi được hỏi.
   Có thể dùng thư mục Game, ZhuxianClient hoặc Binaries\Win64.
   Ví dụ: D:\ZXSJclient\ZXSJ\Game.
4. Mở game qua launcher như thường lệ. Nếu bản dịch yêu cầu mở lại,
   thoát game rồi mở lại.

Nếu game nằm trong Program Files hoặc thư mục bị Windows hạn chế quyền
ghi, có thể cần nhấp chuột phải install.bat > Run as administrator.
Quyền quản trị phụ thuộc nơi cài game và quyền ghi của tài khoản Windows.

CẬP NHẬT VÀ GỠ

- Cập nhật: thoát game rồi chạy install.bat của gói mới.
- Kiểm tra bản đã cài: chạy verify.bat.
- Gỡ bản dịch: thoát game rồi chạy uninstall.bat.
- Khôi phục một lần cài/gỡ: chạy rollback.bat và nhập mã giao dịch được
  bộ cài in ra. Không xóa backup hoặc tự đổi file giữa lúc khôi phục.

Các thao tác này cũng cần quyền ghi phù hợp với thư mục game. Bộ cài
không tự mở hay đóng game; nếu gặp file bị thay đổi bởi mod khác, nó sẽ
dừng để giữ nguyên file đó.

Vẫn có nội dung chưa dịch, câu cũ chưa soát hết và màn hình có thể còn
tràn/cắt chữ. Game cập nhật có thể khiến bản dịch cần được chỉnh lại.
Xem KNOWN_ISSUES.txt. Khi báo lỗi, gửi tên bản phát hành, ảnh và cách tái
hiện; kiểm tra thông tin riêng tư trước khi chia sẻ log.

Bản phát hành và hướng dẫn: https://github.com/yakiro-nvg/wojd_trans
