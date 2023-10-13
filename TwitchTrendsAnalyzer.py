import requests
import pandas as pd
import time
import locale
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Set locale to Portuguese to format the currency correctly
locale.setlocale(locale.LC_MONETARY, 'pt_BR.UTF-8')

def fetch_twitch_data("https://streamscharts.com/trends/games"):
    chrome_options = Options()
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    
    driver = None
    attempts = 0
    
    while driver is None and attempts < 3:
        try:
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
            driver.get("https://streamscharts.com/trends/games")
            wait = WebDriverWait(driver, 30)  # Esperar até 30 segundos
            game_elements = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tr'))
            )
            print(f"Found {len(game_elements)} 'tr' elements")
        except Exception as e:
            print(f"An error occurred: {str(e)}. Retrying...")
            attempts += 1
    
    if driver is None:
        print("Failed to create a Chrome instance after 3 attempts.")
        return None
        
    data = []
    try:
        game_elements = driver.find_elements(By.CSS_SELECTOR, 'tr')
        print(f"Found {len(game_elements)} 'tr' elements")
        
        for game in game_elements[1:]:
            game_title_element = game.find_element(By.CSS_SELECTOR, 'div.truncate a')
            game_title = game_title_element.text.strip()
            data.append({'Game Title': game_title})
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        driver.quit()
    
    return pd.DataFrame(data)

def save_to_txt(data, filepath='games_data.txt'):
    with open(filepath, 'w', encoding='utf-8') as file:
        for index, row in data.iterrows():
            file.write(f"{row['Game Title']}, {row.get('Steam AppID', '')}\n")

def load_from_txt(filepath='games_data.txt'):
    data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line in file:
                game_title, _, steam_id = line.partition(',')
                data.append({'Game Title': game_title.strip(), 'Steam AppID': steam_id.strip()})
        return pd.DataFrame(data)
    except FileNotFoundError:
        return pd.DataFrame(columns=['Game Title', 'Steam AppID'])

def update_game_data(new_data, filepath='games_data.txt'):
    existing_data = load_from_txt(filepath)
    
    merged_data = pd.merge(new_data, existing_data, on='Game Title', how='left')
    old_games = existing_data[~existing_data['Game Title'].isin(merged_data['Game Title'])]
    updated_data = pd.concat([merged_data, old_games], ignore_index=True)
    
    save_to_txt(updated_data, filepath)
    return updated_data

def fetch_steam_price(app_id):
    if pd.isna(app_id) or app_id == 'nan':
        return "Não distribuído pela Steam ou Código desatualizado"
    
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
        response = requests.get(url)
        data = response.json()
        
        if data[str(app_id)]['success']:
            if data[str(app_id)]['data']['is_free']:
                price = "F2P (Free to Play)"
            elif 'price_overview' in data[str(app_id)]['data']:
                price = float(data[str(app_id)]['data']['price_overview']['final']) / 100
                price = locale.currency(price, grouping=True, symbol=True)
            else:
                price = "Não distribuído pela Steam ou Código desatualizado"
        else:
            price = "Não distribuído pela Steam ou Código desatualizado"
    except Exception as e:
        print(f"Error fetching price for app ID {app_id}: {str(e)}")
        price = "Error fetching price"
    
    return price

def send_to_discord(data, webhook_url):
    message = "```"
    
    for index, row in data.iterrows():
        line = f"{row['Game Title']} - {row['Steam AppID']} - {row['Price']}\n"
        message += line
    
    message += "```"
    
    payload = {"content": message}
    response = requests.post(webhook_url, data=payload)
    
    if response.status_code == 204:
        print("Message sent to Discord successfully!")
    else:
        print(f"Failed to send message to Discord: {response.status_code}")

# URL
twitch_url = "https://streamscharts.com/trends/games"

# Step 1: Extract game titles
twitch_data = fetch_twitch_data(twitch_url)

# Step 2: Update game data with existing data
if twitch_data is not None and not twitch_data.empty:
    updated_data = update_game_data(twitch_data)

    # Step 3: Fetch prices from Steam API
    prices = []
    for _, row in updated_data.iterrows():
        app_id = row['Steam AppID']
        price = fetch_steam_price(app_id)
        prices.append(price)
    
    updated_data['Price'] = prices
    
    # Replace YOUR_WEBHOOK_URL with your actual webhook URL.
    YOUR_WEBHOOK_URL = "https://discord.com/api/webhooks/1162473309770887309/MmzFWifVrshcZcdZZeJIF79TYKU0oQsIr1jpYxDUtufBF2SyaiZvSZYtO3fBdT2WjVgR"
    send_to_discord(updated_data, YOUR_WEBHOOK_URL)
else:
    print("No data to send.")
