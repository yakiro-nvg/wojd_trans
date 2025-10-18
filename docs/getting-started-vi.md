# Hướng dẫn thiết lập và sử dụng wojd-trans (Tiếng Việt)

## 0. Tổng quan

- Bộ công cụ hoạt động trên Ubuntu trong Windows Subsystem for Linux 2 (WSL2).
- Quy trình cơ bản:
  1. Chuẩn bị môi trường (WSL2, Node.js, Python).
  2. Thu thập log từ game và đồng bộ vào kho dữ liệu dịch (`collect`, `sync`, `fmtstring`, `import`).
  3. Dịch (tự động hoặc thủ công) và, khi cần, đóng gói lại bản vá (`pack`, tùy chọn).
- Hãy đọc hết từng mục trước khi thao tác. Nếu màn hình của bạn khác biệt nhiều, hãy dừng lại và kiểm tra lại bước trước.

---

## 1. Cài đặt WSL2 và Ubuntu

### 1.1 Cập nhật Windows và bật WSL2
1. Mở `Settings` → `Windows Update` → `Check for updates` → cài đặt mọi bản cập nhật → khởi động lại.
2. Mở Start, gõ `PowerShell`, nhấp chuột phải vào **Windows PowerShell**, chọn **Run as administrator**.
3. Dán lệnh sau và nhấn Enter:
   ```powershell
   wsl --install
   ```
4. Nếu Windows yêu cầu khởi động lại, hãy restart ngay.
5. Sau khi máy mở lại, Trình quản lý Microsoft Store sẽ tự cài Ubuntu (mặc định). Nếu không thấy, chạy lại lệnh ở bước 3.

### 1.2 Khởi tạo Ubuntu lần đầu
1. Mở Start → gõ “Ubuntu” → chọn ứng dụng Ubuntu mới cài.
2. Cửa sổ đen sẽ cài đặt trong vài phút. Khi được hỏi:
   - `Enter new UNIX username`: gõ tên đơn giản, không dấu (ví dụ `vietuser`).
   - `New password`: nhập hai lần (mật khẩu không hiện chữ khi gõ, cứ nhập rồi Enter).
3. Khi dòng lệnh xuất hiện dạng `vietuser@DESKTOP-xxxx:~$` là hoàn tất.

