import vertexai
from vertexai.generative_models import GenerativeModel
from datetime import datetime as dt
import random

# ======== Initialize Vertex AI ========
PROJECT_ID = "hackathon-468512"
LOCATION = "us-central1"
vertexai.init(project=PROJECT_ID, location=LOCATION)

# ======== Load Gemini text model ========
text_model = GenerativeModel(model_name="gemini-2.5-flash")

# ======== Holiday mapping (optional) ========
HOLIDAY_MAP = {
    "12-25": "聖誕節",
    "1-1": "元旦",
    "2-14": "情人節",
    "5-1": "勞動節",
    "10-10": "雙十節"
}

def detect_holiday(date=None):
    if not date:
        date = dt.now().strftime("%Y-%m-%d")
    m, d = date.split("-")[1:]
    return HOLIDAY_MAP.get(f"{int(m)}-{int(d)}", None)

# ======== Step 1: Generate English image prompt ========
def generate_image_prompt(user_input=None, holiday=None):
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

# ======== Step 2: Generate blessing text in Chinese ========
def generate_blessing(user_input=None, image_prompt=None, holiday=None):
    if not image_prompt:
        raise ValueError("image_prompt required to generate blessing")

    system_prompt = f"""
我有以下資訊：
- 用戶輸入: {user_input or '無'}
- 圖片描述: {image_prompt}
- 節日: {holiday or '無'}

請生成一句中文祝福語，用於圖片上方。
要求：不超過8個字、貼近節日或主題，如果沒有特定節日，生成通用"繁體中文"祝福。
只輸出祝福文字，不要其他描述。
    """.strip()

    response = text_model.generate_content(system_prompt)
    return response.text.strip()

# ======== Demo interface ========
if __name__ == "__main__":
    user_input = input("請輸入主題或祝福描述（留空隨機生成）: ").strip() or None
    date = None
    holiday = detect_holiday(date)

    print(f"[INFO] 偵測到節日: {holiday}")

    img_prompt = generate_image_prompt(user_input, holiday)
    print(f"\n[IMAGE PROMPT (ENGLISH)]\n{img_prompt}")

    blessing = generate_blessing(user_input, img_prompt, holiday)
    print(f"\n[BLESSING TEXT (CHINESE)]\n{blessing}")
