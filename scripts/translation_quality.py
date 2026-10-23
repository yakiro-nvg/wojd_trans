"""Structural translation contracts: formatting/logic tokens are immutable."""
import collections,re
ANGLE=re.compile(r'</>|</?[A-Za-z_\u3400-\u9fff][^<>]*>')
ROUND=re.compile(r'\((?:##|@@)[^)]*\)|\(/(?:Link|Image)\)')
PRINTF=re.compile(r'%%|%(?:\d+\$)?[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|ll|h|l|j|z|t|L)?[diuoxXfFeEgGaAcsp]|%[hmntw]')
BRACES=re.compile(r'\$?\{[^{}\r\n]*\}')
# Include the complete backslash run. Otherwise a doubled literal escape can
# match at its last slash and look identical to the original single escape.
NEWLINES=re.compile(r'\\+r\\+n|\\+[nrtf]|\r\n|[\x01-\x1f]')
# Preserve every literal backslash run, without assigning control semantics.
BACKSLASH_RUNS=re.compile(r'\\+')
NUMBER=re.compile(r'[-+]?\d+(?:[.,]\d+)*(?:[%％])?')
DISPLAY=re.compile(r'(?P<prefix>\btext\s*=\s*)(?P<q>[\"\x27])(?P<value>.*?)(?P=q)',re.S)
LITERAL_PERCENT=re.compile(r'(?<=\d)%(?=$|[\s\u3400-\u9fff。，；、])')
# A2F is an ASCII technical token even beside CJK prose; longer ASCII
# identifiers containing it are not separate tokens.
PROTECTED=re.compile(r'@[pP]\([^\r\n)]*\)|@t\([^@\r\n]*@@|\(@@Image\)[^\r\n]*?\(/Image\)|\bbiaoqing_[A-Za-z0-9_]+|(?<![A-Za-z0-9_])A2F(?![A-Za-z0-9_])|█+|\|\||【(?:徒名|师名)】')
VARIANT_PREFIX=re.compile(r'(?:^|(?<=\\n))(?:原版|(?:青云|鬼王|焚香|合欢|灵汐|天音)(?:男|女|少女|萝莉)?)[：:]',re.M)

# A leading numeric SexIf selector may be consumed before prose rendering.
# Its exact colon form is retained until that consumer is demonstrated.
SEXIF_SELECTOR_PREFIX=re.compile(r'^\(@@SexIf\)[0-9]+\(/SexIf\)[：:]')

def sexif_prefix_contract(text):
    match=SEXIF_SELECTOR_PREFIX.match(text)
    return match.group() if match else None

def variant_prefix_contract(text):
    # Multi-variant dialogue labels may be branch selectors. Their consumer
    # is unproven; retain exact CJK labels, order and colon bytes defensively.
    labels=VARIANT_PREFIX.findall(text)
    return labels if len(labels)>=2 else []

def technical_contract(text):
    # Image payloads/paths and wrapper separators are data, even when they
    # contain Chinese filenames. Only the prose between them is translatable.
    return PROTECTED.findall(text)

def visible_text(text):
    if variant_prefix_contract(text):text=VARIANT_PREFIX.sub('',text)
    display=[]
    for match in ANGLE.finditer(text):
        if re.match(r'<a(?:\s|>)',match.group()):display.extend(m['value'] for m in DISPLAY.finditer(match.group()))
    return PROTECTED.sub('',BRACES.sub('',ROUND.sub('',ANGLE.sub('',text))))+' '.join(display)

def format_text(text):
    # A numeric 5% followed by Vietnamese prose such as " sát" is not printf "% s".
    # Keep actual 5%d, % d, %s and %% formatting tokens visible to the parser.
    return LITERAL_PERCENT.sub('％',text)

def markup_contract(text):
    tokens=[]
    for match in sorted(list(ANGLE.finditer(text))+list(ROUND.finditer(text)),key=lambda x:x.start()):
        token=match.group()
        if re.match(r'<a(?:\s|>)',token):
            token=DISPLAY.sub(lambda m:m['prefix']+m['q']+'__DISPLAY_TEXT__'+m['q'],token)
        tokens.append(token)
    return tokens

def numeric_contract(text):
    display=[]
    for match in ANGLE.finditer(text):
        if re.match(r'<a(?:\s|>)',match.group()):display.extend(m['value'] for m in DISPLAY.finditer(match.group()))
    plain=ROUND.sub('',ANGLE.sub('',text))+' '.join(display)
    plain=PRINTF.sub('',BRACES.sub('',format_text(plain)))
    plain=plain.replace('％','%')
    return collections.Counter(NUMBER.findall(plain))

