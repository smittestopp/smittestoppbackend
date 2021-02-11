import pandas as pd

def create_map_for_user(dict_m):
    """
    Creates the map for a single user or several users in the db.

    Parameters
    ----------
    dict_m : dictionary
        Dictionary containing the users gps data

    Returns
    ----------
    keplergl map
        A map object containing all users points in the map. Can be printed
        with print(map) or saved to file via map.save_to_html(file_name=your_file_name)
    """

    try:
        from keplergl import KeplerGl
        map_to_print = KeplerGl()
        for user in dict_m:
            df_map = dict_m[user]
            df_pp = pd.DataFrame(df_map, columns=["latitude", "longitude"])
            map_to_print.add_data(data=df_pp, name=user)
        return map_to_print

    except:
        print("Kepler is not instaled!")
        print("Please install kepler if you wish to generate map visualizations.")