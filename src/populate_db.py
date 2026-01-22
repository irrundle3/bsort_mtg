import asyncio
import logging
from card_db import CardDBClient, DBSpecialist
from common import SetInfo, CardInfo, PriceInfo, PriceInfoRaw
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
        all_price_records_raw = MTGJsonLoader().load_price_records()
        filtered_price_records_raw = [
            record for record in all_price_records_raw 
            if record.card_id in existing_card_ids
        ]
        for missing_card_in in [record for record in all_price_records_raw if record.card_id not in existing_card_ids]:
            logger.warning(f"Card {missing_card_in.card_id} not found in database")
        logger.debug(f"Filtered {len(all_price_records_raw)} price records to {len(filtered_price_records_raw)} records for existing cards")
        
        # Normalize price records: convert source_name and currency to IDs
        # The lookup cache is automatically loaded when the client connects
        logger.debug("Normalizing price records...")
        normalized_price_records = []
        for record in filtered_price_records_raw:
            source_id = await client.lookup_cache.get_or_create_source_id(record.source_name)
            currency_id = await client.lookup_cache.get_or_create_currency_id(record.currency)
            
            normalized_price_records.append(PriceInfo(
                card_id=record.card_id,
                source_id=source_id,
                currency_id=currency_id,
                price_type=record.price_type,
                finish_type=record.finish_type,
                date_priced=record.date_priced,
                price=record.price
            ))
        
        logger.debug(f"Normalized {len(normalized_price_records)} price records")
        
        specialist = DBSpecialist(client, "price_info", PriceInfo)
        await specialist.write_items(
            normalized_price_records,
            conflict_column=["card_id", "source_id", "currency_id", "price_type", "finish_type", "date_priced"]
        )

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main())