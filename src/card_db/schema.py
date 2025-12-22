"""
Database schema creation for MTG card database.

Creates three tables: set_info, card_info, and price_info with proper
foreign keys, ENUMs, and minimized JSONB usage.
"""
import logging
from typing import Optional
from .db_utils import CardDBClient

logger = logging.getLogger(__name__)

# SQL statements for schema creation

CREATE_ENUMS = """
-- Create ENUM types for price_info table
DO $$ BEGIN
    CREATE TYPE price_type_enum AS ENUM ('buylist', 'retail');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE finish_type_enum AS ENUM ('etched', 'foil', 'normal');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
"""

CREATE_SET_INFO_TABLE = """
CREATE TABLE IF NOT EXISTS set_info (
    code TEXT PRIMARY KEY,
    block TEXT,
    cardsphereSetId INTEGER,
    codeV3 TEXT,
    isForeignOnly BOOLEAN,
    isNonFoilOnly BOOLEAN,
    isPaperOnly BOOLEAN,
    isPartialPreview BOOLEAN,
    languages TEXT[],
    mcmId INTEGER,
    mcmIdExtras INTEGER,
    mcmName TEXT,
    mtgoCode TEXT,
    parentCode TEXT,
    tcgplayerGroupId INTEGER,
    tokenSetCode TEXT,
    baseSetSize INTEGER NOT NULL DEFAULT 0,
    isFoilOnly BOOLEAN NOT NULL DEFAULT FALSE,
    isOnlineOnly BOOLEAN NOT NULL DEFAULT FALSE,
    keyruneCode TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    releaseDate TEXT NOT NULL DEFAULT '',
    totalSetSize INTEGER NOT NULL DEFAULT 0,
    type TEXT NOT NULL DEFAULT '',
    booster JSONB,
    translations JSONB,
    decks JSONB,
    sealedProduct JSONB,
    tokens JSONB
);
"""

CREATE_CARD_INFO_TABLE = """
CREATE TABLE IF NOT EXISTS card_info (
    uuid TEXT PRIMARY KEY,
    setCode TEXT NOT NULL REFERENCES set_info(code),
    artist TEXT,
    artistIds TEXT[],
    asciiName TEXT,
    attractionLights INTEGER[],
    boosterTypes TEXT[],
    cardParts TEXT[],
    colorIndicator TEXT[],
    defense TEXT,
    duelDeck TEXT,
    edhrecRank INTEGER,
    edhrecSaltiness NUMERIC,
    faceConvertedManaCost NUMERIC,
    faceFlavorName TEXT,
    faceManaValue NUMERIC,
    faceName TEXT,
    flavorName TEXT,
    flavorText TEXT,
    hand TEXT,
    hasAlternativeDeckLimit BOOLEAN,
    hasContentWarning BOOLEAN,
    isAlternative BOOLEAN,
    isFullArt BOOLEAN,
    isFunny BOOLEAN,
    isGameChanger BOOLEAN,
    isOnlineOnly BOOLEAN,
    isOversized BOOLEAN,
    isPromo BOOLEAN,
    isRebalanced BOOLEAN,
    isReprint BOOLEAN,
    isReserved BOOLEAN,
    isStarter BOOLEAN,
    isStorySpotlight BOOLEAN,
    isTextless BOOLEAN,
    isTimeshifted BOOLEAN,
    keywords TEXT[],
    life TEXT,
    loyalty TEXT,
    manaCost TEXT,
    originalPrintings TEXT[],
    originalReleaseDate TEXT,
    originalText TEXT,
    originalType TEXT,
    otherFaceIds TEXT[],
    power TEXT,
    printings TEXT[],
    promoTypes TEXT[],
    rebalancedPrintings TEXT[],
    securityStamp TEXT,
    side TEXT,
    signature TEXT,
    subsets TEXT[],
    text TEXT,
    toughness TEXT,
    variations TEXT[],
    watermark TEXT,
    availability TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    borderColor TEXT NOT NULL DEFAULT '',
    colorIdentity TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    colors TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    convertedManaCost NUMERIC NOT NULL DEFAULT 0.0,
    finishes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    frameVersion TEXT NOT NULL DEFAULT '',
    hasFoil BOOLEAN NOT NULL DEFAULT FALSE,
    hasNonFoil BOOLEAN NOT NULL DEFAULT FALSE,
    language TEXT NOT NULL DEFAULT '',
    layout TEXT NOT NULL DEFAULT '',
    manaValue NUMERIC NOT NULL DEFAULT 0.0,
    name TEXT NOT NULL DEFAULT '',
    number TEXT NOT NULL DEFAULT '',
    rarity TEXT NOT NULL DEFAULT '',
    subtypes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    supertypes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    type TEXT NOT NULL DEFAULT '',
    types TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    identifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
    legalities JSONB NOT NULL DEFAULT '{}'::jsonb,
    purchaseUrls JSONB NOT NULL DEFAULT '{}'::jsonb,
    leadershipSkills JSONB,
    relatedCards JSONB,
    rulings JSONB,
    foreignData JSONB,
    sourceProducts JSONB,
    frameEffects TEXT[]
);
"""

