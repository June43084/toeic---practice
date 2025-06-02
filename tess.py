from selenium import webdriver  
from selenium.webdriver.chrome.options import Options  
from selenium.webdriver.chrome.service import Service  
from selenium.webdriver.common.by import By  
from selenium.webdriver.support.ui import WebDriverWait  
from selenium.webdriver.support import expected_conditions as EC  
import time, pytest,os
from dotenv import load_dotenv

load_dotenv()

# 建立 pytest fixture，初始化 Chrome 瀏覽器
@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--start-maximized")  
    service = Service(executable_path="chromedriver.exe") 
    driver = webdriver.Chrome(service=service, options=options)  
    yield driver  # 把 driver 提供給測試函式使用
    driver.quit()  

# 測試登入流程（錯誤帳號）
def test_login_flow(driver):
    driver.get("http://localhost:5000")  # 開啟本機伺服器頁面

    # 輸入帳號與密碼
    email_input = driver.find_element(By.ID, "username")
    password_input = driver.find_element(By.ID, "password")
    login_btn = driver.find_element(By.ID, "login_btn")  

    # 輸入錯誤的帳密（測試用戶）
    email_input.send_keys("測試用戶@example.com")
    password_input.send_keys("password123")
    login_btn.click()  

    time.sleep(3)  

# 測試正常登入後，操作各項按鈕並登出
def test_login_get(driver):
    driver.get("http://localhost:5000")  

    # 輸入帳號密碼
    email_input = driver.find_element(By.ID, "username")
    password_input = driver.find_element(By.ID, "password")
    login_btn = driver.find_element(By.ID, "login_btn")

    # 輸入正確帳密
    email_input.send_keys(os.getenv("ADMIN_EMAIL"))
    password_input.send_keys("000000")
    login_btn.click()

    # 等待警告框（例如 JavaScript alert）出現後點擊確認
    try:
        WebDriverWait(driver, 5).until(EC.alert_is_present())  
        alert = driver.switch_to.alert  
        print(f"✅ 登入後警告框內容：{alert.text}")
        alert.accept()  
    except:
        print("沒有警告框或已被關閉")

    # 顯示單字列表：等待按鈕可點擊再點
    show_word_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[1]/button[1]"))  # 等待顯示單字按鈕可點擊
    )
    show_word_btn.click()
    time.sleep(2)
    # 點擊複習單字 測試聲音
    voice_btn = driver.find_element(By.XPATH ,"/html/body/div[1]/div[2]/div[1]/button[1]")
    voice_btn.click()
    time.sleep(2)

    # 輸入單字到輸入框（假設有 id="word_input"）
    input_box = driver.find_element(By.ID, "word_input")
    input_box.clear()  
    input_box.send_keys("apple")  
    time.sleep(2)

    # 點擊新增單字按鈕
    add_btn = driver.find_element(By.XPATH, "/html/body/div[1]/div[1]/div[1]/button[1]")
    add_btn.click()

    # 處理儲存單字後的 alert 警告框
    try:
        WebDriverWait(driver, 5).until(EC.alert_is_present())  
        alert = driver.switch_to.alert
        print(f"✅ 儲存後警告框內容：{alert.text}")
        alert.accept()  # 點擊確認
    except:
        print("⚠️ 儲存後沒有出現警告框")

    time.sleep(2)

    # 點擊搜尋按鈕
    search_btn = driver.find_element(By.XPATH, "/html/body/div[1]/div[1]/div[1]/button[3]")
    input_box.send_keys("apple")
    search_btn.click()
    time.sleep(2)

    # 點擊刪除單字按鈕
    del_btn = driver.find_element(By.XPATH, "/html/body/div[1]/div[1]/div[1]/button[2]")
    del_btn.click()
    time.sleep(2)
