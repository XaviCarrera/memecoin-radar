import json
import time
import logging
import requests
from datetime import datetime, timedelta
from pymongo.errors import ConnectionFailure
from tqdm import tqdm
from utils import get_mongo_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set API endpoints and rate limit parameters
COIN_PRICE_URL = "https://api.coingecko.com/api/v3/coins/{}/market_chart/range"
CALLS_PER_MINUTE = 30
DELAY_BETWEEN_CALLS = 60 / CALLS_PER_MINUTE  # Calculate delay in seconds
MAX_RETRIES = 5  # Maximum number of retries for a request
RETRY_DELAY = 5  # Initial delay between retries in seconds (increases exponentially)

def get_stored_meme_coins():
    """Retrieve all meme coins from the 'memecoins' collection."""
    try:
        client = get_mongo_client()
        db = client['memecoin_radar']
        collection = db['memecoins']
        coins = collection.find({}, {"_id": 0, "id": 1})  # Fetch coin IDs
        coin_ids = [coin['id'] for coin in coins]
        logging.info(f"Retrieved {len(coin_ids)} meme coins from the 'memecoins' collection.")
        return coin_ids
    except Exception as e:
        logging.error(f"An error occurred while retrieving meme coins from the database: {e}")
        return []
    finally:
        client.close()

def get_last_update_date(coin_id):
    """Retrieve the last update date for a given coin from the 'prices' collection."""
    try:
        client = get_mongo_client()
        db = client['memecoin_radar']
        collection = db['prices']
        latest_record = collection.find_one({"coin_id": coin_id}, sort=[("date", -1)])
        if latest_record:
            return latest_record['date']
        return None
    except Exception as e:
        logging.error(f"An error occurred while retrieving the last update date for coin '{coin_id}': {e}")
        return None
    finally:
        client.close()

def fetch_historical_data(coin_id, start_date, end_date):
    """Fetch historical daily price data for a given coin between start_date and end_date with retry mechanism."""
    url = COIN_PRICE_URL.format(coin_id)
    params = {
        "vs_currency": "usd",
        "from": start_date.timestamp(),
        "to": end_date.timestamp()
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
    """Main function to update historical data for stored meme coins."""
    coin_ids = get_stored_meme_coins()
    if not coin_ids:
        logging.error("No meme coins found in the 'memecoins' collection.")
        return

    for coin_id in tqdm(coin_ids, desc="Updating prices for meme coins"):
        # Get the last update date
        last_update_date = get_last_update_date(coin_id)
        if last_update_date:
            if isinstance(last_update_date, str):
                last_update_date = datetime.strptime(last_update_date, '%Y-%m-%d')
            start_date = last_update_date + timedelta(days=1)
        else:
            # If no data exists, start from 30 days ago
            start_date = datetime.utcnow() - timedelta(days=30)

        end_date = datetime.utcnow()

        # Fetch historical data
        data = fetch_historical_data(coin_id, start_date, end_date)
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
