import os
from typing import Dict
from dataclasses import asdict

import streamlit as st
from betis_management import CocCommunication
from db_management import DbManagement
from DB_sqlite import SQLAdapter
from dict_to_df import DictToDataFrame
from dataframe_operations import DataFrameOperations
from string_operations import  StringOperations
from data.war import War
from data.clan import Clan
import pandas as pd
from data.player import Player
import bcrypt
from dotenv import load_dotenv
import torch
import asyncio
import pickle

torch.classes.__path__ = []


from dataclasses import is_dataclass, fields
from enum import Enum
from datetime import datetime, date


def to_serializable(obj):
    """Convierte datos a estructuras simples serializables."""

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {
            str(k): to_serializable(v)
            for k, v in obj.items()
        }

    if isinstance(obj, (list, tuple, set)):
        return [to_serializable(v) for v in obj]

    if is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: to_serializable(getattr(obj, f.name))
            for f in fields(obj)
        }

    raise TypeError(
        f"No se puede serializar un objeto de tipo "
        f"{type(obj).__name__}"
    )


@st.cache_data(ttl=3600, show_spinner=False)
def get_war_data(clan_tag):
    return asyncio.run(fetch_war_data(clan_tag))

async def fetch_war_data(clan_tag):
    _, db_management = get_db_classes()
    coc_comm = await create_coc_communication()
    coc_war_obj = await coc_comm.get_war(clan_tag)
    war_info = War.get_war_info(coc_war_obj)

    if war_info is None:
        return None, None, None, None, None

    members, opponents = await coc_comm.get_war_players_info_separado(clan_tag=clan_tag)

    enemy_info = await coc_comm.get_clan_info(war_info.tag_opponent)
    enemy_info = fix_badge_url(enemy_info)
    war_id = db_management.add_war_from_object(war=war_info)
    return war_info.to_dict(), members, opponents, enemy_info, war_id


def comprobar_pickle(**objetos):
    for nombre, objeto in objetos.items():
        try:
            pickle.dumps(objeto)
            print(f"[OK] {nombre}: {type(objeto)}")
        except Exception as e:
            print(f"[ERROR] {nombre}: {type(objeto)}")
            print(f"        {repr(e)}")

@st.cache_resource
def get_db_classes():
    db_key = st.secrets["DB_KEY"]
    db_url = st.secrets["DB_URL"]
    db_adapter = SQLAdapter(db_url=db_url, db_key=db_key)
    db_management = DbManagement(db_adapter=db_adapter)
    return db_adapter, db_management


# async def create_coc_communication():
#     api_token = st.secrets["COC_API_TOKEN"]
#     my_clan = st.secrets["MY_CLAN"]
#     if not api_token:
#         raise RuntimeError(f"api_token no están definidos correctamente.")
#     coc_comm = await CocCommunication.create(api_token=api_token, my_clan=my_clan)
#     return coc_comm
async def create_coc_communication():
    email = st.secrets["EMAIL"]
    password = st.secrets["COCKEY"]
    my_clan = st.secrets["MY_CLAN"]

    if not email or not password:
        raise RuntimeError("Las credenciales de Clash of Clans no están configuradas.")

    coc_comm = await CocCommunication.create_by_account(email=email, password=password, my_clan=my_clan)

    return coc_comm

@st.cache_data(ttl=28800, show_spinner=False)
def get_clan_data(_db_management: DbManagement):
    return asyncio.run(fetch_clan_data(_db_management))

