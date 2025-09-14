import os
import json
import base64
import random
from flask import Flask, request, jsonify
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from vertexai.preview.vision_models import ImageGenerationModel

app = Flask(__name__)

# Initialize Vertex AI
PROJECT_ID = "hackathon-468512"
LOCATION = "us-central1"
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Global variables
image_model = None
text_model = None
morning_config = None

def load_morning_config():
    """Load morning image configuration from JSON file"""
    global morning_config
    if morning_config is None:
        config_path = os.path.join(os.path.dirname(__file__), 'morning_image_config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                morning_config = json.load(f)
                print("Morning image configuration loaded successfully")
        except Exception as e:
            print(f"Error loading morning config: {e}")
            morning_config = {}
    return morning_config

def get_models():
    global image_model, text_model
    if image_model is None or text_model is None:
        image_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        text_model = GenerativeModel(model_name="gemini-2.5-flash")
    return image_model, text_model

@app.route('/generate-image', methods=['POST'])
def generate_image():
    """Generate image based on text prompt only"""
    try:
        request_data = request.get_json()
        if not request_data or 'prompt' not in request_data:
            return jsonify({
                'status': 'error',
                'message': 'Missing prompt parameter'
            }), 400
        
        prompt = request_data['prompt']
        number_of_images = request_data.get('number_of_images', 1)
        guidance_scale = request_data.get('guidance_scale', 20)
        safety_filter_level = request_data.get('safety_filter_level', 'block_few')
        
        image_model, _ = get_models()
        
        # Generate images
        images = image_model.generate_images(
            prompt=prompt,
            number_of_images=number_of_images,
            guidance_scale=guidance_scale,
            safety_filter_level=safety_filter_level
        )
        
        # Convert images to base64
        image_data = []
        for i, image in enumerate(images):
            image_bytes = image._image_bytes
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            image_data.append({
                'image_id': i + 1,
                'image_base64': image_b64,
                'mime_type': 'image/png'
            })
        
        return jsonify({
            'status': 'success',
            'prompt': prompt,
            'images': image_data,
            'count': len(image_data)
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Image generation error: {str(e)}'
        }), 500

@app.route('/prompt-test', methods=['POST'])
def prompt_test():
    """Quick prompt testing with optional image input - returns one image"""
    try:
        # Check if multipart form data (with files) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload + prompt
            prompt = request.form.get('prompt')
            if not prompt:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing prompt parameter'
                }), 400
            
            # Get uploaded images
            uploaded_files = []
            for key in request.files:
                file = request.files[key]
                if file and file.filename:
                    uploaded_files.append(file)
            
            if uploaded_files:
                # Use Gemini for image + text → descriptive text, then generate image
                _, text_model = get_models()
                
                # Process first uploaded image
                image_file = uploaded_files[0]
                image_bytes = image_file.read()
                mime_type = image_file.content_type or 'image/jpeg'
                
                # Create a more detailed prompt using Gemini vision
                vision_prompt = f"""
Analyze this image and enhance the following prompt for image generation: "{prompt}"

Create a detailed, descriptive prompt that:
1. Incorporates visual elements from the uploaded image
2. Enhances the user's original prompt
3. Adds specific visual details, lighting, style, and composition
4. Results in a prompt suitable for high-quality image generation

Return only the enhanced prompt, no explanations.
                """.strip()
                
                parts = [vision_prompt, Part.from_data(mime_type=mime_type, data=image_bytes)]
                response = text_model.generate_content(parts)
                enhanced_prompt = response.text.strip()
            else:
                enhanced_prompt = prompt
        
        else:
            # Handle JSON request (text only)
            request_data = request.get_json()
            if not request_data or 'prompt' not in request_data:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing prompt parameter'
                }), 400
            
            enhanced_prompt = request_data['prompt']
        
        # Generate one image using enhanced prompt
        image_model, _ = get_models()
        images = image_model.generate_images(
            prompt=enhanced_prompt,
            number_of_images=1,
            guidance_scale=20,
            safety_filter_level='block_few'
        )
        
        # Convert to base64
        if images:
            image_bytes = images[0]._image_bytes
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            return jsonify({
                'status': 'success',
                'original_prompt': prompt if 'prompt' in locals() else enhanced_prompt,
                'enhanced_prompt': enhanced_prompt,
                'had_input_image': len(uploaded_files) > 0 if 'uploaded_files' in locals() else False,
                'image_base64': image_b64,
                'mime_type': 'image/png'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'No image generated'
            }), 500
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Prompt testing error: {str(e)}'
        }), 500

@app.route('/enhance-prompt', methods=['POST'])
def enhance_prompt():
    """Enhance user prompt using Gemini for better image generation"""
    try:
        request_data = request.get_json()
        if not request_data or 'prompt' not in request_data:
            return jsonify({
                'status': 'error',
                'message': 'Missing prompt parameter'
            }), 400
        
        user_prompt = request_data['prompt']
        style = request_data.get('style', 'realistic')
        
        _, text_model = get_models()
        
        enhancement_prompt = f"""
You are a prompt engineer specializing in image generation. 
Enhance the following user prompt to create better, more detailed image generation prompts.

User prompt: {user_prompt}
Style preference: {style}

Please enhance this prompt by:
1. Adding relevant visual details
2. Specifying composition and lighting
3. Including style descriptors
4. Ensuring clarity and specificity

Return only the enhanced prompt, no explanations.
        """.strip()
        
        response = text_model.generate_content(enhancement_prompt)
        enhanced_prompt = response.text.strip()
        
        return jsonify({
            'status': 'success',
            'original_prompt': user_prompt,
            'enhanced_prompt': enhanced_prompt,
            'style': style
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Prompt enhancement error: {str(e)}'
        }), 500

