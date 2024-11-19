from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Union
from utils import get_mongo_client  # Assuming this is correctly imported
from datetime import datetime, timedelta
import re

# Initialize FastAPI app
app = FastAPI()

# MongoDB configuration
DB_NAME = "memecoin_radar"
PRICES_COLLECTION = "prices"

# Define response models
class CoinData(BaseModel):
    symbol: str
    last_price: Union[float, str]
    market_cap: Union[float, str]

class TopCoinsResponse(BaseModel):
    total_market_cap: float
    top_10_coins: List[CoinData]

class PriceHistoryData(BaseModel):
    date: str  # ISO formatted date string
    price: float

class PercentageChangeData(BaseModel):
    symbol: str
    percentage_change: float
    price_history: List[PriceHistoryData]

class TopMoversResponse(BaseModel):
    top_movers: List[PercentageChangeData]

def clean_numeric_string(value):
    if isinstance(value, str):
        # Remove any commas or non-numeric characters except periods and minus signs
        value = re.sub(r'[^\d\.\-]', '', value)
    return value

@app.get("/top-coins", response_model=TopCoinsResponse)
async def top_coins():
    """Endpoint to fetch the top 10 meme coins by market cap."""
    client = get_mongo_client()
    try:
        db = client[DB_NAME]
        collection = db[PRICES_COLLECTION]

        # Use aggregation to get the latest document for each coin
        pipeline = [
            {
                "$sort": {"date": -1}  # Sort by date in descending order
            },
            {
                "$group": {
                    "_id": "$coin_id",
                    "symbol": {"$first": "$coin_id"},
                    "market_cap": {"$first": "$market_cap"},
                    "last_price": {"$first": "$price"}
                }
            }
        ]
        coins = list(collection.aggregate(pipeline))

        if not coins:
            raise HTTPException(status_code=404, detail="No meme coins found in the database.")

        # Process each coin
        for coin in coins:
            # Process 'market_cap'
            market_cap_value = coin.get('market_cap', 0)
            market_cap_value = clean_numeric_string(market_cap_value)
            try:
                coin['market_cap'] = float(market_cap_value)
            except (ValueError, TypeError) as e:
                coin['market_cap'] = 0.0

            # Process 'last_price'
            last_price_value = coin.get('last_price', 0)
            last_price_value = clean_numeric_string(last_price_value)
            try:
                coin['last_price'] = float(last_price_value)
            except (ValueError, TypeError) as e:
                coin['last_price'] = 0.0

        # Calculate total market cap of all meme coins
        total_market_cap = sum(coin['market_cap'] for coin in coins)

        # Sort coins by market cap in descending order and get the top 10
        top_10_coins = sorted(coins, key=lambda x: x['market_cap'], reverse=True)[:10]

        # Structure the response
        response = TopCoinsResponse(
            total_market_cap=total_market_cap,
            top_10_coins=[
                CoinData(
                    symbol=coin["symbol"],
                    last_price=coin['last_price'],
                    market_cap=coin['market_cap']
                )
                for coin in top_10_coins
            ]
        )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        client.close()

@app.get("/top-gainers", response_model=TopMoversResponse)
async def top_gainers():
    """Endpoint to fetch the top 5 meme coins with the largest percentage increase over the last 7 days."""
    return await get_top_movers(is_gainer=True)

@app.get("/top-losers", response_model=TopMoversResponse)
async def top_losers():
    """Endpoint to fetch the top 5 meme coins with the largest percentage decrease over the last 7 days."""
    return await get_top_movers(is_gainer=False)

async def get_top_movers(is_gainer: bool):
    client = get_mongo_client()
    try:
        db = client[DB_NAME]
        collection = db[PRICES_COLLECTION]

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        # Fetch price data for the last 7 days for all coins
        pipeline = [
            {
                "$match": {
                    "date": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$sort": {"date": 1}  # Sort by date ascending
            },
            {
                "$group": {
                    "_id": {
                        "coin_id": "$coin_id",
                        "date": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": "$date"}
                        }
                    },
                    "symbol": {"$first": "$coin_id"},
                    "date": {"$first": "$date"},
                    "price": {"$first": "$price"}
                }
            },
            {
                "$sort": {"_id.coin_id": 1, "date": 1}
            }
        ]

        aggregated_data = list(collection.aggregate(pipeline))

        if not aggregated_data:
            raise HTTPException(status_code=404, detail="No price data found for the last 7 days.")

        # Organize data by coin
        coin_price_history = {}
        for data in aggregated_data:
            coin_id = data['symbol']
            if coin_id not in coin_price_history:
                coin_price_history[coin_id] = []
            price_value = clean_numeric_string(data['price'])
            try:
                price = float(price_value)
            except (ValueError, TypeError):
                price = 0.0
            coin_price_history[coin_id].append({
                "date": data['date'].isoformat(),
                "price": price
            })

        # Calculate percentage change for each coin
        movers = []
        for coin_id, prices in coin_price_history.items():
            if len(prices) >= 2:
                first_price = prices[0]['price']
                last_price = prices[-1]['price']
                if first_price != 0:
                    percentage_change = ((last_price - first_price) / first_price) * 100
                else:
                    percentage_change = 0.0

                movers.append({
                    "symbol": coin_id,
                    "percentage_change": percentage_change,
                    "price_history": prices
                })

        # Sort the coins based on percentage change
        if is_gainer:
            sorted_movers = sorted(movers, key=lambda x: x['percentage_change'], reverse=True)
        else:
            sorted_movers = sorted(movers, key=lambda x: x['percentage_change'])

        top_5_movers = sorted_movers[:5]

        # Prepare the response
        response = TopMoversResponse(
            top_movers=[
                PercentageChangeData(
                    symbol=mover['symbol'],
                    percentage_change=round(mover['percentage_change'], 2),
                    price_history=[
                        PriceHistoryData(
                            date=price['date'],
                            price=price['price']
                        )
                        for price in mover['price_history']
                    ]
                )
                for mover in top_5_movers
            ]
        )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        client.close()