async def fetch_clan_data(db_management: DbManagement):
    coc_comm = await create_coc_communication()
    clan_tag = await coc_comm.get_clan_tag("Betis CoC Club")
    clan_info = await coc_comm.get_clan_info(clan_tag)
    clan_info = fix_badge_url(clan_info)
    clan_info["icon"] = {}

    members_dict = await coc_comm.get_members_info(clan_tag)

    members = DictToDataFrame.members_dict_to_dataframe(members_dict)
    betis_clan = Clan.from_dict(clan_info)

    print("Añadiendo jugadores a la base de datos...")
    db_management.add_players(members_dict)
    _ = db_management.add_betis_clan_info(betis_info=betis_clan)

    print("Recuperando jugadores de la base de datos...")
    players = db_management.get_all_players()
    players_usernames = []
    for player in players:
        player.medals = db_management.get_player_medals(player.tag)
        players_usernames.append(player.username)
    print(f"Se han recuperado {len(players_usernames)} nombres de jugadores de la base de datos.")
    Player.populate_from_dicts(players, members_dict)

    members = DataFrameOperations.add_medals_and_days_to_players_df(members, players)
    players_dicts = [asdict(player) for player in players]

    return (
        clan_tag,
        to_serializable(clan_info),
        members,
        to_serializable(players_dicts),
        players_usernames
    )

def fix_badge_url(clan_info: Dict) -> Dict:
    if clan_info is not None:
        badge = clan_info.get("badge")
        if badge is not None:
            clan_info["badge"] = {"url": badge.url}
    return clan_info

def check_password(plain_password: str) -> bool:
    """Verifica la contraseña contra el hash almacenado en .env"""
    hashed_password = st.secrets["coliders"]["password"].encode()
    if not hashed_password:
        raise RuntimeError("password no está definido en tombl")

    return bcrypt.checkpw(plain_password.encode(), hashed_password)


