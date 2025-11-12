import os
import re
import html
import shutil
import xml.etree.ElementTree as ET

# 固定參數
FPS = 23.976

def tc_to_srt_time(tc: str, fps: float) -> str:
    # 解析 "HH:MM:SS:FF" → 毫秒 → "HH:MM:SS,mmm"
    h, m, s, f = map(int, tc.split(":"))
    total_ms = (h * 3600 + m * 60 + s) * 1000 + round(f * 1000.0 / fps)
    h = total_ms // 3600000
    total_ms %= 3600000
    m = total_ms // 60000
    total_ms %= 60000
    s = total_ms // 1000
    ms = total_ms % 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def run(xml_file_name: str, image_texts: dict, save_path: str | None = None, make_backup: bool = True):
    """
    1) 根據 image_texts 替換 XML 中 <Graphic> 文字
    2) 產生 SRT（檔名固定為 xml_file_name.srt）

    參數：
        xml_file_name (str): 要處理的 XML 路徑（輸出 SRT 亦以此為基底）
        image_texts (dict): {原文字: 新文字}
        save_path (str|None): 若提供，更新後 XML 另存到此；否則覆寫 xml_file_name
        make_backup (bool): 覆寫時是否 .bak 備份
    """
    xml_path = 'data/' + xml_file_name
    target_xml = 'output/' + xml_file_name

    # 1) 替換 XML 文字
    if make_backup and not save_path and os.path.exists(xml_path):
        backup_path = xml_path + ".bak"
        shutil.copy2(xml_path, backup_path)
        print(f"已建立備份：{backup_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    replaced = 0
    for elem in root.iter():
        tag = elem.tag.split('}')[-1]  # 去除 namespace 前綴
        if tag != "Graphic":
            continue
        text = (elem.text or "").strip()
        if text in image_texts:
            elem.text = image_texts[text]
            replaced += 1

    tree.write(target_xml, encoding="utf-8", xml_declaration=True)
    print(f"✅ XML 已替換 {replaced} 筆，已儲存：{target_xml}")

    # ===== 2) 產生 SRT（檔名固定以 xml_file_name 為基底） =====
    output_srt = "output/"+os.path.splitext(xml_file_name)[0] + ".srt"

    # 直接從「更新後要輸出的那份 XML 文字」來解析
    with open(target_xml, "r", encoding="utf-8") as f:
        xml_text = f.read()

    # 抓出所有 Event（允許換行），並取 InTC/OutTC 與 Graphic 文字（保留你的正則與流程）
    event_re = re.compile(
        r'<Event\s+[^>]*InTC="([^"]+)"\s+OutTC="([^"]+)"[^>]*>(.*?)</Event>',
        flags=re.DOTALL
    )
    graphic_re = re.compile(r"<Graphic[^>]*>(.*?)</Graphic>", flags=re.DOTALL)

    subs = []
    for m in event_re.finditer(xml_text):
        in_tc, out_tc, body = m.group(1), m.group(2), m.group(3)
        lines = [html.unescape(x.strip()) for x in graphic_re.findall(body)]
        text_block = "\n".join([l for l in lines if l]) or ""
        if not text_block:
            continue
        start = tc_to_srt_time(in_tc, FPS)
        end = tc_to_srt_time(out_tc, FPS)
        subs.append((start, end, text_block))

    with open(output_srt, "w", encoding="utf-8") as f:
        for i, (st, et, tx) in enumerate(subs, 1):
            f.write(f"{i}\n{st} --> {et}\n{tx}\n\n")

    print(f"🎬 完成！輸出：{output_srt}（共 {len(subs)} 段）")
    return replaced, output_srt
