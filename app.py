from flask import Flask, render_template, request
import os
from werkzeug.utils import secure_filename
from googletrans import Translator
from docx import Document
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import cv2
import numpy as np

app = Flask(__name__)

# Configuration
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
poppler_path = r"Release-24.08.0-0\poppler-24.08.0\Library\bin"

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'jpg', 'jpeg', 'png'}
translator = Translator()

# Utility Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_with_opencv(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)

def extract_text(filepath, extension):
    extension = extension.lower()

    if extension in ['.jpg', '.jpeg', '.png']:
        try:
            pil_img = preprocess_with_opencv(filepath)
            return pytesseract.image_to_string(pil_img, lang='hin+mar+eng')
        except Exception as e:
            return f"Failed to extract text from image. Error: {str(e)}"

    elif extension == '.pdf':
        try:
            images = convert_from_path(filepath, poppler_path=poppler_path)
            all_text = []
            for idx, image in enumerate(images):
                temp_image_path = f"temp_page_{idx}.png"
                image.save(temp_image_path)
                pil_img = preprocess_with_opencv(temp_image_path)
                text = pytesseract.image_to_string(pil_img, lang='hin+mar+eng')
                all_text.append(text)
                os.remove(temp_image_path)
            return '\n'.join(all_text)
        except Exception as e:
            return f"Failed to extract text from PDF. Error: {str(e)}"

    elif extension == '.docx':
        try:
            doc = Document(filepath)
            return '\n'.join([para.text for para in doc.paragraphs])
        except Exception as e:
            return f"Failed to read DOCX file. Error: {str(e)}"

    return "Unsupported file type."

def translate_text_line_by_line(text):
    translated_lines = []
    for line in text.split('\n'):
        if line.strip():
            try:
                detected = translator.detect(line)
                if detected.lang in ['hi', 'mr']:
                    translated = translator.translate(line, src=detected.lang, dest='en').text
                    translated_lines.append(f"{line}\n→ {translated}")
                else:
                    translated_lines.append(line)
            except Exception as e:
                translated_lines.append(f"{line}\n[Translation failed: {str(e)}]")
        else:
            translated_lines.append("")
    return '\n'.join(translated_lines)

def wrap_text(text, width=100):
    return '\n'.join([text[i:i+width] for i in range(0, len(text), width)])

# Flask Routes
@app.route('/')
def index():
    return render_template('template.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'legalfile' not in request.files:
        return "No file uploaded", 400

    files = request.files.getlist('legalfile')
    if not files or all(file.filename == '' for file in files):
        return "No file selected", 400

    os.makedirs('uploads', exist_ok=True)
    combined_text = ""

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join('uploads', filename)
            file.save(filepath)

            extension = os.path.splitext(filename)[1].lower()
            raw_text = extract_text(filepath, extension)
            translated_text = translate_text_line_by_line(raw_text)
            formatted_text = wrap_text(translated_text, 100)

            combined_text += f"\n\n=== Text from {filename} ===\n{formatted_text}"

    if not combined_text.strip():
        combined_text = "No text detected from any file."

    return f"<h3>Files uploaded!</h3><pre>{combined_text[:30000]}</pre>"

if __name__ == '__main__':
    app.run(debug=True)