> Mẹo: cài Visual Studio Code trên Windows (https://code.visualstudio.com/) và tiện ích **Remote - WSL** để chỉnh sửa file trong Ubuntu dễ hơn.

### 1.3 Những lưu ý quan trọng khi cài WSL2

- **Kiểm tra phiên bản Windows:** mở hộp thoại Run (`Win + R`), gõ `winver`. WSL2 cần Windows 10 từ bản 19041 hoặc Windows 11. Nếu quá cũ, hãy cài Windows Update trước.
- **Bật ảo hóa trong BIOS:** khởi động lại máy, vào BIOS/UEFI và bật tính năng `Intel VT-x`, `Intel Virtualization Technology` hoặc `SVM` (tùy hãng). Nếu không bật, WSL2 sẽ báo lỗi “Virtualization support is disabled”.
- **Bật tính năng hệ thống cần thiết:** mở `OptionalFeatures.exe`, tick **Virtual Machine Platform** và **Windows Subsystem for Linux**, sau đó `OK` và khởi động lại. Tương đương, bạn có thể chạy trong PowerShell (Admin):
  ```powershell
  dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
  dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
  ```
- **Cập nhật nhân WSL:** sau khi cài xong, chạy `wsl --update` để lấy kernel mới nhất. Trên máy vừa thiết lập, nên chạy thêm `wsl --set-default-version 2` để mặc định dùng WSL2.
- **Nếu cài đặt bị treo ở “Installing…”:** đóng cửa sổ, bảo đảm các bước trên đã hoàn tất, rồi mở lại Ubuntu. Một số máy cần khởi động lại thêm một lần sau khi bật tính năng ảo hóa.

---

## 2. Chuẩn bị môi trường trong Ubuntu

Tất cả lệnh ở phần này chạy trong cửa sổ Ubuntu (WSL). Nếu lệnh bắt đầu bằng `sudo`, Ubuntu sẽ yêu cầu mật khẩu vừa tạo.

### 2.1 Cập nhật gói hệ thống và cài công cụ cơ bản
```bash
sudo apt update
sudo apt upgrade
sudo apt install git curl unzip build-essential
```

### 2.2 Cài Python và các thành phần liên quan
```bash
sudo apt install python3 python3-pip python3-venv python3-dev
python3 --version
pip3 --version
```

> Sau khi có Python, chúng ta sẽ tạo một **virtual environment** (môi trường ảo) dành riêng cho dự án để tránh cảnh báo `pip` về việc cài đặt hệ thống toàn cục.

### 2.3 Cài Node.js thông qua fnm (Fast Node Manager)
```bash
curl -fsSL https://fnm.vercel.app/install | bash   # tham khảo hướng dẫn mới nhất tại https://github.com/Schniz/fnm
source ~/.bashrc                                   # nạp lại thiết lập fnm để dùng ngay
fnm --version
fnm install --lts                                   # cài phiên bản Node ổn định dài hạn mới nhất
fnm use --lts
node -v                                            # ví dụ: v20.x.x
npm -v
```

> Nếu muốn chắc chắn shell mới luôn tự nhận Node, mở `~/.bashrc` kiểm tra đã có dòng `eval "$(fnm env)"`. Khi mở terminal mới, `fnm` sẽ tự kích hoạt phiên bản mặc định. Nếu bạn đóng terminal rồi mở lại mà không thấy Node, chạy lại `source ~/.bashrc` hoặc `fnm use --lts`.

### 2.4 (Tuỳ chọn) Công cụ nâng cao

Những công cụ dưới đây chỉ cần khi bạn muốn **giải nén tài nguyên từ game** hoặc **đóng gói lại PAK hoàn chỉnh**. Người mới tập trung vào luồng thu log (`collect` → `sync`) có thể bỏ qua và quay lại sau khi đã quen.

- **FModel** (Windows GUI): dùng để mở PAK chính thức và trích `Game.locres`, `FormatString/*.txt`. Cần nhập đúng AES key của game (bạn phải tự tìm từ cộng đồng hoặc tài liệu nội bộ).
- **repak** (CLI đa nền tảng): chỉ cần khi bạn muốn đóng gói lại thành `~VI_PATCH.pak`. Quy trình thu log → đồng bộ → dịch **không dùng repak**. Nếu chỉ cần tạo `Game.locres` bằng script Python (`scripts/build_locres.py`) thì không phải cài công cụ này. Khi bạn thật sự muốn đóng gói PAK, tham khảo phần 12 để biết cách chuẩn bị repak trên Windows hoặc WSL.

> Lưu ý: việc khai thác tài nguyên game có thể vi phạm điều khoản của nhà phát hành. Hãy chắc chắn bạn hiểu rủi ro trước khi thực hiện.

---

## 3. Lấy mã nguồn wojd-trans và cài phụ thuộc

### 3.1 Tạo thư mục làm việc và tải dự án
```bash
cd ~
mkdir -p wojd && cd wojd
git clone https://github.com/yakiro-nvg/wojd_trans.git
cd wojd_trans
```

> Không dùng Git? Bạn có thể tải file `.zip` từ GitHub, giải nén vào `~/wojd/`, rồi dùng `cd ~/wojd/wojd_trans`.

### 3.2 Cài Node modules và build CLI
```bash
npm install
npm run build
```

### 3.3 Tạo virtual environment và cài thư viện Python
```bash
python3 -m venv .venv                     # tạo môi trường ảo trong thư mục dự án
source .venv/bin/activate                  # kích hoạt (ghi nhớ tất cả câu lệnh pip sau đó đều trong venv)
pip install --upgrade pip
pip install -r requirements.txt
```

> Mỗi lần mở terminal mới bạn cần kích hoạt lại bằng `source .venv/bin/activate`. Nếu bỏ qua môi trường ảo và dùng `pip3 install ...`, bạn sẽ thấy cảnh báo kiểu `WARNING: Running pip as the 'root' user` hoặc `The scripts ... are installed in '/home/.../.local/bin' which is not on PATH` vì pip cài đặt lên toàn hệ thống.

Để thoát môi trường ảo sau khi làm xong, dùng `deactivate`.

### 3.4 Kiểm tra CLI
```bash
npx wojd-trans --help
```
Nếu thấy danh sách lệnh (`collect`, `sync`, `pack`, ...) là môi trường đã sẵn sàng.

---

## 4. Cấu trúc thư mục quan trọng

- `FormatString/`: bản xuất các file `.txt` gốc của game.
- `translations/vi.ndjson`: kho dữ liệu locres (mỗi dòng là một chuỗi JSON).
- `translations/vi.fmtstring.ndjson`: kho dữ liệu cho FormatString.
- `collected.json`: dữ liệu trích từ log (tạo bằng lệnh `collect`).
- `prompts/vi/system-prompt.txt`: prompt dùng cho dịch tự động.
- `artifacts/`: thư mục xuất ra `Game.locres` và `~VI_PATCH.pak` sau khi đóng gói.

---

## 5. Bật ghi log chi tiết trong game (thực hiện một lần)

1. Mở thư mục cài đặt game trên Windows (ví dụ: `C:\Program Files\ZXSJclient\ZXSJ\Game\ZhuxianClient`).
2. Đi theo đường dẫn `Saved\Config\Windows`.
3. Mở `Engine.ini` (hoặc tạo mới nếu chưa có) bằng Notepad.
4. Thêm đoạn sau vào cuối file:
   ```
   [Core.Log]
   LogTextLocalizationManager=VeryVerbose
   ```
5. Lưu lại. Từ giờ game sẽ ghi đầy đủ thông tin localization vào `ZhuxianClient.log`.

---

## 6. Thu log mới sau khi chơi

1. Chạy game, đi tới những màn hình chứa nội dung cần dịch (giao diện, nhiệm vụ, vật phẩm...). Khi text tiếng Trung hiển thị, log đã ghi nhận.
2. Thoát game.
3. Trên Windows, mở `ZhuxianClient\Saved\Logs` và sao chép `ZhuxianClient.log` (kèm `ZhuxianClient-backup-*.log` nếu có) vào thư mục dự án trong Ubuntu. Có thể dùng đường dẫn mạng `\\wsl$\Ubuntu\home\<tên_bạn>\wojd\wojd_trans` rồi dán file vào.

---

## 7. Tạo `collected.json` từ log

Đứng tại thư mục dự án trong Ubuntu (`cd ~/wojd/wojd_trans`):
```bash
npx wojd-trans collect collected.json --force
```

- CLI sẽ tự tìm các file `ZhuxianClient*.log` trong thư mục hiện tại.
- Nếu log ở đường dẫn khác, truyền rõ đường dẫn file trước tên file đầu ra:
  ```bash
  npx wojd-trans collect /mnt/c/Program\ Files/ZXSJclient/ZXSJ/Game/ZhuxianClient/Saved/Logs/ZhuxianClient.log collected.json --force
  ```
- Kết quả: `collected.json` chứa danh sách namespace/key/text đã xuất hiện.

---

## 8. Đồng bộ kho locres (`sync`)

```bash
npx wojd-trans sync collected.json
```

- Thêm mục mới vào `translations/vi.ndjson` (và các ngôn ngữ khác trong `languages.json`).
- Nếu muốn reset toàn bộ bản dịch (cẩn thận), dùng thêm `--force`.

---

## 9. Đồng bộ các file FormatString (`fmtstring`)

1. Thư mục `FormatString/` đã có sẵn trong repo. Nếu chỉ làm quen quy trình, giữ nguyên bản hiện tại.
2. Khi game ra bản mới và bạn muốn cập nhật `FormatString`, dùng công cụ như **FModel** (Windows) để trích xuất file `.txt` rồi sao chép đè vào thư mục này. Bước này yêu cầu AES key và thuộc nhóm thao tác nâng cao.
3. Chạy:
   ```bash
   npx wojd-trans fmtstring FormatString
   ```
4. File `translations/vi.fmtstring.ndjson` sẽ được cập nhật. Dùng `--force` nếu cần xóa bản dịch cũ.

---

## 10. Nhập dữ liệu từ `Game.locres` chính thức (`import`)

Nếu nhà phát hành cập nhật `Game.locres`:

1. Trích xuất file `Game.locres` từ bản PAK chính thức (dùng FModel hoặc repak nếu bạn đã thiết lập công cụ nâng cao) và chép vào thư mục dự án.
2. Chạy:
   ```bash
   npx wojd-trans import Game.locres
   ```
3. Bản dịch gốc sẽ lưu vào trường `locresImport`, giúp tái sử dụng khi đóng gói.

---

## 11. Dịch nội dung

### 11.1 Dịch tự động (tuỳ chọn)

```bash
npx wojd-trans translate --language vi
```

- CLI sẽ hỏi chọn dịch vụ (Amazon Bedrock hoặc Google Gemini) và yêu cầu nhập khóa truy cập.
- Một số tham số hữu ích:
  - `--limit 50`: chỉ dịch tối đa 50 chuỗi.
  - `--test` (hoặc `--test=5`): chạy chế độ thử nhanh với vài chuỗi.
  - `--force`: xóa bản dịch hiện tại rồi dịch lại (cần cân nhắc).

### 11.2 Dịch thủ công

- Mở `translations/vi.ndjson` bằng trình soạn thảo chịu được file lớn như Sublime Text, Visual Studio Code chỉ nên dùng để xem diff hoặc chỉnh sửa nhỏ.
- Mỗi dòng là một đối tượng JSON, chỉ chỉnh trường `"translated"`.
- Giữ nguyên placeholder (`<RTP_*>`, `${...}`, `(##Color:...)`).
- `translations/vi.fmtstring.ndjson` xử lý tương tự cho các file `.txt`.

> Gợi ý: dùng Git để commit từng đợt dịch nhỏ giúp dễ hoàn tác.

---

## 12. Đóng gói bản vá (`pack`) *(nâng cao)*

`wojd-trans pack` sử dụng script Python (`pylocres`) để sinh `Game.locres` và, nếu tìm thấy lệnh `repak`, sẽ tiếp tục đóng gói thành `~VI_PATCH.pak`. Vì vậy:

- **Nếu bạn chỉ cần tệp `Game.locres`** để kiểm tra hoặc chia sẻ, có thể bỏ qua repak hoàn toàn và chạy trực tiếp:
  ```bash
  source .venv/bin/activate
  python3 scripts/build_locres.py --input translations/vi.ndjson --output artifacts/Game.locres
  ```
  (Thay `vi` bằng mã ngôn ngữ mong muốn.)

- **Nếu muốn tạo PAK hoàn chỉnh**, hãy chuẩn bị repak (cài trên Windows hoặc WSL) rồi chạy:
  ```bash
  source .venv/bin/activate
  npx wojd-trans pack artifacts
  ```
  Khi đó CLI sẽ:
  - Tạo `Game.locres` và các file `FormatString` đã dịch trong thư mục tạm.
  - Gọi repak để sinh `artifacts/~VI_PATCH.pak` (thêm dấu `~` để ưu tiên nạp).
  - Nếu muốn giữ thư mục tạm để kiểm tra, thêm `--keep-temp`.

### 12.1 Cài patch vào game *(khi đã có PAK)*

1. Mở Windows Explorer và duyệt tới thư mục dự án WSL qua đường dẫn `\\wsl$\Ubuntu\home\<tên_bạn>\wojd\wojd_trans\artifacts`.
2. Mở một cửa sổ Explorer khác tới thư mục PAK của game, ví dụ `C:\Program Files\ZXSJclient\ZXSJ\Game\ZhuxianClient\Content\Paks`.
3. Kéo thả `~VI_PATCH.pak` từ thư mục artifacts sang thư mục PAK của game (Windows sẽ hiển thị hộp thoại xin quyền quản trị, hãy đồng ý để tiếp tục).
4. Xóa hoặc đổi tên patch cũ trước khi chép patch mới.
5. Mở game kiểm tra các khu vực đã dịch.

---

## 13. Chu trình cập nhật khi game có bản mới

1. Lấy patch mới → cập nhật `FormatString/` và `Game.locres` (nếu thay đổi).
2. Chơi game thu log mới → copy `ZhuxianClient.log`.
3. Chạy tuần tự:
   ```bash
   npx wojd-trans collect collected.json --force
   npx wojd-trans sync collected.json
   npx wojd-trans fmtstring FormatString
   npx wojd-trans import Game.locres
   ```
4. Dịch phần mới (tự động hoặc thủ công).
5. (Tuỳ chọn) `npx wojd-trans pack artifacts` → copy `~VI_PATCH.pak` vào game khi bạn đã chuẩn bị repak.
6. Làm việc nhóm thì dùng Git (`git pull`, `git commit`, `git push`, mở Pull Request).

---

## 14. Xử lý lỗi thường gặp

| Vấn đề | Cách khắc phục |
| --- | --- |
| `wsl --install` báo lỗi quyền | Mở PowerShell bằng quyền Administrator. |
| `npx: command not found` | Chạy `source ~/.bashrc` rồi `fnm use --lts`. |
| `repak: command not found` | Cài repak theo hướng dẫn trong mục 12 (Windows hoặc WSL), rồi thử lại. |
| `Missing dependency 'pylocres'` | Chạy `source .venv/bin/activate` rồi `pip install -r requirements.txt` để đảm bảo trong môi trường ảo. |
| Không copy được `.pak` sang ổ C | Đóng game và mọi chương trình đang dùng file đó, thử lại. |
| Đường dẫn Windows trong Ubuntu | Ổ C nằm tại `/mnt/c`, ví dụ Desktop: `/mnt/c/Users/<Tên bạn>/Desktop`. |

---

## 15. Bước tiếp theo đề xuất

1. Làm quen lệnh terminal cơ bản: `ls`, `cd`, `cp`, `mv`, `rm` (cẩn thận khi xóa file).
2. Dùng công cụ phù hợp với file lớn (ví dụ Sublime Text) để chỉnh NDJSON; VS Code (Remote WSL) hữu ích khi cần xem diff hoặc thực hiện chỉnh sửa nhỏ.
3. Tìm hiểu Git nếu làm việc nhóm hoặc muốn quản lý phiên bản bản dịch.
4. Đọc thêm: [docs/methodology.md](methodology.md) để hiểu sâu pipeline, [docs/release-process.md](release-process.md) nếu muốn tự động hóa trên CI.

Chúc bạn xây dựng bản Việt hóa thành công! Nếu gặp lỗi cụ thể, hãy lưu lại thông báo/ảnh màn hình và trao đổi với đội ngũ duy trì dự án để được hỗ trợ.
