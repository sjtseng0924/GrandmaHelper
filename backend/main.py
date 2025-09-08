import os
import json
import sqlalchemy
from flask import Flask, request
from google.cloud.sql.connector import Connector, IPTypes
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.generative_models import Part
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
from googleapiclient.discovery import build

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


def search_line_help(query, num_results=5):
    """Search LINE help documentation using Custom Search API"""
    API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
    SEARCH_ENGINE_ID = "44e73185ae7344428"  # Your provided search engine ID
    
    if not API_KEY:
        print("Warning: GOOGLE_SEARCH_API_KEY not found in environment variables")
        return []
    
    try:
        service = build("customsearch", "v1", developerKey=API_KEY)
        result = service.cse().list(
            q=query,
            cx=SEARCH_ENGINE_ID,
            num=num_results,
            hl='zh-TW'  # Set language to Traditional Chinese
        ).execute()
        
        search_results = []
        for item in result.get('items', []):
            search_results.append({
                'title': item.get('title'),
                'link': item.get('link'),
                'snippet': item.get('snippet'),
                'displayLink': item.get('displayLink')
            })
        
        return search_results
    except Exception as e:
        print(f"Search error: {e}")
        return []


@app.route('/', methods=['POST'])
def handle_app_request():
    try:
        request_json = request.get_json(silent=True)
        file_storage = request.files.get('file') if 'file' in request.files else None
        meta_file = request.files.get('metadata')  # NEW

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

        # Always search LINE help documentation since service is only for LINE usage
        search_results = search_line_help(user_message + " " + current_goal)
        search_context = ""
        if search_results:
            search_context = "\n\n參考資料（來自LINE官方說明文件）：\n"
            for result in search_results:
                search_context += f"- {result['title']}: {result['snippet']}\n  連結：{result['link']}\n\n"

        prompt = f"""
        你是一個幫助年長者使用LINE手機APP的虛擬助手，你的首要任務是協助使用者達成「最終目標」。

        請根據以下資訊判斷下一步的正確操作。

        最終目標: {current_goal}

        使用者訊息: {user_message}

        歷史操作資訊(做為參考，請不要過於依賴，請當作非常不確定的參考):{rag_context}{search_context}

        規則：
        1. 你必須優先依照「最終目標」判斷，而不是使用者訊息。
        2. 如果最終目標是「什麼也不做」，代表已經達成目標，請直接單獨回覆「恭喜成功！」，不要將「恭喜成功！」接在其他句子後面或是前面。
        3. 一些常見的操作指引:
            -如果螢幕資訊中包含「選擇貼圖及表情貼」，且使用者想要傳送貼圖，請使用者點擊位於螢幕下方，文字輸入框旁邊的笑臉圖示。
            -如果螢幕資訊中包含「附加選單」，且需要使用附加選單中的功能，請使用者點擊左下角的+號。
            -如果螢幕資訊中包含「相機」，且使用者想要拍照、傳送照片，請使用者點擊左下角的相機圖案(位於+號右邊)。
            -如果螢幕資訊中包含「照片和影片」，且使用者想要傳送照片或是影片，請使用者點擊位於螢幕下方，文字輸入框旁邊的圖片圖案(位於相機圖案右邊)。
            -如果螢幕資訊中包含「語音訊息」，且使用者想要傳送語音訊息，請使用者點擊螢幕右下角的麥克風圖案(位於笑臉右邊)。
        4. 如果按鈕/選修被標為 selected ，請視為使用者已點擊此按鈕/選修。
        5. 判斷任務是否達成：
            - 如果「最終目標」是買貼圖，且螢幕上顯示「購買」或「確定」按鈕，請回覆「恭喜成功！」。
            - 如果「最終目標」是傳送照片，且螢幕上顯示「傳送」或「發送」按鈕，請回覆「恭喜成功！」。
            - 如果「最終目標」是傳送訊息，且螢幕上顯示「傳送」或「發送」按鈕，請回覆「恭喜成功！」。
            - 如果你判斷當前畫面已經是完成任務的最後一步，請直接單獨回覆「恭喜成功！」，不要將「恭喜成功！」接在其他句子後面或是前面。
        6. 如果問題與畫面無關，請回覆「抱歉，我無法回答這個問題，我是個只會操作手機的助手。」。
        7. 如果使用者的表達你無法理解，請猜測使用者的意圖並詢問使用者，是否是「{current_goal}」，
            -如果使用者回答是，請依照當前目標繼續指示使用者操作。
            -如果使用者回答不是，請回覆「抱歉，我無法理解你的意思，請重新說明你的問題。」。
        8. 其他情況下，請只提供一句易於理解且口語化的中文指示，簡短清楚，例如：「請點擊右下角的聊天按鈕。」。
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


@app.route('/search', methods=['POST'])
def search_endpoint():
    """Custom search endpoint for testing LINE help documentation search"""
    try:
        request_json = request.get_json(silent=True)
        if not request_json or 'query' not in request_json:
            return json.dumps({"status": "error", "message": "Missing query parameter"}), 400
        
        query = request_json['query']
        results = search_line_help(query)
        
        return json.dumps({
            'status': 'success',
            'query': query,
            'results': results,
            'count': len(results)
        }, ensure_ascii=False), 200, {'Content-Type': 'application/json'}
        
    except Exception as e:
        return json.dumps({
            'status': 'error', 
            'message': str(e)
        }), 500, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
