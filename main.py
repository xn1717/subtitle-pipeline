from modules import load_en_images
from modules import load_ch_images
from modules import ocr_ocr
from modules import xml_srt
from paddleocr import PaddleOCR


if __name__ == "__main__":

    # # 載入英文圖片檔
    file_name_en = "輕量版__英文測試" # (to do)
    xml_file_name_en = "subtitle_en.xml"
    # drive_url_en = "https://drive.google.com/file/d/1PndgivkmqBPyBmTgsKY6gNWDRrC1vYPR/view?usp=drive_link"
    # load_en_images.run(file_name_en=file_name_en, url=drive_url_en)
    
    # 載入中文圖片檔
    file_name_ch = "輕量版__中文測試" # (to do)
    xml_file_name_ch = "subtitle_ch.xml"
    # drive_url_ch = "https://drive.google.com/file/d/1PndgivkmqBPyBmTgsKY6gNWDRrC1vYPR/view?usp=drive_link"
    # load_ch_images.run(file_name_ch=file_name_ch, url=drive_url_ch)
    
    #辨識圖片英文文字
    image_texts_en = ocr_ocr.run(file_name_en)
    print(image_texts_en)
    
    #辨識圖片中文文字
    image_texts_ch = ocr_ocr.run(file_name_ch)
    print(image_texts_ch)

    # 輸出英文srt檔
    xml_srt.run(xml_file_name_en, image_texts_en, make_backup=True)

    # merge_srt
    from modules.merge_srt import merge_bilingual_srt
    merge_bilingual_srt(
        ch_srt_name="subtitle_ch.srt",
        en_srt_name="subtitle_en.srt",
        output_dir="output"
    )