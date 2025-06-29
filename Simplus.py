import streamlit as st
from web3 import Web3
from eth_account import Account
import secrets
import json
import os

# --- Configuration ---
INFURA_URL = "https://sepolia.infura.io/v3/e0fcce634506410b87fc31064eed915a"
SIMPLUS_CONTRACT_ADDRESS = "0x7263b8726C96566927626773CbD6B19d32ff76E3"
USDC_CONTRACT_ADDRESS = "0x2Bc7c4Afc076088DB03366a6CA9729ba9E450DaA"
WALLET_DB_FILE = "wallet_db.json"

SIMPLUS_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "userDepositOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "vaultUSDCBalance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function"
    }
]

# --- Wallet DB ---
def load_wallet_db():
    if os.path.exists(WALLET_DB_FILE):
        with open(WALLET_DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_wallet_db(db):
    with open(WALLET_DB_FILE, "w") as f:
        json.dump(db, f)

# --- Web3 Setup ---
w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# --- Session State Init ---
if "wallet_db" not in st.session_state:
    st.session_state["wallet_db"] = load_wallet_db()
if "logged_in_wallet" not in st.session_state:
    st.session_state["logged_in_wallet"] = None

# --- UI ---
st.set_page_config(page_title="Simplus Wallet (USDC)", page_icon="💳")
st.title("💳 Simplus Wallet")
mode = st.radio("Select mode:", ["Admin", "User"])

# --- Admin Panel ---
if mode == "Admin":
    st.header("Admin Panel")
    with st.expander("Create a new Simplus Wallet"):
        if st.button("Create Wallet"):
            acct = Account.create()
            wallet_address = Web3.to_checksum_address(acct.address)
            private_key = acct.key.hex()
            access_code = secrets.token_urlsafe(8)
            st.session_state["wallet_db"][wallet_address] = {
                "private_key": private_key,
                "access_code": access_code
            }
            save_wallet_db(st.session_state["wallet_db"])
            st.success(f"Wallet created for user: {wallet_address}")
            st.code(f"Access Code: {access_code}", language="text")

# --- User Wallet ---
if mode == "User":
    st.header("User Wallet Access")
    input_address = st.text_input("Wallet Address")
    input_code = st.text_input("Access Code", type="password")

    if st.button("Login"):
        db = load_wallet_db()
        wallet_info = db.get(Web3.to_checksum_address(input_address))
        if wallet_info and input_code == wallet_info["access_code"]:
            st.session_state["logged_in_wallet"] = Web3.to_checksum_address(input_address)
            st.success("Access granted!")
        else:
            st.error("Invalid wallet address or access code")

    if st.session_state["logged_in_wallet"]:
        wallet_address = st.session_state["logged_in_wallet"]
        wallet_info = st.session_state["wallet_db"].get(wallet_address)
        private_key = wallet_info["private_key"]

        simplus_contract = w3.eth.contract(address=Web3.to_checksum_address(SIMPLUS_CONTRACT_ADDRESS), abi=SIMPLUS_ABI)
        usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_CONTRACT_ADDRESS), abi=USDC_ABI)

        try:
            balance = usdc_contract.functions.balanceOf(wallet_address).call()
            st.write(f"**USDC Balance:** {balance / 1e6:.6f} USDC")
        except Exception as e:
            st.error(f"Error checking balance: {e}")

        try:
            vault_balance = simplus_contract.functions.userDepositOf(wallet_address).call()
            st.write(f"**Deposited in Vault:** {vault_balance / 1e6:.6f} USDC")
        except Exception as e:
            st.error(f"Error checking vault deposit: {e}")

        deposit_amt = st.number_input("Deposit USDC to Simplus Vault", min_value=0.0, step=0.01)
        if st.button("Approve & Deposit"):
            try:
                # Approve USDC for vault
                tx1 = usdc_contract.functions.approve(SIMPLUS_CONTRACT_ADDRESS, int(deposit_amt * 1e6)).build_transaction({
                    "from": wallet_address,
                    "nonce": w3.eth.get_transaction_count(wallet_address),
                    "gas": 100000,
                    "gasPrice": w3.eth.gas_price
                })
                signed_tx1 = w3.eth.account.sign_transaction(tx1, private_key)
                w3.eth.send_raw_transaction(signed_tx1.rawTransaction)
                st.info("Approval sent, waiting...")
                
                # Deposit to vault
                tx2 = simplus_contract.functions.deposit(int(deposit_amt * 1e6)).build_transaction({
                    "from": wallet_address,
                    "nonce": w3.eth.get_transaction_count(wallet_address),
                    "gas": 100000,
                    "gasPrice": w3.eth.gas_price
                })
                signed_tx2 = w3.eth.account.sign_transaction(tx2, private_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx2.rawTransaction)
                st.success(f"Deposited {deposit_amt} USDC. Tx: {w3.to_hex(tx_hash)}")
            except Exception as e:
                st.error(f"Deposit failed: {e}")

        withdraw_amt = st.number_input("Withdraw USDC from Vault", min_value=0.0, step=0.01)
        if st.button("Withdraw"):
            try:
                tx = simplus_contract.functions.withdraw(int(withdraw_amt * 1e6)).build_transaction({
                    "from": wallet_address,
                    "nonce": w3.eth.get_transaction_count(wallet_address),
                    "gas": 100000,
                    "gasPrice": w3.eth.gas_price
                })
                signed_tx = w3.eth.account.sign_transaction(tx, private_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                st.success(f"Withdrawal of {withdraw_amt} USDC successful. Tx: {w3.to_hex(tx_hash)}")
            except Exception as e:
                st.error(f"Withdrawal failed: {e}")

        if st.button("Logout"):
            st.session_state["logged_in_wallet"] = None
            st.success("Logged out.")
