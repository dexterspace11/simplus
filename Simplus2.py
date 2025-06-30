# simplus_wallet_app.py
import streamlit as st
from web3 import Web3
import secrets
import json
import os
from eth_account import Account

# -------- Configuration --------
INFURA_URL = "https://sepolia.infura.io/v3/YOUR_INFURA_KEY"
SIMPLUS_CONTRACT_ADDRESS = "0x7263b8726C96566927626773CbD6B19d32ff76E3"
USDC_CONTRACT_ADDRESS = "0x2Bc7c4Afc076088DB03366a6CA9729ba9E450DaA"
WALLET_DB_FILE = "wallet_db.json"

# -------- Load ABIs --------
with open("simplus_abi.json") as f:
    SIMPLUS_ABI = json.load(f)
with open("usdc_abi.json") as f:
    USDC_ABI = json.load(f)

# -------- Init Web3 --------
w3 = Web3(Web3.HTTPProvider(INFURA_URL))
if not w3.is_connected():
    st.error("Failed to connect to Web3 provider.")
    st.stop()

# -------- DB --------
def load_wallet_db():
    if os.path.exists(WALLET_DB_FILE):
        with open(WALLET_DB_FILE) as f:
            return json.load(f)
    return {}

def save_wallet_db(db):
    with open(WALLET_DB_FILE, "w") as f:
        json.dump(db, f)

wallet_db = load_wallet_db()

# -------- UI --------
st.set_page_config("Simplus Wallet", "💸")
st.title("💸 Simplus Wallet (USDC)")
mode = st.radio("Choose Mode", ["Admin", "User"])

# -------- Admin --------
if mode == "Admin":
    st.header("Admin Tools")

    with st.expander("Generate New Wallet"):
        if st.button("Create Wallet"):
            acct = Account.create()
            addr = acct.address
            pk = acct.key.hex()
            pwd = secrets.token_urlsafe(8)
            wallet_db[addr] = {"private_key": pk, "password": pwd}
            save_wallet_db(wallet_db)
            st.success("Wallet created.")
            st.code(f"Address: {addr}")
            st.code(f"Password: {pwd}")

    with st.expander("Check USDC Balance"):
        query = st.text_input("Wallet to Check")
        if st.button("Check Balance"):
            try:
                usdc = w3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=USDC_ABI)
                balance = usdc.functions.balanceOf(query).call() / 1e6
                st.write(f"USDC Balance: {balance:.6f}")
            except Exception as e:
                st.error(str(e))

# -------- User --------
elif mode == "User":
    st.header("Wallet Login")

    addr = st.text_input("Wallet Address")
    pwd = st.text_input("Access Code", type="password")

    if st.button("Login"):
        if wallet_db.get(addr) and wallet_db[addr]["password"] == pwd:
            st.session_state["user"] = addr
            st.session_state["key"] = wallet_db[addr]["private_key"]
            st.success("Welcome!")
        else:
            st.error("Invalid credentials.")

    if st.session_state.get("user"):
        addr = st.session_state["user"]
        key = st.session_state["key"]
        usdc = w3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=USDC_ABI)
        vault = w3.eth.contract(address=SIMPLUS_CONTRACT_ADDRESS, abi=SIMPLUS_ABI)

        st.markdown(f"**Your Wallet:** `{addr}`")

        try:
            bal = usdc.functions.balanceOf(addr).call() / 1e6
            st.write(f"USDC Balance: {bal:.6f}")
        except Exception as e:
            st.error("Balance error: " + str(e))

        # Deposit
        amt = st.number_input("Amount to Deposit (USDC)", min_value=0.000001, step=0.01)
        if st.button("Deposit"):
            try:
                nonce = w3.eth.get_transaction_count(addr)
                tx1 = usdc.functions.approve(SIMPLUS_CONTRACT_ADDRESS, int(amt * 1e6)).build_transaction({
                    "from": addr, "nonce": nonce, "gas": 80000, "gasPrice": w3.eth.gas_price
                })
                tx2 = vault.functions.deposit(int(amt * 1e6)).build_transaction({
                    "from": addr, "nonce": nonce + 1, "gas": 100000, "gasPrice": w3.eth.gas_price
                })
                signed1 = w3.eth.account.sign_transaction(tx1, key)
                signed2 = w3.eth.account.sign_transaction(tx2, key)
                w3.eth.send_raw_transaction(signed1.rawTransaction)
                tx_hash = w3.eth.send_raw_transaction(signed2.rawTransaction)
                st.success(f"Deposited! TX: {w3.to_hex(tx_hash)}")
            except Exception as e:
                st.error(f"Deposit error: {e}")

        # Withdraw to self
        wd_amt = st.number_input("Withdraw to My Wallet", min_value=0.000001, step=0.01, key="wd")
        if st.button("Withdraw to Wallet"):
            try:
                nonce = w3.eth.get_transaction_count(addr)
                tx = vault.functions.withdraw(int(wd_amt * 1e6)).build_transaction({
                    "from": addr, "nonce": nonce, "gas": 100000, "gasPrice": w3.eth.gas_price
                })
                signed = w3.eth.account.sign_transaction(tx, key)
                tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
                st.success(f"Withdrawn! TX: {w3.to_hex(tx_hash)}")
            except Exception as e:
                st.error(str(e))

        # Withdraw to another address
        st.subheader("Send USDC to Another Wallet")
        to = st.text_input("Recipient Address")
        amt2 = st.number_input("Amount", min_value=0.000001, step=0.01, key="send")
        if st.button("Send USDC"):
            try:
                nonce = w3.eth.get_transaction_count(addr)
                tx = vault.functions.withdrawTo(to, int(amt2 * 1e6)).build_transaction({
                    "from": addr, "nonce": nonce, "gas": 120000, "gasPrice": w3.eth.gas_price
                })
                signed = w3.eth.account.sign_transaction(tx, key)
                tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
                st.success(f"Sent! TX: {w3.to_hex(tx_hash)}")
            except Exception as e:
                st.error("Send error: " + str(e))

        if st.button("Logout"):
            st.session_state.clear()
            st.success("Logged out.")
