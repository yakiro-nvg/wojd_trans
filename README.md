# World of Jade Dynasty Translation

## Tiếng Việt

### Cài đặt nhanh
1. Tải gói phù hợp từ trang [Releases](https://github.com/yakiro-nvg/wojd_trans/releases/latest).
2. Giải nén để thu được file `.pak`.
3. Sao chép file `.pak` vào thư mục trò chơi (ví dụ):
   ```
   C:\Program Files\ZXSJclient\ZXSJ\Game\ZhuxianClient\Content\Paks
   ```
4. Xóa các bản Việt hóa cũ (nếu có) trước khi chép gói mới.

### Các phiên bản

| Phiên bản | Mô tả |
|-----------|-------|
| `VI_PATCH.zip` | Bản dịch cơ bản |
| `VI_PATCH_LIM_XF.zip` | Boss/3D convert (XiaoFan) |
| `VI_PATCH_LIM_MVH.zip` | Boss/3D convert (MeVietHoa) |

- **Base**: Chỉ thay thế text đã dịch, chữ Hán chưa dịch giữ nguyên.
- **LIM**: Chuyển đổi Hán-Việt cho kỹ năng boss, tên 3D. Các vị trí khác giữ nguyên chữ Hán. Phù hợp khi chỉ muốn đọc nhanh skill boss mà không convert toàn bộ game.

### Font overlay (dùng với Base)
Chuyển đổi Hán-Việt toàn bộ game. Có thể bật/tắt convert qua cài đặt font: **"Thể khải"** = bật, **"Tổng Thể"** = tắt.

Dùng kèm với `VI_PATCH.zip` (không dùng với LIM). Tải từ [misc/](misc/):
- `VI_QFONT_XF.zip` (33MB) - XiaoFan
- `VI_QFONT_MVH.zip` (51MB) - MeVietHoa

> Chi tiết xem [Font convert](misc/README-fonts.md)

### Thông tin thêm
- [Hướng dẫn phát triển](docs/getting-started-vi.md)
- [Phương pháp dịch thuật](docs/methodology.md)
- [Quy trình phát hành](docs/release-process.md)
- [Hướng dẫn đóng góp dịch thuật](docs/contributing-vi.md)
- [Tùy biến font hiển thị](docs/font-customization-vi.md)
- [Font convert](misc/README-fonts.md)

## English

Not support, you can try TW version in this discord: https://discord.com/invite/Nk5gEq9gZ9

### More Info
- [Getting started (Vietnamese)](docs/getting-started-vi.md)
- [Localization pipeline](docs/methodology.md)
- [Release workflow](docs/release-process.md)
- [Contribution guide](docs/contributing-en.md)
