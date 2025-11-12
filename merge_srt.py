from modules.merge_srt import merge_bilingual_srt

if __name__ == "__main__":
    merge_bilingual_srt(
        ch_srt_name="subtitle_ch.srt",
        en_srt_name="subtitle_en.srt",
        output_dir="output"
    )