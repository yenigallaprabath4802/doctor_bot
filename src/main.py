"""
AgriVoice AI Prototype

This is a functional prototype for AgriVoice AI, a multi-modal assistant for precision farming.
Built using Python with Intel OpenVINO for offline AI inference.

Features:
- User registration and login (local)
- Language detection and response
- Crop disease diagnosis (simulated)
- Cultivation advisory
- Digital prescription (simulated)
- Weather data integration (simulated)
- GPS for locations (simulated)

Offline-first design with local database.
"""

import os
import sqlite3
import hashlib
import json
import socket
import requests
from datetime import datetime
from pathlib import Path
import difflib
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from PIL import Image
import torch
import torch.nn.functional as F

try:
    from . import voice
except ImportError:
    import voice

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

import re

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_DOCUMENT_EXTENSIONS = {'txt', 'pdf', 'docx'}

TEMPLATE_DIR = BASE_DIR / 'templates'
STATIC_DIR = BASE_DIR / 'static'

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Set SECRET_KEY in Render for production

# MongoDB connection (required for cloud deployment)
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://231fa04802_db_user:DqSE99aMsPOykHss@cluster0.uhxlrp0.mongodb.net/')
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client['agrivoice_cloud']

# Dataset API base
DATASET_API_BASE = 'http://localhost:8000/api'

KNOWN_CROPS = ['rice', 'tomato', 'wheat', 'cotton', 'maize', 'banana', 'mango', 'chili', 'sugarcane']

# Dynamically try to load more crops from dataset on startup
CACHED_PLANTS_DATA = []
CACHED_DISEASE_DATA = []
try:
    resp = requests.get(f'{DATASET_API_BASE}/development', timeout=5)
    if resp.status_code == 200:
        CACHED_PLANTS_DATA = resp.json()
        for item in CACHED_PLANTS_DATA:
            cname = item.get("crop_name", "").lower()
            if cname and cname not in KNOWN_CROPS:
                KNOWN_CROPS.append(cname)
    resp_d = requests.get(f'{DATASET_API_BASE}/disease', timeout=5)
    if resp_d.status_code == 200:
        CACHED_DISEASE_DATA = resp_d.json()
except Exception:
    pass

DEFAULT_CULTIVATION_GUIDES = {
    'Rice': 'Rice prefers clayey loam soil, flooded fields during early growth, and regular weeding. Plant in Kharif season, keep fields moist, and harvest after 120-150 days.',
    'Tomato': 'Tomato grows well in well-drained loamy soil, requires regular watering and full sun, staking for support, and harvesting fruit when red and firm.',
    'Wheat': 'Wheat prefers fertile loamy soil, sow in rabi season, maintain moderate watering, apply nitrogen-rich fertilizer, and harvest when grains turn golden.',
    'Cotton': 'Cotton does best in black cotton soil with drip irrigation, warm temperatures, and good weed control. Pick bolls when they open fully.',
    'Maize': 'Maize grows in well-drained loam, needs full sun and regular watering, space plants properly, and harvest when kernels are firm and dry.',
    'Banana': 'Banana needs rich, well-drained soil, lots of water, organic mulch, and protection from strong winds. Fertilize regularly and remove old leaves.',
    'Mango': 'Mango trees prefer deep, well-drained soil, full sunlight, low water during flowering, and more water during fruit development. Prune for airflow.',
    'Chili': 'Chili peppers thrive in warm weather, sandy loam soil, regular watering, and bright sunlight. Support plants and harvest when pods reach desired size.',
    'Sugarcane': 'Sugarcane needs fertile soil, plenty of water, and long warm seasons. Plant setts in furrows, irrigate frequently, and manage weeds closely.'
}

LOCAL_DISEASE_DATA = {
    'Rice': {
        'blast': 'Rice Blast causes dark lesions on leaves and can be managed with resistant varieties and proper spacing.',
        'brown spot': 'Brown Spot appears as round brown lesions; improve soil health and avoid excessive nitrogen.',
        'bacterial leaf blight': 'Bacterial leaf blight leads to yellow stripes; use clean seed and avoid standing water.'
    },
    'Tomato': {
        'early blight': 'Early Blight causes concentric rings on leaves and fruit; use crop rotation and remove infected debris.',
        'late blight': 'Late Blight causes dark, water-soaked patches; ensure good field drainage and use resistant varieties.',
        'powdery mildew': 'Powdery Mildew appears as white powder on leaves; improve airflow and reduce humidity around plants.'
    },
    'Wheat': {
        'rust': 'Wheat rust appears as orange pustules; plant resistant varieties and avoid excessive irrigation.',
        'powdery mildew': 'Powdery mildew produces white powder on leaves; ensure adequate spacing and fungicide application if needed.'
    }
}

TERM_TRANSLATIONS = {
    'Watering': {'Hindi': 'पानी', 'Telugu': 'నీరు'},
    'Sunlight': {'Hindi': 'धूप', 'Telugu': 'సూర్యరశ్మి'},
    'Growth Rate': {'Hindi': 'वृद्धि दर', 'Telugu': 'వృద్ధి వేగం'},
    'Soil': {'Hindi': 'मिट्टी', 'Telugu': 'మట్టిపన'}
}

ERROR_COUNTERS = {
    'db_error': 0,
    'invalid_credentials': 0,
    'runtime': 0,
}

last_error = {'message': None}


def increment_error_counter(key, message=None):
    if key in ERROR_COUNTERS:
        ERROR_COUNTERS[key] += 1
    else:
        ERROR_COUNTERS['runtime'] += 1
    if message:
        last_error['message'] = message


import threading

