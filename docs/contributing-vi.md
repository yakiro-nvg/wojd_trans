# Phát triển bản dịch

[Guide EN](contributing-en.md) có đầy đủ lệnh và cấu trúc cho VI/EN. Công cụ không cần API key; người dịch hoặc agent review batch rồi nhập qua kiểm tra source/marker.

## Thu log sạch

Dump là mục tiêu build dành cho người phát triển; release không cung cấp ZIP dump cho người chơi. Khi chuẩn bị một phiên thu riêng, dùng DLL dump và bảo đảm cả hai route **không có locres dịch**. Chuyển mọi PAK locres dịch khác ra ngoài, kể cả tên tùy biến. Nếu locres cũ vẫn nạp, nó che miss; lọc source sau đó không lấy lại được.

Sao lưu INI người dùng rồi bật LogTextLocalizationManager=VeryVerbose trong [Core.Log] nếu cần; xem vị trí ở guide EN. Kiểm tra log mới thực sự có warning miss. Log rất lớn; hoàn nguyên mức log sau khi thu. Installer không tự sửa INI.

Sửa ue_log_path trong Binaries/Win64/wojd/settings.json theo máy. Mở các màn hình cần kiểm tra, thoát game rồi lấy thư mục phiên mới trong wojd/logs/. Mỗi lượt có dump, native log, build metadata và bản sao UE log riêng. Chỉ coi archive hoàn chỉnh khi archive-result.json báo PASS. Kiểm tra readiness, lỗi/drop, số mục và tập source giữa các lượt có cùng điều kiện.

## Ba nguồn

1. Native: tạo index từ legacy VI, chạy native-sync với dump mới và --reviewed catalog hiện tại để giữ quyết định review. So nguyên source, không dùng ID hoặc chuẩn hóa newline.
2. Locres: fallback-sync dùng **log sạch mới**, giữ namespace/key/source hiện tại. Chỉ loại đúng output đã bị native thay; source CN trùng .data vẫn có thể thuộc widget/route khác. Source equality là bằng chứng reuse, không phải chứng minh producer. Residual không khôi phục đủ stock/generated widget bindings: gói release dựng hai route riêng từ resources/locres, giữ namespace/key/CRC/target đã xác minh. Cập nhật binding và manifest qua đối chiếu đầy đủ; không nhập ID lịch sử từ kho legacy.
3. FormatString: đối chiếu riêng file/key/source với bộ TXT hiện tại; không lọc theo .data. Giữ BOM/encoding/comment/newline/cấu trúc và cập nhật source template khi game đổi.

## Quyết định và dọn rác

Tái sử dụng bản dịch cũ chỉ cần source khớp nguyên văn trong kho NDJSON đã index, không ràng buộc nguồn, namespace hay key. Các trường vị trí chỉ phục vụ xuất file hiện tại. Giữ kiểm tra marker/cấu trúc trước khi nhận bản dịch.

Khi đã có catalog hiện tại của cả ba nguồn, đưa chúng vào index cùng kho legacy để tận dụng cả các câu đã review bổ sung sau này. Chỉ trộn các catalog cùng ngôn ngữ.

Output Việt do native đã thay có thể sinh miss chứa Hán tự trong marker. Đối chiếu về source CN để review, tránh đưa lại output đã thay vào residual. Điều này không cho phép loại mọi CN trùng từ điển native. Giữ quyết định context/ignore và cờ review cho câu chưa giải quyết.

Native chỉ có translated, missing, ignore. Ignore chủ động giữ CN và ghi lý do, không quay lại hàng chờ dịch. Không suy đoán dated cho native khi thiếu ID ổn định. Riêng FormatString có file/key nên có dated khi source đổi; chưa xác nhận giữ CN.

review-export chia batch; điền bản dịch hoặc ignore, giữ source/SHA rồi review-import. Giữ tag, thuộc tính logic, placeholder và thứ tự tham số, số liệu, newline thật/escape. Không thêm [VI]. Tên riêng dùng Hán Việt nhất quán; thoại/mô tả dùng Việt tự nhiên. QA cấu trúc không thay được review ý nghĩa.

