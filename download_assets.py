from config import load_config
from modules import load_en_images, load_ch_images

if __name__ == "__main__":
    cfg = load_config()
    load_en_images.run(cfg["file_name_en"], cfg["drive_url_en"])
    load_ch_images.run(cfg["file_name_ch"], cfg["drive_url_ch"])