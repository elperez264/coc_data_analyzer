# python
from enum import Enum

class Rank(Enum):
    LEADER = "lider"
    CO_LEADER = "colider"
    VETERAN = "veterano"
    MEMBER = "miembro"

    def __str__(self) -> str:
        return self.value
