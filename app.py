import os
import time
import logging
import requests
import threading
from flask import Flask, render_template_string
from markupsafe import Markup
from web3 import Web3
from mnemonic import Mnemonic
from bip_utils import Bip44, Bip44Coins, Bip44Changes
from utils import permutation_generator
from email_utils import send_notification

# === Flask App Setup ===
app = Flask(__name__)

# === Configuration ===
INPUT_PHRASE_FILE = "input_phrase.txt"
PERMUTATIONS_FILE = "permutations.txt"
STATE_FILE = "state.txt"
RESULTS_FILE = "results.txt"
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
        "rpc": None,
        "coingecko_id": "bitcoin",
        "coin_enum": Bip44Coins.BITCOIN,
        "symbol": "BTC"
    }
]
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

PRICE_CACHE = {}
CACHE_DURATION = 300

# === Wallet Checker Logic (from original script) ===

def load_state() -> int:
    if os.path.exists(STATE_FILE):
        try:
            return int(open(STATE_FILE).read().strip())
        except (ValueError, IOError) as e:
            logging.error(f"Error reading state file: {e}")
    return 0

def save_state(index: int):
    with open(STATE_FILE, "w") as f:
        f.write(str(index))

def derive_address(mnemonic: str, coin: Bip44Coins) -> str:
    seed = Mnemonic("english").to_seed(mnemonic)
    ctx = Bip44.FromSeed(seed, coin)
    acct = ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
    return acct.PublicKey().ToAddress()

def get_price_usd(coingecko_id: str) -> float:
    current_time = time.time()
    if coingecko_id in PRICE_CACHE:
        price, timestamp = PRICE_CACHE[coingecko_id]
        if current_time - timestamp < CACHE_DURATION:
            return price
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        price = r.json()[coingecko_id]["usd"]
        PRICE_CACHE[coingecko_id] = (price, current_time)
        return price
    except Exception as e:
        logging.error(f"Error fetching price for {coingecko_id}: {e}")
        return PRICE_CACHE.get(coingecko_id, (0.0,))[0]

def get_btc_balance(address: str) -> int:
    try:
        url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json().get('balance', 0)
    except Exception as e:
        logging.error(f"Error fetching BTC balance for {address}: {e}")
    return 0

def run_wallet_checker():
    logging.info("Starting wallet checker worker thread...")
    time.sleep(2) # Give the server a moment to start up

    try:
        with open(INPUT_PHRASE_FILE, "r") as f:
            phrase = f.read().strip()
    except FileNotFoundError:
        logging.error(f"Input file not found: {INPUT_PHRASE_FILE}. The checker will not run.")
        with open(RESULTS_FILE, "a") as f:
            f.write(f"ERROR: Input file not found: {INPUT_PHRASE_FILE}. Please create it and add your 12 or 24-word phrase.")
        return

    state_index = load_state()
    gen = permutation_generator(phrase)

    with open(PERMUTATIONS_FILE, "a") as perm_file, open(RESULTS_FILE, "a") as results_file:
        network_prices = {net["name"]: get_price_usd(net["coingecko_id"]) for net in NETWORKS}

        for idx, perm_str in enumerate(gen):
            if idx < state_index:
                continue

            logging.info(f"Checking phrase idx {idx}: {perm_str}")
            perm_file.write(perm_str + "\n")
            perm_file.flush()

            valuable_wallet_found = False
            valuable_output_details = []

            for net in NETWORKS:
                try:
                    addr = derive_address(perm_str, net["coin_enum"])
                    balance = 0
                    if net["name"] == "Bitcoin":
                        balance = get_btc_balance(addr) / 1e8
                    else:
                        w3 = Web3(Web3.HTTPProvider(net["rpc"]))
                        if w3.is_connected():
                            balance_wei = w3.eth.get_balance(addr)
                            balance = w3.from_wei(balance_wei, 'ether')
                        else:
                            logging.error(f"Failed to connect to {net['name']}")
                            continue

                    price = network_prices.get(net["name"], 0)
                    usd_val = float(balance) * price

                    out = (f"[{net['name']}] Phrase idx {idx} | Address: {addr} | "
                           f"Balance: {balance:.6f} {net['symbol']} (~${usd_val:.2f})")
                    logging.info(out)
                    results_file.write(out + "\n")

                    if usd_val >= 1.0:
                        valuable_wallet_found = True
                        valuable_output_details.append(out)

                except Exception as e:
                    logging.error(f"Error on {net['name']} for phrase idx {idx}: {e}")
                time.sleep(1)

            if valuable_wallet_found:
                summary = (f"\n\n=== VALUABLE WALLET FOUND ===\n"
                           f"Phrase idx {idx}: {perm_str}\n"
                           f"Details:\n" + "\n".join(valuable_output_details) +
                           f"\n==============================\n")
                logging.warning(summary)
                results_file.write(summary)
                results_file.flush()

                # Send email notification
                email_subject = "Valuable Wallet Found!"
                email_body = f"A wallet with a balance over $1 was found.\n\nPhrase: {perm_str}\n\n" + "\n".join(valuable_output_details)
                send_notification(email_subject, email_body)

            save_state(idx + 1)

    logging.info("Completed all permutations.")

# === Flask Routes ===
@app.route('/')
def index():
    """Displays the results file content."""
    try:
        with open(RESULTS_FILE, 'r') as f:
            content = f.read().replace('\n', '<br>')
    except FileNotFoundError:
        content = "No results yet. The checker might be starting up or the results file hasn't been created."

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Wallet Checker Status</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body { font-family: monospace; background-color: #f4f4f4; color: #333; }
            .container { max-width: 800px; margin: auto; padding: 20px; }
            pre { background-color: #fff; padding: 15px; border: 1px solid #ddd; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Wallet Checker Status</h1>
            <p>This page refreshes every 30 seconds. Displaying contents of <code>results.txt</code>:</p>
            <pre>{{ content|safe }}</pre>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, content=content)

# === Main Execution ===
if __name__ == '__main__':
    # Start the wallet checker in a background thread
    # We use a lock to prevent the thread from starting multiple times in debug mode
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        checker_thread = threading.Thread(target=run_wallet_checker, daemon=True)
        checker_thread.start()

    # Run the Flask app
    app.run(host='0.0.0.0', port=8080)
