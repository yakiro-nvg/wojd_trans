# Legacy không DLL

Legacy dùng các PAK chứa locres, FormatString, font Hán–Việt và những sửa bố cục hiện hành. Gói `VI_LEGACY.zip` không chứa DLL, EXE hay từ điển cho DLL. Các tệp `.data` có chữ ký và DLL gốc của game được giữ nguyên.

`VI_PATCH.zip` cho chọn **Đầy đủ** hoặc **Legacy** trong `install.bat`. Gói Legacy riêng tự chọn Legacy. Khi đổi bản, đóng game rồi chạy bộ cài mới; bộ cài gỡ DLL Việt hóa do dự án quản lý, khôi phục DLL gốc nếu trước đó đã có và giữ thiết lập riêng, key cùng lịch sử khôi phục. Có thể đổi lại Đầy đủ hoặc dùng `rollback.bat`.

Legacy không có dịch chat tự động. Các nội dung đi ngoài locres/FormatString không nhận được bản dịch từ điển lúc chạy. Legacy dùng một font convert riêng áp dụng chung, kể cả ô tên, lấy lại 45 cách thay chữ theo nghĩa từ bảng MVH, như 你 → Ngươi, 吃 → Ăn, 拉 → Kéo, 饭 → Cơm. Những chữ còn lại giữ bảng đọc hiện tại. Đây là thay từng chữ để dễ đọc hơn, không dịch cả câu hay đổi ngữ pháp Trung. Tên riêng có các chữ này cũng đổi theo nghĩa; không tách font theo từng loại widget.

Coverage hiện tại là 26.972 chữ, dùng nét font chính, không nhập nét MVH/XF. Chữ Việt và cỡ chữ hiện có giữ nguyên; chữ ngoài bảng tiếp tục dùng font dự phòng của game. Bản Đầy đủ giữ font tên Hán–Việt riêng (Nhĩ, Cật, Lạp), không dùng bảng thay nghĩa của Legacy. Việc sửa tài nguyên game vẫn chịu quy định của nhà phát hành; không có cam kết về tài khoản.

## Thu một lượt log

1. Cài Legacy khi game đã đóng.
2. Mở game bằng launcher, vào nhân vật và mở các màn hình cần thu chữ.
3. Thoát game bình thường, chạy `collect-legacy-log.bat` trong gói vừa giải nén.
4. Công cụ kiểm tra Legacy đang cài, từ chối log cũ hơn lần cài và lưu bản sao có SHA256 trong `Binaries/Win64/wojd/logs/legacy-...`. Nó không tự mở game hay gửi log đi.

Log có thể chứa thông tin riêng. Kiểm tra trước khi chia sẻ. Nếu game không ghi miss, người phát triển có thể sao lưu Engine.ini của người dùng và bật `LogTextLocalizationManager=VeryVerbose` trong `[Core.Log]`, rồi hoàn nguyên khi thu xong. Installer không tự sửa INI.

## Dành cho người phát triển

Tái tạo font riêng bằng `python scripts/build_player_name_font.py --legacy --output assets/vi-legacy/WOJD_Legacy_Convert.ufont`. `resources/legacy-font-readings.json` chứa các thay nghĩa đã chọn từ bảng MVH; các sửa lỗi chép âm khác vẫn giữ. Bước overlay Legacy thay cùng một font vào 24 mặt font chính và mặt font tên đã có, không sửa thêm widget. Không ghi font này vào `assets/vi-base` hoặc bảng đọc native của bản Đầy đủ.

Không suy namespace/key locres từ khóa chẩn đoán của `.data`. Chỉ dùng identity/source thật trong UE log, hoặc giữ các binding tài nguyên đã xác minh. Câu gốc trùng `.data` vẫn được thu; chỉ dùng sự trùng nguyên văn để tìm lại bản dịch. Không gọi LLM hay dịch lại. Câu chưa có bản dịch và identity có nhiều source được đưa ra để kiểm tra, không đoán hoặc ghi đè im lặng. Tái dùng câu không tự nâng chất lượng thành đã review nghĩa hay đã thử trong client.

```powershell
python scripts/legacy_locres.py --logs <log-1> <log-2> --out work/legacy-collection
```

Sau khi kiểm tra catalog/conflicts/report, dùng `--publish resources/legacy-locres` với toàn bộ log cần giữ để tạo overrides. Cập nhật hai pin locres trong `config/legacy-payload.json` theo kết quả cook; bản Đầy đủ và `resources/locres` không đổi. Mỗi identity giữ nguyên source CRC, target, markup, khoảng trắng và độ sâu escape. Các binding có cùng CRC được giữ nguyên, kể cả lựa chọn target riêng cho từng tuyến. Chỉ refresh CRC khác trong namespace đã đối chiếu và khai báo bằng `--refresh-namespace`; xung đột ngoài phạm vi này dừng cook. Binding widget từ đợt quét trước không bị thay bằng kết quả tái dùng đại trà. Các thay đổi chỉ áp dụng cho hai tuyến locres Legacy.

Để lộ miss bị PAK dịch che, build **riêng một gói thu log cục bộ**:

```powershell
python scripts/build_package.py --repak <repak.exe> --variant legacy --collect-legacy --out work/legacy-collect --revision LOCAL-LEGACY-COLLECT
```

Gói thu log bỏ đúng hai locres dịch, giữ bố cục/font/FormatString và toàn bộ tài nguyên game gốc. Sau lượt thu, cook lại gói Legacy thường. Không phát hành gói thu log như bản dịch hoàn chỉnh. Miss không bao phủ các bản stock CN vẫn khớp hoặc text bỏ qua UE localization; font không khắc phục được giới hạn chèn bản dịch.

Build cả hai ZIP bằng lệnh build thông thường; `--variant legacy` có thể build ZIP Legacy riêng mà không cần thư mục `native/build` hay DLL đã biên dịch. Mọi PAK/ZIP được đọc lại đầy đủ và so với manifest. Hai mức ưu tiên PAK được giữ nguyên.
