Bản này thay thế **v20261023-192952**, bản có lỗi chỉ dịch được một phần. **Không nên dùng bản đó:** kiểm tra hook đã từ chối nhầm một kiểu nhảy qua trạm trung gian, trả mã 13 và tắt nhánh đọc dữ liệu gốc.

Đã sửa kiểm tra đường nhảy và thêm ca tái hiện lỗi trên cả hai kiểu hook thực tế. Hook đọc dữ liệu vẫn được bật sớm để không bỏ lỡ thoại nhiệm vụ lúc game khởi động.

Giữ các bản dịch kỹ năng/boss, font tiếng Việt và sửa giao diện của bản trước. Chat translator và cách dàn chữ trong thư vẫn đang được phát triển, chưa có trong bản này; phần soát nghĩa còn lại tiếp tục sau.

**Tải VI_PATCH.zip**. Chỉ có một gói cài đặt; không cài kèm LIM/QFONT cũ.

DLL được CI tạo tự động từ mã nguồn công khai. Người có kiến thức kỹ thuật có thể kiểm tra code, lượt build và chứng thực bản phát hành. **Chỉ tải ZIP từ GitHub Releases của dự án.** Không dùng DLL gửi riêng hoặc bản sửa, bản chia sẻ lại không rõ nguồn; một DLL bị sửa với dụng ý xấu có thể gây hại cho máy hoặc đánh cắp thông tin.

> **Rủi ro từ game và Perfect World:** bản dịch nạp thêm DLL để thay chữ khi game chạy, nên có thể gây lỗi/văng game hoặc bị hệ thống chống gian lận cảnh báo/chặn. Dù dùng đúng bản phát hành của dự án, **Perfect World vẫn có thể hạn chế, đình chỉ hoặc khóa tài khoản**. Dự án chưa có xác nhận chấp thuận từ họ, không cam kết an toàn tài khoản và không chịu trách nhiệm nếu họ xử lý tài khoản vì việc sử dụng bản dịch. **Sử dụng là lựa chọn của bạn và đồng nghĩa với việc chấp nhận các rủi ro này.**

Game dùng đường nạp chữ riêng, nhiều phần không đi qua hệ thống ngôn ngữ chuẩn của Unreal. Cách cũ chỉ thay tệp ngôn ngữ không dịch được những phần đó, trong khi dữ liệu gốc được game kiểm tra chữ ký. Vì vậy, bản hiện tại giữ nguyên các tệp dữ liệu gốc và thay chuỗi sau khi game đọc lên. Giới hạn này là lý do phải dùng cách can thiệp trên; nó không loại bỏ rủi ro.

Thoát game, giải nén và chạy **install.bat** rồi dán đường dẫn thư mục game. Nếu từng dùng bản cũ, chuyển file bắt đầu bằng `~VI_PATCH`/`~VI_QFONT` ra ngoài Content\Paks. Nếu game nằm trong Program Files hoặc Windows không cho ghi vào thư mục cài, có thể cần **Run as administrator**. Khi bản dịch yêu cầu mở lại game, thoát rồi mở lại qua launcher.

`verify.bat` kiểm tra bản đã cài; `uninstall.bat` gỡ; `rollback.bat` khôi phục một lần cài/gỡ bằng mã giao dịch được bộ cài in ra. Xem README trong ZIP để biết chi tiết.

Còn nội dung chưa dịch, câu cũ chưa soát hết và bố cục chưa kiểm tra ở mọi tỉ lệ giao diện. Khi báo lỗi, gửi tên bản phát hành, ảnh và cách tái hiện; kiểm tra thông tin riêng tư trước khi chia sẻ log.

DLL production được build từ source trong CI, tắt thu thập chuỗi và chức năng kiểm thử. Gói có checksum, bản kê file và chứng thực CI; không kèm DLL/EXE gốc của game.
