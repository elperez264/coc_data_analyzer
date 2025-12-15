from DB_sqlite import SQLiteAdapter
from typing import Dict, List
from data.player import Player
from data.medal import Medal
from data.clan import Clan
from data.war import War
from datetime import datetime


class DbManagement:
    def __init__(self, db_adapter: SQLiteAdapter):
        self.db_adapter = db_adapter

    def get_all_players(self) -> List[Player]:
        players_df = self.db_adapter.get_all_players()
        players_list: List[Player] = []
        for _, row in players_df.iterrows():
            players_list.append(Player(tag=row["player_tag"], username=row["username"],
                                       membership_days=self.get_membership_days(row["player_tag"])["total_days"]))
        return players_list

    # python
    def add_players(self, players: List[Dict]):
        """Add multiple players to the database.
        :param players: Use the Response of coc_comm.get_members_info(clan_tag)"""
        actual_players = self.get_all_players()
        actual_tags = [p.tag for p in actual_players]
        for player in players:
            if not player['tag']:
                raise ValueError("tag es obligatorio")
            if player['tag'][0] != '#':
                raise ValueError("tag debe comenzar con '#'")
            if not player['tag'] in actual_tags:
                # Primero asegurar que el jugador exista en la tabla players
                self.db_adapter.add_or_update_player(player['Nombre'], player['tag'])
                # Luego registrar el evento de unión
                self.db_adapter.add_member_membership(player_tag=player["tag"], event_type="join", date=datetime.now(),
                                                      check_player_exists=False)
            else:
                # Si ya existía, solo actualizar nombre
                self.db_adapter.add_or_update_player(player['Nombre'], player['tag'])

        for actual_player in actual_players:
            if not any(p['tag'] == actual_player.tag for p in players):
                self.db_adapter.add_member_membership(player_tag=actual_player.tag, event_type="leave",
                                                      date=datetime.now(),
                                                      check_player_exists=False)


    def get_player_medals(self, player_tag: str) -> List[Medal]:
        medals_df = self.db_adapter.get_medals_by_player(player_tag)
        medals_list: List[Medal] = []
        for _, row in medals_df.iterrows():
            medals_list.append(Medal(description=row["description"], is_positive=bool(row["is_positive"])))
        return medals_list


    def add_betis_clan_info(self, betis_info: Clan) -> Dict:
        """
        Intenta añadir la info del clan y detecta dos condiciones de rechazo:
        - Entrada para la misma fecha ya existe -> devuelve reason='duplicate_date'
        - Entrada idéntica a la última registrada -> devuelve reason='identical_to_last'
        Devuelve {'inserted': True, 'rowid': int} si se inserta, o
        {'inserted': False, 'reason': str, 'message': str} si se rechaza.
        """
        try:
            rowid = self.db_adapter.add_betis_clan_info(
                level=betis_info.level,
                total_trophies=betis_info.total_trophies,
                members_count=betis_info.members_count,
                wins=betis_info.wins,
                losses=betis_info.losses,
                streak=betis_info.streak,
                capital_points=betis_info.capital_points,
                capital_league=betis_info.capital_league
            )
            return {"inserted": True, "rowid": rowid}
        except ValueError as e:
            msg = str(e)
            if msg.startswith("Ya existe una entrada para la fecha"):
                return {"inserted": False, "reason": "duplicate_date"}
            if msg == "Entrada idéntica a la última registrada; no se inserta.":
                return {"inserted": False, "reason": "identical_to_last"}
            raise


    def get_membership_days(self, player_tag: str) -> dict:
        """
        Devuelve dict con:
        - total_days: días acumulados en el clan (float, dos decimales)
        - current_days: días desde la última unión si está dentro actualmente (0.0 si no)
        - currently_in_clan: bool
        """
        if not player_tag:
            raise ValueError("player_tag es obligatorio")

        # evitar dependencia en el top del módulo: importar pandas localmente
        import pandas as pd
        from datetime import datetime as _dt

        df = self.db_adapter.get_membership_by_player(player_tag)
        if df.empty:
            return {"total_days": 0.0, "current_days": 0.0, "currently_in_clan": False}

        # ordenar cronológicamente (asc)
        df = df.sort_values(by="event_date", ascending=True)

        total_seconds = 0.0
        in_clan = False
        current_start = None
        last_join = None

        for _, row in df.iterrows():
            etype = row.get("event_type")
            edate = row.get("event_date")

            if pd.isna(edate):
                continue

            # asegurar tipo datetime (pd.Timestamp -> datetime)
            if isinstance(edate, pd.Timestamp):
                edate_dt = edate.to_pydatetime()
            elif isinstance(edate, _dt):
                edate_dt = edate
            else:
                # si no es datetime, intentar parsear
                try:
                    edate_dt = _dt.fromisoformat(str(edate))
                except Exception:
                    continue

            if etype == "join":
                if not in_clan:
                    in_clan = True
                    current_start = edate_dt
                    last_join = edate_dt
                else:
                    # entrada redundante 'join' mientras ya está dentro -> ignorar
                    continue
            elif etype == "leave":
                if in_clan and current_start is not None:
                    # sumar intervalo y cerrar periodo
                    if edate_dt > current_start:
                        total_seconds += (edate_dt - current_start).total_seconds()
                    in_clan = False
                    current_start = None
                else:
                    # 'leave' sin 'join' previo -> ignorar
                    continue
            else:
                # tipo de evento desconocido -> ignorar
                continue

        current_days = 0.0
        if in_clan and current_start is not None:
            now = _dt.now()
            # sumar el tiempo desde current_start hasta ahora al total acumulado
            if now > current_start:
                total_seconds += (now - current_start).total_seconds()
            current_days = (now - last_join).total_seconds() / 86400.0
            currently_in_clan = True
        else:
            currently_in_clan = False

        total_days = total_seconds / 86400.0

        return {
            "total_days": round(total_days, 2),
            "current_days": round(current_days, 2),
            "currently_in_clan": currently_in_clan
        }


    def add_war_from_object(self, war: War) -> int:
        """
        Inserta una guerra a partir de un objeto `War` llamando a `self.db_adapter.add_war`.
        Lanza ValueError si faltan campos obligatorios o si la inserción falla.
        """
        if war is None:
            raise ValueError("war es obligatorio")

        # import local para evitar dependencias al importar el módulo
        from data.war import War
        if not isinstance(war, War):
            raise ValueError("Objeto `war` debe ser una instancia de data.war.War")

        # preferir tag_opponent (tag), si no usar opponent_name
        opponent_tag = getattr(war, "tag_opponent", None) or getattr(war, "opponent_name", None)
        end_hour = getattr(war, "end_hour", None)
        is_league = bool(getattr(war, "is_league", False))
        attacks_per_member = getattr(war, "attacks_per_member", 2)

        if not opponent_tag:
            raise ValueError("opponent_tag (tag_opponent u opponent_name) es obligatorio")
        if not end_hour:
            raise ValueError("end_hour es obligatorio")

        # Delegar a SQLiteAdapter; dejar que lance ValueError en caso de duplicados o formato inválido
        return self.db_adapter.add_war(
            clan_opponent_tag=opponent_tag,
            end_hour=end_hour,
            is_league=is_league,
            attacks_per_member=attacks_per_member
        )

    # python
    def add_members_and_attacks(self, members: List, opponents: List, clan_tag: str, opponent_clan_tag: str) -> Dict:
        """
        Inserta war_members y attacks para ambos bandos.
        - members: lista de jugadores del clan (cada uno con 'tag','name','map_position','townhall','ataques_realizados')
        - opponents: lista de jugadores del clan contrario (misma estructura)
        - clan_tag: tag del clan propio
        - opponent_clan_tag: tag del clan contrario
        """
        if not isinstance(members, list) or not isinstance(opponents, list):
            raise ValueError("members y opponents deben ser listas")
        if not clan_tag:
            raise ValueError("clan_tag es obligatorio")
        if not opponent_clan_tag:
            raise ValueError("opponent_clan_tag es obligatorio")

        summary = {
            "players_processed": 0,
            "members_inserted": 0,
            "members_skipped": 0,
            "attacks_inserted": 0,
            "attacks_skipped": 0
        }

        # Asegurar guerras para ambos bandos (silencioso)
        try:
            self.db_adapter.add_war(clan_opponent_tag=opponent_clan_tag, end_hour="00:00")
        except Exception:
            pass
        try:
            self.db_adapter.add_war(clan_opponent_tag=clan_tag, end_hour="00:00")
        except Exception:
            pass

        def _process_side(players_list: List[dict], owner_clan_tag: str, enemy_clan_tag: str):
            """
            owner_clan_tag: tag del clan al que pertenece cada jugador de esta lista
            enemy_clan_tag: tag del clan contrario (se usará como clan_opponent_tag)
            """
            for p in players_list:
                try:
                    ptag = p.get("tag")
                    pname = p.get("name", "") or ""
                    map_pos = p.get("map_position")
                    townhall = p.get("townhall")
                    ataques = p.get("ataques_realizados", []) or []

                    if not ptag or not pname:
                        continue

                    # Registrar/actualizar jugador
                    try:
                        self.db_adapter.add_or_update_player(pname, ptag)
                        summary["players_processed"] += 1
                    except Exception:
                        # continuar aun si falla el nombre
                        pass

                    # Insertar como miembro: clan_tag = owner_clan_tag, clan_opponent_tag = enemy_clan_tag
                    try:
                        added = self.db_adapter.add_war_member(
                            player_tag=ptag,
                            clan_tag=owner_clan_tag,
                            clan_opponent_tag=enemy_clan_tag,
                            town_hall=townhall,
                            map_position=map_pos,
                            check_war_exists=True
                        )
                    except ValueError:
                        # intentar crear la guerra correspondiente y reintentar
                        try:
                            self.db_adapter.add_war(clan_opponent_tag=enemy_clan_tag, end_hour="00:00")
                            added = self.db_adapter.add_war_member(
                                player_tag=ptag,
                                clan_tag=owner_clan_tag,
                                clan_opponent_tag=enemy_clan_tag,
                                town_hall=townhall,
                                map_position=map_pos,
                                check_war_exists=True
                            )
                        except Exception:
                            added = False

                    if added:
                        summary["members_inserted"] += 1
                    else:
                        summary["members_skipped"] += 1

                    # Procesar ataques del jugador
                    for atk in ataques:
                        try:
                            stars = atk.get("stars")
                            destruction_raw = atk.get("destruction")
                            target_tag = atk.get("opponent_tag") or atk.get("opponent") or atk.get("target")
                            duration = atk.get("duration")
                            target_name = atk.get("opponent_name", "") or ""

                            if not target_tag:
                                summary["attacks_skipped"] += 1
                                continue

                            # Normalizar destruction (p. ej. "84.0%" -> 84.0)
                            if isinstance(destruction_raw, str):
                                destruction_num = destruction_raw.strip().rstrip("%").strip()
                                destruction = float(destruction_num) if destruction_num != "" else 0.0
                            else:
                                destruction = float(destruction_raw or 0.0)

                            stars = int(stars)
                            duration = int(duration)

                            inserted = self.db_adapter.add_attack(
                                player_tag=ptag,
                                player_opponent_tag=target_tag,
                                stars=stars,
                                destruction=destruction,
                                duration=duration
                            )
                            if inserted:
                                summary["attacks_inserted"] += 1
                            else:
                                summary["attacks_skipped"] += 1
                        except Exception:
                            summary["attacks_skipped"] += 1
                            continue
                except Exception:
                    continue

        # Procesar oponentes: owner_clan = opponent_clan_tag, enemy_clan = clan_tag
        _process_side(opponents, owner_clan_tag=opponent_clan_tag, enemy_clan_tag=clan_tag)
        # Procesar miembros propios: owner_clan = clan_tag, enemy_clan = opponent_clan_tag
        _process_side(members, owner_clan_tag=clan_tag, enemy_clan_tag=opponent_clan_tag)

        return summary

    # def add_members_and_attacks(self, members: List, opponents: List, clan_tag: str, opponent_clan_tag: str) -> Dict:
    #     if not isinstance(members, list) or not isinstance(opponents, list):
    #         raise ValueError("members y opponents deben ser listas")
    #     if not clan_tag:
    #         raise ValueError("clan_tag es obligatorio")
    #     if not opponent_clan_tag:
    #         raise ValueError("opponent_clan_tag es obligatorio")
    #
    #     summary = {
    #         "players_processed": 0,
    #         "members_inserted": 0,
    #         "members_skipped": 0,
    #         "attacks_inserted": 0,
    #         "attacks_skipped": 0
    #     }
    #
    #     # Asegurar guerras para ambos bandos (silencioso)
    #     try:
    #         try:
    #             self.db_adapter.add_war(opponent_clan_tag, end_hour="00:00")
    #         except TypeError:
    #             self.db_adapter.add_war(opponent_clan_tag, "00:00")
    #     except Exception:
    #         pass
    #
    #     try:
    #         try:
    #             self.db_adapter.add_war(clan_tag, end_hour="00:00")
    #         except TypeError:
    #             self.db_adapter.add_war(clan_tag, "00:00")
    #     except Exception:
    #         pass
    #
    #     # Procesar oponentes: registrar player, añadir como miembro del bando contrario y procesar sus ataques
    #     for op in opponents:
    #         try:
    #             otag = op.get("tag")
    #             oname = op.get("name", "") if isinstance(op, dict) else None
    #             map_pos = op.get("map_position")
    #             townhall = op.get("townhall")
    #             ataques = op.get("ataques_realizados", []) or []
    #
    #             if not otag or not oname:
    #                 continue
    #
    #             # Registrar/actualizar player
    #             try:
    #                 self.db_adapter.add_or_update_player(oname, otag)
    #                 summary["players_processed"] += 1
    #             except Exception:
    #                 pass
    #
    #             # Añadir oponente como war_member (clan = opponent_clan_tag, opponent = clan_tag)
    #             try:
    #                 added_opponent_member = self.db_adapter.add_war_member(
    #                     player_tag=otag,
    #                     clan_tag=opponent_clan_tag,
    #                     clan_opponent_tag=clan_tag,
    #                     town_hall=townhall,
    #                     map_position=map_pos,
    #                     check_war_exists=True
    #                 )
    #             except ValueError:
    #                 # intentar crear guerra y reintentar
    #                 try:
    #                     try:
    #                         self.db_adapter.add_war(clan_tag, end_hour="00:00")
    #                     except TypeError:
    #                         self.db_adapter.add_war(clan_tag, "00:00")
    #                     added_opponent_member = self.db_adapter.add_war_member(
    #                         player_tag=otag,
    #                         clan_tag=opponent_clan_tag,
    #                         clan_opponent_tag=clan_tag,
    #                         town_hall=townhall,
    #                         map_position=map_pos,
    #                         check_war_exists=True
    #                     )
    #                 except Exception:
    #                     added_opponent_member = False
    #
    #             if added_opponent_member:
    #                 summary["members_inserted"] += 1
    #             else:
    #                 summary["members_skipped"] += 1
    #
    #             # Procesar ataques del oponente
    #             for atk in ataques:
    #                 try:
    #                     stars = atk.get("stars")
    #                     destruction_raw = atk.get("destruction")
    #                     target_tag = atk.get("opponent_tag")
    #                     duration = atk.get("duration")
    #
    #                     if not target_tag:
    #                         continue
    #
    #                     if isinstance(destruction_raw, str):
    #                         destruction_num = destruction_raw.strip().rstrip("%")
    #                         destruction = float(destruction_num) if destruction_num != "" else 0.0
    #                     else:
    #                         destruction = float(destruction_raw)
    #
    #                     duration = int(duration)
    #                     stars = int(stars)
    #
    #                     inserted_attack = self.db_adapter.add_attack(
    #                         player_tag=otag,
    #                         player_opponent_tag=target_tag,
    #                         stars=stars,
    #                         destruction=destruction,
    #                         duration=duration
    #                     )
    #                     if inserted_attack:
    #                         summary["attacks_inserted"] += 1
    #                     else:
    #                         summary["attacks_skipped"] += 1
    #                 except Exception:
    #                     summary["attacks_skipped"] += 1
    #                     continue
    #         except Exception:
    #             continue
    #
    #     # Procesar miembros propios (igual que antes)
    #     for m in members:
    #         try:
    #             player_tag = m.get("tag")
    #             player_name = m.get("name", "")
    #             map_pos = m.get("map_position")
    #             townhall = m.get("townhall")
    #             ataques = m.get("ataques_realizados", []) or []
    #
    #             if not player_tag or not player_name:
    #                 continue
    #
    #             self.db_adapter.add_or_update_player(player_name, player_tag)
    #             summary["players_processed"] += 1
    #
    #             # Añadir miembro propio
    #             try:
    #                 inserted_member = self.db_adapter.add_war_member(
    #                     player_tag=player_tag,
    #                     clan_tag=clan_tag,
    #                     clan_opponent_tag=opponent_clan_tag,
    #                     town_hall=townhall,
    #                     map_position=map_pos,
    #                     check_war_exists=True
    #                 )
    #             except ValueError:
    #                 try:
    #                     try:
    #                         self.db_adapter.add_war(opponent_clan_tag, end_hour="00:00")
    #                     except TypeError:
    #                         self.db_adapter.add_war(opponent_clan_tag, "00:00")
    #                     inserted_member = self.db_adapter.add_war_member(
    #                         player_tag=player_tag,
    #                         clan_tag=clan_tag,
    #                         clan_opponent_tag=opponent_clan_tag,
    #                         town_hall=townhall,
    #                         map_position=map_pos,
    #                         check_war_exists=True
    #                     )
    #                 except Exception:
    #                     inserted_member = False
    #
    #             if inserted_member:
    #                 summary["members_inserted"] += 1
    #             else:
    #                 summary["members_skipped"] += 1
    #
    #             # Procesar ataques del miembro
    #             for atk in ataques:
    #                 try:
    #                     stars = atk.get("stars")
    #                     destruction_raw = atk.get("destruction")
    #                     opponent_tag = atk.get("opponent_tag")
    #                     duration = atk.get("duration")
    #
    #                     if not opponent_tag:
    #                         continue
    #
    #                     if isinstance(destruction_raw, str):
    #                         destruction_num = destruction_raw.strip().rstrip("%")
    #                         destruction = float(destruction_num) if destruction_num != "" else 0.0
    #                     else:
    #                         destruction = float(destruction_raw)
    #
    #                     duration = int(duration)
    #                     stars = int(stars)
    #
    #                     inserted_attack = self.db_adapter.add_attack(
    #                         player_tag=player_tag,
    #                         player_opponent_tag=opponent_tag,
    #                         stars=stars,
    #                         destruction=destruction,
    #                         duration=duration
    #                     )
    #                     if inserted_attack:
    #                         summary["attacks_inserted"] += 1
    #                     else:
    #                         summary["attacks_skipped"] += 1
    #                 except Exception:
    #                     summary["attacks_skipped"] += 1
    #                     continue
    #         except Exception:
    #             continue
    #
    #     return summary

