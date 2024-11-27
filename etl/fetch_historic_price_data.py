import json
import time
import logging
import requests
from datetime import datetime
from tqdm import tqdm
from path_setup import setup_project_root
from tools.utils import get_mongo_client

setup_project_root()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set your rate limit parameters
CALLS_PER_MINUTE = 30
DELAY_BETWEEN_CALLS = 60 / CALLS_PER_MINUTE  # Calculate delay in seconds
MAX_RETRIES = 5  # Maximum number of retries for a request
RETRY_DELAY = 5  # Initial delay between retries in seconds (increases exponentially)

def get_stored_coins():
    """Retrieve all stored coins from the 'memecoins' collection."""
    try:
        client = get_mongo_client()
        db = client['memecoin_radar']
        collection = db['memecoins']
        coins = collection.find({}, {"_id": 0, "id": 1})  # Fetch coin IDs
        coin_ids = [coin['id'] for coin in coins]
        logging.info(f"Retrieved {len(coin_ids)} coins from the 'memecoins' collection.")
        return coin_ids
    except Exception as e:
        logging.error(f"An error occurred while retrieving coins from the database: {e}")
        return []
    finally:
        client.close()

def check_if_data_exists(coin_id):
    """Check if data for the given coin_id already exists in the 'prices' collection."""
    try:
        client = get_mongo_client()
        db = client['memecoin_radar']
        collection = db['prices']
        exists = collection.count_documents({"coin_id": coin_id}) > 0
        return exists
    except Exception as e:
        logging.error(f"An error occurred while checking existing data for coin '{coin_id}': {e}")
        return False
    finally:
        client.close()

def fetch_historical_data(coin_id):
    """Fetch historical daily price data for a given coin with retry mechanism."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": "30",
        "interval": "daily"
    }
    retries = 0

    while retries < MAX_RETRIES:
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if response.status_code == 429:  # Too Many Requests
                retries += 1
                wait_time = RETRY_DELAY * (2 ** (retries - 1))  # Exponential backoff
                logging.warning(f"Rate limit exceeded for '{coin_id}'. Retrying in {wait_time} seconds... (Attempt {retries}/{MAX_RETRIES})")
                time.sleep(wait_time)
            else:
                logging.error(f"Failed to fetch data for coin '{coin_id}': {e}")
                break
    logging.error(f"Exceeded max retries for coin '{coin_id}'.")
    return None

def process_historical_data(coin_id, data):
    """Process historical data into a structured format."""
    if not data:
        logging.warning(f"No data to process for coin '{coin_id}'.")
        return []

    prices = data.get('prices', [])
    market_caps = data.get('market_caps', [])
    total_volumes = data.get('total_volumes', [])

    if not (len(prices) == len(market_caps) == len(total_volumes)):
        logging.error(f"Data lists are not of the same length for coin '{coin_id}'.")
        return []

    records = []
    for i in range(len(prices)):
        timestamp_ms = prices[i][0]
        date = datetime.utcfromtimestamp(timestamp_ms / 1000)  # Convert ms to seconds
        record = {
            'coin_id': coin_id,
            'date': date,
            'price': prices[i][1],
            'market_cap': market_caps[i][1],
            'total_volume': total_volumes[i][1]
        }
        records.append(record)

    logging.info(f"Processed {len(records)} records for coin '{coin_id}'.")
    return records

def insert_data_into_db(records):
    """Insert processed records into the 'prices' collection in MongoDB."""
    if not records:
        logging.warning("No records to insert into the database.")
        return

    try:
        client = get_mongo_client()
        db = client['memecoin_radar']
        collection = db['prices']
        collection.insert_many(records)
        logging.info(f"Inserted {len(records)} records into the 'prices' collection.")
    except Exception as e:
        logging.error(f"An error occurred while inserting data into MongoDB: {e}")
    finally:
        client.close()

def main():
    """Main function to orchestrate the retrieval, processing, and storage of historical data."""
    coin_ids = get_stored_coins()
    if not coin_ids:
        logging.error("No coins found in the 'memecoins' collection.")
        return

    for coin_id in tqdm(coin_ids, desc="Fetching historical data for coins"):
        # Skip coins that already have data in the 'prices' collection
        if check_if_data_exists(coin_id):
            logging.info(f"Data for coin '{coin_id}' already exists. Skipping...")
            continue

        # Fetch historical data
        data = fetch_historical_data(coin_id)
        if data:
            # Process data
            records = process_historical_data(coin_id, data)
            # Insert data into the database
            insert_data_into_db(records)
        # Add a delay to respect the rate limit between calls
        logging.info(f"Waiting for {DELAY_BETWEEN_CALLS} seconds to respect rate limit...")
        time.sleep(DELAY_BETWEEN_CALLS)

if __name__ == "__main__":
    main()
