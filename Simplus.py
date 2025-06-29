import streamlit as st
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

# --- CONFIG ---
INFURA_URL = "https://sepolia.infura.io/v3/e0fcce634506410b87fc31064eed915a"
USDC_ADDRESS = "0x2Bc7c4Afc076088DB03366a6CA9729ba9E450DaA"  # USDC token contract on Sepolia
VAULT_ADDRESS = "0x7263b8726C96566927626773CbD6B19d32ff76E3"  # Your deployed SimplusVault

# --- ABIs ---
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
        "stateMutability": "view"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
        "stateMutability": "nonpayable"
    },
]

VAULT_ABI = [
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

# --- Web3 setup ---
w3 = Web3(Web3.HTTPProvider(INFURA_URL))
usdc_contract = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
vault_contract = w3.eth.contract(address=VAULT_ADDRESS, abi=VAULT_ABI)

st.title("Simplus Vault - USDC on Sepolia")

# --- User login ---
private_key = st.text_input("Enter your wallet private key (for signing transactions)", type="password")

if private_key:
    try:
        account = Account.from_key(private_key)
        user_address = account.address
        st.success(f"Logged in as: {user_address}")

        # Display balances
        try:
            usdc_balance = usdc_contract.functions.balanceOf(user_address).call()
            user_deposit = vault_contract.functions.userDepositOf(user_address).call()
            vault_balance = vault_contract.functions.vaultUSDCBalance().call()

            st.write(f"Your USDC Wallet Balance: {usdc_balance / 1e6:.6f} USDC")
            st.write(f"Your Deposited USDC in Vault: {user_deposit / 1e6:.6f} USDC")
            st.write(f"Total USDC in Vault: {vault_balance / 1e6:.6f} USDC")

        except Exception as e:
            st.error(f"Error fetching balances: {e}")

        # --- Deposit USDC ---
        st.header("Deposit USDC to Vault")
        deposit_amount = st.number_input("Amount of USDC to deposit", min_value=0.0, step=0.000001)
        if st.button("Deposit"):
            if deposit_amount <= 0:
                st.error("Enter a valid deposit amount")
            elif usdc_balance < int(deposit_amount * 1e6):
                st.error("Insufficient USDC balance")
            else:
                try:
                    nonce = w3.eth.get_transaction_count(user_address)
                    amount_wei = int(deposit_amount * 1e6)

                    # Approve vault to spend USDC
                    approve_tx = usdc_contract.functions.approve(VAULT_ADDRESS, amount_wei).build_transaction({
                        'from': user_address,
                        'nonce': nonce,
                        'gas': 100000,
                        'gasPrice': w3.eth.gas_price,
                    })
                    signed_approve = w3.eth.account.sign_transaction(approve_tx, private_key)
                    approve_hash = w3.eth.send_raw_transaction(signed_approve.rawTransaction)
                    st.info(f"Approve tx sent: {w3.to_hex(approve_hash)}")
                    w3.eth.wait_for_transaction_receipt(approve_hash)

                    # Deposit
                    nonce += 1
                    deposit_tx = vault_contract.functions.deposit(amount_wei).build_transaction({
                        'from': user_address,
                        'nonce': nonce,
                        'gas': 200000,
                        'gasPrice': w3.eth.gas_price,
                    })
                    signed_deposit = w3.eth.account.sign_transaction(deposit_tx, private_key)
                    deposit_hash = w3.eth.send_raw_transaction(signed_deposit.rawTransaction)
                    st.success(f"Deposit tx sent: {w3.to_hex(deposit_hash)}")

                except Exception as e:
                    st.error(f"Deposit failed: {e}")

        # --- Withdraw USDC ---
        st.header("Withdraw USDC from Vault")
        withdraw_amount = st.number_input("Amount of USDC to withdraw", min_value=0.0, step=0.000001)
        if st.button("Withdraw"):
            if withdraw_amount <= 0:
                st.error("Enter a valid withdraw amount")
            elif user_deposit < int(withdraw_amount * 1e6):
                st.error("Insufficient deposited balance")
            else:
                try:
                    nonce = w3.eth.get_transaction_count(user_address)
                    amount_wei = int(withdraw_amount * 1e6)

                    withdraw_tx = vault_contract.functions.withdraw(amount_wei).build_transaction({
                        'from': user_address,
                        'nonce': nonce,
                        'gas': 200000,
                        'gasPrice': w3.eth.gas_price,
                    })
                    signed_withdraw = w3.eth.account.sign_transaction(withdraw_tx, private_key)
                    withdraw_hash = w3.eth.send_raw_transaction(signed_withdraw.rawTransaction)
                    st.success(f"Withdraw tx sent: {w3.to_hex(withdraw_hash)}")
                except Exception as e:
                    st.error(f"Withdraw failed: {e}")

    except Exception as e:
        st.error(f"Invalid private key: {e}")
else:
    st.info("Please enter your private key to log in.")

st.markdown("---")
st.markdown("**Note:** You need Sepolia testnet USDC and ETH for gas to interact with this vault.")
