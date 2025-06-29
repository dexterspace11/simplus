import streamlit as st
from eth_account import Account
from web3 import Web3
import secrets
import os
import json
import time

# --- CONFIGURATION ---
INFURA_URL = "https://sepolia.infura.io/v3/e0fcce634506410b87fc31064eed915a"
USDC_CONTRACT_ADDRESS = "0x2Bc7c4Afc076088DB03366a6CA9729ba9E450DaA"  # Replace with real USDC Sepolia address
SIMPLUS_VAULT_CONTRACT_ADDRESS = "0x7263b8726C96566927626773CbD6B19d32ff76E3"  # If any
WALLET_DB_FILE = "wallet_db.json"

# Minimal ERC20 ABI for balanceOf, transfer, approve
ERC20_ABI = [
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
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "success", "type": "bool"}],
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

def load_wallet_db():
    if os.path.exists(WALLET_DB_FILE):
        with open(WALLET_DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_wallet_db(db):
    with open(WALLET_DB_FILE, "w") as f:
        json.dump(db, f)

w3 = Web3(Web3.HTTPProvider(INFURA_URL))

if not w3.isConnected():
    st.error("❌ Web3 provider not connected. Check your INFURA_URL.")
    st.stop()

if "wallet_db" not in st.session_state:
    st.session_state["wallet_db"] = load_wallet_db()
if "last_created_wallet" not in st.session_state:
    st.session_state["last_created_wallet"] = None
if "logged_in_wallet" not in st.session_state:
    st.session_state["logged_in_wallet"] = None

st.set_page_config(page_title="Simplus Vault", page_icon="💼")
st.title("💼 Simplus Vault")

mode = st.radio("Select mode:", ["Admin", "User"])

usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_CONTRACT_ADDRESS), abi=ERC20_ABI)

MINIMUM_DEPOSIT = 1 * 10**6  # $1 USDC with 6 decimals

# --- ADMIN MODE ---
if mode == "Admin":
    st.header("Admin Panel")
    st.markdown("Create new wallets and view balances.")

    with st.expander("Create a New Wallet"):
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
            st.session_state["last_created_wallet"] = wallet_address
            st.success("Wallet created!")
            st.write(f"**Wallet Address:** `{wallet_address}`")
            st.write(f"**Access Code:** `{access_code}`")
            st.info("Share the wallet address and access code securely with the user.")

    if st.session_state.get("last_created_wallet"):
        wallet_address = st.session_state["last_created_wallet"]
        wallet_info = st.session_state["wallet_db"].get(wallet_address)
        if wallet_info:
            with st.expander("Show Private Key for Last Created Wallet (for testing only)"):
                st.code(wallet_info["private_key"], language="text")

    st.markdown("---")
    st.subheader("Access Any Wallet")
    input_address = st.text_input("Wallet Address (Admin)", key="admin_login_address")
    input_code = st.text_input("Access Code (Admin)", type="password", key="admin_login_code")

    if st.button("Admin Login"):
        wallet_db = load_wallet_db()
        try:
            input_address_checksum = Web3.to_checksum_address(input_address)
        except Exception:
            st.error("Invalid wallet address format.")
            st.stop()
        wallet_info = wallet_db.get(input_address_checksum)
        if wallet_info and input_code == wallet_info["access_code"]:
            st.success("Access granted!")
            st.session_state["logged_in_wallet"] = input_address_checksum
            # Show USDC balance after login
            try:
                balance = usdc_contract.functions.balanceOf(input_address_checksum).call()
                st.write(f"**USDC balance:** {balance / 1e6} USDC")
            except Exception as e:
                st.error(f"Error fetching USDC balance: {e}")
        else:
            st.error("Invalid wallet address or access code.")

    if st.session_state.get("logged_in_wallet"):
        wallet_address = st.session_state["logged_in_wallet"]
        wallet_info = st.session_state["wallet_db"].get(wallet_address)
        if wallet_info:
            with st.expander("Show Private Key for Last Logged In Wallet (for testing only)"):
                st.code(wallet_info["private_key"], language="text")
        if st.button("Logout (Admin)"):
            st.session_state["logged_in_wallet"] = None
            st.success("Logged out.")

# --- USER MODE ---
if mode == "User":
    st.header("User Wallet Access")
    st.markdown("Log in with your wallet address and access code (provided by admin).")

    input_address = st.text_input("Wallet Address", key="user_login_address")
    input_code = st.text_input("Access Code", type="password", key="user_login_code")

    if st.button("User Login"):
        wallet_db = load_wallet_db()
        try:
            input_address_checksum = Web3.to_checksum_address(input_address)
        except Exception:
            st.error("Invalid wallet address format.")
            st.stop()
        wallet_info = wallet_db.get(input_address_checksum)
        if wallet_info and input_code == wallet_info["access_code"]:
            st.success("Access granted!")
            st.session_state["logged_in_wallet"] = input_address_checksum
        else:
            st.error("Invalid wallet address or access code.")

    if st.session_state.get("logged_in_wallet"):
        wallet_address = st.session_state["logged_in_wallet"]
        wallet_info = st.session_state["wallet_db"].get(wallet_address)
        st.markdown(f"### Wallet: `{wallet_address}`")

        # Show USDC balance
        try:
            balance = usdc_contract.functions.balanceOf(wallet_address).call()
            st.write(f"**USDC balance:** {balance / 1e6} USDC")
        except Exception as e:
            st.error(f"Error checking balance: {e}")

        # Withdraw USDC
        st.markdown("#### Withdraw USDC")
        withdraw_amount = st.number_input("Amount of USDC to withdraw", min_value=0.0, step=0.01, key="withdraw_amount")
        withdraw_to = st.text_input("Recipient USDC address", key="withdraw_to_address")

        if st.button("Withdraw USDC"):
            if withdraw_amount <= 0:
                st.error("Enter a positive amount.")
            elif not Web3.is_address(withdraw_to):
                st.error("Invalid recipient address.")
            else:
                try:
                    private_key = wallet_info["private_key"]
                    nonce = w3.eth.get_transaction_count(wallet_address)
                    tx = usdc_contract.functions.transfer(
                        Web3.to_checksum_address(withdraw_to),
                        int(withdraw_amount * 1e6)
                    ).build_transaction({
                        "from": wallet_address,
                        "nonce": nonce,
                        "gas": 100000,
                        "gasPrice": w3.eth.gas_price,
                    })
                    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
                    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                    st.success(f"Withdraw transaction sent: {w3.to_hex(tx_hash)}")
                except Exception as e:
                    st.error(f"Withdraw failed: {e}")

        st.markdown("---")
        st.markdown("#### Deposit USDC")
        st.markdown("To deposit USDC, send tokens to your wallet address from another wallet.")

        # Placeholder for Compound / Uniswap connect button
        st.markdown("---")
        st.markdown("#### DeFi Integration (Coming Soon)")
        st.info("Connect to Compound, Uniswap, and other DeFi apps coming soon!")

        # Show private key for testing only
        with st.expander("Show Private Key (for testing only)"):
            st.code(wallet_info["private_key"], language="text")

        if st.button("Logout (User)"):
            st.session_state["logged_in_wallet"] = None
            st.success("Logged out.")

st.markdown("---")
st.markdown("""
**Notes:**

- Deposits: send USDC to your wallet address from an external wallet or exchange.
- Withdrawals: signed and sent directly from this app using your stored private key.
- Microtransactions supported due to USDC 6 decimals.
- This app is connected to the Sepolia testnet.
- Keep your access code secure.
""")
