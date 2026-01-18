const fs = require('fs');

// Load pending items
const data = JSON.parse(fs.readFileSync('translations/to_translate.json', 'utf8'));

// Stat translations
const statMap = {
  '会心': 'hội tâm',
  '专精': 'chuyên tinh',
  '调息': 'điều tức',
  '破甲': 'phá giáp'
};

// Equipment type translations
const equipMap = {
  '天灵': 'thiên linh',
  '地宝': 'địa bảo',
  '武器': 'vũ khí',
  '护符': 'hộ phù',
  '腕饰': 'uyển sức',
  '衣服': 'y phục',
  '鞋子': 'hài tử',
  '手部': 'tay',
  '腰部': 'eo',
  '脚部': 'chân',
  '披风': 'phi phong'
};

// Translate equipment description pattern
function translateEquipment(zh) {
  // Pattern: 可在琥珀商店-装备中兑换【主X副Y】ZZZ品质等级的WWW。
  const match = zh.match(/可在琥珀商店-装备中兑换【主(.+?)副(.+?)】(\d+\/\d+)品质等级的(.+?)。/);
  if (match) {
    const [, mainStat, subStat, quality, equipType] = match;
    const mainVi = statMap[mainStat] || mainStat;
    const subVi = statMap[subStat] || subStat;
    const equipVi = equipMap[equipType] || equipType;
    return `Có thể đổi trang bị [${mainVi} chính ${subVi} phụ] phẩm cấp ${quality} ${equipVi} tại cửa hàng Hổ Phách - Trang bị.`;
  }
  return null;
}

