import os
import tempfile
import shutil
import sys
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, ElementClickInterceptedException
import undetected_chromedriver as uc

app = Flask(__name__) # Corrected typo: __name__
CORS(app)

TARGET_URL = "https://corebiolabs.limsabc.com/"
EMAIL_FIELD_ID = "b14343b2__form_username"
PASSWORD_FIELD_ID = "b14343b2__form_password"
LOGIN_BUTTON_ID = "b14343b2__form_form_submit"

# Element IDs/Xpaths for navigation/interactions
ACCESSIONING_MENU_XPATH = "//div[@menu-id='2345']//a"
ALL_TAB_ID = "limsabc_corebiolabs_tabmenu_i5" # ID for the 'All' tab
SEARCH_INPUT_ID = "e8a8eb47__m_search_line"
SEARCH_REFRESH_BUTTON_ID = "e8a8eb47__m_search_line_htmlelement_button" # This is the "lightning bolt" icon
SEARCH_CLEAR_BUTTON_ID = "e8a8eb47__m_search_line_htmlelement_button_2"  # This is the "X" icon
DETAILS_ICON_CSS = ".grid-selected-row-icon.pb_expander" # CSS selector for details icon (the three horizontal lines)
ATTACHMENTS_TAB_XPATH = "//li[@data-tabid='view_htmlelement_6']//a[normalize-space()='Attachments']" # XPATH for Attachments tab
ADD_ATTACHMENT_BUTTON_XPATH = "//div[contains(@id, 'attachments_crud_grid_buttonset_gbtn22')]//div[contains(@class,'toolbar-icon-circle')]" # XPATH for Add Attachment button (the paperclip icon)

# Common loading spinner/overlay (You MUST verify this XPath for your site!)
# This is crucial. Inspect your page when loaders appear and update this XPath.
GLOBAL_LOADER_XPATH = "//div[contains(@class, 'loading-spinner') or contains(@class, 'gwt-PopupPanelGlass') or contains(@class, 'lims-loading-mask') or contains(@class, 'loading-indicator') or contains(@class, 'dialog-glass') or contains(@class, 'overlay')]"

# --- UPLOAD MODAL LOCATORS ---
UPLOAD_MODAL_CONTAINER_XPATH = "//div[contains(@class, 'lims-modal-body') and contains(@class, 'ui-dialog')]"
FILE_INPUT_IN_MODAL_ID = "5fb192ce__ad_form_upload" # Confirmed via HTML
DROPDOWN_HEADER_XPATH = "//div[@class='lims-dropdown-header']" # The clickable part to open the dropdown
DROPDOWN_OPTIONS_LIST_WRAPPER_XPATH = "//div[@class='dropdown-list-wrapper']" # The container for the options list
DROPDOWN_OPTION_REQUISITION_FORM_XPATH = "//div[@class='dropdown-list']//div[@class='list-item' and normalize-space()='Requisition form']" # Precise XPath for the option
UPLOAD_SAVE_BUTTON_ID = "5fb192ce__ad_form_form_submit" # Confirmed via HTML (it's a div with ID, not a button)

# Specific loader for the upload modal (Re-verify comprehensive XPath, similar to GLOBAL_LOADER_XPATH)
UPLOAD_MODAL_LOADER_XPATH = "//div[contains(@class, 'loading-overlay-in-modal') or contains(@class, 'loading-overlay') or contains(@class, 'gwt-PopupPanelGlass') or contains(@class, 'loading-indicator') or contains(@class, 'dialog-glass') or contains(@class, 'overlay')]" 

driver_instance = None
last_search_term = None
last_login_attempt_time = None # To prevent rapid login retries

