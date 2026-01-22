from typing import Generic, TypeVar, Type, Collection, List, Iterator, Optional
from dataclasses import fields, is_dataclass, asdict
import asyncpg
from .const import DB_PORT, DB_NAME, DB_USER, DB_HOST
from .lookup_tables import LookupTableCache
from mtg_json.loader import MTGJsonLoader
from common import PriceInfo, PriceInfoRaw
import os
import logging
import json

logger = logging.getLogger(__name__)

RowType = TypeVar("RowType")

class DBSpecialist(Generic[RowType]):
    """
    Wraps a CardDBClient, allowing the user to deal with only dataclass types.
    """
    def __init__(self, client: "CardDBClient", table_name: str, row_type: Type[RowType], debug: bool = False):
        if not is_dataclass(row_type):
            raise ValueError(f"row_type must be a dataclass, got {row_type}")
        self.client = client
        self.table_name = table_name
        self.row_type = row_type
        # Get field names from dataclass
        self.field_names = [f.name for f in fields(row_type)]

    async def write_item(self, item: RowType, exclude_fields: Collection[str] = [], conflict_column: str | list[str] | None = None) -> RowType:
        """
        Insert or update (upsert) the item into the associated table. Item is a dataclass.
        """
        if not self.client or not self.client._conn:
            raise RuntimeError("DBWriter client not set with connection.")
        # Convert dataclass to dict
        item_dict = asdict(item)
        for field in exclude_fields:
            if field in item:
                del item[field]
            else:
                logger.warning(f"Field {field} not present in row type {RowType.__name__}")
        field_names = [name for name in self.field_names if name not in exclude_fields]
        await self.client.upsert_rows(self.table_name, field_names, [item_dict], conflict_column=conflict_column)
        return item

    async def write_items(self, items: List[RowType], exclude_fields: Collection[str] = [], conflict_column: str | list[str] | None = None) -> List[RowType]:
        """
        Insert or update (upsert) multiple items into the associated table.
        """
        if not self.client or not self.client._conn:
            raise RuntimeError("DBWriter client not set with connection.")
        if not items:
            return []
        # Convert dataclasses to dicts
        items_dict = [asdict(item) for item in items]
        for item in items_dict:
            for field in exclude_fields:
                if field in item:
                    del item[field]
                else:
                    logger.warning(f"Field {field} not present in row type {RowType.__name__}")
        field_names = [name for name in self.field_names if name not in exclude_fields]
        await self.client.upsert_rows(self.table_name, field_names, items_dict, conflict_column=conflict_column)
        return items

    async def read_items(self, where_clause: str = "", params: tuple = ()) -> List[RowType]:
        """
        Read items from the associated table. Optionally filter with where_clause and params.
        """
        if not self.client or not self.client._conn:
            raise RuntimeError("DBWriter client not set with connection.")
        query = f"SELECT * FROM {self.table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        result = await self.client.execute_query(query, params)
        # Convert dict rows to dataclass instances
        return [self.row_type(**row) for row in result]

