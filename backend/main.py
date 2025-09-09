import os
import json
import sqlalchemy
from flask import Flask, request
from google.cloud.sql.connector import Connector, IPTypes
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.generative_models import Part
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

app = Flask(__name__)

connector = None
engine = None
model = None
embedding_model = None

def get_db_engine():
    global connector, engine
    if engine is None:
        DB_USER = os.environ.get("DB_USER")
        DB_PASS = os.environ.get("DB_PASS")
        DB_NAME = os.environ.get("DB_NAME")
        INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")

        connector = Connector()
        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=lambda: connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASS,
                db=DB_NAME,
                ip_type=IPTypes.PUBLIC
            )
        )
    return engine


def get_models():
    global model, embedding_model
    if model is None or embedding_model is None:
        PROJECT_ID = "hackathon-468512"
        LOCATION = "us-central1"
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel(model_name="gemini-2.5-flash")
        embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")
    return model, embedding_model

def get_embedding(text: str):
    _, embedding_model = get_models()
    embedding = embedding_model.get_embeddings([TextEmbeddingInput(text)])
    return embedding[0].values

def get_similar_conversations(query_vector, goal):
    engine = get_db_engine()
    with engine.connect() as conn:
        query = sqlalchemy.text(
            "SELECT user_input, ai_response "
            "FROM conversations "
            "WHERE goal = :goal_val "
            "ORDER BY user_input_vector <-> CAST(:vec AS vector) LIMIT 3"
        )
        result = list(conn.execute(query, {"vec": str(query_vector), "goal_val": goal}))
        return result


def insert_conversation(user_message, user_vector, ai_response, screen_info, goal):
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text(
            "INSERT INTO conversations (user_input, user_input_vector, ai_response, screen_info, goal) "
            "VALUES (:u, :v, :a, :s, :g)"
        ), {
            "u": user_message,
            "v": str(user_vector),
            "a": ai_response,
            "s": json.dumps(screen_info) if isinstance(screen_info, (dict, list)) else str(screen_info),
            "g": goal
        })
        conn.commit()


@app.route('/', methods=['POST'])
def handle_app_request():
    try:
        request_json = request.get_json(silent=True)
        file_storage = request.files.get('file') if 'file' in request.files else None
        meta_file = request.files.get('metadata') 

        user_message = None
        screen_info = None
        current_goal = '初始目標'

        if request_json:
            user_message = request_json.get('user_message')
            screen_info = request_json.get('screen_info')
            current_goal = request_json.get('goal', '初始目標')

        elif meta_file:
            try:
                meta = json.loads(meta_file.read().decode('utf-8'))  # NEW
            except Exception:
                return 'Invalid metadata JSON', 400
            user_message = meta.get('user_message')
            screen_info = meta.get('screen_info')
            current_goal = meta.get('goal', '初始目標')

        else:
            user_message = request.form.get('user_message')
            current_goal = request.form.get('goal', '初始目標')
            raw = request.form.get('screen_info')
            if raw:
                try:
                    screen_info = json.loads(raw)
                except Exception:
                    screen_info = raw 
            if not file_storage and not user_message:
                return 'Invalid JSON or multipart form data', 400

        if not user_message:
            return 'Missing required fields: user_message', 400
        if not file_storage and screen_info is None:
            return 'Missing screen image or screen_info', 400

        user_vector = get_embedding(user_message)
        similar_conversations = get_similar_conversations(user_vector, current_goal)
        rag_context = ""
        if similar_conversations:
            rag_context = "以下是相關的歷史對話，請參考：\n\n"
            for user_text, ai_text in similar_conversations:
                rag_context += f"使用者: {user_text}\nGemini: {ai_text}\n\n"

        prompt = f"""
        # Task
        依據「最終目標」與當前畫面，產生**下一個單一步驟**的操作指示，讓使用者更接近目標。
        若已達成完成判定，請只回覆「恭喜成功！」。

        # Inputs
        - 最終目標: {current_goal}
        - 使用者訊息: {user_message}


        # 歷史參考（不可靠，僅供靈感）
        {rag_context}

        # Constraints
        1) 僅提供一行中文、口語化、可操作的「單一步驟」指示，務必描述元素位置（例：「請點擊右下角的笑臉圖示」）。
        2) 請使用下列固定用語及規則來描述按鈕，禁止直接引用螢幕顯示文字當作回覆：
            - 螢幕元素「選擇貼圖及表情貼」→ 口語固定說法：「笑臉圖示」
            - 螢幕元素「附加選單」→ 口語固定說法：「 + 號」
            - 螢幕元素「相機」→ 口語固定說法：「相機圖案」
            - 螢幕元素「照片和影片」→ 口語固定說法：「圖片圖案」
            - 螢幕元素「語音訊息」→ 口語固定說法：「麥克風圖案」
            - 使用者選擇聊天頁面時，右上角會有四個沒有名稱的圖示，從右到左分別是圖示為三個點的「更多」、圖示為聊天泡泡的「創建聊天/群組/會議」、圖示為方形的「社群」、圖示為資料夾的「所有相簿」，請仔細對照並回答。
            請**務必**描述按鈕的位置，例如「請點擊右下角的笑臉圖示」、「請點擊螢幕中間區域的聊天視窗」。
            若同時存在畫面文案與口語固定說法，**一律**採用口語固定說法做回覆。
        3) 若元素已為 selected，視為已點擊，勿重複指示。
        4) 若完成條件成立或當前畫面是最後一步，請「只回覆」：恭喜成功！
        5) 若問題與畫面操作無關，回覆守門條款固定句。
        6) 若無法理解使用者表達，先進行意圖確認邏輯（見系統指令），再依結果行動。

        # Output
        - 僅一行文字（或僅「恭喜成功！」），不要加前後綴說明。
        """.strip()

        if not file_storage and screen_info is not None:
            prompt += f"\n\n螢幕資訊:{json.dumps(screen_info, ensure_ascii=False, indent=2)}\n"

        model, _ = get_models()

        if file_storage:
            image_bytes = file_storage.read()
            filename = (file_storage.filename or "").lower()
            mime = "image/jpeg" if filename.endswith((".jpg", ".jpeg")) else "image/png"
            parts = [prompt, Part.from_data(mime_type=mime, data=image_bytes)]
            response = model.generate_content(parts)
        else:
            response = model.generate_content(prompt)

        ai_response = response.text
        insert_conversation(
            user_message,
            user_vector,
            ai_response,
            screen_info if screen_info is not None else "IMAGE_UPLOADED",
            current_goal
        )

        response_data = {
            'status': 'success',
            'message': ai_response
        }
        return json.dumps(response_data, ensure_ascii=False), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        error_message = f"與服務或 Gemini 溝通時發生錯誤：{e}"
        return json.dumps({"status": "error", "message": error_message}), 500, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
