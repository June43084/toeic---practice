from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth
import random
import logging
import os
from google.api_core.exceptions import GoogleAPICallError
from logging.handlers import RotatingFileHandler
from google.cloud.firestore import FieldFilter

app = Flask(__name__)

# 確保日誌目錄存在
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 設定日誌格式
log_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(module)s - %(lineno)d - %(message)s')

# 設定檔案日誌處理器
file_handler = RotatingFileHandler(os.path.join(log_dir, 'app.log'),
                                  maxBytes=1024 * 1024,
                                  backupCount=7)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.ERROR)

# 設定控制台日誌處理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# 取得 logger 並添加處理器
logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

load_dotenv()

# Firebase 初始化
try:
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if not cred_path:
        logger.critical("FIREBASE_CREDENTIALS_PATH 環境變數未設定！", exc_info=True)
        raise EnvironmentError("缺少環境變數：FIREBASE_CREDENTIALS_PATH")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("Firebase 初始化成功 (使用 .env 檔案)")
except Exception as e:
    logger.critical(f"Firebase 初始化失敗: {str(e)}", exc_info=True)
    raise

# 驗證使用者身份
def verify_user(token):
    try:
        decoded_token = auth.verify_id_token(token, clock_skew_seconds=30)
        return decoded_token['uid']
    except Exception as e:
        logger.error(f"驗證使用者失敗: {str(e)}", exc_info=True)
        return None

# 統一 token 提取邏輯
def request_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({"success": False, "message": "未提供身份驗證令牌！"}), 401
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "message": "身份驗證標頭格式錯誤！"}), 401
    token = auth_header.split(' ')[1]
    uid = verify_user(token)
    if not uid:
        return jsonify({"success": False, "message": "身份驗證失敗！"}), 401
    return uid