class CardDBClient:
    def __init__(self):
        self._conn: asyncpg.Connection | None = None
        self._lookup_cache: LookupTableCache | None = None

    async def __aenter__(self) -> "CardDBClient":
        await self.connect_to_db()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.disconnect_from_db()

    async def connect_to_db(self) -> asyncpg.Connection:
        if self._conn is not None:
            return self._conn
        self._conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=os.getenv("DB_PASSWORD")
            if os.getenv("DB_PASSWORD")
            else "postgres",
        )
        # Initialize and load lookup cache when connecting
        if self._lookup_cache is None:
            self._lookup_cache = LookupTableCache(self)
            await self._lookup_cache.load()
        return self._conn

    async def disconnect_from_db(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
        self._lookup_cache = None

    async def execute_query(self, query: str, params: tuple = ()) -> list[dict]:
        # asyncpg uses $1, $2, etc. for parameters
        # Convert %s placeholders to $1, $2, etc.
        if params:
            # Replace each %s with $1, $2, etc. in order
            param_num = 1
            converted_query = ""
            i = 0
            while i < len(query):
                if query[i : i + 2] == "%s":
                    converted_query += f"${param_num}"
                    param_num += 1
                    i += 2
                else:
                    converted_query += query[i]
                    i += 1
            result = await self._conn.fetch(converted_query, *params)
        else:
            result = await self._conn.fetch(query)
        # Convert asyncpg Record objects to dicts
        return [dict(row) for row in result]

    async def upsert_rows(
        self,
        table: str,
        columns: list[str],
        rows: list[dict],
        conflict_column: str | None = None,
        batch_size: int = 100,
    ) -> None:
        """
        Insert or update rows in the specified table using batch inserts for better performance.

        Args:
            table: Name of the table
            columns: List of column names in the order they appear in the rows
            rows: List of dictionaries, each containing column: value pairs
            conflict_column: Optional column name to use for ON CONFLICT clause (for upsert)
            batch_size: Number of rows to insert per batch (default: 1000)
        """
        if not rows:
            return

        # Calculate batch size to avoid exceeding asyncpg's parameter limit (32767)
        # Each row uses len(columns) parameters
        max_params_per_row = len(columns)
        safe_batch_size = max(1, min(batch_size, 32767 // max_params_per_row))
        if safe_batch_size < batch_size:
            logger.debug(f"Reduced batch size from {batch_size} to {safe_batch_size} to avoid parameter limit")

        # Quote column names to preserve case-sensitivity (e.g. camelCase)
        quoted_columns = [f'"{col}"' for col in columns]
        columns_str = ", ".join(quoted_columns)

        # Build ON CONFLICT clause if conflict_column is provided
        conflict_clause = ""
        if conflict_column:
            # Handle both single column and composite keys
            if isinstance(conflict_column, str):
                conflict_columns = [conflict_column]
            else:
                conflict_columns = conflict_column
            
            quoted_conflicts = [f'"{col}"' for col in conflict_columns]
            quoted_conflict_str = ", ".join(quoted_conflicts)
            quoted_update_assignments = [
                f'"{col}" = EXCLUDED."{col}"' for col in columns if col not in conflict_columns
            ]
            conflict_clause = (
                f" ON CONFLICT ({quoted_conflict_str}) DO UPDATE SET "
                + ", ".join(quoted_update_assignments)
            )
        else:
            conflict_clause = " ON CONFLICT DO NOTHING"

        logger.debug("got here")

        # Get JSONB columns for this table
        jsonb_columns = await self._get_jsonb_columns(table)

        # Process rows in batches
        for i in range(0, len(rows), safe_batch_size):
            batch = rows[i : i + safe_batch_size]

            # Build VALUES clause with multiple rows using asyncpg's $1, $2, etc. syntax
            placeholders_list = []
            values_list = []
            param_counter = 1

            for row in batch:
                row_placeholders = []
                for col in columns:
                    row_placeholders.append(f"${param_counter}")
                    value = row.get(col)
                    # Convert dict/list to JSON string for JSONB columns only
                    if col in jsonb_columns and (isinstance(value, dict) or isinstance(value, list)):
                        value = json.dumps(value)
                    values_list.append(value)
                    param_counter += 1
                placeholders_list.append("(" + ", ".join(row_placeholders) + ")")

            # Build the batch INSERT query
            values_clause = ", ".join(placeholders_list)
            query = f"INSERT INTO {table} ({columns_str}) VALUES {values_clause}{conflict_clause}"

            # Execute the batch insert
            await self._conn.execute(query, *values_list)

    async def _get_jsonb_columns(self, table: str) -> set[str]:
        """
        Query the database to get all JSONB column names for a given table.
        """
        try:
            # Remove quotes from table name if present, and convert to lowercase
            # PostgreSQL stores table names in lowercase in information_schema
            table_name_lower = table.strip('"').lower()
            # Query using pg_catalog for more reliable results
            query = """
                SELECT attname as column_name
                FROM pg_attribute
                WHERE attrelid = (
                    SELECT oid 
                    FROM pg_class 
                    WHERE relname = $1
                )
                AND atttypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'jsonb'
                )
                AND attnum > 0
                AND NOT attisdropped
            """
            result = await self.execute_query(query, (table_name_lower,))
            jsonb_cols = {row['column_name'] for row in result}
            logger.debug(f"Found JSONB columns for table {table}: {jsonb_cols}")
            return jsonb_cols
        except Exception as e:
            logger.warning(f"Failed to query JSONB columns for table {table}: {e}. Will not auto-convert.")
            # Return empty set - we'll only convert if we know the column is JSONB
            return set()
    
    async def reload_lookup_cache(self) -> None:
        """
        Reload the lookup table cache from the database.
        This should be called if there's a chance that lookup tables have changed.
        """
        if self._lookup_cache is not None:
            await self._lookup_cache.load()
    
    @property
    def lookup_cache(self) -> LookupTableCache:
        """
        Get the lookup table cache.
        Raises RuntimeError if the client is not connected.
        """
        if self._lookup_cache is None:
            raise RuntimeError("Lookup cache not initialized. Connect to database first.")
        return self._lookup_cache
    
    async def load_historical_price_records(
        self, 
        existing_card_ids: Optional[set[str]] = None,
        mtgjson_dir: Optional[str] = None
    ) -> Iterator[PriceInfo]:
        """
        Load historical prices from AllPrices.json and yield PriceInfo records.
        This uses a generator to handle the large file (1.5GB) without loading it all into memory.
        The records are automatically normalized using the lookup cache.
        
        Args:
            existing_card_ids: Optional set of card IDs to filter by. If None, includes all cards.
            mtgjson_dir: Optional directory containing MTGJSON data files. If None, uses default.
        
        Yields:
            PriceInfo records (normalized with source_id and currency_id) one at a time
        """
        if self._lookup_cache is None:
            raise RuntimeError("Lookup cache not initialized. Connect to database first.")
        
        loader = MTGJsonLoader(mtgjson_dir=mtgjson_dir)
        
        for raw_record in loader.load_historical_price_records(existing_card_ids):
            # Normalize the record using the lookup cache
            source_id = await self._lookup_cache.get_or_create_source_id(raw_record.source_name)
            currency_id = await self._lookup_cache.get_or_create_currency_id(raw_record.currency)
            
            yield PriceInfo(
                card_id=raw_record.card_id,
                source_id=source_id,
                currency_id=currency_id,
                price_type=raw_record.price_type,
                finish_type=raw_record.finish_type,
                date_priced=raw_record.date_priced,
                price=raw_record.price
            )