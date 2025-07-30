from flask import Flask, render_template, request
import os
from werkzeug.utils import secure_filename

from docx import Document
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import easyocr
import cv2
import numpy as np

app = Flask(__name__)

pytesseract.pytesseract.tesseract_cmd = r'Add you path'
poppler_path = r"#add your path"
easyocr_reader = easyocr.Reader(['en', 'hi', 'mr'])  # For fallback if needed

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_with_opencv(image_path):
    """Preprocess image using OpenCV for better OCR results."""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    pil_img = Image.fromarray(thresh)
    return pil_img

def extract_text(filepath, extension):
    extension = extension.lower()

    if extension in ['.jpg', '.jpeg', '.png']:
        try:
            pil_img = preprocess_with_opencv(filepath)
            result = pytesseract.image_to_string(pil_img, lang='hin+mar')
            return result
        except Exception as e:
            return f"Failed to extract text from image. Error: {str(e)}"

    elif extension == '.pdf':
        try:
            images = convert_from_path(filepath, poppler_path=poppler_path)
            all_text = []
            for idx, image in enumerate(images):
                # Convert PDF page image to OpenCV format and preprocess
                temp_image_path = f"temp_page_{idx}.png"
                image.save(temp_image_path)
                pil_img = preprocess_with_opencv(temp_image_path)
                text = pytesseract.image_to_string(pil_img, lang='eng+hin+mar')
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
            extracted_text = extract_text(filepath, extension)
            
            # Break lines at 100 characters for better readability
            formatted_text = '\n'.join([extracted_text[i:i+100] for i in range(0, len(extracted_text), 100)])
            combined_text += f"\n\n=== Text from {filename} ===\n{formatted_text}"

    if not combined_text.strip():
        combined_text = "No text detected from any file."

    return f"<h3>Files uploaded!</h3><pre>{combined_text[:30000]}</pre>"

if __name__ == '__main__':
    app.run(debug=True)