# --- Helper to get driver safely ---
def get_driver():
    global driver_instance
    if driver_instance:
        try:
            driver_instance.current_url # Attempt a simple command to check if the driver is alive
            print("Reusing existing driver instance.")
            return driver_instance
        except WebDriverException as e:
            print(f"Existing driver instance appears broken ({e}). Quitting and initializing a new one.")
            try:
                driver_instance.quit()
            except Exception as quit_e:
                 print(f"Error during quit of broken driver: {quit_e}")
            driver_instance = None # Force re-initialization

    print("Initializing new driver...")
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage") # Important for Docker/Linux without large /dev/shm
    
    # --- IMPORTANT: FOR DEBUGGING, KEEP THIS TO FALSE ---
    # Once stable, change to True for server deployment.
    chrome_options.headless = False # Keep False for debugging UI issues / crashes
    # --- END IMPORTANT ---

    # Additional arguments for stability and to mimic a real browser
    chrome_options.add_argument("--disable-gpu") # Often helps with headless issues
    chrome_options.add_argument("--window-size=1920,1080") # Set a consistent window size
    chrome_options.add_argument("--start-maximized") # Maximize window (may not apply in headless but good practice)
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-features=EnableEphemeralBadges")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--no-zygote") # Might help on some Linux systems
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--allow-insecure-localhost") # If dealing with self-signed certs (e.g., dev environment)
    # chrome_options.add_argument('--ignore-certificate-errors') # Uncomment if needed for specific TLS issues

    try:
        driver_instance = uc.Chrome(version_main=136, use_subprocess=True, options=chrome_options)
        time.sleep(1) # Small initial wait for browser window to stabilize
        print("Driver initialized successfully.")
    except Exception as e:
        print(f"Error initializing driver: {e}")
        print("Failed to initialize browser. Exiting application.")
        sys.exit(1) # Exit the application process

    return driver_instance

def teardown_driver(exception=None):
    global driver_instance
    if driver_instance: # Check if driver_instance is not None
        print("Closing driver...")
        try:
            driver_instance.quit()
            print("Driver closed.")
        except WebDriverException as e:
            print(f"Error during driver quit: {e}")
        except Exception as e:
             print(f"Unexpected error during driver quit: {e}")
        driver_instance = None

# Helper to save screenshot on error
def save_screenshot(driver, filename_prefix="error_screenshot"):
    try:
        # Check if driver is still alive and a browser (not a bare service)
        if driver and driver.service.process.poll() is None and driver.name == 'chrome':
            screenshot_name = f"{filename_prefix}_{int(time.time())}.png"
            driver.save_screenshot(screenshot_name)
            print(f"Screenshot saved: {screenshot_name}")
            return screenshot_name
    except Exception as e:
        print(f"Failed to save screenshot: {e}")
    return None

@app.route('/')
def index():
    return jsonify({"message": "Flask PDF Upload Server is running."})

@app.route('/upload', methods=['POST'])
def upload_files():
    email = request.form.get('email')
    password = request.form.get('password')
    uploaded_files = request.files.getlist("files")

    if not email or not password:
        return jsonify({"message": "Email and password are required."}), 400
    if not uploaded_files:
        return jsonify({"message": "No files uploaded."}), 400

    temp_dir = tempfile.mkdtemp()
    file_paths = []
    seen_filenames = set()

    try:
        for file in uploaded_files:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                 print(f"Skipping invalid or non-PDF file: {file.filename}")
                 continue
            filename = os.path.basename(file.filename)
            if filename in seen_filenames:
                print(f"Skipping duplicate filename in this session: {filename}")
                continue

            save_path = os.path.join(temp_dir, filename)
            try:
                file.save(save_path)
                file_paths.append(save_path)
                seen_filenames.add(filename)
            except Exception as e:
                print(f"Error saving file {filename} to temp directory: {e}")

        if not file_paths:
            return jsonify({"message": "No valid or unique PDF files to process."}), 400

        process_files_with_selenium(email, password, file_paths)

        return jsonify({"message": f"Attempted processing for {len(file_paths)} PDF(s) via Selenium. Check server logs for details."}), 200

    except Exception as e:
        print(f"An error occurred during file processing or Selenium execution: {e}")
        save_screenshot(get_driver(), "overall_upload_error") # Try to get screenshot if driver is still alive
        return jsonify({"message": f"An internal error occurred during processing: {e}"}), 500
    finally:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temp directory: {temp_dir}")
            except Exception as cleanup_e:
                print(f"Error cleaning up temp directory {temp_dir}: {cleanup_e}")

