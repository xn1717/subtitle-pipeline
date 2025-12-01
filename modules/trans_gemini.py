import os
import json
import re
from typing import Dict

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions


def _load_config(project_root: str) -> Dict:
    """
    從專案根目錄讀取 config.json
    """
    config_path = os.path.join(project_root, "config.json")
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"找不到 config.json：{config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if not isinstance(cfg, dict):
        raise ValueError("config.json 應為 JSON 物件 (dict) 格式")

    return cfg


def _get_api_key_from_config(cfg: Dict) -> str:
    """
    從 config.json 取得 API key：
    優先讀取 'API_key'，否則讀取 'api_key'
    """
    api_key = cfg.get("API_key") or cfg.get("api_key")
    if not api_key:
        raise ValueError("config.json 中找不到 'API_key' 或 'api_key'")
    return api_key


def _load_subtitle_dict_from_json(data_dir: str) -> Dict[str, str]:
    """
    從 data 資料夾中找到第一個 json 檔作為字幕字典
    （注意：只掃描 data/，不會讀到根目錄的 config.json）
    """
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"找不到 data 資料夾：{data_dir}")

    json_files = [
        f for f in os.listdir(data_dir)
        if f.lower().endswith(".json")
    ]

    if not json_files:
        raise FileNotFoundError(f"{data_dir} 中找不到任何 json 檔")

    # 若有多個就使用第一個
    if len(json_files) > 1:
        print(f"警告：{data_dir} 中有多個 json，將使用第一個：{json_files[0]}")

    json_path = os.path.join(data_dir, json_files[0])
    print(f"使用字幕 JSON 檔案：{json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("字幕 JSON 應為 dict 格式 {key: value}")

    return {str(k): ("" if v is None else str(v)) for k, v in data.items()}


def _parse_gemini_output(text: str, subtitle_dict: Dict[str, str]) -> Dict[str, str]:
    """
    解析 Gemini 回傳內容成 {key: translated_value}
    """
    parsed: Dict[str, str] = {}

    # {key: value} 或 {key：value}（含全形冒號）
    pattern = re.compile(r"\{([^:]+?)[:：]\s*(.*?)\s*\}", re.DOTALL)

    for m in pattern.finditer(text):
        key = m.group(1).strip().strip(' "“”\'')
        val = m.group(2).strip().strip(' "“”\'')
        if key in subtitle_dict:
            parsed[key] = val
        else:
            print(f"警告：在原始字幕中找不到 Key '{key}'")

    if not parsed:
        print("警告：正規表示式未成功解析任何條目")

    return parsed


def _detect_language(text: str) -> str:
    """
    偵測是否含有中文：
    - 有中文 → 回傳 'ch'
    - 無中文 → 回傳 'en'
    """
    if re.search(r"[\u4e00-\u9fff]", text):
        return "ch"
    return "en"


def _gemini_trans() -> Dict[str, str]:
    """
    主要流程：
    1. 從 config.json 讀取 API key
    2. 從 data/ 掃描字幕 JSON
    3. 呼叫 Gemini 翻譯（中→英、英→中）
    4. 將結果輸出到 data/img_to_text_{語言}.json
       - 若原始字幕為中文 → 語言代碼 'en'
       - 若原始字幕為英文 → 語言代碼 'ch'
    5. 回傳翻譯結果 dict
    """
    # 設定路徑
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, "data")

    # 讀取 config.json 並取得 API key
    cfg = _load_config(project_root)
    api_key = _get_api_key_from_config(cfg)

    # 設定 Gemini
    genai.configure(api_key=api_key)

    # 載入字幕
    subtitle_dict = _load_subtitle_dict_from_json(data_dir)

    # 偵測原文語言（用第一筆即可）
    first_text = next(iter(subtitle_dict.values()), "")
    src_lang = _detect_language(first_text)
    # 原文是中文 → 翻成英文 → 檔名用 en
    # 原文是英文 → 翻成中文 → 檔名用 ch
    output_lang = "en" if src_lang == "ch" else "ch"

    # 準備模型
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={"temperature": 0.1},
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    )

    # 建立 prompt
    prompt = (
        "請你扮演專業翻譯員。我會提供一個 Python 字典格式的字幕列表，"
        "Key 是檔名，Value 是字幕文字。請翻譯 Value：繁體中文翻譯成英文，"
        "英文翻譯成繁體中文，並嚴格保留原本的 Key，不可遺漏或新增。\n"
        "請用以下格式輸出：{key_1: 翻譯後的 value_1}, {key_2: 翻譯後的 value_2} ...\n\n"
        "以下是需要翻譯的內容：\n"
    )

    parts = [f"{{{k}：{v}}}" for k, v in subtitle_dict.items()]
    prompt += ", ".join(parts)

    print("正在向 Gemini 發送翻譯請求...")

    try:
        resp = model.generate_content(prompt)
        raw_output = (resp.text or "").strip()

        print("\n--- Gemini 原始輸出 ---")
        print(raw_output)

        result_dict = _parse_gemini_output(raw_output, subtitle_dict)

        # 若解析不到任何 key，fallback：整段塞進 'ALL'
        if not result_dict:
            print("解析失敗，啟用 fallback：全部內容存入 'ALL'")
            result_dict = {"ALL": raw_output}

    except google_exceptions.GoogleAPIError as e:
        print(f"Google API 錯誤：{e}")
        result_dict = {k: f"翻譯失敗：{e}" for k in subtitle_dict}
    except Exception as e:
        print(f"翻譯過程發生錯誤：{e}")
        result_dict = {k: f"翻譯失敗：{e}" for k in subtitle_dict}

    # 輸出 JSON 檔
    output_filename = f"img_to_text_{output_lang}.json"
    output_path = os.path.join(data_dir, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    print(f"翻譯完成，已輸出：{output_path}")

    return result_dict
