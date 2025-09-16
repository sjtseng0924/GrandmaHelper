import os
import json
import base64
import random
import tempfile
import datetime
from datetime import datetime as dt
import pytz
from flask import Flask, request, jsonify, send_file
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview.vision_models import ImageGenerationModel
from src.utils.text_overlay import overlay_greeting
import traceback

app = Flask(__name__)

# Initialize Vertex AI
PROJECT_ID = "hackathon-468512"
LOCATION = "us-central1"
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Global variables
image_model = None
text_model = None
morning_config = None

# Create debug directory
DEBUG_DIR = "/tmp/morning_debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

# Holiday mapping (from prompt_generation.py)
HOLIDAY_MAP = {
    "12-25": "聖誕節",
    "1-1": "元旦",
    "2-14": "情人節",
    "5-1": "勞動節",
    "10-10": "雙十節"
}

def get_time_based_greeting():
    """Get greeting based on current time in GMT+8"""
    gmt8 = pytz.timezone('Asia/Taipei')
    current_time = dt.now(gmt8)
    hour = current_time.hour
    
    if 0 <= hour < 11:
        return "早安"
    elif 11 <= hour < 16:
        return "午安"
    else:  # 16 <= hour < 24
        return "晚安"

def log_debug(step, data, save_file=None):
    """Debug logging with savepoints"""
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S_%f")
    print(f"[DEBUG {timestamp}] Step {step}: {data}")
    
    # Save to file if specified
    if save_file:
        debug_file = os.path.join(DEBUG_DIR, f"{timestamp}_{step}_{save_file}")
        if isinstance(data, (dict, list)):
            with open(debug_file + ".json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif isinstance(data, bytes):
            with open(debug_file + ".bin", 'wb') as f:
                f.write(data)
        else:
            with open(debug_file + ".txt", 'w', encoding='utf-8') as f:
                f.write(str(data))
        print(f"[DEBUG] Saved to: {debug_file}")

def load_morning_config():
    """Load morning image configuration from JSON file"""
    global morning_config
    if morning_config is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'morning_image_config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                morning_config = json.load(f)
                log_debug("CONFIG_LOAD", "Morning image configuration loaded successfully")
        except Exception as e:
            log_debug("CONFIG_ERROR", f"Error loading morning config: {e}")
            morning_config = {}
    return morning_config

def get_models():
    global image_model, text_model
    if image_model is None or text_model is None:
        image_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        text_model = GenerativeModel(model_name="gemini-2.5-flash")
        log_debug("MODELS_INIT", "Models initialized successfully")
    return image_model, text_model

def detect_holiday_from_date(date_str):
    """Detect holiday/solar term from date string (enhanced from prompt_generation.py)"""
    try:
        if not date_str:
            return None
        
        # Parse date
        date_obj = dt.strptime(date_str, "%Y-%m-%d")
        month, day = date_obj.month, date_obj.day
        
        holiday = HOLIDAY_MAP.get(f"{month}-{day}")
        log_debug("DATE_DETECT", f"Date {date_str} -> Holiday: {holiday}")
        return holiday
    except Exception as e:
        log_debug("DATE_ERROR", f"Error detecting holiday from {date_str}: {e}")
        return None

def generate_image_prompt_with_gemini(user_input=None, holiday=None):
    """Generate English image prompt using Gemini (from prompt_generation.py)"""
    _, text_model = get_models()
    
    if user_input:
        input_text = f"User input: {user_input}"
    else:
        input_text = "User did not provide input, generate a random theme, object, and style"

    if holiday:
        input_text += f" It's for {holiday}."

    system_prompt = f"""
You are a professional prompt engineer for image generation.
Turn the following text into a ready-to-use **English prompt** for an image generation model.
Requirements:
- Include theme, style, objects, scene elements (optional), color tone.
- 1:1 aspect ratio
- Do NOT include any text in the image.

{input_text}
    """.strip()

    response = text_model.generate_content(system_prompt)
    return response.text.strip()

def generate_blessing_text(user_input=None, image_prompt=None, holiday=None):
    """Generate blessing text in Chinese using Gemini (from prompt_generation.py)"""
    _, text_model = get_models()
    
    if not image_prompt:
        # Fallback blessing if no image prompt - use time-based greeting
        return f"{get_time_based_greeting()}祝福"

    system_prompt = f"""
我有以下資訊：
- 用戶輸入: {user_input or '無'}
- 圖片描述: {image_prompt}
- 節日: {holiday or '無'}

請生成一句中文祝福語，用於圖片上方。
要求：簡短、貼近節日或主題，如果沒有特定節日，生成通用"繁體中文"祝福。
只輸出祝福文字，不要其他描述。
    """.strip()

    response = text_model.generate_content(system_prompt)
    return response.text.strip()

def generate_display_text(config, prompt=None, date=None, custom_text=None):
    """Enhanced text generation using prompt_generation.py logic"""
    log_debug("TEXT_GEN_START", {"prompt": prompt, "date": date, "custom_text": custom_text})
    
    # Detect holiday from date
    holiday = detect_holiday_from_date(date) if date else None
    
    # Generate blessing text using new Gemini approach
    if custom_text:
        blessing_text = custom_text
    else:
        # Use prompt generation logic to create smart blessing
        try:
            # First generate image prompt for context
            temp_image_prompt = generate_image_prompt_with_gemini(prompt, holiday)
            # Then generate blessing based on that context
            blessing_text = generate_blessing_text(prompt, temp_image_prompt, holiday)
        except Exception as e:
            log_debug("BLESSING_GEN_ERROR", f"Error generating blessing: {e}")
            # Fallback to simple blessing
            if holiday:
                blessing_text = f"{holiday}快樂"
            else:
                blessing_text = f"{get_time_based_greeting()}祝福"
    
    # Get time-based greeting instead of static default
    main_text = get_time_based_greeting()
    
    result = {
        "main_text": main_text,
        "blessing_text": blessing_text,
        "holiday": holiday,
        "prompt_input": prompt
    }
    
    log_debug("TEXT_GEN_RESULT", result, "text_generation")
    return result

def build_image_prompt(config, text_data, uploaded_image=None, style=None):
    """Enhanced prompt building using prompt_generation.py logic"""
    log_debug("PROMPT_BUILD_START", {
        "text_data": text_data, 
        "has_uploaded": uploaded_image is not None,
        "style": style
    })
    
    if uploaded_image:
        log_debug("PROMPT_BUILD_SKIP", "Using uploaded image, skipping generation")
        return None, "user_uploaded"
    
    # Use the new Gemini-based prompt generation
    try:
        prompt_input = text_data.get('prompt_input')
        holiday = text_data.get('holiday')
        
        # Generate smart prompt using Gemini
        formatted_prompt = generate_image_prompt_with_gemini(prompt_input, holiday)
        
        log_debug("PROMPT_BUILD_RESULT", {"prompt": formatted_prompt}, "image_prompt")
        return formatted_prompt, "gemini_generated"
        
    except Exception as e:
        log_debug("PROMPT_BUILD_ERROR", f"Error with Gemini prompt generation: {e}")
        
        # Fallback to original logic
        prompt_templates = config.get('prompt_templates', {})
        main_template = prompt_templates.get('main_template', {})
        
        # Fallback template with time-based greeting
        time_greeting = get_time_based_greeting()
        formatted_prompt = f"""生成一張{time_greeting}祝福背景圖片，台灣日常質感。
金色晨光 + 淺景深 + 柔和散景，畫面乾淨、通透。
構圖：三分法構圖，背景層次分明。
重要：請不要包含任何文字、字體或文案，只要純淨的背景畫面。
相機質感：50mm F1.8 寫實攝影，比例：1:1正方形。
關鍵詞：台味、溫暖、吉祥、乾淨背景、無文字。"""
        
        log_debug("PROMPT_BUILD_FALLBACK", {"prompt": formatted_prompt})
        return formatted_prompt, "config_fallback"

def generate_background_image(prompt):
    """Step 4: Generate background image using Imagen"""
    log_debug("IMAGE_GEN_START", {"prompt": prompt[:100] + "..."})
    
    try:
        image_model, _ = get_models()
        
        # Get negative prompt from config
        config = load_morning_config()
        negative_prompt = config.get('prompt_templates', {}).get('negative_prompt', '')
        
        # Generate image
        generate_params = {
            'prompt': prompt,
            'number_of_images': 1,
            'guidance_scale': 20,
            'safety_filter_level': 'block_few'
        }
        
        if negative_prompt:
            generate_params['negative_prompt'] = negative_prompt
        
        log_debug("IMAGE_GEN_PARAMS", generate_params)
        
        images = image_model.generate_images(**generate_params)
        
        if not images:
            raise Exception("No images generated")
        
        # Get image bytes
        image_bytes = images[0]._image_bytes
        
        # Save debug image
        debug_image_path = os.path.join(DEBUG_DIR, f"generated_bg_{dt.now().strftime('%H%M%S')}.png")
        with open(debug_image_path, 'wb') as f:
            f.write(image_bytes)
        
        log_debug("IMAGE_GEN_SUCCESS", f"Image generated and saved to {debug_image_path}")
        return image_bytes, debug_image_path
        
    except Exception as e:
        log_debug("IMAGE_GEN_ERROR", f"Error generating image: {e}")
        traceback.print_exc()
        raise

def compose_final_image(image_source, text_data, source_type="generated"):
    """Step 5: Compose final result with text overlay (enhanced with smart text)"""
    log_debug("COMPOSE_START", {"source_type": source_type, "text_data": text_data})
    
    try:
        # Create temporary files
        if source_type == "generated" or source_type == "gemini_generated" or source_type == "config_fallback":
            # image_source is bytes
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_bg:
                temp_bg.write(image_source)
                bg_path = temp_bg.name
        else:
            # image_source is file path (uploaded image)
            bg_path = image_source
        
        # SAVE ORIGINAL BACKGROUND IMAGE FOR DEBUGGING
        bg_debug_path = os.path.join(DEBUG_DIR, f"background_only_{dt.now().strftime('%H%M%S')}.png")
        if source_type != "user_uploaded":
            with open(bg_debug_path, 'wb') as f:
                f.write(image_source)
            log_debug("BACKGROUND_SAVED", f"Original background saved: {bg_debug_path}")
        
        # Create output path
        final_path = os.path.join(DEBUG_DIR, f"final_image_{dt.now().strftime('%H%M%S')}.jpg")
        
        # Log text overlay details
        log_debug("TEXT_OVERLAY_START", {
            "main_text": text_data['main_text'],
            "blessing_text": text_data['blessing_text'],
            "background_path": bg_path,
            "output_path": final_path
        }, "text_overlay_params")
        
        # Apply text overlay using smart generated text
        overlay_greeting(
            image_path=bg_path,
            top_text=text_data['main_text'],
            small_vertical_text=text_data['blessing_text'],
            output_path=final_path,
            layout='random'  # Use random layout
        )
        
        # Read final image
        with open(final_path, 'rb') as f:
            final_image_bytes = f.read()
        
        log_debug("COMPOSE_SUCCESS", f"Final image created: {final_path}")
        log_debug("FILES_AVAILABLE", {
            "original_background": bg_debug_path if source_type != "user_uploaded" else bg_path,
            "final_with_text": final_path,
            "sizes": {
                "background": len(image_source) if isinstance(image_source, bytes) else os.path.getsize(bg_path),
                "final": len(final_image_bytes)
            }
        }, "debug_files")
        
        return final_image_bytes, final_path
        
    except Exception as e:
        log_debug("COMPOSE_ERROR", f"Error composing final image: {e}")
        traceback.print_exc()
        raise
    finally:
        # DON'T clean up temp background - keep for debugging
        pass

# ============= API ENDPOINTS (MAINTAINING EXACT SAME FORMAT) =============

@app.route('/generate', methods=['POST'])
def generate():
    """Main generate endpoint - ENHANCED with smart prompt generation and text overlay"""
    try:
        config = load_morning_config()
        log_debug("API_START", "Generate endpoint called with enhanced features")
        
        # Step 1: Parse input - handle both multipart and empty requests (SAME AS BEFORE)
        prompt = None
        date = None
        custom_text = None
        style = None
        uploaded_image = None
        
        # Handle multipart form data
        if request.content_type and 'multipart/form-data' in request.content_type:
            prompt = request.form.get('prompt')
            date = request.form.get('date')  
            custom_text = request.form.get('custom_text')
            style = request.form.get('style')
            
            # Handle uploaded image
            if 'image' in request.files:
                image_file = request.files['image']
                if image_file and image_file.filename:
                    # Save uploaded image
                    upload_path = os.path.join(DEBUG_DIR, f"uploaded_{dt.now().strftime('%H%M%S')}_{image_file.filename}")
                    image_file.save(upload_path)
                    uploaded_image = upload_path
                    log_debug("UPLOAD_SUCCESS", f"Image uploaded: {upload_path}")
        
        # Handle empty POST request (Basic Random Image case)
        elif not request.data and not request.form:
            log_debug("EMPTY_REQUEST", "Empty POST request - generating random morning image")
        
        log_debug("INPUT_PARSED", {
            "prompt": prompt,
            "date": date, 
            "custom_text": custom_text,
            "style": style,
            "has_upload": uploaded_image is not None
        }, "input_data")
        
        # Step 2: Generate display text using ENHANCED logic with Gemini
        text_data = generate_display_text(config, prompt, date, custom_text)
        
        # Step 3: Build image prompt using ENHANCED logic with Gemini
        image_prompt, source_type = build_image_prompt(config, text_data, uploaded_image, style)
        
        # Step 4: Generate or use uploaded image
        if source_type == "user_uploaded":
            image_source = uploaded_image
        else:
            image_source, debug_path = generate_background_image(image_prompt)
        
        # Step 5: Compose final image with SMART TEXT OVERLAY
        final_image_bytes, final_path = compose_final_image(image_source, text_data, source_type)
        
        # Step 6: Return raw image file (SAME FORMAT AS BEFORE)
        log_debug("API_SUCCESS", f"Returning image file: {len(final_image_bytes)} bytes")
        
        # Return the image directly as file
        return send_file(
            final_path, 
            mimetype='image/jpeg',
            as_attachment=False,
            download_name='morning.png'
        )
        
    except Exception as e:
        log_debug("API_ERROR", f"Generate endpoint error: {e}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'debug_dir': DEBUG_DIR
        }), 500