def process_files_with_selenium(email, password, file_paths):
    global driver_instance, last_login_attempt_time
    driver = get_driver()
    wait = WebDriverWait(driver, 45)

    print(f"Starting Selenium process for {len(file_paths)} files.")

    try:
        # Initial login check
        is_logged_in_and_on_app = False
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, ACCESSIONING_MENU_XPATH)))
            print("Accessioning menu found. Likely logged in and on app page.")
            is_logged_in_and_on_app = True
        except (TimeoutException, NoSuchElementException, WebDriverException):
            print("Accessioning menu not found during brief check. Browser likely not logged in or in a bad state.")
            is_logged_in_and_on_app = False

        if not is_logged_in_and_on_app:
            print("Browser not logged in. Attempting login.")
            current_time = time.time()
            if last_login_attempt_time is None or (current_time - last_login_attempt_time > 120):
                last_login_attempt_time = current_time
                try:
                    login(driver, wait, email, password)
                except Exception as login_e:
                    print(f"Login failed: {login_e}")
                    save_screenshot(driver, "login_critical_failure")
                    raise RuntimeError(f"Login failed: {login_e}. Cannot proceed.") from login_e
            else:
                 print("Skipping login attempt due to recent failure (within 120s). Driver might be stuck from previous attempt.")
                 raise RuntimeError("Skipping login attempt due to recent failure. Cannot proceed.")

        # Navigate to Accessioning and All tab once
        try:
            navigate_to_accessioning(driver, wait)
            click_all_tab(driver, wait)
            print("Waiting for search input/grid to load after clicking All tab...")
            # Wait for main grid loader to disappear after tab click
            wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
            wait.until(EC.presence_of_element_located((By.ID, SEARCH_INPUT_ID)))
            print("Search input found. Accessioning grid appears ready.")
        except Exception as nav_e:
            print(f"Fatal: Navigation to Accessioning failed: {nav_e}. Cannot proceed with file processing.")
            save_screenshot(driver, "fatal_navigation_error")
            raise RuntimeError(f"Navigation to Accessioning failed: {nav_e}") from nav_e

        # Process each file
        for i, path in enumerate(file_paths):
            base_name = os.path.splitext(os.path.basename(path))[0]
            print(f"\n--- Processing file {i+1}/{len(file_paths)}: {base_name} ---")
            
            try:
                search_for_file(driver, wait, base_name)
                click_details_and_open_attachment(driver, wait)

                print(f"--- Attempting upload for {base_name} from {os.path.basename(path)} ---")
                upload_file_and_select_dropdown(driver, wait, path)
                print(f"--- Upload process completed successfully for {base_name} ---")

            except (TimeoutException, NoSuchElementException, WebDriverException, ElementClickInterceptedException) as e:
                print(f"ERROR: Skipping {base_name} due to Selenium error (Timeout, NoSuchElement, WebDriver, or Click Intercepted issues). Error: {e}")
                save_screenshot(driver, f"selenium_error_{base_name.replace('.', '_')}")
            except Exception as e:
                print(f"ERROR: An unexpected error occurred while processing {base_name}: {e}")
                save_screenshot(driver, f"unexpected_error_{base_name.replace('.', '_')}")
            finally:
                # IMPORTANT: Clean up UI state for the next file
                close_details_panel(driver, wait)
                
                # Ensure any lingering upload modals are closed if the previous step failed before full modal closure
                try:
                    WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.XPATH, UPLOAD_MODAL_CONTAINER_XPATH)))
                    print("Confirmed upload modal is closed (or was never open).")
                except TimeoutException:
                    print("Upload modal still present, attempting to interact to close it...")
                    # Fallback if modal persists: try to find a close button or send ESC
                    try:
                        # Common close button XPath for UI-dialog (jQuery UI)
                        close_button_modal = driver.find_element(By.XPATH, "//div[contains(@class, 'ui-dialog-titlebar-close')]") 
                        driver.execute_script("arguments[0].click();", close_button_modal)
                        wait.until(EC.invisibility_of_element_located((By.XPATH, UPLOAD_MODAL_CONTAINER_XPATH)))
                        print("Modal closed via close button.")
                    except (NoSuchElementException, TimeoutException, WebDriverException):
                        print("Could not find modal close button or it didn't close. Trying ESC key (may disrupt UI).")
                        # from selenium.webdriver.common.keys import Keys # Need to import Keys
                        # driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE) 
                        # time.sleep(1) # Give time for ESC to register
                    except Exception as exc:
                        print(f"Error during fallback modal close: {exc}")
                
                # After cleaning up, ensure search input is available for the next iteration
                # Wait for any global loaders to disappear after closing panels/modals
                wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
                wait.until(EC.presence_of_element_located((By.ID, SEARCH_INPUT_ID)))
                print("UI reset for next file: search input is ready.")


        print("\n--- Finished processing batch of files ---")

    except Exception as e:
         print(f"\n--- Fatal error during initial Selenium setup, navigation, or login that halted processing: {e} ---")
         save_screenshot(driver, "fatal_process_error")
         raise