def sync_user_to_cloud(phone, language):
    def background_sync():
        try:
            mongo_db.users.update_one(
                {'phone': phone},
                {'$set': {'phone': phone, 'language': language, 'last_sync': datetime.now()}},
                upsert=True
            )
        except Exception as e:
            increment_error_counter('db_error', str(e))
    
    threading.Thread(target=background_sync, daemon=True).start()
    return True


def sync_chat_history_to_cloud(phone, chat_history):
    def background_sync():
        try:
            mongo_db.chat_histories.update_one(
                {'phone': phone},
                {'$set': {'phone': phone, 'history': chat_history, 'last_sync': datetime.now()}},
                upsert=True
            )
        except Exception as e:
            increment_error_counter('db_error', str(e))
            
    threading.Thread(target=background_sync, daemon=True).start()
    return True


def route_error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as exc:
            increment_error_counter('db_error', str(exc))
            flash('A database error occurred. Please try again.')
            return redirect(url_for('login'))
        except Exception as exc:
            increment_error_counter('runtime', str(exc))
            flash('An internal error occurred. Please try again.')
            return redirect(url_for('login'))

    wrapper.__name__ = func.__name__
    return wrapper


def is_online():
    try:
        # A simple lightweight GET request to a highly reliable endpoint used by Android
        # This completely bypasses restrictive corporate/ISP firewalls that block raw sockets or DNS ports.
        requests.get('http://clients3.google.com/generate_204', timeout=3)
        return True
    except requests.RequestException:
        return False


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def allowed_document_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOCUMENT_EXTENSIONS


def process_uploaded_files(files, user):
    if not files:
        return {'images': [], 'documents': []}
    saved_images = []
    saved_documents = []
    for uploaded_file in files:
        if uploaded_file:
            filename = secure_filename(uploaded_file.filename)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            saved_name = f"{user}_{timestamp}_{filename}"
            saved_path = UPLOAD_FOLDER / saved_name
            if allowed_image_file(filename):
                uploaded_file.save(saved_path)
                saved_images.append(saved_name)
            elif allowed_document_file(filename):
                uploaded_file.save(saved_path)
                saved_documents.append(saved_name)
    return {'images': saved_images, 'documents': saved_documents}

def cross_reference_database(text):
    text_lower = text.lower()
    matches = []
    # Check remote cache/API data
    for item in CACHED_PLANTS_DATA:
        crop = item.get('crop_name', '')
        if crop and crop.lower() in text_lower:
            dev = item.get('development', {})
            matches.append(f"{crop.capitalize()}: Thrives in {dev.get('climate_required', 'various climates')}, Soil: {dev.get('soil_required', 'well-drained soil')}, Season: {dev.get('planting_season', 'appropriate seasons')}")
            
    # Check local SQLite crop_knowledge table
    conn = sqlite3.connect('agrivoice.db')
    c = conn.cursor()
    try:
        c.execute('SELECT crop, guide FROM crop_knowledge')
        rows = c.fetchall()
        for row in rows:
            crop, guide = row
            if crop.lower() in text_lower and not any(crop.lower() in m.lower() for m in matches):
                matches.append(f"{crop.capitalize()} Cultivation: {guide}")
    except sqlite3.Error as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()
        
    if matches:
        return "\n".join(matches)
    return "No local database matches found for the entities in the document."


def add_chat_message(role, message):
    history = session.get('chat_history', [])
    history.append({'role': role, 'message': message})
    session['chat_history'] = history


SYSTEM_PROMPT = """
**Role:** You are **AgriVoice AI**, a multi-modal assistant for precision farming built for the Intel oneAPI and OpenVINO ecosystem.

**Core Functions:**
* **Automatic Language Detection:** Analyze user input and respond in **Telugu, Hindi, or English**.
* **Hybrid Diagnosis:** Combine user-uploaded images (analyzed via **MobileNetV3**) with real-time weather and soil pH data to identify crop diseases.
* **Cultivation Advisory:** When asked how to grow a specific plant, provide localized, step-by-step guides including soil requirements, watering schedules, and seasonal suitability.
* **Digital Prescription:** Calculate exact chemical dosages. **Safety Gate:** Only provide these if the confidence score is high.

**Operational Rules:**
* **Offline-First:** All primary AI inference must happen locally on the device.
* **User Privacy:** Handle **Registration and Login** (Phone, PIN) locally. Process GPS data locally to find the nearest **Rythu Bharosa Kendras**.
* **Impact Focus:** Your advice must aim for a **30% reduction in crop failure** and **20% cost savings**.
"""


def preprocess_text(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s\u0900-\u097F\u0C00-\u0C7F]', ' ', text)
    return re.sub(r'\s+', ' ', text)


INDIAN_ENGLISH_DICT = {
    r'\bspring\b': 'Spring (Rabi season)',
    r'\bsummer\b': 'Summer (Zaid season)',
    r'\bautumn\b': 'Autumn (Kharif season)',
    r'\bfall\b': 'Autumn (Kharif season)',
    r'\bmonsoon\b': 'Monsoon (Kharif season)',
    r'\bloam\b': 'soft, well-draining soil',
    r'\bloamy\b': 'soft and well-draining',
    r'\bprecipitation\b': 'rainfall',
    r'\bthrives in\b': 'grows best in',
    r'\boptimum\b': 'best',
    r'\boptimal\b': 'best',
    r'\bcultivate\b': 'grow',
    r'\bcultivating\b': 'growing',
    r'\bcultivation\b': 'growing',
    r'\bsusceptible to\b': 'easily affected by',
    r'\birrigation\b': 'watering',
    r'\bhectares\b': 'hectares (about 2.5 acres)',
    r'\byield\b': 'harvest',
    r'\bfoliage\b': 'leaves',
    r'\bclimate\b': 'weather conditions',
    r'\badaptable to general garden climates\b': 'can grow in most normal weather conditions',
    r'\bgarden loam\b': 'normal field soil'
}

