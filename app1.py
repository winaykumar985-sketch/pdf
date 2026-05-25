import streamlit as st
import fitz  # PyMuPDF
from paddleocr import PaddleOCR
import pandas as pd
import re
import os
import gc

st.title("Cloud PDF-to-Excel Structured Converter")
st.write("Upload your scanned PDF. The cloud will process it—your laptop RAM stays completely free!")

uploaded_file = st.file_uploader("Upload Scanned PDF", type=["pdf"])

if uploaded_file is not None:
    if st.button("Start Cloud Processing"):
        # Create placeholders for live status updates
        status = st.empty()
        progress_bar = st.progress(0)
        
        status.info("Step 1: Splitting PDF into high-res images in the cloud...")
        
        # Save uploaded PDF to cloud disk temporarily
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        pdf_document = fitz.open("temp.pdf")
        total_pages = len(pdf_document)
        
        # Initialize PaddleOCR on cloud server (Forces CPU mode for stability)
        ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
        
        excel_data = []
        
        # Process each page
        for page_num in range(total_pages):
            status.info(f"Step 2: Processing page {page_num + 1} of {total_pages}...")
            progress_bar.progress((page_num + 1) / total_pages)
            
            # Extract page as image
            page = pdf_document[page_num]
            matrix = fitz.Matrix(2.0, 2.0) 
            pix = page.get_pixmap(matrix=matrix)
            img_path = f"page_{page_num}.jpg"
            pix.save(img_path)
            
            # Run OCR on the image
            result = ocr.ocr(img_path, cls=True)
            
            # Process text lines immediately to extract structured table
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
            
            # Append this page's structured data to global sheet list
            if current_items:
                excel_data.append(["Shop Name:", current_shop, "", "", ""])
                excel_data.append(["GST Details:", current_gst, "", "", ""])
                excel_data.append(["SN", "DESCRIPTION", "Qty", "RATE", "AMOUNT"])
                excel_data.extend(current_items)
                excel_data.append(["", "", "", "", ""]) # One row space
                
            # Delete temporary image to keep cloud memory clean
            os.remove(img_path)
            gc.collect()
            
        pdf_document.close()
        os.remove("temp.pdf")
        
        # Convert everything to Excel
        status.success("🎉 Cloud Processing Complete! Your file is ready.")
        df = pd.DataFrame(excel_data)
        
        # Save to memory buffer for downloader
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, header=False, sheet_name='Clean_Data')
        processed_data = output.getvalue()
        
        st.download_button(
            label="📥 Download Structured Excel File",
            data=processed_data,
            file_name="Structured_Bills.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
