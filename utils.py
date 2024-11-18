from dotenv import load_dotenv
import logging
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "")

# Function to get MongoDB client
def get_mongo_client():
    try:
        client = MongoClient(MONGO_URI)
        return client
    except ConnectionFailure as e:
        logging.error("Could not connect to MongoDB: %s", e)
        raise
    