@app.route('/generate-json', methods=['POST'])  
def generate_json():
    """Generate endpoint - returns JSON with base64 image and full debug info (ENHANCED)"""
    try:
        config = load_morning_config()
        log_debug("API_JSON_START", "Generate-json endpoint called with enhanced features")
        
        # Step 1: Parse input - handle both form data types (SAME AS BEFORE)
        prompt = None
        date = None
        custom_text = None
        style = None
        uploaded_image = None
        
        # Handle multipart form data
        if request.content_type and 'multipart/form-data' in request.content_type:
            prompt = request.form.get('prompt')
            date = request.form.get('date')
            custom_text = request.form.get('custom_text')
            style = request.form.get('style')
            
            if 'image' in request.files:
                image_file = request.files['image']
                if image_file and image_file.filename:
                    upload_path = os.path.join(DEBUG_DIR, f"uploaded_{dt.now().strftime('%H%M%S')}_{image_file.filename}")
                    image_file.save(upload_path)
                    uploaded_image = upload_path
        
        # Steps 2-5: Enhanced processing with Gemini
        text_data = generate_display_text(config, prompt, date, custom_text)
        image_prompt, source_type = build_image_prompt(config, text_data, uploaded_image, style)
        
        if source_type == "user_uploaded":
            image_source = uploaded_image
        else:
            image_source, debug_path = generate_background_image(image_prompt)
        
        final_image_bytes, final_path = compose_final_image(image_source, text_data, source_type)
        
        # Step 6: Return JSON with comprehensive debug info (ENHANCED SAVEPOINTS)
        final_image_b64 = base64.b64encode(final_image_bytes).decode('utf-8')
        
        result = {
            'status': 'success',
            'image_base64': final_image_b64,
            'mime_type': 'image/jpeg',
            'savepoints': {
                '1_input_parsing': {
                    'prompt': prompt,
                    'date': date,
                    'custom_text': custom_text,
                    'style': style,
                    'uploaded_image': uploaded_image is not None
                },
                '2_text_generation': text_data,
                '3_prompt_building': {
                    'image_prompt': image_prompt,
                    'source_type': source_type,
                    'generation_method': 'gemini_enhanced' if source_type == 'gemini_generated' else 'config_based'
                },
                '4_image_generation': {
                    'source_type': source_type,
                    'background_image_size': len(image_source) if isinstance(image_source, bytes) else 'uploaded_file'
                },
                '5_final_composition': {
                    'final_size_bytes': len(final_image_bytes),
                    'output_file': final_path,
                    'text_overlay_method': 'smart_generated'
                }
            },
            'debug_dir': DEBUG_DIR
        }
        
        log_debug("API_JSON_SUCCESS", "JSON response ready with enhanced savepoints", "final_response")
        return jsonify(result), 200
        
    except Exception as e:
        log_debug("API_JSON_ERROR", f"Generate-json endpoint error: {e}")
        traceback.print_exc()
        return jsonify({
            'status': 'error', 
            'message': str(e),
            'debug_dir': DEBUG_DIR,
            'traceback': traceback.format_exc()
        }), 500

