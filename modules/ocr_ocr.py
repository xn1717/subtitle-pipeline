import os
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)

def run(file_name):
    """
    🔤 辨識英文圖片文字，回傳 {檔名: 文字} 字典
    參數：
        file_name (str): 圖片資料夾名稱，例如 '輕量版__英文測試'
        ocr: PaddleOCR 或其他 OCR 模型物件
    回傳：
        dict: {檔名: 辨識出的文字}
    """
    # 指定要掃描的資料夾
    folder_path = "data/" + file_name

    # 建立空字典
    image_texts = {}

    # 遍歷所有檔案
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)

            # 辨識
            try:
                text = " ".join(ocr.predict(file_path)[0]['rec_texts'])
            except Exception as e:
                print(f"⚠️ 無法辨識：{file_path} ({e})")
                text = ""
                pass

            # 以檔名作為 key，辨識文字作為 value
            image_texts[file] = text

    print(f"✅ 已完成辨識，共 {len(image_texts)} 筆")
    return image_texts
