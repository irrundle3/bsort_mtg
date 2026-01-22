"""
Object-oriented cache for managing normalized lookup tables for price_info.
"""
import logging
from typing import Dict
from .db_utils import CardDBClient

logger = logging.getLogger(__name__)


class LookupTableCache:
    """
    Object-oriented cache for lookup tables (source and currency IDs).
    Encapsulates the cache and provides methods to access it.
    """
    
    def __init__(self, client: CardDBClient):
        """
        Initialize the lookup table cache.
        
        Args:
            client: CardDBClient instance to use for database operations
        """
        self.client = client
        self._source_cache: Dict[str, int] = {}
        self._currency_cache: Dict[str, int] = {}
        self._loaded = False
    
    async def load(self) -> None:
        """
        Load the cache from the database.
        This should be called after initialization to populate the cache.
        """
        sources = await self.client.execute_query("SELECT id, name FROM price_source")
        currencies = await self.client.execute_query("SELECT id, code FROM currency")
        
        self._source_cache = {row['name']: row['id'] for row in sources}
        self._currency_cache = {row['code']: row['id'] for row in currencies}
        self._loaded = True
        logger.debug(f"Loaded lookup cache: {len(self._source_cache)} sources, {len(self._currency_cache)} currencies")
    
    async def get_or_create_source_id(self, source_name: str) -> int:
        """
        Get or create a source ID for the given source name.
        Uses the internal cache to avoid repeated database queries.
        Reloads the cache if a new source is created.
        
        Args:
            source_name: Name of the price source
            
        Returns:
            The source_id
        """
        if source_name in self._source_cache:
            return self._source_cache[source_name]
        
        # Not in cache, check database
        result = await self.client.execute_query(
            "SELECT id FROM price_source WHERE name = $1",
            (source_name,)
        )
        
        if result:
            source_id = result[0]['id']
            # Update cache
            self._source_cache[source_name] = source_id
        else:
            # Create new source
            result = await self.client.execute_query(
                "INSERT INTO price_source (name) VALUES ($1) RETURNING id",
                (source_name,)
            )
            source_id = result[0]['id']
            # Reload cache to ensure consistency
            await self.load()
        
        return source_id
    
    async def get_or_create_currency_id(self, currency_code: str) -> int:
        """
        Get or create a currency ID for the given currency code.
        Uses the internal cache to avoid repeated database queries.
        Reloads the cache if a new currency is created.
        
        Args:
            currency_code: Currency code (e.g., 'USD', 'EUR')
            
        Returns:
            The currency_id
        """
        if currency_code in self._currency_cache:
            return self._currency_cache[currency_code]
        
        # Not in cache, check database
        result = await self.client.execute_query(
            "SELECT id FROM currency WHERE code = $1",
            (currency_code,)
        )
        
        if result:
            currency_id = result[0]['id']
            # Update cache
            self._currency_cache[currency_code] = currency_id
        else:
            # Create new currency
            result = await self.client.execute_query(
                "INSERT INTO currency (code) VALUES ($1) RETURNING id",
                (currency_code,)
            )
            currency_id = result[0]['id']
            # Reload cache to ensure consistency
            await self.load()
        
        return currency_id
    
    @property
    def source_cache(self) -> Dict[str, int]:
        """Get the source cache dictionary."""
        return self._source_cache
    
    @property
    def currency_cache(self) -> Dict[str, int]:
        """Get the currency cache dictionary."""
        return self._currency_cache

