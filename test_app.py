import allure
import pytest
import logging
import json
from app import app
import firebase_admin
from firebase_admin import auth
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore import FieldFilter

# 設定日誌
logger = logging.getLogger(__name__)

# 測試夾具
@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# 模擬 Firebase 認證
@pytest.fixture
def mock_token(monkeypatch):
    def mock_verify_id_token(*args, **kwargs):
        return {'uid': 'test_user_id'}
    monkeypatch.setattr(auth, 'verify_id_token', mock_verify_id_token)
    return "test_token"

class TestApp:
    def setup_method(self):
        with app.app_context():
            from app import db
            def delete_test_word(word):
                try:
                    query = (db.collection("toeic_words")
                             .where(filter=FieldFilter("user_id", "==", 'test_user_id'))
                             .where(filter=FieldFilter("word", "==", word))
                             .limit(1))
                    results = query.get()
                    for doc in results:
                        doc.reference.delete()
                    return True
                except GoogleAPICallError as e:
                    logger.error(f"測試前清理：刪除單字 '{word}' 失敗: {e}")
                    return False
            for word in ['exam', 'good', 'bad', 'cool', 'test']:
                delete_test_word(word)

    def teardown_method(self):
        with app.app_context():
            from app import db
            def delete_test_word(word):
                try:
                    query = (db.collection("toeic_words")
                             .where(filter=FieldFilter("user_id", "==", 'test_user_id'))
                             .where(filter=FieldFilter("word", "==", word))
                             .limit(1))
                    results = query.get()
                    for doc in results:
                        doc.reference.delete()
                    return True
                except GoogleAPICallError as e:
                    logger.error(f"測試後清理：刪除單字 '{word}' 失敗: {e}")
                    return False
            for word in ['exam', 'good', 'bad', 'cool', 'test']:
                delete_test_word(word)

    @allure.feature('首頁功能')
    def test_index(self, client):
        allure.step("測試首頁路由")
        logger.info("測試首頁路由")
        response = client.get('/')
        assert response.status_code == 200

    @allure.feature('使用者身份驗證')
    def test_unauthorized_access(self, client):
        allure.step("測試未授權訪問")
        logger.info("測試未授權訪問")
        response = client.post('/save_word', data={'word': 'post'})
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['message'] == "未提供身份驗證令牌！"

    @allure.feature('單字儲存')
    def test_save_word(self, client, mock_token):
        allure.step("測試儲存單字功能")
        logger.info("測試儲存單字功能")
        headers = {'Authorization': f'Bearer {mock_token}'}
        response = client.post('/save_word',
                            data={'word': 'exam'},
                            headers=headers)
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] == True

    @allure.feature('單字儲存')
    def test_save_duplicate_word(self, client, mock_token):
        allure.step("測試重複儲存單字")
        logger.info("測試重複儲存單字")
        headers = {'Authorization': f'Bearer {mock_token}'}
        # 第一次儲存
        response = client.post('/save_word',
                            data={'word': 'good'},
                            headers=headers)
        assert response.status_code == 201, f"第一次儲存失敗: {response.data}"
        data = json.loads(response.data)
        assert data['success'] == True, f"第一次儲存應成功，但實際為: {data}"
        # 檢查單字是否存在
        from app import load_words
        words = load_words('test_user_id')
        assert any(w['word'] == 'good' for w in words), f"單字 'good' 未正確儲存: {words}"
        # 第二次儲存相同單字
        response = client.post('/save_word',
                            data={'word': 'good'},
                            headers=headers)
        data = json.loads(response.data)
        assert data['success'] == False, f"預期重複儲存失敗，但實際為: {data}"
        assert "已存在" in data['message'], f"預期訊息包含 '已存在'，但實際為: {data['message']}"

    @allure.feature('單字搜尋')
    def test_search_word(self, client, mock_token):
        allure.step("測試搜尋單字功能")
        logger.info("測試搜尋單字功能")
        headers = {'Authorization': f'Bearer {mock_token}'}
        # 先儲存單字
        response = client.post('/save_word',
                            data={'word': 'bad'},
                            headers=headers)
        assert response.status_code == 201, f"儲存單字失敗: {response.data}"
        data = json.loads(response.data)
        assert data['success'] == True, f"儲存應成功，但實際為: {data}"
        # 檢查單字是否存在
        from app import load_words
        words = load_words('test_user_id')
        assert any(w['word'] == 'bad' for w in words), f"單字 'bad' 未正確儲存: {words}"
        # 搜尋單字
        response = client.post('/search_word',
                            data={'keyword': 'bad'},
                            headers=headers)
        data = json.loads(response.data)
        assert data['success'] == True, f"預期搜尋成功，但實際為: {data}"
        assert 'bad' in data['words'], f"預期找到單字 'bad'，但實際為: {data['words']}"

    @allure.feature('單字管理')
    def test_mark_unfamiliar(self, client, mock_token):
        allure.step("測試標記不熟單字功能")
        logger.info("測試標記不熟單字功能")
        headers = {'Authorization': f'Bearer {mock_token}'}
        client.post('/save_word',
                    data={'word': 'cool'},
                    headers=headers)
        response = client.post('/mark_unfamiliar',
                            data={'word': 'cool'},
                            headers=headers)
        data = json.loads(response.data)
        assert data['success'] == True

    @allure.feature('儲存空白單字')
    def test_spaceSave(self, client, mock_token):
        allure.step("測試儲存空白")
        logger.info("測試儲存空白")
        headers = {'Authorization': f'Bearer {mock_token}'}
        response = client.post('/save_word',
                            data={},
                            headers=headers)
        assert response.status_code != 500
    @allure.feature('含空白的單字儲存')
    def test_spaceSave_word(self, client, mock_token):
        allure.step("測試儲存含空白的單字")
        logger.info("測試儲存含空白的單字")
        headers = {'Authorization': f'Bearer {mock_token}'}
        response = client.post('/save_word',
                            data={'word': ' exam'},
                            headers=headers)
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] == True
