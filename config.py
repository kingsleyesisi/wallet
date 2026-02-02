import os
from bip_utils import Bip44Coins
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
INPUT_PHRASE_FILE = "input_phrase.txt"
PERMUTATIONS_FILE = "permutations.txt"
STATE_FILE = "state.txt"
RESULTS_FILE = "results.txt"
FOUND_FILE = "found.txt"

# Rate Limiting & Concurrency
MAX_WORKERS = 3  # Number of concurrent threads (adjust based on system/network limits)

# Networks to check
NETWORKS = [
    {
        "name": "Ethereum",
        "rpc": os.getenv("ETH_RPC", "https://mainnet.infura.io/v3/8d6d51e263974250994d2359a5119a96"),
        "coingecko_id": "ethereum",
        "coin_enum": Bip44Coins.ETHEREUM,
        "symbol": "ETH"
    },
    {
        "name": "Binance Smart Chain",
        "rpc": os.getenv("BSC_RPC", "https://bsc-dataseed.binance.org/"),
        "coingecko_id": "binancecoin",
        "coin_enum": Bip44Coins.BINANCE_SMART_CHAIN,
        "symbol": "BNB"
    },
    {
        "name": "Polygon",
        "rpc": os.getenv("POLYGON_RPC", "https://polygon-rpc.com/"),
        "coingecko_id": "matic-network",
        "coin_enum": Bip44Coins.POLYGON,
        "symbol": "MATIC"
    },
    {
        "name": "Bitcoin",
        "rpc": None,  # Not using Web3 for Bitcoin
        "coingecko_id": "bitcoin",
        "coin_enum": Bip44Coins.BITCOIN,
        "symbol": "BTC"
    }
]

# Email Configuration
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
TO_EMAIL = os.getenv("TO_EMAIL", "")