def numbered_channel_value(text):
    # WorldPlane's explicit channel-name family uses written CJK numerals.
    # This verifies numeric equivalence only, never translates prose or proves
    # that an unknown consumer is display-only. Bare numeral tables stay separate.
    match=re.fullmatch(r'线路([一二三四五六七八九]|十[一二三四五六七八九]?|[二三四五六七八九]十[一二三四五六七八九]?|[一二三四五六七八九]百(?:零[一二三四五六七八九]|[一二三四五六七八九]十[一二三四五六七八九]?)?)',text)
    if not match:return None
    digits={'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    value=0;pending=None;last_unit=1000
    for char in match[1]:
        if char in digits:
            digit=digits[char]
            if pending is not None and pending!=0:return None
            pending=digit
        else:
            unit=10 if char=='十' else 100
            if unit>=last_unit:return None
            value+=(1 if pending is None else pending)*unit;pending=None;last_unit=unit
    value+=pending or 0
    return value if 1<=value<=999 else None

def numbered_preset_value(text):
    # MindTechnique's six display labels spell their ordinal in financial CJK
    # numerals. Recognize only these complete labels, not prose or digit tables.
    return {'方案壹':1,'方案贰':2,'方案叁':3,'方案肆':4,'方案伍':5,'方案陆':6}.get(text)

def validate(source,target):
    reasons=[]
    if not isinstance(target,str) or not target: return ['empty_target']
    try:
        if max(len(source.encode('utf-8')),len(target.encode('utf-8')))>65535:reasons.append('catalog_byte_limit')
    except UnicodeError:return ['invalid_unicode']
    if '\0' in target:reasons.append('embedded_nul')
    if '[VI]' in target:reasons.append('test_tag')
    if markup_contract(source)!=markup_contract(target):reasons.append('markup_or_logic_attribute_changed')
    if technical_contract(source)!=technical_contract(target):reasons.append('resource_or_technical_token_changed')
    if variant_prefix_contract(source)!=variant_prefix_contract(target):reasons.append('dialogue_variant_selector_changed')
    if sexif_prefix_contract(source)!=sexif_prefix_contract(target):reasons.append('numeric_sexif_prefix_changed')
    if PRINTF.findall(format_text(source))!=PRINTF.findall(format_text(target)):reasons.append('printf_argument_sequence_changed')
    if BRACES.findall(source)!=BRACES.findall(target):reasons.append('brace_placeholder_sequence_changed')
    if NEWLINES.findall(source)!=NEWLINES.findall(target):reasons.append('newline_or_escape_form_changed')
    if BACKSLASH_RUNS.findall(source)!=BACKSLASH_RUNS.findall(target):reasons.append('literal_backslash_run_sequence_changed')
    if numeric_contract(source)!=numeric_contract(target):
        # Standalone written numerals may become a numeral; body values stay literal.
        label_number=numbered_channel_value(source)
        preset_number=numbered_preset_value(source)
        if label_number is None:label_number=preset_number
        # Preset ordinals are unsigned; NUMBER deliberately remains unchanged
        # for older contracts. Do not waive a sign it cannot tokenize here.
        unsigned_preset=preset_number is None or not re.search(r'[-+\u2212\u2012\u2013\u2014\ufe63\uff0d\u207b\u208b\ufe62\uff0b]\s*\d',target)
        equivalent_label=unsigned_preset and label_number is not None and numeric_contract(target)==collections.Counter([str(label_number)])
        if not equivalent_label and not re.fullmatch('[零〇一二三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾]+',source):reasons.append('literal_numeric_value_changed')
    return reasons

if __name__=='__main__':
    for ordinal,written in enumerate('壹贰叁肆伍陆',1):
        assert not validate('方案'+written,'Bộ '+str(ordinal))
        assert 'literal_numeric_value_changed' in validate('方案'+written,'Bộ '+str(ordinal+1))
    assert 'literal_numeric_value_changed' in validate('方案壹','Bộ 1, 2')
    assert 'literal_numeric_value_changed' in validate('方案壹伤害','Bộ 1 sát thương')
    assert 'literal_numeric_value_changed' in validate('方案柒','Bộ 7')
    for sign in ('−','‒','–','—','﹣','－','⁻','₋','﹢','＋','-','+'):
        assert 'literal_numeric_value_changed' in validate('方案壹','Bộ '+sign+'1')
        assert 'literal_numeric_value_changed' in validate('方案壹','Bộ '+sign+' 1')
    assert not validate('伤害%d，持续%s秒','Sát thương %d, kéo dài %s giây')
    assert validate('%s受到%d伤害','%d sát thương lên %s')
    assert not validate('<a taskID="114" text="慈悲天" mapID="25"></>','<a taskID="114" text="Từ Bi Thiên" mapID="25"></>')
    assert validate('<a taskID="114" text="慈悲天" mapID="25"></>','<a taskID="115" text="Từ Bi Thiên" mapID="25"></>')
    assert validate('<RTP_A>3秒</>','<RTP_B>3 giây</>')
    assert validate('甲\\n乙','Giáp\nẤt')
    assert validate('3秒，最多8层','3 giây, tối đa 9 tầng')
    assert validate('属性-5','Thuộc tính 5')
    assert validate('甲\t乙','Giáp Ất')
    assert not validate('提高5%','Tăng 5% sát thương')
    assert validate('提高5%','Tăng 6% sát thương')
    assert not validate('伤害5%d','Sát thương 5%d')
    assert validate('${Name}造成{0}伤害','${Name} gây {1} sát thương')
    assert not validate('(##Color:Valid_Green)新增(##Color:Default)','(##Color:Valid_Green)Mới(##Color:Default)')
    print('Formatting, logical attributes, placeholder order, numbers and newline contracts: PASS')