# 載入單字
def load_words(uid, is_unfamiliar=None):
    try:
        query = db.collection("toeic_words").where(filter=FieldFilter("user_id", "==", uid))
        if is_unfamiliar is not None:
            query = query.where(filter=FieldFilter("is_unfamiliar", "==", is_unfamiliar))
        words = [{
            "id": doc.id,
            "word": doc.to_dict().get("word", ""),
            "is_unfamiliar": doc.to_dict().get("is_unfamiliar", False)
        } for doc in query.stream()]
        logger.info(f"載入使用者 {uid} 的單字完成，數量: {len(words)}, 不熟單字模式: {is_unfamiliar}")
        return words
    except GoogleAPICallError as e:
        logger.error(f"Firestore 資料庫錯誤: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.critical(f"系統未預期錯誤: {e}", exc_info=True)
        raise

# 主頁
@app.route('/')
def index():
    return render_template('index.html')

# 儲存單字
@app.route('/save_word', methods=['POST'])
def save_word():
    uid = request_token()
    if not isinstance(uid, str):
        return uid
    if not request.form or 'word' not in request.form:
        return jsonify({'message': '請求格式錯誤'}), 400
    try:
        existing_words = [w["word"] for w in load_words(uid)]
        word = request.form['word'].strip()
        if word in existing_words:
            return jsonify({'message': '單字已存在', 'success': False}), 409
        new_word = {
            "user_id": uid,
            "word": word,
            "is_unfamiliar": False
        }
        db.collection("toeic_words").add(new_word)
        return jsonify({'message': '單字儲存成功', 'success': True}), 201
    except Exception as e:
        logger.error(f"儲存單字失敗: {e}")
        return jsonify({'message': '儲存單字失敗', 'success': False}), 500

# 刪除單字
@app.route('/delete_word', methods=['POST'])
def delete_word():
    uid = request_token()
    if not isinstance(uid, str):
        return uid
    word = request.form['word'].strip()
    if not word:
        return jsonify({"success": False, "message": "請輸入要刪除的單字！"})
    try:
        query = (db.collection("toeic_words")
                 .where(filter=FieldFilter("user_id", "==", uid))
                 .where(filter=FieldFilter("word", "==", word))
                 .limit(1))
        docs = query.stream()
        deleted = False
        for doc in docs:
            doc.reference.delete()
            deleted = True
        if deleted:
            return jsonify({"success": True, "message": f"單字 '{word}' 已刪除！"})
        else:
            return jsonify({"success": False, "message": "找不到此單字！"})
    except GoogleAPICallError as e:
        logger.error(f"刪除單字 '{word}' 失敗: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"刪除單字 '{word}' 失敗"}), 500

# 搜尋單字
@app.route('/search_word', methods=['POST'])
def search_word():
    uid = request_token()
    if not isinstance(uid, str):
        return uid
    keyword = request.form['keyword'].strip()
    if not keyword:
        return jsonify({"success": False, "message": "請輸入搜尋關鍵字！"})
    words = load_words(uid)
    matched_words = [w["word"] for w in words if keyword.lower() in w["word"].lower()]
    if matched_words:
        return jsonify({"success": True,"words": matched_words})
    return jsonify({"success": False, "message": "沒有符合的單字！"})

# 標記不熟單字
@app.route('/mark_unfamiliar', methods=['POST'])
def mark_unfamiliar():
    uid = request_token()
    if not isinstance(uid, str):
        return uid
    word = request.form['word'].strip()
    try:
        query = (db.collection("toeic_words")
                 .where(filter=FieldFilter("user_id", "==", uid))
                 .where(filter=FieldFilter("word", "==", word))
                 .limit(1))
        docs = query.stream()
        updated = False
        for doc in docs:
            if doc.to_dict().get("is_unfamiliar", False):
                return jsonify({"success": False, "message": f"'{word}' 已經是不熟單字！"})
            doc.reference.update({"is_unfamiliar": True})
            updated = True
        if updated:
            return jsonify({"success": True, "message": f"'{word}' 已標記為不熟！"})
        else:
            return jsonify({"success": False, "message": "找不到此單字！"})
    except GoogleAPICallError as e:
        logger.error(f"標記不熟單字 '{word}' 失敗: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"標記不熟單字 '{word}' 失敗"}), 500

# 取消標記不熟單字
@app.route('/unmark_unfamiliar', methods=['POST'])
def unmark_unfamiliar():
    uid = request_token()
    if not isinstance(uid, str):
        return uid
    word = request.form['word'].strip()
    try:
        query = (db.collection("toeic_words")
                 .where(filter=FieldFilter("user_id", "==", uid))
                 .where(filter=FieldFilter("word", "==", word))
                 .limit(1))
        docs = query.stream()
        updated = False
        for doc in docs:
            if not doc.to_dict().get("is_unfamiliar", False):
                return jsonify({"success": False, "message": f"'{word}' 本來就不是不熟單字！"})
            doc.reference.update({"is_unfamiliar": False})
            updated = True
        if updated:
            return jsonify({"success": True, "message": f"'{word}' 已取消標記不熟！"})
        else:
            return jsonify({"success": False, "message": "找不到此單字！"})
    except GoogleAPICallError as e:
        logger.error(f"取消標記不熟單字 '{word}' 失敗: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"取消標記不熟單字 '{word}' 失敗"}), 500

# 複習單字
@app.route('/review_words', methods=['POST'])
def review_words():
    uid = request_token()
    if not isinstance(uid, str):
        return uid
    try:
        is_unfamiliar = request.form.get('is_unfamiliar', 'false') == 'true'
        words = load_words(uid, is_unfamiliar)
        if not words:
            return jsonify({"success": False, "message": "目前沒有單字可複習！"})
        return jsonify({"success": True, "words": words})
    except Exception as e:
        logger.error(f"複習單字錯誤: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"}), 500

# 隨機 10 個單字
@app.route('/random_words', methods=['POST'])
def random_words():
    uid = request_token()
    if not isinstance(uid, str):
        return uid
    try:
        is_unfamiliar = request.form.get('is_unfamiliar', 'false') == 'true'
        words = load_words(uid, is_unfamiliar)
        if not words:
            return jsonify({"success": False, "message": "目前沒有單字可選擇！"})
        random_words = random.sample(words, min(10, len(words)))
        return jsonify({"success": True, "words": random_words})
    except Exception as e:
        logger.error(f"隨機單字錯誤: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"}), 500

# 載入所有單字
@app.route('/load_all_words', methods=['POST'])
def load_all_words():
    uid = request_token()
    if not isinstance(uid, str):
        return uid
    try:
        words = load_words(uid)
        if not words:
            return jsonify({"success": False, "message": "目前沒有單字！"})
        return jsonify({"success": True, "words": words})
    except Exception as e:
        logger.error(f"載入所有單字錯誤: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"伺服器錯誤: {str(e)}"}), 500

# 驗證作者碼
@app.route('/verify_author', methods=['POST'])
def verify_author():
    code = request.form.get("auth_code", "").strip().lower()
    correct_code = os.getenv("AUTHOR_CODE", "").lower()
    if code != correct_code:
        return jsonify({"success": False, "message": "作者驗證碼錯誤！"}), 401
    return jsonify({"success": True, "message": "驗證碼正確"})

if __name__ == '__main__':
    app.run(debug=False)
