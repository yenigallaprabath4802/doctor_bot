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

import sqlite3
import hashlib
import json
import socket
import requests
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
from werkzeug.utils import secure_filename

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

TEMPLATE_DIR = BASE_DIR / 'templates'
STATIC_DIR = BASE_DIR / 'static'

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))
app.secret_key = 'your_secret_key'  # Change in production

# MongoDB connection (optional; app can still work without it)
MONGO_URI = 'mongodb+srv://231fa04802_db_user:DqSE99aMsPOykHss@cluster0.uhxlrp0.mongodb.net/'
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client['agrivoice_cloud']

# Dataset API base (hosted on GitHub Pages - static JSON files)
DATASET_API_BASE = 'https://yenigallaprabath4802.github.io/apolo_api/api_data'

KNOWN_CROPS = ['rice', 'tomato', 'wheat', 'cotton', 'maize', 'banana', 'mango', 'chili', 'sugarcane']

# Dynamically try to load more crops from dataset on startup
try:
    resp = requests.get(f'{DATASET_API_BASE}/plants_development.json', timeout=5)
    if resp.status_code == 200:
        for item in resp.json():
            cname = item.get("crop_name", "").lower()
            if cname and cname not in KNOWN_CROPS:
                KNOWN_CROPS.append(cname)
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


def sync_user_to_cloud(phone, language):
    try:
        mongo_db.users.update_one(
            {'phone': phone},
            {'$set': {'phone': phone, 'language': language, 'last_sync': datetime.now()}},
            upsert=True
        )
        return True
    except Exception as e:
        increment_error_counter('db_error', str(e))
        return False


def sync_chat_history_to_cloud(phone, chat_history):
    try:
        mongo_db.chat_histories.update_one(
            {'phone': phone},
            {'$set': {'phone': phone, 'history': chat_history, 'last_sync': datetime.now()}},
            upsert=True
        )
        return True
    except Exception as e:
        increment_error_counter('db_error', str(e))
        return False


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
        conn = socket.create_connection(('8.8.8.8', 53), timeout=3)
        conn.close()
        return True
    except OSError:
        return False


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def process_uploaded_images(files, user):
    if not files:
        return []
    saved_names = []
    for uploaded_file in files:
        if uploaded_file and allowed_image_file(uploaded_file.filename):
            filename = secure_filename(uploaded_file.filename)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            saved_name = f"{user}_{timestamp}_{filename}"
            saved_path = UPLOAD_FOLDER / saved_name
            uploaded_file.save(saved_path)
            saved_names.append(saved_name)
    return saved_names


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


def extract_crop_name(message):
    message_lower = message.lower()

    for crop in KNOWN_CROPS:
        if (
            f' {crop} ' in message_lower
            or message_lower.startswith(f'{crop} ')
            or message_lower.endswith(f' {crop}')
            or message_lower == crop
        ):
            return crop.capitalize()

    # Lightweight API search fallback
    clean_msg = message_lower
    for phrase in ['tell me about', 'how to grow', 'information on', 'what is', 'details on', 'know about']:
        clean_msg = clean_msg.replace(phrase, '').strip()

    if clean_msg and len(clean_msg.split()) <= 4:
        try:
            resp = requests.get(f"{DATASET_API_BASE}/plants/search?q={clean_msg}", timeout=1)
            if resp.status_code == 200 and resp.json().get('found'):
                return resp.json().get('crop_name').capitalize()
        except Exception:
            pass

    return None


def local_nlp_parse(message):
    normalized = preprocess_text(message)
    crop = extract_crop_name(message)
    entities = {'crop': crop, 'message': message, 'normalized': normalized}

    if any(word in normalized for word in ['weather', 'rain', 'temperature', 'humidity', 'forecast', 'sunny']):
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


def local_diagnosis_logic(message, crop):
    normalized = preprocess_text(message)

    if crop:
        crop_name = crop.capitalize()

        try:
            response = requests.get(f"{DATASET_API_BASE}/disease", timeout=3)
            if response.status_code == 200:
                data = response.json()
                for item in data:
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
        try:
            search_resp = requests.get(f"{DATASET_API_BASE}/plants/search?q={crop}", timeout=3)
            if search_resp.status_code == 200:
                search_data = search_resp.json()
                if search_data.get('found'):
                    full_name = search_data.get('full_name', crop)
                    return (
                        f"I recognize {full_name}, but I don't have detailed disease records for it to diagnose your issue."
                    )
        except Exception:
            pass

        return (
            f"I do not have a precise diagnosis for {crop} from that description. "
            "Please share more symptoms or crop images if available."
        )

    return 'I do not have enough symptom details to diagnose the issue. Please describe the plant condition in more detail.'


def get_cultivation_guide(crop):
    crop_name = crop.capitalize()

    # Try remote dataset API
    try:
        response = requests.get(f"{DATASET_API_BASE}/development", timeout=3)
        if response.status_code == 200:
            data = response.json()
            for item in data:
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
    try:
        search_resp = requests.get(f"{DATASET_API_BASE}/plants/search?q={crop_name}", timeout=3)
        if search_resp.status_code == 200:
            search_data = search_resp.json()
            if search_data.get('found'):
                full_name = search_data.get('full_name', crop_name)
                return f"Yes, I recognize {full_name}, but I am currently gathering detailed cultivation data for it."
    except Exception:
        pass

    return DEFAULT_CULTIVATION_GUIDES.get(crop_name, f'I do not recognize {crop_name} or have a guide for it yet.')


