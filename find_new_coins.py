import requests
import json
import logging
import os
from time import sleep
from pymongo.errors import ConnectionFailure
from utils import get_mongo_client  # Assuming you have this function to get a MongoDB client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# CoinGecko API endpoints
COINS_LIST_URL = 'https://api.coingecko.com/api/v3/coins/list'
COIN_DETAILS_URL = 'https://api.coingecko.com/api/v3/coins/{}'

# Rate limit parameters
CALLS_PER_MINUTE = 50  # CoinGecko allows up to 50 calls per minute for free users
DELAY_BETWEEN_CALLS = 60 / CALLS_PER_MINUTE  # Calculate delay in seconds

# Cache file path
CACHE_FILE = 'cache/all_coins_cache.json'
DB_NAME = 'memecoin_radar'
MEMECOINS_COLLECTION = 'memecoins'

def load_cache():
    """Load the cache of processed coin IDs from a file. Create the file if it doesn't exist."""
    if not os.path.exists(CACHE_FILE):
        # Create an empty cache file
        with open(CACHE_FILE, 'w') as file:
            json.dump([], file)
        logging.info(f"Cache file '{CACHE_FILE}' created.")
        return []
    else:
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
    """Main function to check for new coins, update the cache, identify meme coins, and store them in MongoDB."""
    # Load the cache of previously processed coins
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

    # Add new coins to the cache
    updated_cache = cached_coins + new_coins
    save_cache(updated_cache)

    # Connect to MongoDB
    try:
        client = get_mongo_client()
        db = client[DB_NAME]
        memecoins_col = db[MEMECOINS_COLLECTION]
    except ConnectionFailure:
        logging.error("MongoDB client is not available. Skipping MongoDB storage.")
        client = None

    # Check each new coin to see if it's a meme coin
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

        # Check if the coin is a meme coin
        if is_meme_coin(coin_details):
            logging.info(f"New meme coin found: {coin_name} ({coin_symbol}) with ID {coin_id}")
            # Store the meme coin details in the database if MongoDB client is available
            if client:
                try:
                    memecoins_col.insert_one(coin_details)
                    logging.info(f"Stored meme coin: {coin_name} ({coin_symbol}) in the database.")
                except Exception as e:
                    logging.error(f"Error storing coin in MongoDB: {e}")

        # Respect rate limits
        sleep(DELAY_BETWEEN_CALLS)

if __name__ == "__main__":
    main()
