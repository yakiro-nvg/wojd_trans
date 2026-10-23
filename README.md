# WOJD Việt hóa

[Tải bản phát hành](https://github.com/yakiro-nvg/wojd_trans/releases/latest) · [Cài đặt](docs/getting-started-vi.md) · [Installation](docs/getting-started-en.md) · [Build/release](docs/release-process.md)

Bản dịch dùng hook native để thay nguyên câu ở các đường đọc dữ liệu đã xác minh, kết hợp hai locres, 296 FormatString và các sửa font/bố cục UI. Text chưa dịch có thể còn tiếng Trung. Đây là bản phát hành tạm; phần review nghĩa còn lại tiếp tục sau release.

Tải **VI_PATCH.zip**, giải nén, đóng game rồi chạy `install.bat`. Đây là bản production tối ưu, tắt capture/self-test, có sẵn font Việt và các sửa UI. Không cần Python, compiler hay quyền quản trị để cài.

`verify.bat` kiểm tra file; `uninstall.bat` gỡ; `rollback.bat` phục hồi giao dịch cài/gỡ. Cập nhật bằng bộ cài của gói mới. Chuyển PAK legacy `~VI_PATCH*`/`~VI_QFONT*` ra ngoài `Content/Paks` trước khi cài.

LIM/QFONT chuyển font Hán Việt thuộc legacy. Bản hiện tại dịch nguyên câu qua native và locres, nên release chỉ cung cấp một cấu hình production. Những gói cũ vẫn có trong lịch sử Releases/Git.

Hook kiểm tra code hiện tại mỗi lần chạy. Nếu cần hiệu chỉnh sau game update, hộp thoại sẽ yêu cầu mở lại game. Bộ cài không chặn theo hash, timestamp hoặc kích thước EXE. Cập nhật lớn vẫn có thể cần sửa bản dịch.

**Lưu ý:** native DLL can thiệp sâu hơn locres thông thường. Không bảo đảm tương thích, ổn định, an toàn tài khoản hay sự chấp thuận của nhà phát hành/anti-cheat.

Source C và MinHook được build trong CI; ZIP gắn revision, manifest và checksum. CI kiểm tra DLL production, fixture native, bộ cài trên thư mục giả và đọc lại toàn bộ PAK/ZIP. Không phân phối DLL/EXE gốc của game. [Credit font](docs/font-credits.txt) và giấy phép đi kèm gói.

Các catalog `translations/vi.native.ndjson`, `vi.residual.ndjson`, `vi.fmtstring.ndjson` dùng để tiếp tục dịch/review. `vi.quality.ndjson` theo dõi bằng chứng gắn cả source và target; có bản dịch không đồng nghĩa đã review nghĩa. `resources/locres/` lưu binding runtime riêng cho hai route, giữ đúng namespace/key/CRC và target. Không dựng lại các binding này chỉ bằng cách so literal với nhánh .data. `translations/legacy/` chỉ là kho reuse. Các nguồn lớn dùng Git LFS.

Xem [hướng dẫn phát triển](docs/contributing-vi.md), [phương pháp](docs/methodology.md), [giới hạn hiện tại](docs/known-issues.txt). Chat companion là nghiên cứu riêng, chưa tích hợp vào gói game.
