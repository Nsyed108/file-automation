import os
import sys
import time
from flask import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, ElementClickInterceptedException
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver



# Constants for selectors and URLs
TARGET_URL = "https://corebiolabs.limsabc.com/"
EMAIL_FIELD_ID = "b14343b2__form_username"
PASSWORD_FIELD_ID = "b14343b2__form_password"
LOGIN_BUTTON_ID = "b14343b2__form_form_submit"
ACCESSIONING_MENU_XPATH = "//div[@menu-id='2345']//a"
ALL_TAB_ID = "limsabc_corebiolabs_tabmenu_i5"
SEARCH_INPUT_ID = "e8a8eb47__m_search_line"
SEARCH_REFRESH_BUTTON_ID = "e8a8eb47__m_search_line_htmlelement_button"
SEARCH_CLEAR_BUTTON_ID = "e8a8eb47__m_search_line_htmlelement_button_2"
DETAILS_ICON_CSS = ".grid-selected-row-icon.pb_expander"
ATTACHMENTS_TAB_XPATH = "//li[@data-tabid='view_htmlelement_6']//a[normalize-space()='Attachments']"
ADD_ATTACHMENT_BUTTON_XPATH = "//div[contains(@id, 'attachments_crud_grid_buttonset_gbtn22')]//div[contains(@class,'toolbar-icon-circle')]"
GLOBAL_LOADER_XPATH = "//div[contains(@class, 'loading-spinner') or contains(@class, 'gwt-PopupPanelGlass') or contains(@class, 'lims-loading-mask') or contains(@class, 'loading-indicator') or contains(@class, 'dialog-glass') or contains(@class, 'overlay')]"
UPLOAD_MODAL_CONTAINER_XPATH = "//div[contains(@class, 'lims-modal-body') and contains(@class, 'ui-dialog')]"
FILE_INPUT_IN_MODAL_ID = "5fb192ce__ad_form_upload"
UPLOAD_SAVE_BUTTON_ID = "5fb192ce__ad_form_form_submit"

# Globals
driver_instance = None
last_search_term = None
last_login_attempt_time = None

def teardown_driver(exception=None):
    global driver_instance
    if driver_instance:
        try:
            driver_instance.quit()
        except Exception:
            pass
        driver_instance = None

def use_cloned_chrome_profile_directly():
    global driver_instance
    if driver_instance:
        try:
            driver_instance.title  # check if still alive
            print("Reusing existing driver instance.")
            return driver_instance
        except WebDriverException:
            print("Driver instance invalid, restarting...")
            try:
                driver_instance.quit()
            except Exception:
                pass
            driver_instance = None

    options = webdriver.ChromeOptions()
    profile_dir = "/tmp/selenium-profile-shared"  # <--- REUSABLE LOCATION
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_experimental_option("detach", True)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(ChromeDriverManager().install())
    driver_instance = webdriver.Chrome(service=service, options=options)

    driver_instance.get("https://corebiolabs.limsabc.com/")
    time.sleep(30)

    return driver_instance



def process_files_with_selenium(email, password, file_paths):
    global driver_instance, last_login_attempt_time, last_search_term
    driver = use_cloned_chrome_profile_directly()
    wait = WebDriverWait(driver, 45)
    file_upload_results = []

    try:
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, ACCESSIONING_MENU_XPATH)))
            is_logged_in_and_on_app = True
        except:
            is_logged_in_and_on_app = False

        if not is_logged_in_and_on_app:
            current_time = time.time()
            if last_login_attempt_time is None or (current_time - last_login_attempt_time > 120):
                last_login_attempt_time = current_time
                login(driver, wait, email, password)
            else:
                raise RuntimeError("Skipping login attempt due to recent failure. Cannot proceed.")

        navigate_to_accessioning(driver, wait)
        click_all_tab(driver, wait)
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
        wait.until(EC.presence_of_element_located((By.ID, SEARCH_INPUT_ID)))

        for path in file_paths:
            name = os.path.splitext(os.path.basename(path))[0]
            try:
                search_for_file(driver, wait, name)
                click_details_and_open_attachment(driver, wait)
                upload_file_and_select_dropdown(driver, wait, path)
                file_upload_results.append({"filename": os.path.basename(path), "status": "Uploaded"})
            except Exception as e:
                file_upload_results.append({"filename": os.path.basename(path), "status": f"Failed: {type(e).__name__}"})
            finally:
                close_details_panel(driver, wait)
                wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
                wait.until(EC.presence_of_element_located((By.ID, SEARCH_INPUT_ID)))

        return file_upload_results
    except Exception as e:
        raise

