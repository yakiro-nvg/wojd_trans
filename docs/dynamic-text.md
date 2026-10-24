# Text động và dịch chat

Bản Đầy đủ hiện có dịch chat nhận Trung → Việt ngay trong cửa sổ chat của game. Người dùng chọn Google Translate web, DeepL, DeepSeek hoặc Gemini; có thể chọn dịch vụ/model cho từng kênh. Tính năng mặc định tắt khi cài mới, không có trong Legacy. [Hướng dẫn cho người chơi](../distribution/CHAT_GUIDE.txt).

Tin gốc, liên kết người chơi/vật phẩm và metadata được giữ lại. Phần Việt nằm dưới tin gốc trong cùng mục; kết quả đến trễ phải khớp đúng phiên và tin đang hiển thị. Cuộn lịch sử, đổi tab và dùng lại cache không tạo thêm tin gốc. Lỗi được đính vào tin tương ứng. Tin hệ thống và Chiêu Mộ được bỏ qua. Nội dung dịch chỉ hiển thị tại máy người dùng, không đưa vào đường gửi hoặc gửi lại tin của game.

Dịch vụ được gọi ở luồng nền của native runtime, không yêu cầu cài Python hay chạy dịch vụ ngoài cho người chơi. Key được mã hóa bằng Windows, cache chỉ nằm trong RAM và có giới hạn số mục, dung lượng, thời gian không dùng. Bật dịch chat đồng nghĩa gửi phần chữ cần dịch tới dịch vụ đã chọn; không tự chuyển sang dịch vụ khác khi lỗi.

## Các đường còn nghiên cứu

Chat riêng dạng bong bóng, loa/thông báo cuộn, thư, tuyên ngôn bang, mô tả nhà và các phần text tự đặt khác có đường dựng/cập nhật riêng. Tính năng chat nhận không chứng minh đã bao phủ chúng. Các thông báo do server điều khiển có thể chỉ gửi ID để client tra template cục bộ, không mặc định mọi chữ đều được gửi nguyên văn qua mạng.

Reader `.data`, locres và FormatString giữ vai trò riêng. Bản dịch tĩnh không chứng minh coverage cho mọi text động. Các thử nghiệm Python/Lua trong [chat_companion](../chat_companion/README.md) là công cụ phát triển cũ và fixture; người chơi không cần chúng cho dịch chat native hiện tại. Những adapter chưa được đưa vào production vẫn cần bằng chứng về callback, phiên/tin, lịch sử, nguồn gốc nội dung và giữ nguyên đường gửi.

Các phép thử tổng hợp kiểm tra cấu trúc và hành vi cụ thể, không chứng minh tương thích mọi phiên bản client, nghĩa của mọi bản dịch hay sự chấp thuận của nhà phát hành.
