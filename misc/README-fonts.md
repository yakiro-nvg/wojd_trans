# Bản dịch tiếng Việt và Font chuyển đổi Hán-Việt

## Các phiên bản có sẵn

| Phiên bản | Mô tả |
|-----------|-------|
| `VI_PATCH.zip` | Bản dịch cơ bản - chỉ thay thế text đã dịch |
| `VI_PATCH_LIM_XF.zip` | Boss/3D convert (XiaoFan) |
| `VI_PATCH_LIM_MVH.zip` | Boss/3D convert (MeVietHoa) |

## Sự khác biệt giữa các phiên bản

- **Base (VI_PATCH)**: Chỉ bao gồm bản dịch. Những đoạn chữ Hán chưa dịch sẽ hiển thị nguyên bản.

- **LIM (Limited Convert)**: Chuyển đổi Hán-Việt cho kỹ năng boss, tên nhân vật 3D. Các vị trí khác giữ nguyên chữ Hán. Phù hợp khi chỉ muốn đọc nhanh skill boss mà không convert toàn bộ game.

## Font overlay (dùng với Base)

Chuyển đổi Hán-Việt cho toàn bộ game. Có thể bật/tắt convert qua cài đặt font trong game:
- Chọn **"Thể khải"** → bật convert
- Chọn **"Tổng Thể"** → tắt convert

**Chỉ dùng với VI_PATCH.zip**, không cần dùng với LIM vì overlay đã bao gồm tất cả.

| File | Kích thước | Mô tả |
|------|-----------|-------|
| `VI_QFONT_XF.zip` | 33MB | Font XiaoFan |
| `VI_QFONT_MVH.zip` | 51MB | Font MeVietHoa |

### Cách sử dụng font overlay

1. Tải `VI_PATCH.zip` từ [Releases](https://github.com/yakiro-nvg/wojd_trans/releases)
2. Tải thêm `VI_QFONT_XF.zip` hoặc `VI_QFONT_MVH.zip` từ thư mục này
3. Giải nén cả hai file
4. Sao chép cả hai file `.pak` vào thư mục game

## Tóm tắt lựa chọn

| Nhu cầu | Phiên bản |
|---------|-----------|
| Chỉ cần bản dịch, không convert | VI_PATCH |
| Convert skill boss/tên 3D (nhẹ) | VI_PATCH_LIM |
| Convert toàn bộ game | VI_PATCH + VI_QFONT |

## Credits

- **XiaoFan**: Font phiên âm Hán-Việt
- **MeVietHoa**: Font phiên âm Hán-Việt
