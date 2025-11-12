from config import load_config
from modules import xml_srt
import json

if __name__ == "__main__":
    cfg = load_config()

    # 讀取 OCR 結果
    with open("data/img_to_text_en.json", "r", encoding="utf-8") as f:
        image_texts_en = json.load(f)
        # print(image_texts_en)

    with open("data/img_to_text_ch.json", "r", encoding="utf-8") as f:
        image_texts_ch = json.load(f)
        print('成功')

    # 產生英文 SRT
    xml_srt.run(cfg["xml_file_name_en"], image_texts_en, make_backup=True)

    # 產生中文 SRT
    xml_srt.run(cfg["xml_file_name_ch"], image_texts_ch, make_backup=True)
