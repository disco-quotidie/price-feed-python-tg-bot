import time
from web3 import Web3
import telebot
from threading import Thread
from dotenv import load_dotenv
import os
import requests

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Read bot token from .env
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

# Initialize Telegram Bot
bot = telebot.TeleBot(BOT_TOKEN)

# List of users who have started the bot
subscribed_users = set()

# RPC URLs
ETH_RPC = "https://rpc.ankr.com/eth"  # Replace with your Infura or other provider URL
OP_RPC = "https://rpc.ankr.com/optimism"  # Optimism RPC URL

# Initialize Web3
eth_web3 = Web3(Web3.HTTPProvider(ETH_RPC))
op_web3 = Web3(Web3.HTTPProvider(OP_RPC))

# Chainlink Price Feed Contract Addresses
PRICE_FEEDS = {
  "ETH/USD": {
    "address": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
    "web3": eth_web3,
  },
  "OP/USD": {
    "address": "0x0D276FC14719f9292D5C1eA2198673d1f4269246",
    "web3": op_web3,
  },
}

# ABI for Chainlink AggregatorV3Interface
AGGREGATOR_ABI = [
  {
    "inputs": [],
    "name": "latestRoundData",
    "outputs": [
      {"internalType": "uint80", "name": "roundId", "type": "uint80"},
      {"internalType": "int256", "name": "answer", "type": "int256"},
      {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
      {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
      {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"},
    ],
    "stateMutability": "view",
    "type": "function",
  }
]

ERC20_ABI = [
  {
    "constant": True,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "payable": False,
    "stateMutability": "view",
    "type": "function",
  }
]

def get_erc20_balance(web3_instance, token_address, wallet_address):
  """Get the ERC-20 token balance of a wallet."""
  # Create contract object
  contract = web3_instance.eth.contract(address=token_address, abi=ERC20_ABI)
  # Call balanceOf function
  balance = contract.functions.balanceOf(wallet_address).call()
  # Return the balance
  return web3_instance.from_wei(balance, 'ether')  # Convert from Wei to token units

def get_balance(web3_instance, address):
  """Get the balance of an address in ETH."""
  balance_wei = web3_instance.eth.get_balance(address)  # Balance in Wei
  balance_eth = web3_instance.from_wei(balance_wei, 'ether')  # Convert to ETH
  return balance_eth

def fetch_price_from_chainlink(feed_name):
  """Fetch live price from Chainlink Price Feed smart contract."""
  feed = PRICE_FEEDS[feed_name]
  contract = feed["web3"].eth.contract(address=feed["address"], abi=AGGREGATOR_ABI)
  try:
    # Call the latestRoundData function
    round_data = contract.functions.latestRoundData().call()
    price = round_data[1] / 1e8  # Scale down the price (Chainlink prices are scaled by 1e8)
    return price
  except Exception as e:
    return f"Error fetching price: {e}"

def fet_price_from_cmc(feed_name):
  api_key = os.getenv("CMC_API_KEY")
  url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

  arr = feed_name.split("/")
  symbol = arr[0]
  convert = arr[1]

  parameters = {
    "symbol": symbol,
    "convert": convert
  }
  headers = {
    "Accepts": "application/json",
    "X-CMC_PRO_API_KEY": api_key,
  }

  try:
    response = requests.get(url, headers=headers, params=parameters)
    response.raise_for_status()  # Raise an error for HTTP errors
    data = response.json()

    if "data" in data and "USUAL" in data["data"]:
      price = data["data"]["USUAL"]["quote"]["USD"]["price"]
      return(f"{price:.4f}")
    else:
      print("Token data not found. Please check the token symbol or slug.")
      return 0
  except requests.exceptions.RequestException as e:
    print(f"Error fetching token price: {e}")
    return 0

def send_prices():
  """Fetch and send live prices to all subscribed users every minute."""
  while True:
    # btc_price = fetch_price_from_chainlink("BTC/USD")
    eth_price = fetch_price_from_chainlink("ETH/USD")
    op_price = fetch_price_from_chainlink("OP/USD")
    usual_price = fet_price_from_cmc("USUAL/USD")

    OP_TOKEN_ADDRESS = op_web3.to_checksum_address("0x4200000000000000000000000000000000000042")
    USUAL_TOKEN_ADDRESS = eth_web3.to_checksum_address("0xC4441c2BE5d8fA8126822B9929CA0b81Ea0DE38E")
    wallet_address = WALLET_ADDRESS
    eth_balance = get_balance(eth_web3, wallet_address)
    opeth_balance = get_balance(op_web3, wallet_address)
    op_token_balance = get_erc20_balance(op_web3, OP_TOKEN_ADDRESS, wallet_address)
    usual_token_balance = get_erc20_balance(eth_web3, USUAL_TOKEN_ADDRESS, wallet_address)

    message = (
      # f"🔹 Live Prices from Chainlink 🔹\n"
      # f"{btc_price}\n"
      f"{eth_price}\n"
      f"{op_price}\n"
      f"{usual_price}\n"
      # f"{eth_balance}\n"
      # f"{opeth_balance}\n"
      # f"{op_token_balance}\n"
      f"\n{int((float(eth_balance) + float(opeth_balance)) * float(eth_price) + float(op_token_balance) * float(op_price) + float(usual_token_balance) * float(usual_price))/10000}"
    )

    try:
      bot.send_message("6960057231", message)
    except Exception as e:
      print(f"Error sending message to Disco: {e}")

    # Send the price message to all subscribed users
    # for user_id in subscribed_users:
    #   try:
    #     bot.send_message(user_id, message)
    #   except Exception as e:
    #     print(f"Error sending message to {user_id}: {e}")

    time.sleep(300)

@bot.message_handler(commands=["start"])
def start_bot(message):
  """Handle the /start command."""
  user_id = message.chat.id
  if user_id not in subscribed_users:
    subscribed_users.add(user_id)
    # bot.reply_to(message, "🤖 You are now subscribed to live price updates every minute!")
  else:
    bot.reply_to(message, "🤖 You are already subscribed!")

@bot.message_handler(commands=["stop"])
def stop_bot(message):
  """Handle the /stop command."""
  user_id = message.chat.id
  if user_id in subscribed_users:
    subscribed_users.remove(user_id)
    # bot.reply_to(message, "❌ You have unsubscribed from live price updates.")
  else:
    bot.reply_to(message, "You are not subscribed.")

# Run the price sender in a separate thread
price_thread = Thread(target=send_prices)
price_thread.daemon = True
price_thread.start()

# Polling to keep the bot running
bot.polling()