@app.route('/generate-template', methods=['POST'])
def generate_template():
    """Template-based generation with JSON body (ENHANCED)"""
    try:
        config = load_morning_config()
        log_debug("TEMPLATE_START", "Generate-template endpoint called with enhanced features")
        
        # Parse JSON body
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Missing JSON body'}), 400
        
        template = data.get('template', 'countryside_landscape')
        custom_text = data.get('custom_text', '')
        
        log_debug("TEMPLATE_INPUT", {"template": template, "custom_text": custom_text})
        
        # Generate text data with enhanced logic
        text_data = generate_display_text(config, None, None, custom_text)
        
        # Use specific style template from config
        image_prompt, source_type = build_image_prompt(config, text_data, None, template)
        
        # Generate image
        image_source, debug_path = generate_background_image(image_prompt)
        final_image_bytes, final_path = compose_final_image(image_source, text_data, source_type)
        
        # Return JSON with debug info
        final_image_b64 = base64.b64encode(final_image_bytes).decode('utf-8')
        
        result = {
            'status': 'success',
            'template': template,
            'image_base64': final_image_b64,
            'mime_type': 'image/jpeg',
            'savepoints': {
                'generated_prompt': image_prompt,
                'text_data': text_data,
                'source_type': source_type,
                'final_size': len(final_image_bytes),
                'enhancement': 'gemini_powered'
            },
            'debug_dir': DEBUG_DIR
        }
        
        log_debug("TEMPLATE_SUCCESS", "Template generation complete with enhancements")
        return jsonify(result), 200
        
    except Exception as e:
        log_debug("TEMPLATE_ERROR", f"Template endpoint error: {e}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'debug_dir': DEBUG_DIR
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'morning-image-api',
        'version': '3.0.0-enhanced',
        'features': ['gemini_prompt_generation', 'smart_text_overlay', 'holiday_detection'],
        'debug_dir': DEBUG_DIR,
        'config_loaded': morning_config is not None,
        'timestamp': dt.now().isoformat()
    }), 200