def main():
    load_dotenv()

    db_adapter, db_management = get_db_classes()

    betis_clan_tag, clan_info, members, players_dict, players_usernames = get_clan_data(db_management)
    betis_clan = Clan.from_dict(clan_info)
    players = Player.from_dicts(players_dict)

    st.set_page_config(
        page_title="Mesa de Guerra Bética",
        page_icon="🟢",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = None  # None = aún no ha intentado
    if "is_co_leader" not in st.session_state:
        st.session_state["is_co_leader"] = False
    if "name" not in st.session_state:
        st.session_state["name"] = None

    # ==== FUNCIÓN PANTALLA DE LOGIN (NUEVO) ====
    def login_screen():
        st.title("Mesa de Guerra Bética")
        st.write("Introduce tu **nombre en el juego**, no importan las mayúsculas, acentos ni símbolos.")

        username_input = st.text_input("Nombre de jugador")
        password_input = None  # solo se usará si es colíder

        if username_input:

            username_login_index = StringOperations.find_name_in_sublists(name=username_input, names_list=players_usernames)

            if username_login_index == -1:
                st.error("No se ha encontrado ese jugador en el clan.")
                st.session_state["authentication_status"] = False
            else:
                # Encontrado en el clan
                player_name = players[username_login_index].username
                st.session_state["name"] = player_name
                st.session_state["player"] = players[username_login_index]

                role_value = str(players[username_login_index].rank).lower()
                is_co_leader = (role_value == "colider" or role_value == "lider")

                st.session_state["is_co_leader"] = is_co_leader

                if is_co_leader:
                    st.info(f"{player_name} es colíder. Se requiere contraseña adicional.")
                    password_input = st.text_input("Contraseña de colíder", type="password")

                if st.button("Entrar"):
                    if is_co_leader:
                        if check_password(password_input):
                            st.session_state["authentication_status"] = True
                            st.success(f"Bienvenido, colíder {player_name} 🛡️")
                            st.rerun()
                        else:
                            st.error("Contraseña de colíder incorrecta.")
                            st.session_state["authentication_status"] = False
                    else:
                        # Miembro normal: solo nombre correcto
                        st.session_state["authentication_status"] = True
                        st.success(f"Bienvenido, {player_name} ⚔️")
                        st.rerun()

        # Mensajes según estado
        if st.session_state["authentication_status"] is None:
            st.warning("Por favor, introduce tu nombre para acceder.")
        elif st.session_state["authentication_status"] is False:
            st.error("No se ha podido iniciar sesión. Revisa el nombre (y contraseña si eres colíder).")

    # ==== SI NO ESTÁ AUTENTICADO, MOSTRAR SOLO LOGIN Y SALIR ====
    if st.session_state["authentication_status"] is not True:
        login_screen()
        return

    st.session_state['file_downloaded'] = False

    # st.sidebar.image(image_path, use_container_width=True)
    st.sidebar.image(betis_clan.badge_url, use_container_width=True)
    st.sidebar.write("<br>" * 1, unsafe_allow_html=True)
    st.sidebar.markdown(f"<small><i>{betis_clan.description}</i><small>", unsafe_allow_html=True)

    st.sidebar.write("<br>" * 4, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([9, 0.2, 0.3])
    with col3:
        st.write("&nbsp;" * 5, unsafe_allow_html=True)

    with col1:
        if st.session_state["is_co_leader"]:
            st.write(f'Bienvenido, venerable colíder *{st.session_state["name"].replace('$', r'\$')}*')
        else:
            st.write(f'Bienvenido, *{st.session_state["name"].replace('$', r'\$')}*')

        st.subheader('Estado de la nación bética')
        st.write(f'Población: {str(betis_clan.members_count)} béticocs.')
        st.write(
            f'{betis_clan.wins_percent}% de victorias, {betis_clan.wins} victorias y {betis_clan.losses} derrotas.')
        if betis_clan.streak > 1:
            st.write(f'Racha de victorias en guerras: {betis_clan.streak} victorias.')
        elif betis_clan.streak == 1:
            st.write(f'El Betis comienza su racha, ha ganado su última guerra.')
        else:
            st.write(f'El Betis CoC Club ha perdido su racha de victorias en guerras.')
        st.write(f'La capital del clan está en la liga {betis_clan.capital_league}.')

        st.subheader('Ilustres miembros del Betis CoC Club')
        st.dataframe(members)
        st.subheader('Medallas y agravios')

    col_add_medal, col_see_medals, empty_col = st.columns([3.5,4.5, 0.5])
    max_rows_visible = 4
    row_height_px = 40
    tags = [player.tag for player in players]

    if st.session_state["is_co_leader"]:
        with col_add_medal:
            medal_option = ["Medalla", "Agravio"]
            st.markdown(f'**Añadir Medalla o agravio**')
            player_username_selected = st.selectbox("Selecciona un jugador:", players_usernames, key="selectbox_medalla")
            medal_agravio_selected = st.selectbox("Medalla o Agravio:", medal_option, key="selectbox_medalla_or_agravio")
            index_player = players_usernames.index(player_username_selected)
            is_medal = True if medal_option.index(medal_agravio_selected) == 0 else False
            tag_selected = tags[index_player]
            max_desc_chars = 70
            description = st.text_input(f"Descripción, máximo {max_desc_chars} carácteres...", key="desc_medalla")

            # Si supera el límite, recorta y muestra aviso
            if len(description) > max_desc_chars:
                st.warning(f"Se han permitido solo {max_desc_chars} caracteres. El texto fue recortado.")
                description = description[:max_desc_chars]

            if st.button("Añadir medalla", key="button_medalla"):
                if description.strip() == "":
                    st.error("La descripción no puede estar vacía.")
                else:
                    db_adapter.add_medal(tag_selected, description, is_positive=is_medal, check_player_exists=True)

        with col_see_medals:
            player_selected = players[index_player]

            st.markdown(f"**Medallas y Agravios de {player_username_selected.replace('$', r'\$')}**")
            desc_medals_of_player = [player_medal.description for player_medal in player_selected.get_positive_medals()]
            desc_agravios_of_player = [player_medal.description for player_medal in player_selected.get_negative_medals()]
            if len(desc_medals_of_player) == 0 and len(desc_agravios_of_player) == 0:
                st.write(player_username_selected.replace('$', r'\$') +" no tiene ni medallas ni agravios.")
            else:
                if len(desc_medals_of_player) > 0:
                    df = pd.DataFrame(desc_medals_of_player, columns=["Medallas"])

                    height = min(len(df), max_rows_visible) * row_height_px + 40  # margen para cabecera
                    st.dataframe(df.reset_index(drop=True), height=height)
                else:
                    st.write(player_username_selected.replace('$', r'\$') +" no tiene medallas.")

                if len(desc_agravios_of_player) > 0:
                    df = pd.DataFrame(desc_agravios_of_player, columns=["Agravios"])
                    height = min(len(df), max_rows_visible) * row_height_px + 40  # margen para cabecera
                    st.dataframe(df.reset_index(drop=True), height=height)
                else:
                    st.write(player_username_selected.replace('$', r'\$') +" no tiene agravios.")
    else:
        with col_add_medal:
            desc_medals_of_player = [player_medal.description for player_medal in st.session_state["player"].get_positive_medals()]
            desc_agravios_of_player = [player_medal.description for player_medal in
                                       st.session_state["player"].get_negative_medals()]
            if len(desc_medals_of_player) == 0 and len(desc_agravios_of_player) == 0:
                st.write(st.session_state["name"].replace('$', r'\$') + " no tiene ni medallas ni agravios.")
            else:
                if len(desc_medals_of_player) > 0:
                    df = pd.DataFrame(desc_medals_of_player, columns=["Medallas"])

                    height = min(len(df), max_rows_visible) * row_height_px + 40  # margen para cabecera
                    st.dataframe(df.reset_index(drop=True), height=height)
                else:
                    st.write(st.session_state["name"].replace('$', r'\$') + " no tiene medallas.")

        with col_see_medals:
            if not (len(desc_medals_of_player) == 0 and len(desc_agravios_of_player) == 0):
                if len(desc_agravios_of_player) > 0:
                    df = pd.DataFrame(desc_agravios_of_player, columns=["Agravios"])
                    height = min(len(df), max_rows_visible) * row_height_px + 40  # margen para cabecera
                    st.dataframe(df.reset_index(drop=True), height=height)
                else:
                    st.write(st.session_state["name"].replace('$', r'\$') + " no tiene agravios.")

    war_info, members, opponents, enemy_info, war_id = get_war_data(betis_clan_tag)
    war_info = War.from_dict(war_info)
    enemy_clan = Clan.from_dict(enemy_info) if enemy_info else None
    if war_info is not None and enemy_clan is not None:
        col_enemy_clan_info, col_enemy_badge, _ = st.columns([6, 2, 2])
        summary = db_management.add_members_and_attacks(members=members, opponents=opponents, clan_tag=betis_clan_tag,
                                              opponent_clan_tag=enemy_clan.tag, war_id=war_id)
        print(summary)

        if war_info.state == "terminada":
            st.subheader('Mesa de Guerra Bética')
            st.write("La guerra ha terminado, descansen béticocs.")
        else:
            with col_enemy_clan_info:
                st.subheader('Mesa de Guerra Bética')
                st.write(f'El Betis está en {war_info.state}.')
                st.write(f'Las batallas se librarán contra **{war_info.opponent_name}**')
                st.write(f'Esta fase acaba {war_info.date_end}, faltan {war_info.time_left}.')
                st.write(f'El clan rival tiene una poblacion de: {str(enemy_clan.members_count)} miembros.')
                st.write(
                    f'{enemy_clan.wins_percent}% de victorias, {enemy_clan.wins} victorias y {enemy_clan.losses} derrotas.')
            with col_enemy_badge:
                st.markdown(
                    f"""
                        <div style="text-align:center;">
                            <h3 style="margin:0; display:block; transform:translateX(11px);">VS</h3>
                            <img src="{enemy_clan.badge_url}" width="200" style="display:block; margin:8px auto;" />
                        </div>
                        """, unsafe_allow_html=True)
    else:
        st.info("El clan no está actualmente en guerra.")






# def main():
#     asyncio.run(main_async())   # 🚀 Ejecuta lo async


# Reemplazar el bloque __main__ para no forzar el login
if __name__ == "__main__":
    # ===== Inicialización para evitar KeyError pero SIN forzar autenticación =====
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = None  # mostrar pantalla de login por defecto
        st.session_state["name"] = None
    # ================================================
    temp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'temp'))
    main()