def localize_to_indian_english(text):
    if not text:
        return text
    
    localized_text = text
    for pattern, replacement in INDIAN_ENGLISH_DICT.items():
        # Using lambda to preserve original case if it was capitalized (mostly)
        # Actually a simple sub will lowercase the replacement, which is fine for our use case,
        # but to make it slightly smarter:
        def match_case(match):
            word = match.group()
            if word.istitle():
                return replacement.capitalize()
            elif word.isupper():
                return replacement.upper()
            return replacement
            
        localized_text = re.sub(pattern, match_case, localized_text, flags=re.IGNORECASE)
        
    return localized_text


CROP_SYNONYMS = {
    'corn': 'maize',
    'paddy': 'rice',
    'brinjal': 'eggplant',
    'capsicum': 'chili'
}

def extract_crop_name(message):
    message_lower = message.lower()
    
    # Pre-process synonyms (e.g., 'corn' becomes 'maize') so the rest of the logic just works
    for syn, canonical in CROP_SYNONYMS.items():
        message_lower = re.sub(r'\b' + re.escape(syn) + r'\b', canonical, message_lower)
        
    words = message_lower.split()

    # 1. Exact regex match first (fastest and most accurate)
    for crop in KNOWN_CROPS:
        if re.search(r'\b' + re.escape(crop.lower()) + r'\b', message_lower):
            return crop.capitalize()

    # 2. Fuzzy match for known crops (handles spelling mistakes)
    known_lower = [c.lower() for c in KNOWN_CROPS]
    for word in words:
        if len(word) > 3:  # Skip very short words like 'is', 'the', 'how'
            matches = difflib.get_close_matches(word, known_lower, n=1, cutoff=0.8)
            if matches:
                return matches[0].capitalize()

    # 3. Lightweight API search fallback
    clean_msg = message_lower
    for phrase in ['tell me about', 'how to grow', 'information on', 'what is', 'details on', 'know about']:
        clean_msg = clean_msg.replace(phrase, '').strip()

    if clean_msg and len(clean_msg.split()) <= 4:
        # Exact match first
        for item in CACHED_PLANTS_DATA:
            cname = item.get("crop_name", "").lower()
            if clean_msg == cname:
                return item.get("crop_name").capitalize()
        # Whole word match
        for item in CACHED_PLANTS_DATA:
            cname = item.get("crop_name", "").lower()
            if re.search(r'\b' + re.escape(clean_msg) + r'\b', cname) or re.search(r'\b' + re.escape(cname) + r'\b', clean_msg):
                return item.get("crop_name").capitalize()
        # Fuzzy match fallback for API data
        all_cnames = [item.get("crop_name", "").lower() for item in CACHED_PLANTS_DATA]
        matches = difflib.get_close_matches(clean_msg, all_cnames, n=1, cutoff=0.8)
        if matches:
            return matches[0].capitalize()

    return None


EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
EMBEDDING_MODEL = None

INTENT_EXAMPLES = {
    'weather': ["What is the weather?", "Is it going to rain today?", "How hot is it outside?", "What's the forecast?", "Is it sunny?"],
    'cultivation': ["How do I grow this?", "What are the steps to cultivate?", "Tell me how to plant", "Sowing instructions", "Harvesting process", "How to care for this crop", "Cultivation guide"],
    'diagnosis': ["What disease is this?", "My plant has spots", "Leaves are turning yellow", "How to identify pests", "It looks wilted", "Symptoms of rust"],
    'prescription': ["What pesticide should I use?", "How much fertilizer to apply?", "Chemical dosage", "Prescribe a treatment", "What to spray for blight"],
    'snippet_water': ["How much water does it need?", "Irrigation schedule", "When to water the plant", "Watering guide"],
    'snippet_soil': ["What kind of soil is best?", "Soil requirements", "Does it need clay or sand?", "Dirt type"],
    'snippet_climate': ["What climate does it prefer?", "Temperature requirements", "Does it need full sun?", "Sunlight needs"],
    'snippet_season': ["When is the best time to plant?", "Which season to sow?", "Planting month", "When to start seeds"],
    'info': ["Tell me about this plant", "What is it?", "Give me general information", "Details on this crop"],
    'greeting': ["Hello", "Hi there", "Good morning", "Namaste", "Hey"],
    'gratitude': ["Thank you", "Thanks a lot", "I appreciate it", "Thanks"]
}

INTENT_EMBEDDINGS = {}

def load_embedding_model():
    global EMBEDDING_MODEL, INTENT_EMBEDDINGS
    if EMBEDDING_MODEL is not None:
        return EMBEDDING_MODEL
    if pipeline is None:
        print('Transformers pipeline not available; semantic router disabled.')
        return None

    try:
        EMBEDDING_MODEL = pipeline('feature-extraction', model=EMBEDDING_MODEL_NAME, device=-1)
        for intent, examples in INTENT_EXAMPLES.items():
            embeddings = []
            for text in examples:
                out = EMBEDDING_MODEL(text, return_tensors=True)
                emb = out.mean(dim=1)
                emb = F.normalize(emb, p=2, dim=1)
                embeddings.append(emb)
            INTENT_EMBEDDINGS[intent] = torch.cat(embeddings, dim=0)
            
    except Exception as e:
        print(f'Embedding model load error: {e}')
        EMBEDDING_MODEL = None
    return EMBEDDING_MODEL


