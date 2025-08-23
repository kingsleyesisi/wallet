import os
import time
import logging
import requests
from web3 import Web3
from mnemonic import Mnemonic
from bip_utils import Bip44, Bip44Coins, Bip44Changes
import itertools

def permutation_generator(phrase: str):
    """Yield each permutation of the mnemonic phrase."""
    words = phrase.split()
    if len(words) not in (12, 24):
        raise ValueError("Phrase must contain exactly 12 or 24 words.")
    for perm in itertools.permutations(words):
        yield " ".join(perm)


# === Configuration ===
INPUT_PHRASE_FILE = "input_phrase.txt"
PERMUTATIONS_FILE = "permutations.txt"
STATE_FILE = "state.txt"
RESULTS_FILE = "results.txt"
# Map network names to RPC URLs and CoinGecko IDs and Bip44Coins
NETWORKS = [
    {
        "name": "Ethereum",
        "rpc": "https://mainnet.infura.io/v3/8d6d51e263974250994d2359a5119a96",
        "coingecko_id": "ethereum",
        "coin_enum": Bip44Coins.ETHEREUM,
        "symbol": "ETH"
    },
    {
        "name": "Binance Smart Chain",
        "rpc": "https://bsc-dataseed.binance.org/",
        "coingecko_id": "binancecoin",
        "coin_enum": Bip44Coins.BINANCE_SMART_CHAIN,
        "symbol": "BNB"
    },
    {
        "name": "Polygon",
        "rpc": "https://polygon-rpc.com/",
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
CHECK_INTERVAL = 10  # seconds between balance checks
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

# Price cache to reduce CoinGecko API calls
PRICE_CACHE = {}
CACHE_DURATION = 300  # 5 minutes in seconds

def load_state() -> int:
    """Load last processed permutation index."""
    if os.path.exists(STATE_FILE):
        try:
            idx = int(open(STATE_FILE).read().strip())
            return idx
        except ValueError as e:
            logging.error(f"Error reading state file: {e}")
            return 0
    logging.debug("No state file found, starting from 0.")
    return 0


def save_state(index: int):
    """Save last processed index to state file."""
    with open(STATE_FILE, "w") as f:
        f.write(str(index))
    logging.debug(f"Saved state index: {index}")


def derive_address(mnemonic: str, coin: Bip44Coins) -> str:
    """Derive address using BIP44 path m/44'/60'/0'/0/0 for EVM, adjusted for others."""
    # logging.debug(f"Deriving for coin: {coin}")
    seed = Mnemonic("english").to_seed(mnemonic)
    ctx = Bip44.FromSeed(seed, coin)
    acct = ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
    address = acct.PublicKey().ToAddress()
    logging.debug(f"Derived address: {address}")
    return address


def get_price_usd(coingecko_id: str) -> float:
    """Fetch token price in USD from CoinGecko with caching."""
    current_time = time.time()

    # Return cached price if valid
    if coingecko_id in PRICE_CACHE:
        price, timestamp = PRICE_CACHE[coingecko_id]
        if current_time - timestamp < CACHE_DURATION:
            # logging.debug(f"Using cached price for {coingecko_id}: {price}")
            return price

    # logging.debug(f"Fetching fresh price for: {coingecko_id}")
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coingecko_id, "vs_currencies": "usd"}
        headers = {'User-Agent': 'WalletChecker/1.0'}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        price = r.json()[coingecko_id]["usd"]
        PRICE_CACHE[coingecko_id] = (price, current_time)
        # logging.debug(f"Fetched new price: {price}")
        return price
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logging.warning("CoinGecko rate limit reached. Using cached value.")
            # Try to return last cached value if available
            if coingecko_id in PRICE_CACHE:
                return PRICE_CACHE[coingecko_id][0]
        logging.error(f"HTTP error fetching price: {e}")
    except Exception as e:
        logging.error(f"Error fetching price: {e}")

    # Fallback to 0 if no cached value
    if coingecko_id in PRICE_CACHE:
        return PRICE_CACHE[coingecko_id][0]
    return 0.0


def get_btc_balance(address: str) -> int:
    """Fetch Bitcoin balance using Blockcypher API."""
    url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance"
    try:
        headers = {'User-Agent': 'WalletChecker/1.0'}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get('balance', 0)  # in satoshis
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logging.warning("Blockcypher rate limit reached.")
        logging.error(f"HTTP error fetching BTC balance: {e}")
    except Exception as e:
        logging.error(f"Error fetching BTC balance: {e}")
    return 0


def main():
    logging.info("Starting wallet checker...")
    start_time = time.time()  # Add this line
    # Load input phrase
    with open(INPUT_PHRASE_FILE, "r") as f:
        phrase = f.read().strip()
    logging.debug(f"Loaded input phrase: {phrase}")

    state_index = load_state()
    gen = permutation_generator(phrase)
    perm_file = open(PERMUTATIONS_FILE, "a")
    results_file = open(RESULTS_FILE, "a")

    # Pre-fetch prices for all networks
    network_prices = {}
    for net in NETWORKS:
        network_prices[net["name"]] = get_price_usd(net["coingecko_id"])

    price_refresh_counter = 0

    for idx, perm_str in enumerate(gen):
        # logging.debug(f"Processing permutation idx {idx}")
        if time.time() - start_time > 5 * 60 * 60:  # 5 hours in seconds
            logging.info("Reached 5 hour limit. Stopping execution.")
            break

        if idx < state_index:
            logging.debug(f"Skipping idx {idx}, already processed.")
            continue

        # Log permutation
        logging.info(f"Checking phrase idx {idx}: {perm_str}")
        perm_file.write(perm_str + "\n")
        perm_file.flush()

        # Track if we found any wallet with >$1
        valuable_wallet_found = False
        valuable_output = ""

        # Check balances across networks
        for i, net in enumerate(NETWORKS):
            # logging.debug(f"Network: {net['name']}, RPC: {net['rpc']}")
            try:
                # Derive address
                addr = derive_address(perm_str, net["coin_enum"])

                if net["name"] == "Bitcoin":
                    # Get BTC balance
                    balance_sat = get_btc_balance(addr)
                    balance = balance_sat / 1e8
                else:
                    # Connect to EVM network
                    w3 = Web3(Web3.HTTPProvider(net["rpc"]))
                    if not w3.is_connected():
                        logging.error(f"Failed to connect to {net['name']} RPC at {net['rpc']}")
                        continue
                    logging.debug(f"Connected to {net['name']} RPC")

                    # Get balance
                    balance_wei = w3.eth.get_balance(addr)
                    balance = w3.from_wei(balance_wei, 'ether')

                price = network_prices[net["name"]]
                usd_val = float(balance) * price

                # Format output
                out = (f"[{net['name']}] Phrase idx {idx} | Address: {addr} | "
                       f"Balance: {balance:.6f} {net['symbol']} (~${usd_val:.2f})")
                print(out)
                logging.info(out)
                results_file.write(out + "\n")

                # Check if balance exceeds $1 threshold
                if usd_val >= 1.0:
                    print("success")
                    logging.info("success")
                    valuable_wallet_found = True
                    valuable_output += f"\n{out}"
                else:
                    print("empty")
                    logging.info("empty")

            except Exception as e:
                err = f"Error on {net['name']} for phrase idx {idx}: {e}"
                logging.error(err)
                results_file.write(err + "\n")

            # Add delay between network checks (except last one)
            if i < len(NETWORKS) - 1:
                time.sleep(1)  # Space out RPC requests

        # Save valuable wallet info with phrase
        if valuable_wallet_found:
            valuable_output = (f"\n\n=== VALUABLE WALLET FOUND ===\n"
                               f"Phrase idx {idx}: {perm_str}\n"
                               f"Networks:{valuable_output}\n"
                               f"==============================\n")
            print(valuable_output)
            logging.warning(valuable_output)
            results_file.write(valuable_output)
            results_file.flush()

        # Periodically refresh prices
        price_refresh_counter += 1
        if price_refresh_counter >= 30:  # Every 30 permutations (~5 minutes)
            logging.info("Refreshing token prices...")
            for net in NETWORKS:
                network_prices[net["name"]] = get_price_usd(net["coingecko_id"])
            price_refresh_counter = 0

        save_state(idx + 1)

    perm_file.close()
    results_file.close()
    logging.info("Completed all permutations.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("Interrupted by user; state saved.")
