import requests
import logging
import time
from tools.utils import get_mongo_client

# Configure logging
logging.basicConfig(level=logging.INFO)

def fetch_memecoins():
    """Fetch all memecoins from CoinGecko."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "meme-token",
        "order": "market_cap_desc",
        "per_page": 250,  # Maximum per page
        "page": 1,
        "sparkline": "false"
    }
    all_memecoins = []
    while True:
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if not data:
                break
            all_memecoins.extend(data)
            logging.info(f"Fetched page {params['page']} with {len(data)} memecoins.")
            params["page"] += 1
            time.sleep(12)  # Delay to respect rate limits
        except requests.exceptions.RequestException as e:
            logging.error(f"An error occurred while fetching data: {e}")
            break
    return all_memecoins

def extract_fields(memecoins):
    """Extract specific fields from the fetched memecoins data."""
    extracted_data = []
    for coin in memecoins:
        extracted_data.append({
            "id": coin.get("id"),
            "symbol": coin.get("symbol"),
            "name": coin.get("name"),
            "image": coin.get("image"),
            "max_supply": coin.get("max_supply")
        })
    return extracted_data

def store_in_mongodb(data):
    """Store the extracted data in the MongoDB collection."""
    client = get_mongo_client()
    db = client["memecoin_radar"]
    collection = db["memecoins"]
    try:
        # Insert data into the collection
        if data:
            collection.insert_many(data)
            logging.info(f"Inserted {len(data)} documents into the 'memecoins' collection.")
        else:
            logging.info("No data to insert.")
    except Exception as e:
        logging.error(f"An error occurred while inserting data into MongoDB: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    memecoins = fetch_memecoins()
    if memecoins:
        extracted_data = extract_fields(memecoins)
        store_in_mongodb(extracted_data)
    else:
        logging.info("No memecoins data fetched.")
