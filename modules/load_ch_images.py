import os
import zipfile
import gdown

def run(file_name_ch: str, url: str, work_dir: str = "data/"):
    """
    下載英文字幕圖片 zip 檔並解壓到本地資料夾。

    Args:
        file_name_en (str): 資料夾命名（例："輕量版__中文測試"）
        url (str): Google Drive 檔案連結
        work_dir (str): 解壓後的工作路徑，預設 data/en_imgs
    """
    os.makedirs(work_dir, exist_ok=True)
    output = os.path.join(work_dir, "ch_images.zip")

    print(f"下載中：{url}")
    gdown.download(url=url, output=output, fuzzy=True)

    print("正在解壓縮...")
    with zipfile.ZipFile(output, 'r') as zip_ref:
        zip_ref.extractall(work_dir)

    os.remove(output)  # 刪除 zip

    # 移除 __MACOSX 與多餘資料夾
    macosx = os.path.join(work_dir, "__MACOSX")
    if os.path.exists(macosx):
        import shutil
        shutil.rmtree(macosx)

    # 找出最新資料夾並重新命名
    latest = max([d for d in os.listdir(work_dir) if os.path.isdir(os.path.join(work_dir, d))],
                 key=lambda d: os.path.getmtime(os.path.join(work_dir, d)))
    os.rename(os.path.join(work_dir, latest), os.path.join(work_dir, file_name_ch))

    # 如果有 subtitle.xml，統一命名
    src_xml = os.path.join(work_dir, file_name_ch, "subtitle.xml")
    dst_xml = os.path.join(work_dir, "subtitle_ch.xml")
    if os.path.exists(src_xml):
        os.rename(src_xml, dst_xml)

    print("字幕圖片載入與解壓完成！")
