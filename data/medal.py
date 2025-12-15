from dataclasses import dataclass

@dataclass
class Medal:
    description: str
    is_positive: bool

    def __str__(self):
        if self.is_positive:
            res = "Medalla por " +str(self.description)
        else:
            res = "Agravio por " +str(self.description)
        return res