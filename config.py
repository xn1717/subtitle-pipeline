# config.py
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

# 預設設定
DEFAULT_CFG = {
    "file_name_en": "",
    "drive_url_en": "",
    "file_name_ch": "",
    "drive_url_ch": "",
    "api_key": "",
    "API_key": "",          # 與 api_key 同步，兼容舊程式
    "translate": "none",
    "output_dir": "output",
    # 若其他腳本需要，可保留這兩鍵
    "xml_file_name_en": "subtitle_en.xml",
    "xml_file_name_ch": "subtitle_ch.xml",
}

def load_config() -> dict:
    """讀取設定，檔案覆蓋預設，缺鍵用預設補上；api_key 與 API_key 互相同步。"""
    cfg = DEFAULT_CFG.copy()
    if CONFIG_PATH.exists():
        try:
            on_disk = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(on_disk, dict):
                cfg.update(on_disk)
        except json.JSONDecodeError:
            pass
    # 同步 api_key / API_key
    if cfg.get("api_key") and not cfg.get("API_key"):
        cfg["API_key"] = cfg["api_key"]
    if cfg.get("API_key") and not cfg.get("api_key"):
        cfg["api_key"] = cfg["API_key"]
    return cfg

def _apply_globals(cfg: dict):
    """同步舊程式使用的全域變數。"""
    global API_key, file_name_en, drive_url_en, file_name_ch, drive_url_ch
    global xml_file_name_en, xml_file_name_ch, output_dir, translate
    API_key = cfg.get("API_key", "")
    file_name_en = cfg.get("file_name_en", "")
    drive_url_en = cfg.get("drive_url_en", "")
    file_name_ch = cfg.get("file_name_ch", "")
    drive_url_ch = cfg.get("drive_url_ch", "")
    xml_file_name_en = cfg.get("xml_file_name_en", "subtitle_en.xml")
    xml_file_name_ch = cfg.get("xml_file_name_ch", "subtitle_ch.xml")
    output_dir = cfg.get("output_dir", "output")
    translate = cfg.get("translate", "none")

def save_config(partial: dict):
    """僅用非空字串覆蓋現有設定；寫回後同步全域。"""
    merged = load_config()
    for k, v in (partial or {}).items():
        if v is None:
            continue
        s = str(v).strip()
        if s != "":
            merged[k] = s
    # 再次同步 api_key / API_key
    if merged.get("api_key"):
        merged["API_key"] = merged["api_key"]
    elif merged.get("API_key"):
        merged["api_key"] = merged["API_key"]
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    _apply_globals(merged)

# 模組載入時先套用一次
_apply_globals(load_config())

# 供舊碼引用的 OCR 暫存
image_texts_en = {}
image_texts_ch = {}

if __name__ == "__main__":
    print(json.dumps(load_config(), ensure_ascii=False, indent=2))
