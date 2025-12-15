import pandas as pd
from typing import List, Dict


class DictToDataFrame:
    """
    Converts a dictionary to a pandas DataFrame.
    """

    @staticmethod
    def to_dataframe(self) -> pd.DataFrame:
        """
        Converts the dictionary to a pandas DataFrame.

        :return: DataFrame representation of the dictionary.
        """
        return pd.DataFrame.from_dict(self.data, orient='index').reset_index()

    @staticmethod
    def list_dict_to_dataframe(list_dict: List[Dict]) -> pd.DataFrame:
        """
        Converts a list of dictionaries to a pandas DataFrame.

        :param list_dict: List of dictionaries to convert.
        :return: DataFrame representation of the list of dictionaries.
        """
        return pd.DataFrame(list_dict)

    @staticmethod
    def members_dict_to_dataframe(members: List[Dict]) -> pd.DataFrame:
        """
        Converts a dictionary of members to a pandas DataFrame.

        :param members: List of Dictionary of members to convert.
        :return: DataFrame representation of the members' dictionary.
        """
        df = DictToDataFrame.list_dict_to_dataframe(members)
        columns_to_drop = ["tag", "Rango", "liga_icono", "Quiere guerra", "Trofeos", "Liga"]  # lista con los nombres de las columnas
        df = df.drop(columns=columns_to_drop)
        df = df.reset_index(drop=True)
        return df