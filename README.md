# WOJD Việt hóa

Bản Việt hóa cộng đồng, gồm bản dịch, font tiếng Việt và các sửa giao diện.

**[Đầy đủ / chọn bản — VI_PATCH.zip](https://github.com/yakiro-nvg/wojd_trans/releases/latest/download/VI_PATCH.zip)** · **[Legacy không DLL — VI_LEGACY.zip](https://github.com/yakiro-nvg/wojd_trans/releases/latest/download/VI_LEGACY.zip)** · [Xem bản phát hành](https://github.com/yakiro-nvg/wojd_trans/releases/latest)

Bộ cài có hai lựa chọn: **Đầy đủ** dùng DLL để dịch các đường dữ liệu riêng và hỗ trợ dịch chat; **Legacy** chỉ dùng PAK chứa locres, FormatString, bố cục và font convert riêng. `VI_LEGACY.zip` là ZIP riêng không chứa DLL. Legacy dịch được ít nội dung hơn; font lấy lại 45 cách thay chữ theo nghĩa từ MVH như “Ngươi / Ăn / Kéo”, áp dụng chung cả tên riêng, còn lại giữ bảng đọc Hán–Việt. Đây là thay từng chữ, không dịch cả câu chat. Bản Đầy đủ giữ font tên Hán–Việt. [Chi tiết Legacy và cách thu log](docs/legacy-vi.md).

Khung chat giữ chiều rộng gốc, mỗi nhãn tab tối đa hai ký tự; danh sách chọn kênh vẫn hiển thị tên đầy đủ.

## Nguồn tải và rủi ro cần biết

**Nguồn phát hành có thể kiểm tra.** DLL trong bản phát hành được tạo tự động bằng CI (GitHub Actions) từ [mã nguồn công khai](native/) của dự án. Người có kiến thức kỹ thuật có thể xem code, [quá trình build](https://github.com/yakiro-nvg/wojd_trans/actions/workflows/build.yml), phiên bản mã nguồn và chứng thực đi kèm để tự đánh giá.

**Chỉ tải ZIP từ GitHub Releases của dự án này.** Không dùng DLL gửi riêng hoặc bản sửa, bản chia sẻ lại không rõ nguồn gốc. DLL là mã chạy trên máy bạn; nếu bị người có dụng ý xấu sửa đổi, nó có thể gây hại cho máy hoặc đánh cắp thông tin. Mã nguồn công khai của dự án không bảo chứng cho một DLL do nơi khác cung cấp.

> **Rủi ro từ game và Perfect World là vấn đề riêng**
>
> Bản đầy đủ nạp thêm DLL để thay chữ khi game đang chạy. Can thiệp này có thể gây lỗi mở game hoặc văng game, nhất là sau cập nhật. Dù dùng đúng bản phát hành của dự án, hệ thống chống gian lận vẫn có thể cảnh báo/chặn và **Perfect World có thể hạn chế, đình chỉ hoặc khóa tài khoản**.
>
> Dự án chưa có xác nhận chấp thuận từ Perfect World và **không cam kết an toàn tài khoản**. Bạn tự quyết định và chấp nhận các rủi ro khi sử dụng. **Dự án không chịu trách nhiệm nếu Perfect World xử lý tài khoản vì việc sử dụng bản dịch.**

## Vì sao phải dùng cách này?

Game dùng đường nạp văn bản riêng: nhiều nội dung, trong đó có kỹ năng và boss, không đi qua hệ thống ngôn ngữ chuẩn của Unreal. Cách cũ chỉ thay tệp ngôn ngữ nên không chèn được bản dịch vào những đường nạp này. Các tệp dữ liệu gốc lại được game kiểm tra chữ ký, nên cũng không thể chỉ sửa rồi chép đè.

Vì giới hạn đó, bản đầy đủ thay chữ **sau khi game đọc dữ liệu lên**. Các tệp dữ liệu gốc được giữ nguyên; DLL tra nguyên câu trong từ điển rồi trả về bản tiếng Việt. Đây là lý do cần phương pháp can thiệp nêu trên, và cũng là nguồn rủi ro cần cân nhắc.

```mermaid
flowchart TD
    Data["Dữ liệu gốc của game<br/>Giữ nguyên, không sửa chữ ký"] --> Read["Game đọc ra chuỗi chữ"]
    Read --> Hook["DLL bản Việt hóa<br/>Tra nguyên câu trong từ điển"]
    Dict["Từ điển tiếng Việt"] --> Hook
    Hook --> Result["Có bản dịch: trả tiếng Việt<br/>Chưa có: giữ nguyên chữ gốc"]
    Result --> UI["Giao diện game"]
    Other["Chữ đi qua tệp ngôn ngữ<br/>hoặc FormatString"] --> Pak["Gói bản dịch, font<br/>và sửa giao diện"]
    Pak --> UI
    classDef intervention fill:#fff0d9,stroke:#bc6400,stroke-width:3px,color:#452300;
    class Hook intervention;
```

**Ô màu cam là phần can thiệp khi game đang chạy.** Luồng thay tệp ngôn ngữ vẫn được dùng cho các phần hỗ trợ nó; riêng các đường dữ liệu nêu trên cần DLL để chèn bản dịch.

## Cài đặt

1. Thoát game bình thường. Tải **VI_PATCH.zip** để dùng Đầy đủ hoặc chọn bản; tải **VI_LEGACY.zip** nếu muốn gói riêng không chứa DLL.
2. Giải nén toàn bộ ZIP vào một thư mục riêng.
3. Chạy **install.bat**, chọn Đầy đủ hoặc Legacy, rồi dán đường dẫn thư mục game khi được hỏi. [Hướng dẫn chọn thư mục](docs/getting-started-vi.md).
4. Với bản Đầy đủ, ở bước **Dịch chat**, chọn tắt hoặc chọn Google Translate, DeepL, DeepSeek hay Gemini. Lần cài đầu mặc định tắt; Google Translate không cần key, ba dịch vụ còn lại cần API key riêng. DeepSeek/Gemini cho chọn model. Khi bật, phần chữ cần dịch được gửi tới dịch vụ đã chọn. [So sánh giá, chất lượng thử nghiệm và hướng dẫn](distribution/CHAT_GUIDE.txt).
5. Mở game qua launcher như thường lệ. Nếu bản dịch yêu cầu mở lại game, thoát rồi mở lại.

Nếu game nằm trong **Program Files** hoặc thư mục bị Windows hạn chế quyền ghi, bạn có thể cần nhấp chuột phải **install.bat → Run as administrator**. Quyền này phụ thuộc nơi cài game và quyền ghi của tài khoản Windows.

Nếu từng dùng bản dịch cũ, chuyển các file bắt đầu bằng `~VI_PATCH` hoặc `~VI_QFONT` ra ngoài thư mục `Content\Paks` trước khi cài. Chọn bản Đầy đủ hoặc Legacy trong bộ cài mới; không cài kèm LIM/QFONT cũ.

## Cập nhật, kiểm tra và gỡ

- **Cập nhật:** thoát game rồi chạy `install.bat` của gói mới.
- **Đổi Đầy đủ/Legacy:** thoát game, chạy `install.bat` và chọn bản muốn dùng. Bộ cài gỡ hoặc khôi phục DLL do dự án quản lý, giữ thiết lập riêng và lịch sử khôi phục.
- **Kiểm tra bản đã cài:** chạy `verify.bat`.
- **Gỡ bản dịch:** thoát game rồi chạy `uninstall.bat`.
- **Khôi phục một lần cài/gỡ:** chạy `rollback.bat` và nhập mã giao dịch mà bộ cài đã in ra.
- **Đổi dịch chat — bản Đầy đủ:** thoát game rồi chạy `chat-settings.bat`. Chọn dịch vụ/model mặc định, sau đó đổi riêng từng kênh hoặc tắt kênh không cần. Kênh đông có thể dùng Google hoặc model rẻ hơn để tiết kiệm; bạn tự chọn. Khi cập nhật, bộ cài cho giữ thiết lập hiện tại.

Legacy không có bước chọn dịch chat. Trong bản Đầy đủ, tin hệ thống và Chiêu Mộ được bỏ qua; dịch chat gửi nội dung cần dịch tới dịch vụ bạn chọn.

**Giữ kín API key khi dùng dịch chat.** Người có key có thể dùng hạn mức hoặc phát sinh phí trên tài khoản của bạn. Bộ cài che chỗ nhập, mã hóa key bằng Windows và không ghi key vào log riêng; bạn vẫn cần tránh để key xuất hiện trong chat/log chia sẻ, ảnh chụp, livestream, trang quản lý key hoặc màn hình biến môi trường. Nếu lỡ lộ, thu hồi key cũ tại dịch vụ và tạo key mới; chỉ xóa ảnh/tin nhắn chưa vô hiệu hóa key.

Tên người chơi trong đội/đoàn, tên và tên bang trên đầu được hỗ trợ cách đọc Hán–Việt. Trong chat, thông tin liên kết tên gốc được giữ để thao tác đúng người chơi. Bước chuyển âm chạy tại máy, cả khi tắt dịch chat cloud. [Phạm vi và giới hạn](docs/font-customization-vi.md).

Các thao tác kiểm tra/gỡ/khôi phục cũng cần quyền ghi phù hợp với thư mục game. Bộ cài không tự mở hay đóng game.

## Những điểm còn tồn đọng

Một số nội dung còn tiếng Trung hoặc dùng bản dịch cũ chưa được soát hết. Vài màn hình có thể còn tràn/cắt chữ ở những tỉ lệ giao diện chưa kiểm tra. Game cập nhật cũng có thể khiến bản dịch cần được chỉnh lại.

Khi [báo lỗi](https://github.com/yakiro-nvg/wojd_trans/issues), gửi tên bản phát hành, ảnh lỗi và thao tác để tái hiện. Kiểm tra thông tin riêng tư trước khi gửi log.

---

Dành cho người đóng góp: [Phát triển bản dịch](docs/contributing-vi.md) · [Phương pháp và giới hạn](docs/methodology.md) · [Build và phát hành](docs/release-process.md) · [Credit font](docs/font-credits.txt).
