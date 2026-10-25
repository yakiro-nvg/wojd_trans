WOJD VIỆT HÓA

VI_PATCH.zip chứa hai lựa chọn: Đầy đủ dùng DLL và Legacy không nạp DLL.
VI_LEGACY.zip là gói riêng hoàn toàn không chứa DLL. Cả hai giữ bản dịch
locres/FormatString, font và sửa giao diện; Legacy dịch được ít nội dung
hơn, không có dịch chat tự động. Không cài kèm LIM/QFONT của bản cũ.

Bản Legacy dùng font convert riêng từ nét font chính cho chữ Trung chưa
được dịch. Một số chữ được thay theo nghĩa để dễ đọc, các chữ còn lại
giữ bảng đọc Hán–Việt. Đây là thay từng chữ, không phải dịch cả câu;
chữ ngoài bảng vẫn có thể hiện chữ Trung. Nội dung tên gốc và ID giữ nguyên.

Khung chat giữ chiều rộng và kích thước tab gốc, mỗi tab tối đa hai ký tự:
TH Tổng hợp, TG Thế giới, GĐ Gần đây, CM Chiêu mộ, Đ Đội, ĐN Đoàn,
MP Môn phái, BP Bang phái, CT Chiến trường, TD Trận doanh, BB Bạn bè,
KV Khu vực, HT Hệ thống, P Phòng, QS Quan sát. Danh sách chọn kênh vẫn
ghi tên đầy đủ. Nếu từng tự kéo rộng khung chat, có thể cần thu lại trong
game vì vị trí/kích thước đã được game lưu riêng.

Legacy dùng 45 cách thay nghĩa từ MVH, như 拉 Kéo, 你 Ngươi, 吃 Ăn,
饭 Cơm; tên riêng cũng chịu cách thay chữ này. Không tách theo từng widget.
Bản Đầy đủ giữ font tên Hán–Việt với Lạp, Nhĩ, Cật. Cả hai giữ cỡ chữ
và nét font chính, không dùng nét MVH/XF.

NGUỒN TẢI VÀ AN TOÀN MÁY TÍNH

DLL trong bản Đầy đủ được tạo tự động bằng CI (GitHub Actions) từ mã
nguồn công khai của dự án. Người có kiến thức kỹ thuật có thể xem code,
quá trình build, phiên bản mã nguồn và chứng thực để tự đánh giá.

Chỉ tải ZIP từ GitHub Releases của dự án này:
https://github.com/yakiro-nvg/wojd_trans/releases

Không dùng DLL gửi riêng hoặc bản sửa, bản chia sẻ lại không rõ nguồn gốc.
DLL là mã chạy trên máy bạn; nếu bị người có dụng ý xấu sửa đổi, nó có
thể gây hại cho máy hoặc đánh cắp thông tin. Mã nguồn công khai của dự án
không bảo chứng cho một DLL do nơi khác cung cấp.

RỦI RO TỪ GAME VÀ PERFECT WORLD

Bản Đầy đủ nạp thêm DLL để thay chữ khi game đang chạy. Can thiệp này có
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

Vì vậy, bản Đầy đủ giữ nguyên các tệp dữ liệu gốc và thay chuỗi sau khi
game đọc lên: DLL tra nguyên câu trong từ điển rồi trả về tiếng Việt.
Giới hạn của game buộc phải dùng cách này để dịch những đường nạp đó;
đồng thời, nó mang theo các rủi ro đã nêu trên.

CÀI ĐẶT

1. Thoát game bình thường. Giải nén toàn bộ ZIP vào một thư mục riêng.
2. Nếu từng dùng bản cũ, chuyển các file bắt đầu bằng ~VI_PATCH hoặc
   ~VI_QFONT ra ngoài thư mục Content\Paks.
3. Chạy install.bat, chọn Đầy đủ hoặc Legacy rồi dán đường dẫn thư mục game khi được hỏi.
   Có thể dùng thư mục Game, ZhuxianClient hoặc Binaries\Win64.
   Ví dụ: D:\ZXSJclient\ZXSJ\Game.
4. Chỉ bản Đầy đủ có bước Dịch chat; Enter để không bật ở lần cài đầu. Có thể chọn
   Google Translate, DeepL, DeepSeek hoặc Gemini. Google Translate không
   cần key; ba dịch vụ còn lại cần API key riêng. DeepSeek/Gemini cho
   chọn model. Khi bật, phần chữ cần dịch được gửi tới dịch vụ đã chọn.
   Đọc CHAT_GUIDE.txt trong VI_PATCH.zip để xem cách lấy key, chọn model,
   giá tham khảo, chất lượng thử nghiệm và hạn mức.
