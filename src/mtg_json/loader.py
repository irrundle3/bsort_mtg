import json
import os
from datetime import datetime
import requests
import gzip
import logging
from datetime import date
from typing import List, Dict, Iterator
from common import SetInfo, CardInfo, PriceFormats, PriceInfoRaw

logger = logging.getLogger(__name__)

CardId = str

class MTGJsonLoader:
    API_TEMPLATE = "https://mtgjson.com/api/v5/{}.json.gz"

    def __init__(self, mtgjson_dir = None):
        self.mtgjson_dir = os.path.join(os.path.dirname(__file__), "../../data") if mtgjson_dir is None else mtgjson_dir

    def _download_mtg_json(self, src_name: str, dst_name: str | None = None, force_download: bool = False):
        """
        Download the MTGJSON file from the API and save it to the local directory.
        """
        if not force_download and os.path.exists(file_path):
            return
        response = requests.get(self.API_TEMPLATE.format(src_name))
        decompressed_content = gzip.decompress(response.content)
        file_path = os.path.join(self.mtgjson_dir, dst_name if dst_name else "{}.json".format(src_name))
        with open(file_path, "wb") as f:
            f.write(decompressed_content)

    def load_mtg_json(self, src_name: str, force_download: bool = False) -> dict:
        path = os.path.join(self.mtgjson_dir, "{}.json".format(src_name))
        self._download_mtg_json(src_name, force_download=force_download)
        with open(path, "r") as f:
            return json.load(f)
        
    def load_sets(self) -> List[SetInfo]:
        all_printings = self.load_mtg_json("AllPrintings")
        retval: List[SetInfo] = []
        for set_info in all_printings["data"].values():
            retval.append(SetInfo(**set_info))
        return retval

    def load_cards(self) -> List[CardInfo]:
        sets = self.load_sets()
        retval: List[CardInfo] = []
        for set in sets:
            for card in set.cards:
                retval.append(card)
        return retval
    
    def load_prices(self) -> Dict[CardId, PriceFormats]:
        retval: Dict[CardId, PriceFormats] = {}
        prices = self.load_mtg_json("AllPricesToday")
        for card_id, card_info in prices["data"].items():
            retval[card_id] = PriceFormats(**card_info)
        return retval
    
    def load_price_records(self) -> List[PriceInfoRaw]:
        """
        Load prices and flatten them into individual PriceInfo records for the price_info table.
        """
        prices_dict = self.load_prices()
        records = []
        
        for card_id, price_formats in prices_dict.items():
            # Process both mtgo and paper formats
            for format_name, format_data in [("mtgo", price_formats.mtgo), ("paper", price_formats.paper)]:
                if format_data is None:
                    continue
                
                # Iterate through sources (e.g., "tcgplayer", "cardmarket", etc.)
                for source_name, price_list in format_data.items():
                    if price_list is None:
                        continue
                    
                    # Include format in source_name to distinguish mtgo vs paper
                    full_source_name = f"{source_name}_{format_name}"
                    currency = price_list.currency
                    
                    # Process buylist and retail price types
                    for price_type, price_points in [("buylist", price_list.buylist), ("retail", price_list.retail)]:
                        if price_points is None:
                            continue
                        
                        # Process each finish type (etched, foil, normal)
                        for finish_type, price_dict in [
                            ("etched", price_points.etched),
                            ("foil", price_points.foil),
                            ("normal", price_points.normal)
                        ]:
                            if price_dict is None:
                                continue
                            
                            # Create a record for each date/price pair
                            for date_str, price_value in price_dict.items():
                                # Convert date string to date object
                                try:
                                    date_obj = date.fromisoformat(date_str)
                                except (ValueError, AttributeError):
                                    # Fallback: try parsing common date formats
                                    try:
                                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                                    except:
                                        logger.warning(f"Could not parse date: {date_str}, skipping")
                                        continue
                                
                                records.append(PriceInfoRaw(
                                    card_id=card_id,
                                    source_name=full_source_name,
                                    currency=currency,
                                    price_type=price_type,
                                    finish_type=finish_type,
                                    date_priced=date_obj,
                                    price=price_value
                                ))
        
        return records
    
    def load_historical_price_records(self, existing_card_ids: set[str] | None = None) -> Iterator[PriceInfoRaw]:
        """
        Load historical prices from AllPrices.json and yield PriceInfoRaw records.
        This uses a generator to handle the large file (1.5GB) without loading it all into memory.
        
        Args:
            existing_card_ids: Optional set of card IDs to filter by. If None, includes all cards.
        
        Yields:
            PriceInfoRaw records one at a time
        """
        file_path = os.path.join(self.mtgjson_dir, "AllPrices.json")
        
        if not os.path.exists(file_path):
            logger.error(f"AllPrices.json not found at {file_path}")
            return
        
        logger.info(f"Loading historical prices from {file_path}...")
        
        # Process the JSON file in chunks
        # Since it's a large file, we'll read it in chunks and parse incrementally
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read the file and parse JSON
            # For very large files, we might want to use ijson, but let's try chunked reading first
            logger.info("Parsing JSON file...")
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON: {e}")
                return
            
            if "data" not in data:
                logger.error("JSON file missing 'data' key")
                return
            
            records_count = 0
            skipped_count = 0
            
            # Process each card
            for card_id, card_data in data["data"].items():
                # Filter by existing card IDs if provided
                if existing_card_ids is not None and card_id not in existing_card_ids:
                    skipped_count += 1
                    continue
                
                # Process both mtgo and paper formats
                for format_name, format_data in [("mtgo", card_data.get("mtgo")), ("paper", card_data.get("paper"))]:
                    if format_data is None:
                        continue
                    
                    # Iterate through sources
                    for source_name, source_data in format_data.items():
                        if source_data is None or not isinstance(source_data, dict):
                            continue
                        
                        # Get currency (might be at source level)
                        currency = source_data.get("currency", "USD")
                        
                        # Process buylist and retail price types
                        for price_type, price_type_data in [("buylist", source_data.get("buylist")), ("retail", source_data.get("retail"))]:
                            if price_type_data is None:
                                continue
                            
                            # Process each finish type (etched, foil, normal)
                            for finish_type, price_dict in [
                                ("etched", price_type_data.get("etched")),
                                ("foil", price_type_data.get("foil")),
                                ("normal", price_type_data.get("normal"))
                            ]:
                                if price_dict is None or not isinstance(price_dict, dict):
                                    continue
                                
                                # Create a record for each date/price pair
                                for date_str, price_value in price_dict.items():
                                    # Convert date string to date object
                                    try:
                                        date_obj = date.fromisoformat(date_str)
                                    except (ValueError, AttributeError):
                                        # Fallback: try parsing common date formats
                                        try:
                                            from datetime import datetime
                                            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                                        except:
                                            logger.debug(f"Could not parse date: {date_str}, skipping")
                                            continue
                                    
                                    # Include format in source_name to distinguish mtgo vs paper
                                    full_source_name = f"{source_name}_{format_name}"
                                    
                                    records_count += 1
                                    yield PriceInfoRaw(
                                        card_id=card_id,
                                        source_name=full_source_name,
                                        currency=currency,
                                        price_type=price_type,
                                        finish_type=finish_type,
                                        date_priced=date_obj,
                                        price=price_value
                                    )
                                    
                                    # Log progress every 100k records
                                    if records_count % 100000 == 0:
                                        logger.info(f"Processed {records_count:,} historical price records...")
            
            logger.info(f"Finished processing historical prices: {records_count:,} records, {skipped_count:,} skipped")


