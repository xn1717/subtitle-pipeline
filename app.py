# app.py
from flask import Flask, render_template, request, jsonify, send_from_directory
import subprocess, sys
from pathlib import Path
from config import load_config, save_config
import shutil, os
import signal, psutil

current_process = None
app = Flask(__name__)
ROOT = Path(__file__).parent

def run_step(cmd, timeout=None):
    """執行單一步驟，回傳 (returncode, output)"""
    proc = subprocess.run(
        [sys.executable, *cmd],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout
    )
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, out


@app.get("/")
def index():
    # 不自動帶值到欄位，但仍可由模板使用 cfg 判斷
    return render_template("index.html", cfg=load_config())

@app.post("/run")
def run_pipeline():
    # 0) 先接收前端輸入並寫入 config.json（只覆蓋有填寫者）
    data = request.get_json(force=True) or {}
    upd = {}
    for k in ["file_name_en", "drive_url_en", "file_name_ch", "drive_url_ch", "api_key", "translate"]:
        v = (data.get(k) or "").strip()
        if v:
            upd[k] = v
    if "api_key" in upd:
        upd["API_key"] = upd["api_key"]    # 與舊鍵名同步
    save_config(upd)
    cfg = load_config()                    # 後續步驟用最新設定
    
    ocr_engine = (data.get("ocr") or "paddle").lower()
    
    # 準備輸出資料夾
    output_dir = Path(cfg.get("output_dir") or "output")
    output_dir.mkdir(parents=True, exist_ok=True)

    logs = []

    # 1) download_assets
    code, out = run_step(["download_assets.py"])
    logs.append(("download_assets.py", code, out))
    if code != 0:
        return jsonify({"ok": False, "logs": logs})

    # 2) ocr_paddle
    # code, out = run_step(["ocr_paddle.py"])
    # logs.append(("ocr_paddle.py", code, out))
    # if code != 0:
    #     return jsonify({"ok": False, "logs": logs})
    # 2) OCR（依使用者選擇）
    # 2) OCR：根據前端選擇執行 Paddle 或 Gemini
    ocr_choice = data.get("ocr", "paddle").strip().lower()

    if ocr_choice == "gemini":
        # 執行 ocr_gemini.py
        code, out = run_step(["ocr_gemini.py"])
        logs.append(("ocr_gemini.py", code, out))
    else:
        # 預設執行 ocr_paddle.py
        code, out = run_step(["ocr_paddle.py"])
        logs.append(("ocr_paddle.py", code, out))

    if code != 0:
        return jsonify({"ok": False, "logs": logs})


    # 3) translate
    translate_mode = (cfg.get("translate") or "none").lower()

    if translate_mode == "none":
        logs.append(("trans.py", 0, "Skip translation."))
    else:
        code, out = run_step(["trans.py"])
        logs.append(("trans.py", code, out))
        if code != 0:
            return jsonify({"ok": False, "logs": logs})



    # 4) xml_to_srt
    code, out = run_step(["xml_to_srt.py"])
    logs.append(("xml_to_srt.py", code, out))
    if code != 0:
        return jsonify({"ok": False, "logs": logs})

    # 5) merge_srt（產出固定檔名 merged.srt）
    code, out = run_step(["merge_srt.py"])
    logs.append(("merge_srt.py", code, out))
    if code != 0:
        return jsonify({"ok": False, "logs": logs})

    # 6) 掃描輸出檔（英文 .srt、中文 .srt、merged.srt）
    en_name = zh_name = merge_name = None

    # 固定檢查 merged.srt
    merged = output_dir / "merged.srt"
    if merged.exists():
        merge_name = merged.name

    all_srts = sorted(output_dir.glob("*.srt"))

    def find_by_hint(hints):
        for srt in all_srts:
            low = srt.name.lower()
            for h in hints:
                if h and h.lower() in low:
                    return srt.name
        return None

    # 用檔名線索找英文/中文（先用 file_name_*，再退而求其次）
    en_name = find_by_hint([cfg.get("file_name_en"), "en", "eng"])
    zh_name = find_by_hint([cfg.get("file_name_ch"), "zh", "ch", "chi", "cht", "chs"])

    # 兜底：從其餘 .srt 中補齊
    def first_non(skip):
        skip = set(x for x in skip if x)
        for srt in all_srts:
            if srt.name not in skip:
                return srt.name
        return None

    if not en_name:
        en_name = first_non({merge_name})
    if not zh_name:
        zh_name = first_non({merge_name, en_name})

    files = {
        "en":    f"/files/{en_name}"    if en_name    else None,
        "zh":    f"/files/{zh_name}"    if zh_name    else None,
        "merge": f"/files/{merge_name}" if merge_name else None,
    }

    return jsonify({"ok": True, "logs": logs, "files": files})

def _wipe_dir_contents(root: Path) -> dict:
    """刪除資料夾底下所有檔案與子資料夾，不刪 root 本身。"""
    root.mkdir(parents=True, exist_ok=True)
    removed_files = 0
    removed_dirs = 0
    for entry in root.iterdir():
        try:
            if entry.is_file() or entry.is_symlink():
                entry.unlink(missing_ok=True)
                removed_files += 1
            elif entry.is_dir():
                shutil.rmtree(entry)
                removed_dirs += 1
        except Exception as e:
            # 可視需要記 log
            pass
    return {"files": removed_files, "dirs": removed_dirs}

@app.post("/reset")
def reset_workspace():
    cfg = load_config()
    data_dir = Path("data")
    out_dir  = Path(cfg.get("output_dir") or "output")
    config_file = Path("config.json")

    # 清空 data 與 output
    stat_data = _wipe_dir_contents(data_dir)
    stat_out  = _wipe_dir_contents(out_dir)

    # 刪除 config.json 本身
    if config_file.exists():
        try:
            config_file.unlink()
            config_status = "deleted"
        except Exception as e:
            config_status = f"delete failed: {e}"
    else:
        config_status = "not found"

    return jsonify({
        "ok": True,
        "data": stat_data,
        "output": stat_out,
        "config": config_status
    })



@app.get("/files/<path:filename>")
def download_file(filename):
    cfg = load_config()
    output_dir = Path(cfg.get("output_dir") or "output")
    return send_from_directory(output_dir, filename, as_attachment=True)



@app.post("/shutdown")
def shutdown():
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        # 非 Werkzeug 或被 reloader 擋住時的保險措施
        os._exit(0)
    func()
    return jsonify({"ok": True, "msg": "server shutting down"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
