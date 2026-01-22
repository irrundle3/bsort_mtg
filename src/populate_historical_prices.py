"""
Script to populate historical prices from AllPrices.json.

This processes the large JSON file (1.5GB) in batches to avoid memory issues.
"""
import asyncio
import logging
from typing import List, Optional
from card_db import CardDBClient, DBSpecialist
from common import PriceInfo
import datetime as dt

logger = logging.getLogger(__name__)

async def populate_historical_prices(batch_size: int = 10000, earliest_date: Optional[dt.date] = None):
    """
    Populate historical prices from AllPrices.json.
    
    Args:
        batch_size: Number of records to process and insert at a time
    """
    logger.info("Starting historical price population...")
    
    async with CardDBClient() as client:
        # Get all card IDs from the database to filter price records
        logger.info("Fetching card IDs from database...")
        card_ids_result = await client.execute_query("SELECT uuid FROM card_info")
        existing_card_ids = {row['uuid'] for row in card_ids_result}
        logger.info(f"Found {len(existing_card_ids)} cards in database")
        
        # Process historical prices in batches
        # The client's load_historical_price_records method automatically normalizes records
        batch: List[PriceInfo] = []
        total_processed = 0
        total_inserted = 0
        
        logger.info("Processing historical prices from AllPrices.json...")
        async for record in client.load_historical_price_records(existing_card_ids):
            record: PriceInfo
            # Filter by earliest_date if specified
            if earliest_date is not None and record.date_priced < earliest_date:
                # logger.info(f"Skipping record {record.date_priced} before earliest date {earliest_date}")
                continue
            
            batch.append(record)
            total_processed += 1
            
            # Insert batch when it reaches batch_size
            if len(batch) >= batch_size:
                specialist = DBSpecialist(client, "price_info", PriceInfo)
                await specialist.write_items(
                    batch,
                    conflict_column=["card_id", "source_id", "currency_id", "price_type", "finish_type", "date_priced"]
                )
                total_inserted += len(batch)
                logger.info(f"Inserted batch: {total_inserted:,} total records inserted ({total_processed:,} processed)")
                batch = []
        
        # Insert remaining records
        if batch:
            specialist = DBSpecialist(client, "price_info", PriceInfo)
            await specialist.write_items(
                batch,
                conflict_column=["card_id", "source_id", "currency_id", "price_type", "finish_type", "date_priced"]
            )
            total_inserted += len(batch)
            logger.info(f"Inserted final batch: {total_inserted:,} total records inserted")
        
        logger.info(f"Historical price population complete!")
        logger.info(f"  Total processed: {total_processed:,}")
        logger.info(f"  Total inserted: {total_inserted:,}")

async def find_last_run_date(client: CardDBClient) -> Optional[dt.date]:
    """
    Find the last date that prices were run for.
    """
    result = await client.execute_query("SELECT MAX(date_priced) FROM price_info")
    try:
        return result[0]['max']
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Error parsing date: {e}, last run date is unknown.")
        return None

async def main():
    """Main function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    async with CardDBClient() as client:
        last_run_date = await find_last_run_date(client)
        logger.info(f"Last run date: {last_run_date}")
    
    await populate_historical_prices(batch_size=10000, earliest_date=last_run_date + dt.timedelta(days=1))

if __name__ == "__main__":
    asyncio.run(main())

