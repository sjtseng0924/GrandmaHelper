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

# Search functionality toggle
ENABLE_SEARCH = os.environ.get('ENABLE_SEARCH', 'true').lower() == 'true'

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
            "s": json.dumps(screen_info) if isinstance(screen_info, (dict, list)) else str(screen_info or ""),
            "g": goal
        })
        conn.commit()


def search_line_help(query, num_results=5):
    """Search LINE help documentation using Custom Search API"""
    if not ENABLE_SEARCH:
        return []
        
    API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
    SEARCH_ENGINE_ID = "44e73185ae7344428"
    if not API_KEY:
        print("Warning: GOOGLE_SEARCH_API_KEY not found in environment variables")
        return []
    
    try:
        service = build("customsearch", "v1", developerKey=API_KEY)
        result = service.cse().list(
            q=query,
            cx=SEARCH_ENGINE_ID,
            num=num_results,
            hl='zh-TW' 
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
                meta = json.loads(meta_file.read().decode('utf-8'))  
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

        # Search LINE help documentation if enabled
        search_context = ""
        if ENABLE_SEARCH:
            search_results = search_line_help(user_message + " " + current_goal)
            if search_results:
                search_context = "\n\n參考資料（來自LINE官方說明文件）：\n"
                for result in search_results:
                    search_context += f"- {result['title']}: {result['snippet']}\n  連結：{result['link']}\n\n"

        prompt = f"""
#預設
你是一個手機App使用助手，幫助不太會使用手機的老年人達成他們想要的目標，主要應用於LINE，也可以使用於其他軟體。

# Task
依據「最終目標」與當前畫面，產生**下一個單一步驟**的操作指示，讓使用者更接近目標。
若已達成完成判定，請只回覆「恭喜成功！」。

# Inputs   
- 最終目標: {current_goal}
- 使用者訊息: {user_message}

#Line使用手冊
{search_context}

# 歷史參考（不可靠，僅供靈感）
{rag_context}

# 判定流程
1) 完成判定：
   - 若已達成目標或當前畫面為最後一步 → 請「只回覆」：恭喜成功！
2) 意圖檢查（不完整意圖直出固定句）：
   - 定義：完整意圖 = 同時包含「行動」與「對象/目標」的請求（例：傳貼圖給小明、把照片傳給孫子、傳文字訊息給兒子）。
   - 不完整意圖 = 寒暄/單詞/閒聊/不明確（例：你好、嗨、傳、兒子、OK、在嗎）。
   - 若判定為不完整意圖 → 請「只回覆」：您的輸入沒有明確目的，請告訴我您想要做到的事情喔!
3) 守門條款（與畫面操作無關）：
   - 若問題與手機畫面操作無關 → 請「只回覆」：我是一個APP助手，請提出相關的要求。
4) 產生下一步（僅在 1/2/3 未觸發時執行）：
   - 依「Constraints」規則輸出**單一步驟**的可操作指示。

# Constraints
1) 僅提供**一行**中文、口語化、可操作的「單一步驟」指示，務必描述元素位置（例：「請點擊右下角的笑臉圖示」）。
2) 按鈕詞彙對照（固定用語，**禁止**直接引用螢幕顯示文字）：
   - 「選擇貼圖及表情貼」→「笑臉圖示」
   - 「附加選單」→「+ 號」
   - 「相機」→「相機圖案」
   - 「照片和影片」→「圖片圖案」
   - 「語音訊息」→「麥克風圖案」
   - 聊天頁右上角四個無名圖示（右→左）：
     三個點＝「更多」、聊天泡泡＝「創建聊天/群組/會議」、方形＝「社群」、資料夾＝「所有相簿」
   - **務必**描述位置，包含左/右/中間+上/下/中間（如「右上角」「上方中間」「螢幕中間區域」），不要以數字描述(如右邊數來第三個)。
   - 若同時存在畫面文案與口語固定說法，**一律**採用口語固定說法。
3) 若元素已為 selected，視為已點擊，勿重複指示。
4) **請完全相信並高度依照「Line使用手冊」的內容來指引使用者。**
5) 僅允許以下四種輸出其一：
   a. 下一步指示（單行）
   b. 恭喜成功！
   c. 您的輸入沒有明確目的，請告訴我您想要做到的事情喔!
   d. 我是一個APP助手，請提出相關的要求。
6) **禁止**加入任何表情符號。
7) 如果使用者要進行傳訊息、打電話等在LINE中可以達到的動作，請預設使用者要使用LINE。
8) 如果使用者目前的所在的畫面/APP無法達成動作，請指引使用者回到主畫面，再指引使用者進入正確的APP。
9) 如果使用者指定的動作對象不在螢幕裡面，例如「我想打電話給兒子」，請回復類似於「請點擊您兒子的聊天框」，不需詢問使用者他的正確名稱。
10) 在拍照/錄影時，請稱呼拍照/錄影的按鈕為「圓形拍照/錄影按鈕」，不要稱呼其為截圖按鈕。

# Output
僅一行文字（或僅「恭喜成功！」），不要加前後綴說明，絕對不要有表情符號(emoji)。
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
    if not ENABLE_SEARCH:
        return json.dumps({"status": "error", "message": "Search functionality is disabled"}), 400
        
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
            'count': len(results),
            'search_enabled': ENABLE_SEARCH
        }, ensure_ascii=False), 200, {'Content-Type': 'application/json'}
        
    except Exception as e:
        return json.dumps({
            'status': 'error', 
            'message': str(e)
        }), 500, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
