import requests
import json
import logging
import os
from time import sleep
from pymongo.errors import ConnectionFailure
from path_setup import setup_project_root
from tools.utils import get_mongo_client

setup_project_root()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# CoinGecko API endpoints
COINS_LIST_URL = 'https://api.coingecko.com/api/v3/coins/list'
COIN_DETAILS_URL = 'https://api.coingecko.com/api/v3/coins/{}'

# Cache file path
CACHE_FILE = './cache/all_coins_cache.json'
DB_NAME = 'memecoin_radar'
MEMECOINS_COLLECTION = 'memecoins'

def load_cache():
    """Load the cache of processed coin IDs from a file."""
    if not os.path.exists(CACHE_FILE):
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, 'w') as file:
            json.dump([], file)
        logging.info(f"Cache file '{CACHE_FILE}' created.")
        return []
    with open(CACHE_FILE, 'r') as file:
        return json.load(file)

def save_cache(coins):
    """Save the list of coins to a cache file."""
    with open(CACHE_FILE, 'w') as file:
        json.dump(coins, file)
    logging.info(f"Saved {len(coins)} coins to the cache file: {CACHE_FILE}")

def fetch_all_coins():
    """Fetch the complete list of coins from CoinGecko."""
    try:
        response = requests.get(COINS_LIST_URL)
        response.raise_for_status()
        coins = response.json()
        logging.info(f"Fetched {len(coins)} coins from CoinGecko.")
        return coins
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from CoinGecko: {e}")
        return []

def fetch_coin_details(coin_id):
    """Fetch detailed information for a specific coin."""
    try:
        response = requests.get(COIN_DETAILS_URL.format(coin_id))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching details for coin '{coin_id}': {e}")
        return None

def is_meme_coin(coin_details):
    """Determine if a coin is a meme coin based on its categories."""
    categories = coin_details.get('categories', [])
    return 'Meme' in categories

def main():
    """Main function to check for new coins, update the cache, and store meme coins in MongoDB."""
    cached_coins = load_cache()
    cached_coin_ids = {coin['id'] for coin in cached_coins}

    # Fetch the latest list of coins
    all_coins = fetch_all_coins()
    if not all_coins:
        logging.error("No coins fetched from CoinGecko.")
        return

    # Identify new coins not present in the cache
    new_coins = [coin for coin in all_coins if coin['id'] not in cached_coin_ids]
    if not new_coins:
        logging.info("No new coins found. Ending the process.")
        return

    logging.info(f"Identified {len(new_coins)} new coins.")
    updated_cache = cached_coins + new_coins
    save_cache(updated_cache)

    # Connect to MongoDB
    try:
        client = get_mongo_client()
        db = client[DB_NAME]
        memecoins_col = db[MEMECOINS_COLLECTION]
    except ConnectionFailure:
        logging.error("MongoDB client is not available. Exiting.")
        return

    # Check each new coin
    for coin in new_coins:
        coin_id = coin.get('id')
        coin_name = coin.get('name')
        coin_symbol = coin.get('symbol')
        if not coin_id:
            continue

        # Fetch coin details
        coin_details = fetch_coin_details(coin_id)
        if not coin_details:
            continue

        # Check if it's a meme coin
        if is_meme_coin(coin_details):
            logging.info(f"New meme coin found: {coin_name} ({coin_symbol}) with ID {coin_id}")
            try:
                memecoins_col.insert_one(coin_details)
                logging.info(f"Stored meme coin: {coin_name} ({coin_symbol}) in the database.")
            except Exception as e:
                logging.error(f"Error storing coin in MongoDB: {e}")

        # Add a 20-second delay after processing each coin
        sleep(20)

if __name__ == "__main__":
    main()
