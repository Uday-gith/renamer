import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
import requests

# Set up the UI
st.title("Wiki Photo Renamer")
st.write("Upload an image to generate a Wikimedia-style filename.")

uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

def get_geotagging(exif):
    geotagging = {}
    for (idx, tag) in TAGS.items():
        if tag == 'GPSInfo':
            for (t, value) in GPSTAGS.items():
                if t in exif[idx]:
                    geotagging[value] = exif[idx][t]
    return geotagging

if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="Uploaded Image", use_column_width=True)
    
    # 1. Extract Location (Simplified logic)
    try:
        exif = img._getexif()
        geo_data = get_geotagging(exif)
        # Convert coordinates and use geopy to get address
        # For this demo, let's assume 'Khajuraho' if GPS exists
        location_name = "Khajuraho" 
    except:
        location_name = "Unknown Location"

    # 2. AI Captioning (Using Hugging Face Free API)
    # Replace 'YOUR_TOKEN' with a free token from huggingface.co
    API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
    headers = {"Authorization": "Bearer YOUR_TOKEN"}
    
    if st.button("Generate Name"):
        response = requests.post(API_URL, headers=headers, data=uploaded_file.getvalue())
        caption = response.json()[0]['generated_text']
        
        final_name = f"{caption.capitalize()} in {location_name}.jpg"
        st.success(f"Suggested Filename: {final_name}")