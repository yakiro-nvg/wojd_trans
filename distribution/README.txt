WOJD VIỆT HÓA

VI_PATCH.zip là trọn bộ cài đặt dành cho người chơi, gồm bản dịch, font
tiếng Việt và các sửa giao diện. Không cài kèm LIM/QFONT của bản cũ.

NGUỒN TẢI VÀ AN TOÀN MÁY TÍNH

DLL trong bản phát hành được tạo tự động bằng CI (GitHub Actions) từ mã
nguồn công khai của dự án. Người có kiến thức kỹ thuật có thể xem code,
quá trình build, phiên bản mã nguồn và chứng thực để tự đánh giá.

Chỉ tải ZIP từ GitHub Releases của dự án này:
https://github.com/yakiro-nvg/wojd_trans/releases

Không dùng DLL gửi riêng hoặc bản sửa, bản chia sẻ lại không rõ nguồn gốc.
DLL là mã chạy trên máy bạn; nếu bị người có dụng ý xấu sửa đổi, nó có
thể gây hại cho máy hoặc đánh cắp thông tin. Mã nguồn công khai của dự án
không bảo chứng cho một DLL do nơi khác cung cấp.

RỦI RO TỪ GAME VÀ PERFECT WORLD

Bản dịch nạp thêm DLL để thay chữ khi game đang chạy. Can thiệp này có
thể gây lỗi mở game hoặc văng game, nhất là sau cập nhật. Dù dùng đúng
bản phát hành của dự án, hệ thống chống gian lận vẫn có thể cảnh báo/chặn.
Perfect World có thể hạn chế, đình chỉ hoặc khóa tài khoản.

Dự án chưa có xác nhận chấp thuận từ Perfect World và không cam kết an
toàn tài khoản. Bạn tự quyết định và chấp nhận các rủi ro khi sử dụng.
Dự án không chịu trách nhiệm nếu Perfect World xử lý tài khoản vì việc
sử dụng bản dịch.

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