def get_semantic_intent(message):
    model = load_embedding_model()
    if not model or not INTENT_EMBEDDINGS:
        return None
        
    try:
        out = model(message, return_tensors=True)
        msg_emb = F.normalize(out.mean(dim=1), p=2, dim=1)
        
        best_intent = None
        best_score = -1.0
        
        for intent, embs in INTENT_EMBEDDINGS.items():
            sims = F.cosine_similarity(msg_emb, embs)
            max_sim = sims.max().item()
            if max_sim > best_score:
                best_score = max_sim
                best_intent = intent
                
        if best_score > 0.65:
            return best_intent
        return None
    except Exception as e:
        print(f"Semantic routing error: {e}")
        return None
def local_nlp_parse(message):
    normalized = preprocess_text(message)
    crop = extract_crop_name(message)
    entities = {'crop': crop, 'message': message, 'normalized': normalized}

    # 1. Semantic Routing (The "Self-Thinking" capability)
    intent = get_semantic_intent(message)
    
    # 2. Fallback to keyword matching if semantic router is unavailable or confidence is low
    if not intent:
        if any(word in normalized for word in ['suggest a crop', 'what should i plant', 'profitable crop', 'suggest crop', 'which crop']):
            intent = 'suggest_crop'
        elif any(word in normalized for word in ['not growing', 'failing', 'why is it dying', 'wont grow']):
            intent = 'troubleshoot'
        elif any(word in normalized for word in ['weather', 'rain', 'temperature', 'humidity', 'forecast', 'sunny']):
            intent = 'weather'
        elif any(word in normalized for word in ['grow', 'sow', 'plant', 'cultivate', 'care', 'harvest', 'season']):
            intent = 'cultivation'
        elif any(word in normalized for word in ['disease', 'symptom', 'pest', 'wilt', 'yellow', 'spot', 'blight', 'mildew', 'rust']):
            intent = 'diagnosis'
        elif any(word in normalized for word in ['prescription', 'dose', 'pesticide', 'fertilizer', 'chemical', 'spray']):
            intent = 'prescription'
        elif any(word in normalized for word in ['how much water', 'water', 'irrigation', 'watering']):
            intent = 'snippet_water'
        elif any(word in normalized for word in ['soil', 'dirt', 'ground']):
            intent = 'snippet_soil'
        elif any(word in normalized for word in ['climate', 'temperature', 'sunlight', 'sun']):
            intent = 'snippet_climate'
        elif any(word in normalized for word in ['season', 'when to plant', 'month']):
            intent = 'snippet_season'
        elif any(word in normalized for word in ['tell me about', 'information', 'what is', 'details on', 'know about']):
            intent = 'info'
        elif any(word in normalized for word in ['hi', 'hello', 'hey', 'namaste', 'good morning', 'good evening', 'greetings']):
            intent = 'greeting'
        elif any(word in normalized for word in ['thank', 'thanks', 'thank you']):
            intent = 'gratitude'
        else:
            intent = 'cultivation' if crop else 'fallback'

    return intent, entities


LOCAL_MODEL_NAME = 'distilgpt2'
LOCAL_MODEL = None


def load_local_llm():
    global LOCAL_MODEL
    if LOCAL_MODEL is not None:
        return LOCAL_MODEL
    if pipeline is None:
        print('Transformers pipeline not available; local LLM disabled.')
        return None

    try:
        LOCAL_MODEL = pipeline('text-generation', model=LOCAL_MODEL_NAME, device=-1)
    except Exception as e:
        print(f'Local LLM load error: {e}')
        LOCAL_MODEL = None
    return LOCAL_MODEL


def generate_local_text(prompt, max_new_tokens=80):
    model = load_local_llm()
    if not model:
        return ''
    try:
        outputs = model(prompt, do_sample=True, max_new_tokens=max_new_tokens, temperature=0.7, top_p=0.9)
        text = outputs[0].get('generated_text', '')
        return text[len(prompt):].strip() if text.startswith(prompt) else text.strip()
    except Exception as e:
        print(f'Local LLM generation error: {e}')
        return ''


def analyze_plant_image(image_path):
    try:
        url = "http://localhost:8000/api/predict/pest"
        with open(image_path, 'rb') as f:
            files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
            response = requests.post(url, files=files, timeout=10)
            
        if response.status_code == 200:
            data = response.json()
            pest_name = data.get('prediction', 'Unknown')
            confidence = data.get('confidence', 0.0)
            pesticides = data.get('recommended_pesticides', [])
            image_url = data.get('reference_image_url', None)
            
            if image_url and not image_url.startswith('http'):
                image_url = f"http://localhost:8000{image_url}"
                
            formatted_label = pest_name.replace('_', ' ').title()
            
            res_text = f"I analyzed the image. The plant appears to be affected by {formatted_label} (Confidence: {confidence:.1%}). "
            if pesticides:
                res_text += f"Recommended treatments: {', '.join(pesticides)}."
                
            return localize_to_indian_english(res_text), image_url
            
        return localize_to_indian_english("I couldn't identify any clear issues in the image."), None
    except Exception as e:
        print(f"Image analysis error: {e}")
        return localize_to_indian_english("An error occurred while analyzing the image with the ML endpoint."), None

