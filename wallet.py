import time
import logging
import requests
import threading
import concurrent.futures
import os
from web3 import Web3
from mnemonic import Mnemonic
from bip_utils import Bip44, Bip44Changes
import config
import notifier
from utils import permutation_generator

# Logging setup
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

class WalletChecker:
    def __init__(self):
        self.price_cache = {}
        self.cache_duration = 300  # 5 minutes
        self.lock = threading.Lock()

    def get_price_usd(self, coingecko_id: str) -> float:
        """Fetch token price in USD from CoinGecko with caching."""
        current_time = time.time()
        RETRY_DURATION = 60  # Wait 60s before retrying after error

        with self.lock:
            # Check cache first
            if coingecko_id in self.price_cache:
                price, timestamp = self.price_cache[coingecko_id]
                # If valid price, use long cache duration
                if price > 0 and current_time - timestamp < self.cache_duration:
                    return price
                # If error (price 0), use short retry duration
                if price == 0 and current_time - timestamp < RETRY_DURATION:
                    return 0.0

            # Fetch fresh price while holding lock to prevent multiple threads hitting API simultaneously
            try:
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {"ids": coingecko_id, "vs_currencies": "usd"}
                headers = {'User-Agent': 'WalletChecker/1.0'}
                r = requests.get(url, params=params, headers=headers, timeout=10)
                r.raise_for_status()
                price = r.json()[coingecko_id]["usd"]
                self.price_cache[coingecko_id] = (price, current_time)
                return price
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logging.warning(f"CoinGecko rate limit for {coingecko_id}. Caching failure for {RETRY_DURATION}s.")
                    self.price_cache[coingecko_id] = (0.0, current_time)
                else:
                    logging.error(f"HTTP error fetching price for {coingecko_id}: {e}")
            except Exception as e:
                logging.error(f"Error fetching price for {coingecko_id}: {e}")

            # Fallback to cached value (even if expired) or 0
            if coingecko_id in self.price_cache:
                return self.price_cache[coingecko_id][0]
            return 0.0

    def derive_address(self, mnemonic: str, coin_enum) -> str:
        """Derive address using BIP44."""
        try:
            seed = Mnemonic("english").to_seed(mnemonic)
            ctx = Bip44.FromSeed(seed, coin_enum)
            acct = ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            address = acct.PublicKey().ToAddress()
            return address
        except Exception as e:
            logging.error(f"Error deriving address: {e}")
            raise

    def get_btc_balance(self, address: str) -> float:
        """Fetch Bitcoin balance using Blockcypher API."""
        url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance"
        try:
            headers = {'User-Agent': 'WalletChecker/1.0'}
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get('balance', 0) / 1e8 # Convert satoshis to BTC
        except Exception as e:
            logging.error(f"Error fetching BTC balance for {address}: {e}")
            return 0.0

    def get_evm_balance(self, address: str, rpc_url: str) -> float:
        """Fetch EVM balance."""
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not w3.is_connected():
                logging.error(f"Failed to connect to RPC: {rpc_url}")
                return 0.0
            balance_wei = w3.eth.get_balance(address)
            return float(w3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            logging.error(f"Error fetching EVM balance for {address} on {rpc_url}: {e}")
            return 0.0

    def check_wallet(self, phrase: str, idx: int) -> dict:
        """Check balances for a single phrase across all networks."""
        results = {
            "phrase": phrase,
            "index": idx,
            "total_value_usd": 0.0,
            "networks": [],
            "found": False
        }

        # Check networks sequentially within this thread
        for net in config.NETWORKS:
            try:
                addr = self.derive_address(phrase, net["coin_enum"])
                balance = 0.0

                if net["name"] == "Bitcoin":
                    balance = self.get_btc_balance(addr)
                else:
                    balance = self.get_evm_balance(addr, net["rpc"])

                price = self.get_price_usd(net["coingecko_id"])
                usd_val = balance * price

                results["total_value_usd"] += usd_val
                results["networks"].append({
                    "network": net["name"],
                    "address": addr,
                    "balance": balance,
                    "symbol": net["symbol"],
                    "usd_value": usd_val
                })

                # Log non-zero balances even if small, for info
                if balance > 0:
                    logging.info(f"[{net['name']}] Idx {idx} | {addr} | {balance:.6f} {net['symbol']} (~${usd_val:.2f})")

            except Exception as e:
                logging.error(f"Error checking {net['name']} for idx {idx}: {e}")

        if results["total_value_usd"] >= 1.0:
            results["found"] = True

        return results

def load_state() -> int:
    """Load last processed permutation index."""
    if os.path.exists(config.STATE_FILE):
        try:
            idx = int(open(config.STATE_FILE).read().strip())
            return idx
        except ValueError as e:
            logging.error(f"Error reading state file: {e}")
            return 0
    return 0

def save_state(index: int):
    """Save last processed index to state file."""
    with open(config.STATE_FILE, "w") as f:
        f.write(str(index))

def handle_found_wallet(result: dict):
    """Handle a found wallet: write to file and send email."""
    msg_lines = [f"Phrase idx {result['index']}: {result['phrase']}"]
    msg_lines.append(f"Total Value: ${result['total_value_usd']:.2f}")
    msg_lines.append("Networks:")
    for net in result['networks']:
        if net['usd_value'] > 0:
            msg_lines.append(f" - {net['network']}: {net['balance']} {net['symbol']} (${net['usd_value']:.2f}) | Address: {net['address']}")

    output = "\n".join(msg_lines)
    output += "\n" + "="*30 + "\n"

    print("\n!!! FOUND WALLET !!!")
    print(output)

    # Write to found file
    with open(config.FOUND_FILE, "a") as f:
        f.write(output)

    # Send email
    subject = f"Wallet Found! ${result['total_value_usd']:.2f}"
    notifier.send_email_notification(subject, output)

def main():
    logging.info("Starting Wallet Checker...")

    try:
        with open(config.INPUT_PHRASE_FILE, "r") as f:
            phrase = f.read().strip()
    except FileNotFoundError:
        logging.error(f"Input file {config.INPUT_PHRASE_FILE} not found.")
        return

    checker = WalletChecker()
    start_index = load_state()
    logging.info(f"Resuming from index {start_index}")

    gen = permutation_generator(phrase)

    # We need to skip the generator to start_index
    # itertools.islice is efficient for this
    import itertools

    # Create an iterator of (index, phrase) starting from start_index
    # Note: enumerate starts at 0, so we slice the generator first, then enumerate with correct start
    sliced_gen = itertools.islice(gen, start_index, None)
    numbered_gen = enumerate(sliced_gen, start=start_index)

    # Use ThreadPoolExecutor with batching to avoid OOM
    BATCH_SIZE = 50

    # Helper for map
    def process(item):
        idx, perm_phrase = item
        if idx % 10 == 0:
            logging.info(f"Processing index {idx}...")
        return checker.check_wallet(perm_phrase, idx)

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        try:
            while True:
                # Take next BATCH_SIZE items
                batch_items = list(itertools.islice(numbered_gen, BATCH_SIZE))
                if not batch_items:
                    break

                # Submit batch
                results_iter = executor.map(process, batch_items)

                for result in results_iter:
                    idx = result['index']

                    with open(config.RESULTS_FILE, "a") as f:
                        f.write(f"Idx {idx} | Total: ${result['total_value_usd']:.2f}\n")

                    if result['found']:
                        handle_found_wallet(result)

                    # Save state incrementally
                    save_state(idx + 1)

        except KeyboardInterrupt:
            logging.warning("Interrupted by user. Exiting...")
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {e}")

if __name__ == "__main__":
    main()
