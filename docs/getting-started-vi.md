# Cài bản Việt hóa

**[Tải VI_PATCH.zip](https://github.com/yakiro-nvg/wojd_trans/releases/latest/download/VI_PATCH.zip)**. Gói này cho chọn Đầy đủ hoặc Legacy; [VI_LEGACY.zip](https://github.com/yakiro-nvg/wojd_trans/releases/latest/download/VI_LEGACY.zip) là ZIP riêng không chứa DLL. Không cài kèm LIM/QFONT cũ. [Giới hạn Legacy](legacy-vi.md).

DLL được CI tạo tự động từ [mã nguồn công khai](../native/) của dự án. Người có kiến thức kỹ thuật có thể kiểm tra code, [quá trình build](https://github.com/yakiro-nvg/wojd_trans/actions/workflows/build.yml) và chứng thực bản phát hành. Chỉ tải ZIP từ GitHub Releases của dự án; không dùng DLL gửi riêng hoặc bản sửa, bản chia sẻ lại không rõ nguồn. DLL bị người có dụng ý xấu sửa đổi có thể gây hại cho máy hoặc đánh cắp thông tin.

> **Rủi ro từ game và Perfect World:** bản dịch can thiệp khi game đang chạy, nên có thể gây lỗi/văng game hoặc bị hệ thống chống gian lận cảnh báo/chặn. Dù dùng đúng bản phát hành của dự án, **Perfect World vẫn có thể hạn chế, đình chỉ hoặc khóa tài khoản**. Chưa có xác nhận chấp thuận từ Perfect World; dự án không cam kết an toàn tài khoản và không chịu trách nhiệm nếu họ xử lý tài khoản vì việc sử dụng bản dịch. **Việc sử dụng là lựa chọn của bạn và đồng nghĩa với việc chấp nhận các rủi ro này.**

Đọc [lý do phải dùng phương pháp này và sơ đồ hoạt động](../README.md#vì-sao-phải-dùng-cách-này) trước khi quyết định cài.

1. Thoát game bình thường, rồi giải nén toàn bộ ZIP vào một thư mục riêng.
2. Nếu từng dùng bản cũ, chuyển các file bắt đầu bằng `~VI_PATCH` hoặc `~VI_QFONT` ra ngoài thư mục `Content\Paks`.
3. Chạy **install.bat**, chọn Đầy đủ hoặc Legacy. Khi được hỏi đường dẫn, mở thư mục game trong File Explorer, sao chép đường dẫn trên thanh địa chỉ rồi dán vào cửa sổ bộ cài.
4. Chỉ bản Đầy đủ có bước **Dịch chat**; Enter để không bật ở lần cài đầu. Có thể chọn Google Translate (không key), DeepL, DeepSeek hoặc Gemini (API key riêng); DeepSeek/Gemini cho chọn model. Bật tính năng đồng nghĩa với việc gửi phần chữ cần dịch tới dịch vụ đã chọn. [So sánh giá, lấy key, đổi model và xử lý lỗi](../distribution/CHAT_GUIDE.txt).
5. Mở game qua launcher. Nếu bản dịch yêu cầu mở lại, thoát game rồi mở lại.

Bộ cài nhận thư mục **Game**, **ZhuxianClient** hoặc **Binaries\Win64**. Ví dụ: `D:\ZXSJclient\ZXSJ\Game`. Dùng đường dẫn thực tế trên máy bạn; không cần giống ví dụ.

**Quyền quản trị phụ thuộc thư mục cài game.** Nếu game nằm trong Program Files hoặc Windows báo không có quyền ghi, nhấp chuột phải file BAT và chọn **Run as administrator**. Các thao tác cài, cập nhật, kiểm tra, gỡ và khôi phục đều cần quyền truy cập phù hợp.

Để cập nhật, thoát game và chạy `install.bat` của gói mới. `verify.bat` kiểm tra bản đã cài; `uninstall.bat` gỡ bản dịch. Muốn khôi phục một lần cài/gỡ, chạy `rollback.bat` và nhập mã giao dịch được bộ cài in ra. Giữ lại backup cho đến khi chắc chắn không cần khôi phục.

Với bản Đầy đủ, muốn đổi dịch chat thì thoát game rồi chạy **chat-settings.bat**. Legacy không có tính năng này. Chọn dịch vụ/model mặc định rồi đổi riêng từng kênh hoặc tắt kênh không cần. Kênh đông có thể dùng Google hoặc model rẻ hơn để tiết kiệm; Đội/Đoàn có thể dùng LLM khi cần giao tiếp. Bạn tự chọn các thiết lập này. Tắt dịch chat vẫn giữ phần Việt hóa game. Khi cập nhật, Enter ở bước chọn chat giữ thiết lập hiện tại.

**API key là thông tin bí mật:** người có key có thể dùng hạn mức hoặc phát sinh phí trên tài khoản của bạn. Bộ cài che ô nhập, mã hóa key bằng Windows và không ghi key vào log riêng; hãy tránh lộ key qua chat/log chia sẻ, ảnh chụp hoặc livestream, nhất là khi mở trang quản lý key và biến môi trường. Nếu lỡ lộ, thu hồi key cũ tại dịch vụ rồi tạo key mới; xóa ảnh/tin nhắn không vô hiệu hóa key.

Bộ cài không tự mở hay đóng game. Nếu file đã bị mod khác thay đổi, nó dừng và giữ nguyên để tránh ghi đè. Các tệp dữ liệu gốc có chữ ký không bị thay thế.

Một số câu còn CN hoặc chưa được soát hết; vài màn hình có thể còn tràn/cắt chữ. Khi báo lỗi, gửi tên bản phát hành, ảnh và cách tái hiện; kiểm tra thông tin riêng tư trước khi chia sẻ log.

Đổi bản bằng `install.bat` khi game đã đóng. Legacy gỡ DLL Việt hóa đang được bộ cài quản lý; dữ liệu và DLL gốc của game được giữ hoặc khôi phục. Thiết lập riêng và key chat giữ lại để dùng khi quay về Đầy đủ.