CREATE_PRICE_INFO_TABLE = """
CREATE TABLE IF NOT EXISTS price_info (
    card_id TEXT NOT NULL REFERENCES card_info(uuid),
    source_name TEXT NOT NULL,
    currency TEXT NOT NULL,
    price_type price_type_enum NOT NULL,
    finish_type finish_type_enum NOT NULL,
    date_priced DATE NOT NULL,
    price NUMERIC NOT NULL,
    PRIMARY KEY (card_id, source_name, price_type, finish_type, date_priced)
);
"""

CREATE_INDEXES = """
-- Indexes for set_info
CREATE INDEX IF NOT EXISTS idx_set_info_code ON set_info(code);

-- Indexes for card_info
CREATE INDEX IF NOT EXISTS idx_card_info_uuid ON card_info(uuid);
CREATE INDEX IF NOT EXISTS idx_card_info_set_code ON card_info(setCode);
CREATE INDEX IF NOT EXISTS idx_card_info_name ON card_info(name);

-- Indexes for price_info
CREATE INDEX IF NOT EXISTS idx_price_info_card_id ON price_info(card_id);
"""


async def create_schema(client: Optional[CardDBClient] = None, drop_existing: bool = False) -> None:
    """
    Create the database schema for MTG card database.
    
    Args:
        client: Optional CardDBClient instance. If None, creates a new one.
        drop_existing: If True, drops existing tables before creating new ones.
    
    Raises:
        RuntimeError: If schema creation fails.
    """
    async def _create_schema(conn_client: CardDBClient) -> None:
        try:
            # Drop tables if requested
            if drop_existing:
                logger.info("Dropping existing tables...")
                await conn_client._conn.execute("DROP TABLE IF EXISTS price_info CASCADE;")
                await conn_client._conn.execute("DROP TABLE IF EXISTS card_info CASCADE;")
                await conn_client._conn.execute("DROP TABLE IF EXISTS set_info CASCADE;")
                # Drop ENUMs (must be done after tables that use them)
                await conn_client._conn.execute("DROP TYPE IF EXISTS finish_type_enum CASCADE;")
                await conn_client._conn.execute("DROP TYPE IF EXISTS price_type_enum CASCADE;")
            
            # Create ENUMs
            logger.info("Creating ENUM types...")
            await conn_client._conn.execute(CREATE_ENUMS)
            
            # Create tables
            logger.info("Creating set_info table...")
            await conn_client._conn.execute(CREATE_SET_INFO_TABLE)
            
            logger.info("Creating card_info table...")
            await conn_client._conn.execute(CREATE_CARD_INFO_TABLE)
            
            logger.info("Creating price_info table...")
            await conn_client._conn.execute(CREATE_PRICE_INFO_TABLE)
            
            # Create indexes
            logger.info("Creating indexes...")
            await conn_client._conn.execute(CREATE_INDEXES)
            
            logger.info("Schema creation completed successfully!")
            
        except Exception as e:
            logger.error(f"Error creating schema: {e}")
            raise RuntimeError(f"Failed to create schema: {e}") from e
    
    if client is not None:
        await _create_schema(client)
    else:
        async with CardDBClient() as client:
            await _create_schema(client)

