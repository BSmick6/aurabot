import json
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
            print(f"\n--- Transaction {i+1} ---")
            
            # Fetch the full transaction data
            transaction_data = client.get_transaction(
                sig.signature,
                commitment="confirmed",
                max_supported_transaction_version=0
            )

            # First, convert the response object to a JSON string, then parse it into a Python dict.
            data_as_dict = json.loads(transaction_data.to_json())
            # Safely access and pretty-print the instructions
            instructions = data_as_dict.get("result", {}).get("transaction", {}).get("message", {}).get("instructions")
            if instructions:
                # Check if there is a second instruction (at index 1)
                if len(instructions) > 1:
                    second_instruction = instructions[1]
                    # Safely get the 'data' field from the second instruction
                    data_field = second_instruction.get("data")
                    if data_field:
                        print(f"  Data from second instruction: {data_field}")
                    else:
                        print("  'data' field not found in the second instruction.")
                else:
                    print("  Transaction does not have a second instruction.")
            else:
                print("  No instructions found in this transaction.")
    else:
        print("No transactions found for the specified program ID.")

except Exception as e:
    print(f"An error occurred: {e}")
