import asyncio
import coc
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List


class CocCommunication:
    def __init__(self, client: coc.Client, email: str, password: str, my_clan: str):
        self.client = client
        self.email = email
        self.password = password
        self.my_clan = my_clan


    @classmethod
    async def create(cls, email: str, password: str, my_clan: str):
        client = coc.Client()
        await client.login(email, password)  # login es async
        return cls(client, email, password, my_clan)


    @staticmethod
    def __simply_league_name(liga: str) -> str:
        s = liga.replace(" League", "")
        return s


    async def get_clan_tag(self, clan_name: str) -> str | None:
        """
        Busca el tag del clan por su nombre.
        Devuelve el tag si lo encuentra, None si no.
        """
        try:
            clans = await self.client.search_clans(name=clan_name, limit=1)
            if clans:
                return clans[0].tag
            else:
                return None
        except coc.NotFound:
            return None


    @staticmethod
    def __wins_percent(wins: int, losses: int) -> int:
        total = wins + losses
        if total == 0:
            return 0  # evitar división por cero
        return int((wins / total) * 100)


    async def get_clan_info(self, clan_tag: str) -> dict:
        """
        Extrae información del clan dado su tag.

        Devuelve un dict con:
        - clan: nombre, nivel, puntos, miembros, etc.
        - members: lista de miembros con trofeos, donaciones y TH
        - current_war: estado si hay guerra en curso (None si no)
        - warlog: últimas guerras (si no están privadas)
        """
        info = {}
        clan = await self.client.get_clan(clan_tag)
        info["badge"] = clan.badge
        info["level"] = clan.level
        info["capital_points"] = clan.capital_points
        info["description"] = clan.description
        info["streak"] = clan.war_win_streak
        info["country"] = clan.location.name
        info["total_trophies"] = clan.points
        info["wins"] = clan.war_wins
        info["losses"] = clan.war_losses
        info["wins_percent"] = self.__wins_percent(clan.war_wins, clan.war_losses)
        info["members_count"] = clan.member_count
        info["capital_league"] = self.__simply_league_name(clan.capital_league.name)
        info["tag"] = clan.tag
        return info
    

    @staticmethod
    def __translate_rol_spanish(rol: str) -> str:
        res = ""
        if rol == "Leader":
            res = "Líder"
        elif rol == "Co-Leader":
            res = "Colíder"
        elif rol == "Member":
            res = "Miembro"
        elif rol == "Elder":
            res = "Veterano"
        return res


    async def get_members_info(self, clan_tag: str) -> List[Dict]:
        clan = await self.client.get_clan(clan_tag)
        rows = []

        async for player in clan.get_detailed_members():
            row = {
                'Nombre': player.name,
                'tag': player.tag,
                'Rol': self.__translate_rol_spanish(player.role.in_game_name),
                'Liga': self.__simply_league_name(player.league.name),
                'liga_icono':player.league.icon,
                'Trofeos': player.trophies,
                'Ayuntamiento': player.town_hall,
                'Total de estrellas': player.war_stars,
                'Puntos de la capital': getattr(player, 'clan_capital_contributions', None),
                'Rango': player.clan_rank,
                'Donaciones': player.donations,
                'Recibidos': player.received,
                'Quiere guerra': player.war_opted_in
            }
            rows.append(row)

        return rows

    async def get_war(self, clan_tag: str) -> Dict | None:
        try:
            war = await self.client.get_current_war(clan_tag)
            return war
        except coc.errors.PrivateWarLog:
            print("Warlog privada para %s, se devuelve None", clan_tag)
            return None
        except coc.errors.NotFound:
            print("No hay guerra activa para %s", clan_tag)
            return None
        except Exception:
            print("Error al obtener la guerra para %s", clan_tag)
            return None


    @staticmethod
    async def get_attack_info(attacks: list[coc.WarAttack]) -> list[dict]:
        """
        Extrae información de los ataques en una guerra.
        Devuelve una lista de diccionarios con:
        - tag del jugador
        - nombre del jugador
        - estrellas obtenidas
        - destrucción
        - oponente atacado
        """
        attack_info = []
        for attack in attacks:
            info = {
                "stars": attack.stars,
                "destruction": f"{attack.destruction:.1f}%",
                "opponent_tag": attack.defender.tag,
                "opponent_name": attack.defender.name,
                "duration": attack.duration
            }
            attack_info.append(info)

        return attack_info


    async def get_war_players_info_separado(self, clan_tag: str):
        """
        Devuelve dos listas:
          - miembros: info de los jugadores de tu clan
          - oponentes: info de los jugadores del clan rival
        """
        try:
            war = await self.client.get_current_war(clan_tag)
        except Exception as e:
            raise RuntimeError("No se puede acceder al registro de guerra.") from e

        async def procesar(miembro):
            ataques = miembro.attacks or []
            return {
                "tag":              miembro.tag,
                "name":             miembro.name,
                "map_position":     miembro.map_position,
                "ataques_realizados": await self.get_attack_info(ataques),
                "townhall":           miembro.town_hall,
            }

        miembros = [await procesar(m)
                    for m in war.clan.members]
        oponentes = [await procesar(m)
                     for m in war.opponent.members]

        return miembros, oponentes