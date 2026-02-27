import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
import requests
import io
import zipfile
import time

st.set_page_config(page_title="Wiki Bulk Renamer", layout="wide")
st.title("📸 Wiki Bulk Image Renamer")

# --- UTILITY FUNCTIONS ---
def get_decimal_from_dms(dms, ref):
    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0
    return -(degrees + minutes + seconds) if ref in ['S', 'W'] else degrees + minutes + seconds

def get_city_name(lat, lon):
    try:
        geolocator = Nominatim(user_agent="wiki_renamer_v3")
        location = geolocator.reverse(f"{lat}, {lon}", language='en', timeout=10)
        return location.raw.get('address', {}).get('city') or location.raw.get('address', {}).get('town') or "Unknown Location"
    except: return "Unknown Location"

def query_ai(image_bytes):
    API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
    headers = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}
    
    # Try 3 times to account for model loading time
    for _ in range(3):
        response = requests.post(API_URL, headers=headers, data=image_bytes)
        result = response.json()
        if response.status_code == 200:
            return result[0]['generated_text'].capitalize()
        elif "estimated_time" in result:
            time.sleep(result['estimated_time']) 
        else:
            time.sleep(3)
    return None

# --- MAIN APP FLOW ---
uploaded_files = st.file_uploader("Upload Images", type=["jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    if "final_names" not in st.session_state:
        st.session_state.final_names = {}

    for i, file in enumerate(uploaded_files):
        img = Image.open(file)
        exif = img._getexif()
        city = None
        
        # Auto-detect location if GPS exists
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) == "GPSInfo":
                    try:
                        city = get_city_name(get_decimal_from_dms(value[2], value[1]), get_decimal_from_dms(value[4], value[3]))
                    except: pass

        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 2, 2])
            col1.image(img, use_container_width=True)
            
            # Location Field (Manual Override)
            loc_val = col2.text_input(f"Location for {file.name}", value=city if city else "", key=f"loc_{i}")
            
            # AI Renaming Button
            if col3.button(f"Analyze & Rename", key=f"btn_{i}"):
                with st.spinner("AI is thinking..."):
                    caption = query_ai(file.getvalue())
                    if caption:
                        st.session_state.final_names[file.name] = f"{caption} in {loc_val}.jpg"
                    else:
                        st.error("AI Server is taking too long. Please try again in 10 seconds.")

            if file.name in st.session_state.final_names:
                col3.success(f"New Name: {st.session_state.final_names[file.name]}")

    # --- BULK DOWNLOAD ---
    if len(st.session_state.final_names) > 0:
        st.divider()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for file in uploaded_files:
                if file.name in st.session_state.final_names:
                    zf.writestr(st.session_state.final_names[file.name], file.getvalue())
        
        st.download_button("📦 Download All Renamed Images (.zip)", zip_buffer.getvalue(), "wiki_batch_renamed.zip", "application/zip", use_container_width=True)
