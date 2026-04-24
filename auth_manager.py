import time
import json
import re
import undetected_chromedriver as uc
from logger_config import log

def fetch_cookies_and_headers():
    options = uc.ChromeOptions()
    
    # Enable performance logging to catch the Authorization header
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # Headless arguments that bypass common bot-detection checks
    options.add_argument("--headless") 
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # These flags help hide the 'headless' nature from Cloudflare
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("--disable-gpu")
    
    # Use a modern, generic User-Agent (matching a real Windows Chrome 147+ profile)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    options.add_argument(f'--user-agent={user_agent}')

    driver = None
    try:
        print("Starting headless browser...")
        driver = uc.Chrome(options=options, version_main=147)

        # Step 1: Visit the home page first. 
        # Directly hitting search results in headless mode is a major "bot" red flag.
        print("Visiting Upwork home to establish session...")
        driver.get("https://www.upwork.com/")
        time.sleep(8) 

        # Step 2: Navigate to the search page
        print("Navigating to search page...")
        driver.get("https://www.upwork.com/nx/search/jobs/?q=python&sort=recency")

        # Step 3: Wait for the page to 'breathe' and fire GraphQL calls.
        # 25 seconds is the sweet spot for slow headless loads.
        print("Waiting 25 seconds for background GraphQL activity...")
        time.sleep(25)

        # Extract Cookies
        selenium_cookies = driver.get_cookies()
        cookies_dict = {cookie["name"]: cookie["value"] for cookie in selenium_cookies}
        
        # Extract Headers from Performance Logs
        logs = driver.get_log("performance")
        headers_dict = {}


        """
        logs = { list of entries }
        Each entry looks like:
        entry = {
            "message": '{"message": {"method": "Network.requestWillBeSent", "params": {...}}}',
            "timestamp": 1234567890,
            "level": "INFO"
        }
        Each Message Dict looks like:
        {
            "method": "Network.requestWillBeSent",
            "params": {
                "request": {
                    "url": "https://www.upwork.com/api/graphql/v1",
                    "headers": {
                        "Authorization": "Bearer eyJhbGc...",
                        "User-Agent": "Mozilla/5.0..."
                    }
                }
            }
        }
        """
        print("Analyzing network logs for Authorization token...")
        for entry in logs:
            try:
                message = json.loads(entry["message"])["message"]
                if message["method"] == "Network.requestWillBeSent":
                    request = message.get("params", {}).get("request", {})
                    url = request.get("url", "")

                    if "graphql" in url:
                        raw_headers = request.get("headers", {})
                        # Normalize keys to lowercase for reliable matching
                        for key, value in raw_headers.items():
                            low_key = key.lower()
                            if low_key == "authorization" and "authorization" not in headers_dict:
                                headers_dict["authorization"] = value
                            if low_key == "user-agent" and "user-agent" not in headers_dict:
                                headers_dict["user-agent"] = value

                        if "authorization" in headers_dict:
                            break
            except Exception:
                continue

        # Status Reporting
        if len(cookies_dict) > 3:
            log.info(f"✅ Success: {len(cookies_dict)} cookies collected.")
        else:
            log.warning(f"⚠️ Warning: Only {len(cookies_dict)} cookies found. Headless mode might be restricted.")

        if "authorization" in headers_dict:
            log.info("✅ Success: Authorization token extracted.")
        else:
            log.warning("⚠️ Warning: Authorization header not found. Cloudflare might have blocked the search.")

        return cookies_dict, headers_dict

    except Exception as e:
        log.error(f"❌ Error during execution: {e}")
        return {}, {}
    finally:
        if driver:
            print("Closing browser...")
            try:
                driver.quit()
            except:
                pass

# UPDATE BOTH COOKIES AND HEADERS IN .env FILE
def update_cookies_and_headers_in_env():
    print("Fetching fresh cookies and headers from browser...")
    new_cookies, new_headers = fetch_cookies_and_headers()

    # Guard: abort if we got nothing useful 
    if not new_cookies and not new_headers:
        log.warning("⚠️  Error: Both cookies and headers are empty. env not updated.")
        return

    # Read current .env content
    with open(".env", "r") as f:
        content = f.read()

    # Update UPWORK_COOKIES
    if new_cookies:
        cookie_str = json.dumps(new_cookies)

        if "UPWORK_COOKIES=" in content:
            content = re.sub(
                r"UPWORK_COOKIES=.*",
                f"UPWORK_COOKIES='{cookie_str}'",
                content
            )
        else:
            content += f"\nUPWORK_COOKIES='{cookie_str}'"

        log.info(f"✅  Cookies updated in .env ({len(new_cookies)} entries).")
    else:
        log.warning("⚠️  Warning: Skipping UPWORK_COOKIES update — no cookies were fetched.")

    # Update UPWORK_HEADERS (only authorization + user-agent)
    if new_headers:
        # Load whatever is already stored so we don't wipe other keys
        match = re.search(r"UPWORK_HEADERS='(.*?)'", content)
        if match:
            try:
                current_headers = json.loads(match.group(1))
            except Exception:
                # Stored value is not valid JSON — start fresh
                current_headers = {}
        else:
            current_headers = {}

        # Apply only the two keys we fetched; everything else stays as-is
        if "authorization" in new_headers:
            # Normalize to always include the "Bearer " prefix exactly once
            raw_token = new_headers["authorization"]
            current_headers["authorization"] = "Bearer " + raw_token.replace("Bearer ", "")

        if "user-agent" in new_headers:
            current_headers["user-agent"] = new_headers["user-agent"]

        new_header_line = f"UPWORK_HEADERS='{json.dumps(current_headers)}'"

        if "UPWORK_HEADERS=" in content:
            content = re.sub(
                r"UPWORK_HEADERS='.*?'",
                new_header_line,
                content
            )
        else:
            content += f"\n{new_header_line}"

        log.info("✅  Headers updated in .env (authorization + user-agent only).")
    else:
        log.warning("⚠️  Warning: Skipping UPWORK_HEADERS update — no headers were fetched.")

    # Write updated content back
    with open(".env", "w") as f:
        f.write(content)

    # print("✅  New Cookies: ", new_cookies)
    # print("✅  New Headers: ", new_headers)
    log.info("✅  Success: .env file updated with fresh cookies and headers.")


"""
# TESTING FETCH FUNCTION 
cookies, headers = fetch_cookies_and_headers()
print("Fetched Cookies:", cookies)
print("Fetched Headers:", headers)
"""

"""
# TESTING UPDATE BOTH COOKIES AND HEADERS TOGETHER
update_cookies_and_headers_in_env()
"""