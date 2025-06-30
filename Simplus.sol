// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface ICUSDC {
    function mint(uint256 amount) external returns (uint256);
    function redeem(uint256 amount) external returns (uint256);
    function balanceOf(address account) external view returns (uint256);
}

contract SimplusVault is Ownable {
    IERC20 public usdc;
    ICUSDC public cUsdc;

    struct Wallet {
        address user;
        uint256 deposit;
        bool exists;
    }

    mapping(address => Wallet) public userWallets;
    uint256 public minimumDeposit;

    event WalletCreated(address indexed user);
    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);

    constructor(address _usdc, address _cUsdc) Ownable(msg.sender) {
        usdc = IERC20(_usdc);
        cUsdc = ICUSDC(_cUsdc);
        minimumDeposit = 1 * 10**6; // $1 USDC in 6 decimals
    }

    // --- Admin creates a new wallet (off-chain password logic) ---
    function registerWallet(address user) external onlyOwner {
        require(!userWallets[user].exists, "Wallet already exists");
        userWallets[user] = Wallet(user, 0, true);
        emit WalletCreated(user);
    }

    // --- Deposit USDC ---
    function deposit(uint256 amount) external {
        require(userWallets[msg.sender].exists, "Wallet not registered");
        require(amount >= minimumDeposit, "Deposit below minimum");
        require(usdc.transferFrom(msg.sender, address(this), amount), "Transfer failed");

        userWallets[msg.sender].deposit += amount;
        emit Deposited(msg.sender, amount);
    }

    // --- Withdraw to own wallet ---
    function withdraw(uint256 amount) external {
        require(userWallets[msg.sender].exists, "Wallet not registered");
        require(userWallets[msg.sender].deposit >= amount, "Insufficient balance");
        require(usdc.transfer(msg.sender, amount), "Withdraw transfer failed");

        userWallets[msg.sender].deposit -= amount;
        emit Withdrawn(msg.sender, amount);
    }

    // --- Withdraw to external address ---
    function withdrawTo(address recipient, uint256 amount) external {
        require(userWallets[msg.sender].exists, "Wallet not registered");
        require(userWallets[msg.sender].deposit >= amount, "Insufficient balance");
        require(usdc.transfer(recipient, amount), "Withdraw transfer failed");

        userWallets[msg.sender].deposit -= amount;
        emit Withdrawn(msg.sender, amount);
    }

    // --- View Balance ---
    function userBalance(address user) external view returns (uint256) {
        return userWallets[user].deposit;
    }

    function vaultUSDCBalance() external view returns (uint256) {
        return usdc.balanceOf(address(this));
    }

    function vaultCUSDCBalance() external view returns (uint256) {
        return cUsdc.balanceOf(address(this));
    }

    // --- Admin-only: Set minimum deposit amount ---
    function setMinimumDeposit(uint256 amount) external onlyOwner {
        require(amount >= 1, "Minimum must be >= 1");
        minimumDeposit = amount;
    }
}