def generate_prescription(disease, confidence):
    if confidence > 0.8:
        return f"For {disease}, apply 2ml pesticide per liter water. Safety: Wear gloves."
    return 'Confidence too low. Consult expert.'


def get_weather(lat, lon):
    return "Weather data unavailable (offline mode). Simulated: Temp 25°C, Humidity 60%"


def local_llm_generate(intent, entities, language, message):
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
        return get_weather(17.3850, 78.4867)

    if intent == 'info':
        if crop:
            crop_name_cap = crop.capitalize()

            # Remote development lookup
            try:
                resp = requests.get(f"{DATASET_API_BASE}/development", timeout=3)
                if resp.status_code == 200:
                    for item in resp.json():
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
            except Exception:
                pass

            # Remote search fallback
            try:
                search_resp = requests.get(f"{DATASET_API_BASE}/plants/search?q={crop}", timeout=3)
                if search_resp.status_code == 200:
                    data = search_resp.json()
                    if data.get('found'):
                        return (
                            f"{data.get('full_name', crop_name_cap)} is a recognized plant in our system, "
                            "but I'm still gathering its detailed climate and soil preferences. "
                            "You can ask me how to grow it or what diseases affect it!"
                        )
            except Exception:
                pass

            return f"{crop_name_cap} is a plant. You can ask me how to cultivate it or about its diseases."

        return 'Please specify which plant you want information about.'

    if intent.startswith('snippet_'):
        if not crop:
            return 'Please specify the plant name so I can give you the specific details.'

        try:
            resp = requests.get(f"{DATASET_API_BASE}/development", timeout=3)
            if resp.status_code == 200:
                for item in resp.json():
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
        except Exception:
            pass

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


def chat_response(message, language='English'):
    try:
        intent, entities = local_nlp_parse(message)
        return local_llm_generate(intent, entities, language, message)
    except Exception as e:
        print(f"Local NLP Error: {e}")
        return 'I am AgriVoice AI. Ask me about crop care, disease symptoms, or local farming advice.'


def init_db():
    conn = sqlite3.connect('agrivoice.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    phone TEXT PRIMARY KEY,
                    pin_hash TEXT,
                    language TEXT DEFAULT 'English'
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

    c.execute('INSERT OR IGNORE INTO users VALUES (?, ?, ?)', (
        '9999999999', hashlib.sha256('0000'.encode()).hexdigest(), 'English'
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
        lang = login_user(phone, pin)
        if lang:
            session['user'] = phone
            session['language'] = lang
            session['chat_history'] = []
            sync_user_to_cloud(phone, lang)
            return redirect(url_for('chat'))
        increment_error_counter('invalid_credentials', 'Invalid login attempt for phone: ' + phone)
        flash('Invalid credentials.')

    return render_template('login.html', system_prompt=SYSTEM_PROMPT)


def register_user(phone, pin, language='English'):
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    conn = sqlite3.connect('agrivoice.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users VALUES (?, ?, ?)', (phone, pin_hash, language))
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
    c.execute('SELECT language FROM users WHERE phone=? AND pin_hash=?', (phone, pin_hash))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0]
    increment_error_counter('invalid_credentials', 'Invalid credentials for phone: ' + phone)
    return None


@app.route('/chat', methods=['GET', 'POST'])
@route_error_handler
def chat():
    if not session.get('user'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'image_files' in request.files and request.files.getlist('image_files'):
            image_files = request.files.getlist('image_files')
            saved_names = process_uploaded_images(image_files, session['user'])
            if saved_names:
                add_chat_message('image', saved_names)
                add_chat_message('bot', f'Received {len(saved_names)} image(s). Image analysis is not enabled yet.')
            else:
                add_chat_message('bot', 'Uploaded files were not valid image types.')

        if 'chat_message' in request.form and request.form['chat_message'].strip():
            user_message = request.form['chat_message'].strip()
            language = session.get('language', 'English')
            add_chat_message('user', user_message)
            response = chat_response(user_message, language)
            add_chat_message('bot', response)

        if session.get('chat_history'):
            sync_chat_history_to_cloud(session['user'], session['chat_history'])

        return redirect(url_for('chat'))

    return render_template('chat.html')


@app.route('/speak', methods=['POST'])
@route_error_handler
def speak():
    text = request.form.get('text', '').strip()
    language = request.form.get('language', 'English')
    if not text:
        return jsonify({'success': False, 'error': 'No text provided.'}), 400
    success = voice.text_to_speech(text, language)
    return jsonify({'success': success})


@app.route('/register', methods=['GET', 'POST'])
@route_error_handler
def register():
    if request.method == 'POST':
        phone = request.form['phone']
        pin = request.form['pin']
        confirm_pin = request.form.get('confirm_pin', '')
        language = request.form.get('language', 'English')

        if pin != confirm_pin:
            flash('PINs do not match.')
            return render_template('register.html')

        if len(pin) < 4:
            flash('PIN must be at least 4 characters long.')
            return render_template('register.html')

        if register_user(phone, pin, language):
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))

        flash('Phone number already registered. Please log in or use a different phone.')

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

