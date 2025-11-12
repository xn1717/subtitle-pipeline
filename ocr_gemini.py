from config import load_config
from modules import ocr_gemini
import json

if __name__ == "__main__":
    cfg = load_config()

    # 英文字幕辨識
    try:
        image_texts_en = ocr_gemini.run(cfg["file_name_en"])
        if image_texts_en:
            print(image_texts_en)
            with open("data/img_to_text_en.json", "w", encoding="utf-8") as f:
                json.dump(image_texts_en, f, ensure_ascii=False, indent=2)
        else:
            print("英文字幕辨識結果 image_texts_en 為空。")
    except FileNotFoundError:
        print("沒有英文字幕圖片檔。")
    except Exception as e:
        print(f"英文字幕辨識發生錯誤：{e}")

    # 中文字幕辨識
    try:
        image_texts_ch = ocr_gemini.run(cfg["file_name_ch"])
        if image_texts_ch:
            print(image_texts_ch)
            with open("data/img_to_text_ch.json", "w", encoding="utf-8") as f:
                json.dump(image_texts_ch, f, ensure_ascii=False, indent=2)
        else:
            print("中文字幕辨識結果 image_texts_ch 為空。")
    except FileNotFoundError:
        print("沒有中文字幕圖片檔。")
    except Exception as e:
        print(f"中文字幕辨識發生錯誤：{e}")