# --- Helper Functions with better waits and error handling ---

def login(driver, wait, email, password):
    print("Navigating to login page...")
    try:
        driver.get(TARGET_URL)
        wait.until(EC.presence_of_element_located((By.ID, EMAIL_FIELD_ID)))
        print("Login page loaded.")

        email_field = driver.find_element(By.ID, EMAIL_FIELD_ID)
        password_field = driver.find_element(By.ID, PASSWORD_FIELD_ID)
        login_button = driver.find_element(By.ID, LOGIN_BUTTON_ID)

        email_field.clear()
        email_field.send_keys(email)
        password_field.clear()
        password_field.send_keys(password)

        try:
            login_button.click()
            print("Clicked login button.")
        except WebDriverException:
             print("Standard click failed for login button, trying execute_script.")
             driver.execute_script("arguments[0].click();", login_button)
             print("Submitted login form via execute_script.")

        wait.until(EC.element_to_be_clickable((By.XPATH, ACCESSIONING_MENU_XPATH)))
        print("Login successful, dashboard loaded.")

    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        print(f"Login failed due to element not found or timeout: {e}")
        save_screenshot(driver, "login_failure")
        raise
    except Exception as e:
         print(f"An unexpected error occurred during login: {e}")
         save_screenshot(driver, "login_unexpected_error")
         raise


def navigate_to_accessioning(driver, wait):
    print("Navigating to Accessioning...")
    try:
        # Ensure any global loader is gone before interacting with main menu
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
        accessioning_menu = wait.until(
            EC.element_to_be_clickable((By.XPATH, ACCESSIONING_MENU_XPATH))
        )
        driver.execute_script("arguments[0].click();", accessioning_menu)
        print("Clicked Accessioning menu.")

        # Wait for page structure to load AND any loader to disappear
        wait.until(EC.presence_of_element_located((By.ID, ALL_TAB_ID)))
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
        print("Accessioning page structure loaded (All tab found) and initial loader gone.")

    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        print(f"Navigation to Accessioning failed: {e}")
        save_screenshot(driver, "navigate_accessioning_failure")
        raise
    except Exception as e:
         print(f"An unexpected error occurred during navigation to Accessioning: {e}")
         save_screenshot(driver, "navigate_accessioning_unexpected_error")
         raise


