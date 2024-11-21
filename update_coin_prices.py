import time
import logging
import requests
from datetime import datetime, timedelta
from pymongo.errors import BulkWriteError
from tqdm import tqdm
from utils import get_mongo_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
DB_NAME = "memecoin_radar"
PRICES_COLLECTION = "prices"
MEMECOINS_COLLECTION = "memecoins"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3/coins/{}/history"
CALLS_PER_MINUTE = 30
DELAY_BETWEEN_CALLS = 60 / CALLS_PER_MINUTE
MAX_RETRIES = 5
RETRY_DELAY = 5

def get_stored_coins():
    """Retrieve all stored coin IDs from the 'memecoins' collection."""
    try:
        client = get_mongo_client()
        db = client[DB_NAME]
        collection = db[MEMECOINS_COLLECTION]
        coins = collection.find({}, {"_id": 0, "id": 1})
        return [coin['id'] for coin in coins]
    except Exception as e:
        logging.error(f"An error occurred while retrieving coins: {e}")
        return []
    finally:
        client.close()

def get_latest_date(coin_id):
    """Retrieve the latest date for a given coin in the 'prices' collection."""
    try:
        client = get_mongo_client()
        db = client[DB_NAME]
        collection = db[PRICES_COLLECTION]
        latest_record = collection.find_one({"coin_id": coin_id}, sort=[("date", -1)])
        return latest_record['date'] if latest_record else None
    except Exception as e:
        logging.error(f"Error retrieving latest date for coin '{coin_id}': {e}")
        return None
    finally:
        client.close()

def generate_missing_dates(latest_date):
    """Generate a list of dates from the day after the latest date up to today."""
    if latest_date:
        start_date = latest_date + timedelta(days=1)
    else:
        start_date = datetime.utcnow() - timedelta(days=30)
    end_date = datetime.utcnow()
    return [start_date + timedelta(days=i) for i in range((end_date - start_date).days)]

def fetch_data_for_date(coin_id, date):
    """Fetch historical data for a coin on a specific date with retry mechanism."""
    url = COINGECKO_API_URL.format(coin_id)
    params = {"date": date.strftime('%d-%m-%Y'), "localization": "false"}
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
                logging.warning(f"Rate limit exceeded for '{coin_id}' on {date}. Retrying in {wait_time} seconds... (Attempt {retries}/{MAX_RETRIES})")
                time.sleep(wait_time)
            else:
                logging.error(f"Failed to fetch data for coin '{coin_id}' on {date}: {e}")
                break
    logging.error(f"Exceeded max retries for coin '{coin_id}' on {date}.")
    return None

def process_data(coin_id, date, data):
    """Process the fetched data into the desired format."""
    if not data or 'market_data' not in data:
        return None
    market_data = data['market_data']
    return {
        'coin_id': coin_id,
        'date': date,
        'price': market_data['current_price'].get('usd'),
        'market_cap': market_data['market_cap'].get('usd'),
        'total_volume': market_data['total_volume'].get('usd')
    }

def insert_data(records):
    """Insert records into the 'prices' collection."""
    if not records:
        return
    try:
        client = get_mongo_client()
        db = client[DB_NAME]
        collection = db[PRICES_COLLECTION]
        for record in records:
            collection.update_one(
                {'coin_id': record['coin_id'], 'date': record['date']},
                {'$set': record},
                upsert=True
            )
            logging.info(f"Upserted record for {record['coin_id']} on {record['date']}.")
    except Exception as e:
        logging.error(f"Error inserting data into MongoDB: {e}")
    finally:
        client.close()


def main():
    """Main function to update the 'prices' collection with missing data."""
    coin_ids = get_stored_coins()
    for coin_id in tqdm(coin_ids, desc="Updating coins"):
        latest_date = get_latest_date(coin_id)
        missing_dates = generate_missing_dates(latest_date)
        records = []
        for date in missing_dates:
            data = fetch_data_for_date(coin_id, date)
            record = process_data(coin_id, date, data)
            if record:
                records.append(record)
            else:
                logging.warning(f"No data retrieved for coin '{coin_id}' on {date}.")
            time.sleep(DELAY_BETWEEN_CALLS)  # Respect rate limit
        insert_data(records)

if __name__ == "__main__":
    main()
