import os
import zipfile
import re
import io
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image
import fitz  # PyMuPDF

# --- DỮ LIỆU ĐA NGÔN NGỮ (ENGLISH IS DEFAULT) ---
LANGUAGES = {
    "English": {
        "title": "Nook CBZ Splitter & Converter",
        "btn_select": "📁 Select Comic Files (.cbz, .pdf, .mobi)",
        "opt_split_spread": "✂️ Auto-split dual pages (Spread Splitter)",
        "opt_grayscale": "🎨 Convert to E-ink Grayscale (Smaller size)",
        "reading": "🔄 Reading file: {}...",
        "no_images": "❌ No images found in this file!",
        "found_pages": "📖 Found {} pages. Processing & splitting...",
        "created": "✅ Created: {}",
        "done": "🎉 ALL COMPLETED!",
        "lang_label": "Language:"
    },
    "Tiếng Việt": {
        "title": "Nook CBZ Splitter & Converter",
        "btn_select": "📁 Chọn File Truyện (.cbz, .pdf, .mobi)",
        "opt_split_spread": "✂️ Tự động cắt đôi trang đôi (Spread Splitter)",
        "opt_grayscale": "🎨 Ép về Đen Trắng E-ink (Giảm dung lượng)",
        "reading": "🔄 Đang đọc file: {}...",
        "no_images": "❌ Không tìm thấy ảnh trong file này!",
        "found_pages": "📖 Tìm thấy {} trang. Đang xử lý & chia part...",
        "created": "✅ Đã tạo: {}",
        "done": "🎉 HOÀN THÀNH TOÀN BỘ!",
        "lang_label": "Ngôn ngữ:"
    },
    "Español": {
        "title": "Nook CBZ Dividir y Convertir",
        "btn_select": "📁 Seleccionar cómics (.cbz, .pdf, .mobi)",
        "opt_split_spread": "✂️ Dividir páginas dobles (Spread Splitter)",
        "opt_grayscale": "🎨 Escala de grises E-ink (Menor tamaño)",
        "reading": "🔄 Leyendo archivo: {}...",
        "no_images": "❌ ¡No se encontraron imágenes!",
        "found_pages": "📖 Se encontraron {} páginas. Procesando...",
        "created": "✅ Creado: {}",
        "done": "🎉 ¡TODO COMPLETADO!",
        "lang_label": "Idioma:"
    },
    "中文": {
        "title": "Nook CBZ 漫画分割与转换器",
        "btn_select": "📁 选择漫画文件 (.cbz, .pdf, .mobi)",
        "opt_split_spread": "✂️ 自动分割跨页/双页 (Spread Splitter)",
        "opt_grayscale": "🎨 转换为墨水屏灰度 (减小体积)",
        "reading": "🔄 正在读取文件: {}...",
        "no_images": "❌ 未找到图像文件！",
        "found_pages": "📖 找到 {} 页。正在处理并分割...",
        "created": "✅ 已生成: {}",
        "done": "🎉 全部完成！",
        "lang_label": "语言:"
    }
}

def chuyen_ten_khong_dau(text):
    """Chuyển tên file thành không dấu và loại bỏ ký tự đặc biệt."""
    text = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', text)
    text = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', text)
    text = re.sub(r'[ìíịỉĩ]', 'i', text)
    text = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', text)
    text = re.sub(r'[ùúụủũưừứựửữ]', 'u', text)
    text = re.sub(r'[ỳýỵỷỹ]', 'y', text)
    text = re.sub(r'[đ]', 'd', text)
    text = re.sub(r'[^a-zA-Z0-9_]', '_', text)
    return text

def lay_danh_sach_anh(file_path):
    """Trích xuất tất cả các tệp ảnh từ file CBZ, ZIP, MOBI hoặc PDF."""
    ext = os.path.splitext(file_path)[1].lower()
    images_bytes = []
    if ext in ['.cbz', '.mobi', '.zip']:
        try:
            with zipfile.ZipFile(file_path, 'r') as src_zip:
                all_files = sorted(src_zip.namelist())
                img_paths = [f for f in all_files if not f.endswith('/') and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))]
                for p in img_paths:
                    images_bytes.append(src_zip.read(p))
        except Exception:
            pass
    elif ext == '.pdf':
        try:
            doc = fitz.open(file_path)
            for page in doc:
                image_list = page.get_images()
                if image_list:
                    for img_info in image_list:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        images_bytes.append(base_image["image"])
                else:
                    pix = page.get_pixmap(dpi=150)
                    images_bytes.append(pix.tobytes("jpeg"))
        except Exception:
            pass
    return images_bytes