## Tiến độ và chất lượng

Ưu tiên các source chưa dịch trước khi review diện rộng kho cũ. Câu tái dùng từ legacy có mức mặc định `unreviewed`, không tự được coi là đúng nghĩa vì qua QA. `draft` là bản nháp; `source_reviewed` đã đối chiếu với nguồn CN; `client_verified` cần ghi bằng chứng riêng của câu/bản dịch trong game. Việc game mở được hoặc fixture DLL chạy qua không đủ để nâng mọi câu lên `client_verified`. `ignore` vẫn là quyết định giữ nguồn, tách khỏi chất lượng ngôn ngữ.

`translations/vi.quality.ndjson` chỉ lưu bằng chứng review đã ghi nhận, gắn với SHA của **cả source và bản dịch**. Thay source hoặc target sẽ không thừa hưởng mức cũ; đổi ID runtime mà nội dung giữ nguyên vẫn dùng được. Những biến thể dịch khác nhau của cùng source có bằng chứng riêng. Không ghi đè bản dịch bằng regex để đạt chỉ tiêu.

Sau `review-import`, dùng `quality-mark` với các catalog hiện tại, `--ledger`, `--review`, `--level`, `--reviewer` và `--note` để ghi mức đã thực hiện. Có thể ghi `--glossary-revision` khi đã dùng một bảng thuật ngữ cụ thể. `quality-report` tạo thống kê; `--sources-out work/review/quality-by-source.ndjson` xuất từng source cùng biến thể và nơi tham chiếu. Nếu có nhiều biến thể đang dùng, tiến độ source lấy mức thấp nhất. Ledger không được nạp vào hook.

Trước mỗi batch: phân biệt text hiển thị với định danh/chuỗi game xử lý; xem ngữ cảnh màn hình, speaker và các câu liên quan; tra tên riêng theo quyết định dự án và bản dịch Tru Tiên đã chọn làm chuẩn. Bảng thuật ngữ cần source, tên Việt chuẩn, loại thực thể, alias, phạm vi/ngữ cảnh, nguồn tham khảo và trạng thái duyệt. Tên trùng chữ nhưng khác thực thể không tự gộp. Bảng thuật ngữ hỗ trợ người dịch và báo lệch để review, không thay thế việc dịch cả câu.

Lịch sử có các hồi quy cần giữ: `4755881` bảo toàn literal `\\n` ở pet; `ec5c4dd` giữ khóa tra cứu ranking; `5a5935f`/`69e94ce` giữ mẫu tên phương án nhuộm thống nhất. Chữ Hán trong placeholder, tên tag, đường dẫn ảnh hoặc chuỗi dùng cho logic có thể bắt buộc giữ nguyên. Chỉ thị `@p/@P`, header `@t`, payload ảnh, dấu phân cách và biến không được đổi. Không dùng việc còn Hán tự như kết luận tự động rằng phải dịch.

Chữ Hán còn có thể là ký hiệu hình dạng. Trong tên Cơ Xảo Thạch, `凸型` cần giữ hình `凸`, tránh đổi thành chữ T đứng làm đảo hướng; họ này cũng phân biệt L và L ngược. `田字型` có thể diễn đạt là “dạng chữ điền” theo ngữ cảnh. Đọc và kiểm tra từng câu đầy đủ, kể cả các biến thể phần thưởng lặp lại; không suy từ một câu rồi sinh cả họ bằng mẫu.

Đọc đúng điều kiện kích hoạt kỹ năng. Chẳng hạn `受到致命伤害时` trong hiệu ứng cứu mạng là “khi nhận sát thương đủ gây tử vong”; dùng “sát thương chí mạng” dễ bị hiểu thành critical hit. Xét cả câu và cơ chế liên quan, không thay thuật ngữ hàng loạt theo một từ khóa.

QA số liệu nhận diện riêng nhãn kênh `线路` với số Hán viết đúng dạng từ 1 đến 999, cho phép target dùng đúng giá trị bằng chữ số Ả Rập. Bảng WorldPlane hiện tại có đến kênh 245. Sai hoặc thêm số vẫn bị chặn. Kiểm tra hẹp này không dịch văn bản và không chứng minh mọi số Hán hay bảng tra cứu đều sửa được; các trường hợp khác cần xét ngữ cảnh riêng. Bản dịch cũ khớp source và qua QA vẫn là `unreviewed` cho đến khi được so nghĩa cả câu.

