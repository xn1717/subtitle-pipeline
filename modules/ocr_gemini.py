# modules/ocr_gemini.py
# 功能：
# 1. 若 data/{file_name}.pdf 不存在 → 將 data/{file_name}/*.png 合併成 PDF
# 2. 將 PDF 切割成多個 chunk（預設每 100 頁）
# 3. 呼叫 Gemini 逐塊 OCR
# 4. 回傳 dict: {"subtitle0001": "文字", ...}
# ⚠️ 不自動寫入 JSON，由外層主程式決定

from __future__ import annotations
import os, re, json, math, time, glob
from pathlib import Path
from typing import Dict, List, Optional
from pypdf import PdfReader, PdfWriter
from PIL import Image
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import config


# --------- 圖片合併成 PDF ---------
def _images_to_pdf(file_name: str) -> Path:
    pdf_path = Path("data") / f"{file_name}.pdf"
    if pdf_path.exists():
        return pdf_path

    folder = Path("data") / file_name
    image_files = sorted(glob.glob(str(folder / "*.png")))
    if not image_files:
        raise FileNotFoundError(f"找不到任何圖片：{folder}/*.png")

    os.makedirs(pdf_path.parent, exist_ok=True)
    imgs = [Image.open(p).convert("RGB") for p in image_files]
    try:
        first, rest = imgs[0], imgs[1:]
        first.save(pdf_path, save_all=True, append_images=rest)
    finally:
        for im in imgs:
            im.close()

    print(f"✅ 已合併 {len(image_files)} 張圖片為 PDF：{pdf_path}")
    return pdf_path


# --------- PDF 拆塊 ---------
def _split_pdf_into_chunks(pdf_path: Path, chunk_size: int = 100) -> List[Path]:
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("PDF 沒有頁面")

    out: List[Path] = []
    base = pdf_path.with_suffix("")
    for i in range(0, total_pages, chunk_size):
        writer = PdfWriter()
        for j in range(i, min(i + chunk_size, total_pages)):
            writer.add_page(reader.pages[j])
        chunk_file = Path(f"{base}_chunk_{len(out)+1}.pdf")
        with open(chunk_file, "wb") as f:
            writer.write(f)
        out.append(chunk_file)
    return out


# --------- 單一 Gemini OCR ---------
def _gemini_ocr_one(pdf_path: Path, api_key: str, timeout_sec: int = 600) -> str:
    genai.configure(api_key=api_key)
    remote = genai.upload_file(path=str(pdf_path))
    try:
        model = genai.GenerativeModel(
            model_name="gemini-flash-latest",
            generation_config={"temperature": 0.1},
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        )

        prompt = (
            "這是一份由圖片組成的 PDF。請逐頁擷取所有繁體中文與英文文字。\n"
            "每頁開頭務必以『第X頁』獨立一行表示頁碼。\n"
            "輸出範例：\n第1頁\n<內容>\n第2頁\n<內容>\n"
        )

        resp = model.generate_content([prompt, remote], request_options={"timeout": timeout_sec})
        return (resp.text or "").strip()
    finally:
        try:
            genai.delete_file(remote.name)
        except Exception:
            pass


# --------- 分頁文字解析 ---------
_PAGE_SPLIT = re.compile(r"(?:^|\n)第\s*([0-9０-９]+)\s*頁(?:[：:\-\s]*)(?!\S)", re.IGNORECASE)

def _parse_pages_to_dict(full_text: str) -> Dict[int, str]:
    if not full_text.strip():
        return {}
    parts = _PAGE_SPLIT.split(full_text)
    out: Dict[int, str] = {}
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            page_no_raw = parts[i]
            page_text = parts[i + 1] if i + 1 < len(parts) else ""
            trans = str.maketrans("０１２３４５６７８９", "0123456789")
            page_no = int(page_no_raw.translate(trans))
            out[page_no] = page_text.strip()
        return out

    # 若模型沒分頁 → 用空行切段
    paras = [p for p in re.split(r"\n{2,}", full_text) if p.strip()]
    for idx, txt in enumerate(paras, 1):
        out[idx] = txt.strip()
    return out


# --------- 主函式（給主程式呼叫） ---------
def run(
    file_name: str,
    *,
    chunk_size: int = 100,
    max_retries: int = 3,
    sleep_on_rate_limit: int = 40,
    timeout_sec: int = 600,
    api_key: Optional[str] = None,
) -> Dict[str, str]:
    """
    執行流程：
      1) 若 data/{file_name}.pdf 不存在，從 data/{file_name}/*.png 建立
      2) 切塊 OCR
      3) 回傳字典 {"subtitle0001": "內容", ...}
    """
    pdf_path = _images_to_pdf(file_name)

    if not api_key:
        cfg = config.load_config()
        api_key = cfg.get("api_key") or cfg.get("API_key") or ""
    if not api_key:
        raise ValueError("缺少 API Key")

    chunk_files = _split_pdf_into_chunks(pdf_path, chunk_size=chunk_size)

    image_texts_by_page: Dict[int, str] = {}
    try:
        for chunk in chunk_files:
            text = None
            for attempt in range(1, max_retries + 1):
                try:
                    text = _gemini_ocr_one(chunk, api_key=api_key, timeout_sec=timeout_sec)
                    break
                except (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable):
                    if attempt == max_retries:
                        raise
                    time.sleep(sleep_on_rate_limit)
                except Exception:
                    if attempt == max_retries:
                        raise
                    time.sleep(2)

            if not text:
                continue

            local = _parse_pages_to_dict(text)
            base = len(image_texts_by_page)
            for k in sorted(local.keys()):
                image_texts_by_page[base + k] = local[k].strip()
    finally:
        for f in chunk_files:
            try: os.remove(f)
            except Exception: pass

    # 轉成 subtitle_0001 形式
    # 把原本的 key 生成處改成有底線形式
    image_texts = {f"subtitle_{i:04d}.png": image_texts_by_page[p]
        for i, p in enumerate(sorted(image_texts_by_page.keys()), 1)}


    print(f"📘 OCR 完成：{file_name}（共 {len(image_texts)} 頁）")
    return image_texts


# if __name__ == "__main__":
#     # 測試：會回傳字典但不存檔
#     d = run("再見柏林中文")
#     print(d)
