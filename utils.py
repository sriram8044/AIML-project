
import os, cv2, numpy as np, statistics
from PIL import Image
import pytesseract
from pytesseract import TesseractError
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import cm

# Point to Windows Tesseract; change path if needed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

def _gray_world_white_balance(img):
    result = img.astype(np.float32)
    avg_b, avg_g, avg_r = result.reshape(-1,3).mean(axis=0)
    avg_gray = (avg_b + avg_g + avg_r) / 3.0
    result[:,:,0] *= (avg_gray/avg_b)
    result[:,:,1] *= (avg_gray/avg_g)
    result[:,:,2] *= (avg_gray/avg_r)
    result = np.clip(result, 0, 255).astype(np.uint8)
    return result

def enhance_image_color(input_path, enhanced_color_path):
    img = cv2.imread(input_path)
    if img is None:
        raise RuntimeError("Failed to read image")
    wb = _gray_world_white_balance(img)
    lab = cv2.cvtColor(wb, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    L2 = clahe.apply(L)
    lab2 = cv2.merge([L2, A, B])
    color_boost = cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)
    den = cv2.bilateralFilter(color_boost, 7, 50, 50)
    blur = cv2.GaussianBlur(den, (0,0), 1.2)
    sharp = cv2.addWeighted(den, 1.5, blur, -0.5, 0)
    cv2.imwrite(enhanced_color_path, sharp)
    return enhanced_color_path

def make_ocr_ready(input_path, ocr_path):
    tmp_color = ocr_path.replace("ocr.png", "tmp_color.png")
    enhance_image_color(input_path, tmp_color)
    img = cv2.imread(tmp_color)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 7, 60, 60)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    if bw.mean() < 127:
        bw = 255 - bw
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel, iterations=1)
    cv2.imwrite(ocr_path, bw)
    try: os.remove(tmp_color)
    except Exception: pass
    return ocr_path

def _ocr_with_conf(pil_img, lang, config):
    data = pytesseract.image_to_data(pil_img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    text = " ".join([w for w in data["text"] if w.strip()])
    confs = [int(c) for c in data["conf"] if c not in ("-1", "", None)]
    mean_conf = statistics.mean(confs) if confs else 0.0
    return text, mean_conf

def extract_text(image_path, lang="eng"):
    pil_img = Image.open(image_path)
    candidates = [
        "--oem 1 --psm 6 -c preserve_interword_spaces=1",
        "--oem 1 --psm 3 -c preserve_interword_spaces=1",
        "--oem 1 --psm 4 -c preserve_interword_spaces=1",
        "--oem 1 --psm 11 -c preserve_interword_spaces=1",
        "--oem 1 --psm 7 -c preserve_interword_spaces=1",
    ]
    best_text, best_conf = "", -1.0
    for cfg in candidates:
        try:
            t, c = _ocr_with_conf(pil_img, lang, cfg)
            if c > best_conf:
                best_conf, best_text = c, t
        except TesseractError:
            continue
    if best_conf < 1 and lang != "eng":
        for cfg in candidates:
            try:
                t, c = _ocr_with_conf(pil_img, "eng", cfg)
                if c > best_conf:
                    best_conf, best_text = c, t
            except TesseractError:
                continue
    return best_text

def export_pdf(original_path, enhanced_color_path, text, pdf_path):
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, height - 2*cm, "Historical Manuscript Restoration + OCR (Color)")
    try:
        img_reader = ImageReader(enhanced_color_path)
        img_w, img_h = img_reader.getSize()
        scale = min((width-4*cm)/img_w, (height/2-3*cm)/img_h)
        c.drawImage(img_reader, 2*cm, height - 3*cm - img_h*scale,
                    width=img_w*scale, height=img_h*scale, preserveAspectRatio=True)
    except Exception:
        pass
    c.showPage()
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2*cm, height - 2*cm, "Extracted Text")
    c.setFont("Helvetica", 11)
    from reportlab.platypus import Frame, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    frame = Frame(2*cm, 2*cm, width-4*cm, height-4*cm, showBoundary=0)
    style = getSampleStyleSheet()["Normal"]
    story = [Paragraph(text.replace("\n","<br/>"), style)]
    frame.addFromList(story, c)
    c.save()
    return pdf_path

def process_pipeline(input_path, workdir, lang="eng"):
    os.makedirs(workdir, exist_ok=True)
    enhanced_color = os.path.join(workdir, "enhanced_color.png")
    ocr_path = os.path.join(workdir, "ocr.png")
    pdf_path = os.path.join(workdir, "result.pdf")
    txt_path = os.path.join(workdir, "result.txt")
    enhance_image_color(input_path, enhanced_color)
    make_ocr_ready(input_path, ocr_path)
    text = extract_text(ocr_path, lang=lang)
    export_pdf(input_path, enhanced_color, text, pdf_path)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"enhanced_color": enhanced_color, "ocr_path": ocr_path, "pdf_path": pdf_path, "text_path": txt_path, "text": text}
