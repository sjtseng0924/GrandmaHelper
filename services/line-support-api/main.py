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
            "SELECT user_input, ai_response,screen_info "
            "FROM conversations "
            "WHERE goal = :goal_val "
            "ORDER BY user_input_vector <-> CAST(:vec AS vector) LIMIT 5"
        )
        result = list(conn.execute(query, {"vec": str(query_vector), "goal_val": goal}))
        return result

def get_last_conversation(goal, id_window=10, allow_cross_goal_fallback=False):
    engine = get_db_engine()
    with engine.connect() as conn:
        max_id_row = conn.execute(sqlalchemy.text("SELECT COALESCE(MAX(id), 0) FROM conversations")).scalar()
        lower_bound_id = max(0, (max_id_row or 0) - id_window)

        q_same_goal = sqlalchemy.text(
            "SELECT user_input, ai_response, screen_info "
            "FROM conversations "
            "WHERE goal = :goal_val "
            "  AND id >= :lower_id "
            "ORDER BY id DESC "
            "LIMIT 1"
        )
        row = conn.execute(q_same_goal, {"goal_val": goal, "lower_id": lower_bound_id}).fetchone()
        if row:
            return row

        return None




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
            for user_text, ai_text, hist_screen_info in similar_conversations:
                rag_context += f"使用者: {user_text}\nGemini: {ai_text}\nscreen_info:{hist_screen_info}\n\n"

         
        last_row = get_last_conversation(current_goal, id_window=10, allow_cross_goal_fallback=False)

        last_conversation = ""
        if last_row:
            last_user, last_ai, last_screen = last_row
            try:
                last_screen_pretty = json.dumps(
                    last_screen if isinstance(last_screen, (dict, list)) else json.loads(last_screen),
                    ensure_ascii=False, indent=2
                )
            except Exception:
                last_screen_pretty = str(last_screen)
            last_conversation = f"上一次的指示：{last_ai}\n上一次的螢幕資訊：\n{last_screen_pretty}"
        else:
            last_conversation = "（無可用的上一筆畫面可供比較）"

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
你是一個手機App使用助手，幫助不太會使用手機的老年人達成他們想要的目標，主要應用於LINE和BubbleAssistant，也可以使用於其他軟體。

# Task
依據「最終目標」與當前畫面，產生**下一個單一步驟**的操作指示，讓使用者更接近目標。
若和上一次的螢幕資訊比較，已達成完成判定，請只回覆「恭喜成功！」。

# Inputs   
- 最終目標: {current_goal}
- 使用者訊息: {user_message}

# Line使用手冊
{search_context}

# 上一次的螢幕資訊
{last_conversation}

# 歷史參考（不可靠，僅供靈感）
{rag_context}

# 判定流程
1) 完成判定：
   - 比對當前的螢幕資訊及上一次的螢幕資訊，如果已經達成目標 → 請「只回覆」：恭喜成功！
2) 意圖檢查（不完整意圖直出固定句）：
   - 定義：完整意圖 = 包含「行動」的請求（例：傳貼圖給小明、把照片傳給孫子、買貼圖）。
   - ***不完整意圖 = 寒暄/單詞/閒聊/不明確（例：你好、嗨、傳、兒子、OK、在嗎）。***
   - ***若判定為不完整意圖 → 請「只回覆」：您的輸入沒有明確目的，請告訴我您想要做到的事情喔!***
3) 守門條款（與畫面操作無關）：
   - 若問題與手機畫面操作無關 → 請「只回覆」：我是一個APP助手，請提出相關的要求。
4) 產生下一步（僅在 1/2/3 未觸發時執行）：
   - 依「Constraints」規則輸出**單一步驟**的可操作指示，請比對當前的螢幕資訊及上一次的螢幕資訊，理解使用者是否已完成動作。

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
   - 請將「進入抽屜模式」替換成「上滑查看更多APP」。
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
9) ***對象名稱規則***：

若使用者或最終目標中的對象是親屬稱謂（例：兒子、女兒、孫女、媽媽、爸爸、外婆、阿姨…），視為不完整對象名稱。

這種情況不要回覆「您的輸入沒有明確目的…」，而是直接產生下一步：「請在上方中間的搜尋欄位輸入該人的名字（而不是親屬稱謂）」。

若使用者已提供具體名字（例：小明、王小美），則以該名字進行搜尋或點擊指引。

範例（僅示意，不要直接輸出引號）：

目標「打電話給孫女」→「請點擊上方中間的搜尋欄位，輸入您孫女的名字。」（若畫面已有孫女聊天框則直接指引點擊）

目標「傳貼圖給兒子」→「請點擊上方中間的搜尋欄位，輸入您兒子的名字。」（若畫面已有兒子聊天框則直接指引點擊）

目標「傳貼圖給小明」→「請點擊上方中間的搜尋欄位，輸入『小明』。」（若畫面已有小明聊天框則直接指引點擊）

10) 在拍照/錄影時，請稱呼拍照/錄影的按鈕為「圓形拍照/錄影按鈕」，不要稱呼其為截圖按鈕。
11) 請仔細比對**上一次的螢幕資訊**和**當前的螢幕資訊**，以他們的不同之處來推斷使用者做了什麼事情，
    例如螢幕資訊中有一個區塊 clickable @(33,1336,77x99)\n • \"\" [id=chat_ui_message_edit] <EditText>，
    如果變成clickable @(33,1336,77x99)\n • \"早安\" [id=chat_ui_message_edit] <EditText> ，
    就代表使用者在輸入框內輸入了早安，以此來結合上一次的螢幕資訊中的ai_response，即可判斷使用者有沒有成功完成。
12) 如果要請使用者返回請說「請點擊螢幕右下角的返回按鈕」、回到主畫面請說請點擊螢幕下方中間的主頁按鈕」。
13) BubbleAssistant中有生成並下載早安圖的功能，如果要生成圖片請使用者點擊輸入框，輸入想要生成的主題，並點擊生成，再點擊存到相簿(圖片會存到相簿)，即可請使用者回到主畫面並打開Line，進行後續的傳送圖片操作。
14) 傳送圖片的操作:請說「請選擇您想要傳送的照片」，而不是「選擇第一張照片」，而監控到使用者已經選擇至少一張照片後，請使用者點擊在螢幕右下角或是螢幕中間右側(視實際情況決定)的「紙飛機圖案」的傳送鍵。
15) 如果在聊天室的監控資訊中有"分享" [id=chat_ui_row_message_share_button] <ImageView> ，代表那是一張圖片。
16) 買貼圖或是傳貼圖的操作:請說「請選擇您想要購買/傳送的貼圖」，不要較使用者選擇第一個貼圖。
17) 當目標是打電話時可以請使用者點擊語音通話，如果要視訊可以點擊視訊通話。
# Output
僅一行文字（或僅「恭喜成功！」），不要加前後綴說明，絕對不要有表情符號(emoji)。
""".strip()

        if not file_storage and screen_info is not None:
            prompt += f"\n\n當前的螢幕資訊:{json.dumps(screen_info, ensure_ascii=False, indent=2)}\n"

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