def local_diagnosis_logic(message, crop):
    normalized = preprocess_text(message)

    if crop:
        crop_name = crop.capitalize()

        try:
            for item in CACHED_DISEASE_DATA:
                if item.get('crop_name', '').capitalize() == crop_name:
                    issues = item.get('issues', item)
                    for disease in issues.get('diseases', []):
                        d_name = preprocess_text(disease.get('disease_name', ''))
                        if d_name in normalized:
                            return (
                                f"Diagnosis ({crop_name} - {disease.get('disease_name')}): "
                                f"{disease.get('symptoms')} Recommended control: {disease.get('control_measures')}"
                            )
                    for pest in issues.get('pests', []):
                        p_name = preprocess_text(pest.get('pest_name', ''))
                        if p_name in normalized:
                            return (
                                f"Pest ({crop_name} - {pest.get('pest_name')}): "
                                f"{pest.get('symptoms')} Recommended control: {pest.get('control_measures')}"
                            )
        except Exception as e:
            print(f"Dataset API Error (Diagnosis): {e}")

    # Local knowledge first
    if crop and crop in LOCAL_DISEASE_DATA:
        for _, summary in LOCAL_DISEASE_DATA[crop].items():
            # Keep original matching by keywords
            for disease_name, s in LOCAL_DISEASE_DATA[crop].items():
                if disease_name in normalized:
                    return s

    symptoms = {
        'yellow': 'Yellowing leaves often point to nutrient deficiency or early blight.',
        'wilt': 'Wilt indicates poor drainage or fungal infection such as Fusarium wilt.',
        'spot': 'Leaf spots may be caused by fungal or bacterial pathogens; remove affected leaves.',
        'blight': 'Blight can spread quickly; use resistant varieties and avoid overhead irrigation.',
        'mildew': 'Powdery mildew usually appears in humid conditions; improve airflow around plants.',
        'rust': 'Rust disease shows orange pustules; practicing crop rotation can help control it.'
    }

    for keyword, diagnosis in symptoms.items():
        if keyword in normalized:
            return diagnosis

    if crop:
        for item in CACHED_PLANTS_DATA:
            cname = item.get("crop_name", "")
            if cname.lower() == crop.lower():
                return f"I recognize {cname}, but I don't have detailed disease records for it to diagnose your issue."

        return (
            f"I do not have a precise diagnosis for {crop} from that description. "
            "Please share more symptoms or crop images if available."
        )

    return 'I do not have enough symptom details to diagnose the issue. Please describe the plant condition in more detail.'


def get_cultivation_guide(crop):
    crop_name = crop.capitalize()

    # Try remote dataset API
    try:
        for item in CACHED_PLANTS_DATA:
            if item.get('crop_name', '').capitalize() == crop_name:
                dev = item.get('development', {})
                api_guide = (
                    f"Soil: {dev.get('soil_required', 'N/A')}. "
                    f"Watering: {dev.get('irrigation', 'N/A')}. "
                    f"Season: {dev.get('planting_season', 'N/A')}. "
                    f"Propagation: {dev.get('propagation_method', 'N/A')}."
                )
                return api_guide
    except Exception as e:
        print(f"Dataset API Error (Cultivation): {e}")

    if crop_name in DEFAULT_CULTIVATION_GUIDES:
        return DEFAULT_CULTIVATION_GUIDES[crop_name]

    # SQLite fallback
    conn = sqlite3.connect('agrivoice.db')
    c = conn.cursor()
    c.execute('SELECT guide FROM crop_knowledge WHERE crop=?', (crop_name,))
    result = c.fetchone()
    conn.close()

    if result:
        return result[0]

    # Search API fallback
    for item in CACHED_PLANTS_DATA:
        cname = item.get("crop_name", "")
        if cname.lower() == crop_name.lower() or crop_name.lower() in cname.lower():
            return f"Yes, I recognize {cname}, but I am currently gathering detailed cultivation data for it."

    return DEFAULT_CULTIVATION_GUIDES.get(crop_name, f'I do not recognize {crop_name} or have a guide for it yet.')


def generate_prescription(disease, confidence):
    if confidence > 0.8:
        return f"For {disease}, apply 2ml pesticide per liter water. Safety: Wear gloves."
    return 'Confidence too low. Consult expert.'


def get_weather(pincode, lat=None, lon=None):
    if not is_online():
        return "Weather data unavailable (offline mode). Simulated: Temp 25°C, Humidity 60%"
        
    api_key = "1712ad72cc89f8a8594cae59c6bbda04"
    if lat and lon:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    else:
        url = f"http://api.openweathermap.org/data/2.5/weather?zip={pincode},IN&appid={api_key}&units=metric"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            temp = data['main']['temp']
            humidity = data['main']['humidity']
            desc = data['weather'][0]['description']
            city_name = data.get('name', 'your area')
            return f"{temp}°C with {humidity}% humidity and {desc} in {city_name}"
    except Exception as e:
        print(f"Weather API Error: {e}")
        
    return "Weather data unavailable (API error). Simulated: Temp 25°C, Humidity 60%"


