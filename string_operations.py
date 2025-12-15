from typing import List



class StringOperations:

    @staticmethod
    def normalize(s: str) -> str:
        import unicodedata
        import re

        if s is None:
            return ""
        s = str(s)
        s = unicodedata.normalize("NFD", s)
        # eliminar marcas de combinación (acentos)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
        s = s.lower()
        # eliminar caracteres que no sean letras/dígitos/espacios (incluye emojis y puntuación)
        s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
        # reemplazar guiones bajos y colapsar espacios
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def find_name_in_sublists(name: str, names_list: List[str]) -> int:
        """
        Busca `name` (normalizado) en cada sublista y devuelve el índice de la sublista
        donde se encuentra la primera coincidencia. Devuelve -1 si no se encuentra.
        """
        target = StringOperations.normalize(name)
        for idx, name_to_compare in enumerate(names_list):
            # print(f"Comparing '{StringOperations.normalize(item)}' with '{target}'")
            if StringOperations.normalize(name_to_compare) == target:
                return idx
        return -1