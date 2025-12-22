from dataclasses import field
from pydantic.dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import date

DateStr = str
SourceName = str

@dataclass
class CardInfo:
    # Optional fields
    artist: Optional[str] = None
    artistIds: Optional[List[str]] = None
    asciiName: Optional[str] = None
    attractionLights: Optional[List[int]] = None
    boosterTypes: Optional[List[str]] = None
    cardParts: Optional[List[str]] = None
    colorIndicator: Optional[List[str]] = None
    defense: Optional[str] = None
    duelDeck: Optional[str] = None
    edhrecRank: Optional[int] = None
    edhrecSaltiness: Optional[float] = None
    faceConvertedManaCost: Optional[float] = None
    faceFlavorName: Optional[str] = None
    faceManaValue: Optional[float] = None
    faceName: Optional[str] = None
    flavorName: Optional[str] = None
    flavorText: Optional[str] = None
    foreignData: Optional[List[Dict[str, Any]]] = None
    frameEffects: Optional[List[str]] = None
    hand: Optional[str] = None
    hasAlternativeDeckLimit: Optional[bool] = None
    hasContentWarning: Optional[bool] = None
    isAlternative: Optional[bool] = None
    isFullArt: Optional[bool] = None
    isFunny: Optional[bool] = None
    isGameChanger: Optional[bool] = None
    isOnlineOnly: Optional[bool] = None
    isOversized: Optional[bool] = None
    isPromo: Optional[bool] = None
    isRebalanced: Optional[bool] = None
    isReprint: Optional[bool] = None
    isReserved: Optional[bool] = None
    isStarter: Optional[bool] = None
    isStorySpotlight: Optional[bool] = None
    isTextless: Optional[bool] = None
    isTimeshifted: Optional[bool] = None
    keywords: Optional[List[str]] = None
    leadershipSkills: Optional[Dict[str, Any]] = None
    life: Optional[str] = None
    loyalty: Optional[str] = None
    manaCost: Optional[str] = None
    originalPrintings: Optional[List[str]] = None
    originalReleaseDate: Optional[str] = None
    originalText: Optional[str] = None
    originalType: Optional[str] = None
    otherFaceIds: Optional[List[str]] = None
    power: Optional[str] = None
    printings: Optional[List[str]] = None
    promoTypes: Optional[List[str]] = None
    relatedCards: Optional[Dict[str, Any]] = None
    rebalancedPrintings: Optional[List[str]] = None
    rulings: Optional[List[Dict[str, Any]]] = None
    securityStamp: Optional[str] = None
    side: Optional[str] = None
    signature: Optional[str] = None
    sourceProducts: Optional[Dict[str, Any]] = None
    subsets: Optional[List[str]] = None
    text: Optional[str] = None
    toughness: Optional[str] = None
    variations: Optional[List[str]] = None
    watermark: Optional[str] = None
    
    # Required fields (no Optional, no default None)
    availability: List[str] = field(default_factory=list)
    borderColor: str = ""
    colorIdentity: List[str] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    convertedManaCost: float = 0.0
    finishes: List[str] = field(default_factory=list)
    frameVersion: str = ""
    hasFoil: bool = False
    hasNonFoil: bool = False
    identifiers: Dict[str, Any] = field(default_factory=dict)
    language: str = ""
    layout: str = ""
    legalities: Dict[str, Any] = field(default_factory=dict)
    manaValue: float = 0.0
    name: str = ""
    number: str = ""
    purchaseUrls: Dict[str, Any] = field(default_factory=dict)
    rarity: str = ""
    setCode: str = ""
    subtypes: List[str] = field(default_factory=list)
    supertypes: List[str] = field(default_factory=list)
    type: str = ""
    types: List[str] = field(default_factory=list)
    uuid: str = ""
    
@dataclass
class SetInfo:
    # Optional fields
    block: Optional[str] = None
    booster: Optional[Dict[str, Dict[str, Any]]] = None
    cardsphereSetId: Optional[int] = None
    codeV3: Optional[str] = None
    decks: Optional[List[Dict[str, Any]]] = None
    isForeignOnly: Optional[bool] = None
    isNonFoilOnly: Optional[bool] = None
    isPaperOnly: Optional[bool] = None
    isPartialPreview: Optional[bool] = None
    languages: Optional[List[str]] = None
    mcmId: Optional[int] = None
    mcmIdExtras: Optional[int] = None
    mcmName: Optional[str] = None
    mtgoCode: Optional[str] = None
    parentCode: Optional[str] = None
    sealedProduct: Optional[List[Dict[str, Any]]] = None
    tcgplayerGroupId: Optional[int] = None
    tokenSetCode: Optional[str] = None
    
    # Required fields
    baseSetSize: int = 0
    cards: List[CardInfo] = field(default_factory=list)
    code: str = ""
    isFoilOnly: bool = False
    isOnlineOnly: bool = False
    keyruneCode: str = ""
    name: str = ""
    releaseDate: str = ""
    tokens: List[Dict[str, Any]] = field(default_factory=list)
    totalSetSize: int = 0
    translations: Dict[str, Any] = field(default_factory=dict)
    type: str = ""

@dataclass
class PricePoints:
    # Optional fields
    etched: Optional[Dict[DateStr, float]] = None
    foil: Optional[Dict[DateStr, float]] = None
    normal: Optional[Dict[DateStr, float]] = None

@dataclass
class PriceList:
    # Optional fields
    buylist: Optional[PricePoints] = None
    retail: Optional[PricePoints] = None
    
    # Required fields
    currency: str = ""

@dataclass
class PriceFormats:
    # Optional fields
    mtgo: Optional[Dict[SourceName, PriceList]] = None
    paper: Optional[Dict[SourceName, PriceList]] = None

@dataclass
class PriceInfo:
    card_id: str
    source_name: str
    currency: str
    price_type: str  # 'buylist' or 'retail'
    finish_type: str  # 'etched', 'foil', or 'normal'
    date_priced: date  # Date object
    price: float