def login(driver, wait, email, password):
    driver.get(TARGET_URL)
    wait.until(EC.presence_of_element_located((By.ID, EMAIL_FIELD_ID)))
    driver.find_element(By.ID, EMAIL_FIELD_ID).send_keys(email)
    driver.find_element(By.ID, PASSWORD_FIELD_ID).send_keys(password)
    driver.find_element(By.ID, LOGIN_BUTTON_ID).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, ACCESSIONING_MENU_XPATH)))

def navigate_to_accessioning(driver, wait):
    wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
    el = wait.until(EC.element_to_be_clickable((By.XPATH, ACCESSIONING_MENU_XPATH)))
    time.sleep(1)  # Ensure the element is ready
    el.click()
    wait.until(EC.presence_of_element_located((By.ID, ALL_TAB_ID)))

def click_all_tab(driver, wait):
    wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
    el = wait.until(EC.element_to_be_clickable((By.ID, ALL_TAB_ID)))
    time.sleep(1)  # Ensure the element is ready
    el.click()

def search_for_file(driver, wait, term):
    global last_search_term
    wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
    input_box = wait.until(EC.presence_of_element_located((By.ID, SEARCH_INPUT_ID)))
    refresh = wait.until(EC.element_to_be_clickable((By.ID, SEARCH_REFRESH_BUTTON_ID)))
    time.sleep(1)  # Ensure the input box is ready
    if last_search_term != term:
        input_box.clear()
        input_box.send_keys(term)
        last_search_term = term
    time.sleep(3)  # Allow time for search to process
    refresh.click()
    wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, DETAILS_ICON_CSS)))

def click_details_and_open_attachment(driver, wait):
    wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
    time.sleep(4)
    icon = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, DETAILS_ICON_CSS)))
    icon.click()
    time.sleep(4)
    wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
    time.sleep(2)
    wait.until(EC.element_to_be_clickable((By.XPATH, ATTACHMENTS_TAB_XPATH))).click()
    time.sleep(3)
    wait.until(EC.element_to_be_clickable((By.XPATH, ADD_ATTACHMENT_BUTTON_XPATH))).click()

def upload_file_and_select_dropdown(driver, wait, file_path):
    wait.until(EC.presence_of_element_located((By.XPATH, UPLOAD_MODAL_CONTAINER_XPATH)))
    time.sleep(2)
    input_elem = wait.until(EC.presence_of_element_located((By.ID, FILE_INPUT_IN_MODAL_ID)))
    time.sleep(2)
    # Ensure it's interactable
    if not input_elem.is_displayed():
        raise Exception("File input is not visible!")
    time.sleep(2)
    print(f"Uploading: {file_path}")
    assert os.path.exists(file_path), f"❌ File path does not exist: {file_path}"
    time.sleep(2)
    input_elem.send_keys(file_path)
    time.sleep(3)

    dropdown = driver.find_element(By.ID, "5fb192ce__ad_form_file_type")
    driver.execute_script("""
        arguments[0].value = '1';
        const evt = new Event('change', { bubbles: true });
        arguments[0].dispatchEvent(evt);
    """, dropdown)
    time.sleep(2)
    save_button = wait.until(EC.element_to_be_clickable((By.ID, UPLOAD_SAVE_BUTTON_ID)))
    try:
        driver.execute_script("arguments[0].click();", save_button)
    except WebDriverException:
        save_button.click()

    WebDriverWait(driver, 15).until(
        EC.invisibility_of_element_located((By.XPATH, UPLOAD_MODAL_CONTAINER_XPATH))
    )
        # Optional: log results to upload_results.txt without duplicating entries
    result_entry = {"filename": os.path.basename(file_path), "status": "Uploaded"}
    upload_log_path = "upload_results.txt"

    existing_results = []
    if os.path.exists(upload_log_path):
        try:
            with open(upload_log_path, "r") as f:
                existing_results = json.load(f)
        except Exception:
            existing_results = []

    if result_entry not in existing_results:
        existing_results.append(result_entry)
        with open(upload_log_path, "w") as f:
            json.dump(existing_results, f, indent=2)

def close_details_panel(driver, wait):
    try:
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, ATTACHMENTS_TAB_XPATH)))
        icon = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, DETAILS_ICON_CSS)))
        icon.click()
        wait.until(EC.invisibility_of_element_located((By.XPATH, ATTACHMENTS_TAB_XPATH)))
    except:
        pass

def auto_upload_from_folder(email, password, folder_path):
    if not os.path.isdir(folder_path):
        print(f"❌ Directory does not exist: {folder_path}")
        return

    pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("No PDF files found to upload.")
        return

    print(f"Found {len(pdf_files)} PDFs. Starting upload...")
    process_files_with_selenium(email, password, pdf_files)
