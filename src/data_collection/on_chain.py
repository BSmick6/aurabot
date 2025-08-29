from solana.rpc.api import Client
from solders.pubkey import Pubkey

# Your dedicated RPC URL
RPC_URL = "https://api.devnet.solana.com"
client = Client(RPC_URL)

# The official pump.fun Devnet program ID
PUMP_FUN_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")

# Fetch the most recent transaction signatures associated with the program ID
print("Fetching recent transactions for pump.fun...")
try:
    signatures = client.get_signatures_for_address(PUMP_FUN_PROGRAM_ID).value

    # Print the signatures of the last 10 transactions
    if signatures:
        print(f"Found {len(signatures)} recent transactions. Here are the first 10:")
        for i, sig in enumerate(signatures[:10]):
            print(f"{i + 1}. Signature: {sig.signature}")
    else:
        print("No transactions found for the specified program ID.")

except Exception as e:
    print(f"An error occurred: {e}")