@app.route('/debug', methods=['GET'])
def debug_info():
    """Debug information endpoint"""
    try:
        # List debug files
        debug_files = []
        if os.path.exists(DEBUG_DIR):
            for file in sorted(os.listdir(DEBUG_DIR))[-10:]:  # Last 10 files
                file_path = os.path.join(DEBUG_DIR, file)
                debug_files.append({
                    'name': file,
                    'size': os.path.getsize(file_path),
                    'modified': os.path.getmtime(file_path)
                })
        
        # Check font availability
        from src.utils.text_overlay import find_font, CANDIDATE_FONTS
        available_fonts = []
        for font_path in CANDIDATE_FONTS:
            if os.path.exists(font_path):
                available_fonts.append(font_path)
        
        font_info = {
            'candidate_fonts': CANDIDATE_FONTS,
            'available_fonts': available_fonts,
            'selected_font': find_font()
        }
        
        return jsonify({
            'debug_directory': DEBUG_DIR,
            'recent_files': debug_files,
            'config_loaded': morning_config is not None,
            'models_initialized': image_model is not None and text_model is not None,
            'enhancements': {
                'gemini_prompt_generation': True,
                'smart_blessing_text': True,
                'holiday_detection': True,
                'chinese_text_overlay': True
            },
            'font_info': font_info
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/files/<filename>', methods=['GET'])
def get_debug_file(filename):
    """Download debug files"""
    try:
        file_path = os.path.join(DEBUG_DIR, filename)
        if os.path.exists(file_path):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                return send_file(file_path, mimetype='image/jpeg')
            elif filename.endswith('.json'):
                return send_file(file_path, mimetype='application/json')
            else:
                return send_file(file_path, mimetype='text/plain')
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Load configuration on startup
    load_morning_config()
    log_debug("STARTUP", f"Server starting with enhanced Gemini features, debug directory: {DEBUG_DIR}")
    
    port = int(os.environ.get('PORT', 8081))
    app.run(host='0.0.0.0', port=port, debug=True)