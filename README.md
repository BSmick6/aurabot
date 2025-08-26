# Aurabot

A bot that senses the "aura" or sentiment of the market.

## Roadmap

1. **Data Pipeline MVP**: Successfully collect and synchronize on-chain and off-chain data.

   1. **On-Chain Data Collector**: A script that successfully connects to an RPC node and fetches the transaction history for a new token launch. Your goal is just to get data flowing.

   2. **Off-Chain Data Collector**: A script that successfully connects to a social media API (e.g., for TikTok or X) and fetches data for a specific keyword.

   3. **Data Synchronizer**: A script that takes the outputs of 1.1 and 1.2 and combines them into a single, clean, time-stamped dataset.

2. **Model MVP**: Train a basic ML model on the synced data.

3. **Simulation MVP**: Build a custom backtesting engine to simulate historical performance.

4. **Live Prep MVP**: Implement a "paper trading" bot to run on live data.
