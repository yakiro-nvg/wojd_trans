# Text động: phạm vi đang nghiên cứu

Mục tiêu là dịch ngay trong UI game, giữ lịch sử/cuộn và chỉ đổi cách hiển thị trên máy người dùng. Text nhận và bản Việt có thể hiện cùng nhau; chiều gửi chỉ dịch khi người dùng chọn, xem trước và xác nhận. Không đưa bản Việt của tin nhận vào đường gửi của game.

Reader `.data` hiện tại xử lý nguồn tĩnh. Nó chưa chứng minh coverage cho tin người chơi, thông báo hay văn bản nhận trong lúc chơi. Sự kiện do server điều khiển cũng có thể chỉ gửi ID để client tra text cục bộ; không mặc định mọi chuỗi ở các màn hình này đều đến nguyên văn từ mạng.

Rà soát tĩnh hiện chia 27 nhóm màn hình. Đã quét 34 danh sách file trong PAK, đối chiếu 176 manifest và xem nội dung 154 module Lua, gồm toàn bộ 109 ứng viên theo từ khóa tên file. Index có 933 đường Lua khác nhau; 779 chưa được xem thân hàm. Còn 255 ứng viên native/SDK cần quan sát riêng, chưa phân tích thân hàm; các đường Blueprint/web cũng chưa đủ bằng chứng. Đây là inventory các đường cần kiểm chứng, chưa phải bằng chứng bao phủ toàn bộ client.

| Nhóm | Phát hiện | Trạng thái |
|---|---|---|
| Chat công cộng, đội, bang và thông báo trong chat | Có item có cấu trúc, lọc kênh, lưu trữ và dựng lại lịch sử | Cần kiểm chứng môi trường callback/UI thread |
| Chat riêng | Có đường bong bóng/lịch sử riêng, tách tên/ngày giờ/nội dung | Cần adapter riêng |
| Loa/thông báo cuộn | Có bộ nhận, thay biến và rich-text riêng | Cần adapter riêng |
| Tips/thông báo nổi | Có đường hiển thị tách chat | Cần phân loại text thô và mã thông báo |
| Thư | Tiêu đề, nội dung, người gửi và chữ ký là các trường riêng | Ưu tiên phần văn bản; giữ danh tính |
| Bang | Có thông báo/tuyên ngôn được lưu và callback cập nhật | Cần xử lý cập nhật, dữ liệu cũ và định danh |
| Giao dịch/đấu giá | Một số tên vật phẩm được tra qua ID từ template cục bộ | Không coi tên vật phẩm là văn bản server mới |
| Nhà ở/tuyển thành viên | Đã thấy mô tả nhà, tuyên ngôn và lời đăng ký; tên nhà là trường riêng | Ưu tiên prose; giữ tên/định danh |
| Chợ/quầy, phòng/đội, pet và text tự đặt khác | Một số là tên hay dữ liệu tra template; còn đường chưa xác nhận | Không dịch mù tên, ID hay chuỗi dùng làm khóa |
| NPC/nhiệm vụ, native/Blueprint/web/SDK và fallback chưa rõ | Có cả nguồn cục bộ và đường chưa quan sát | Tiếp tục rà soát, chưa kết luận nguồn mạng |

Điểm cần bảo vệ: thao tác gửi lại tin của game có thể đọc text đã render. Hiển thị song ngữ chỉ được bật khi gửi lại vẫn dùng đúng bản gốc. Kết quả dịch trễ phải gắn đúng tin, phiên và phiên bản nội dung; không thay nhầm tin sau khi đổi nhân vật, lọc kênh hoặc dựng lại lịch sử. Nếu không xác nhận được, giữ nguyên nguồn.

Phần dịch nền, giao thức cục bộ và adapter giả lập đã có kiểm thử. Việc nối vào game vẫn đang nghiên cứu; gói runtime hiện tại chưa có tính năng dịch chat. Xem [thành phần dịch nền](../chat_companion/README.md). Tài liệu công khai không mô tả offset hay cách vượt cơ chế bảo vệ.

Review probe Lua đã phát hiện thiếu bước bảo đảm dung lượng stack khi chen một lời gọi mới. Vì vậy bản probe native hiện bị vô hiệu hóa đường chạy/cài thử, chờ xác nhận API dung lượng stack và review lại. Bản dịch tĩnh đang cài không bị thay bằng probe này.

Tham khảo kiến trúc: [ChatTranslator](https://github.com/Haplo064/ChatTranslator) dùng sự kiện hiển thị chat và in kết quả cục bộ qua Dalamud; [WhatchaSay](https://github.com/Deccentric/WhatchaSay) có chọn kênh và thao tác chuẩn bị bản dịch trước khi gửi. Các API đó thuộc FFXIV/Dalamud, không chứng minh WOJD có API tương đương.
