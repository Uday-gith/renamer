import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
import requests
import io
import zipfile
import time

# Page Configuration
st.set_page_config(page_title="Wiki Bulk Renamer", layout="wide")
st.title("📸 Wiki Bulk Image Renamer")
st.write("Process your images for Wikimedia Commons. AI will caption the content and GPS will detect the location.")

# --- UTILITY FUNCTIONS ---

def get_decimal_from_dms(dms, ref):
    """Converts Degrees Minutes Seconds to Decimal Degrees."""
    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0
    if ref in ['S', 'W']:
        return -(degrees + minutes + seconds)
    return degrees + minutes + seconds

def get_city_name(lat, lon):
    """Reverse geocoding to find city/town names."""
    try:
        geolocator = Nominatim(user_agent="wiki_renamer_v3")
        location = geolocator.reverse(f"{lat}, {lon}", language='en', timeout=10)
        address = location.raw.get('address', {})
        return address.get('city') or address.get('town') or address.get('village') or "Unknown Location"
    except:
        return "Unknown Location"

def query_ai(image_bytes):
    """Calls Hugging Face API with a retry loop to handle model wake-up."""
    API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
    headers = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}
    
    # Try up to 5 times to handle 503/410 "Model Loading" states
    for attempt in range(5):
        try:
            response = requests.post(API_URL, headers=headers, data=image_bytes, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result[0]['generated_text'].capitalize()
            
            elif response.status_code in [503, 410, 429]:
                st.info(f"AI is waking up (Attempt {attempt+1}/5). Waiting 15 seconds...")
                time.sleep(15)
            else:
                st.error(f"API Error: {response.status_code}")
                return None
        except Exception as e:
            time.sleep(2)
    
    st.error("AI server is taking too long to respond. Please try again in a minute.")
    return None

# --- MAIN APPLICATION LOGIC ---

# 1. Multi-file uploader
uploaded_files = st.file_uploader("Upload Images (JPG/JPEG)", type=["jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    # Initialize session state for renames if not present
    if "renames" not in st.session_state:
        st.session_state.renames = {}

    st.header("Step 1: Review & Generate Names")
    
    for i, file in enumerate(uploaded_files):
        img = Image.open(file)
        exif = img._getexif()
        detected_city = None
        
        # Extract GPS Data from EXIF
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) == "GPSInfo":
                    try:
                        lat = get_decimal_from_dms(value[2], value[1])
                        lon = get_decimal_from_dms(value[4], value[3])
                        detected_city = get_city_name(lat, lon)
                    except:
                        detected_city = None

        # UI Row for each image
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 2, 2])
            
            # Column 1: Preview
            col1.image(img, use_container_width=True)
            
            # Column 2: Location Handling
            # Pre-fill with detected city, or allow manual entry if missing
            loc_val = col2.text_input(
                f"Location for {file.name}:", 
                value=detected_city if detected_city else "", 
                placeholder="Enter city (e.g., Khajuraho)", 
                key=f"loc_{i}"
            )
            
            # Column 3: AI Action
            if col3.button(f"Generate Wiki Name", key=f"btn_{i}"):
                with st.spinner("AI is analyzing image..."):
                    caption = query_ai(file.getvalue())
                    if caption:
                        # Format: [Caption] in [Location].jpg
                        final_name = f"{caption} in {loc_val}.jpg" if loc_val else f"{caption}.jpg"
                        st.session_state.renames[file.name] = final_name
                        st.rerun()

            # Display generated name for confirmation/editing
            if file.name in st.session_state.renames:
                new_name = st.text_input("Final Filename (Edit if needed):", value=st.session_state.renames[file.name], key=f"edit_{i}")
                st.session_state.renames[file.name] = new_name
                st.success(f"Ready: {new_name}")

    # --- BULK DOWNLOAD SECTION ---
    
    if len(st.session_state.renames) > 0:
        st.divider()
        st.header("Step 2: Download Batch")
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for file in uploaded_files:
                if file.name in st.session_state.renames:
                    # Save the original image bytes with the new Wikimedia filename
                    zf.writestr(st.session_state.renames[file.name], file.getvalue())
        
        st.download_button(
            label="📦 Download All Renamed Images (.zip)",
            data=zip_buffer.getvalue(),
            file_name="wikimedia_commons_batch.zip",
            mime="application/zip",
            use_container_width=True
        )
