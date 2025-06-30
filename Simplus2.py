# simplus_wallet_app.py
import streamlit as st
from web3 import Web3
import secrets
import json
import os
from eth_account import Account

# ---------------- Configuration ----------------
INFURA_URL = "https://sepolia.infura.io/v3/e0fcce634506410b87fc31064eed915a"  # Replace with your Infura Project ID
SIMPLUS_CONTRACT_ADDRESS = "0x7263b8726C96566927626773CbD6B19d32ff76E3"      # Replace with your deployed SimplusVault contract address
USDC_CONTRACT_ADDRESS = "0x2Bc7c4Afc076088DB03366a6CA9729ba9E450DaA"                 # USDC on Sepolia (or mock USDC)
WALLET_DB_FILE = "wallet_db.json"

SIMPLUS_ABI = json.load(open("simplus_abi.json"))  # Save ABI as simplus_abi.json
USDC_ABI = json.load(open("usdc_abi.json"))        # Save standard ERC20 ABI as usdc_abi.json

# ---------------- Load Wallet Database ----------------
def load_wallet_db():
    if os.path.exists(WALLET_DB_FILE):
        with open(WALLET_DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_wallet_db(db):
    with open(WALLET_DB_FILE, 'w') as f:
        json.dump(db, f)

w3 = Web3(Web3.HTTPProvider(INFURA_URL))
if not w3.is_connected():
    st.error("Failed to connect to Web3 provider.")
    st.stop()

wallet_db = load_wallet_db()
st.set_page_config(page_title="Simplus Wallet", page_icon="🌐")
st.title("Simplus Wallet - USDC Focused")
mode = st.radio("Select Mode", ["Admin", "User"])

# ---------------- Admin Mode ----------------
if mode == "Admin":
    st.header("Admin Panel")

    with st.expander("Create a New Simplus Wallet"):
        if st.button("Create Wallet"):
            acct = Account.create()
            address = acct.address
            private_key = acct.key.hex()
            password = secrets.token_urlsafe(8)
            wallet_db[address] = {"private_key": private_key, "password": password}
            save_wallet_db(wallet_db)
            st.success("Wallet Created")
            st.write(f"**Wallet Address:** `{address}`")
            st.write(f"**Access Code:** `{password}`")

    with st.expander("Check User USDC Balance"):
        check_addr = st.text_input("Wallet Address to Check")
        if st.button("Check Balance"):
            try:
                usdc_contract = w3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=USDC_ABI)
                balance = usdc_contract.functions.balanceOf(check_addr).call() / 1e6
                st.write(f"USDC Balance: {balance:.6f} USDC")
            except Exception as e:
                st.error(f"Error checking balance: {e}")

# ---------------- User Mode ----------------
elif mode == "User":
    st.header("User Wallet Access")
    address = st.text_input("Wallet Address")
    code = st.text_input("Access Code", type="password")

    if st.button("Login"):
        if wallet_db.get(address) and wallet_db[address]["password"] == code:
            st.success("Login Successful")
            user_key = wallet_db[address]["private_key"]
            st.session_state["user_address"] = address
            st.session_state["user_key"] = user_key
        else:
            st.error("Invalid Address or Access Code")

    if st.session_state.get("user_address"):
        user_address = st.session_state["user_address"]
        user_key = st.session_state["user_key"]
        usdc_contract = w3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=USDC_ABI)
        vault_contract = w3.eth.contract(address=SIMPLUS_CONTRACT_ADDRESS, abi=SIMPLUS_ABI)

        st.subheader(f"Welcome `{user_address}`")

        # Show on-chain USDC balance
        try:
            onchain_bal = usdc_contract.functions.balanceOf(user_address).call() / 1e6
            st.write(f"USDC in Wallet: {onchain_bal:.6f} USDC")
        except:
            st.error("Error fetching USDC balance")

        # Deposit to vault
        deposit_amt = st.number_input("USDC to Deposit to Vault", min_value=0.000001, step=0.01)
        if st.button("Deposit to Vault"):
            try:
                nonce = w3.eth.get_transaction_count(user_address)
                approve_tx = usdc_contract.functions.approve(SIMPLUS_CONTRACT_ADDRESS, int(deposit_amt * 1e6)).build_transaction({
                    "from": user_address,
                    "nonce": nonce,
                    "gas": 80000,
                    "gasPrice": w3.eth.gas_price
                })
                signed_approve = w3.eth.account.sign_transaction(approve_tx, private_key=user_key)
                w3.eth.send_raw_transaction(signed_approve.rawTransaction)

                nonce += 1
                deposit_tx = vault_contract.functions.deposit(int(deposit_amt * 1e6)).build_transaction({
                    "from": user_address,
                    "nonce": nonce,
                    "gas": 120000,
                    "gasPrice": w3.eth.gas_price
                })
                signed_deposit = w3.eth.account.sign_transaction(deposit_tx, private_key=user_key)
                tx_hash = w3.eth.send_raw_transaction(signed_deposit.rawTransaction)
                st.success(f"Deposit Sent: {w3.to_hex(tx_hash)}")
            except Exception as e:
                st.error(f"Deposit failed: {e}")

        # Withdraw to own wallet
        withdraw_amt = st.number_input("USDC to Withdraw to My Wallet", min_value=0.000001, step=0.01)
        if st.button("Withdraw to Self"):
            try:
                nonce = w3.eth.get_transaction_count(user_address)
                tx = vault_contract.functions.withdraw(int(withdraw_amt * 1e6)).build_transaction({
                    "from": user_address,
                    "nonce": nonce,
                    "gas": 100000,
                    "gasPrice": w3.eth.gas_price
                })
                signed_tx = w3.eth.account.sign_transaction(tx, private_key=user_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                st.success(f"Withdraw Transaction Sent: {w3.to_hex(tx_hash)}")
            except Exception as e:
                st.error(f"Withdraw failed: {e}")

        # Withdraw to another address
        st.subheader("Withdraw to Another Wallet")
        target_addr = st.text_input("Recipient Address")
        amt_to_send = st.number_input("Amount (USDC)", min_value=0.000001, step=0.01, key="send_amt")
        if st.button("Send to Address"):
            try:
                nonce = w3.eth.get_transaction_count(user_address)
                tx = vault_contract.functions.withdrawTo(target_addr, int(amt_to_send * 1e6)).build_transaction({
                    "from": user_address,
                    "nonce": nonce,
                    "gas": 150000,
                    "gasPrice": w3.eth.gas_price
                })
                signed_tx = w3.eth.account.sign_transaction(tx, private_key=user_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                st.success(f"Sent: {w3.to_hex(tx_hash)}")
            except Exception as e:
                st.error(f"Error sending USDC: {e}")

        if st.button("Logout"):
            st.session_state.clear()
            st.success("Logged out.")
