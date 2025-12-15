import os
import streamlit as st
from betis_management import CocCommunication
from db_adapter import DbManagement
from DB_sqlite import SQLiteAdapter
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
import requests

torch.classes.__path__ = []



def check_password(plain_password: str) -> bool:
    """Verifica la contraseña contra el hash almacenado en .env"""
    hashed_password = st.secrets["coliders"]["password"].encode()
    if not hashed_password:
        raise RuntimeError("password no está definido en tombl")

    return bcrypt.checkpw(plain_password.encode(), hashed_password)


async def main_async():
    load_dotenv()
    email = os.getenv("EMAIL")
    password = os.getenv("COCKEY")
    my_clan = os.getenv("MY_CLAN")

    if not email or not password:
        raise RuntimeError(
            f"EMAIL o COCKEY no están definidos correctamente. "
            f"EMAIL={email!r}, COCKEY definido={bool(password)}"
        )

    coc_comm = await CocCommunication.create(email=email, password=password, my_clan=my_clan)
    betis_clan_tag = await coc_comm.get_clan_tag("Betis CoC Club")
    clan_info = await coc_comm.get_clan_info(betis_clan_tag)
    betis_clan = Clan.from_dict(clan_info)
    db_adapter = SQLiteAdapter(db_name="DB/BetisDB.db")

    # await coc_comm.get_war_players_info_separado(clan_tag)

    members_dict = await coc_comm.get_members_info(betis_clan_tag)
    members = DictToDataFrame.members_dict_to_dataframe(members_dict)
    db_management = DbManagement(db_adapter=db_adapter)
    db_management.add_players(members_dict)
    _ = db_management.add_betis_clan_info(betis_info=betis_clan)

    players = db_management.get_all_players()
    players_usernames = []

    for player in players:
        player.medals = db_management.get_player_medals(player.tag)
        players_usernames.append(player.username)

    Player.populate_from_dicts(players, members_dict)

    members = DataFrameOperations.add_medals_and_days_to_players_df(members, players)

    badge_url = betis_clan.badge_url#clan_info["badge"].url
    response = requests.get(badge_url)
    image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'images', 'clan_badge.png'))
    if os.path.exists(image_path):
        os.remove(image_path)

    with open(image_path, "wb") as f:
        f.write(response.content)

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

    # ==== DESDE AQUÍ TU APP NORMAL (antes estaba dentro del if authentication_status) ====

    st.session_state['file_downloaded'] = False

    st.sidebar.image(image_path, use_container_width=True)
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



    coc_war_obj = await coc_comm.get_war(betis_clan_tag)
    war_info = await War.get_war_info(coc_war_obj)

    if db_management.add_war_from_object(war=war_info):
        print("Guerra añadida a la base de datos.")

    members, opponents = await coc_comm.get_war_players_info_separado(clan_tag=betis_clan_tag)


    col_enemy_clan_info, col_enemy_badge, _ = st.columns([ 6, 2, 2])
    if war_info is not None:

        enemy_clan = Clan.from_dict(await coc_comm.get_clan_info(war_info.tag_opponent))
        summary = db_management.add_members_and_attacks(members=members, opponents=opponents, clan_tag=betis_clan_tag,
                                              opponent_clan_tag=enemy_clan.tag)
        print(summary)
        print("Miembros de la guerra añadidos a la base de datos.")
        db_adapter.get_all_war_members()
        print("ATAQUES")
        db_adapter.get_all_war_attacks()
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






def main():
    asyncio.run(main_async())   # 🚀 Ejecuta lo async


# Reemplazar el bloque __main__ para no forzar el login
if __name__ == "__main__":
    # ===== Inicialización para evitar KeyError pero SIN forzar autenticación =====
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = None  # mostrar pantalla de login por defecto
        st.session_state["name"] = None
    # ================================================
    temp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'temp'))
    main()
