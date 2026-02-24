import os
import re
import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import base64
import json
from closet import closet
from streamlit_option_menu import option_menu
from dotenv import load_dotenv
from openai import OpenAI
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Load environment variables (for local .env fallback)
load_dotenv()

# Helper: read from st.secrets (Streamlit Cloud) or os.getenv (local .env)
def get_secret(key, default=None):
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, default)

# Cloudinary configuration
cloudinary.config(
    cloud_name=get_secret("CLOUDINARY_CLOUD_NAME"),
    api_key=get_secret("CLOUDINARY_API_KEY"),
    api_secret=get_secret("CLOUDINARY_API_SECRET"),
    secure=True
)

# OpenRouter configuration
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=get_secret("OPENROUTER_API_KEY"),
    default_headers={
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "Virtual Wardrobe",
    }
)
OPENROUTER_MODEL = get_secret("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

# Metadata file path
METADATA_FILE = 'metadata.csv'

st.set_page_config(
    page_title="Virtual Wardrobe",
    page_icon="👔",
    layout="wide",
)

# ──────────────────────────────────────────────
# Custom CSS for professional UI
# ──────────────────────────────────────────────

st.markdown("""
<style>
    /* ── Global ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* ── Closet item card ── */
    .closet-card {
        position: relative;
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        padding: 12px;
        margin-bottom: 16px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        overflow: hidden;
    }
    .closet-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
    }
    .closet-card img {
        border-radius: 12px;
        width: 100%;
        object-fit: cover;
    }
    .card-label {
        margin-top: 8px;
        font-size: 13px;
        font-weight: 500;
        color: #e0e0e0;
        text-align: center;
    }
    .card-badge {
        display: inline-block;
        font-size: 11px;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 20px;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: #fff;
        margin: 2px;
    }

    /* ── Delete icon button ── */
    .delete-btn-wrap {
        position: absolute;
        top: 8px;
        right: 8px;
        z-index: 10;
    }

    /* ── Section headers ── */
    .section-header {
        font-size: 28px;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    .section-sub {
        font-size: 14px;
        color: #aaa;
        margin-bottom: 24px;
    }

    /* ── Outfit card ── */
    .outfit-header {
        font-size: 18px;
        font-weight: 600;
        color: #e0e0e0;
        padding: 10px 0 6px;
        border-bottom: 2px solid rgba(102, 126, 234, 0.4);
        margin-bottom: 12px;
    }
    .outfit-wrap {
        background: rgba(255,255,255,0.05);
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.08);
    }

    /* ── Upload area ── */
    .upload-section {
        background: rgba(255,255,255,0.05);
        border-radius: 16px;
        padding: 24px;
        border: 1px dashed rgba(102, 126, 234, 0.5);
        margin-bottom: 20px;
    }

    /* ── Form styling ── */
    .stSelectbox > div > div,
    .stTextInput > div > div > input {
        border-radius: 10px !important;
    }

    /* ── Empty state ── */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #888;
    }
    .empty-state .icon {
        font-size: 64px;
        margin-bottom: 16px;
    }
    .empty-state .msg {
        font-size: 18px;
        font-weight: 500;
    }

    /* ── Success toast ── */
    .success-toast {
        background: linear-gradient(135deg, #00c853, #00e676);
        color: #fff;
        padding: 14px 20px;
        border-radius: 12px;
        font-weight: 600;
        text-align: center;
        margin: 12px 0;
    }

    /* ── Filter sidebar ── */
    .sidebar .sidebar-content {
        background: rgba(0,0,0,0.3);
    }

    /* ── Hide default Streamlit button styling for delete icons ── */
    .small-del button {
        background: rgba(255, 80, 80, 0.15) !important;
        border: 1px solid rgba(255, 80, 80, 0.3) !important;
        border-radius: 50% !important;
        padding: 4px 8px !important;
        font-size: 14px !important;
        line-height: 1 !important;
        color: #ff5252 !important;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .small-del button:hover {
        background: rgba(255, 80, 80, 0.35) !important;
        transform: scale(1.15);
    }
</style>
""", unsafe_allow_html=True)


def add_bg_from_local(image_file):
    with open(image_file, "rb") as image:
        encoded_image = base64.b64encode(image.read()).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{encoded_image}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# Add local background image
if os.path.exists("bg.jpg"):
    add_bg_from_local("bg.jpg")


# ──────────────────────────────────────────────
# Metadata helpers (CSV stores Cloudinary URLs)
# ──────────────────────────────────────────────

REQUIRED_COLUMNS = ['Image URL', 'Public ID', 'Category', 'Color', 'Season']

def save_metadata(image_url, public_id, category, color, season):
    """Append one item to the metadata CSV."""
    if os.path.exists(METADATA_FILE):
        df = pd.read_csv(METADATA_FILE)
        if not all(col in df.columns for col in REQUIRED_COLUMNS):
            df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    else:
        df = pd.DataFrame(columns=REQUIRED_COLUMNS)

    new_entry = pd.DataFrame({
        'Image URL': [image_url],
        'Public ID': [public_id],
        'Category': [category],
        'Color': [color],
        'Season': [season],
    })

    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(METADATA_FILE, index=False)


def load_metadata():
    """Load the metadata CSV into a DataFrame."""
    if os.path.exists(METADATA_FILE):
        df = pd.read_csv(METADATA_FILE)
        if not all(col in df.columns for col in REQUIRED_COLUMNS):
            df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        return df
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def delete_item(index):
    """Delete an item from both Cloudinary and the metadata CSV."""
    df = load_metadata()
    if not df.empty and index in df.index:
        public_id = df.at[index, 'Public ID']
        try:
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            st.warning(f"Could not delete from Cloudinary: {e}")
        df = df.drop(index).reset_index(drop=True)
        df.to_csv(METADATA_FILE, index=False)


# ──────────────────────────────────────────────
# Upload helper
# ──────────────────────────────────────────────

def upload_to_cloudinary(file_bytes, filename):
    """Upload an image to Cloudinary and return (url, public_id)."""
    try:
        result = cloudinary.uploader.upload(
            file_bytes,
            folder="wardrobe",
            public_id=os.path.splitext(filename)[0],
            overwrite=True,
            resource_type="image",
        )
        return result['secure_url'], result['public_id']
    except Exception as e:
        st.error(f"Cloudinary upload failed: {e}")
        return None, None


# ──────────────────────────────────────────────
# AI outfit suggestions via OpenRouter
# ──────────────────────────────────────────────

def get_outfit_suggestions(user_prompt, df):
    """Send wardrobe data + user prompt to OpenRouter and return parsed outfits."""
    clothes_list = "\n".join(
        f"{row['Image URL']},{row['Category']},{row['Color']},{row['Season']}"
        for _, row in df.iterrows()
    )

    system_message = (
        "You are an AI fashion stylist. The user has a wardrobe of clothes. "
        "Choose outfit sets based on their request. "
        "Return ONLY a JSON array of arrays, where each inner array contains the Image URLs of one outfit. "
        "Example: [[\"url1\", \"url2\"], [\"url3\", \"url4\"]]. "
        "Do NOT include any other text, markdown, or explanation — just the raw JSON."
    )

    user_message = (
        f"Here is my wardrobe:\n"
        f"Image URL, Category, Color, Season\n"
        f"{clothes_list}\n\n"
        f"Request: {user_prompt}"
    )

    try:
        response = openrouter_client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=4096,
        )

        raw = response.choices[0].message.content.strip()

        # Handle markdown code blocks
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        # Extract the outermost JSON array [[...]] even if there's extra text
        match = re.search(r'\[\s*\[.*?\]\s*\]', raw, re.DOTALL)
        if match:
            raw = match.group(0)

        outfits = json.loads(raw)
        return outfits

    except json.JSONDecodeError as e:
        st.error(f"Error parsing AI response: {e}")
        st.code(raw)
        return None
    except Exception as e:
        st.error(f"Error getting outfit suggestions: {e}")
        return None


