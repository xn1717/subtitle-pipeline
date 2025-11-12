import os
import re
from sentence_transformers import SentenceTransformer, util

def merge_bilingual_srt(ch_srt_name="subtitle_ch.srt",
                        en_srt_name="subtitle_en.srt",
                        output_dir="output",
                        semantic_weight=0.5,
                        time_weight=0.5):
    """
    合併中英 SRT 檔案（放在 output/ 資料夾中），
    產生 merged.srt
    """

    os.makedirs(output_dir, exist_ok=True)

    # ====== 1. 讀取並解析 srt 檔案 ======
    def parse_srt(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        blocks = content.strip().split("\n\n")
        srt_list = []
        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) >= 3:
                index = lines[0].strip()
                timecode = lines[1].strip()
                text = "\n".join(lines[2:]).strip()
                srt_list.append([index, timecode, text])
        return srt_list

    def print_first_n(records, n=10):
        for rec in records[:n]:
            print(rec)

    # ====== 2. 處理兩人講話的格式 ======
    def process_dialogue(text, lang="ch"):
        lines = [line.strip() for line in text.splitlines() if line.strip() != ""]
        processed_lines = []
        for i, line in enumerate(lines):
            if i == 0:
                processed_lines.append(line)
            else:
                if not line.startswith("-"):
                    processed_lines.append("-" + line)
                else:
                    processed_lines.append(line)
        if lang == "ch":
            return "\u3000".join(processed_lines)
        else:
            return " ".join(processed_lines)

    # ====== 3. 時間解析相關 ======
    def time_str_to_seconds(t):
        h, m, s_milli = t.split(":")
        s, milli = s_milli.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(milli) / 1000.0

    def get_time_bounds(timecode):
        start_str, end_str = timecode.split(" --> ")
        start_seconds = time_str_to_seconds(start_str)
        end_seconds = time_str_to_seconds(end_str)
        return start_seconds, end_seconds

    def compute_overlap(start1, end1, start2, end2):
        overlap = max(0, min(end1, end2) - max(start1, start2))
        return overlap

    # ====== 4. 合併邏輯 ======
    def merge_subtitles(ch_srt, en_srt, semantic_weight=0.5, time_weight=0.5):
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

        chinese_records = []
        for rec in ch_srt:
            index, timecode, text = rec
            start, end = get_time_bounds(timecode)
            processed_text = process_dialogue(text, lang="ch")
            ch_embedding = model.encode(processed_text, convert_to_tensor=True)
            chinese_records.append({
                "index": index,
                "timecode": timecode,
                "start": start,
                "end": end,
                "text": processed_text,
                "embedding": ch_embedding
            })

        merged_records = []
        used_ch_indices = set()

        for rec in en_srt:
            index, timecode, text = rec
            start_e, end_e = get_time_bounds(timecode)
            en_text_proc = process_dialogue(text, lang="en")
            en_embedding = model.encode(en_text_proc, convert_to_tensor=True)

            best_score = -1.0
            best_candidate = None

            for c_rec in chinese_records:
                overlap = compute_overlap(start_e, end_e, c_rec["start"], c_rec["end"])
                duration = end_e - start_e
                overlap_ratio = overlap / duration if duration > 0 else 0
                cosine_similarity = util.cos_sim(en_embedding, c_rec["embedding"]).item()
                final_score = time_weight * overlap_ratio + semantic_weight * cosine_similarity
                if final_score > best_score:
                    best_score = final_score
                    best_candidate = c_rec

            if best_candidate is not None and best_candidate["index"] not in used_ch_indices:
                merged_records.append({
                    "index": len(merged_records) + 1,
                    "timecode": timecode,
                    "text": best_candidate["text"]
                })
                used_ch_indices.add(best_candidate["index"])

        return merged_records

    # ====== 5. 儲存合併後的 SRT ======
    def save_srt(merged_records, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in merged_records:
                f.write(str(rec["index"]) + "\n")
                f.write(rec["timecode"] + "\n")
                f.write(rec["text"] + "\n\n")
        print("✅ 合併後的 srt 檔案已儲存為:", output_path)

    # ====== 主流程 ======
    chinese_srt_file = os.path.join(output_dir, ch_srt_name)
    english_srt_file = os.path.join(output_dir, en_srt_name)

    ch_srt_list = parse_srt(chinese_srt_file)
    en_srt_list = parse_srt(english_srt_file)

    print("前 10 筆中文 srt 資料檢查：")
    print_first_n(ch_srt_list, 10)

    print("\n前 10 筆英文 srt 資料檢查：")
    print_first_n(en_srt_list, 10)

    merged_records = merge_subtitles(ch_srt_list, en_srt_list,
                                     semantic_weight=semantic_weight,
                                     time_weight=time_weight)

    output_path = os.path.join(output_dir, "merged.srt")
    save_srt(merged_records, output_path)
    return output_path
