from data.player import Player
from typing import List
import pandas as pd

class DataFrameOperations:

    @staticmethod
    def add_medals_and_days_to_players_df(players_df: pd.DataFrame, players: List[Player]) -> pd.DataFrame:
        """
        Añade tres columnas al DataFrame copia:
        - 'Medallas': número de medallas positivas.
        - 'Agravios': número de medallas negativas.
        - 'membership_days': días acumulados en el clan (float).

        Empareja usando player.username con la columna `Nombre` del DataFrame (case-insensitive).
        No modifica el DataFrame original; devuelve una copia y establece `self.membership_days`
        como una pandas.Series alineada con el DataFrame devuelto.
        """
        if not isinstance(players_df, pd.DataFrame):
            raise TypeError("players_df debe ser un pandas.DataFrame")

        # localizar la columna que representa el nombre de usuario (Nombre, case-insensitive)
        name_col = None
        for col in players_df.columns:
            if str(col).strip().lower() == "nombre":
                name_col = col
                break
        if name_col is None:
            raise ValueError("No se encontró la columna `Nombre` en el DataFrame")

        # mapa username -> (positivas, negativas) y username -> membership_days
        counts_map = {}
        days_map = {}
        for p in players:
            username = getattr(p, "username", None)
            # Medallas (se intenta usar métodos proporcionados por Player, fallback a 0)
            try:
                pos = len(p.get_positive_medals()) if getattr(p, "get_positive_medals", None) else 0
            except Exception:
                pos = 0
            try:
                neg = len(p.get_negative_medals()) if getattr(p, "get_negative_medals", None) else 0
            except Exception:
                neg = 0
            counts_map[username] = (pos, neg)

            # Días de membresía (atributo o callable); normalizar a float
            days_val = getattr(p, "membership_days", None)
            if callable(days_val):
                try:
                    days_val = days_val()
                except Exception:
                    days_val = None
            try:
                days_f = float(days_val) if days_val is not None else 0.0
            except Exception:
                days_f = 0.0
            days_map[username] = days_f

        df = players_df.copy()

        # funciones para obtener los conteos para una fila (manejan NaN)
        def get_positive(u):
            if pd.isna(u):
                return 0
            return counts_map.get(u, (0, 0))[0]

        def get_negative(u):
            if pd.isna(u):
                return 0
            return counts_map.get(u, (0, 0))[1]

        def get_days(u):
            if pd.isna(u):
                return 0.0
            return days_map.get(u, 0.0)

        df["Medallas"] = df[name_col].apply(get_positive)
        df["Agravios"] = df[name_col].apply(get_negative)

        # columna de días y guardar en self.membership_days (Serie alineada con el DataFrame)
        membership_series = df[name_col].apply(get_days).astype(float)
        df["Días en el clan"] = membership_series

        return df




