# Hướng dẫn thay font chữ (Tiếng Việt)

Các bản vá mặc định đính kèm nhiều bộ chữ cái đã đóng gói sẵn (`.ufont`) để hiển thị tiếng Việt trong game. Nếu bạn muốn thử nghiệm font khác, có thể tự tạo một PAK font phụ và đặt tên để nạp sau bản dịch chính.

## 1. Chuẩn bị font
1. Tải font `.ttf` bạn muốn sử dụng (ví dụ: font chữ hiện đại, font viết tay...).
2. Đổi tên file vừa tải thành **một trong những tên font đang được game sử dụng**. Danh sách dưới đây mang tính tham khảo; bạn cần thử nghiệm để xác định font nào điều khiển từng khu vực giao diện (tiêu đề, chat, tooltip...).
   - `FZBWKSK_GBK.ufont`
   - `FZDBSJW.ufont`
   - `FZDBSK_GBK.ufont`
   - `FZFWZhuZiMinchoE.ufont`
   - `FZHCJW.ufont`
   - `FZKTK.ufont`
   - `FZL2JW.ufont`
   - `FZLBK.ufont`
   - `FZLanTYJW.ufont`
   - `FZLanTYJW_Xian.ufont`
   - `FZQTJW.ufont`
   - `FZSJSJW.ufont`
   - `FZShengSKSJW_0.ufont`
   - `FZShengSKSJW_Zhong.ufont`
   - `FZXKJW.ufont`
   - `FZXKK_GBK.ufont`
   - `FZZJ-DNXSJW.ufont`
   - `HYKaiTiJ.ufont`
   - `HYZhongKaiJ.ufont`
   - `STXINGKA.ufont`
   - `ZKTQingKJW.ufont`
   - `ZKTQingKJW_Stream.ufont`
   
   > Mẹo: sao lưu font gốc trước khi ghi đè và ghi chú lại font nào ảnh hưởng khu vực nào để dễ hoàn tác.

   > Lưu ý: Unreal Engine mong đợi file `.ufont`, nhưng trong bản phát hành Trung Quốc các font này thực chất chỉ là dữ liệu font gốc được đóng gói. Vì vậy bạn có thể dùng lại tên cũ để ghi đè.

3. Giữ nguyên thư mục gốc: `ZhuxianClient/Content/UI/UI_Texture/UI_ziti/`. Ví dụ cấu trúc dự án tạm:  
   ```
   VI_QFONT/ 
   └── ZhuxianClient/
       └── Content/
           └── UI/
               └── UI_Texture/
                   └── UI_ziti/
                       └── FZShengSKSJW_Zhong.ufont    (tên mới của font)
   ```

## 2. Đóng gói bằng repak
1. Tải công cụ repak (phiên bản 0.2.2) tại: https://github.com/trumank/repak/releases/tag/v0.2.2  
   - Trên Windows: tải file `.zip` đi kèm và giải nén `repak.exe`.
2. Mở Command Prompt/PowerShell tại thư mục chứa `repak` và chạy:
   ```powershell
   repak pack VI_QFONT
   ```
   - `~VI_QFONT.pak` nên bắt đầu bằng dấu `~` và có chữ cái **Q** (đứng sau `~VI_PATCH.pak` trong bảng chữ cái) để đảm bảo được nạp sau bản dịch chính.

## 3. Cài đặt
1. Sao chép `~VI_QFONT.pak` vào thư mục game, ví dụ:  
   `C:\Program Files\ZXSJclient\ZXSJ\Game\ZhuxianClient\Content\Paks`
2. Đảm bảo các bản vá cũ đã được xóa hoặc đổi tên (giữ lại `~VI_PATCH.pak` của bản dịch).
3. Khởi động game để kiểm tra font mới.

> **Lưu ý:** Font tự thêm chỉ có tác dụng trên máy của bạn. Nếu muốn chia sẻ với cộng đồng, hãy ghi rõ nguồn gốc và giấy phép sử dụng của font chữ.