5. Mở game qua launcher như thường lệ. Nếu bản dịch yêu cầu mở lại,
   thoát game rồi mở lại.

Nếu game nằm trong Program Files hoặc thư mục bị Windows hạn chế quyền
ghi, có thể cần nhấp chuột phải install.bat > Run as administrator.
Quyền quản trị phụ thuộc nơi cài game và quyền ghi của tài khoản Windows.

CẬP NHẬT VÀ GỠ

- Cập nhật: thoát game rồi chạy install.bat của gói mới.
- Đổi bản: thoát game, chạy install.bat và chọn Đầy đủ/Legacy. Bộ cài
  xử lý DLL đang được quản lý, giữ thiết lập chat và key riêng.
- Kiểm tra bản đã cài: chạy verify.bat.
- Đổi dịch chat (chỉ bản Đầy đủ): thoát game rồi chạy chat-settings.bat. Chọn dịch vụ/model
  mặc định, sau đó đổi riêng từng kênh hoặc tắt kênh không cần. Kênh đông
  có thể dùng Google hoặc model rẻ hơn để tiết kiệm; bạn tự chọn.
- Gỡ bản dịch: thoát game rồi chạy uninstall.bat.
- Khôi phục một lần cài/gỡ: chạy rollback.bat và nhập mã giao dịch được
  bộ cài in ra. Không xóa backup hoặc tự đổi file giữa lúc khôi phục.

GIỮ KÍN API KEY DỊCH CHAT. Người có key có thể dùng hạn mức hoặc phát
sinh phí trên tài khoản của bạn. Bộ cài che ô nhập, mã hóa key bằng
Windows và không ghi key vào log riêng; vẫn cần tránh lộ key qua chat,
log chia sẻ, ảnh chụp hoặc livestream, nhất là khi mở trang quản lý key
và màn hình biến môi trường. Nếu lỡ lộ, thu hồi key cũ tại dịch vụ rồi
tạo key mới. Xóa tin/ảnh đã gửi không vô hiệu hóa key. Xem CHAT_GUIDE.txt.

Các thao tác này cũng cần quyền ghi phù hợp với thư mục game. Bộ cài
không tự mở hay đóng game; nếu gặp file bị thay đổi bởi mod khác, nó sẽ
dừng để giữ nguyên file đó.

Vẫn có nội dung chưa dịch, câu cũ chưa soát hết và màn hình có thể còn
tràn/cắt chữ. Game cập nhật có thể khiến bản dịch cần được chỉnh lại.
Xem KNOWN_ISSUES.txt. Khi báo lỗi, gửi tên bản phát hành, ảnh và cách tái
hiện; kiểm tra thông tin riêng tư trước khi chia sẻ log.

Bản phát hành và hướng dẫn: https://github.com/yakiro-nvg/wojd_trans

TÊN ĐỘNG HÁN–VIỆT

Tên đội/đoàn và tên, tên bang trên đầu dùng cách đọc Hán–Việt từng chữ.
Tên vốn là tiếng Việt giữ nguyên. Ô tên trên đầu dùng chung nên NPC còn
chữ Trung cũng có thể được phiên âm. Chat giữ thông tin liên kết tên gốc
để thao tác đúng người chơi. Chuyển âm tên chạy tại máy, kể cả khi tắt
dịch chat cloud. Với bản Đầy đủ, đọc CHAT_GUIDE.txt để biết chi tiết.

THU LOG LEGACY

Sau khi cài Legacy, mở game qua launcher, vào các màn hình cần kiểm tra,
rồi thoát bình thường. Chạy collect-legacy-log.bat để sao lưu log game.
Công cụ chỉ đọc log và kiểm tra bản đã cài; không nạp DLL hay sửa .data.
Log phải mới hơn lần cài Legacy. Không tự gửi log hay thông tin cá nhân.

DÙNG GEMINI CHO TẤT CẢ KÊNH CHAT ĐƯỢC HỖ TRỢ

Cài bản Đầy đủ, chọn Gemini ở bước Dịch chat rồi chọn model mong muốn.
Ở bước đổi riêng theo kênh, Enter để các kênh dùng chung Gemini. Nếu
đang có thiết lập cũ, chạy chat-settings.bat và chọn lại như trên để thay
các lựa chọn theo kênh cũ. Tin hệ thống và Chiêu Mộ vẫn được bỏ qua.
Khi được hỏi key, nhập key riêng hoặc giữ key đã lưu trên máy; không
chia sẻ key với người khác. Model/dịch vụ có thể tính phí theo lượng
chat. Có thể tắt dịch chat bất cứ lúc nào mà vẫn dùng bản Việt hóa game.
