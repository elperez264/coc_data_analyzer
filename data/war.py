# python
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Optional


class War:
    def __init__(self, is_league: bool, end_hour: str, end_date: Optional[datetime], state: Optional[str] = None,
        opponent_name: Optional[str] = None, tag_opponent: Optional[str] = None, date_end: Optional[str] = None,
        time_left: Optional[str] = None, is_preparation_day: bool = False, attacks_per_member: int = 2,
                 start_date: Optional[datetime] = None):

        self.end_date = end_date
        self.state = state
        self.opponent_name = opponent_name
        self.tag_opponent = tag_opponent
        self.date_end = date_end
        self.time_left = time_left
        self.is_preparation_day = is_preparation_day
        self.attacks_per_member = attacks_per_member
        self.is_league = is_league
        self.end_hour = end_hour
        self.start_date = start_date



    @classmethod
    async def get_war_info(cls, war) -> War | None:
        if not war or getattr(war, "state", None) is None:
            return None

        if str(war.state.value) == "notInWar":
            return None

        war_state = str(war.state.value)
        attacks_per_member = getattr(war, "attacks_per_member", 2)
        is_league = war.is_cwl

        if str(war.state.value) == "inWar":
            war_state = "guerra"
        elif str(war.state.value) == "warEnded":
            war_state = "terminada"
        elif str(war.state.value) == "preparation":
            war_state = "preparación"

        start_obj = getattr(war, "start_time", None)
        end_obj = getattr(war, "end_time", None)

        inicio_naive = getattr(start_obj, "time", start_obj)
        fin_naive = getattr(end_obj, "time", end_obj)

        if not inicio_naive or not fin_naive:
            print("Tiempos de guerra incompletos para el clan")
            return None

        def to_utc(dt):
            if getattr(dt, "tzinfo", None) is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        try:
            inicio_utc = to_utc(inicio_naive)
            fin_utc = to_utc(fin_naive)
        except Exception:
            print("Formato de datetime inesperado en war para el clan")
            return None

        ahora_utc = datetime.now(timezone.utc)

        # Si aún no ha empezado, mostramos tiempo hasta inicio; si ya empezó, hasta el fin
        if ahora_utc < inicio_utc:
            restante = inicio_utc - ahora_utc
            prep = True
        else:
            restante = fin_utc - ahora_utc
            prep = False

        dias, resto = restante.days, restante.seconds
        horas, resto = divmod(resto, 3600)
        minutos, segundos = divmod(resto, 60)
        tiempo_rest = f"{dias}d {horas}h {minutos}m {segundos}s"

        zona_local = ZoneInfo("Europe/Madrid")
        inicio_local = inicio_utc.astimezone(zona_local)
        fin_local = fin_utc.astimezone(zona_local)

        # Usar la fecha/hora de inicio si estamos en preparación, si no la de fin
        target_local = inicio_local if prep else fin_local

        hoy = ahora_utc.astimezone(zona_local).date()
        target_date = target_local.date()
        if target_date == hoy:
            prefijo = "hoy"
        elif target_date == hoy + timedelta(days=1):
            prefijo = "mañana"
        else:
            prefijo = target_local.strftime("%A")

        hora_str = target_local.strftime("%H:%M")
        fecha_fin_str = f"{prefijo} a las {hora_str}"

        opponent_name = getattr(getattr(war, "opponent", None), "name", None)
        opponent_tag = getattr(getattr(war, "opponent", None), "tag", None)

        return cls(end_date=fin_utc, state=war_state, opponent_name=opponent_name, tag_opponent=opponent_tag,
                   date_end=fecha_fin_str, time_left=tiempo_rest, is_preparation_day=prep, start_date=str(inicio_naive),
                   attacks_per_member=attacks_per_member, is_league=is_league, end_hour=hora_str)


    def __str__(self) -> str:
        return (f"Guerra(estado={self.state}, oponente={self.opponent_name}, "
                f"fin={self.date_end}, tiempo_restante={self.time_left}, hora_fin={self.end_hour}, "
                f"preparación={self.is_preparation_day}, ataques_por_miembro={self.attacks_per_member}, "
                f"es_liga={self.is_league})")