// Manual translations for specific items
const manualTranslations = {
  // Story chapter names
  '琉璃幻梦': 'Lưu Ly Huyễn Mộng',
  '破妄显真': 'Phá Vọng Hiển Chân',
  '无相者众': 'Vô Tướng Giả Chúng',
  '双重禁制': 'Song Trùng Cấm Chế',

  // Skill names
  '摇光冲撞': 'Dao Quang Xung Chàng',
  '孙七普攻': 'Tôn Thất Phổ Công',
  '召妖诀·晖暮熠光': 'Triệu Yêu Quyết - Huy Mộ Dực Quang',
  '玉净瓶·妖藤裂涌': 'Ngọc Tịnh Bình - Yêu Đằng Liệt Dũng',
  '地火红莲·爆炎': 'Địa Hỏa Hồng Liên - Bạo Viêm',
  '蜈毒冲噬': 'Ngô Độc Xung Phệ',
  '毒蜈绞缠': 'Độc Ngô Giảo Triền',
  '魇音之唤': 'Yểm Âm Chi Hoán',
  '混乱旋律': 'Hỗn Loạn Tuyền Luật',
  '召唤白骨': 'Triệu Hoán Bạch Cốt',
  '冰霜之力': 'Băng Sương Chi Lực',
  '位移-雪': 'Vị Di - Tuyết',
  '前后刀-冰': 'Tiền Hậu Đao - Băng',
  '前后刀-雪': 'Tiền Hậu Đao - Tuyết',
  '鸢影飞弹': 'Diên Ảnh Phi Đạn',
  '百羽分形': 'Bách Vũ Phân Hình',
  '鸿影疾突': 'Hồng Ảnh Tật Đột',
  '幻影冲击': 'Huyễn Ảnh Xung Kích',
  '破军撼地': 'Phá Quân Hám Địa',
  '摇光冲撞_终结一击': 'Dao Quang Xung Chàng - Chung Kết Nhất Kích',
  '攫石陷阵': 'Quắc Thạch Hãm Trận',
  '机枢飞星': 'Cơ Khu Phi Tinh',
  '天工雷狱': 'Thiên Công Lôi Ngục',
  '六合回环': 'Lục Hợp Hồi Hoàn',
  '锢魂规仪': 'Cố Hồn Quy Nghi',
  '惊霆索灵': 'Kinh Đình Sách Linh',
  '地动山摇': 'Địa Động Sơn Dao',
  '雪球杂技': 'Tuyết Cầu Tạp Kỹ',
  '佛莲绽放': 'Phật Liên Trán Phóng',
  '昏迷飞弹': 'Hôn Mê Phi Đạn',
  '冰骨千灭': 'Băng Cốt Thiên Diệt',
  '破冰': 'Phá Băng',
  '暴风雪': 'Bão Phong Tuyết',
  '极乐幻境': 'Cực Lạc Huyễn Cảnh',
  '白骨祟风': 'Bạch Cốt Sùng Phong',
  '冰封禁制': 'Băng Phong Cấm Chế',
  '通慧执': 'Thông Huệ Chấp',
  '冰渊永寂': 'Băng Uyên Vĩnh Tịch',
  '冰裂万向': 'Băng Liệt Vạn Hướng',
  '天地冰封': 'Thiên Địa Băng Phong',
  '迷幻粉': 'Mê Huyễn Phấn',
  '寒葬': 'Hàn Táng',
  '霜刃回风': 'Sương Nhận Hồi Phong',
  '位移攻击-冰': 'Vị Di Công Kích - Băng',
  '位移攻击-雪': 'Vị Di Công Kích - Tuyết',
  '决战·伐邪破障复清天': 'Quyết Chiến - Phạt Tà Phá Chướng Phục Thanh Thiên',
  '决战阶段': 'Giai Đoạn Quyết Chiến',
  '营地净化度': 'Độ Tịnh Hóa Doanh Trại',
  '形象页违规': 'Trang Hình Ảnh Vi Phạm',
  '名片违规': 'Danh Thiếp Vi Phạm',
  '炽羽': 'Sí Vũ',
  '增压': 'Tăng Áp',
  '莲华妙法·绽放': 'Liên Hoa Diệu Pháp - Trán Phóng',
  '背水一战·治疗': 'Bối Thủy Nhất Chiến - Trị Liệu',
  '烬燃术': 'Tẫn Nhiên Thuật',
  '魔盾固守·血渴': 'Ma Thuẫn Cố Thủ - Huyết Khát',
  '胃土雉': 'Vị Thổ Trĩ',
  '中间花朵': 'Hoa ở giữa',
  '两侧花朵': 'Hoa hai bên',
  '尾巴一': 'Đuôi một',
  '尾巴二': 'Đuôi hai',
  '尾巴三': 'Đuôi ba',
  '身体花纹': 'Hoa văn thân',
  '尾巴花纹': 'Hoa văn đuôi',
  '天音初始神兵礼包': 'Gói Quà Thần Binh Sơ Cấp Thiên Âm',
  '天音进阶神兵礼包': 'Gói Quà Thần Binh Tiến Giai Thiên Âm',
  '夔牛岛众生百态匣': 'Hộp Chúng Sinh Bách Thái Đảo Quỳ Ngưu',
  '415品级装备自选礼包': 'Gói Quà Trang Bị Tự Chọn Phẩm Cấp 415',

  // Story text
  '原想随无相者潜入，却被守卫灵偶当作未戴面具的次品拦在满月祭外。灵偶老大则借机提出，若能向其展现足够决意与法力，便可换取无相者面具，踏入真正大道。':
    'Vốn định theo Vô Tướng Giả lén vào, nhưng bị linh ngẫu bảo vệ coi như thứ phẩm chưa đeo mặt nạ chặn lại ngoài Mãn Nguyệt Tế. Linh ngẫu đầu lĩnh nhân cơ hội đề xuất, nếu có thể thể hiện đủ quyết tâm và pháp lực, có thể đổi lấy mặt nạ Vô Tướng Giả, bước vào đại đạo thực sự.',

  '甫入灵枢府，便觉阴寒森然——尤以那些举止诡谲、异常热情的无相者为甚。无相者、引渡使次第登场，这座沉寂的灵枢府，骤然成了一方热闹非凡的戏台。':
    'Vừa vào Linh Khu Phủ, liền cảm thấy âm hàn rờn rợn - đặc biệt là những Vô Tướng Giả có cử chỉ quái dị, nhiệt tình bất thường. Vô Tướng Giả, Dẫn Độ Sứ lần lượt xuất hiện, tòa Linh Khu Phủ trầm tịch này đột nhiên trở thành một sân khấu náo nhiệt.',

  '两道禁制，解法各异。先于暗处设下法阵，诱蜃妖上钩；再以入念法门深入另一重照夜白禁制，得知楚玄因病与霜龙遗骸融合之过往，后又于念境深处击溃方荼残念，终破除禁制。':
    'Hai đạo cấm chế, cách giải khác nhau. Trước tiên lập pháp trận ở nơi tối, dụ sấn yêu mắc bẫy; sau đó dùng Nhập Niệm Pháp Môn đi sâu vào một trùng cấm chế Chiếu Dạ Bạch khác, biết được quá khứ Sở Huyền vì bệnh mà hợp nhất với di hài Sương Long, sau đó lại ở sâu trong niệm cảnh đánh tan tàn niệm của Phương Đồ, cuối cùng phá bỏ cấm chế.',

  '不知为何，念境仍未止息。再次进到那片血雾之中，见无名缄默，墓碑无穷，更有……蚩尤破封而出！此间种种，是幻是真？重重迷雾，缘何而生？而这念境……又为谁所有？':
    'Không biết vì sao, niệm cảnh vẫn chưa dừng lại. Lại tiến vào mảng huyết vụ đó, thấy Vô Danh im lặng, bia mộ vô tận, còn có... Xi Vưu phá phong mà ra! Những điều này là huyễn hay thật? Mịt mù trùng trùng, vì sao mà sinh? Còn niệm cảnh này... thuộc về ai?',

  '心绪纷扰之际，所设困兽阵忽生异动。阵中霜华蜃妖灵光澄澈，敌意未消。然向其阐明破禁本意后，它默然片刻，终是为守护方荼与楚玄同生共死之誓，选择解开最后一道禁制。':
    'Giữa lúc tâm tư rối loạn, Khốn Thú Trận đã lập bỗng có dị động. Trong trận Sương Hoa Sấn Yêu linh quang trong suốt, địch ý chưa tan. Nhưng sau khi giải thích rõ bản ý phá cấm, nó im lặng giây lát, cuối cùng vì bảo vệ lời thề sống chết cùng nhau của Phương Đồ và Sở Huyền, chọn cách mở đạo cấm chế cuối cùng.',

  '谒者骤然现身，山川剧震，魔相竟被提前唤醒——整座极乐天竟随之升起，没入浩瀚星海之中！眼下唯有依无名所言，蓄势静待那直指星河深处的时机。':
    'Yết Giả đột nhiên hiện thân, sơn xuyên chấn động dữ dội, Ma Tướng bị đánh thức sớm - cả tòa Cực Lạc Thiên theo đó bay lên, chìm vào biển sao mênh mông! Lúc này chỉ có thể theo lời Vô Danh, tích lũy sức mạnh tĩnh đợi thời cơ trực chỉ sâu vào ngân hà.',

  '购买九霄行纪·昴日鸡的驰星令或流霆驰星令时享受八折折扣，不可用于升级驰星令。购买时或到期自动扣除。':
    'Được giảm giá 20% khi mua Trì Tinh Lệnh hoặc Lưu Đình Trì Tinh Lệnh của Cửu Tiêu Hành Kỷ - Mão Nhật Kê, không dùng để nâng cấp Trì Tinh Lệnh. Tự động trừ khi mua hoặc khi hết hạn.',

  '购买九霄行纪·毕月乌的驰星令或流霆驰星令时享受八折折扣，不可用于升级驰星令。购买时或到期自动扣除。':
    'Được giảm giá 20% khi mua Trì Tinh Lệnh hoặc Lưu Đình Trì Tinh Lệnh của Cửu Tiêu Hành Kỷ - Tất Nguyệt Ô, không dùng để nâng cấp Trì Tinh Lệnh. Tự động trừ khi mua hoặc khi hết hạn.',

  '购买九霄行纪·觜火猴的驰星令或流霆驰星令时享受八折折扣，不可用于升级驰星令。购买时或到期自动扣除。':
    'Được giảm giá 20% khi mua Trì Tinh Lệnh hoặc Lưu Đình Trì Tinh Lệnh của Cửu Tiêu Hành Kỷ - Chủy Hỏa Hầu, không dùng để nâng cấp Trì Tinh Lệnh. Tự động trừ khi mua hoặc khi hết hạn.',

  '购买九霄行纪·参水猿的驰星令或流霆驰星令时享受八折折扣，不可用于升级驰星令。购买时或到期自动扣除。':
    'Được giảm giá 20% khi mua Trì Tinh Lệnh hoặc Lưu Đình Trì Tinh Lệnh của Cửu Tiêu Hành Kỷ - Sâm Thủy Viên, không dùng để nâng cấp Trì Tinh Lệnh. Tự động trừ khi mua hoặc khi hết hạn.',

  '九霄行纪·娄金狗已经正式开启。激活驰星令，完成行纪任务，可获得云赏点、柔香结佩饰、溯光浮影背挂、紫虚凝晶匣等丰厚奖励。立刻前往查看吧！':
    'Cửu Tiêu Hành Kỷ - Lâu Kim Cẩu đã chính thức mở. Kích hoạt Trì Tinh Lệnh, hoàn thành nhiệm vụ Hành Kỷ, có thể nhận Vân Thưởng Điểm, Nhu Hương Kết Bội Sức, Tố Quang Phù Ảnh Bối Quải, Tử Hư Ngưng Tinh Hạp và nhiều phần thưởng hậu hĩnh. Mau đi xem nào!',

  '解锁时装套装：云若·梦影游仙': 'Mở khóa bộ thời trang: Vân Nhược - Mộng Ảnh Du Tiên',
  '云想衣裳·云若·梦影游仙': 'Vân Tưởng Y Thường - Vân Nhược - Mộng Ảnh Du Tiên',
  '老先生，求您救救我姐姐！救救她……': 'Lão tiên sinh, xin ngài cứu chị tôi! Cứu cô ấy...',
  '使用技能"铁骨藤"，告知方荼当年真相！': 'Sử dụng kỹ năng "Thiết Cốt Đằng", nói cho Phương Đồ biết sự thật năm xưa!',
  '使用技能"铁骨藤"，告知方荼当年真相！': 'Sử dụng kỹ năng "Thiết Cốt Đằng", nói cho Phương Đồ biết sự thật năm xưa!',
  '使用：解锁全场最佳动画【冠绝·烛幽魅影】。': 'Sử dụng: Mở khóa hoạt họa toàn trường xuất sắc nhất [Quán Tuyệt - Chúc U Mị Ảnh].',
  '使用技能照夜白，尝试唤醒霜龙之躯中沉睡的楚玄残识。': 'Sử dụng kỹ năng Chiếu Dạ Bạch, thử đánh thức tàn thức của Sở Huyền đang ngủ trong thân xác Sương Long.',
  '本次联赛拍卖分红方式为【{1}】，您在本次拍卖中分得{0}银两。': 'Phương thức chia hoa hồng đấu giá liên tái lần này là [{1}], bạn được chia {0} bạc lượng trong lần đấu giá này.',
  '使用：随机获得一件炎烬锁锋刃·动态中产出的480/480品级装备。': 'Sử dụng: Ngẫu nhiên nhận được một món trang bị phẩm cấp 480/480 từ Viêm Tẫn Tỏa Phong Nhận - Động Thái.',
  '使用：随机获得一件炎烬锁锋刃·困难中产出的480/495品级装备。': 'Sử dụng: Ngẫu nhiên nhận được một món trang bị phẩm cấp 480/495 từ Viêm Tẫn Tỏa Phong Nhận - Khốn Nan.',
  '开启宝库后，从已解锁首领的奖励库中随机获得一件该门派的最高495品质等级团本装备\\n相同部位的装备只会保留最高品质等级': 'Sau khi mở bảo khố, ngẫu nhiên nhận được một món trang bị phụ bản đoàn đội phẩm cấp cao nhất 495 của môn phái từ kho thưởng thủ lĩnh đã mở khóa\\nTrang bị cùng bộ phận chỉ giữ lại phẩm cấp cao nhất',
  '本次联赛拍卖分红方式为【{1}】，您在本次拍卖中分得{0}银两，请到邮箱处领取。': 'Phương thức chia hoa hồng đấu giá liên tái lần này là [{1}], bạn được chia {0} bạc lượng trong lần đấu giá này, vui lòng đến hòm thư nhận.',
  '命中敌人后自身物攻和法攻提高16.5%，持续8秒': 'Sau khi trúng địch, vật công và pháp công bản thân tăng 16.5%, kéo dài 8 giây',
  '26-02-19 8:00,26-03-19 8:00': '19-02-26 8:00,19-03-26 8:00',
  '决战阶段-Boss(消失阶段)描述描述(WXLPublicEvent-Formatstring-113)': 'Giai đoạn quyết chiến - Boss (Giai đoạn biến mất) mô tả (WXLPublicEvent-Formatstring-113)',
  '受慈悲戒师·方荼幻术所控制，神识混乱，无法行动。': 'Bị huyễn thuật của Từ Bi Giới Sư Phương Đồ khống chế, thần thức hỗn loạn, không thể hành động.',

  // Additional story text
  '与无名师叔会合，共探慈悲戒师执掌之地——慈悲天。却见此间信众神似魔怔，入其念境亦是一片白茫，唯有一朵晶莹剔透的花。':
    'Hội hợp với sư thúc Vô Danh, cùng thám hiểm nơi Từ Bi Giới Sư chưởng quản - Từ Bi Thiên. Nhưng thấy tín chúng nơi đây thần thái như mê cuồng, vào niệm cảnh cũng là một màu trắng xóa, chỉ có một đóa hoa trong suốt long lanh.',

  '因触碰念境之花，意外惊动慈悲戒师麾下花妖。信众于花妖邪术之下竟化作障鬼，犹豫间无名已将之诛尽，又及时阻止花妖暗中所起杀阵，力挽狂澜。':
    'Vì chạm vào đóa hoa niệm cảnh, bất ngờ kinh động Hoa Yêu dưới trướng Từ Bi Giới Sư. Tín chúng dưới tà thuật của Hoa Yêu biến thành chướng quỷ, trong lúc do dự Vô Danh đã giết sạch, lại kịp thời ngăn cản sát trận mà Hoa Yêu âm thầm dựng nên, lực vãn cuồng lan.',

  '虽击溃花妖邪术，却未能阻其遁走。所幸拾得所遗丹药，又去信请辞镜姑娘从中寻得克制之法。随后与无名师叔分头行动，深入慈悲天，继续探查慈悲戒师之虚实。':
    'Tuy đánh tan tà thuật của Hoa Yêu, nhưng không thể ngăn nó trốn thoát. May thay nhặt được đan dược bỏ lại, lại gửi thư nhờ cô nương Từ Kính tìm cách khắc chế. Sau đó cùng sư thúc Vô Danh chia nhau hành động, tiến sâu vào Từ Bi Thiên, tiếp tục thăm dò hư thực của Từ Bi Giới Sư.',

  '辞镜姑娘回信，字里行间关切之情溢于言表。后依其指点，于慈悲天解忧洞中探查慈悲戒师的用药习性，亦对慈悲戒师所知渐深。':
    'Cô nương Từ Kính hồi thư, tình cảm quan tâm tràn đầy trong từng chữ. Sau đó theo chỉ dẫn của nàng, ở Giải Ưu Động trong Từ Bi Thiên thăm dò thói quen dùng thuốc của Từ Bi Giới Sư, hiểu biết về Từ Bi Giới Sư cũng dần sâu hơn.',

  '再次与无名师叔会合，却于琉璃阶不慎遇伏，为慈悲戒师所缚。危急关头，幸得无名假扮花妖，巧施调虎离山之计，方才得救。':
    'Lại hội hợp với sư thúc Vô Danh, nhưng ở Lưu Ly Giai bất cẩn gặp phục kích, bị Từ Bi Giới Sư trói buộc. Ở thời khắc nguy cấp, may nhờ Vô Danh giả trang Hoa Yêu, khéo léo dùng kế điệu hổ ly sơn, mới được cứu thoát.',

  '先前所询皆有回音，慈悲戒师昔年竟曾因不忍错过了一线生机，以致今日之局！如今解忧洞中毒草幻药遍布，为断根源，遂引术焚爆，以免无相天再陷人痴惘。':
    'Những gì hỏi trước đều có hồi âm, Từ Bi Giới Sư năm xưa vì không nỡ mà bỏ lỡ một tia hy vọng sống, dẫn đến cục diện hôm nay! Nay Giải Ưu Động đầy độc thảo huyễn dược, để cắt đứt nguồn gốc, bèn dẫn thuật thiêu đốt, tránh để Vô Tướng Thiên lại hãm người vào mê muội.',

  '遂与无名师叔分头行动，假借无相者次品身份，向小灵偶们展露不凡，终获无相者面具。于此，也得知灵偶老大的盘算：希望借此机会，替它们这些老旧造物向主人求取一丝垂怜。':
    'Bèn cùng sư thúc Vô Danh chia nhau hành động, mượn thân phận thứ phẩm Vô Tướng Giả, triển lộ phi phàm trước các tiểu linh ngẫu, cuối cùng nhận được mặt nạ Vô Tướng Giả. Ở đây, cũng biết được tính toán của linh ngẫu đầu lĩnh: hy vọng mượn cơ hội này, thay mặt những tạo vật cũ kỹ này xin chủ nhân một chút thương xót.',

  '念境补全，方知元凶竟是亲缘尽断、大道负心的周歧。与此同时，那神机谷青年也显露本相——既是周歧，也是止欲戒师。他冷笑天道本虚，一切皆如戏本，随即隐入机关之中。':
    'Niệm cảnh bổ toàn, mới biết nguyên hung lại là Chu Kỳ - người đoạn tuyệt thân duyên, phụ bạc đại đạo. Cùng lúc đó, thanh niên Thần Cơ Cốc kia cũng hiện bản tướng - vừa là Chu Kỳ, cũng là Chỉ Dục Giới Sư. Hắn cười lạnh thiên đạo vốn hư, tất cả đều như kịch bản, rồi ẩn vào trong cơ quan.',

  '赶赴通慧戒师所在的通慧天，临近无垢净海却为结界所阻。其上两道禁制交叠相生，幽微难测，令人无从着手。未免横生枝节，唯有先于四周寻觅破禁之机。':
    'Chạy đến Thông Huệ Thiên nơi Thông Huệ Giới Sư ở, gần Vô Cấu Tịnh Hải lại bị kết giới ngăn cản. Trên đó hai đạo cấm chế chồng chéo tương sinh, u vi khó đoán, khiến người không biết bắt đầu từ đâu. Để tránh sinh thêm rắc rối, chỉ có thể trước tiên tìm kiếm cơ hội phá cấm ở bốn phía.',

  '通慧戒师竟是慈悲戒师方荼昔年挚友楚玄！洞悉禁制来历后，循无名踪迹至古神窟，却见其因后卿魔相失神。依他所言，无相天掠取信众神魂，正是为了唤醒它以实现寂灭！':
    'Thông Huệ Giới Sư lại chính là tri kỷ năm xưa của Từ Bi Giới Sư Phương Đồ - Sở Huyền! Sau khi thấu hiểu lai lịch của cấm chế, theo dấu vết Vô Danh đến Cổ Thần Quật, nhưng thấy y vì Ma Tướng Hậu Khanh mà thất thần. Theo lời y nói, Vô Tướng Thiên cướp đoạt thần hồn tín chúng, chính là để đánh thức nó thực hiện tịch diệt!',

  '请完成璇玑线第十四章《慈航不渡》。': 'Vui lòng hoàn thành chương 14 tuyến Tuyền Cơ "Từ Hàng Bất Độ".',

  // System messages
  '<RTP_MailHello>系统检测到您的形象页涉嫌违规，现已将您的形象页还原，请您以后避免此类装扮。如继续违规，则可能面临封禁处罚。</>':
    '<RTP_MailHello>Hệ thống phát hiện trang hình ảnh của bạn có dấu hiệu vi phạm, đã khôi phục trang hình ảnh của bạn, vui lòng tránh trang phục như vậy trong tương lai. Nếu tiếp tục vi phạm, có thể bị phạt khóa tài khoản.</>',

  '<RTP_MailHello>系统检测到您的名片涉嫌违规，现已将您的名片屏蔽，请您重新设置名片显示。如继续违规，则可能面临封禁处罚。</>':
    '<RTP_MailHello>Hệ thống phát hiện danh thiếp của bạn có dấu hiệu vi phạm, đã chặn danh thiếp của bạn, vui lòng thiết lập lại hiển thị danh thiếp. Nếu tiếp tục vi phạm, có thể bị phạt khóa tài khoản.</>',

  // RTP skill descriptions
  '<RTP_Default>轰焱、炎龙降世会心率提高</>': '<RTP_Default>Tỷ lệ hội tâm của Oanh Viêm, Viêm Long Giáng Thế tăng</>',
  '<RTP_Default>免疫控制效果并增加自身移动速度</>': '<RTP_Default>Miễn dịch hiệu ứng khống chế và tăng tốc độ di chuyển của bản thân</>',
  '<RTP_Default>根据造成的伤害恢复自身气血</>': '<RTP_Default>Hồi phục khí huyết bản thân theo sát thương gây ra</>',
  '<RTP_Default>莲华妙法产生的气血恢复效果</>': '<RTP_Default>Hiệu quả hồi phục khí huyết tạo ra bởi Liên Hoa Diệu Pháp</>',
  '<RTP_Default>受到玩家伤害降低</>': '<RTP_Default>Sát thương nhận từ người chơi giảm</>',
  '<RTP_SkillTitleName>免疫</><RTP_Default>所有控制效果，受到玩家伤害降低</>': '<RTP_SkillTitleName>Miễn dịch</><RTP_Default>tất cả hiệu ứng khống chế, sát thương nhận từ người chơi giảm</>',
};

