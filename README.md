# Modular Wallet Checker

This script checks multiple permutations of a mnemonic seed phrase for balances across Ethereum, Binance Smart Chain, Polygon, and Bitcoin.

## Features
- **Modular Design**: Configurable settings and separated logic.
- **Efficient**: Uses multithreading to check balances in parallel.
- **Notifications**: Sends an email when a wallet with >$1 is found.
- **State Saving**: Resumes from the last checked permutation if interrupted.
- **Found Log**: Saves found wallets to `found.txt`.

## Prerequisites
- Python 3.8+
- An internet connection

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up configuration:
   - Copy `.env.example` to `.env`.
   - Open `.env` and fill in your details.
     - **Email**: To receive notifications, provide SMTP credentials. For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833).
     - **RPCs**: You can provide your own RPC URLs (e.g., Infura, Alchemy) for better reliability and fewer rate limits.

3. Prepare Input:
   - Ensure `input_phrase.txt` contains your 12-word seed phrase (space-separated).

## Usage

Run the script:
```bash
python wallet.py
```

## Output
- **Console**: Shows progress and any non-zero balances.
- **results.txt**: Logs all checked permutations and their total value.
- **found.txt**: Stores details of any wallet found with >= $1 USD.
- **state.txt**: Tracks the current progress (index) to allow resuming.

## Configuration
Adjust `config.py` to change:
- `MAX_WORKERS`: Number of concurrent threads (default: 5). Increase for speed, decrease if hitting rate limits.
- `CHECK_INTERVAL`: Delay between checks (default: 0.5s).

## Notes
- The script uses free public RPCs and APIs (CoinGecko, Blockcypher) which have rate limits. If you see many errors, consider using private RPCs (defined in `.env`) or reducing `MAX_WORKERS`.
