import logging
import requests
from web3 import Web3
from mnemonic import Mnemonic
from bip_utils import Bip44, Bip44Coins, Bip44Changes
import time
def runtime_checker(func):
	"""
	A decorator to measure the runtime of a function.
	"""
	def wrapper(*args, **kwargs):
		start_time = time.time()
		result = func(*args, **kwargs)
		end_time = time.time()
		runtime = end_time - start_time
		logging.info(f"Function '{func.__name__}' executed in {runtime:.4f} seconds")
		print(f"Function '{func.__name__}' executed in {runtime:.4f} seconds")
		return result
	return wrapper
# Configure logging
t = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=t)

# === Configuration ===
# Hardcoded 12- or 24-word mnemonic phrase
MNEMONIC = "review field card rice rotate beauty bitter occur engine organ toast either"
# Ethereum node RPC URL (e.g., Infura endpoint)
RPC_URL = "https://mainnet.infura.io/v3/8d6d51e263974250994d2359a5119a96"
# Derivation path details: account 0, external chain, address index 0


def get_eth_price_usd() -> float:
    """
    Fetches the current Ethereum price in USD using CoinGecko's public API.
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "ethereum", "vs_currencies": "usd"}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data["ethereum"]["usd"]


def derive_eth_address(mnemonic: str) -> str:
    """
    Derives an Ethereum address from the given mnemonic using BIP44.
    """
    # Generate seed from mnemonic
    mnemo = Mnemonic("english")
    seed_bytes = mnemo.to_seed(mnemonic)

    # Derive BIP44 Ethereum account: m/44'/60'/0'/0/0
    bip44_def_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
    bip44_acc = (
        bip44_def_ctx
        .Purpose()
        .Coin()
        .Account(0)
        .Change(Bip44Changes.CHAIN_EXT)
        .AddressIndex(0)
    )

    return bip44_acc.PublicKey().ToAddress()

@runtime_checker
def main():
    # Derive Ethereum address
    address = derive_eth_address(MNEMONIC)

    # Connect to Ethereum network
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        logging.error("Failed to connect to Ethereum node at %s", RPC_URL)
        return

    # Retrieve ETH balance for the address
    balance_wei = w3.eth.get_balance(address)
    balance_eth = w3.from_wei(balance_wei, 'ether')
    print(f"Balance in Ether (full precision): {balance_eth} ETH")

    # Fetch current ETH price in USD
    eth_price_usd = get_eth_price_usd()
    total_usd_value = float(balance_eth) * eth_price_usd

    # Output details
    print(f"Wallet Address: {address}")
    print(f"ETH Balance: {balance_eth:.6f} ETH")
    print(f"Approx. Value: ${total_usd_value:.2f} USD")

    # Log if balance exceeds $1
    if total_usd_value > 1:
        logging.info(f"Balance exceeds $1 USD: ${total_usd_value:.2f}")
    else:
        logging.info(f"Balance does not exceed $1 USD: ${total_usd_value:.2f}")


if __name__ == "__main__":
    main()

# Dependencies:
# pip install web3 requests mnemonic bip_utils
