# Bản dịch tiếng Việt và Font chuyển đổi Hán-Việt

## Các phiên bản có sẵn

| Phiên bản | Mô tả |
|-----------|-------|
| `VI_PATCH.zip` | Bản dịch cơ bản - chỉ thay thế text đã dịch |
| `VI_PATCH_LIM_XF.zip` | Bản dịch + Font chuyển đổi giới hạn (XiaoFan) - chuyển kỹ năng boss, tên 3D |
| `VI_PATCH_LIM_MVH.zip` | Bản dịch + Font chuyển đổi giới hạn (MeVietHoa) - chuyển kỹ năng boss, tên 3D |
| `VI_PATCH_FULL_XF.zip` | Bản dịch + Font chuyển đổi đầy đủ (XiaoFan) - bao gồm chatbox |
| `VI_PATCH_FULL_MVH.zip` | Bản dịch + Font chuyển đổi đầy đủ (MeVietHoa) - bao gồm chatbox |
| `VI_PATCH_DYN_XF.zip` | Bản dịch + Chuyển đổi động (XiaoFan) - bật/tắt qua cài đặt font |
| `VI_PATCH_DYN_MVH.zip` | Bản dịch + Chuyển đổi động (MeVietHoa) - bật/tắt qua cài đặt font |

## Sự khác biệt giữa các phiên bản

- **Base (VI_PATCH)**: Chỉ bao gồm bản dịch. Những đoạn chữ Hán chưa dịch sẽ hiển thị nguyên bản.

- **LIM (Limited Convert)**: Chuyển đổi Hán-Việt cho các vị trí đặc biệt như thanh kỹ năng boss, tên nhân vật 3D. Chatbox vẫn hiển thị chữ Hán nguyên bản.

- **FULL (Full Convert)**: Chuyển đổi Hán-Việt cho tất cả vị trí, bao gồm cả chatbox. Mọi chữ Hán chưa dịch đều được chuyển sang phiên âm Việt.

- **DYN (Dynamic)**: Cho phép bật/tắt chuyển đổi Hán-Việt trong game. Vào Cài đặt > Cài đặt phông chữ:
  - Chọn **"Thể khải"** để bật chuyển đổi Hán-Việt
  - Chọn **"Tổng Thể"** để hiển thị chữ Hán nguyên bản

## Font chuyển đổi

- **XiaoFan (XF)**: Font nhỏ gọn (~7MB), phù hợp khi cần tiết kiệm dung lượng.
- **MeVietHoa (MVH)**: Font đầy đủ (~17MB), hỗ trợ nhiều ký tự hơn.

## Cách sử dụng

1. Tải xuống phiên bản phù hợp từ trang [Releases](https://github.com/yakiro-nvg/wojd_trans/releases).
2. Giải nén file `.zip`.
3. Sao chép file `.pak` vào thư mục game:
   `C:\Program Files\ZXSJclient\ZXSJ\Game\ZhuxianClient\Content\Paks`
4. Khởi động lại game.

> **Lưu ý:** Chỉ cần cài một phiên bản. Nếu muốn đổi sang phiên bản khác, xóa file `.pak` cũ trước khi cài mới.

## Credits

- **XiaoFan**: Font phiên âm Hán-Việt
- **MeVietHoa**: Font phiên âm Hán-Việt đầy đủ
