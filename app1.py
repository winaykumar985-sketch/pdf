import os
# --- THE SHIELD: Fix the broken server tools instantly ---
os.system("pip uninstall -y opencv-python opencv-contrib-python")
os.system("pip install opencv-python-headless")

import streamlit as st
import fitz  # PyMuPDF
from paddleocr import PaddleOCR
import pandas as pd
import re
import os
import gc
from io import BytesIO
from PIL import Image

# ... rest of your UI code stays exactly the same ...

st.title("Cloud OCR: Bill to Excel Converter")
st.write("Extract structured data from scanned bills instantly.")

if 'camera_photos' not in st.session_state:
    st.session_state.camera_photos = []

def process_images_to_excel(image_paths_or_bytes, is_bytes=False):
    status = st.empty()
    progress_bar = st.progress(0)
    
    # Initialize PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
    excel_data = []
    total_images = len(image_paths_or_bytes)
    
    for i, item in enumerate(image_paths_or_bytes):
        status.info(f"Processing image {i + 1} of {total_images}...")
        progress_bar.progress((i + 1) / total_images)
        
        if is_bytes:
            img = Image.open(item)
            temp_path = f"temp_cam_{i}.jpg"
            img.save(temp_path)
            target_img = temp_path
        else:
            target_img = item

        result = ocr.ocr(target_img, cls=True)
        
        current_shop = "Unknown Shop"
        current_gst = "Not Found"
        current_items = []
        line_counter = 0
        
        if result[0] is not None:
            for line_data in result[0]:
                line = line_data[1][0].strip()
                line_counter += 1
                
                if line_counter == 2:
                    current_shop = line
                if "GST" in line.upper():
                    current_gst = line
                    
                if re.match(r'^\d+', line):
                    parts = line.rsplit(maxsplit=3)
                    if len(parts) == 4:
                        sn_desc = parts[0].split(maxsplit=1)
                        if len(sn_desc) == 2:
                            current_items.append([sn_desc[0], sn_desc[1], parts[1], parts[2], parts[3]])
        
        if current_items:
            excel_data.append(["Shop Name:", current_shop, "", "", ""])
            excel_data.append(["GST Details:", current_gst, "", "", ""])
            excel_data.append(["SN", "DESCRIPTION", "Qty", "RATE", "AMOUNT"])
            excel_data.extend(current_items)
            excel_data.append(["", "", "", "", ""]) 
            
        if is_bytes and os.path.exists(target_img):
            os.remove(target_img)
        gc.collect()
        
    status.success("🎉 Cloud Processing Complete! Your file is ready.")
    df = pd.DataFrame(excel_data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Clean_Data')
    return output.getvalue()

st.divider()
option = st.radio("Choose Input Method:", ["1. Single PDF (All Pages)", "2. Multiple Separate PDFs", "3. Camera (Take up to 50 photos)"])

if option == "1. Single PDF (All Pages)":
    uploaded_file = st.file_uploader("Upload ONE PDF", type=["pdf"])
    if uploaded_file and st.button("Process PDF"):
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        pdf_document = fitz.open("temp.pdf")
        image_paths = []
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_path = f"page_{page_num}.jpg"
            pix.save(img_path)
            image_paths.append(img_path)
            
        pdf_document.close()
        os.remove("temp.pdf")
        
        excel_bytes = process_images_to_excel(image_paths, is_bytes=False)
        st.download_button(label="📥 Download Excel", data=excel_bytes, file_name="Structured_Bills.xlsx")
        
        for path in image_paths:
            if os.path.exists(path):
                os.remove(path)

elif option == "2. Multiple Separate PDFs":
    uploaded_files = st.file_uploader("Upload Multiple PDFs", type=["pdf"], accept_multiple_files=True)
    if uploaded_files and st.button("Process All PDFs"):
        image_paths = []
        file_counter = 0
        
        for uploaded_file in uploaded_files:
            temp_pdf_name = f"temp_{file_counter}.pdf"
            with open(temp_pdf_name, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            pdf_document = fitz.open(temp_pdf_name)
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                img_path = f"file_{file_counter}_page_{page_num}.jpg"
                pix.save(img_path)
                image_paths.append(img_path)
                
            pdf_document.close()
            os.remove(temp_pdf_name)
            file_counter += 1
            
        excel_bytes = process_images_to_excel(image_paths, is_bytes=False)
        st.download_button(label="📥 Download Excel", data=excel_bytes, file_name="Structured_Bills.xlsx")
        
        for path in image_paths:
            if os.path.exists(path):
                os.remove(path)

elif option == "3. Camera (Take up to 50 photos)":
    st.write("Take pictures of your bills one by one. They will save below.")
    photo = st.camera_input("Take a photo")
    
    if photo is not None:
        if len(st.session_state.camera_photos) < 50:
            if photo not in st.session_state.camera_photos:
                st.session_state.camera_photos.append(photo)
        else:
            st.warning("You have reached the maximum of 50 photos.")

    st.info(f"Photos queued for processing: {len(st.session_state.camera_photos)} / 50")
    
    if len(st.session_state.camera_photos) > 0:
        if st.button("Clear Photos & Start Over"):
            st.session_state.camera_photos = []
            st.rerun()
            
        st.divider()
        if st.button("Submit & Process Photos"):
            excel_bytes = process_images_to_excel(st.session_state.camera_photos, is_bytes=True)
            st.download_button(label="📥 Download Excel", data=excel_bytes, file_name="Camera_Bills.xlsx")
            st.session_state.camera_photos = []
