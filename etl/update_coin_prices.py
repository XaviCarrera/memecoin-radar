import time
import logging
import requests
from datetime import datetime, timedelta
from pymongo.errors import BulkWriteError
from tqdm import tqdm
from path_setup import setup_project_root
from tools.utils import get_mongo_client

setup_project_root()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
DB_NAME = "memecoin_radar"
PRICES_COLLECTION = "prices"
COINGECKO_API_URL_RANGE = "https://api.coingecko.com/api/v3/coins/{}/market_chart/range"
CALLS_PER_MINUTE = 30
DELAY_BETWEEN_CALLS = 60 / CALLS_PER_MINUTE
MAX_RETRIES = 5
RETRY_DELAY = 5

def get_coins_sorted_by_market_cap():
    """Retrieve all coin IDs and their latest market cap, then sort by market cap descending."""
    try:
        client = get_mongo_client()
        db = client[DB_NAME]
        collection = db[PRICES_COLLECTION]
        
        # Aggregate to get the latest market cap for each coin
        pipeline = [
            {
                '$sort': {'date': -1}  # Sort by date descending
            },
            {
                '$group': {
                    '_id': '$coin_id',
                    'latest_market_cap': {'$first': '$market_cap'},
                    'latest_date': {'$first': '$date'}
                }
            },
            {
                '$sort': {'latest_market_cap': -1}
            }
        ]
        
        results = list(collection.aggregate(pipeline))
        # Convert results to a list of dictionaries
        coins = [{'coin_id': res['_id'], 'latest_market_cap': res['latest_market_cap'], 'latest_date': res['latest_date']} for res in results]
        return coins
    except Exception as e:
        logging.error(f"An error occurred while retrieving coins: {e}")
        return []
    finally:
        client.close()

def get_oldest_date(coin_id):
    """Retrieve the oldest date for a given coin in the 'prices' collection."""
    try:
        client = get_mongo_client()
        db = client[DB_NAME]
        collection = db[PRICES_COLLECTION]
        oldest_record = collection.find_one({"coin_id": coin_id}, sort=[("date", 1)])
        return oldest_record['date'] if oldest_record else None
    except Exception as e:
        logging.error(f"Error retrieving oldest date for coin '{coin_id}': {e}")
        return None
    finally:
        client.close()

def fetch_data_for_range(coin_id, from_timestamp, to_timestamp):
    """Fetch historical data for a coin over a range of dates."""
    url = COINGECKO_API_URL_RANGE.format(coin_id)
    params = {
        "vs_currency": "usd",
        "from": from_timestamp,
        "to": to_timestamp
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

def process_range_data(coin_id, data):
    """Process the fetched range data into the desired format."""
    if not data:
        return []
    prices = data.get('prices', [])
    market_caps = data.get('market_caps', [])
    total_volumes = data.get('total_volumes', [])

    records = []
    # Create a mapping from timestamp to data
    price_dict = {int(price[0]/1000): price[1] for price in prices}
    market_cap_dict = {int(mc[0]/1000): mc[1] for mc in market_caps}
    total_volume_dict = {int(tv[0]/1000): tv[1] for tv in total_volumes}

    # Get all timestamps
    timestamps = set(price_dict.keys()) | set(market_cap_dict.keys()) | set(total_volume_dict.keys())

    for ts in timestamps:
        date = datetime.utcfromtimestamp(ts).replace(hour=0, minute=0, second=0, microsecond=0)
        record = {
            'coin_id': coin_id,
            'date': date,
            'price': price_dict.get(ts),
            'market_cap': market_cap_dict.get(ts),
            'total_volume': total_volume_dict.get(ts)
        }
        records.append(record)
    return records

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
    coins_info = get_coins_sorted_by_market_cap()
    if not coins_info:
        logging.error("No coins found in the prices collection.")
        return

    reference_coin = coins_info[0]
    reference_coin_id = reference_coin['coin_id']
    reference_oldest_date = get_oldest_date(reference_coin_id)
    if not reference_oldest_date:
        logging.error(f"No records found for reference coin '{reference_coin_id}'.")
        return

    for coin_info in tqdm(coins_info, desc="Updating coins"):
        coin_id = coin_info['coin_id']
        latest_date = coin_info['latest_date']

        if coin_id != reference_coin_id and latest_date < reference_oldest_date:
            logging.info(f"Skipping coin '{coin_id}' as its latest date {latest_date} is older than reference oldest date {reference_oldest_date}.")
            continue

        # If no latest date, fetch data from 30 days ago
        if latest_date:
            from_timestamp = int(latest_date.timestamp())
        else:
            from_timestamp = int((datetime.utcnow() - timedelta(days=30)).timestamp())
        to_timestamp = int(datetime.utcnow().timestamp())

        data = fetch_data_for_range(coin_id, from_timestamp, to_timestamp)
        records = process_range_data(coin_id, data)
        insert_data(records)
        time.sleep(DELAY_BETWEEN_CALLS)  # Respect rate limit

if __name__ == "__main__":
    main()