def local_llm_generate(intent, entities, language, message, pincode='500001', lat=None, lon=None):
    crop = entities.get('crop')
    normalized = entities.get('normalized', '')

    if intent == 'greeting':
        return {
            'English': 'Hello! I am AgriVoice AI. How can I support your farm today?',
            'Hindi': 'नमस्ते! मैं AgriVoice AI हूं। आज मैं आपकी खेती में कैसे सहायता कर सकता हूँ?',
            'Telugu': 'హలో! నేను AgriVoice AI. నేను మీకు ఈరోజు ఎలా సహాయపడగలవను?'
        }.get(language, 'Hello! I am AgriVoice AI. How can I support your farm today?')

    if intent == 'gratitude':
        return {
            'English': 'You are welcome! Ask me anything about crop care or farming.',
            'Hindi': 'आपका स्वागत है! मुझसे फसल की देखभाल या खेती के बारे में कुछ भी पूछें।',
            'Telugu': 'మీకు స్వాగతం! పంట సంరక్షణ లేదా వ్యవసాయం గురించి ఏదైనా నన్ను అడగండి.'
        }.get(language, 'You are welcome! Ask me anything about crop care or farming.')

    if intent == 'weather':
        return get_weather(pincode, lat, lon)

    if intent == 'troubleshoot':
        return ("I understand your crop is not growing as expected. Even if the weather is perfect and you "
                "are using the correct soil type (like black soil or loam), your plant will not grow if the Soil pH "
                "is incorrect! Incorrect pH prevents the roots from absorbing nutrients. Please test your soil pH immediately "
                "and share it with me so I can give further advice.")

    if intent == 'suggest_crop':
        ph_match = re.search(r'ph(?: is)?\s*([0-9.]+)', normalized)
        if not ph_match:
            return ("I can suggest the most profitable crop for your exact location! "
                    "But first, I need to know your soil's acidity. Could you tell me your soil pH value? (e.g., 'My soil pH is 6.5')")
        
        ph = float(ph_match.group(1))
        weather_info = get_weather(pincode, lat, lon)
        
        if 5.5 <= ph <= 7.0:
            suggestion = "Rice or Maize"
        elif 6.0 <= ph <= 7.5:
            suggestion = "Cotton or Tomato"
        else:
            suggestion = "Sugarcane or Banana"
            
        return (f"Based on your local weather ({weather_info}) and your soil pH of {ph}, "
                f"the most profitable crops for you to plant right now are {suggestion}. "
                "Testing soil pH regularly is highly recommended for maximum yield and profit!")

    if intent == 'info':
        if crop:
            crop_name_cap = crop.capitalize()

            # Remote development lookup
            for item in CACHED_PLANTS_DATA:
                if item.get('crop_name', '').lower() == crop.lower():
                    cat = item.get('category', 'Plant')
                    dev = item.get('development', {})
                    climate = dev.get('climate_required', 'various climates')
                    soil = dev.get('soil_required', 'well-drained soil')
                    season = dev.get('planting_season', 'appropriate seasons')
                    return (
                        f"{crop_name_cap} is categorized as {cat}. It generally thrives in {climate} "
                        f"and prefers {soil}. The typical planting season is {season}. "
                        "You can ask me how to grow it or about its diseases for more details!"
                    )

            # Remote search fallback
            for item in CACHED_PLANTS_DATA:
                cname = item.get("crop_name", "")
                if re.search(r'\b' + re.escape(crop.lower()) + r'\b', cname.lower()):
                    return (
                        f"{cname} is a recognized plant in our system, "
                        "but I'm still gathering its detailed climate and soil preferences. "
                        "You can ask me how to grow it or what diseases affect it!"
                    )

            return f"{crop_name_cap} is a plant. You can ask me how to cultivate it or about its diseases."

        return 'Please specify which plant you want information about.'

    if intent.startswith('snippet_'):
        if not crop:
            return 'Please specify the plant name so I can give you the specific details.'

        for item in CACHED_PLANTS_DATA:
            if item.get('crop_name', '').lower() == crop.lower():
                dev = item.get('development', {})
                if intent == 'snippet_water':
                    return f"Watering for {crop.capitalize()}: {dev.get('irrigation', 'Data not available.')}"
                if intent == 'snippet_soil':
                    return f"Soil required for {crop.capitalize()}: {dev.get('soil_required', 'Data not available.')}"
                if intent == 'snippet_climate':
                    return f"Climate required for {crop.capitalize()}: {dev.get('climate_required', 'Data not available.')}"
                if intent == 'snippet_season':
                    return f"Planting season for {crop.capitalize()}: {dev.get('planting_season', 'Data not available.')}"

        return f"I couldn't find specific details for {crop}. You can ask 'How to grow {crop}' for the full guide."

    if intent == 'cultivation':
        if crop:
            return get_cultivation_guide(crop)
        return 'Please tell me the crop name you want to grow, and I will give you a step-by-step cultivation guide.'

    if intent == 'diagnosis':
        diagnosis = local_diagnosis_logic(message, crop)
        return f'For {crop}, {diagnosis}' if crop else diagnosis

    if intent == 'prescription':
        disease = None
        for keyword in ['blight', 'wilt', 'mildew', 'rust', 'spot']:
            if keyword in normalized:
                disease = keyword
                break
        if disease:
            return generate_prescription(disease, 0.85)
        if crop:
            return f'I can suggest a safe crop care routine for {crop}: avoid overwatering, remove damaged leaves, and use protective measures.'
        return 'Please tell me the crop and the problem so I can suggest a safe treatment or prescription.'

    if intent == 'fallback':
        prompt = f"System: {SYSTEM_PROMPT}\nUser: {message}\nAssistant:"
        generated = generate_local_text(prompt)
        return generated or 'I am AgriVoice AI. Ask me about crop care, disease symptoms, or local farming advice.'

    return 'I am AgriVoice AI. Ask me about crop care, disease symptoms, or local farming advice.'