@app.route('/test-prompts', methods=['POST'])
def test_prompts():
    """Test multiple variations of a prompt"""
    try:
        request_data = request.get_json()
        if not request_data or 'base_prompt' not in request_data:
            return jsonify({
                'status': 'error',
                'message': 'Missing base_prompt parameter'
            }), 400
        
        base_prompt = request_data['base_prompt']
        variations = request_data.get('variations', 3)
        
        _, text_model = get_models()
        
        # Generate prompt variations
        variation_prompt = f"""
Create {variations} different variations of this image generation prompt: {base_prompt}

Each variation should:
- Maintain the core concept
- Add different styling approaches
- Use different descriptive words
- Vary the composition or perspective

Return the variations as a numbered list, one per line.
        """.strip()
        
        response = text_model.generate_content(variation_prompt)
        variations_text = response.text.strip()
        
        # Parse variations
        variation_list = []
        for line in variations_text.split('\n'):
            if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith('-')):
                # Remove numbering/bullets
                clean_line = line.strip()
                if clean_line[0].isdigit():
                    clean_line = clean_line.split('.', 1)[1].strip()
                elif clean_line.startswith('-'):
                    clean_line = clean_line[1:].strip()
                variation_list.append(clean_line)
        
        return jsonify({
            'status': 'success',
            'base_prompt': base_prompt,
            'variations': variation_list,
            'count': len(variation_list)
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Prompt testing error: {str(e)}'
        }), 500

@app.route('/generate', methods=['POST'])
def generate_morning_image():
    """Generate morning greeting image using configuration templates"""
    try:
        config = load_morning_config()
        if not config:
            return jsonify({
                'status': 'error',
                'message': 'Configuration not loaded'
            }), 500
        
        # Handle both JSON and form data
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict()
        
        # Extract parameters
        festival = data.get('festival', '')
        custom_blessing = data.get('blessing', '')
        style = data.get('style', 'countryside_landscape')
        
        # Build prompt using configuration
        prompt = build_morning_prompt(config, festival, custom_blessing, style)
        negative_prompt = config.get('prompt_templates', {}).get('negative_prompt', '')
        
        # Generate image
        image_model, _ = get_models()
        images = image_model.generate_images(
            prompt=prompt,
            number_of_images=1,
            guidance_scale=20,
            safety_filter_level='block_few',
            negative_prompt=negative_prompt if negative_prompt else None
        )
        
        if images:
            image_bytes = images[0]._image_bytes
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            return jsonify({
                'status': 'success',
                'festival': festival,
                'style': style,
                'prompt_used': prompt,
                'image_base64': image_b64,
                'mime_type': 'image/png'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'No image generated'
            }), 500
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Morning image generation error: {str(e)}'
        }), 500

def build_morning_prompt(config, festival, custom_blessing, style):
    """Build morning image prompt using configuration templates"""
    try:
        # Get main template
        main_template = config.get('prompt_templates', {}).get('main_template', '')
        
        # Determine festival/solar term info
        festival_info = None
        if festival:
            festival_info = (config.get('solar_terms', {}).get(festival) or 
                           config.get('holidays', {}).get(festival))
        
        # Get blessing phrase
        if not custom_blessing:
            blessing_phrases = config.get('blessing_phrases', [])
            custom_blessing = random.choice(blessing_phrases) if blessing_phrases else "早安你好，祝你幸福安康"
        
        # Get style template
        style_templates = config.get('image_styles', {})
        if style in style_templates:
            style_template = style_templates[style].get('template', '')
            # Use style template if available, otherwise use main template
            if style_template:
                return style_template.format(
                    節氣=festival or "早安",
                    祝福短句=custom_blessing
                )
        
        # Fallback to main template
        if festival_info:
            elements = festival_info.get('elements', '晨光、自然')
            colors = festival_info.get('colors', '溫暖金黃')
            blessing = festival_info.get('blessing', custom_blessing)
            
            return main_template.format(
                節氣=festival,
                季節意象與地景=elements,
                主物件=elements.split('、')[0] if elements else '花朵',
                祝福短句=blessing,
                配色建議=colors,
                比例="16:9"
            )
        else:
            # Generic morning image
            return f"生成一張溫馨的早安祝福圖片，台灣風格，清晨氛圍。主要文字：『早安』和『{custom_blessing}』。金色晨光，柔和色調，乾淨背景。16:9比例。"
    
    except Exception as e:
        print(f"Error building prompt: {e}")
        return f"Generate a warm morning greeting image with text: Good Morning, {custom_blessing}"

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'image-generation-api',
        'version': '1.0.0'
    }), 200

if __name__ == '__main__':
    # Load configuration on startup
    load_morning_config()
    
    port = int(os.environ.get('PORT', 8081))
    app.run(host='0.0.0.0', port=port, debug=True)