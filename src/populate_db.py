import asyncio
import logging
from card_db import CardDBClient, DBSpecialist
from common import SetInfo, CardInfo, PriceInfo
from mtg_json import MTGJsonLoader

logger = logging.getLogger(__name__)

async def main():
    logger.debug("Starting populate_db.main()")
    async with CardDBClient() as client:
        specialist = DBSpecialist(client, "set_info", SetInfo)
        await specialist.write_items(MTGJsonLoader().load_sets(), exclude_fields=["cards"])
        specialist = DBSpecialist(client, "card_info", CardInfo)
        await specialist.write_items(MTGJsonLoader().load_cards())
        
        # Get all card IDs from the database to filter price records
        logger.debug("Fetching card IDs from database...")
        card_ids_result = await client.execute_query("SELECT uuid FROM card_info")
        existing_card_ids = {row['uuid'] for row in card_ids_result}
        logger.debug(f"Found {len(existing_card_ids)} cards in database")
        
        # Filter price records to only include cards that exist
        all_price_records = MTGJsonLoader().load_price_records()
        filtered_price_records = [
            record for record in all_price_records 
            if record.card_id in existing_card_ids
        ]
        logger.debug(f"Filtered {len(all_price_records)} price records to {len(filtered_price_records)} records for existing cards")
        
        specialist = DBSpecialist(client, "price_info", PriceInfo)
        await specialist.write_items(
            filtered_price_records,
            conflict_column=["card_id", "source_name", "price_type", "finish_type", "date_priced"]
        )

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main())