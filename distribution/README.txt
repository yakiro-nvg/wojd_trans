WOJD Việt hóa — bản production

Giải nén toàn bộ gói vào một thư mục. Thoát game bình thường, chạy
install.bat rồi nhập thư mục Game, ZhuxianClient hoặc Binaries\Win64.
Mở game qua launcher như thường lệ. Không cần Python, compiler hoặc
quyền quản trị để cài bản dịch.

Nếu trong game hiện thông báo đã cập nhật địa chỉ, thoát game rồi mở lại.
Đây là bước hiệu chỉnh sau khi client thay đổi. Bộ cài không tự mở hay
đóng game và không kiểm tra bản client bằng timestamp hoặc kích thước EXE.
Hook kiểm tra code thực tế mỗi lần chạy. Nếu không tương thích, giữ lại
nội dung thông báo để báo lỗi; không chạy thêm công cụ đọc process.

verify.bat kiểm tra các file đang cài. uninstall.bat gỡ bản dịch và phục hồi
DLL có sẵn trước khi cài, nếu trước đó thư mục game có DLL này.
Cache, thiết lập, log và lịch sử giao dịch trong thư mục wojd được giữ lại.

Mỗi lần cài/gỡ đều có mã giao dịch và backup. Muốn khôi phục chính giao
dịch đó, đóng game rồi chạy rollback.bat và nhập mã được in khi cài/gỡ.
Nếu file đã bị đổi bởi mod hay một bản cài khác, bộ cài dừng và giữ nguyên
file để tránh ghi đè. Không xóa backup hoặc đổi file giữa lúc khôi phục.

VI_PATCH.zip là gói production đầy đủ. Không cài kèm LIM/QFONT cũ. Chuyển
PAK legacy ~VI_PATCH*/~VI_QFONT* ra ngoài Content/Paks trước khi cài.

DLL trong gói là production tối ưu, tắt capture và self-test; không có
binary dump/debug. Gói này giữ hook C8, font/bố cục đã chỉnh, hai tài nguyên locres, FormatString
và bản sửa HUD S2. Hai PAK có thứ tự ưu tiên riêng được quản lý chung bởi
một bộ cài. DLL gốc của game được sao từ chính máy người dùng khi cài;
gói không phân phối DLL/EXE gốc của game.

Bản tạm còn câu dịch cũ chưa được soát nghĩa và một số bố cục chưa được
kiểm tra trong mọi màn hình/độ phân giải. Đợt này ưu tiên sửa lỗi chữ hỏng,
ký tự lẫn và lỗi hiển nhiên đã review; việc lọc từ không chứng nhận toàn bộ
bản dịch. Các tồn đọng tiếp tục được theo dõi sau đợt phát hành này.

Đây là can thiệp bằng DLL native. Tính tương thích, ổn định, an toàn tài khoản
và sự chấp thuận của nhà phát hành/anti-cheat không được bảo đảm.

Kiểm tra checksum và nguồn gói. Nếu ghi local-unpublished thì đây là bản
dựng cục bộ, chưa có chứng thực từ một lượt CI công khai. Log có thể chứa
thông tin riêng tư; chỉ chia sẻ phần liên quan sau khi kiểm tra nội dung.
