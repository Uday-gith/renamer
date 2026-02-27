import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
import requests
import io
import zipfile

st.set_page_config(page_title="Wiki Bulk Renamer", layout="wide")
st.title("📸 Wiki Bulk Image Renamer")
st.info("Upload multiple images. If GPS is missing, you can enter the location manually.")

# Helper: Convert GPS to Decimal
def get_decimal_from_dms(dms, ref):
    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0
    if ref in ['S', 'W']:
        return -(degrees + minutes + seconds)
    return degrees + minutes + seconds

def get_city_name(lat, lon):
    try:
        geolocator = Nominatim(user_agent="wiki_renamer_v2")
        location = geolocator.reverse(f"{lat}, {lon}", language='en', timeout=10)
        address = location.raw.get('address', {})
        return address.get('city') or address.get('town') or address.get('village') or "Unknown Location"
    except:
        return "Unknown Location"

# --- UPLOAD SECTION ---
uploaded_files = st.file_uploader("Upload Images", type=["jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    processed_images = [] # Stores (bytes, filename)
    
    for i, file in enumerate(uploaded_files):
        img = Image.open(file)
        exif = img._getexif()
        detected_city = None
        
        # 1. Try to get GPS
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) == "GPSInfo":
                    try:
                        lat = get_decimal_from_dms(value[2], value[1])
                        lon = get_decimal_from_dms(value[4], value[3])
                        detected_city = get_city_name(lat, lon)
                    except:
                        detected_city = None

        # 2. UI Row for each image
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 2, 2])
            col1.image(img, use_container_width=True)
            
            # Location Logic
            if not detected_city or detected_city == "Unknown Location":
                location_input = col2.text_input(f"Location for {file.name}:", placeholder="e.g. Khajuraho", key=f"loc_{i}")
            else:
                col2.success(f"📍 Detected: {detected_city}")
                location_input = detected_city

            # Rename Logic
            if col3.button(f"Generate Name", key=f"btn_{i}"):
                with st.spinner("AI analyzing image..."):
                    API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
                    headers = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}
                    response = requests.post(API_URL, headers=headers, data=file.getvalue())
                    
                    if response.status_code == 200:
                        caption = response.json()[0]['generated_text'].capitalize()
                        final_name = f"{caption} in {location_input}.jpg"
                        st.session_state[f"name_{i}"] = final_name
                    else:
                        st.error("AI Model Busy. Try again in a moment.")

            if f"name_{i}" in st.session_state:
                new_name = st.session_state[f"name_{i}"]
                col3.code(new_name)
                processed_images.append((file.getvalue(), new_name))

    # --- BULK DOWNLOAD ---
    if processed_images and len(processed_images) == len(uploaded_files):
        st.divider()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for img_bytes, name in processed_images:
                zf.writestr(name, img_bytes)
        
        st.download_button(
            label="📦 Download All Renamed Images (.zip)",
            data=zip_buffer.getvalue(),
            file_name="wiki_bulk_renamed.zip",
            mime="application/zip",
            use_container_width=True
        )
