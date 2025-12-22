import json
import os
import time
import requests
import gzip
import logging
from datetime import date
from typing import List, Dict
from common import SetInfo, CardInfo, PriceFormats, PriceInfo

logger = logging.getLogger(__name__)

CardId = str

class MTGJsonLoader:
    API_TEMPLATE = "https://mtgjson.com/api/v5/{}.json.gz"

    def __init__(self, mtgjson_dir = None):
        self.mtgjson_dir = os.path.join(os.path.dirname(__file__), "../data") if mtgjson_dir is None else mtgjson_dir

    def download_mtg_json(self, src_name: str, dst_name: str | None = None) -> dict:
        response = requests.get(self.API_TEMPLATE.format(src_name))
        decompressed_content = gzip.decompress(response.content)
        file_path = os.path.join(self.mtgjson_dir, dst_name if dst_name else "{}.json".format(src_name))
        with open(file_path, "wb") as f:
            f.write(decompressed_content)
        with open(file_path, "r") as f:
            return json.load(f)

    def load_mtg_json(self, src_name: str) -> dict:
        path = os.path.join(self.mtgjson_dir, "{}.json".format(src_name))
        if not os.path.exists(path):
            return self.download_mtg_json(src_name)
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
    
    def load_price_records(self) -> List[PriceInfo]:
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
                                        from datetime import datetime
                                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                                    except:
                                        logger.warning(f"Could not parse date: {date_str}, skipping")
                                        continue
                                
                                records.append(PriceInfo(
                                    card_id=card_id,
                                    source_name=full_source_name,
                                    currency=currency,
                                    price_type=price_type,
                                    finish_type=finish_type,
                                    date_priced=date_obj,
                                    price=price_value
                                ))
        
        return records