def xu_ly_file(file_path, log_func, lang_dict, split_spread=False, to_grayscale=False, max_size_mb=50):
    """Xử lý cắt ảnh, chuyển hệ màu và chia nhỏ thành các part CBZ."""
    max_bytes = max_size_mb * 1024 * 1024
    
    # Lấy đúng tên file gốc (loại bỏ đường dẫn ổ C:\...)
    file_name_only = os.path.basename(file_path)
    raw_base_name = os.path.splitext(file_name_only)[0]
    clean_base_name = chuyen_ten_khong_dau(raw_base_name)
    
    log_func(lang_dict["reading"].format(file_name_only))
    raw_images = lay_danh_sach_anh(file_path)
    if not raw_images:
        log_func(lang_dict["no_images"])
        return

    log_func(lang_dict["found_pages"].format(len(raw_images)))

    part_num = 1
    current_size = 0
    current_files_data = []

    for img_raw in raw_images:
        try:
            img = Image.open(io.BytesIO(img_raw))
            
            # Cắt đôi trang đôi (Spread Splitter) nếu tích chọn
            processed_imgs = []
            if split_spread and img.width > img.height:
                half_width = img.width // 2
                left_box = (0, 0, half_width, img.height)
                right_box = (half_width, 0, img.width, img.height)
                processed_imgs.append(img.crop(right_box)) # Trang phải trước (Manga)
                processed_imgs.append(img.crop(left_box))
            else:
                processed_imgs.append(img)

            for sub_img in processed_imgs:
                if to_grayscale:
                    sub_img = sub_img.convert('L') # Chuyển sang 8-bit Grayscale
                elif sub_img.mode != 'RGB':
                    sub_img = sub_img.convert('RGB')

                out_buffer = io.BytesIO()
                sub_img.save(out_buffer, format='JPEG', quality=80)
                jpg_bytes = out_buffer.getvalue()

                file_size = len(jpg_bytes)

                if current_files_data and (current_size + file_size > max_bytes):
                    output_name = f"{clean_base_name}_part{part_num:02d}.cbz"
                    _ghi_cbz(current_files_data, output_name)
                    log_func(lang_dict["created"].format(output_name))
                    part_num += 1
                    current_files_data = []
                    current_size = 0

                current_files_data.append(jpg_bytes)
                current_size += file_size

        except Exception:
            pass

    if current_files_data:
        output_name = f"{clean_base_name}_part{part_num:02d}.cbz"
        _ghi_cbz(current_files_data, output_filename=output_name)
        log_func(lang_dict["created"].format(output_name))

def _ghi_cbz(images_data_list, output_filename):
    """Ghi tập hợp ảnh thành file CBZ."""
    with zipfile.ZipFile(output_filename, 'w', compression=zipfile.ZIP_STORED) as dest_zip:
        for index, img_bytes in enumerate(images_data_list):
            dest_zip.writestr(f"page_{index+1:04d}.jpg", img_bytes)

# --- GIAO DIỆN GUI ĐA LUỒNG ---
class AppCBZ:
    def __init__(self, root):
        self.root = root
        self.current_lang = "English" # Tiếng Anh mặc định
        self.lang = LANGUAGES[self.current_lang]

        self.root.title("Nook CBZ Splitter & Converter")
        self.root.geometry("560x480")

        # Khung chọn ngôn ngữ
        lang_frame = tk.Frame(root)
        lang_frame.pack(anchor="ne", padx=10, pady=5)
        
        self.lbl_lang = tk.Label(lang_frame, text=self.lang["lang_label"])
        self.lbl_lang.pack(side="left", padx=5)

        self.combo_lang = ttk.Combobox(lang_frame, values=list(LANGUAGES.keys()), state="readonly", width=12)
        self.combo_lang.set(self.current_lang)
        self.combo_lang.pack(side="left")
        self.combo_lang.bind("<<ComboboxSelected>>", self.thay_doi_ngon_ngu)

        # Tiêu đề
        self.lbl_title = tk.Label(root, text="Nook CBZ Splitter (50MB/Part)", font=("Arial", 14, "bold"))
        self.lbl_title.pack(pady=5)

        # Khung tùy chọn (Mặc định không tích chọn)
        opt_frame = tk.LabelFrame(root, text=" Options / Tùy chọn ", padx=10, pady=5)
        opt_frame.pack(pady=5, fill="x", padx=15)

        self.var_spread = tk.BooleanVar(value=False)
        self.chk_spread = tk.Checkbutton(opt_frame, text=self.lang["opt_split_spread"], variable=self.var_spread)
        self.chk_spread.pack(anchor="w")

        self.var_grayscale = tk.BooleanVar(value=False)
        self.chk_grayscale = tk.Checkbutton(opt_frame, text=self.lang["opt_grayscale"], variable=self.var_grayscale)
        self.chk_grayscale.pack(anchor="w")

        # Nút chọn file
        self.btn_select = tk.Button(root, text=self.lang["btn_select"], font=("Arial", 11, "bold"), bg="#4CAF50", fg="white", command=self.bat_dau_xu_ly)
        self.btn_select.pack(pady=10)

        # Khung hiển thị log
        self.log_text = tk.Text(root, height=12, width=65)
        self.log_text.pack(pady=5)

    def thay_doi_ngon_ngu(self, event=None):
        self.current_lang = self.combo_lang.get()
        self.lang = LANGUAGES[self.current_lang]
        
        self.lbl_lang.config(text=self.lang["lang_label"])
        self.btn_select.config(text=self.lang["btn_select"])
        self.chk_spread.config(text=self.lang["opt_split_spread"])
        self.chk_grayscale.config(text=self.lang["opt_grayscale"])

    def log(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def bat_dau_xu_ly(self):
        files = filedialog.askopenfilenames(
            title="Select comic files",
            filetypes=[("Comic Files", "*.cbz *.pdf *.mobi")]
        )
        if files:
            # Khóa nút bấm để tránh người dùng click nhiều lần
            self.btn_select.config(state="disabled")
            # Khởi chạy luồng xử lý ngầm (Threading)
            threading.Thread(target=self._tien_trinh_ngam, args=(files,), daemon=True).start()

    def _tien_trinh_ngam(self, files):
        for f in files:
            xu_ly_file(
                f, 
                self.log, 
                self.lang, 
                split_spread=self.var_spread.get(),
                to_grayscale=self.var_grayscale.get()
            )
        self.log(self.lang["done"])
        # Mở lại nút bấm khi xử lý xong
        self.btn_select.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = AppCBZ(root)
    root.mainloop()