def click_all_tab(driver, wait):
    print("Attempting to click All tab...")
    try:
        # Ensure any global loader is gone before clicking tab
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
        all_tab_button = wait.until(
            EC.element_to_be_clickable((By.ID, ALL_TAB_ID))
        )
        driver.execute_script("arguments[0].click();", all_tab_button)
        print("Clicked All tab.")
        # The wait for GLOBAL_LOADER_XPATH and SEARCH_INPUT_ID is handled in main processing flow after this.

    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        print(f"Clicking All tab failed: {e}")
        save_screenshot(driver, "click_all_tab_failure")
        raise
    except Exception as e:
        print(f"An unexpected error occurred while clicking All tab: {e}")
        save_screenshot(driver, "click_all_tab_unexpected_error")
        raise


def search_for_file(driver, wait, filename_without_ext):
    global last_search_term
    print(f"Searching for: '{filename_without_ext}'")
    try:
        # Ensure any existing global loaders are gone before interacting with search
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
        search_input = wait.until(EC.presence_of_element_located((By.ID, SEARCH_INPUT_ID)))
        refresh_button = wait.until(EC.element_to_be_clickable((By.ID, SEARCH_REFRESH_BUTTON_ID)))

        if last_search_term != filename_without_ext:
            print("New search term detected. Attempting to clear previous input.")
            try:
                search_input.clear()
                # Additional methods for robust clearing if .clear() isn't enough
                search_input.send_keys('\ue009' + 'a')  # Ctrl+A (Select All)
                search_input.send_keys('\ue003')        # Backspace (Delete)
                wait.until(EC.text_to_be_present_in_element_value((By.ID, SEARCH_INPUT_ID), ""), timeout=5)
                print("Cleared search input successfully.")
            except Exception as e:
                print(f"Warning: Could not reliably clear search input field: {e}. Proceeding anyway.")
            
            time.sleep(1) # Small buffer after clearing for UI to register
            search_input.send_keys(filename_without_ext)
            last_search_term = filename_without_ext
            print(f"Typed '{filename_without_ext}' into search.")
        else:
            print(f"Search term is the same ('{filename_without_ext}'). Not clearing input, just refreshing.")

        driver.execute_script("arguments[0].click();", refresh_button)
        print("Clicked refresh button.")

        # IMPORTANT: Wait for the GLOBAL_LOADER_XPATH to disappear after search refresh
        print("Waiting for search results loader to disappear...")
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
        print("Search results loader is invisible.")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, DETAILS_ICON_CSS)))
        print("Search results loaded, details icon found for a row.")

    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        print(f"Search for '{filename_without_ext}' failed: {e}")
        save_screenshot(driver, f"search_failure_{filename_without_ext.replace('.', '_')}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during search for '{filename_without_ext}': {e}")
        save_screenshot(driver, f"search_unexpected_error_{filename_without_ext.replace('.', '_')}")
        raise