// Load existing translations from translations_all.json for reference
let existingTranslations = new Map();
try {
  const existing = JSON.parse(fs.readFileSync('translations/translations_all.json', 'utf8'));
  for (const item of existing) {
    if (item.vi && item.zh) {
      existingTranslations.set(item.zh, item.vi);
    }
  }
  console.log('Loaded existing translations:', existingTranslations.size);
} catch(e) {
  console.log('Could not load existing translations');
}

// Substring-based patches for long RTP skills and story text
const substringPatches = [
  // Story items
  {
    match: '慈心照夜，镜花水月',
    vi: 'Từ tâm chiếu đêm, gương hoa đáy nước. Sau khi phá vỡ ảo vọng của Từ Bi Giới Sư Phương Đồ, một viên "Phật Châu - Bệnh Chi Khổ" hiện hình trên Lưu Ly Giai. Đến đây, cũng kiên định quyết tâm, phải để Tịch Diệt Chi Ngôn không còn có thể bóp nghẹt những tiếng nói cầu sinh!'
  },
  {
    match: '与无名师叔会合后，一同前往止欲戒师',
    vi: 'Sau khi hội hợp với sư thúc Vô Danh, cùng nhau tiến đến Chỉ Dục Thiên do Chỉ Dục Giới Sư quản lý. Dưới bức tường khổng lồ ngoài An Tức Lâm, nhìn thấy một hàng Vô Tướng Giả "đã được giải thoát" đang lặng lẽ đi vào, bèn lén theo dõi, cho đến trước Linh Khu Phủ.'
  },
  {
    match: '以入念法门窥破机关运转',
    vi: 'Dùng Nhập Niệm Pháp Môn để khám phá cơ quan vận chuyển, cuối cùng đến được phế tích diệt môn Thần Cơ Cốc. Hóa ra Chỉ Dục Giới Sư Chu Kỳ, lại chính là Thiếu Cốc Chủ Thần Cơ Cốc năm xưa! Tuy nhiên niệm cảnh tàn khuyết, cần phải tìm được vật then chốt trong Linh Khu Phủ, mới có thể bổ sung hoàn chỉnh sân khấu, kết thúc vở "hí kịch" này.'
  },
  {
    match: '已终，余韵难平。止欲戒师的光阴与神魂',
    vi: '"Hí kịch" đã kết thúc, dư vận khó bình. Thời gian và thần hồn của Chỉ Dục Giới Sư, mãi mãi ngưng đọng vào ngày thảm án, không bao giờ tiến về phía trước. Nhưng dù cùng một pháp môn, tâm niệm khác nhau, đạo cũng khác đường, tuyệt không thể để hắn coi người sống như linh ngẫu mà đùa bỡn.'
  },
  {
    match: '水中捞月，对风讨价',
    vi: 'Vớt trăng trong nước, mặc cả với gió. Chỉ Dục Giới Sư Chu Kỳ chết cũng chưa ngộ, tuy vậy vọng phá trần quy, nhân quả tự hiện, một viên "Phật Châu - Cầu Bất Đắc Khổ" hiện hình tại Đoạn Vọng Nhai. Tiếp theo phải khẩn trương đến Thông Huệ Thiên, vì chúng sinh mở ra một con đường bất diệt!'
  },
  {
    match: '为阻魔相复苏，亦为将',
    vi: 'Để ngăn Ma Tướng hồi sinh, cũng để giải phóng hoàn toàn thân xác hợp nhất đau khổ "Thông Huệ Giới Sư" khỏi giam cầm, cùng Vô Danh xông vào Vô Cấu Tịnh Hải. Sau khi chém đứt sự trói buộc của tà pháp, bất ngờ thực sự đánh thức được một sợi thần thức trong sáng của Sở Huyền.'
  },
  {
    match: '离如沙漏，归期在彼',
    vi: 'Chia ly như đồng hồ cát, ngày trở về ở phía kia. Sau khi một sợi thần thức thuộc riêng về Sở Huyền tiêu tán, trong Vô Cấu Tịnh Hải hiện hình "Phật Châu - Ái Biệt Ly Khổ". Còn Thông Huệ Giới Sư đã chết, Sương Long Chi Hựu cũng theo đó tan biến, nên tranh thủ cơ hội này, trực chỉ nơi Ma Tướng ở, một đòn phá vỡ căn bản của hắn.'
  },
  // RTP Skills
  {
    match: '灵爆</><RTP_Default>从专精率中额外获得100%增益',
    vi: '<RTP_SkillTitleName>Linh Bạo</><RTP_Default>nhận thêm 100% tăng ích từ tỷ lệ chuyên tinh</>\r\n<RTP_Default>Khi thi triển </><RTP_SkillTitleName>Linh Bạo</><RTP_Default> triệu hồi 3 con linh đồn giận dữ tại vị trí mục tiêu, sau một khoảng chậm trễ ngắn gây thêm </><RTP_SkillHurtNumber>${common_damage(5.4,0,0,0,0,0,0,0,0,0)}</><RTP_Default>sát thương pháp thuật</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Linh Đồn Oanh Tạc</><RTP_Default>sát thương gây ra cho người chơi giảm </><RTP_SkillHurtNumber>25%</>'
  },
  {
    match: '在周围气血最低的队友位置召唤一朵莲花',
    vi: '<RTP_Default>Triệu hồi một đóa sen tại vị trí đồng đội có khí huyết thấp nhất xung quanh, sen liên tục hồi phục đồng đội xung quanh, sau một khoảng thời gian nở ra tạo hiệu quả trị liệu mạnh mẽ, hồi phục khí huyết cho tối đa 10 đồng đội trong phạm vi rộng</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Liên Hoa Diệu Pháp</><RTP_Default>khi trúng hơn 5 đồng đội hiệu quả hồi phục sẽ giảm đáng kể</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Thời gian duy trì sen</><RTP_Default>：</><RTP_SkillTitleName>5 giây</>\r\n<RTP_SkillTitleName>Hồi phục khí huyết liên tục</><RTP_Default>：</><RTP_SkillHealNumber>${lianhuamiaofachixuzhiliao} điểm mỗi lần</>\r\n<RTP_SkillTitleName>Hồi phục khí huyết khi nở</><RTP_Default>：</><RTP_SkillHealNumber>${lianhuamiaofazhiliao}</>'
  },
  {
    match: '每次</><RTP_SkillTitleName>灵昧</><RTP_Default>造成的伤害时，都有5%概率',
    vi: '<RTP_Default>Mỗi khi </><RTP_SkillTitleName>Linh Muội</><RTP_Default>gây sát thương, có 5% xác suất tạo ra một vụ nổ trên mục tiêu, vụ nổ sẽ gây </><RTP_SkillHurtNumber>${common_damage(0.8,0,0,0,0,0,0,0,0,0)}sát thương pháp thuật</><RTP_Default>cho mục tiêu và kẻ địch trong phạm vi 6 mét, mỗi 1% chuyên tinh tăng 2% sát thương Liêu Nguyên</>'
  },
  {
    match: '使下一个</><RTP_SkillTitleName>无量寿',
    vi: '<RTP_Default>Tăng cường hiệu quả trị liệu của </><RTP_SkillTitleName>Vô Lượng Thọ</><RTP_Default>、</><RTP_SkillTitleName>Trấn La Sát - Tịnh</><RTP_Default>tiếp theo</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Tăng cường trị liệu</><RTP_Default>：</><RTP_SkillHealNumber>10%</>'
  },
  {
    match: '向前方连续高速用禅杖攻击',
    vi: '<RTP_Default>Liên tục dùng thiền trượng tấn công về phía trước với tốc độ cao, nhanh đến mức chỉ có thể thấy bóng mờ của thiền trượng, mỗi lần tấn công trúng tăng </><RTP_SkillTitleName>Phạn Âm</><RTP_Default>và kéo dài hiệu ứng </><RTP_SkillTitleName>Khống cứng</><RTP_Default>trên địch</>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Loại sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>${tianlongyecha}</>\r\n<RTP_SkillTitleName>Sát thương gây ra cho người chơi giảm：50%</>\r\n<RTP_SkillTitleName>Phạn Âm tăng：</><RTP_SkillPower>Tổng 40 điểm</>'
  },
  {
    match: '释放</><RTP_SkillTitleName>杖法技能</><RTP_Default>期间，天音受到伤害降低',
    vi: '<RTP_Default>Trong thời gian thi triển </><RTP_SkillTitleName>Kỹ năng trượng pháp</><RTP_Default>, Thiên Âm giảm </><RTP_SkillTitleName>30%</><RTP_Default>sát thương nhận vào</>\r\n<RTP_Default></>\r\n<RTP_Default>Sau khi mở khóa kỹ năng </><RTP_SkillTitleName>Hàng Long Phục Tượng</><RTP_Default>: Khi kỹ năng môn phái Thiên Âm </><RTP_SkillTitleName>Hất bay</><RTP_Default>địch, trong </><RTP_SkillTitleName>5 giây</><RTP_Default>có thể thi triển thêm một lần </><RTP_SkillTitleName>Hàng Long Phục Tượng</><RTP_Default>(hiệu ứng này tối đa kích hoạt 1 lần mỗi 10 giây), lần </><RTP_SkillTitleName>Hàng Long Phục Tượng</><RTP_Default>đó trong khi thi triển bản thân </><RTP_SkillTitleName>Bá Thể</>'
  },
  {
    match: '慈心咒</><RTP_Default>释放时有概率获得</><RTP_SkillTitleName>慈悲为怀',
    vi: '<RTP_SkillTitleName>Từ Tâm Chú</><RTP_Default>khi thi triển có xác suất nhận được hiệu ứng </><RTP_SkillTitleName>Từ Bi Vi Hoài</><RTP_Default>(mỗi 1% tỷ lệ điều tức tăng 1% xác suất này)</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Từ Bi Vi Hoài</><RTP_Default>：Tăng cường hiệu quả trị liệu của </><RTP_SkillTitleName>Vô Lượng Thọ</><RTP_Default>、</><RTP_SkillTitleName>Trấn La Sát - Tịnh</><RTP_Default>tiếp theo</>\r\n<RTP_Default>&</>\r\n<RTP_SkillTitleName>Từ Tâm Chú</><RTP_Default>khi thi triển có xác suất nhận được hiệu ứng </><RTP_SkillTitleName>Từ Bi Vi Hoài</><RTP_Default>(mỗi 1% tỷ lệ điều tức tăng 2% xác suất này)</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Từ Bi Vi Hoài</><RTP_Default>：Tăng cường hiệu quả trị liệu của </><RTP_SkillTitleName>Vô Lượng Thọ</><RTP_Default>、</><RTP_SkillTitleName>Trấn La Sát - Tịnh</><RTP_Default>tiếp theo</>'
  },
  {
    match: '对目标造成伤害，恢复1颗玄火珠，并使目标在一段时间内持续受到伤害。业火难灭拥有2层充能',
    vi: '<RTP_Default>Gây sát thương cho mục tiêu, hồi phục 1 viên Huyền Hỏa Châu, và khiến mục tiêu chịu sát thương liên tục trong một khoảng thời gian. Nghiệp Hỏa Nan Diệt có 2 lớp nạp năng</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Hỏa thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(1.4,0,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Thời gian sát thương liên tục：</><RTP_SkillTitleName>15 giây</>\r\n<RTP_SkillTitleName>Sát thương liên tục：</><RTP_SkillHurtNumber>${common_damage(0.05,0,0,0,0,0,0,0,0,0)}sát thương hỏa thuộc tính</>\r\n<RTP_SkillTitleName>Khoảng cách hiệu ứng sát thương liên tục：1.5 giây</>\r\n<RTP_SkillTitleName>Hiệu ứng：Sát thương gây ra cho người chơi giảm 50%</>'
  },
  {
    match: '瞬间燃爆敌人，造成伤害，并恢复1颗玄火珠。灵火炙魂拥有2层充能',
    vi: '<RTP_Default>Lập tức đốt cháy kẻ địch, gây sát thương và hồi phục 1 viên Huyền Hỏa Châu. Linh Hỏa Chích Hồn có 2 lớp nạp năng</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Pháp thuật</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(2.8,0,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Hiệu ứng：Sát thương gây ra cho người chơi giảm 50%</>'
  },
  {
    match: '三段连击，攻击前方敌人，造成范围伤害，并有概率获得拂袖千星·暗香',
    vi: '<RTP_Default>Ba đoạn liên kích, tấn công kẻ địch phía trước, gây sát thương diện rộng và có xác suất nhận được Phất Tụ Thiên Tinh - Ám Hương</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.65,0,0,0,0,0,0,0,0)}/${common_damage(0,0.75,0,0,0,0,0,0,0,0)}/${common_damage(0,0.85,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Xác suất nhận Phất Tụ Thiên Tinh - Ám Hương：</><RTP_SkillPower>50%</>'
  },
  {
    match: '施放灵言咒法，对目标位置所有敌人造成伤害和击飞效果，并附加</><RTP_SkillTitleName>灵昧</><RTP_Default>效果</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>灵昧</><RTP_Default>会在受到</><RTP_SkillTitleName>焚秽</><RTP_Default>和</><RTP_SkillTitleName>万炎归宗</><RTP_Default>的伤害时被引爆，造成额外伤害，灵昧最多叠加60层，多个目标同时触发时伤害会递减',
    vi: '<RTP_Default>Thi triển Linh Ngôn chú pháp, gây sát thương và hiệu ứng hất bay cho tất cả kẻ địch tại vị trí mục tiêu, đồng thời phụ thêm hiệu ứng </><RTP_SkillTitleName>Linh Muội</><RTP_Default></>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Linh Muội</><RTP_Default>sẽ bị kích nổ khi nhận sát thương từ </><RTP_SkillTitleName>Phần Uế</><RTP_Default>và </><RTP_SkillTitleName>Vạn Viêm Quy Tông</><RTP_Default>, gây sát thương thêm, Linh Muội tối đa chồng 60 lớp, khi nhiều mục tiêu cùng kích hoạt sát thương sẽ giảm dần</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Pháp thuật</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(1,0,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Số lớp Linh Muội phụ thêm：</><RTP_SkillTitleName>5 lớp</>\r\n<RTP_SkillTitleName>Sát thương Linh Muội：</><RTP_SkillHurtNumber>${common_damage(0.21,0,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Sát thương Linh Muội gây ra cho người chơi giảm 10%</>\r\n<RTP_SkillTitleName>Thời gian hất bay：2 giây</>'
  },
  {
    match: '施放灵言咒法，对目标位置所有敌人造成伤害和击飞效果，并附加</><RTP_SkillTitleName>灵昧</><RTP_Default>效果</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>灵昧</><RTP_Default>会在受到</><RTP_SkillTitleName>焚秽</><RTP_Default>和</><RTP_SkillTitleName>万炎归宗</><RTP_Default>的伤害时被引爆，造成额外伤害，灵昧最多叠加60层</>\r\n',
    vi: '<RTP_Default>Thi triển Linh Ngôn chú pháp, gây sát thương và hiệu ứng hất bay cho tất cả kẻ địch tại vị trí mục tiêu, đồng thời phụ thêm hiệu ứng </><RTP_SkillTitleName>Linh Muội</><RTP_Default></>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Linh Muội</><RTP_Default>sẽ bị kích nổ khi nhận sát thương từ </><RTP_SkillTitleName>Phần Uế</><RTP_Default>và </><RTP_SkillTitleName>Vạn Viêm Quy Tông</><RTP_Default>, gây sát thương thêm, Linh Muội tối đa chồng 60 lớp</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Pháp thuật</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(1,0,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Số lớp Linh Muội phụ thêm：</><RTP_SkillTitleName>5 lớp</>\r\n<RTP_SkillTitleName>Sát thương Linh Muội：</><RTP_SkillHurtNumber>${common_damage(0.21,0,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Sát thương Linh Muội gây ra cho người chơi giảm 10%</>\r\n<RTP_SkillTitleName>Thời gian hất bay：2 giây</>'
  },
  {
    match: '召唤飞剑快速对敌方造成伤害并恢复1颗玄火珠',
    vi: '<RTP_Default>Triệu hồi phi kiếm nhanh chóng gây sát thương cho địch và hồi phục 1 viên Huyền Hỏa Châu</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Pháp thuật</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0.6,0,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Hiệu ứng：Sát thương gây ra cho người chơi giảm 50%</>'
  },
  {
    match: '真霆雷动</><RTP_Default>的基础伤害提高',
    vi: '<RTP_SkillTitleName>Chân Đình Lôi Động</><RTP_Default>sát thương cơ bản tăng </><RTP_SkillHurtNumber>25</><RTP_SkillHurtNumber>%</><RTP_Default>, sau khi thi triển khiến </><RTP_SkillTitleName>Dẫn Lôi Quyết</><RTP_Default>tiếp theo có sát thương cơ bản tăng </><RTP_SkillHurtNumber>25</><RTP_SkillHurtNumber>%</><RTP_Default>, và không cần tiêu hao </><RTP_SkillPower>Thiên Lôi Ấn</>'
  },
  {
    match: '在一个敌方位置引发水爆，对目标造成伤害和减速效果</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>灵爆</><RTP_Default>命中时获得1层</><RTP_SkillTitleName>灵吟</><RTP_Default>效果</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>灵爆</><RTP_Default>对玩家造成的伤害降低</><RTP_SkillHurtNumber>25%</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>伤害类型',
    vi: '<RTP_Default>Gây vụ nổ nước tại vị trí một kẻ địch, gây sát thương và hiệu ứng giảm tốc cho mục tiêu</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Linh Bạo</><RTP_Default>khi trúng nhận được 1 lớp hiệu ứng </><RTP_SkillTitleName>Linh Ngâm</><RTP_Default></>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Linh Bạo</><RTP_Default>sát thương gây ra cho người chơi giảm </><RTP_SkillHurtNumber>25%</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Thủy thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${baozhahaitun}</>\r\n<RTP_SkillTitleName>Mức giảm tốc：70%</>\r\n<RTP_SkillTitleName>Thời gian giảm tốc：2 giây</>'
  },
  {
    match: '在一个敌方位置引发水爆，对目标造成伤害和减速效果</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>灵爆</><RTP_Default>命中时获得1层</><RTP_SkillTitleName>灵吟</><RTP_Default>效果</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>灵爆</><RTP_Default>对玩家造成的伤害降低</><RTP_SkillHurtNumber>25%</>',
    vi: '<RTP_Default>Gây vụ nổ nước tại vị trí một kẻ địch, gây sát thương và hiệu ứng giảm tốc cho mục tiêu</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Linh Bạo</><RTP_Default>khi trúng nhận được 1 lớp hiệu ứng </><RTP_SkillTitleName>Linh Ngâm</><RTP_Default></>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Linh Bạo</><RTP_Default>sát thương gây ra cho người chơi giảm </><RTP_SkillHurtNumber>25%</>'
  },
  {
    match: '明王降世咒</><RTP_Default>释放时，鬼王气血低于',
    vi: '<RTP_SkillTitleName>Minh Vương Giáng Thế Chú</><RTP_Default>khi thi triển, nếu khí huyết Quỷ Vương thấp hơn </><RTP_SkillTitleName>40%</><RTP_Default>kích hoạt：Hồi phục </><RTP_SkillHealNumber>15%</><RTP_Default>khí huyết tối đa của Quỷ Vương (hiệu ứng này tối đa kích hoạt 1 lần mỗi 100 giây)</>\r\n<RTP_Default>&</>\r\n<RTP_SkillTitleName>Minh Vương Giáng Thế Chú</><RTP_Default>khi thi triển, nếu khí huyết Quỷ Vương thấp hơn </><RTP_SkillTitleName>40%</><RTP_Default>kích hoạt：Hồi phục </><RTP_SkillHealNumber>30%</><RTP_Default>khí huyết tối đa của Quỷ Vương (hiệu ứng này tối đa kích hoạt 1 lần mỗi 100 giây)</>'
  },
  {
    match: '对周围目标造成伤害和嘲讽效果，并将目标牵引至鬼王身前，随后添加定身效果，技能释放期间鬼王</><RTP_SkillTitleName>霸体</><RTP_Default>；鬼王受到伤害时能够减少技能的冷却时间（同时最多牵引10名目标）</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>伤害类型',
    vi: '<RTP_Default>Gây sát thương và hiệu ứng khiêu khích cho mục tiêu xung quanh, đồng thời kéo mục tiêu về trước Quỷ Vương, sau đó thêm hiệu ứng định thân, trong thời gian thi triển kỹ năng Quỷ Vương </><RTP_SkillTitleName>Bá Thể</><RTP_Default>；Khi Quỷ Vương chịu sát thương có thể giảm thời gian hồi kỹ năng (đồng thời tối đa kéo 10 mục tiêu)</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>${jiehunzhua}</>\r\n<RTP_SkillTitleName>Mức khiêu khích：Thù hận trở thành 400% trong thời gian hiệu ứng</>\r\n<RTP_SkillTitleName>Thời gian khiêu khích：5</><RTP_SkillTitleName>giây</>\r\n<RTP_SkillTitleName>Thời gian định thân：2 giây</>\r\n<RTP_SkillTitleName>Giảm thời gian hồi：</><RTP_Default>Mỗi lần chịu sát thương giảm 1%</>'
  },
  {
    match: '对周围目标造成伤害和嘲讽效果，并将目标牵引至鬼王身前，随后添加定身效果，技能释放期间鬼王</><RTP_SkillTitleName>霸体</><RTP_Default>；鬼王受到伤害时能够减少技能的冷却时间（同时最多牵引10名目标）</>',
    vi: '<RTP_Default>Gây sát thương và hiệu ứng khiêu khích cho mục tiêu xung quanh, đồng thời kéo mục tiêu về trước Quỷ Vương, sau đó thêm hiệu ứng định thân, trong thời gian thi triển kỹ năng Quỷ Vương </><RTP_SkillTitleName>Bá Thể</><RTP_Default>；Khi Quỷ Vương chịu sát thương có thể giảm thời gian hồi kỹ năng (đồng thời tối đa kéo 10 mục tiêu)</>'
  },
  {
    match: '对目标造成伤害并将目标牵引至鬼王身前，随后添加定身效果，技能释放期间鬼王</><RTP_SkillTitleName>霸体</><RTP_Default>；鬼王受到伤害时能够减少技能的冷却时间</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>伤害类型',
    vi: '<RTP_Default>Gây sát thương cho mục tiêu và kéo mục tiêu về trước Quỷ Vương, sau đó thêm hiệu ứng định thân, trong thời gian thi triển kỹ năng Quỷ Vương </><RTP_SkillTitleName>Bá Thể</><RTP_Default>；Khi Quỷ Vương chịu sát thương có thể giảm thời gian hồi kỹ năng</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>${jiehunzhua}</>\r\n<RTP_SkillTitleName>Thời gian định thân：2 giây</>\r\n<RTP_SkillTitleName>Giảm thời gian hồi：</><RTP_Default>Mỗi lần chịu sát thương giảm 1%</>'
  },
  {
    match: '对目标造成伤害并将目标牵引至鬼王身前，随后添加定身效果，技能释放期间鬼王</><RTP_SkillTitleName>霸体</><RTP_Default>；鬼王受到伤害时能够减少技能的冷却时间</>',
    vi: '<RTP_Default>Gây sát thương cho mục tiêu và kéo mục tiêu về trước Quỷ Vương, sau đó thêm hiệu ứng định thân, trong thời gian thi triển kỹ năng Quỷ Vương </><RTP_SkillTitleName>Bá Thể</><RTP_Default>；Khi Quỷ Vương chịu sát thương có thể giảm thời gian hồi kỹ năng</>'
  },
  {
    match: '鬼斩重锋</><RTP_Default>攻击命中对目标添加1层',
    vi: '<RTP_SkillTitleName>Quỷ Trảm Trọng Phong</><RTP_Default>tấn công trúng thêm 1 lớp </><RTP_SkillTitleName>Thương Khẩu</><RTP_Default>cho mục tiêu；</><RTP_SkillTitleName>Quỷ Trảm Loạn Vũ</><RTP_Default>tấn công trúng thêm 3 lớp </><RTP_SkillTitleName>Thương Khẩu</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Thương Khẩu</><RTP_Default>：Trong </><RTP_SkillTitleName>30 giây</><RTP_Default>mỗi </><RTP_SkillTitleName>4 giây</><RTP_Default>chịu </><RTP_SkillHurtNumber>${shangkou}</><RTP_Default>sát thương, tối đa 10 lớp, mỗi </><RTP_SkillTitleName>1 lớp</><RTP_Default>Thương Khẩu sát thương tăng </><RTP_SkillTitleName>100%</><RTP_Default>；mỗi 1% tỷ lệ chuyên tinh tăng </><RTP_SkillHurtNumber>1%</><RTP_Default>sát thương</>\r\n<RTP_Default>&</>\r\n<RTP_SkillTitleName>Quỷ Trảm Trọng Phong</><RTP_Default>tấn công trúng thêm 1 lớp </><RTP_SkillTitleName>Thương Khẩu</><RTP_Default>cho mục tiêu；</><RTP_SkillTitleName>Quỷ Trảm Loạn Vũ</><RTP_Default>tấn công trúng thêm 3 lớp </><RTP_SkillTitleName>Thương Khẩu</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Thương Khẩu</><RTP_Default>：Trong </><RTP_SkillTitleName>3</><RTP_SkillTitleName>0</><RTP_SkillTitleName>giây</><RTP_Default>mỗi </><RTP_SkillTitleName>2</><RTP_SkillTitleName>giây</><RTP_Default>chịu </><RTP_SkillHurtNumber>${shangkou}</><RTP_Default>sát thương, tối đa 10 lớp, mỗi </><RTP_SkillTitleName>1 lớp</><RTP_Default>Thương Khẩu sát thương tăng </><RTP_SkillTitleName>100%</><RTP_Default>；mỗi 1% tỷ lệ chuyên tinh tăng </><RTP_SkillHurtNumber>1%</><RTP_Default>sát thương</>'
  },
  {
    match: '被动</><RTP_Default>：释放</><RTP_SkillTitleName>乾坤一刃</><RTP_Default>技能后，大刀状态下替换鬼斩技能</>\r\n<RTP_Default></>\r\n<RTP_Default>开始蓄力，蓄力期间自身获得</><RTP_SkillTitleName>霸体</><RTP_Default>效果</>\r\n<RTP_SkillTitleName></>\r\n<RTP_Default>蓄力结束后依据蓄力时间不同对周围敌人造成不同的伤害，满蓄时释放会向前进行位移并且最后一击能够击飞敌方</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>伤害类型',
    vi: '<RTP_SkillTitleName>Bị động</><RTP_Default>：Sau khi thi triển kỹ năng </><RTP_SkillTitleName>Càn Khôn Nhất Nhận</><RTP_Default>, ở trạng thái đại đao thay thế kỹ năng Quỷ Trảm</>\r\n<RTP_Default></>\r\n<RTP_Default>Bắt đầu tích lực, trong thời gian tích lực bản thân nhận hiệu ứng </><RTP_SkillTitleName>Bá Thể</><RTP_Default></>\r\n<RTP_SkillTitleName></>\r\n<RTP_Default>Sau khi tích lực xong, tùy theo thời gian tích lực khác nhau gây sát thương khác nhau cho kẻ địch xung quanh, khi tích đầy thi triển sẽ dịch chuyển về phía trước và đòn cuối có thể hất bay địch</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>${julingzhan}/${julingzhansha}</>\r\n<RTP_SkillTitleName>Khoảng cách dịch chuyển khi tích đầy：6 mét</>\r\n<RTP_SkillTitleName>Thời gian hất bay：</><RTP_SkillTitleName>2 giây</>\r\n<RTP_SkillTitleName>Sát thương gây ra cho người chơi giảm：</><RTP_SkillHurtNumber>50%</>'
  },
  {
    match: '被动</><RTP_Default>：释放</><RTP_SkillTitleName>乾坤一刃</><RTP_Default>技能后，大刀状态下替换鬼斩技能</>\r\n<RTP_Default></>\r\n<RTP_Default>开始蓄力，蓄力期间自身获得</><RTP_SkillTitleName>霸体</><RTP_Default>效果</>\r\n<RTP_SkillTitleName></>\r\n<RTP_Default>蓄力结束后依据蓄力时间不同对周围敌人造成不同的伤害，满蓄时释放会向前进行位移并且最后一击能够击飞敌方</>',
    vi: '<RTP_SkillTitleName>Bị động</><RTP_Default>：Sau khi thi triển kỹ năng </><RTP_SkillTitleName>Càn Khôn Nhất Nhận</><RTP_Default>, ở trạng thái đại đao thay thế kỹ năng Quỷ Trảm</>\r\n<RTP_Default></>\r\n<RTP_Default>Bắt đầu tích lực, trong thời gian tích lực bản thân nhận hiệu ứng </><RTP_SkillTitleName>Bá Thể</><RTP_Default></>\r\n<RTP_SkillTitleName></>\r\n<RTP_Default>Sau khi tích lực xong, tùy theo thời gian tích lực khác nhau gây sát thương khác nhau cho kẻ địch xung quanh, khi tích đầy thi triển sẽ dịch chuyển về phía trước và đòn cuối có thể hất bay địch</>'
  },
  {
    match: '对目标发起多次攻击，并向周围至多4个目标造成溅射伤害，附带月袭效果',
    vi: '<RTP_Default>Phát động nhiều đòn tấn công vào mục tiêu, đồng thời gây sát thương văng ra tối đa 4 mục tiêu xung quanh, kèm theo hiệu ứng Nguyệt Tập</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.18,0,0,0,0,0,0,0,0)}x5</>\r\n<RTP_SkillTitleName>Hiệu ứng Nguyệt Tập：Gây sát thương cho kẻ địch xung quanh bản thân và tăng 5% tỷ lệ phá giáp của bản thân, kéo dài 5 giây</>\r\n<RTP_SkillTitleName>Sát thương Nguyệt Tập：</><RTP_SkillHurtNumber>${common_damage(0,0.3,0,0,0,0,0,0,0,0)}x4</>\r\n<RTP_SkillTitleName>Phạm vi văng：</><RTP_SkillTitleName>6 mét</>\r\n<RTP_SkillTitleName>Sát thương văng：</><RTP_SkillHurtNumber>${common_damage(0,0.9,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Hiệu ứng bị động：Giảm sát thương từ quái vật tăng 10%</>'
  },
  {
    match: '召唤影子协同自身战斗，持续10分钟',
    vi: '<RTP_Default>Triệu hồi bóng tối hiệp đồng chiến đấu cùng bản thân, kéo dài 10 phút, bóng tối sẽ phối hợp tấn công khi bản thân thi triển một số kỹ năng, khi bóng tối có mặt, kỹ năng này biến thành </><RTP_SkillTitleName>Ảnh Khu Sách</>\r\n<RTP_Default>Khi khoảng cách giữa Hợp Hoan và bóng tối vượt quá 50 mét, thi triển lại kỹ năng sẽ triệu hồi lại bóng tối</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Hiệu ứng bị động：</><RTP_Default>Khi thi triển </><RTP_SkillTitleName>Nguyệt Nhận Chi Tức</><RTP_Default>, nhận được </><RTP_SkillHealNumber>${common_damage(0,0.25,0,0,0,0,0,0,0,0)}</><RTP_SkillHealNumber>khiên</><RTP_Default>, tối đa chồng </><RTP_SkillTitleName>8 lớp</><RTP_Default>, kéo dài 60 giây</>\r\n<RTP_SkillTitleName>Ảnh Khu Sách：</><RTP_Default>Điều khiển bóng tối dịch chuyển đến bên mục tiêu, gây sát thương và hiệu ứng định thân</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Bóng tối phối hợp thi triển kỹ năng：Tuyệt Tình, Nguyệt Nhận Chi Tức, Phất Tụ Thiên Tinh, Ảnh Vũ, Nguyệt</><RTP_SkillTitleName>Toái</>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Tuyệt Tình - Ảnh：</>\r\n<RTP_Default>Dịch chuyển tức thời đến vị trí mục tiêu gây sát thương</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.16,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Nguyệt Nhận Chi Tức - Ảnh：</><RTP_Default></>\r\n<RTP_Default>Dịch chuyển tức thời đến vị trí mục tiêu gây sát thương</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.375,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillHurtNumber></>\r\n<RTP_SkillTitleName>Phất Tụ Thiên Tinh - Ảnh：</><RTP_Default></>\r\n<RTP_Default>Phóng phi tiêu về hướng mục tiêu hiện tại, gây sát thương</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.48,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillHurtNumber></>\r\n<RTP_SkillTitleName>Ảnh Vũ - Ảnh：</><RTP_Default></>\r\n<RTP_Default>Bóng tối dịch chuyển tức thời đến bên mục tiêu được chọn, gây sát thương cho tất cả kẻ địch xung quanh, và sau 1 giây gây hất bay</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.6,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Thời gian hất bay：2 giây</>\r\n<RTP_SkillHurtNumber></>\r\n<RTP_SkillTitleName>Nguyệt Toái - Ảnh：</><RTP_Default></>\r\n<RTP_Default>Gây tối đa ba đòn sát thương liên tiếp cho tất cả kẻ địch xung quanh bóng tối</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.3,0,0,0,0,0,0,0,0)}/${common_damage(0,0.4,0,0,0,0,0,0,0,0)}/${common_damage(0,0.5,0,0,0,0,0,0,0,0)}</>'
  },
  {
    match: '召唤影子协同自身战斗，持续180秒',
    vi: '<RTP_Default>Triệu hồi bóng tối hiệp đồng chiến đấu cùng bản thân, kéo dài 180 giây, bóng tối sẽ phối hợp tấn công khi bản thân thi triển một số kỹ năng, khi bóng tối có mặt, kỹ năng này biến thành </><RTP_SkillTitleName>Ảnh Khu Sách</>\r\n<RTP_Default>Khi khoảng cách giữa Hợp Hoan và bóng tối vượt quá 50 mét, thi triển lại kỹ năng sẽ triệu hồi lại bóng tối</>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Hiệu ứng bị động：</><RTP_Default>Khi thi triển </><RTP_SkillTitleName>Nguyệt Nhận Chi Tức</><RTP_Default>, nhận được </><RTP_SkillHealNumber>${common_damage(0,0.25,0,0,0,0,0,0,0,0)}khiên</><RTP_Default>, tối đa chồng </><RTP_SkillTitleName>8 lớp</><RTP_Default>, kéo dài 60 giây</>\r\n<RTP_SkillTitleName>Ảnh Khu Sách：</><RTP_Default>Điều khiển bóng tối dịch chuyển đến bên mục tiêu, gây sát thương và hiệu ứng định thân</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Bóng tối phối hợp thi triển kỹ năng：Tuyệt Tình, Nguyệt Nhận Chi Tức, Phất Tụ Thiên Tinh, Ảnh Vũ, Nguyệt</><RTP_SkillTitleName>Toái</>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Tuyệt Tình - Ảnh：</>\r\n<RTP_Default>Dịch chuyển tức thời đến vị trí mục tiêu gây sát thương</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.16,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Nguyệt Nhận Chi Tức - Ảnh：</><RTP_Default></>\r\n<RTP_Default>Dịch chuyển tức thời đến vị trí mục tiêu gây sát thương</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.375,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillHurtNumber></>\r\n<RTP_SkillTitleName>Phất Tụ Thiên Tinh - Ảnh：</><RTP_Default></>\r\n<RTP_Default>Phóng phi tiêu về hướng mục tiêu hiện tại, gây sát thương</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.6,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillHurtNumber></>\r\n<RTP_SkillTitleName>Ảnh Vũ - Ảnh：</><RTP_Default></>\r\n<RTP_Default>Bóng tối dịch chuyển tức thời đến bên mục tiêu được chọn, gây sát thương cho tất cả kẻ địch xung quanh, và sau 1 giây gây hất bay</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.6,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Thời gian hất bay：2 giây</>\r\n<RTP_SkillHurtNumber></>\r\n<RTP_SkillTitleName>Nguyệt Toái - Ảnh：</><RTP_Default></>\r\n<RTP_Default>Gây tối đa ba đòn sát thương liên tiếp cho tất cả kẻ địch xung quanh bóng tối</>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Âm thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.3,0,0,0,0,0,0,0,0)}/${common_damage(0,0.4,0,0,0,0,0,0,0,0)}/${common_damage(0,0.5,0,0,0,0,0,0,0,0)}</>'
  },
  {
    match: '召唤1个戾刺辅助攻击',
    vi: '<RTP_Default>Triệu hồi 1 Lệ Thích hỗ trợ tấn công, mỗi lần Lệ Thích tấn công sẽ hồi phục một lượng khí huyết cho đồng đội, kéo dài 10 giây, hiệu quả trị liệu của Lệ Thích được triệu hồi bởi người chơi chức trách đầu ra giảm 80%, người chơi chức trách tank giảm 30%</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_Default>Pháp thuật</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${fabaoyinhundeng_gongji}</>\r\n<RTP_SkillTitleName>Trị liệu：</><RTP_SkillHealNumber>${fabaoyinhundeng_zhiliao}</>'
  },
  {
    match: '替换</><RTP_SkillTitleName>炎龙降世',
    vi: '<RTP_Default>Thay thế </><RTP_SkillTitleName>Viêm Long Giáng Thế</>\r\n<RTP_Default>Thi triển Linh Ngôn chú pháp, gây sát thương và hiệu ứng hất bay cho tất cả kẻ địch tại vị trí mục tiêu, đồng thời phụ thêm hiệu ứng </><RTP_SkillTitleName>Linh Muội</><RTP_Default></><RTP_SkillTitleName></>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Linh Muội</><RTP_Default>sẽ bị kích nổ khi nhận sát thương từ </><RTP_SkillTitleName>Phần Uế</><RTP_Default>và </><RTP_SkillTitleName>Vạn Viêm Quy Tông</><RTP_Default>, gây sát thương thêm, Linh Muội tối đa chồng 60 lớp</><RTP_SkillTitleName>，</><RTP_Default>khi nhiều mục tiêu cùng kích hoạt sát thương sẽ giảm dần</>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Pháp thuật</><RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(1,0,0,0,0,0,0,0,0,0)}</><RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Số lớp Linh Muội phụ thêm：</><RTP_SkillTitleName>5 lớp</>\r\n<RTP_SkillTitleName>Sát thương Linh Muội：</><RTP_SkillHurtNumber>${common_damage(0.21,0,0,0,0,0,0,0,0,0)}</><RTP_Default></>\r\n<RTP_SkillTitleName>Sát thương Linh Muội gây ra cho người chơi giảm 10%</>\r\n<RTP_SkillTitleName>Thời gian hất bay：2 giây</>'
  },
  {
    match: '合欢每次释放</><RTP_SkillTitleName>月刃之息</><RTP_Default>时，都有20%概率使下个</><RTP_SkillTitleName>月刃之息</><RTP_Default>获得强化，使其附带</><RTP_SkillTitleName>月袭</><RTP_Default>效果</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>月袭</><RTP_Default>会对自身周围敌人造成4次伤害，并使自身的破甲率提高，持续5秒</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>伤害类型',
    vi: '<RTP_Default>Mỗi khi Hợp Hoan thi triển </><RTP_SkillTitleName>Nguyệt Nhận Chi Tức</><RTP_Default>, có 20% xác suất khiến </><RTP_SkillTitleName>Nguyệt Nhận Chi Tức</><RTP_Default>tiếp theo được tăng cường, khiến nó kèm theo hiệu ứng </><RTP_SkillTitleName>Nguyệt Tập</><RTP_Default></>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Nguyệt Tập</><RTP_Default>sẽ gây 4 lần sát thương cho kẻ địch xung quanh bản thân, và tăng tỷ lệ phá giáp của bản thân, kéo dài 5 giây</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,0.3,0,0,0,0,0,0,0,0)}x4</>\r\n<RTP_SkillTitleName>Tỷ lệ phá giáp tăng：</><RTP_SkillHurtNumber>5%</>'
  },
  {
    match: '合欢每次释放</><RTP_SkillTitleName>月刃之息</><RTP_Default>时，都有20%概率使下个</><RTP_SkillTitleName>月刃之息</><RTP_Default>获得强化，使其附带</><RTP_SkillTitleName>月袭</><RTP_Default>效果</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>月袭</><RTP_Default>会对自身周围敌人造成4次伤害，并使自身的破甲率提高，持续5秒</>',
    vi: '<RTP_Default>Mỗi khi Hợp Hoan thi triển </><RTP_SkillTitleName>Nguyệt Nhận Chi Tức</><RTP_Default>, có 20% xác suất khiến </><RTP_SkillTitleName>Nguyệt Nhận Chi Tức</><RTP_Default>tiếp theo được tăng cường, khiến nó kèm theo hiệu ứng </><RTP_SkillTitleName>Nguyệt Tập</><RTP_Default></>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Nguyệt Tập</><RTP_Default>sẽ gây 4 lần sát thương cho kẻ địch xung quanh bản thân, và tăng tỷ lệ phá giáp của bản thân, kéo dài 5 giây</>'
  },
  {
    match: '蓄力0.7秒后，位移到目标前方',
    vi: '<RTP_Default>Sau khi tích lực 0.7 giây, dịch chuyển đến trước mục tiêu, gây sát thương và </><RTP_SkillTitleName>Hất bay</><RTP_Default>cho tất cả kẻ địch trong phạm vi 6 mét tại điểm đến</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0,4,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Thời gian hất bay：2 giây</>\r\n<RTP_SkillTitleName>Hiệu ứng：Sát thương gây ra cho người chơi giảm 25%</>'
  },
  {
    match: '进入</><RTP_SkillTitleName>化元</><RTP_Default>状态，持续2秒',
    vi: '<RTP_Default>Tiến vào trạng thái </><RTP_SkillTitleName>Hóa Nguyên</><RTP_Default>, kéo dài 2 giây</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Hóa Nguyên：Trong thời gian duy trì giảm 10% sát thương nhận vào, nếu nhận đòn tấn công kỹ năng cảnh báo đặc biệt từ quái vật, sẽ miễn dịch đòn tấn công này, và tiến vào trạng thái Hóa Nguyên 0.5 giây nữa (có thể kích hoạt nhiều lần), sau khi trạng thái Hóa Nguyên kết thúc, sẽ lập tức gây một đòn sát thương vào khu vực phía trước；nếu nhận hiệu ứng khống chế, sẽ lập tức gây một </><RTP_Default>đòn sát thương</>\r\n<RTP_SkillTitleName></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Vô thuộc tính</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${huayuanfanji}</>\r\n<RTP_SkillTitleName>Mỗi lần Hóa Nguyên thành công thêm tăng sát thương Hóa Nguyên：</><RTP_SkillHurtNumber>100%</>'
  },
  {
    match: '施法后，用火焰冲击敌人造成伤害，并恢复1颗玄火珠，焚秽可减少驭火诀冷却时间',
    vi: '<RTP_Default>Sau khi thi pháp, dùng hỏa diệm xung kích địch gây sát thương và hồi phục 1 viên Huyền Hỏa Châu, Phần Uế có thể giảm thời gian hồi Ngự Hỏa Quyết</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Pháp thuật</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(1.3,0,0,0,0,0,0,0,0,0)}</>\r\n<RTP_SkillTitleName>Giảm thời gian hồi：Phần Uế mỗi lần gây sát thương giảm 0.4 giây thời gian hồi</>\r\n<RTP_SkillTitleName>Hiệu ứng：Sát thương gây ra cho người chơi giảm 50%</>'
  },
  {
    match: '短暂的施法后，引导大量飞剑攻击前方范围内所有敌人，最多造成18次伤害，每次造成伤害时都会触发灵昧效果，最后一击附带眩晕并触发更多的灵昧效果，命中1个目标时伤害提升21%</>\r\n<RTP_Default></>\r\n<RTP_Default>万炎归宗持续期间可以移动并且提高自身移动速度，引导期间获得</><RTP_SkillTitleName>霸体</><RTP_Default>效果，受到玩家伤害降低</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>伤害类型',
    vi: '<RTP_Default>Sau khi thi pháp ngắn, dẫn dắt lượng lớn phi kiếm tấn công tất cả kẻ địch trong phạm vi phía trước, tối đa gây 18 lần sát thương, mỗi lần gây sát thương đều kích hoạt hiệu ứng Linh Muội, đòn cuối kèm choáng và kích hoạt thêm nhiều hiệu ứng Linh Muội, khi trúng 1 mục tiêu sát thương tăng 21%</>\r\n<RTP_Default></>\r\n<RTP_Default>Trong thời gian Vạn Viêm Quy Tông có thể di chuyển và tăng tốc độ di chuyển, trong thời gian dẫn dắt nhận hiệu ứng </><RTP_SkillTitleName>Bá Thể</><RTP_Default>, sát thương nhận từ người chơi giảm</>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương：</><RTP_SkillHurtNumber>Pháp thuật</>\r\n<RTP_SkillTitleName>Sát thương：</><RTP_SkillHurtNumber>${common_damage(0.33,0,0,0,0,0,0,0,0,0)}x</><RTP_SkillHurtNumber>18</>\r\n<RTP_SkillTitleName>Kích hoạt Linh Muội：2 lớp</>\r\n<RTP_SkillTitleName>Đòn cuối kích hoạt Linh Muội：6 lớp</>\r\n<RTP_SkillTitleName>Tốc độ di chuyển tăng：</><RTP_SkillTitleName>25%</>\r\n<RTP_SkillTitleName>Thời gian choáng：3 giây</>\r\n<RTP_SkillTitleName>Hiệu ứng：Sát thương nhận từ người chơi giảm 30%</>'
  },
  {
    match: '短暂的施法后，引导大量飞剑攻击前方范围内所有敌人，最多造成18次伤害，每次造成伤害时都会触发灵昧效果，最后一击附带眩晕并触发更多的灵昧效果，命中1个目标时伤害提升21%</>\r\n<RTP_Default></>\r\n<RTP_Default>万炎归宗持续期间可以移动并且提高自身移动速度，引导期间获得</><RTP_SkillTitleName>霸体</><RTP_Default>效果，受到玩家伤害降低</>',
    vi: '<RTP_Default>Sau khi thi pháp ngắn, dẫn dắt lượng lớn phi kiếm tấn công tất cả kẻ địch trong phạm vi phía trước, tối đa gây 18 lần sát thương, mỗi lần gây sát thương đều kích hoạt hiệu ứng Linh Muội, đòn cuối kèm choáng và kích hoạt thêm nhiều hiệu ứng Linh Muội, khi trúng 1 mục tiêu sát thương tăng 21%</>\r\n<RTP_Default></>\r\n<RTP_Default>Trong thời gian Vạn Viêm Quy Tông có thể di chuyển và tăng tốc độ di chuyển, trong thời gian dẫn dắt nhận hiệu ứng </><RTP_SkillTitleName>Bá Thể</><RTP_Default>, sát thương nhận từ người chơi giảm</>'
  },
  // Additional RTP substring patches
  {
    match: '蓄力后跃起，在周身范围发起强力攻击',
    vi: '<RTP_Default>Sau khi tích lực nhảy lên, phát động tấn công mạnh mẽ trong phạm vi xung quanh </><RTP_SkillTitleName>Hất bay</><RTP_Default>địch；trong thời gian tích lực tốc độ di chuyển bản thân tăng mạnh；trong thời gian thi triển bản thân </><RTP_SkillTitleName>Bá Thể</><RTP_Default></>\r\n<RTP_Default></>\r\n<RTP_SkillTitleName>Loại sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>Vật lý</>\r\n<RTP_SkillTitleName>Sát thương</><RTP_Default>：</><RTP_SkillHurtNumber>${hanglongfuxiang}</>\r\n<RTP_SkillTitleName>Thời gian hất bay：</><RTP_SkillTitleName>2 giây</>\r\n<RTP_SkillTitleName>Sát thương gây ra cho người chơi giảm：</><RTP_SkillHurtNumber>50%</>'
  },
  {
    match: '下落攻击</><RTP_Default>和</><RTP_SkillTitleName>空中攻击</><RTP_Default>的冷却时间缩短',
    vi: '<RTP_SkillTitleName>Hạ Lạc Công Kích</><RTP_Default>và </><RTP_SkillTitleName>Không Trung Công Kích</><RTP_Default>thời gian hồi rút ngắn</><RTP_SkillTitleName>3 giây</>'
  },
  {
    match: '神剑御雷真</><RTP_Default>诀造成伤害时，自身最终伤害提高',
    vi: '<RTP_SkillTitleName>Thần Kiếm Ngự Lôi Chân</><RTP_Default>Quyết gây sát thương, sát thương cuối cùng bản thân tăng </><RTP_SkillHurtNumber>12%</><RTP_Default>, kéo dài </><RTP_SkillTitleName>5 giây</>'
  },
  {
    match: '鬼斩</><RTP_Default>释放时，根据湮魂爪触发率的50%',
    vi: '<RTP_SkillTitleName>Quỷ Trảm</><RTP_Default>khi thi triển, theo 50% tỷ lệ kích hoạt Yên Hồn Trảo (mỗi 1% tỷ lệ hội tâm tăng 2% xác suất này) khiến </><RTP_SkillTitleName>Liên Tinh</><RTP_Default>tiếp theo được tăng cường</>'
  },
  {
    match: '鬼王对玩家造成的伤害增加',
    vi: '<RTP_Default>Sát thương Quỷ Vương gây ra cho người chơi tăng </><RTP_SkillHurtNumber>25%</><RTP_Default>；sát thương nhận từ người chơi tăng </><RTP_SkillTitleName>25%</>'
  },
  {
    match: '祈福</><RTP_Default>的持续时间增加至',
    vi: '<RTP_SkillTitleName>Kỳ Phúc</><RTP_Default>thời gian duy trì tăng lên </><RTP_SkillTitleName>15 giây</><RTP_Default>, </><RTP_SkillTitleName>Kỳ Phúc</><RTP_Default>hiệu quả trị liệu tăng </><RTP_SkillHealNumber>30%</>'
  },
  {
    match: '受到的伤害降低</><RTP_SkillTitleName>5%</><RTP_Default>，</><RTP_SkillTitleName>瞬流光',
    vi: '<RTP_Default>Sát thương nhận vào giảm </><RTP_SkillTitleName>5%</><RTP_Default>, </><RTP_SkillTitleName>Thuấn Lưu Quang</><RTP_Default>sau khi thi triển nhận được hiệu ứng </><RTP_SkillTitleName>Bá Thể</><RTP_Default>trong </><RTP_SkillTitleName>3 giây</>'
  },
  {
    match: '天音门派技能</><RTP_SkillTitleName>击飞</><RTP_Default>敌方时，恢复自身',
    vi: '<RTP_Default>Khi kỹ năng môn phái Thiên Âm </><RTP_SkillTitleName>Hất bay</><RTP_Default>địch, hồi phục bản thân </><RTP_SkillPower>60 điểm</><RTP_SkillPower>Phạn Âm</>'
  },
  {
    match: '持戒</><RTP_Default>、</><RTP_SkillTitleName>醒世杖</><RTP_Default>、</><RTP_SkillTitle',
    vi: '<RTP_SkillTitleName>Trì Giới</><RTP_Default>, </><RTP_SkillTitleName>Tỉnh Thế Trượng</><RTP_Default>, </><RTP_SkillTitleName>Trấn La Sát</><RTP_Default>, </><RTP_SkillTitleName>Chấn Tích Độ Thế</><RTP_Default>tấn công trúng, theo tỷ lệ hội tâm kỳ vọng nhận được </><RTP_SkillPower>1-2 điểm</><RTP_SkillPower>Phạn Âm</>'
  },
  {
    match: '持戒、醒世杖、镇罗刹</><RTP_Default>、</><RTP_SkillTitleName>振锡渡世',
    vi: '<RTP_SkillTitleName>Trì Giới, Tỉnh Thế Trượng, Trấn La Sát</><RTP_Default>, </><RTP_SkillTitleName>Chấn Tích Độ Thế</><RTP_Default>tấn công trúng, theo tỷ lệ hội tâm kỳ vọng nhận được </><RTP_SkillPower>1-2 điểm</><RTP_SkillPower>Phạn Âm</>'
  },
  {
    match: '莲华妙法</><RTP_Default>召唤的莲花持续时间减少2秒',
    vi: '<RTP_SkillTitleName>Liên Hoa Diệu Pháp</><RTP_Default>sen được triệu hồi thời gian duy trì giảm 2 giây, hiệu quả trị liệu liên tục tăng </><RTP_SkillHealNumber>100%</><RTP_Default>, hiệu quả trị liệu khi nở hoa giảm </><RTP_SkillHealNumber>35%</>'
  },
  {
    match: '下落攻击</><RTP_Default>、</><RTP_SkillTitleName>空中攻击</><RTP_Default>的冷却时间减少',
    vi: '<RTP_SkillTitleName>Hạ Lạc Công Kích</><RTP_Default>, </><RTP_SkillTitleName>Không Trung Công Kích</><RTP_Default>thời gian hồi giảm </><RTP_SkillTitleName>3 giây</>'
  },
  {
    match: '鬼啸</><RTP_Default>释放后每命中1个敌方使鬼王受到来自玩家的伤害降低',
    vi: '<RTP_SkillTitleName>Quỷ Tiếu</><RTP_Default>sau khi thi triển mỗi trúng 1 địch khiến Quỷ Vương sát thương nhận từ người chơi giảm </><RTP_SkillTitleName>5%</><RTP_Default>, tối đa chồng </><RTP_SkillTitleName>4 lớp</><RTP_Default>, kéo dài </><RTP_SkillTitleName>10 giây</>'
  },
  {
    match: '魔盾固守</><RTP_Default>效果持续期间受到来自玩家伤害降低',
    vi: '<RTP_SkillTitleName>Ma Thuẫn Cố Thủ</><RTP_Default>trong thời gian hiệu ứng duy trì sát thương nhận từ người chơi giảm </><RTP_SkillTitleName>40%</>'
  },
  {
    match: '铁骨藤',
    vi: 'Sử dụng kỹ năng "Thiết Cốt Đằng", nói cho Phương Đồ biết sự thật năm xưa!'
  }
];

