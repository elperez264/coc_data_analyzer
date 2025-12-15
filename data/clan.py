from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import re


CAPITAL_LEAGUE_TRANSLATIONS: Dict[str, str] = {
    "Gold": "Oro",
    "Silver": "Plata",
    "Bronze": "Bronce",
}

def _extract_badge_url(badge: Any) -> Optional[str]:
    if badge is None:
        return None
    if isinstance(badge, str):
        return badge
    url = getattr(badge, "url", None)
    if url:
        return str(url)
    if isinstance(badge, dict):
        return badge.get("url")
    return None

def _translate_capital_league(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    translated = value
    for src, dst in CAPITAL_LEAGUE_TRANSLATIONS.items():
        translated = re.sub(rf"\b{re.escape(src)}\b", dst, translated)
    return translated


@dataclass
class Clan:
    tag: str
    badge_url: Optional[str] = field(default=None)
    level: Optional[int] = field(default=None)
    capital_points: Optional[int] = field(default=None)
    description: Optional[str] = field(default=None)
    streak: Optional[int] = field(default=None)
    country: Optional[str] = field(default=None)
    total_trophies: Optional[int] = field(default=None)
    wins: Optional[int] = field(default=None)
    losses: Optional[int] = field(default=None)
    wins_percent: Optional[int] = field(default=None)
    members_count: Optional[int] = field(default=None)
    capital_league: Optional[str] = field(default=None)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Clan":
        return cls(
            badge_url=_extract_badge_url(data.get("badge")),
            level=data.get("level"),
            capital_points=data.get("capital_points"),
            description=data.get("description"),
            streak=data.get("streak"),
            country=data.get("country"),
            total_trophies=data.get("total_trophies"),
            wins=data.get("wins"),
            losses=data.get("losses"),
            wins_percent=data.get("wins_percent"),
            members_count=data.get("members_count"),
            capital_league=_translate_capital_league(data.get("capital_league")),
            tag=data.get("tag", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "badge_url": self.badge_url,
            "level": self.level,
            "capital_points": self.capital_points,
            "description": self.description,
            "streak": self.streak,
            "country": self.country,
            "total_trophies": self.total_trophies,
            "wins": self.wins,
            "losses": self.losses,
            "wins_percent": self.wins_percent,
            "members_count": self.members_count,
            "capital_league": self.capital_league,
            "tag": self.tag
        }