import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
import requests
import io
import zipfile
import time

# Page Configuration for a professional look
st.set_page_config(page_title="Wiki Bulk Renamer", layout="wide")
st.title("📸 Wiki Bulk Image Renamer")
st.info("Upload multiple images. AI will caption them, and GPS will suggest locations.")

# --- UTILITIES ---

def get_decimal_from_dms(dms, ref):
    """Converts Degrees Minutes Seconds to Decimal Degrees."""
    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0
    if ref in ['S', 'W']:
        return -(degrees + minutes + seconds)
    return degrees + minutes + seconds

def get_city_name(lat, lon):
    """Gets the city name from coordinates using OpenStreetMap."""
    try:
        geolocator = Nominatim(user_agent="wiki_renamer_uday")
        location = geolocator.reverse(f"{lat}, {lon}", language='en', timeout=10)
        address = location.raw.get('address', {})
        return address.get('city') or address.get('town') or address.get('village') or "Unknown Location"
    except:
        return "Unknown Location"

def query_ai(image_bytes):
    """Calls Hugging Face API with a robust retry mechanism."""
    API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
    
    # Use the token you saved in Streamlit Secrets
    try:
        headers = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}
    except:
        st.error("Secret 'HF_TOKEN' not found. Please add it to your Streamlit dashboard.")
        return None
    
    # Retry up to 5 times to handle the model waking up (Status 503 or 410)
    for attempt in range(5):
        try:
            response = requests.post(API_URL, headers=headers, data=image_bytes, timeout=35)
            
            if response.status_code == 200:
                result = response.json()
                return result[0]['generated_text'].capitalize()
            
            elif response.status_code in [503, 410, 429]:
                st.warning(f"AI is waking up (Attempt {attempt+1}/5). Please wait 15 seconds...")
                time.sleep(15)
            else:
                st.error(f"Hugging Face Error: {response.status_code}")
                return None
        except requests.exceptions.Timeout:
            st.warning("Request timed out. Trying again...")
            time.sleep(2)
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return None
            
    return None

# --- MAIN APP LOGIC ---

# Upload section
uploaded_files = st.file_uploader("Upload Images", type=["jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    # Use session state to keep data during re-renders
    if "renames" not in st.session_state:
        st.session_state.renames = {}

    for i, file in enumerate(uploaded_files):
        img = Image.open(file)
        exif = img._getexif()
        city = None
        
        # Extract GPS data
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) == "GPSInfo":
                    try:
                        lat = get_decimal_from_dms(value[2], value[1])
                        lon = get_decimal_from_dms(value[4], value[3])
                        city = get_city_name(lat, lon)
                    except:
                        city = None

        # UI Row for each image
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 2, 2])
            
            col1.image(img, use_container_width=True)
            
            # Location input (Pre-filled if GPS exists)
            final_city = col2.text_input(
                f"Location for {file.name}:", 
                value=city if city else "", 
                placeholder="e.g. Khajuraho", 
                key=f"loc_{i}"
            )
            
            # AI Name Generation
            if col3.button(f"Generate Wiki Name", key=f"btn_{i}"):
                with st.spinner("AI is analyzing image..."):
                    caption = query_ai(file.getvalue())
                    if caption:
                        # Wikimedia format: [Caption] in [Location].jpg
                        new_name = f"{caption} in {final_city}.jpg" if final_city else f"{caption}.jpg"
                        st.session_state.renames[file.name] = new_name
                        st.rerun()

            # Result and Editing
            if file.name in st.session_state.renames:
                edit_name = col3.text_input("Edit final name:", value=st.session_state.renames[file.name], key=f"edit_{i}")
                st.session_state.renames[file.name] = edit_name
                st.success(f"Ready: {edit_name}")

    # --- BULK DOWNLOAD ---
    if len(st.session_state.renames) > 0:
        st.divider()
        st.header("Step 2: Download Batch")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for file in uploaded_files:
                if file.name in st.session_state.renames:
                    # Rename the file within the ZIP
                    zf.writestr(st.session_state.renames[file.name], file.getvalue())
        
        st.download_button(
            label="📦 Download All Renamed Images (.zip)",
            data=zip_buffer.getvalue(),
            file_name="wiki_batch_renamed.zip",
            mime="application/zip",
            use_container_width=True
        )