// Translate all items
let translated = 0;
let failed = [];

for (const item of data) {
  const zh = item.zh;

  // Try equipment pattern first
  const equipTrans = translateEquipment(zh);
  if (equipTrans) {
    item.vi = equipTrans;
    translated++;
    continue;
  }

  // Try manual translations
  if (manualTranslations[zh]) {
    item.vi = manualTranslations[zh];
    translated++;
    continue;
  }

  // Try existing translations
  if (existingTranslations.has(zh)) {
    item.vi = existingTranslations.get(zh);
    translated++;
    continue;
  }

  // Try substring patches for long RTP skills and story text
  let foundPatch = false;
  for (const patch of substringPatches) {
    if (zh.includes(patch.match)) {
      item.vi = patch.vi;
      translated++;
      foundPatch = true;
      break;
    }
  }
  if (foundPatch) continue;

  // Not translated
  failed.push(zh);
}

console.log('Translated:', translated);
console.log('Failed:', failed.length);

if (failed.length > 0) {
  console.log('\nFailed items (first 50):');
  failed.slice(0, 50).forEach((f, i) => {
    console.log((i+1) + '.', f.substring(0, 100));
  });
}

// Save
fs.writeFileSync('translations/to_translate.json', JSON.stringify(data, null, 2), 'utf8');
console.log('\nSaved to to_translate.json');