def click_details_and_open_attachment(driver, wait):
    print("Clicking details icon and opening attachments...")
    try:
        # Ensure no global loader before clicking details
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
        
        # --- ADDED AS PER USER REQUEST ---
        time.sleep(1) # Added to ensure UI stability before clicking the details icon
        print("Paused for 1 second before clicking details icon.")
        # --- END ADDITION ---

        details_icon = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, DETAILS_ICON_CSS)
        ))
        driver.execute_script("arguments[0].click();", details_icon)
        print("Details icon clicked.")

        # IMPORTANT: Wait for a loader to disappear after clicking the details icon
        print("Waiting for details panel loader to disappear...")
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))
        print("Details panel loader is invisible.")

        attachments_tab = wait.until(EC.element_to_be_clickable((
            By.XPATH, ATTACHMENTS_TAB_XPATH
        )))
        print("Attachments tab is visible.")
        driver.execute_script("arguments[0].scrollIntoView(true);", attachments_tab)
        driver.execute_script("arguments[0].click();", attachments_tab)
        print("Clicked Attachments tab.")

        add_attachment_button = wait.until(EC.element_to_be_clickable((
            By.XPATH, ADD_ATTACHMENT_BUTTON_XPATH
        )))
        print("'Add Attachment' toolbar icon is visible and clickable.")
        driver.execute_script("arguments[0].scrollIntoView(true);", add_attachment_button)
        driver.execute_script("arguments[0].click();", add_attachment_button)
        print("'Add Attachment' toolbar icon clicked.")

    except (TimeoutException, NoSuchElementException, WebDriverException, ElementClickInterceptedException) as e:
        print(f"Failed to click details, attachments tab, or add attachment button: {e}")
        save_screenshot(driver, "open_attachment_failure")
        raise
    except Exception as e:
        print(f"An unexpected error occurred while clicking details/attachments: {e}")
        save_screenshot(driver, "open_attachment_unexpected_error")
        raise


def close_details_panel(driver, wait):
    """
    Attempts to close the details panel after an accession record has been processed.
    This is crucial to return to the main grid view for the next search.
    Assumes clicking the details icon again collapses the panel.
    """
    print("Attempting to close details panel...")
    try:
        # Check if the attachments tab (which is part of the details panel) is still visible
        try:
            # Use a short wait to see if it's currently visible
            WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, ATTACHMENTS_TAB_XPATH)))
            print("Attachments tab is visible, implying details panel is open. Attempting to close.")
            
            # Re-click the details icon to close the panel
            details_icon = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, DETAILS_ICON_CSS)
            ))
            driver.execute_script("arguments[0].click();", details_icon)
            print("Details icon re-clicked to close panel.")

            # Wait for the attachments tab to become invisible, confirming closure
            wait.until(EC.invisibility_of_element_located((By.XPATH, ATTACHMENTS_TAB_XPATH)))
            print("Details panel confirmed closed.")
            
        except TimeoutException:
            print("Details panel or attachments tab not found or already closed after initial check (Timeout).")
        except NoSuchElementException:
             print("Details panel or attachments tab not found or already closed (NoSuchElementException).")
        
        # Ensure any global loaders triggered by closing are gone
        wait.until(EC.invisibility_of_element_located((By.XPATH, GLOBAL_LOADER_XPATH)))


    except Exception as e:
        print(f"An error occurred while trying to close the details panel: {e}")
        save_screenshot(driver, "close_details_panel_error")


