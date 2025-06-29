import streamlit as st
from eth_account import Account
from web3 import Web3
import secrets
import os
import json
import time

# --- CONFIGURATION ---
INFURA_URL = "https://sepolia.infura.io/v3/e0fcce634506410b87fc31064eed915a"
SIMPLETH_CONTRACT_ADDRESS = "0xe0271f5571AB60dD89EF11F1743866a213406542"
STETH_CONTRACT_ADDRESS = "0xFD5d07334591C3eE2699639Bb670de279ea45f65"
UNISWAP_ROUTER = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"  # Uniswap V3 router on Sepolia
UNISWAP_POOL_FEE = 3000  # 0.3%
WALLET_DB_FILE = "wallet_db.json"

STETH_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

SIMPLETH_ABI = STETH_ABI

UNISWAP_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenIn", "type": "address"},
            {"internalType": "address", "name": "tokenOut", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
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

if not w3.is_connected():
    st.error("❌ Web3 provider not connected. Check your INFURA_URL.")
    st.stop()

if "wallet_db" not in st.session_state:
    st.session_state["wallet_db"] = load_wallet_db()
if "last_created_wallet" not in st.session_state:
    st.session_state["last_created_wallet"] = None
if "logged_in_wallet" not in st.session_state:
    st.session_state["logged_in_wallet"] = None

st.set_page_config(page_title="Simpleth Wallet", page_icon="🦊")
st.title("🦊 Simpleth Wallet")

mode = st.radio("Select mode:", ["Admin", "User"])

# --- ADMIN MODE ---
if mode == "Admin":
    st.header("Admin Panel")
    st.markdown("Create wallets for users and view balances.")

    with st.expander("Create a New Simpleth Wallet"):
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
            st.info("Share this wallet address and access code with the user.")

            # Show balances after creation
            try:
                steth_contract = w3.eth.contract(address=Web3.to_checksum_address(STETH_CONTRACT_ADDRESS), abi=STETH_ABI)
                steth_balance = steth_contract.functions.balanceOf(wallet_address).call()
                st.write(f"**stETH balance in wallet:** {steth_balance / 1e18} stETH")
            except Exception as e:
                st.error(f"Error fetching stETH wallet balance: {e}")
            try:
                simpleth_contract = w3.eth.contract(address=Web3.to_checksum_address(SIMPLETH_CONTRACT_ADDRESS), abi=SIMPLETH_ABI)
                balance = simpleth_contract.functions.balanceOf(wallet_address).call()
                st.write(f"**stETH balance in Simpleth:** {balance / 1e18} stETH")
            except Exception as e:
                st.error(f"Error fetching Simpleth balance: {e}")

    if st.session_state.get("last_created_wallet"):
        wallet_address = st.session_state["last_created_wallet"]
        wallet_info = st.session_state["wallet_db"].get(wallet_address)
        if wallet_info:
            with st.expander("Show Private Key for Last Created Wallet (for testing only)"):
                st.code(wallet_info["private_key"], language="text")

    st.markdown("---")
    st.subheader("Access Any Simpleth Wallet")
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
            # Show balances after login
            try:
                steth_contract = w3.eth.contract(address=Web3.to_checksum_address(STETH_CONTRACT_ADDRESS), abi=STETH_ABI)
                steth_balance = steth_contract.functions.balanceOf(input_address_checksum).call()
                st.write(f"**stETH balance in wallet:** {steth_balance / 1e18} stETH")
            except Exception as e:
                st.error(f"Error fetching stETH wallet balance: {e}")
            try:
                simpleth_contract = w3.eth.contract(address=Web3.to_checksum_address(SIMPLETH_CONTRACT_ADDRESS), abi=SIMPLETH_ABI)
                balance = simpleth_contract.functions.balanceOf(input_address_checksum).call()
                st.write(f"**stETH balance in Simpleth:** {balance / 1e18} stETH")
            except Exception as e:
                st.error(f"Error fetching Simpleth balance: {e}")
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

    st.markdown("---")
    st.markdown("""
    **Admin Instructions:**  
    To pre-deposit stETH (or mock stETH) for a user, send tokens to their wallet address, then have the user approve and deposit into Simpleth using your contract's functions.
    """)

# --- USER MODE ---
if mode == "User":
    st.header("User Wallet Access")
    st.markdown("Log in with your wallet address and access code (provided by the admin).")

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
        wallet_db = load_wallet_db()
        wallet_info = wallet_db.get(wallet_address)
        st.markdown(f"### Wallet: `{wallet_address}`")

        # Show stETH balance
        try:
            steth_contract = w3.eth.contract(address=Web3.to_checksum_address(STETH_CONTRACT_ADDRESS), abi=STETH_ABI)
            steth_balance = steth_contract.functions.balanceOf(wallet_address).call()
            st.write(f"**stETH balance:** {steth_balance / 1e18} stETH")
        except Exception as e:
            st.error(f"Error fetching stETH balance: {e}")

        # --- Swap stETH to ETH ---
        st.markdown("#### Swap stETH to ETH")
        swap_amount = st.number_input("Amount of stETH to swap for ETH", min_value=0.0, step=0.01, key="swap_amount")
        if st.button("Swap stETH for ETH"):
            if swap_amount <= 0:
                st.error("Enter a positive amount.")
            elif steth_balance / 1e18 < swap_amount:
                st.error("Insufficient stETH balance.")
            else:
                try:
                    private_key = wallet_info["private_key"]
                    # Approve Uniswap router to spend stETH
                    approve_tx = steth_contract.functions.approve(
                        UNISWAP_ROUTER, int(swap_amount * 1e18)
                    ).build_transaction({
                        "from": wallet_address,
                        "nonce": w3.eth.get_transaction_count(wallet_address),
                        "gas": 100000,
                        "gasPrice": w3.eth.gas_price,
                    })
                    signed_approve = w3.eth.account.sign_transaction(approve_tx, private_key)
                    approve_hash = w3.eth.send_raw_transaction(signed_approve.rawTransaction)
                    st.info(f"Approve transaction sent: {w3.to_hex(approve_hash)}")
                    w3.eth.wait_for_transaction_receipt(approve_hash)

                    # Swap stETH for ETH
                    router = w3.eth.contract(address=Web3.to_checksum_address(UNISWAP_ROUTER), abi=UNISWAP_ABI)
                    deadline = int(time.time()) + 600
                    swap_tx = router.functions.exactInputSingle(
                        STETH_CONTRACT_ADDRESS,
                        "0xC778417E063141139Fce010982780140Aa0cD5Ab",  # WETH address on Sepolia (update if needed)
                        UNISWAP_POOL_FEE,
                        wallet_address,
                        deadline,
                        int(swap_amount * 1e18),
                        0,  # Accept any amount of ETH out (for testnet)
                        0
                    ).build_transaction({
                        "from": wallet_address,
                        "nonce": w3.eth.get_transaction_count(wallet_address),
                        "gas": 400000,
                        "gasPrice": w3.eth.gas_price,
                        "value": 0
                    })
                    signed_swap = w3.eth.account.sign_transaction(swap_tx, private_key)
                    swap_hash = w3.eth.send_raw_transaction(signed_swap.rawTransaction)
                    st.success(f"Swap transaction sent: {w3.to_hex(swap_hash)}")
                except Exception as e:
                    st.error(f"Swap failed: {e}")

        # --- Withdraw ETH to any address ---
        st.markdown("#### Withdraw ETH to Any Address")
        eth_balance = w3.eth.get_balance(wallet_address) / 1e18
        st.write(f"**ETH balance:** {eth_balance} ETH")
        withdraw_to = st.text_input("Recipient ETH address", key="user_withdraw_to")
        withdraw_eth_amount = st.number_input("Amount of ETH to withdraw", min_value=0.0, step=0.01, key="user_withdraw_eth_amount")
        if st.button("Withdraw ETH"):
            if withdraw_eth_amount <= 0:
                st.error("Enter a positive amount.")
            elif eth_balance < withdraw_eth_amount:
                st.error("Insufficient ETH balance.")
            elif not Web3.is_address(withdraw_to):
                st.error("Invalid recipient address.")
            else:
                try:
                    private_key = wallet_info["private_key"]
                    tx = {
                        "from": wallet_address,
                        "to": Web3.to_checksum_address(withdraw_to),
                        "value": int(withdraw_eth_amount * 1e18),
                        "gas": 21000,
                        "gasPrice": w3.eth.gas_price,
                        "nonce": w3.eth.get_transaction_count(wallet_address)
                    }
                    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
                    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                    st.success(f"ETH withdrawal transaction sent: {w3.to_hex(tx_hash)}")
                except Exception as e:
                    st.error(f"ETH withdrawal failed: {e}")

        # --- Show Private Key (Optional, for testing only) ---
        with st.expander("Show Private Key (for testing only)"):
            st.code(wallet_info["private_key"], language="text")

        if st.button("Logout (User)"):
            st.session_state["logged_in_wallet"] = None
            st.success("Logged out.")

    st.markdown("---")
    st.markdown("""
    **Note:**  
    - Swapping and withdrawing are real blockchain transactions and require gas (ETH) in the wallet.
    - Always double-check recipient addresses.
    - This is for Sepolia testnet; use with test tokens only.
    """)
