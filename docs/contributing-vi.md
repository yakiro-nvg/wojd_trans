# Hướng Dẫn Đóng Góp Dịch Thuật

## Nếu bạn chỉ muốn báo lỗi dịch
1. Mở tab Issues trên GitHub của dự án.
2. Tạo một Issue mới, nêu rõ:
   - Nội dung tiếng Việt hoặc tiếng Trung xuất hiện trong game.
   - Bối cảnh (nhiệm vụ, NPC, hệ thống…).
   - Ảnh chụp màn hình (nếu có) để minh họa.
3. Maintainer sẽ kiểm tra và cập nhật bản dịch trong catalog.
4. Nếu game vừa có bản cập nhật lớn, hãy kiên nhẫn chờ vài ngày; đừng tạo nhiều Issue trùng lặp để tránh quá tải.

## Nếu bạn muốn tự sửa (mức nâng cao)
Những bước dưới đây dành cho người quen với việc chỉnh sửa tệp lớn và thao tác Git cơ bản. Bạn có thể dùng để thử nghiệm trước khi gửi Issue hoặc PR.

### Cấu trúc catalog
- Locres: `translations/<lang>.ndjson`
- FormatString: `translations/<lang>.fmtstring.ndjson`
Mỗi dòng là một đối tượng JSON độc lập với các trường `namespace`, `key`, `source`, `translated`.

### Quy trình cơ bản
1. Fork repository và clone về máy.
2. Sử dụng editor hỗ trợ file lớn (Sublime Text...).
3. Tìm dòng cần sửa bằng từ khóa ngắn (vì chuỗi có thể chứa thẻ như `<RTP_*>`, `${...}`...).
4. Chỉ sửa trường `"translated"`, giữ nguyên các placeholder, thẻ v.v..
5. Nếu muốn tạo PAK thử nghiệm:
   ```
   npm install -g
   npm run build
   wojd-trans pack artifacts
   ```
6. Tự kiểm tra trong game, sau đó gửi Issue mô tả thay đổi hoặc mở PR nếu tự tin với Git.

> **Lưu ý:** Việc xử lý xung đột merge, rebase… không được hướng dẫn chi tiết ở đây. Nếu gặp khó khăn, hãy trao đổi với maintainer trước khi tiếp tục.
