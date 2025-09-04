import asyncio
import logging
import os
import struct
from typing import Final

from construct import Bytes, Flag, Int64ul, Struct
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey

# These imports are from the pumpfun-bonkfun-bot `src` directory,
# which is installed as an editable package.
from core.client import SolanaClient
from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
from interfaces.core import Platform, TokenInfo
from monitoring.listener_factory import ListenerFactory
from platforms import platform_factory
from utils.logger import get_logger

load_dotenv()

def setup_logging():
    """Configures logging to both file and console."""
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        handlers=[logging.FileHandler("aurabot.log"), logging.StreamHandler()],
    )


setup_logging()
logger = get_logger(__name__)

# --- Bonding Curve Parsing Logic (from get_bonding_curve_status.py) ---

BONDING_CURVE_DISCRIMINATOR: Final[bytes] = struct.pack("<Q", 6966180631402821399)


class BondingCurveState:
    """
    A simplified parser for the bonding curve account state, based on the
    working logic in the `get_bonding_curve_status.py` example.
    """

    _STRUCT_V1 = Struct(
        "virtual_token_reserves" / Int64ul,
        "virtual_sol_reserves" / Int64ul,
        "real_token_reserves" / Int64ul,
        "real_sol_reserves" / Int64ul,
        "token_total_supply" / Int64ul,
        "complete" / Flag,
    )
    _STRUCT_V2 = Struct(
        "virtual_token_reserves" / Int64ul,
        "virtual_sol_reserves" / Int64ul,
        "real_token_reserves" / Int64ul,
        "real_sol_reserves" / Int64ul,
        "token_total_supply" / Int64ul,
        "complete" / Flag,
        "creator" / Bytes(32),
    )

    def __init__(self, data: bytes) -> None:
        """Parse bonding curve data."""
        if data[:8] != BONDING_CURVE_DISCRIMINATOR:
            raise ValueError("Invalid curve state discriminator")

        # The example uses a length check to determine the struct version.
        parsed = self._STRUCT_V2.parse(data[8:]) if len(data) > 150 else self._STRUCT_V1.parse(data[8:])
        self.__dict__.update(parsed)
        if hasattr(self, "creator") and isinstance(self.creator, bytes):
            self.creator = Pubkey.from_bytes(self.creator)

async def on_new_token(token_info: TokenInfo, solana_client: SolanaClient):
    """
    This is the callback function that will be executed when a new token is detected.
    It serves as the core of the on-chain data collector.
    """
    logger.info(f"🚀 New Token Detected on {token_info.platform.value}!")
    logger.info(f"   - Name: {token_info.name}, Symbol: {token_info.symbol}")
    logger.info(f"   - Mint: {token_info.mint}")
    logger.info(f"   - Creator: {token_info.creator}")

    try:
        # Get the platform-specific implementations (curve manager, etc.)
        implementations = platform_factory.create_for_platform(
            token_info.platform, solana_client
        )
        address_provider = implementations.address_provider

        # Derive the bonding curve address from the mint, which is the most reliable
        # method, as seen in the working `get_bonding_curve_status.py` example.
        pool_address = address_provider.derive_pool_address(token_info.mint)

        # Log both for comparison and debugging.
        logger.info(f"   - Bonding Curve (from event): {token_info.bonding_curve}")
        logger.info(f"   - Bonding Curve (derived):    {pool_address}")

        if str(token_info.bonding_curve) != str(pool_address):
            logger.warning("   - MISMATCH: Bonding curve from event and derived address do not match!")

        # Retry logic to handle RPC propagation delay
        max_retries = 5
        retry_delay = 1.5  # seconds

        for attempt in range(max_retries):
            try:
                # Use a direct AsyncClient call, as seen in the working example,
                # to bypass any potential issues in the abstraction layers.
                rpc_url = os.getenv("SOLANA_NODE_RPC_ENDPOINT")
                async with AsyncClient(rpc_url) as client:
                    response = await client.get_account_info(
                        pool_address, encoding="base64", commitment=Confirmed
                    )

                if not response.value or not response.value.data:
                    raise ValueError(f"No data in bonding curve account {pool_address}")

                # Parse the data using the logic from the example
                curve_state = BondingCurveState(response.value.data)

                # Manually calculate price and reserves from the parsed state
                if curve_state.virtual_token_reserves > 0:
                    price_lamports = curve_state.virtual_sol_reserves / curve_state.virtual_token_reserves
                    initial_price = price_lamports * (10**TOKEN_DECIMALS) / LAMPORTS_PER_SOL
                else:
                    initial_price = 0.0

                reserves = (curve_state.virtual_token_reserves, curve_state.virtual_sol_reserves)

                logger.info("✅ Successfully fetched initial on-chain data:")
                logger.info(f"   - Initial Price: {initial_price:.12f} SOL")
                logger.info(f"   - Token Reserves: {reserves[0]}")
                logger.info(f"   - SOL Reserves: {reserves[1]}")
                logger.info("-" * 50)
                # Here you would save the combined data to your dataset for the pipeline
                return  # Exit the function on success

            except ValueError as e:
                # Catch errors indicating the account isn't ready yet.
                # This is more robust than just checking for "Account not found", as other
                # propagation issues can raise different but related ValueErrors.
                error_str = str(e)
                if ("Account not found" in error_str or "Invalid bonding curve state" in error_str) and attempt < max_retries - 1:
                    logger.warning(
                        f"Bonding curve for {token_info.symbol} not found on attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    raise e  # Re-raise the exception if it's not 'Account not found' or on the last retry

    except Exception as e:
        logger.error(f"❌ Failed to fetch on-chain data for {token_info.mint}: {e}")


async def main():
    """
    Main entry point for the Aurabot On-Chain Data Collector.
    """
    print("🚀 Aurabot starting up...")

    rpc_url = os.getenv("SOLANA_NODE_RPC_ENDPOINT")
    wss_url = os.getenv("SOLANA_NODE_WSS_ENDPOINT")

    if not rpc_url or not wss_url:
        logger.error(
            "❌ SOLANA_NODE_RPC_ENDPOINT and SOLANA_NODE_WSS_ENDPOINT must be set."
        )
        return

    solana_client = SolanaClient(rpc_url)

    # Create a listener for the pump.fun platform
    listener = ListenerFactory.create_listener(
        listener_type="logs",  # 'logs' is a great starting point
        wss_endpoint=wss_url,
        platforms=[Platform.PUMP_FUN],
    )

    logger.info("Starting On-Chain Data Collector for pump.fun...")
    logger.info("Listening for new token launches. Press Ctrl+C to stop.")

    # The listener will run indefinitely, calling on_new_token for each new token
    await listener.listen_for_tokens(
        lambda token_info: on_new_token(token_info, solana_client)
    )


if __name__ == "__main__":
    asyncio.run(main())
