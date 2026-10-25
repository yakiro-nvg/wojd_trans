Bản phát hành này có **Đầy đủ dùng DLL** và **Legacy không DLL**, cùng bộ cài cho phép đổi qua lại khi game đã đóng.

Sửa khung chat về chiều rộng gốc và ô tab 24 × 24, giữ cỡ chữ. Mỗi nhãn tab chỉ còn tối đa hai ký tự (TH, TG, GĐ, CM, Đ, ĐN, MP, BP, CT, TD, BB, KV, HT, P, QS), áp dụng cho cả Đầy đủ và Legacy. Danh sách chọn kênh vẫn dùng tên đầy đủ. Nếu từng tự kéo rộng khung chat, có thể cần thu lại trong game vì kích thước đã được lưu riêng.

Legacy có font convert riêng áp dụng chung, lấy lại 45 cách thay chữ theo nghĩa từ bảng MVH như Kéo, Ngươi, Ăn. Tên riêng có các chữ này cũng đổi theo nghĩa; đây vẫn là thay từng chữ, không phải dịch cả câu. Bản Đầy đủ giữ font tên Hán–Việt với Lạp, Nhĩ, Cật. Cả hai dùng nét font chính, không nhập nét MVH/XF.

- **VI_PATCH.zip:** chọn Đầy đủ để dịch các đường dữ liệu riêng của game và dùng dịch chat; cũng có sẵn lựa chọn Legacy.
- **VI_LEGACY.zip:** gói riêng không chứa DLL. Giữ bản dịch locres/FormatString, các sửa bố cục và font convert riêng, nhưng phạm vi dịch hạn chế hơn và không có dịch chat tự động.

Legacy bổ sung 565.250 ID locres từ lượt log không DLL, tái dùng bản dịch đã có. Các binding widget từ đợt quét tài nguyên trước được giữ lại. Những mục chưa có bản dịch hoặc xung đột nguồn chưa được áp dụng; vẫn có thể hiện chữ Trung hay cách đọc Hán–Việt.

**Dịch chat tùy chọn trong bản Đầy đủ:** Google Translate web, DeepL, DeepSeek và Gemini; có thể chọn dịch vụ/model chung hoặc riêng từng kênh. Tin gốc và phần Việt hiện cùng một mục, giữ liên kết tên và vật phẩm. Tên đọc đặt dưới phần VI, bọc bằng 【…】. Lỗi dịch hiện tại đúng tin để dễ nhận biết. Tin hệ thống và Chiêu Mộ được bỏ qua. Lần cài đầu mặc định tắt; khi cập nhật có thể giữ thiết lập và key đã lưu. Xem CHAT_GUIDE.txt trong VI_PATCH.zip để chọn dịch vụ, model và hiểu chi phí, hạn mức, việc gửi nội dung chat tới dịch vụ.

Font tên trên đầu, đội/đoàn và nguồn hiệu ứng dùng bảng đọc Hán–Việt từ MVH cùng từ điển bổ sung, ghép bằng nét font chính. Bảng hỗ trợ 26.972 chữ, không phân biệt ngữ cảnh đa âm và không thay thế bản dịch nghĩa.

**Cài hoặc đổi bản:** thoát game, giải nén toàn bộ ZIP vào một thư mục riêng và chạy install.bat. Chọn Đầy đủ hoặc Legacy nếu được hỏi, rồi dán đường dẫn Game, ZhuxianClient hoặc Binaries\Win64. Khi chuyển sang Legacy, bộ cài gỡ DLL Việt hóa đang được quản lý; thiết lập riêng, key và lịch sử khôi phục được giữ lại. Không cài chồng LIM/QFONT cũ. Nếu còn ~VI_PATCH/~VI_QFONT trong Content\Paks, chuyển các gói cũ đó ra ngoài trước. Với thư mục bị Windows hạn chế quyền ghi, có thể cần Run as administrator.

verify.bat kiểm tra file đã cài; uninstall.bat gỡ; rollback.bat khôi phục bằng mã giao dịch. chat-settings.bat chỉ có trong gói Đầy đủ và dùng khi đã cài bản DLL. Các công cụ không tự mở hoặc đóng game.

**Chỉ tải ZIP từ GitHub Releases của dự án.** DLL bản Đầy đủ được CI tạo từ mã nguồn công khai; gói kèm checksum, bản kê file và chứng thực CI. Không dùng DLL gửi riêng hoặc bản sửa không rõ nguồn. Không gửi API key qua chat, log, ảnh hoặc livestream; nếu lộ, thu hồi tại dịch vụ rồi tạo key mới.

**Rủi ro từ game và Perfect World:** bản Đầy đủ nạp DLL khi game chạy, có thể gây lỗi hoặc bị hệ thống chống gian lận cảnh báo/chặn. Legacy chỉ sửa tài nguyên nhưng vẫn là bản sửa game. Dự án chưa có xác nhận chấp thuận từ Perfect World, không cam kết an toàn tài khoản và không chịu trách nhiệm nếu tài khoản bị hạn chế, đình chỉ hoặc khóa vì sử dụng bản dịch. Người dùng tự quyết định và chấp nhận rủi ro.

Còn câu chưa dịch hoặc chưa soát nghĩa và bố cục chưa được kiểm tra ở mọi tỉ lệ UI. Khi báo lỗi, gửi phiên bản, ảnh và thao tác tái hiện; kiểm tra thông tin riêng tư trước khi chia sẻ log.
