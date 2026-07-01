from email.mime import text
import os, json, sys
from datetime import datetime, date, timedelta
from time import sleep
from random import uniform
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import tkinter as tk
from tkinter import messagebox
from collections import Counter
import requests
import sys
import re


try:
    from cloakbrowser.download import ensure_binary
    from cloakbrowser.config import get_chromium_version, get_default_stealth_args

    _HAS_CLOAK = True
except ImportError:
    _HAS_CLOAK = False


class Automation:
    def _log(self, message):
        print(f"[Air Arabia Bot] {message}")

        # Skip file logging when started from dashboard.py
        if sys.argv[0].endswith("dashboard.py"):
            return

        from app_paths import get_app_dir
        from session_logger import append_log_line

        try:
            SCRIPT_DIR = get_app_dir()
            append_log_line(message, SCRIPT_DIR)
        except OSError:
            pass

    def __init__(self):
        self.config = self.read_json('config.json')

        if self.config:
            self._log("Settings loaded from config.json.")
        else:
            self._log("Warning: config.json is missing or empty — check your dashboard settings.")

        self.headless = bool(self.config.get('headless', False))
        browser_mode = "headless (no window)" if self.headless else "visible"
        self._log(f"Opening Chrome browser — {browser_mode}...")
        self.driver = self.get_driver(headless=self.headless)
        self._log("Browser ready.")
        self.iframe_found = False

        self.start_automation()

    def element_exists(self, selector: str, timeout: int = 30) -> bool:
        by = By.XPATH if selector.startswith("/") or selector.startswith("(") else By.CSS_SELECTOR
        try:
            WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((by, selector)))
            return True
        except:
            return False

    @staticmethod
    def get_driver(profile_dir: str = "./chrome_profile", headless: bool = False) -> uc.Chrome:
        options = uc.ChromeOptions()

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # 🔥 IMPORTANT: allow popups
        options.add_argument("--disable-popup-blocking") 
        options.add_argument("--disable-notifications")

        # keep same session (recommended for popups)
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--profile-directory=Default")

        #avoid automation detection issue
        options.add_argument("--start-maximized")

        if headless:
            options.add_argument("--headless=new")

        kwargs = {}
        if _HAS_CLOAK:
            options.binary_location = ensure_binary()
            for arg in get_default_stealth_args():
                options.add_argument(arg)
            kwargs["version_main"] = int(get_chromium_version().split(".")[0])

        return uc.Chrome(options=options, **kwargs)


    def random_sleep(self):
        sleep(uniform(1.2, 4.8))


    def _close_browser_safely(self) -> None:
        try:
            if self.driver:
                self.driver.quit()
                self._log("Browser Quited.")

        except Exception:
            pass
        self.driver = None


    def start_automation(self):
        self._log("Automation run started.")

        self.do_login()
        iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src='showTop']")

        if not iframes:
            self.look_for_otp()
        

        airports = self.get_airports()
        self._log(f"Airports: {airports}")
        self.click_reservation()


        for airport in airports['airport']:
            self.perform_search(airport)
            self.look_for_fare(airport)
        
        input("last step performed")
        self._close_browser_safely()


    def do_login(self):
        self._log("doing login...")
        wait = WebDriverWait(self.driver, 30)
        self.random_sleep()
        # 1. Capture main window BEFORE navigation
        main_window = self.driver.current_window_handle
        try:
            self.driver.get("https://agents.airarabia.com/xbe/#")
            self.random_sleep()
            # 3. Wait for new window OR same window redirect
            wait.until(
                lambda d: len(d.window_handles) >= 1
            )
            self.random_sleep()  # allow popup to fully spawn
            # 4. If new window opened → switch
            handles = self.driver.window_handles
            self._log(f"All windows: {handles}")

            if len(handles) > 1:
                for handle in handles:
                    if handle != main_window:
                        self.driver.switch_to.window(handle)
                        break
            else:
                self._log("No popup window, staying in main tab")

            # 5. Confirm current page
            self._log(f"Current URL: {self.driver.current_url}")

            self._log("Switched to popup window:")
            # 1. Switch to iframe
            
            iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src='showTop']")

            if iframes:
                self._log("already login detected")
                return
                
            
            self.type_input(By.ID,"username_txt", self.config.get('email', ''))
            self.type_input(By.ID,"j_password", self.config.get('password', ''))
            
            login_button = wait.until(EC.element_to_be_clickable((By.ID, "btnLogin")))
            self.scroll_to_element(login_button)
            try:
                login_button.click()
            except Exception:
                self.driver.execute_script(
                    "arguments[0].click();",
                    login_button
                )

            self._log("Login successfully.")
            # input("enter to look for otp")
            
            # messagebox.showinfo(
            #     "Please complete Login and click ok",
            #     "Please complete the action in the browser, then click OK."
            # )
        except Exception as e:
            self._log(f"could not login Error: {e}")


        self._log("Login complete")

    def look_for_otp(self):
        self._log("Looking for OTP.")
        wait = WebDriverWait(self.driver, 30)
        # Open Gmail
        self.driver.execute_script("window.open('https://mail.google.com', '_blank');")
        self.driver.switch_to.window(self.driver.window_handles[-1])

        wait.until(
            EC.presence_of_element_located(By.CSS_SELECTOR, "tr.zA.yO")
        )

        emails = self.driver.find_elements(By.CSS_SELECTOR, "tr.zA")
        emails[0].click()

        # extrack OTP
        self.random_sleep()

        body_text = self.driver.find_element(By.CSS_SELECTOR, "div.a3s").text

        otp_match = re.search(r"\b\d{4,8}\b", body_text)

        otp = otp_match.group() if otp_match else None

        print("OTP FOUND:", otp)

        self.driver.switch_to.window(self.driver.window_handles[0])

        otp_input = self.driver.find_element(By.ID, "otp_input")
        otp_input.send_keys(otp)

        self.driver.find_element(By.ID, "verify_button").click()

    def click_reservation(self):
        wait = WebDriverWait(self.driver, 20)
        self._log("searching element")
        self.random_sleep()

        wait.until(
        EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[src='showTop']"))
        )
        # 2. Click Make Reservation
        make_res = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//nobr[text()='Make Reservation']"))
        )

        try:
            make_res.click()
        except:
            self.driver.execute_script("arguments[0].click();", make_res)

        # 3. Back to main page
        # self.driver.switch_to.default_content()

        self.random_sleep()

        self._log("Reservation button clicked.")
        

    def perform_search(self, airport):
        global iframe_found
        try:
            self._log(f"Performing search for {airport}")
            self._log(f"airport from {airport['from']}")
            self.driver.switch_to.default_content()

            self.random_sleep()
            wait = WebDriverWait(self.driver, 15)
            # if not self.iframe_found:
            wait.until(
                EC.frame_to_be_available_and_switch_to_it(
                    (By.CSS_SELECTOR, "iframe[src='showMain']")
                )
            )
            # iframe_found = True

            self.driver.find_element(By.ID, "ext-gen3").click()  # From

            self.random_sleep()

            # self.select_airport("fAirport", self.config.get('from_airport', ''))
            self.select_airport("fAirport", airport['from'])
            self.random_sleep()
            self._log("airport select from complete.")
        
            self.driver.find_element(By.ID, "ext-gen6").click()  # To
        
            
            self.random_sleep()
            # self.select_airport("tAirport", self.config.get('to_airport', ''))
            self.select_airport("tAirport", airport['to'])
            self.random_sleep()

            slot_range = self.config.get("slot_date_range", {})
            departure_date = slot_range.get("from", "").strip()
            converted_departure_date = datetime.strptime(departure_date, "%d/%m/%Y").date()

            if converted_departure_date > date.today():
                self.type_input(By.ID,"departureDate", slot_range.get("from", "").strip())
                self.type_input(By.ID,"returnDate", slot_range.get("to", "").strip())
            else:
                futureDate = date.today() + timedelta(days=3)
                self.type_input(By.ID,"returnDate", futureDate.strftime("%d/%m/%Y"))

            self.driver.find_element(By.ID, "btnSearch").click()
            self.random_sleep()


            self._log("search button clicked ...")
        except Exception as e:
            self._log(f"could not perform search Error: {e}")

    def select_airport(self, field_id, airport_text):
        wait = WebDriverWait(self.driver, 20)

        try:
            # Find airport input
            airport_input = wait.until(
                EC.element_to_be_clickable((By.ID, field_id))
            )

            # Open dropdown
            airport_input.click()
            self.random_sleep()

            # Clear existing value
            airport_input.clear()

            # Type slowly (helps some autocomplete controls)
            for ch in airport_text:
                airport_input.send_keys(ch)
                sleep(0.1)

            self.random_sleep()

            # Wait for dropdown options
            wait.until(
                lambda d: len(
                    d.find_elements(
                        By.CSS_SELECTOR,
                        "div.x-combo-list-item"
                    )
                ) > 0
            )

            options = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.x-combo-list-item"
            )

            # self._log(f"Found {len(options)} options")

            # Print all options for debugging
            # for i, opt in enumerate(options, 1):
            #     if opt.text:
            #         self._log(f"{i}: {opt.text}")

            # Find matching option
            airport_text_upper = airport_text.upper().strip()

            for opt in options:
                option_text = opt.text.strip()
                option_text_upper = option_text.upper()

                # Match partial text
                if airport_text_upper in option_text_upper:
                    if option_text:
                        self._log(
                            f"Matching airport found: {option_text}"
                        )

                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});",
                            opt
                        )

                    self.random_sleep()

                    try:
                        opt.click()
                    except Exception:
                        self.driver.execute_script(
                            "arguments[0].click();",
                            opt
                        )

                    self._log(
                        f"Selected airport: {option_text}"
                    )

                    return True

            self._log(
                f"Airport not found: {airport_text}"
            )

            return False

        except Exception as e:
            self._log(
                f"Error selecting airport '{airport_text}': {e}"
            )

            return False


    def look_for_fare(self, airport):
        max_days = int(airport['days_to_check'])
        # max_days = self.config.get("check_for_days", "")
        self._log(f"Finding suitable fare for {max_days} days...")
        wait = WebDriverWait(self.driver, 20)
        self.fare_counts = Counter()

        for day in range(max_days):
            self._log(f"Checking day {day + 1}/{max_days}")
            self.random_sleep()
            out_price = None
            in_price = None

            # --------------------------
            # STEP 1: OUTBOUND FLIGHT
            # --------------------------
            try:
                out_table = self.driver.find_element(By.ID, "tblOutboundFlights")
                first_row = out_table.find_element(By.CSS_SELECTOR, "tr")
                departure_out = first_row.find_element(By.XPATH, "./td[5]").text
                self._log(f"departure time: {departure_out}")
                # input("departure out time found")

                # arrival_out = first_row.find_element(By.XPATH, "./td[6]").text
                # self._log(f"arrival time: {arrival_out}")
                # input("arival in time found")
                first_row.click()
                self.random_sleep()
                out_price = int(self.driver.find_element(
                    By.XPATH,
                    "//span[@id='bundleNameId' and normalize-space()='Basic']"
                    "/ancestor::tr//div[@class='priceBg']/b"
                ).text)
                self._log(f"Price found: {out_price}")
                # input(f"{day + 1} Outbound found")
            except Exception:
                self._log("Outbound not found → clicking next day")
                # input(f"{day + 1} Outbound not found")

                self._click_next_day(wait)
                continue


            # --------------------------
            # STEP 2: INBOUND FLIGHT
            # --------------------------
            try:
                self.random_sleep()
                in_table = self.driver.find_element(By.ID, "tblInboundFlights")
                first_row_in = in_table.find_element(By.CSS_SELECTOR, "tr")
                departure_in = first_row_in.find_element(By.XPATH, "./td[5]").text
                self._log(f"departure time Inbound: {departure_in}")
                # input("departure time found")

                # arrival = first_row_in.find_element(By.XPATH, "./td[6]").text
                # self._log(f"arrival time: {arrival}")
                # input("arival time found")

                first_row_in.click()
                self.random_sleep()
                self._log("Inbound clicked")
                in_price = int(in_table.find_elements(By.CLASS_NAME, "priceBg")[0].find_element(By.TAG_NAME, "b").text)
                self._log(f"{day + 1} Price is {in_price}")


            except Exception:
                self._log("Inbound not found → clicking next day")
                # input(f"{day + 1} Inbound not found")

                self._click_next_day(wait)
                continue


            # --------------------------
            # STEP 3: VALID RESULT
            # --------------------------
            self.random_sleep()
            flight_price = out_price + in_price
            self.fare_counts[flight_price] += 1

            self._log(f"Day {day + 1} fare: {flight_price}")
            if flight_price <= float(airport['promo_fare']):
                self._log("posting fare price")
                depart = datetime.strptime(departure_out, "%a %d%b%y %H:%M")
                arriv = datetime.strptime(departure_in, "%a %d%b%y %H:%M")

                prams = {
                    "from": airport['from'],
                    "to": airport['to'],
                    "departure": depart.strftime("%Y-%m-%d %H:%M:%S"),
                    "return": arriv.strftime("%Y-%m-%d %H:%M:%S"),
                    "fare": flight_price,
                    "airport_id": airport['id'],
                }
                posting = [
                    "http://localhost/fasttrack_perfex/holiday/api/update_fare",
                    # "https://fasttracktourism.emmartax.com/holiday/api/update_fare",
                    # "https://pinastraveltourism.emmartax.com/holiday/api/update_fare",
                    # "https://kabayantraveltourism.emmartax.com/holiday/api/update_fare",
                ]
                headers = {
                    "X-API-KEY": "eyJ1c2VybmFtZSI6ImluZm8uZ3N0c3ZuMTEwOEBnbWFpbC5jb20iLCJw8uZ3N0c3ZuMTEwYXNzd29yZCI6IjEyMzQ1NmFAIiwiQVBJX1RJTUUiOjE1NzQzOTU4NTl9",
                    "Accept": "application/json"
                }
                for post in posting:
                    response = requests.get(
                        post,
                        params=prams,
                        headers=headers
                    )
                    self._log(f"api response {response}")
                    self.random_sleep()

            # input(f"first api posted Response: {response}")
            self.random_sleep()

            self._click_next_day(wait)
            # input(f"{day + 1} loop finished")

            

        for fare, count in sorted(self.fare_counts.items()):
            self._log(f"AED {fare} found {count} times in {max_days} days")
        if self.fare_counts:
            cheapest = min(self.fare_counts)
            self._log(
                f"Cheapest fare: AED {cheapest} "
                f"(found {self.fare_counts[cheapest]} times)"
            )

        return cheapest
    

    def _click_next_day(self, wait):
        try:
            btn_out = wait.until(
                EC.element_to_be_clickable((By.ID, "lnkON"))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});",
                btn_out
            )
            btn_out.click()

            sleep(1)

            btn_in = wait.until(
                EC.element_to_be_clickable((By.ID, "lnkRN"))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});",
                btn_in
            )
            btn_in.click()

            self._log("Moved to next day")

            sleep(3)

        except Exception as e:
            self._log(f"Next day click failed: {e}")
       

    def scroll_to_element(self, element):
            self.driver.execute_script("""arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center'});""", element)
            self.random_sleep()

    def type_input(self, by, value, text):
        wait = WebDriverWait(self.driver, 20)
        element = wait.until(EC.presence_of_element_located((by, value)))
        self.scroll_to_element(element)

        element.clear()
        for ch in text:
            element.send_keys(ch)
            sleep(0.15)

        self.random_sleep()

    def select_dropdown(self, dropdown_id, option_text):
        wait = WebDriverWait(self.driver, 20)
        dropdown = wait.until(EC.element_to_be_clickable((By.ID, dropdown_id)))

        self.scroll_to_element(dropdown)
        self.driver.execute_script("arguments[0].click();",dropdown)

        self.random_sleep()

        # Search all visible options
        options = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "mat-option")))
        for option in options:
            text = option.text.strip()

            if option_text.strip().lower() == text.lower():                
                self.scroll_to_element(option)
                self.driver.execute_script("arguments[0].click();",option)
                self.random_sleep()
                return
            
        raise Exception(f"Option '{option_text}' not found in dropdown '{dropdown_id}'.")   


    def read_json(self, file_path):
        """ Read JSON configuration file."""

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception:
            return {}
    
    def get_airports(self):
        self._log(f"getting airports")
        
        headers = {
            "X-API-KEY": "eyJ1c2VybmFtZSI6ImluZm8uZ3N0c3ZuMTEwOEBnbWFpbC5jb20iLCJw8uZ3N0c3ZuMTEwYXNzd29yZCI6IjEyMzQ1NmFAIiwiQVBJX1RJTUUiOjE1NzQzOTU4NTl9",
            "Accept": "application/json"
        }

        try:
            response = requests.get(
                'http://localhost/fasttrack_perfex/holiday/api/get_airports',
                # 'https://fasttracktourism.emmartax.com/holiday/api/get_airports',
                headers=headers,
                timeout=30

            )
            airports = response.json()
            self._log(f"airports found: {airports}")
            return airports
        except Exception as e:
            self._log(f"Error: {e}")


        



if __name__ == "__main__":
    print("[Air Arabia Bot] Launching Automation...")
    automation = Automation()
    print("[Air Arabia Bot] Session ended.")

