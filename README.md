# WOJD Việt hóa

Bản Việt hóa cộng đồng, gồm bản dịch, font tiếng Việt và các sửa giao diện.

**[Tải VI_PATCH.zip](https://github.com/yakiro-nvg/wojd_trans/releases/latest/download/VI_PATCH.zip)** · [Xem bản phát hành](https://github.com/yakiro-nvg/wojd_trans/releases/latest)

## Nguồn tải và rủi ro cần biết

**Nguồn phát hành có thể kiểm tra.** DLL trong bản phát hành được tạo tự động bằng CI (GitHub Actions) từ [mã nguồn công khai](native/) của dự án. Người có kiến thức kỹ thuật có thể xem code, [quá trình build](https://github.com/yakiro-nvg/wojd_trans/actions/workflows/build.yml), phiên bản mã nguồn và chứng thực đi kèm để tự đánh giá.

**Chỉ tải ZIP từ GitHub Releases của dự án này.** Không dùng DLL gửi riêng hoặc bản sửa, bản chia sẻ lại không rõ nguồn gốc. DLL là mã chạy trên máy bạn; nếu bị người có dụng ý xấu sửa đổi, nó có thể gây hại cho máy hoặc đánh cắp thông tin. Mã nguồn công khai của dự án không bảo chứng cho một DLL do nơi khác cung cấp.

> **Rủi ro từ game và Perfect World là vấn đề riêng**
>
> Bản dịch nạp thêm DLL để thay chữ khi game đang chạy. Can thiệp này có thể gây lỗi mở game hoặc văng game, nhất là sau cập nhật. Dù dùng đúng bản phát hành của dự án, hệ thống chống gian lận vẫn có thể cảnh báo/chặn và **Perfect World có thể hạn chế, đình chỉ hoặc khóa tài khoản**.
>
> Dự án chưa có xác nhận chấp thuận từ Perfect World và **không cam kết an toàn tài khoản**. Bạn tự quyết định và chấp nhận các rủi ro khi sử dụng. **Dự án không chịu trách nhiệm nếu Perfect World xử lý tài khoản vì việc sử dụng bản dịch.**

## Vì sao phải dùng cách này?

Game dùng đường nạp văn bản riêng: nhiều nội dung, trong đó có kỹ năng và boss, không đi qua hệ thống ngôn ngữ chuẩn của Unreal. Cách cũ chỉ thay tệp ngôn ngữ nên không chèn được bản dịch vào những đường nạp này. Các tệp dữ liệu gốc lại được game kiểm tra chữ ký, nên cũng không thể chỉ sửa rồi chép đè.

Vì giới hạn đó, bản hiện tại phải thay chữ **sau khi game đọc dữ liệu lên**. Các tệp dữ liệu gốc được giữ nguyên; DLL tra nguyên câu trong từ điển rồi trả về bản tiếng Việt. Đây là lý do cần phương pháp can thiệp nêu trên, và cũng là nguồn rủi ro cần cân nhắc.

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

1. Thoát game bình thường và tải **VI_PATCH.zip** ở liên kết phía trên.
2. Giải nén toàn bộ ZIP vào một thư mục riêng.
3. Chạy **install.bat**, rồi dán đường dẫn thư mục game khi được hỏi. [Hướng dẫn chọn thư mục](docs/getting-started-vi.md).
4. Mở game qua launcher như thường lệ. Nếu bản dịch yêu cầu mở lại game, thoát rồi mở lại.

Nếu game nằm trong **Program Files** hoặc thư mục bị Windows hạn chế quyền ghi, bạn có thể cần nhấp chuột phải **install.bat → Run as administrator**. Quyền này phụ thuộc nơi cài game và quyền ghi của tài khoản Windows.

Nếu từng dùng bản dịch cũ, chuyển các file bắt đầu bằng `~VI_PATCH` hoặc `~VI_QFONT` ra ngoài thư mục `Content\Paks` trước khi cài. Bản mới chỉ có một gói; không cài kèm LIM/QFONT cũ.

## Cập nhật, kiểm tra và gỡ

- **Cập nhật:** thoát game rồi chạy `install.bat` của gói mới.
- **Kiểm tra bản đã cài:** chạy `verify.bat`.
- **Gỡ bản dịch:** thoát game rồi chạy `uninstall.bat`.
- **Khôi phục một lần cài/gỡ:** chạy `rollback.bat` và nhập mã giao dịch mà bộ cài đã in ra.

Các thao tác kiểm tra/gỡ/khôi phục cũng cần quyền ghi phù hợp với thư mục game. Bộ cài không tự mở hay đóng game.

## Những điểm còn tồn đọng

Một số nội dung còn tiếng Trung hoặc dùng bản dịch cũ chưa được soát hết. Vài màn hình có thể còn tràn/cắt chữ ở những tỉ lệ giao diện chưa kiểm tra. Game cập nhật cũng có thể khiến bản dịch cần được chỉnh lại.

Khi [báo lỗi](https://github.com/yakiro-nvg/wojd_trans/issues), gửi tên bản phát hành, ảnh lỗi và thao tác để tái hiện. Kiểm tra thông tin riêng tư trước khi gửi log.

---

Dành cho người đóng góp: [Phát triển bản dịch](docs/contributing-vi.md) · [Phương pháp và giới hạn](docs/methodology.md) · [Build và phát hành](docs/release-process.md) · [Credit font](docs/font-credits.txt).