Giữ đúng cả số dấu gạch chéo ngược trong escape literal. Ví dụ một dấu `\` trước `n` không tương đương với hai dấu `\` trước `n`, cũng không tương đương ký tự xuống dòng thật. QA kiểm tra toàn bộ chuỗi gạch chéo, kể cả dạng CRLF và tab; không tự escape thêm khi ghi NDJSON.

native-usage đối chiếu nhiều phiên dump có build metadata. not_observed chỉ là chưa gặp trong đầu vào, không chứng minh dead. Không xóa tự động theo một lượt. Runtime không thu hit từng câu.

Không công khai log chat/tài khoản, key, game DLL/EXE hoặc .data nguyên bản. [Methodology](methodology.md) chỉ mô tả mức cần cho dịch thuật, không bổ sung công thức can thiệp sâu.

## Điều phối nhiều người hoặc agent

`scripts/batch_workflow.py --help` cung cấp hàng chờ SQLite ngoại tuyến. Coordinator tạo inventory các source hiện còn thiếu, kèm SHA và tham chiếu ngữ cảnh, rồi dùng `refresh` và `batch` để chia đầu vào bất biến theo cả số câu lẫn tổng ký tự. Không reset database để bắt đầu lượt mới. `claim --stage TRANSLATE` nhận việc; `submit` lưu một attempt. Reviewer khác dùng `claim --stage REVIEW`, đọc đầy đủ CN/VI và `review` từng nguồn. Gia hạn lease bằng `heartbeat`; lease hết hạn không tự chứng minh người làm đã ngừng.

Workflow dùng các enum EN như `READY`, `TRANSLATING`, `AWAITING_REVIEW`, `REVIEWING`, `PARTIALLY_APPROVED`, `NEEDS_CONTEXT`. Quyết định nháp là `TRANSLATED`, `IGNORE`, `NEEDS_CONTEXT`; reviewer ghi `APPROVE`, `REJECT` hoặc `NEEDS_CONTEXT` với lý do riêng. Không đồng nhất trạng thái workflow với mức chất lượng ngôn ngữ. Với thoại có nhiều biến thể môn phái/giới tính, giữ nguyên các nhãn nhánh CN và dạng dấu hai chấm khi chưa biết consumer xử lý chúng thế nào.

Coordinator kiểm tra `export` và manifest SHA đi kèm trước khi nhập. Chỉ tập con đã được duyệt mới đi vào catalog; ghi receipt, bằng chứng quality và cập nhật inventory sau nhập để tránh nhập lặp. Export không tự sửa catalog và không thay thế receipt. Giữ attempt/review cũ khi sửa target; target mới phải được review với hash mới. Bản review compact có thể tham chiếu SHA source/target bất biến thay vì lặp lại cả câu; công cụ có thể tính hash và ghép metadata, còn việc đánh giá nghĩa vẫn cần đọc toàn bộ câu.

Nếu QA được bổ sung sau khi một attempt đã đóng băng, reviewer vẫn có thể ghi `REJECT` hoặc `NEEDS_CONTEXT` cho target vừa bị phát hiện lỗi. `APPROVE` luôn kiểm tra lại cấu trúc hiện tại, cả khi export. Việc cho phép ghi nhận từ chối không cho phép target lỗi vào catalog; source/target và hash của attempt cũ vẫn phải khớp nguyên vẹn.

Ước lượng tiến độ phải ghi số nguồn dịch, số giữ nguyên và số đang chờ ngữ cảnh riêng; đo thời gian dịch, review, sửa và nhập, không chỉ thời gian sinh nháp. Mẫu cần gồm chuỗi ngắn, vừa và đoạn dài; cập nhật ETA từ throughput thực tế sau mỗi mốc đủ lớn. Chưa thấy trong một phiên không phải bằng chứng source đã chết.
