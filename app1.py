import streamlit as st
import fitz  # PyMuPDF
from paddleocr import PaddleOCR
import pandas as pd
import gc
import os
from io import BytesIO
from PIL import Image

st.title("Cloud OCR: Bill to Excel Converter")
st.write("Extracting and aligning text horizontally.")

if 'camera_photos' not in st.session_state:
    st.session_state.camera_photos = []

def process_images_to_excel(image_paths_or_bytes, is_bytes=False):
    status = st.empty()
    progress_bar = st.progress(0)
    
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
        
        excel_data.append([f"--- BILL PAGE {i+1} ---"])
        
        if result[0] is not None:
            # 1. Gather all text boxes with their X and Y coordinates
            boxes_and_texts = []
            for line_data in result[0]:
                box = line_data[0]
                text = line_data[1][0].strip()
                # Find the vertical center (Y-axis) of the text
                y_center = (box[0][1] + box[2][1]) / 2 
                # Save: (Y-coord, X-coord, Text)
                boxes_and_texts.append((y_center, box[0][0], text))

            # 2. Sort all text from top to bottom of the page
            boxes_and_texts.sort(key=lambda x: x[0])

            # 3. Group text that sits on the same horizontal line
            current_row = []
            current_y = None
            Y_TOLERANCE = 15 # If text is within 15 pixels vertically, it's the same row

            for item in boxes_and_texts:
                y, x, text = item
                if current_y is None:
                    current_y = y
                    current_row.append((x, text))
                elif abs(y - current_y) <= Y_TOLERANCE:
                    current_row.append((x, text))
                else:
                    # Sort the row from left to right (X-axis) before saving
                    current_row.sort(key=lambda x: x[0])
                    excel_data.append([t[1] for t in current_row])
                    
                    # Start a new row
                    current_y = y
                    current_row = [(x, text)]

            # Save the very last row
            if current_row:
                current_row.sort(key=lambda x: x[0])
                excel_data.append([t[1] for t in current_row])
        
        excel_data.append([""]) 
            
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
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
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
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
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
