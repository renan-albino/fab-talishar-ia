from typing import Any, List, Dict, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import math

def clean_int_value(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return default
        return int(v)
    if isinstance(v, str):
        cleaned = v.strip().lower()
        if not cleaned or cleaned in ("none", "null", "nan", "inf", "-inf", "undefined"):
            return default
        try:
            return int(cleaned)
        except ValueError:
            try:
                f = float(cleaned)
                if math.isnan(f) or math.isinf(f):
                    return default
                return int(f)
            except (ValueError, OverflowError):
                return default
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default

def clean_list_value(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, (tuple, set)):
        return list(v)
    if isinstance(v, (str, bytes, bytearray, dict, int, float, bool)):
        return []
    try:
        return list(v)
    except (TypeError, ValueError):
        return []

def clean_dict_value(v: Any) -> Dict[str, Any]:
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    return {}

def clean_str_value(v: Any, default: str = "") -> str:
    if v is None:
        return default
    if isinstance(v, str):
        return v
    try:
        return str(v)
    except Exception:
        return default

class Card(BaseModel):
    cardID: Optional[str] = None
    cardNumber: Optional[str] = None
    name: Optional[str] = None
    pitch: int = 0
    cost: int = 0
    power: int = 0
    defense: int = 0
    type: str = ""
    
    @field_validator("pitch", "cost", "power", "defense", mode="before")
    @classmethod
    def clean_ints(cls, v):
        return clean_int_value(v)
        
    @field_validator("cardID", "cardNumber", "name", "type", mode="before")
    @classmethod
    def clean_strs(cls, v):
        return clean_str_value(v)
        
    model_config = {"extra": "allow"}

class Player(BaseModel):
    health: int = 0
    pitch: int = 0
    
    @field_validator("health", "pitch", mode="before")
    @classmethod
    def clean_ints(cls, v):
        return clean_int_value(v)
        
    model_config = {"extra": "allow"}

class GameState(BaseModel):
    playerHealth: int = 0
    opponentHealth: int = 0
    turnNo: int = 1
    currentTurn: int = 1
    gameStatus: int = 0
    turnPlayer: int = 1
    
    havePriority: bool = False
    
    turnPhase: Any = ""
    
    opponentHand: List[Any] = Field(default_factory=list)
    opponentHandCount: int = 0
    
    playerArsenal: List[Any] = Field(default_factory=list)
    playerArse: List[Any] = Field(default_factory=list)
    
    theirArsenal: List[Any] = Field(default_factory=list)
    theirArse: List[Any] = Field(default_factory=list)
    opponentArsenal: List[Any] = Field(default_factory=list)
    
    theirItems: List[Any] = Field(default_factory=list)
    opponentItems: List[Any] = Field(default_factory=list)
    
    theirAuras: List[Any] = Field(default_factory=list)
    opponentAuras: List[Any] = Field(default_factory=list)
    
    theirPermanents: List[Any] = Field(default_factory=list)
    opponentPermanents: List[Any] = Field(default_factory=list)
    
    theirEquipment: List[Any] = Field(default_factory=list)
    opponentEquipment: List[Any] = Field(default_factory=list)
    
    theirAllies: List[Any] = Field(default_factory=list)
    opponentAllies: List[Any] = Field(default_factory=list)
    
    activeChainLink: Dict[str, Any] = Field(default_factory=dict)
    popup: Dict[str, Any] = Field(default_factory=dict)
    playerPrompt: Dict[str, Any] = Field(default_factory=dict)
    
    promptButtons: List[Any] = Field(default_factory=list)
    buttons: List[Any] = Field(default_factory=list)

    @field_validator("playerHealth", "opponentHealth", "turnNo", "currentTurn", "gameStatus", "turnPlayer", "opponentHandCount", mode="before")
    @classmethod
    def clean_ints(cls, v):
        return clean_int_value(v)

    @field_validator("opponentHand", "playerArsenal", "playerArse", "theirArsenal", "theirArse", "opponentArsenal",
                     "theirItems", "opponentItems", "theirAuras", "opponentAuras", "theirPermanents", "opponentPermanents",
                     "theirEquipment", "opponentEquipment", "theirAllies", "opponentAllies", "promptButtons", "buttons", mode="before")
    @classmethod
    def clean_lists(cls, v):
        return clean_list_value(v)

    @field_validator("activeChainLink", "popup", "playerPrompt", mode="before")
    @classmethod
    def clean_dicts(cls, v):
        return clean_dict_value(v)

    model_config = {"extra": "allow"}
