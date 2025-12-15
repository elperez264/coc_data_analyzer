from dataclasses import dataclass, field
from data.medal import Medal
from data.rank import Rank
from typing import List, Optional, Union

@dataclass
class Player:
    _tag: str = field(init=False, repr=False)
    _username: str = field(init=False, repr=False)
    _rank: Rank = field(init=False, repr=True)
    medals: Optional[List[Medal]] = None
    membership_days: float = 0.0

    def __init__(self, tag: str, username: str, medals: Optional[List[Medal]] = None,
                 rank: Optional[Rank | None] = Rank.MEMBER, membership_days: float = 0.0) -> None:
        self.username = username
        self.tag = tag  # valida usando el setter
        self.medals = medals
        self.rank = rank  # usa el setter para validar
        self.membership_days = membership_days



    @property
    def rank(self) -> Rank:
        return self._rank

    @rank.setter
    def rank(self, value: Union[Rank, str]) -> None:
        if isinstance(value, Rank):
            self._rank = value
            return
        if not isinstance(value, str):
            raise ValueError("rank debe ser un Rank o una cadena")
        v = value.strip().lower()
        mapping = {
            "lider": Rank.LEADER,
            "líder": Rank.LEADER,
            "leader": Rank.LEADER,
            "colider": Rank.CO_LEADER,
            "colíder": Rank.CO_LEADER,
            "co-leader": Rank.CO_LEADER,
            "coleader": Rank.CO_LEADER,
            "co_leader": Rank.CO_LEADER,
            "veterano": Rank.VETERAN,
            "veteran": Rank.VETERAN,
            "miembro": Rank.MEMBER,
            "member": Rank.MEMBER,
        }
        if v not in mapping:
            raise ValueError(f"rank desconocido: {value!r}")
        self._rank = mapping[v]

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        self._username = value

    @property
    def tag(self) -> str:
        return self._tag

    @tag.setter
    def tag(self, value: str) -> None:
        if not value:
            raise ValueError("tag es obligatorio")
        if value[0] != '#':
            raise ValueError("tag debe comenzar con '#'")
        self._tag = value

    def get_positive_medals(self) -> List[Medal]:
        """
        Devuelve el número de medallas positivas.
        Acepta None o listas vacías.
        """
        positive_medals = [medal for medal in (self.medals or []) if bool(getattr(medal, "is_positive", False))]
        return positive_medals

    def get_negative_medals(self) -> List[Medal]:
        """
        Devuelve el número de medallas negativas.
        Acepta None o listas vacías.
        """
        positive_medals = [medal for medal in (self.medals or []) if not bool(getattr(medal, "is_positive", False))]
        return positive_medals

    def __str__(self):
        return f"Player(tag={self.tag}, username={self.username}, rank={self.rank.name})"


    @staticmethod
    def populate_from_dicts(players: List['Player'], info_list: List[dict]) -> None:
        """
        Completa los objetos Player a partir de una lista de diccionarios.
        - Coincide `Nombre` (ignorando mayúsculas/espacios) con player.username.
        - Usa los setters para `tag` y `rank`; para el resto crea atributos dinámicos.
        """
        if not players or not info_list:
            return

        lookup = { (p.username or "").strip().lower(): p for p in players }

        def _set_safe(obj, attr, value):
            if value is None:
                return
            try:
                if attr == "tag":
                    obj.tag = value
                elif attr == "rank":
                    obj.rank = value
                else:
                    setattr(obj, attr, value)
            except Exception:
                # ignorar valores inválidos para no romper el flujo
                pass

        for info in info_list:
            nombre = info.get("Nombre") or info.get("name")
            if not nombre:
                continue
            key = str(nombre).strip().lower()
            player = lookup.get(key)
            if not player:
                continue

            mapping = {
                "rank": info.get("Rol"),
                # "league": info.get("Liga"),
                # "league_icon": info.get("liga_icono"),
                # "trophies": info.get("Trofeos"),
                # "townhall": info.get("Ayuntamiento"),
                # "total_stars": info.get("Total de estrellas"),
                # "capital_points": info.get("Puntos de la capital"),
                # "rank_position": info.get("Rango"),
                # "donations": info.get("Donaciones"),
                # "received": info.get("Recibidos"),
                # "wants_war": info.get("Quiere guerra"),
            }

            for attr, val in mapping.items():
                _set_safe(player, attr, val)
