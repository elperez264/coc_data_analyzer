import sqlite3
from datetime import datetime
from typing import Optional, Union
import pandas as pd


class SQLiteAdapter:
    def __init__(self, db_name: str):
        self.__db_name = db_name
        self.__create_tables()



    def get_all_players(self) -> pd.DataFrame:
        """
        Devuelve pandas.DataFrame con todas las filas de la tabla `players`.
        Columnas: 'player_tag', 'username' (en ese orden).
        Lanza ImportError si pandas no está instalado.
        """

        conn = sqlite3.connect(self.__db_name)
        try:
            # seleccionamos únicamente las columnas requeridas y ordenamos por username (ignorando mayúsculas)
            query = """
                SELECT player_tag, username
                FROM players
                ORDER BY username COLLATE NOCASE
            """
            df = pd.read_sql_query(query, conn)
            # asegurarnos del orden/tuplas de columnas esperado
            df = df.loc[:, ["player_tag", "username"]]
            return df
        finally:
            conn.close()

    def add_or_update_player(self, username: str, player_tag: str) -> int:
        """
        Inserta o actualiza un jugador. Primero intenta UPDATE; si no hay filas
        afectadas, realiza un INSERT. Retorna el rowid del registro.
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")

        conn = sqlite3.connect(self.__db_name)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys = ON")

            # Intentar actualizar
            cur.execute(
                "UPDATE players SET username = ? WHERE player_tag = ?",
                (username, player_tag)
            )

            if cur.rowcount == 0:
                # No existía: insertar
                cur.execute(
                    "INSERT INTO players (player_tag, username) VALUES (?, ?)",
                    (player_tag, username)
                )
                rowid = cur.lastrowid
            else:
                # Existía: obtener su rowid
                cur.execute("SELECT rowid FROM players WHERE player_tag = ? LIMIT 1", (player_tag,))
                rowid = cur.fetchone()[0]

            conn.commit()
            return rowid
        finally:
            conn.close()

    def add_donation(self,
                     player_tag: str,
                     donated: int = 0,
                     received: int = 0,
                     date: Optional[Union[str, datetime]] = None,
                     check_player_exists: bool = True) -> int:
        """
        Inserta una nueva entrada en la tabla `donations`.

        Parámetros:
        - player_tag (str): tag del jugador (debe existir en players si check_player_exists=True).
        - donated (int): cantidad donada por el jugador en esta entrada (>= 0).
        - received (int): cantidad recibida por el jugador en esta entrada (>= 0).
        - date (str|datetime|None): fecha de la entrada. Si es None se usa la hora actual del sistema.
            Si es str se espera formato 'YYYY-MM-DD HH:MM:SS' o ISO compatible.
        - check_player_exists (bool): si True comprueba que player_tag exista en players y lanza ValueError si no.

        Retorna:
        - int: rowid de la fila insertada (id autoincrement).
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")

        # Validaciones simples para cantidades
        try:
            donated = int(donated)
            received = int(received)
        except (TypeError, ValueError):
            raise ValueError("donated y received deben ser enteros")

        if donated < 0 or received < 0:
            raise ValueError("donated y received deben ser >= 0")

        # Normalizar fecha
        if date is None:
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(date, datetime):
            date_str = date.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(date, str):
            date_str = date
        else:
            raise ValueError("date debe ser None, str o datetime")

        conn = sqlite3.connect(self.__db_name)
        cur = conn.cursor()
        try:
            # Activar comprobación de foreign keys (por si la tabla tiene FK)
            cur.execute("PRAGMA foreign_keys = ON")

            # Comprobar existencia del jugador si se solicitó
            if check_player_exists:
                cur.execute("SELECT 1 FROM players WHERE player_tag = ? LIMIT 1", (player_tag,))
                if cur.fetchone() is None:
                    raise ValueError(f"player_tag '{player_tag}' no existe en la tabla players. "
                                     "Inserta el jugador antes o usa check_player_exists=False.")

            # Insertar la fila
            cur.execute(
                """
                INSERT INTO donations (player_tag, donated, received, date)
                VALUES (?, ?, ?, ?)
                """,
                (player_tag, donated, received, date_str)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


    def add_medal(self, player_tag: str, description: str, is_positive: bool = True,
                  check_player_exists: bool = True) -> int:
        """
        Inserta una entrada en la tabla `medals`.

        Parámetros:
        - player_tag (str): tag del jugador (ej. "#ABC123").
        - description (str): descripción de la medalla (no vacío).
        - is_positive (bool|int|str): indica si la medalla es positiva.
            Por defecto True (positiva).
        - check_player_exists (bool): si True comprueba que player_tag exista en players.

        Retorna:
        - int: rowid de la fila insertada.

        Lanza:
        - ValueError si los parámetros son inválidos o si check_player_exists=True y el jugador no existe.
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")
        if not description or not description.strip():
            raise ValueError("description es obligatoria y no puede estar vacía")

        is_pos_int = 1 if is_positive else 0

        desc = description.strip()

        conn = sqlite3.connect(self.__db_name)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys = ON")

            if check_player_exists:
                cur.execute("SELECT 1 FROM players WHERE player_tag = ? LIMIT 1", (player_tag,))
                if cur.fetchone() is None:
                    raise ValueError(f"player_tag '{player_tag}' no existe en la tabla players. "
                                     "Inserta el jugador antes o usa check_player_exists=False.")

            cur.execute(
                """
                INSERT INTO medals (player_tag, description, is_positive)
                VALUES (?, ?, ?)
                """,
                (player_tag, desc, is_pos_int)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


    def get_medals_by_player(self, player_tag: str) -> pd.DataFrame:
        """
        Devuelve un pandas.DataFrame con todas las medallas del jugador indicado.
        Columnas: 'id', 'player_tag', 'description', 'is_positive' (bool), ordenadas por id DESC.
        Lanza ValueError si player_tag está vacío.
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")

        conn = sqlite3.connect(self.__db_name)
        try:
            query = """
                SELECT id, player_tag, description, is_positive
                FROM medals
                WHERE player_tag = ?
                ORDER BY id DESC
            """
            df = pd.read_sql_query(query, conn, params=[player_tag])
            # Asegurar orden de columnas esperado incluso si no hay filas
            for col in ["id", "player_tag", "description", "is_positive"]:
                if col not in df.columns:
                    df[col] = pd.Series(dtype="object")
            # Normalizar is_positive a booleano (0/1 -> False/True)
            df["is_positive"] = df["is_positive"].astype(bool)
            return df.loc[:, ["id", "player_tag", "description", "is_positive"]]
        finally:
            conn.close()

    @staticmethod
    def _parse_date_to_str(date: Optional[Union[str, datetime]]) -> str:
        """Helper: convierte None/str/datetime a 'YYYY-MM-DD HH:MM:SS'."""
        if date is None:
            dt = datetime.now()
        elif isinstance(date, datetime):
            dt = date
        elif isinstance(date, str):
            try:
                dt = datetime.fromisoformat(date)
            except ValueError:
                try:
                    dt = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    raise ValueError("Formato de fecha no reconocido. Usa ISO o 'YYYY-MM-DD HH:MM:SS'.")
        else:
            raise ValueError("date debe ser None, str o datetime")
        return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")



    def add_betis_clan_info(self, level: Optional[int] = None, capital_points: Optional[int] = None,
                            streak: Optional[int] = None, total_trophies: Optional[int] = None, wins: Optional[int] = None,
                            losses: Optional[int] = None, members_count: Optional[int] = None,
                            capital_league: Optional[str] = None, date: Optional[Union[str, datetime]] = None) -> int:
        """
        Inserta una fila en betis_clan_info solo si:
        - no existe ya una fila para la misma fecha (YYYY-MM-DD), y
        - los campos (level, capital_points, streak, total_trophies, wins, losses, members_count, capital_league)
          difieren de la última fila registrada.
        Retorna rowid de la fila insertada. Lanza ValueError si se rechaza la inserción.
        """

        # normalizar tipos básicos
        def to_int_or_none(v):
            if v is None:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                raise ValueError("Campos numéricos deben ser enteros o None")

        level = to_int_or_none(level)
        capital_points = to_int_or_none(capital_points)
        streak = to_int_or_none(streak)
        total_trophies = to_int_or_none(total_trophies)
        wins = to_int_or_none(wins)
        losses = to_int_or_none(losses)
        members_count = to_int_or_none(members_count)
        capital_league_norm = capital_league.strip() if isinstance(capital_league,
                                                                   str) and capital_league.strip() != "" else None

        # normalizar fecha a YYYY-MM-DD
        if date is None:
            dt = datetime.now()
        elif isinstance(date, datetime):
            dt = date
        elif isinstance(date, str):
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.fromisoformat(date) if fmt == "%Y-%m-%d" and len(date) == 10 else datetime.strptime(
                        date, fmt)
                    break
                except Exception:
                    dt = None
            if dt is None:
                # último intento con fromisoformat general
                try:
                    dt = datetime.fromisoformat(date)
                except Exception:
                    raise ValueError("Formato de fecha no reconocido. Usa 'YYYY-MM-DD' o ISO.")
        else:
            raise ValueError("date debe ser None, str o datetime")

        date_day = dt.date().isoformat()

        conn = sqlite3.connect(self.__db_name)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys = ON")

            # 1) comprobar si ya hay entrada para el mismo día
            cur.execute("SELECT 1 FROM betis_clan_info WHERE date = ? LIMIT 1", (date_day,))
            if cur.fetchone() is not None:
                raise ValueError(f"Ya existe una entrada para la fecha {date_day}")

            # 2) obtener la última entrada y comparar campos (excepto date)
            cur.execute("""
                SELECT level, capital_points, streak, total_trophies, wins, losses, members_count, capital_league
                FROM betis_clan_info
                ORDER BY id DESC
                LIMIT 1
            """)
            last = cur.fetchone()
            if last is not None:
                last_normalized = (
                    None if last[0] is None else int(last[0]),
                    None if last[1] is None else int(last[1]),
                    None if last[2] is None else int(last[2]),
                    None if last[3] is None else int(last[3]),
                    None if last[4] is None else int(last[4]),
                    None if last[5] is None else int(last[5]),
                    None if last[6] is None else int(last[6]),
                    None if last[7] is None else str(last[7]).strip()
                )
                current_tuple = (level, capital_points, streak, total_trophies, wins, losses, members_count,
                                 capital_league_norm)
                if current_tuple == last_normalized:
                    raise ValueError("Entrada idéntica a la última registrada; no se inserta.")

            # 3) insertar
            cur.execute("""
                INSERT INTO betis_clan_info
                    (level, capital_points, streak, total_trophies, wins, losses, members_count, capital_league, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (level, capital_points, streak, total_trophies, wins, losses, members_count, capital_league_norm,
                  date_day))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def add_member_membership(self, player_tag: str, event_type: str, date: Optional[Union[str, datetime]] = None,
                              notes: Optional[str] = None, check_player_exists: bool = True) -> int:
        """
        Inserta un evento de membresía en `clan_membership`.

        Parámetros:
        - player_tag: tag del jugador (obligatorio).
        - event_type: 'join' o 'leave'.
        - date: None | str | datetime (si None usa ahora).
        - notes: texto opcional.
        - check_player_exists: si True valida que player_tag exista en `players`.

        Retorna:
        - rowid de la fila insertada.
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")

        if event_type not in ("join", "leave"):
            raise ValueError("event_type debe ser 'join' o 'leave'")

        # normalizar fecha a 'YYYY-MM-DD HH:MM:SS'
        date_str = self._parse_date_to_str(date)

        conn = sqlite3.connect(self.__db_name)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys = ON")

            if check_player_exists:
                cur.execute("SELECT 1 FROM players WHERE player_tag = ? LIMIT 1", (player_tag,))
                if cur.fetchone() is None:
                    raise ValueError(f"player_tag '{player_tag}' no existe en la tabla players. "
                                     "Inserta el jugador antes o usa check_player_exists=False.")

            cur.execute(
                """
                INSERT INTO clan_membership (player_tag, event_date, event_type, notes)
                VALUES (?, ?, ?, ?)
                """,
                (player_tag, date_str, event_type, notes)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


    def get_membership_by_player(self, player_tag: str) -> pd.DataFrame:
        """
        Devuelve un pandas.DataFrame con los eventos de membresía del jugador.
        Columnas: id, player_tag, event_date (datetime), event_type, notes.
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")

        conn = sqlite3.connect(self.__db_name)
        try:
            query = """
                SELECT id, player_tag, event_date, event_type, notes
                FROM clan_membership
                WHERE player_tag = ?
                ORDER BY event_date DESC, id DESC
            """
            df = pd.read_sql_query(query, conn, params=[player_tag])

            # Asegurar columnas incluso si no hay filas
            for col in ["id", "player_tag", "event_date", "event_type", "notes"]:
                if col not in df.columns:
                    df[col] = pd.Series(dtype="object")

            # Normalizar event_date a datetime (NaT si no parseable)
            df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")

            return df.loc[:, ["id", "player_tag", "event_date", "event_type", "notes"]]
        finally:
            conn.close()

    # def add_war(self, clan_opponent_tag: str, end_hour: str, is_league: bool = False,
    #             attacks_per_member: int = 2) -> bool:
    #     """
    #     Inserta una guerra en la tabla `wars` verificando unicidad por opponent_tag.
    #     Si ya existe, devuelve la guerra existente como dict:
    #         {"rowid": int, "opponent_tag": str, "end_hour": str, "is_league": bool, "attacks_per_member": int}
    #     Si se inserta, devuelve el rowid (int) de la nueva fila.
    #     """
    #     if not clan_opponent_tag:
    #         raise ValueError("clan_opponent_tag es obligatorio")
    #
    #     # Normalizar end_hour a 'HH:MM' o 'HH:MM:SS'
    #     try:
    #         dt = datetime.strptime(end_hour, "%H:%M:%S")
    #         end_norm = dt.strftime("%H:%M:%S")
    #     except Exception:
    #         try:
    #             dt = datetime.strptime(end_hour, "%H:%M")
    #             end_norm = dt.strftime("%H:%M")
    #         except Exception:
    #             raise ValueError("end_hour debe tener formato 'HH:MM' o 'HH:MM:SS'")
    #
    #     try:
    #         attacks_per_member = int(attacks_per_member)
    #         if attacks_per_member < 0:
    #             raise ValueError()
    #     except Exception:
    #         raise ValueError("attacks_per_member debe ser un entero >= 0")
    #
    #     is_league_int = 1 if is_league else 0
    #
    #     conn = sqlite3.connect(self.__db_name)
    #     cur = conn.cursor()
    #     try:
    #         cur.execute("PRAGMA foreign_keys = ON")
    #
    #         # Intentar obtener la guerra existente (incluye rowid)
    #         cur.execute(
    #             "SELECT rowid, clan_opponent_tag, end_hour, is_league, attacks_per_member FROM wars WHERE opponent_tag = ? LIMIT 1",
    #             (clan_opponent_tag,)
    #         )
    #         existing = cur.fetchone()
    #         if existing is not None:
    #             return False
    #
    #         # Insertar nueva guerra
    #         cur.execute(
    #             """
    #             INSERT INTO wars (clan_opponent_tag, end_hour, is_league, attacks_per_member)
    #             VALUES (?, ?, ?, ?)
    #             """,
    #             (clan_opponent_tag, end_norm, is_league_int, attacks_per_member)
    #         )
    #         conn.commit()
    #         return True
    #     finally:
    #         conn.close()
    def add_war(self, clan_opponent_tag: str, end_hour: str, is_league: bool = False,
                attacks_per_member: int = 2) -> bool:
        """
        Inserta una guerra en la tabla `wars` verificando unicidad por clan_opponent_tag.
        Devuelve True si se inserta, False si ya existe.
        """
        if not clan_opponent_tag:
            raise ValueError("clan_opponent_tag es obligatorio")

        # Normalizar end_hour a 'HH:MM' o 'HH:MM:SS'
        try:
            dt = datetime.strptime(end_hour, "%H:%M:%S")
            end_norm = dt.strftime("%H:%M:%S")
        except Exception:
            try:
                dt = datetime.strptime(end_hour, "%H:%M")
                end_norm = dt.strftime("%H:%M")
            except Exception:
                raise ValueError("end_hour debe tener formato 'HH:MM' o 'HH:MM:SS'")

        try:
            attacks_per_member = int(attacks_per_member)
            if attacks_per_member < 0:
                raise ValueError()
        except Exception:
            raise ValueError("attacks_per_member debe ser un entero >= 0")

        is_league_int = 1 if is_league else 0

        conn = sqlite3.connect(self.__db_name)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys = ON")

            # Intentar obtener la guerra existente por la columna correcta
            cur.execute(
                "SELECT rowid, clan_opponent_tag, end_hour, is_league, attacks_per_member FROM wars WHERE clan_opponent_tag = ? LIMIT 1",
                (clan_opponent_tag,)
            )
            existing = cur.fetchone()
            if existing is not None:
                return False

            # Insertar nueva guerra
            cur.execute(
                """
                INSERT INTO wars (clan_opponent_tag, end_hour, is_league, attacks_per_member)
                VALUES (?, ?, ?, ?)
                """,
                (clan_opponent_tag, end_norm, is_league_int, attacks_per_member)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    # def add_war_member(self, player_tag: str, clan_tag: str, clan_opponent_tag: str, town_hall: Optional[int] = None,
    #                    map_position: Optional[int] = None, check_war_exists: bool = True) -> bool:
    #     """
    #     Inserta un miembro de guerra en `war_members`. Si ya existe la combinación
    #     (player_tag, clan_tag, opponent_tag) devuelve su rowid, si no la inserta y
    #     devuelve el nuevo rowid.
    #     """
    #     if not player_tag:
    #         raise ValueError("player_tag es obligatorio")
    #     if not clan_tag:
    #         raise ValueError("clan_tag es obligatorio")
    #     if not clan_opponent_tag:
    #         raise ValueError("opponent_tag es obligatorio")
    #
    #     # Normalizar enteros opcionales
    #     try:
    #         town_hall = None if town_hall is None else int(town_hall)
    #     except (TypeError, ValueError):
    #         raise ValueError("town_hall debe ser un entero o None")
    #     try:
    #         map_position = None if map_position is None else int(map_position)
    #     except (TypeError, ValueError):
    #         raise ValueError("map_position debe ser un entero o None")
    #
    #     conn = sqlite3.connect(self.__db_name)
    #     cur = conn.cursor()
    #     try:
    #         cur.execute("PRAGMA foreign_keys = ON")
    #
    #         if check_war_exists:
    #             cur.execute("SELECT 1 FROM wars WHERE opponent_tag = ? LIMIT 1", (clan_opponent_tag,))
    #             if cur.fetchone() is None:
    #                 raise ValueError(f"clan_opponent_tag '{clan_opponent_tag}' no existe en la tabla wars")
    #
    #         # Comprobar existencia de la combinación única
    #         cur.execute(
    #             "SELECT rowid FROM war_members WHERE player_tag = ? AND clan_tag = ? AND clan_opponent_tag = ? LIMIT 1",
    #             (player_tag, clan_tag, clan_opponent_tag)
    #         )
    #         existing = cur.fetchone()
    #         if existing is not None:
    #             return False
    #
    #         # Insertar nueva fila
    #         cur.execute(
    #             """
    #             INSERT INTO war_members (player_tag, clan_tag, clan_opponent_tag, town_hall, map_position)
    #             VALUES (?, ?, ?, ?, ?)
    #             """,
    #             (player_tag, clan_tag, clan_opponent_tag, town_hall, map_position)
    #         )
    #         conn.commit()
    #         return True
    #     finally:
    #         conn.close()
    def add_war_member(self, player_tag: str, clan_tag: str, clan_opponent_tag: str, town_hall: Optional[int] = None,
                       map_position: Optional[int] = None, check_war_exists: bool = True) -> bool:
        """
        Inserta un miembro de guerra en `war_members`. Si ya existe la combinación
        (player_tag, clan_tag, clan_opponent_tag) devuelve False, si no la inserta y
        devuelve True.
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")
        if not clan_tag:
            raise ValueError("clan_tag es obligatorio")
        if not clan_opponent_tag:
            raise ValueError("clan_opponent_tag es obligatorio")

        # Normalizar enteros opcionales
        try:
            town_hall = None if town_hall is None else int(town_hall)
        except (TypeError, ValueError):
            raise ValueError("town_hall debe ser un entero o None")
        try:
            map_position = None if map_position is None else int(map_position)
        except (TypeError, ValueError):
            raise ValueError("map_position debe ser un entero o None")

        conn = sqlite3.connect(self.__db_name)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys = ON")

            if check_war_exists:
                # comprobar existencia de la guerra usando la columna correcta
                cur.execute("SELECT 1 FROM wars WHERE clan_opponent_tag = ? LIMIT 1", (clan_opponent_tag,))
                if cur.fetchone() is None:
                    raise ValueError(f"clan_opponent_tag '{clan_opponent_tag}' no existe en la tabla wars")

            # Comprobar existencia de la combinación única
            cur.execute(
                "SELECT rowid FROM war_members WHERE player_tag = ? AND clan_tag = ? AND clan_opponent_tag = ? LIMIT 1",
                (player_tag, clan_tag, clan_opponent_tag)
            )
            existing = cur.fetchone()
            if existing is not None:
                return False

            # Insertar nueva fila
            cur.execute(
                """
                INSERT INTO war_members (player_tag, clan_tag, clan_opponent_tag, town_hall, map_position)
                VALUES (?, ?, ?, ?, ?)
                """,
                (player_tag, clan_tag, clan_opponent_tag, town_hall, map_position)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def add_attack(self, player_tag: str, player_opponent_tag: str, stars: int, destruction: Union[float, int],
                   duration: int) -> bool:
        """
        Inserta un ataque en la tabla `attacks`. Si ya existe otra fila con la misma
        combinación (excepto id) devuelve su rowid; si no, inserta y devuelve el nuevo rowid.
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")
        if not player_opponent_tag:
            raise ValueError("player_opponent_tag es obligatorio")

        # validar stars
        try:
            stars = int(stars)
        except (TypeError, ValueError):
            raise ValueError("stars debe ser un entero")
        if stars not in (0, 1, 2, 3):
            raise ValueError("stars debe estar en 0,1,2 o 3")

        # validar destruction (0..100) y normalizar (redondear para comparación estable)
        try:
            destruction = round(float(destruction), 3)
        except (TypeError, ValueError):
            raise ValueError("destruction debe ser un número")
        if destruction < 0 or destruction > 100:
            raise ValueError("destruction debe estar entre 0 y 100")

        # validar duration
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            raise ValueError("duration debe ser un entero (segundos)")
        if duration < 0:
            raise ValueError("duration debe ser >= 0")

        conn = sqlite3.connect(self.__db_name)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys = ON")

            # Comprobar existencia de la combinación única (ignorando id)
            cur.execute(
                """
                SELECT rowid FROM attacks
                WHERE player_tag = ? AND player_opponent_tag = ? AND stars = ? AND destruction = ? AND duration = ?
                LIMIT 1
                """,
                (player_tag, player_opponent_tag, stars, destruction, duration)
            )
            existing = cur.fetchone()
            if existing is not None:
                return False

            # Insertar nuevo ataque
            cur.execute(
                """
                INSERT INTO attacks (player_tag, player_opponent_tag, stars, destruction, duration)
                VALUES (?, ?, ?, ?, ?)
                """,
                (player_tag, player_opponent_tag, stars, destruction, duration)
            )
            conn.commit()
            return True
        finally:
            conn.close()


    def get_all_war_members(self) -> pd.DataFrame:
        """
        Devuelve un pandas.DataFrame con todos los registros de `war_members`.
        Columnas en este orden: id, player_tag, clan_tag, opponent_tag, town_hall, map_position.
        (Se hace alias de clan_opponent_tag a opponent_tag para compatibilidad).
        """
        conn = sqlite3.connect(self.__db_name)
        try:
            query = """
                SELECT id, player_tag, clan_tag, clan_opponent_tag AS opponent_tag, town_hall, map_position
                FROM war_members
                ORDER BY (map_position IS NULL), map_position, id
            """
            df = pd.read_sql_query(query, conn)
            # Asegurar orden/tuplas de columnas esperado incluso si no hay filas
            df = df.loc[:, ["id", "player_tag", "clan_tag", "opponent_tag", "town_hall", "map_position"]]
            print(df)
            return df
        finally:
            conn.close()

    def get_all_war_attacks(self) -> pd.DataFrame:
        """
        Devuelve un pandas.DataFrame con todos los registros de `war_members`.
        Columnas en este orden: id, player_tag, clan_tag, opponent_tag, town_hall, map_position.
        (Se hace alias de clan_opponent_tag a opponent_tag para compatibilidad).
        """
        conn = sqlite3.connect(self.__db_name)
        try:
            query = """
                SELECT *
                FROM attacks
            """
            df = pd.read_sql_query(query, conn)
            print(df)
            return df
        finally:
            conn.close()


    def __create_tables(self):
        connection = sqlite3.connect(self.__db_name)
        cursor = connection.cursor()

        # Tabla de jugadores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_tag TEXT PRIMARY KEY,
                username TEXT NOT NULL
            )
        """)

        # # Histórico de donaciones (donado y recibido)
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS donations (
        #         id INTEGER PRIMARY KEY AUTOINCREMENT,
        #         player_tag TEXT NOT NULL,
        #         donated INTEGER DEFAULT 0,     -- Donaciones hechas
        #         received INTEGER DEFAULT 0,    -- Donaciones recibidas
        #         date TEXT NOT NULL,            -- Fecha en formato ISO (YYYY-MM-DD HH:MM:SS)
        #         FOREIGN KEY (player_tag) REFERENCES players (player_tag)
        #     )
        # """)

        # Medallas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT NOT NULL,
                description TEXT NOT NULL,
                is_positive BOOLEAN NOT NULL,  -- TRUE = positiva, FALSE = negativa
                FOREIGN KEY (player_tag) REFERENCES players (player_tag)
            )
        """)

        # Histórico de membresía en el clan
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clan_membership (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT NOT NULL,
                event_date TEXT NOT NULL, -- fecha/hora ISO 'YYYY-MM-DD HH:MM:SS'
                event_type TEXT NOT NULL CHECK(event_type IN ('join','leave')),
                notes TEXT,
                FOREIGN KEY (player_tag) REFERENCES players (player_tag)
            );""")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS betis_clan_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level INTEGER,
                capital_points INTEGER,
                streak INTEGER,
                total_trophies INTEGER,
                wins INTEGER,
                losses INTEGER,
                members_count INTEGER,
                capital_league TEXT,
                date TEXT NOT NULL UNIQUE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wars (
                clan_opponent_tag TEXT NOT NULL UNIQUE,
                end_hour TEXT NOT NULL, -- formato 'HH:MM o HH:MM:SS'
                is_league INTEGER NOT NULL DEFAULT 0 CHECK (is_league IN (0,1)),
                attacks_per_member INTEGER NOT NULL DEFAULT 2
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS war_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT NOT NULL,
                clan_tag TEXT NOT NULL,
                clan_opponent_tag TEXT NOT NULL,
                town_hall INTEGER,
                map_position INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT NOT NULL,
                player_opponent_tag TEXT NOT NULL,
                stars INTEGER NOT NULL CHECK (stars IN (0,1,2,3)),
                destruction REAL NOT NULL CHECK (destruction >= 0 AND destruction <= 100),
                duration INTEGER NOT NULL CHECK (duration >= 0)
            )
        """)

        connection.commit()
        connection.close()