def chat_response(message, language='English', pincode='500001', lat=None, lon=None, document_context=""):
    try:
        from knowledge_base import create_teaching_context
        # Use faq mode to pull from root docs, but it could be expanded
        context_str = create_teaching_context("faq") 
    except Exception as e:
        print(f"Knowledge base error: {e}")
        context_str = ""

    weather_info = get_weather(pincode, lat, lon)

    prompt = f"""IDENTITY:
You are AgriVoice AI, a highly advanced agricultural assistant and AI Teaching Companion.
You help farmers and students learn by answering their questions using course materials and your vast knowledge.

RULES:
- Be accurate — use information from the provided course materials where possible.
- If you don't know or the materials don't cover it, you can use your general farming knowledge.
- Keep responses concise, clear, and actionable.
- Respond in this language: {language}.
- Current weather for the user: {weather_info}.

{context_str}

DOCUMENT UPLOAD AND DATABASE CROSS-REFERENCE:
{document_context}

USER REQUEST:
{message}
"""

    try:
        ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
        # Try gemma3:4b first, fallback to llama3 if not specified
        payload = {
            "model": os.environ.get("LLM_MODEL", "gemma3:4b"),
            "prompt": prompt,
            "stream": False
        }
        resp = requests.post(ollama_url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return localize_to_indian_english(data.get("response", "I am AgriVoice AI. How can I help?"))
        else:
            print(f"Ollama returned {resp.status_code}")
    except Exception as e:
        print(f"Ollama generation error: {e}")

    # Fallback if Ollama fails
    try:
        intent, entities = local_nlp_parse(message)
        response = local_llm_generate(intent, entities, language, message, pincode, lat, lon)
        return localize_to_indian_english(response)
    except Exception as e:
        print(f"Local NLP Error: {e}")
        return localize_to_indian_english('I am AgriVoice AI. Ask me about crop care, disease symptoms, or local farming advice.')


def init_db():
    conn = sqlite3.connect('agrivoice.db')
    c = conn.cursor()
    # Drop the old users table to migrate schema
    c.execute('DROP TABLE IF EXISTS users')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    phone TEXT PRIMARY KEY,
                    pin_hash TEXT,
                    language TEXT DEFAULT 'English',
                    pincode TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS prescriptions (
                    id INTEGER PRIMARY KEY,
                    phone TEXT,
                    prescription TEXT,
                    date TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS crop_knowledge (
                    crop TEXT PRIMARY KEY,
                    guide TEXT
                )''')

    sample_crops = [
        ('Rice', 'Soil: Clayey loam. Watering: Flooded fields. Season: Kharif (June-Oct). Steps: 1. Prepare land. 2. Sow seeds. 3. Irrigate. 4. Harvest after 120-150 days.'),
        ('Cotton', 'Soil: Black cotton soil. Watering: Drip irrigation. Season: Kharif. Steps: 1. Till soil. 2. Plant seeds. 3. Fertilize. 4. Pick bolls.')
    ]
    for crop, guide in sample_crops:
        c.execute('INSERT OR IGNORE INTO crop_knowledge VALUES (?, ?)', (crop, guide))

    c.execute('''CREATE TABLE IF NOT EXISTS crop_cache (
                    crop TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at TEXT
                )''')

    c.execute('INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)', (
        '9999999999', hashlib.sha256('0000'.encode()).hexdigest(), 'English', '500001'
    ))

    conn.commit()
    conn.close()


@app.route('/')
def index():
    if session.get('user'):
        return redirect(url_for('chat'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
@route_error_handler
def login():
    if session.get('user'):
        return redirect(url_for('chat'))

    if request.method == 'POST':
        phone = request.form['phone']
        pin = request.form['pin']
        lang, pincode = login_user(phone, pin)
        if lang:
            session['user'] = phone
            session['language'] = lang
            session['pincode'] = pincode
            session['chat_history'] = []
            sync_user_to_cloud(phone, lang)
            return redirect(url_for('chat'))
        increment_error_counter('invalid_credentials', 'Invalid login attempt for phone: ' + phone)
        flash('Invalid credentials.')

    return render_template('login.html', system_prompt=SYSTEM_PROMPT)


def register_user(phone, pin, language='English', pincode='500001'):
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    conn = sqlite3.connect('agrivoice.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users VALUES (?, ?, ?, ?)', (phone, pin_hash, language, pincode))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def login_user(phone, pin):
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    conn = sqlite3.connect('agrivoice.db')
    c = conn.cursor()
    c.execute('SELECT language, pincode FROM users WHERE phone=? AND pin_hash=?', (phone, pin_hash))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0], result[1]
    increment_error_counter('invalid_credentials', 'Invalid credentials for phone: ' + phone)
    return None, None


@app.route('/chat', methods=['GET', 'POST'])
@route_error_handler
def chat():
    if not session.get('user'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        image_analysis_response = ""
        document_context = ""
        if 'image_files' in request.files and request.files.getlist('image_files'):
            image_files = request.files.getlist('image_files')
            processed_files = process_uploaded_files(image_files, session['user'])
            
            if processed_files['images']:
                add_chat_message('image', processed_files['images'])
                analyses = []
                image_url = None
                for name in processed_files['images']:
                    image_path = UPLOAD_FOLDER / name
                    res_text, res_url = analyze_plant_image(str(image_path))
                    analyses.append(res_text)
                    if res_url:
                        image_url = res_url
                image_analysis_response = " ".join(analyses)
                add_chat_message('bot', image_analysis_response)
                
            if processed_files['documents']:
                from knowledge_base import read_file
                from pathlib import Path
                doc_texts = []
                for name in processed_files['documents']:
                    doc_path = UPLOAD_FOLDER / name
                    text = read_file(Path(doc_path))
                    if text:
                        doc_texts.append(f"--- Document: {name} ---\n{text}")
                        add_chat_message('bot', f'Successfully read document: {name}. I am analyzing its contents.')
                
                if doc_texts:
                    full_text = "\n".join(doc_texts)
                    db_context = cross_reference_database(full_text)
                    document_context = f"{full_text}\n\nDATABASE MATCHES:\n{db_context}"

        if 'chat_message' in request.form and request.form['chat_message'].strip():
            user_message = request.form['chat_message'].strip()
            language = session.get('language', 'English')
            pincode = session.get('pincode', '500001')
            add_chat_message('user', user_message)
            
            # Combine image analysis context if present
            if image_analysis_response:
                user_message_with_context = f"Image Context: {image_analysis_response}. User: {user_message}"
                response = chat_response(user_message_with_context, language, pincode, lat=None, lon=None, document_context=document_context)
            else:
                response = chat_response(user_message, language, pincode, lat=None, lon=None, document_context=document_context)
                
            add_chat_message('bot', response)
        elif document_context:
            language = session.get('language', 'English')
            pincode = session.get('pincode', '500001')
            user_message = "I have uploaded a document. Please review it and tell me the most important details."
            add_chat_message('user', "Uploaded document for analysis.")
            response = chat_response(user_message, language, pincode, lat=None, lon=None, document_context=document_context)
            add_chat_message('bot', response)

        if session.get('chat_history'):
            sync_chat_history_to_cloud(session['user'], session['chat_history'])

        return redirect(url_for('chat'))

    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
@route_error_handler
def api_chat():
    if not session.get('user'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_message = ""
    image_analysis_response = ""
    image_url = None
    lat = None
    lon = None
    
    document_context = ""
    # Handle both JSON and FormData
    if request.is_json:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        lat = data.get('lat')
        lon = data.get('lon')
    else:
        user_message = request.form.get('chat_message', '').strip()
        lat = request.form.get('lat')
        lon = request.form.get('lon')
        if 'image_files' in request.files and request.files.getlist('image_files'):
            image_files = request.files.getlist('image_files')
            processed_files = process_uploaded_files(image_files, session['user'])
            
            if processed_files['images']:
                add_chat_message('image', processed_files['images'])
                analyses = []
                for name in processed_files['images']:
                    image_path = UPLOAD_FOLDER / name
                    res_text, res_url = analyze_plant_image(str(image_path))
                    analyses.append(res_text)
                    if res_url:
                        image_url = res_url
                image_analysis_response = " ".join(analyses)
                
            if processed_files['documents']:
                from knowledge_base import read_file
                from pathlib import Path
                doc_texts = []
                for name in processed_files['documents']:
                    doc_path = UPLOAD_FOLDER / name
                    text = read_file(Path(doc_path))
                    if text:
                        doc_texts.append(f"--- Document: {name} ---\n{text}")
                
                if doc_texts:
                    full_text = "\n".join(doc_texts)
                    db_context = cross_reference_database(full_text)
                    document_context = f"{full_text}\n\nDATABASE MATCHES:\n{db_context}"

    if not user_message and not image_analysis_response and not document_context:
        return jsonify({'error': 'No message provided'}), 400
        
    language = session.get('language', 'English')
    pincode = session.get('pincode', '500001')
    
    if user_message or document_context:
        if not user_message and document_context:
            user_message = "I have uploaded a document. Please review it and tell me the most important details."
            
        add_chat_message('user', user_message)
        if image_analysis_response:
            # First send the image analysis so they see it, then send the response to their text
            add_chat_message('bot', image_analysis_response)
            
            user_message_with_context = f"Image Context: {image_analysis_response}. User: {user_message}"
            response = chat_response(user_message_with_context, language, pincode, lat, lon, document_context)
            add_chat_message('bot', response)
            
            # Return combined response for UI
            final_response = f"{image_analysis_response}\n\n{response}"
        else:
            final_response = chat_response(user_message, language, pincode, lat, lon, document_context)
            add_chat_message('bot', final_response)
    else:
        add_chat_message('bot', image_analysis_response)
        final_response = image_analysis_response
    
    if session.get('chat_history'):
        sync_chat_history_to_cloud(session['user'], session['chat_history'])
        
    response_data = {
        'response': final_response,
        'role': 'bot'
    }
    if image_url:
        response_data['image_url'] = image_url
        
    return jsonify(response_data)


@app.route('/speak', methods=['POST'])
@route_error_handler
def speak():
    text = request.form.get('text', '').strip()
    language = request.form.get('language', 'English')
    if not text:
        return jsonify({'success': False, 'error': 'No text provided.'}), 400
    success = voice.text_to_speech(text, language)
    return jsonify({'success': success})

@app.route('/api/tts', methods=['POST'])
@route_error_handler
def api_tts():
    if not session.get('user'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json() if request.is_json else request.form
    text = data.get('text', '').strip()
    voice_style = data.get('voice_style', 'male').lower()
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
        
    # Generate unique filename
    import uuid
    filename = f"tts_{uuid.uuid4().hex}.wav"
    output_path = UPLOAD_FOLDER / filename
    
    success = voice.generate_tts_audio_file(text, str(output_path), voice_style)
    
    if success:
        return jsonify({'audio_url': url_for('static', filename=f'uploads/{filename}')})
    else:
        return jsonify({'error': 'Failed to generate audio'}), 500


@app.route('/register', methods=['GET', 'POST'])
@route_error_handler
def register():
    if request.method == 'POST':
        phone = request.form['phone']
        pin = request.form['pin']
        confirm_pin = request.form.get('confirm_pin', '')
        pincode = request.form.get('pincode', '500001').strip()
        language = request.form.get('language', 'English')

        if pin != confirm_pin:
            flash('PINs do not match.')
            return render_template('register.html')

        if len(pin) < 4:
            flash('PIN must be at least 4 characters long.')
            return render_template('register.html')

        if register_user(phone, pin, language, pincode):
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))

        flash('Phone number already registered. Please log in or use a different phone.')

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# Initialize the database so it's created even when running via Gunicorn on Render
init_db()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