def upload_file_and_select_dropdown(driver, wait, file_path):
    print(f"Attempting to upload file: {os.path.basename(file_path)}")
    try:
        # 1. Wait for the upload modal to appear
        upload_modal_container = wait.until(EC.presence_of_element_located((By.XPATH, UPLOAD_MODAL_CONTAINER_XPATH)))
        print("Upload modal is visible.")

        # 2. Locate file input and send file
        file_input = wait.until(EC.presence_of_element_located((By.ID, FILE_INPUT_IN_MODAL_ID)))

        # Make file input visible and accessible using JavaScript.
        driver.execute_script("""
            arguments[0].style.display = 'block';
            arguments[0].style.visibility = 'visible';
            arguments[0].style.opacity = 1;
            arguments[0].style.height = '1px';
            arguments[0].style.width = '1px';
            arguments[0].style.position = 'absolute';
            arguments[0].style.top = '0';
            arguments[0].style.left = '0';
        """, file_input)
        print(f"File input visibility adjusted. Sending keys: {file_path}")

        file_input.send_keys(file_path)
        print("File path sent to input field.")

        # 3. CRUCIAL WAIT: Wait for any loading spinner/overlay within the modal to disappear.
        print("Waiting for modal loader to disappear (indicating file processing)...")
        try:
            WebDriverWait(driver, 20).until(EC.invisibility_of_element_located((By.XPATH, UPLOAD_MODAL_LOADER_XPATH)))
            print("Modal loader is invisible. File likely processed by front-end.")
        except TimeoutException:
            print("Warning: Modal loader did not disappear within timeout or was not found. Proceeding with caution.")
            time.sleep(2) # Fallback sleep if no explicit loader was detected or it's very brief

        # 4. Re-locate the custom dropdown header before interacting with it.
        dropdown_header = wait.until(EC.element_to_be_clickable((By.XPATH, DROPDOWN_HEADER_XPATH)))
        driver.execute_script("arguments[0].click();", dropdown_header)
        print("Dropdown header clicked to open options.")

        # 5. Wait for dropdown options container to be visible and then the specific option
        print("Waiting for dropdown options list to appear...")
        options_container = wait.until(EC.visibility_of_element_located((By.XPATH, DROPDOWN_OPTIONS_LIST_WRAPPER_XPATH)))
        print("Dropdown options list wrapper is visible.")
        
        time.sleep(0.5) # A tiny buffer, as a last resort if explicit waits fail here.

        # 6. Re-locate and click the "Requisition form" list item
        requisition_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, DROPDOWN_OPTION_REQUISITION_FORM_XPATH)
        ))
        driver.execute_script("arguments[0].click();", requisition_option)
        print("Dropdown option 'Requisition form' selected.")

        # --- MODIFIED: REMOVED THE WAIT FOR DROPDOWN LIST INVISIBILITY ---
        # print("Waiting for dropdown options list to close...")
        # wait.until(EC.invisibility_of_element_located((By.XPATH, DROPDOWN_OPTIONS_LIST_WRAPPER_XPATH)))
        # print("Dropdown options list is now invisible (dropdown closed).")
        print("Skipping wait for dropdown list to close as requested. It might remain visible.")
        # --- END MODIFICATION ---

        # Wait for the text in the dropdown header's input field to update
        # This confirms the visual selection has registered.
        dropdown_text_input_xpath = "//div[@class='lims-dropdown-header']//input[@class='dropdown-text']"
        print(f"Verifying selected text in dropdown header: '{dropdown_text_input_xpath}' should contain 'Requisition form'...")
        wait.until(EC.text_to_be_present_in_element_value((By.XPATH, dropdown_text_input_xpath), "Requisition form"))
        print("Dropdown header now displays 'Requisition form'.")

        # 7. Re-locate and click the Save button
        save_button = wait.until(EC.element_to_be_clickable((By.ID, UPLOAD_SAVE_BUTTON_ID)))
        driver.execute_script("arguments[0].click();", save_button)
        print("Save button clicked.")

        # 8. CRUCIAL WAIT: Wait for the upload modal to close or become invisible
        print("Waiting for upload modal to close (confirming complete upload)...")
        wait.until(EC.invisibility_of_element_located((By.XPATH, UPLOAD_MODAL_CONTAINER_XPATH)))
        print("Upload modal closed successfully. File upload process completed.")

    except (TimeoutException, NoSuchElementException, WebDriverException, ElementClickInterceptedException) as e:
        print(f"ERROR during file upload for {os.path.basename(file_path)}: {e}")
        save_screenshot(driver, f"upload_failure_{os.path.basename(file_path).replace('.', '_')}")
        raise
    except Exception as e:
        print(f"UNEXPECTED ERROR during file upload for {os.path.basename(file_path)}: {e}")
        save_screenshot(driver, f"upload_unexpected_error_{os.path.basename(file_path).replace('.', '_')}")
        raise


if __name__ == '__main__':
    try:
        print("Starting Flask server...")
        get_driver() 
        app.run(debug=False, port=5000, threaded=False)
    except Exception as e:
        print(f"Flask application failed to start or encountered a fatal error: {e}")
    finally:
        print("Flask application stopping. Attempting to close driver...")
        teardown_driver()