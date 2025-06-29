import streamlit as st
from eth_account import Account
from web3 import Web3
import secrets
import os
import json
import time

# ----------------------------- CONFIGURATION -----------------------------
INFURA_URL = "https://sepolia.infura.io/v3/e0fcce634506410b87fc31064eed915a"
SIMPLUS_CONTRACT_ADDRESS = "0x7263b8726C96566927626773CbD6B19d32ff76E3"
USDC_CONTRACT_ADDRESS = "0x2Bc7c4Afc076088DB03366a6CA9729ba9E450DaA"
SIMPLUS_ABI_FILE = "simplus_abi.json"
WALLET_DB_FILE = "simplus_wallet_db.json"

# ----------------------------- HELPER FUNCTIONS -----------------------------
def load_wallet_db():
    if os.path.exists(WALLET_DB_FILE):
        with open(WALLET_DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_wallet_db(db):
    with open(WALLET_DB_FILE, "w") as f:
        json.dump(db, f)

def load_abi():
    with open(SIMPLUS_ABI_FILE, "r") as f:
        return json.load(f)

# ----------------------------- SETUP -----------------------------
w3 = Web3(Web3.HTTPProvider(INFURA_URL))
simplus_abi = load_abi()
simplus_contract = w3.eth.contract(address=Web3.to_checksum_address(SIMPLUS_CONTRACT_ADDRESS), abi=simplus_abi)
usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_CONTRACT_ADDRESS), abi=simplus_abi)  # using same minimal ABI

# ----------------------------- STREAMLIT UI -----------------------------
st.set_page_config(page_title="Simplus Wallet", page_icon="💰")
st.title("💰 Simplus Wallet (USDC)")

if "wallet_db" not in st.session_state:
    st.session_state.wallet_db = load_wallet_db()

if "logged_in_wallet" not in st.session_state:
    st.session_state.logged_in_wallet = None

mode = st.radio("Select mode:", ["Admin", "User"])

# ----------------------------- ADMIN -----------------------------
if mode == "Admin":
    st.header("Admin Panel")
    with st.expander("Create a New Simplus Wallet"):
        if st.button("Create Wallet"):
            acct = Account.create()
            wallet_address = Web3.to_checksum_address(acct.address)
            private_key = acct.key.hex()
            access_code = secrets.token_urlsafe(8)
            st.session_state.wallet_db[wallet_address] = {
                "private_key": private_key,
                "access_code": access_code
            }
            save_wallet_db(st.session_state.wallet_db)
            st.success("Wallet created!")
            st.write(f"**Wallet Address:** `{wallet_address}`")
            st.write(f"**Access Code:** `{access_code}`")

    st.subheader("Access Wallet")
    input_address = st.text_input("Wallet Address (Admin)")
    input_code = st.text_input("Access Code (Admin)", type="password")
    if st.button("Login (Admin)"):
        wallet_info = st.session_state.wallet_db.get(Web3.to_checksum_address(input_address))
        if wallet_info and input_code == wallet_info["access_code"]:
            st.session_state.logged_in_wallet = Web3.to_checksum_address(input_address)
            st.success("Access granted")
        else:
            st.error("Invalid wallet address or code")

# ----------------------------- USER -----------------------------
if mode == "User":
    st.header("User Panel")
    input_address = st.text_input("Wallet Address")
    input_code = st.text_input("Access Code", type="password")
    if st.button("Login"):
        wallet_info = st.session_state.wallet_db.get(Web3.to_checksum_address(input_address))
        if wallet_info and input_code == wallet_info["access_code"]:
            st.session_state.logged_in_wallet = Web3.to_checksum_address(input_address)
            st.success("Access granted")
        else:
            st.error("Invalid wallet address or code")

# ----------------------------- WALLET ACTIONS -----------------------------
if st.session_state.logged_in_wallet:
    wallet_address = st.session_state.logged_in_wallet
    wallet_info = st.session_state.wallet_db.get(wallet_address)
    private_key = wallet_info["private_key"]
    st.subheader(f"Wallet: `{wallet_address}`")

    # Check USDC balance
    try:
        usdc_balance = usdc_contract.functions.balanceOf(wallet_address).call()
        st.write(f"**USDC Balance:** {usdc_balance / 1e6:.6f} USDC")
    except Exception as e:
        st.error(f"Error checking balance: {e}")

    # Deposit
    st.markdown("### Deposit USDC to Simplus Vault")
    deposit_amount = st.number_input("Amount to deposit (USDC)", min_value=0.01, step=0.01)
    if st.button("Deposit"):
        try:
            tx1 = usdc_contract.functions.approve(SIMPLUS_CONTRACT_ADDRESS, int(deposit_amount * 1e6)).build_transaction({
                "from": wallet_address,
                "nonce": w3.eth.get_transaction_count(wallet_address),
                "gas": 100000,
                "gasPrice": w3.eth.gas_price
            })
            signed1 = w3.eth.account.sign_transaction(tx1, private_key)
            tx_hash1 = w3.eth.send_raw_transaction(signed1.rawTransaction)
            st.info(f"Approval TX sent: {w3.to_hex(tx_hash1)}")
            w3.eth.wait_for_transaction_receipt(tx_hash1)

            tx2 = simplus_contract.functions.deposit(int(deposit_amount * 1e6)).build_transaction({
                "from": wallet_address,
                "nonce": w3.eth.get_transaction_count(wallet_address),
                "gas": 150000,
                "gasPrice": w3.eth.gas_price
            })
            signed2 = w3.eth.account.sign_transaction(tx2, private_key)
            tx_hash2 = w3.eth.send_raw_transaction(signed2.rawTransaction)
            st.success(f"Deposit TX sent: {w3.to_hex(tx_hash2)}")
        except Exception as e:
            st.error(f"Deposit failed: {e}")

    # Withdraw
    st.markdown("### Withdraw USDC from Simplus Vault")
    withdraw_amount = st.number_input("Amount to withdraw (USDC)", min_value=0.01, step=0.01)
    if st.button("Withdraw"):
        try:
            tx = simplus_contract.functions.withdraw(int(withdraw_amount * 1e6)).build_transaction({
                "from": wallet_address,
                "nonce": w3.eth.get_transaction_count(wallet_address),
                "gas": 150000,
                "gasPrice": w3.eth.gas_price
            })
            signed = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            st.success(f"Withdraw TX sent: {w3.to_hex(tx_hash)}")
        except Exception as e:
            st.error(f"Withdraw failed: {e}")

    if st.button("Logout"):
        st.session_state.logged_in_wallet = None
        st.success("Logged out")
