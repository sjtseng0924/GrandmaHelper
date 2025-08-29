import os
import json
import sqlalchemy
from flask import Flask, request
from google.cloud.sql.connector import Connector, IPTypes
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

# Flask app
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
        model = GenerativeModel(model_name="gemini-2.0-flash")
        embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")
    return model, embedding_model

def get_embedding(text: str):
    _, embedding_model = get_models()
    embedding = embedding_model.get_embeddings([TextEmbeddingInput(text)])
    return embedding[0].values

def get_similar_conversations(query_vector):
    engine = get_db_engine()
    with engine.connect() as conn:
        query = sqlalchemy.text(
            "SELECT user_input, ai_response "
            "FROM conversations "
            "ORDER BY user_input_vector <-> CAST(:vec AS vector) LIMIT 3"
        )
        result = conn.execute(query, {"vec": str(query_vector)}).fetchall()
        return result


def insert_conversation(user_message, user_vector, ai_response, screen_info):
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text(
            "INSERT INTO conversations (user_input, user_input_vector, ai_response, screen_info, operation_success) "
            "VALUES (:u, :v, :a, :s, :op)"
        ), {
            "u": user_message,
            "v": str(user_vector),
            "a": ai_response,
            "s": json.dumps(screen_info),
            "op": False
        })
        conn.commit()


@app.route('/', methods=['POST'])
def handle_app_request():
    try:
        request_json = request.get_json(silent=True)
        if not request_json:
            return 'Invalid JSON format', 400

        user_message = request_json.get('user_message')
        screen_info = request_json.get('screen_info')

        if not user_message or not screen_info:
            return 'Missing required fields', 400

        user_vector = get_embedding(user_message)
        similar_conversations = get_similar_conversations(user_vector)
        rag_context = ""
        if similar_conversations:
            rag_context = "以下是相關的歷史對話，請參考：\n\n"
            for user_text, ai_text in similar_conversations:
                rag_context += f"使用者: {user_text}\nGemini: {ai_text}\n\n"

        prompt = f"""
        你是一個幫助年長者使用 LINE 的虛擬助手。
        請根據以下資訊判斷下一步的正確操作。

        使用者想做的事:{user_message}

        螢幕資訊:{json.dumps(screen_info, indent=2)}

        歷史操作資訊(做為參考):{rag_context}

        請只提供一句中文指示，指示下一步，簡短清楚，例如：「請點擊右下角的聊天按鈕。」
        """

        model, _ = get_models()
        response = model.generate_content(prompt) 
        ai_response = response.text
        insert_conversation(user_message, user_vector, ai_response, screen_info)

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