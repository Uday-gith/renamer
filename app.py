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
        address = location.raw.get('address', {})
        return address.get('city') or address.get('town') or address.get('village') or "Unknown Location"
    except: return "Unknown Location"

def query_ai(image_bytes):
    API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
    headers = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}
    
    try:
        response = requests.post(API_URL, headers=headers, data=image_bytes, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result[0]['generated_text'].capitalize()
        elif response.status_code == 503:
            # This handles the "Model Busy/Loading" state properly
            st.warning("The AI is waking up. Please wait 15-20 seconds and click Generate again.")
            return None
        else:
            st.error(f"Hugging Face returned an error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None

# --- APP FLOW ---
uploaded_files = st.file_uploader("Upload Images", type=["jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    if "renames" not in st.session_state:
        st.session_state.renames = {}

    for i, file in enumerate(uploaded_files):
        img = Image.open(file)
        exif = img._getexif()
        city = None
        
        # GPS Extraction logic
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) == "GPSInfo":
                    try:
                        city = get_city_name(get_decimal_from_dms(value[2], value[1]), get_decimal_from_dms(value[4], value[3]))
                    except: pass

        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 2, 2])
            col1.image(img, use_container_width=True)
            
            # Location input (Pre-filled if GPS found)
            final_city = col2.text_input(f"Location ({file.name})", value=city if city else "", placeholder="e.g. Khajuraho", key=f"loc_{i}")
            
            # Renaming Button
            if col3.button(f"Generate Wiki Name", key=f"btn_{i}"):
                with st.spinner("AI is analyzing..."):
                    caption = query_ai(file.getvalue())
                    if caption:
                        st.session_state.renames[file.name] = f"{caption} in {final_city}.jpg"
                        st.rerun()

            if file.name in st.session_state.renames:
                st.session_state.renames[file.name] = col3.text_input("Edit generated name:", value=st.session_state.renames[file.name], key=f"edit_{i}")
                col3.success(f"Final Name: {st.session_state.renames[file.name]}")

    # --- BULK DOWNLOAD ---
    if len(st.session_state.renames) > 0:
        st.divider()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for file in uploaded_files:
                if file.name in st.session_state.renames:
                    zf.writestr(st.session_state.renames[file.name], file.getvalue())
        
        st.download_button("📦 Download All Renamed Images (.zip)", zip_buffer.getvalue(), "wiki_batch_renamed.zip", "application/zip", use_container_width=True)