# ──────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────

# Title
closet("Radha's Wardrobe")

# Top bar option menu
selected_option = option_menu(
    None,
    ["Your Closet", "Add New Items", "Suggest Outfits"],
    icons=["grid-fill", "cloud-arrow-up-fill", "stars"],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {
            "padding": "8px",
            "background": "rgba(255,255,255,0.05)",
            "border-radius": "14px",
            "border": "1px solid rgba(255,255,255,0.1)",
            "backdrop-filter": "blur(10px)",
        },
        "icon": {"color": "#a78bfa", "font-size": "18px"},
        "nav-link": {
            "font-size": "15px",
            "font-weight": "500",
            "color": "#ccc",
            "border-radius": "10px",
            "padding": "10px 20px",
            "transition": "all 0.3s ease",
        },
        "nav-link-selected": {
            "background": "linear-gradient(135deg, #667eea, #764ba2)",
            "color": "#fff",
            "font-weight": "600",
        },
    },
)


# ══════════════════════════════════════════════
# YOUR CLOSET
# ══════════════════════════════════════════════
if selected_option == "Your Closet":
    st.sidebar.markdown("### 🔍 Filter Items")
    df = load_metadata()

    unique_colors = df['Color'].dropna().unique()
    unique_categories = df['Category'].dropna().unique()
    unique_seasons = df['Season'].dropna().unique()

    selected_colors = st.sidebar.multiselect('🎨 Color:', unique_colors)
    selected_categories = st.sidebar.multiselect('👕 Category:', unique_categories)
    selected_seasons = st.sidebar.multiselect('🌤️ Season:', unique_seasons)

    if selected_colors:
        df = df[df['Color'].isin(selected_colors)]
    if selected_categories:
        df = df[df['Category'].isin(selected_categories)]
    if selected_seasons:
        df = df[df['Season'].isin(selected_seasons)]

    # Header
    st.markdown('<div class="section-header">👗 Your Closet</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">{len(df)} item{"s" if len(df) != 1 else ""} in your wardrobe</div>', unsafe_allow_html=True)

    if not df.empty:
        cols = st.columns(4, gap="medium")
        for index, row in df.iterrows():
            with cols[index % 4]:
                # Card with image, badges, and small delete icon
                st.markdown(f"""
                <div class="closet-card">
                    <img src="{row['Image URL']}" alt="{row['Category']}" />
                    <div class="card-label">
                        <span class="card-badge">{row['Category']}</span>
                        <span class="card-badge">{row['Color']}</span>
                        <span class="card-badge">{row['Season']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                # Small delete icon button
                with st.container():
                    st.markdown('<div class="small-del">', unsafe_allow_html=True)
                    if st.button('🗑️', key=f"delete_{index}", help="Delete this item"):
                        delete_item(index)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">👗</div>
            <div class="msg">Your closet is empty</div>
            <p style="color:#666; margin-top:8px;">Head over to <b>Add New Items</b> to start building your wardrobe!</p>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# ADD NEW ITEMS
# ══════════════════════════════════════════════
if selected_option == "Add New Items":
    st.markdown('<div class="section-header">➕ Add New Items</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Upload a photo and tag it to grow your wardrobe</div>', unsafe_allow_html=True)

    # Two-column layout: preview on left, form on right
    col_preview, col_form = st.columns([1, 1], gap="large")

    with col_preview:
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        uploaded_image = st.file_uploader("📸 Drop your image here", type=['png', 'jpg', 'jpeg'])

        if uploaded_image:
            preview_image = Image.open(uploaded_image)
            st.image(preview_image, caption="Preview", use_column_width=True)
            uploaded_image.seek(0)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_form:
        st.markdown("#### 🏷️ Item Details")

        category = st.selectbox('Category', [
            'Hats', 'Shirts', 'Pants', 'Dresses', 'Jackets',
            'Sweaters', 'Shorts', 'Skirts', 'Shoes', 'Accessories', 'Other'
        ])
        if category == 'Other':
            category = st.text_input('Specify category')

        color = st.selectbox('Color', [
            'White', 'Black', 'Red', 'Blue', 'Green',
            'Yellow', 'Orange', 'Purple', 'Pink', 'Brown', 'Other'
        ])
        if color == 'Other':
            color = st.text_input('Specify color')

        season = st.selectbox('Season', ['Spring', 'Summer', 'Fall', 'Winter', 'All', 'Other'])
        if season == 'Other':
            season = st.text_input('Specify season')

        st.markdown("---")

        if st.button('🚀 Upload to Wardrobe', use_container_width=True):
            if uploaded_image:
                with st.spinner("Uploading to Cloudinary..."):
                    image_url, public_id = upload_to_cloudinary(
                        uploaded_image.getvalue(), uploaded_image.name
                    )
                if image_url:
                    save_metadata(image_url, public_id, category, color, season)
                    st.markdown('<div class="success-toast">✅ Item added to your wardrobe!</div>', unsafe_allow_html=True)
            else:
                st.warning("Please upload an image first.")


# ══════════════════════════════════════════════
# SUGGEST OUTFITS
# ══════════════════════════════════════════════
if selected_option == "Suggest Outfits":
    st.markdown('<div class="section-header">✨ AI Outfit Stylist</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Tell us the occasion and our AI will pick the perfect outfit from your closet</div>', unsafe_allow_html=True)

    user_prompt = st.text_input(
        "What's the occasion?",
        placeholder="e.g. 'casual brunch', 'formal dinner', 'summer beach day'..."
    )

    if st.button('💡 Get Suggestions', use_container_width=True):
        if user_prompt:
            df = load_metadata()
            if df.empty:
                st.markdown("""
                <div class="empty-state">
                    <div class="icon">🛒</div>
                    <div class="msg">Your closet is empty!</div>
                    <p style="color:#666; margin-top:8px;">Add some items first so the AI has something to work with.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                with st.spinner("✨ The AI stylist is putting together outfits for you..."):
                    outfits = get_outfit_suggestions(user_prompt, df)

                if outfits:
                    st.markdown(f'<div class="section-header" style="font-size:22px;">🎯 {len(outfits)} Outfit{"s" if len(outfits) != 1 else ""} Suggested</div>', unsafe_allow_html=True)
                    for i, outfit in enumerate(outfits):
                        st.markdown(f"""
                        <div class="outfit-wrap">
                            <div class="outfit-header">👔 Outfit {i+1}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        outfit_cols = st.columns(len(outfit), gap="medium")
                        for j, image_url in enumerate(outfit):
                            with outfit_cols[j]:
                                st.markdown(f"""
                                <div class="closet-card">
                                    <img src="{image_url}" alt="outfit piece" />
                                </div>
                                """, unsafe_allow_html=True)
        else:
            st.warning("Please enter a prompt to get outfit suggestions.")
