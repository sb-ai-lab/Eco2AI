import os
import psutil
from eco2ai.resource_path import resource_filename
import json
import pandas as pd
import string
import numpy as np
import warnings
import requests
import datetime
from eco2ai.tools.tools_cpu import all_available_cpu
from eco2ai.tools.tools_gpu import all_available_gpu


class FileDoesNotExistsError(Exception):
    pass


class NotNeededExtensionError(Exception):
    pass


def available_devices() -> None:
    """
        This function prints all the available CPU & GPU devices

        Parameters
        ----------
        No parameters

        Returns
        -------
        No returns        
    
    """
    all_available_cpu()
    all_available_gpu()
    # need to add RAM


def is_file_opened(
    needed_file
):
    """
        This function checks if given file is opened in any python or jupyter process
        
        Parameters
        ----------
        needed_file: str
            Name of file that is going to be checked 
        
        Returns
        -------
        result: bool
            True if file is opened in any python or jupyter process
            

    """
    result = False
    needed_file = os.path.abspath(needed_file)
    python_processes = []
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=["name", "cpu_percent", "pid"])
            if "python" in pinfo["name"].lower() or "jupyter" in pinfo["name"].lower():
                python_processes.append(pinfo["pid"])
                flist = proc.open_files()
                if flist:
                    for nt in flist:
                        if needed_file in nt.path:
                            result = True
        except:
            pass
    return result


class NoCountryCodeError(Exception):
    pass


def _read_location_cache():
    """
        Country and region from the home config.
        An old location.json is copied into that file once and then removed.
    """
    data = _load_user_config_raw()
    location = os.path.join(os.path.dirname(user_config_path()), "location.json")
    if data.get("country"):
        _remove_file(location)
        return data.get("country"), data.get("region")
    old = _read_json_object(location)
    if not old or not old.get("country"):
        return None
    data["country"] = old["country"]
    data["region"] = old.get("region")
    _store_user_config(data)
    return data["country"], data.get("region")


def _write_location_cache(country, region):
    data = _load_user_config_raw()
    data["country"] = country
    data["region"] = region
    _store_user_config(data)


def _ip_location():
    """
    One IP lookup. None when the request fails or returns no country.
    """
    try:
        response = requests.get("https://ipinfo.io/", timeout=3)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    country = payload.get("country")
    if not country:
        return None
    return country, payload.get("region")


def _resolve_country_without_code():
    """
    Country and region when the caller did not pass alpha_2_code.
    Order: ECO2AI_ALPHA2, one IP request (then cache it), the cache, then World.
    """
    env_code = os.environ.get("ECO2AI_ALPHA2")
    if env_code:
        return env_code, None
    located = _ip_location()
    if located is not None:
        _write_location_cache(located[0], located[1])
        return located
    cached = _read_location_cache()
    if cached is not None:
        return cached
    warnings.warn(
        message="Country could not be resolved from ECO2AI_ALPHA2, the network, or the location cache. Using the World emission factor, 458.490 kg/MWh."
    )
    return "WORLD", None


def _carbon_factors(
    emission_level=None, 
    alpha_2_code=None,
    region=None
):
    """
        This function get an IP of user, defines country and region.
        Then, it searches user emission level by country and region in the emission level database.
        If there is no certain country, then it returns worldwide constant. 
        If there is certain country in the database, but no certain region, 
        then it returns average country emission level. 
        User can define own emission level and country, using the alpha2 country code.

        Parameters
        ----------
        emission_level: float
            User specified emission level value.
            emission_level is the mass of CO2 in kilos, which is produced  per every MWh of consumed energy.
            Default is None
        region: str
            User specified country region/state/district.
            Default is None
        alpha_2_code: str
            User specified country code
            User can search own country code here: https://www.iban.com/country-codes
            Default is None
        
        Returns
        -------
        tuple: tuple
            A tuple, where the first element is float emission value
            and the second element is a string containing a country 
            if user specified it or country and region in other case

    """
    if alpha_2_code is None and region is not None:
        raise NoCountryCodeError("In order to set 'region' parameter, 'alpha_2_code' parameter should be set")
    carbon_index_table_name = resource_filename('eco2ai', 'data/carbon_index.csv')
    if alpha_2_code is None:
        country, region = _resolve_country_without_code()
    else:
        country = alpha_2_code
    if emission_level is not None:
        label = f'({country}/{region})' if region is not None else f'({country})'
        return {
            "level": emission_level,
            "label": label,
            "year": "N/A",
            "source": "user",
            "basis": "user",
        }
    data = pd.read_csv(carbon_index_table_name)
    result = data[data['alpha_2_code'] == country]
    if result.shape[0] < 1:
        result = data[data['country'] == 'World']
    elif result.shape[0] > 1 and region is None:
        result = result[result['region'] == 'Whole country']
    elif result.shape[0] > 1:
        if result[result['region'] == region].shape[0] > 0:
            result = result[result['region'] == region]
        else: 
            flag = False
            for alternative_names in data[data['alpha_2_code'] == country]["alternative_name"].values:
                if (
                    type(alternative_names) is str and 
                    region.lower() in alternative_names.lower().split(',') and 
                    region != ""
                ):
                    flag = True
                    result = data[data['alternative_name'] == alternative_names]
            
            if flag is False:
                warnings.warn(
                    message=f"""
    Your 'region' parameter value, which is '{region}', is not found in our region database for chosen country. 
    Please, check, if your region name is written correctly
    """
                )
                result = result[result['region'] == 'Whole country']
    row = result.iloc[0]
    reference = str(row["reference"])
    basis = "CO2e" if reference in ("nga2025", "nir2024") else "CO2"
    label = f'{country}/{region}' if region is not None else f'{country}'
    return {
        "level": float(row["Emission intensity, kg/MWh"]),
        "label": label,
        "year": str(int(row["year"])),
        "source": reference,
        "basis": basis,
    }


def define_carbon_index(
    emission_level=None,
    alpha_2_code=None,
    region=None
):
    """
    Emission intensity and the country or country/region label.
    """
    factors = carbon_factors(emission_level, alpha_2_code, region)
    return (factors["level"], factors["label"])


def carbon_factors(
    emission_level=None,
    alpha_2_code=None,
    region=None
):
    """
    Intensity, label, data year, reference key, and CO2 or CO2e basis
    for the resolved carbon row. A user emission_level has year N/A
    and source and basis "user".
    """
    return _carbon_factors(emission_level, alpha_2_code, region)


class IncorrectPricingDict(Exception):
    pass


def electricity_pricing_check( 
    electricity_pricing,
):
    """
    This function takes electricity pricing dictionary and
    check it if the dictionary is constructed correctly.
    Rules for 'electricity_pricing' parameter construction is written below.        
    
    Parameters
    ----------
    electricity_pricing: dict
        Dictionary with time intervals as keys and electricity price during that intervals as values.
        Electricity price should be set without any currency designation.
        Every interval must be constructed as follows:
            1) "hh:mm-hh:mm", hh - hours, mm - minutes. hh in [0, ..., 23], mm in [0, ..., 59]
            ) Intervals should be consistent: they mustn't overlap and they should in chronological order.
            Instance of consistent intervals: "8:30-19:00", "19:00-6:00", "6:00-8:30"
            Instance of inconsistent intervals: "8:30-20:00", "18:00-3:00", "6:00-12:30"
            3) Total duration of time intervals in hours must be 24 hours(1 day). 

    Returns
    -------
    No returns
    """
    if electricity_pricing is None:
        return True
    electricity_pricing_array = [] 
    for key in electricity_pricing:
        tmp = [[int(i) for i in j.split(":")] for j in key.split("-")]
        electricity_pricing_array.append(tmp)
    electricity_pricing_array = np.array(electricity_pricing_array)
    
    # First check
    if (electricity_pricing_array[:, :, 0] >= 24).sum() > 0:
        raise IncorrectPricingDict(
            "Hour must be in 0..23"
        )
    
    # Second check
    if (electricity_pricing_array[:, :, 1] >= 60).sum() > 0:
        raise IncorrectPricingDict(
            "Minutes must be in 0..59"
        )
        
    today_date = datetime.datetime.today().timetuple()    

    dates = [[] for i in range(len(electricity_pricing_array))]
    for index, intervals in enumerate(electricity_pricing_array):
        add = 0
        if intervals[0][0] > intervals[1][0]:
            add += 1
        dt1 = datetime.datetime(
            year=today_date.tm_year,
            month=today_date.tm_mon,
            day=today_date.tm_mday,
            hour=intervals[0][0],
            minute=intervals[0][1],
        )
        dt2 = datetime.datetime(
            year=today_date.tm_year,
            month=today_date.tm_mon,
            day=today_date.tm_mday,
            hour=intervals[1][0],
            minute=intervals[1][1],
        )
        dt2 += datetime.timedelta(days=add)
        dates[index].append(dt1)
        dates[index].append(dt2)
            
    # Third check
    summ = 0
    for i in dates:
        summ += (i[1] - i[0]).total_seconds()
    summ /= 3600
    if summ != 24:
        raise IncorrectPricingDict(
            f"""
Total duration of time intervals in hours must be 24 hours!
Now, total duration equals: {summ}
"""
        )

    # Fourth check
    flag = True
    for index, _ in enumerate(dates):
        diff = (dates[index][0] - dates[index-1][1]).total_seconds() % (86400)
        if diff != 0:
            flag=False
    if not flag:
        raise IncorrectPricingDict(
            "Time intervals mustn't overlap and they should be sorted by time"
        )


def calculate_price( 
    electricity_pricing,
    kwh_energy,
):
    """
    This function takes electricity pricing dictionary and
    defines time interval current time belongs to.
    Rules for 'electricity_pricing' parameter construction is written below.        
    
    Parameters
    ----------
    electricity_pricing: dict
        Dictionary with time intervals as keys and electricity price during that intervals as values.
        Electricity price should be set without any currency designation.
        Every interval must be constructed as follows:
            1) "hh:mm-hh:mm", hh - hours, mm - minutes. hh in [0, ..., 23], mm in [0, ..., 59]
            ) Intervals should be consistent: they mustn't overlap and they should in chronological order.
            Instance of consistent intervals: "8:30-19:00", "19:00-6:00", "6:00-8:30"
            Instance of inconsistent intervals: "8:30-20:00", "18:00-3:00", "6:00-12:30"
            3) Total duration of time intervals in hours must be 24 hours(1 day). 
        
            
    kwh_energy: float
        Electrical power spent in kWh

    Returns
    -------
    electricity_price: float
        Total price of Electricity spent
    """
    electricity_pricing_array = [] 
    for key in electricity_pricing:
        tmp = [[int(i) for i in j.split(":")] for j in key.split("-")]
        electricity_pricing_array.append(tmp)
    electricity_pricing_array = np.array(electricity_pricing_array)
        
    today_date = datetime.datetime.today().timetuple()    
    interval_index = None

    dates = [[] for i in range(len(electricity_pricing_array))]
    for index, intervals in enumerate(electricity_pricing_array):
        add = 0
        if intervals[0][0] > intervals[1][0]:
            add += 1
        dt1 = datetime.datetime(
            year=today_date.tm_year,
            month=today_date.tm_mon,
            day=today_date.tm_mday,
            hour=intervals[0][0],
            minute=intervals[0][1],
        )
        dt2 = datetime.datetime(
            year=today_date.tm_year,
            month=today_date.tm_mon,
            day=today_date.tm_mday,
            hour=intervals[1][0],
            minute=intervals[1][1],
        )
        dt2 += datetime.timedelta(days=add)
        dates[index].append(dt1)
        dates[index].append(dt2)
        if (dt1-datetime.datetime.today()).total_seconds() * (dt2-datetime.datetime.today()).total_seconds() < 0:
            interval_index = index
        elif (
            (dt1-datetime.datetime.today()-datetime.timedelta(days=1)).total_seconds() * 
            (dt2-datetime.datetime.today()-datetime.timedelta(days=1)).total_seconds()
            ) < 0:
            interval_index = index

    electricity_price = list(electricity_pricing.values())[interval_index] * kwh_energy
    return electricity_price


def home_config_dir():
    """
        Directory of the machine-wide config, under the user home.
        The directory is created only when a config file is written.
    """
    return os.path.join(os.path.expanduser("~"), ".eco2ai")


def user_config_path():
    """
        Path of the config that holds tracker defaults plus country, region, and cpu_sockets.
        A worktree settings_dir selects <settings_dir>/config.json.
        Otherwise the file is ~/.eco2ai/config.json.
        The installed package data file is not writable for a non-root user.
    """
    settings = project_settings_dir()
    if settings:
        return os.path.join(settings, "config.json")
    return os.path.join(home_config_dir(), "config.json")


def project_config_dir(start=None):
    """
        Nearest directory that already contains .eco2ai/config.json or config.txt.
        The walk starts at start, or the current directory, and stops at the
        filesystem root. The home directory itself is not a project config.
        None when no project config exists.
    """
    found = _project_config_file(start)
    if found is None:
        return None
    return os.path.dirname(found)


def _project_config_file(start=None):
    home = os.path.normcase(os.path.abspath(home_config_dir()))
    current = os.path.abspath(start or os.getcwd())
    while True:
        directory = os.path.join(current, ".eco2ai")
        if os.path.normcase(os.path.abspath(directory)) != home:
            for name in ("config.json", "config.txt"):
                candidate = os.path.join(directory, name)
                if os.path.isfile(candidate):
                    return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _read_json_object(path):
    if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _remove_file(path):
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _legacy_config_path(config_path):
    return os.path.join(os.path.dirname(config_path), "config.txt")


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _load_user_config_raw():
    """
        Home config.json, or a sibling config.txt when the json file is absent.
        A missing file is an empty dict and is not created.
    """
    path = user_config_path()
    loaded = _read_json_object(path)
    if loaded is not None:
        return loaded
    legacy = _legacy_config_path(path)
    if _same_path(legacy, path):
        return {}
    loaded = _read_json_object(legacy)
    if loaded is None:
        return {}
    return loaded


def _absorb_sidecar_files(data, directory):
    location = os.path.join(directory, "location.json")
    old_location = _read_json_object(location)
    if old_location is not None:
        if not data.get("country") and old_location.get("country"):
            data["country"] = old_location["country"]
            if "region" not in data:
                data["region"] = old_location.get("region")
        _remove_file(location)
    hardware = os.path.join(directory, "hardware.json")
    old_hardware = _read_json_object(hardware)
    if old_hardware is not None:
        if _positive_int(data.get("cpu_sockets")) is None:
            count = _positive_int(old_hardware.get("cpu_sockets"))
            if count is not None:
                data["cpu_sockets"] = count
        _remove_file(hardware)
    return data


def _store_user_config(data):
    """
        Write the home config and drop a sibling config.txt after that write.
        location.json and hardware.json are folded in and removed.
    """
    path = user_config_path()
    directory = os.path.dirname(path)
    payload = _absorb_sidecar_files(dict(data), directory)
    os.makedirs(directory, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(temporary, path)
    legacy = _legacy_config_path(path)
    if not _same_path(legacy, path):
        _remove_file(legacy)
    return path


def _project_directory_value(key, start=None):
    path = _project_config_file(start)
    if path is None:
        return None
    loaded = _read_json_object(path)
    if not loaded:
        return None
    value = loaded.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return os.path.abspath(os.path.expanduser(value.strip()))


def project_settings_dir(start=None):
    """
        settings_dir from the nearest project .eco2ai config, or None.
        That directory's config.json holds country, region, cpu_sockets, and set_params defaults.
    """
    return _project_directory_value("settings_dir", start)


def project_results_dir(start=None):
    """
        results_dir from the nearest project .eco2ai config, or None.
    """
    return _project_directory_value("results_dir", start)


def describe_folders(start=None):
    """
        Two lines naming the active settings folder and results folder.
        A missing settings_dir is the user home .eco2ai directory.
        A missing results_dir is the process working directory.
    """
    settings = project_settings_dir(start)
    if not settings:
        settings = os.path.abspath(home_config_dir())
    results = project_results_dir(start)
    if not results:
        results = "(working directory)"
    return "settings_dir: %s\nresults_dir: %s\n" % (settings, results)


def resolve_results_file(file_name):
    """
        Join a relative file_name to results_dir when that setting exists.
        An absolute file_name is returned unchanged.
        A missing results_dir leaves a relative file_name unchanged.
    """
    if not file_name or os.path.isabs(file_name):
        return file_name
    results_dir = project_results_dir()
    if not results_dir:
        return file_name
    resolved = os.path.join(results_dir, file_name)
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return resolved


def _default_config():
    return {
        "project_name": "default project name",
        "experiment_description": "default experiment description",
        "file_name": "emission.csv",
        "measure_period": 10,
        "pue": 1,
    }


def _config_dictionary(params):
    dictionary = dict(params)
    for key, value in _default_config().items():
        if key not in dictionary:
            dictionary[key] = value
    return dictionary


def write_config_file(path, params):
    """
        Replace one config file with params.
        Missing tracker defaults are filled in. Other keys, including
        cpu_sockets, are stored as given. The replace is atomic for readers.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(_config_dictionary(params)))
    os.replace(temporary, path)


def set_params(**params):
    """
        This function sets default Tracker attributes values in ~/.eco2ai/config.json:
        project_name = ...
        experiment_description = ...
        file_name = ...
        measure_period = ...
        pue = ...
        
        Parameters
        ----------
        params: dict
            Keyword arguments stored in the home config.
            project_name, experiment_description, file_name, measure_period, and pue
            are filled with built-in values when omitted.
            Any other keyword is stored as given.
            country, region, and cpu_sockets already in the file are kept.
        
        Returns
        -------
        No return

    """
    current = _load_user_config_raw()
    current.update(params)
    write_config_file(user_config_path(), current)
    legacy = _legacy_config_path(user_config_path())
    if not _same_path(legacy, user_config_path()):
        _remove_file(legacy)


def get_params():
    """
        This function returns default Tracker attributes values from
        ~/.eco2ai/config.json. An old config.txt is read when the json file
        is absent. A missing file returns built-in defaults and does not
        create a file.
        project_name = ...
        experiment_description = ...
        file_name = ...
        measure_period = ...
        pue = ...
        More complete information about attributes can be seen in Tracker class
        
        Parameters
        ----------
        No parameters
        
        Returns
        -------
        params: dict
            Dictionary of Tracker parameters: project_name, experiment_description, file_name, measure_period and pue

    """
    loaded = _load_user_config_raw()
    if not loaded:
        return _builtin_tracker_defaults()
    result = _builtin_tracker_defaults()
    result.update(loaded)
    return result


def _builtin_tracker_defaults():
    return {
        "project_name": "Default project name",
        "experiment_description": "no experiment description",
        "file_name": "emission.csv",
        "measure_period": 10,
        "pue": 1,
    }


def _positive_int(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def read_cpu_socket_cache():
    """
        Cached socket count from the home config, or None.
        An old hardware.json is copied into that file once and then removed.
    """
    data = _load_user_config_raw()
    hardware = os.path.join(os.path.dirname(user_config_path()), "hardware.json")
    count = _positive_int(data.get("cpu_sockets"))
    if count is not None:
        _remove_file(hardware)
        return count
    old = _read_json_object(hardware)
    if not old:
        return None
    count = _positive_int(old.get("cpu_sockets"))
    if count is None:
        return None
    data["cpu_sockets"] = count
    _store_user_config(data)
    return count


def write_cpu_socket_cache(count):
    """
        Store one probed socket count in the home config.
    """
    data = _load_user_config_raw()
    data["cpu_sockets"] = int(count)
    _store_user_config(data)


def encode(f_string):
    """
        This function encodes given string.

        Parameters
        ----------
        f_string: str
            A string user wants to encode

        Returns
        -------
        encoded_string: str
            Resultant encoded string
    
    """
    n=5
    symbols = string.printable[:95] + 'йцукенгшщзхъфывапролджэячсмитьбюёЁЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ'
    symbols = symbols.replace(',', '')
    symbols = symbols.replace('\"', '')
    symbols = symbols.replace('\'', '')
    s = ''
    for i in range(0,int(len(symbols)/2)):
        s += symbols[i] + symbols[i+int(len(symbols)/2)]
    symbols = s
    
    encoded_string = ""
    for letter in f_string:
        try:
            index = symbols.index(letter)
            encoded_string += symbols[index+n]
        except:
            encoded_string += letter
    return encoded_string


def encode_dataframe(values):
    """
        This function encodes every value of a two-dimensional array

        Parameters
        ----------
        values: array
            Array, which values user wants to encode

        Returns
        -------
        values: array
            Resultant encoded array
        
    
    """
    values = values.astype(str)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            values[i][j] = encode(values[i][j])
    return values


def summary(
    filename,
    write_to_file=False,
):
    """
        This function makes a summary of the specified .csv file. 
        It sums up duration, power consumption and CO2 emissions for every project separately
        and for all the projects together. 
        For every sum up it makes separate line in a summary dataframe with the following columns:
            project_name
            total duration(s)
            total power_consumption(kWTh)
            total CO2_emissions(kg)
            total electricity cost
        Number of lines equals number of projects + 1, as the last line is summary for all the projects.
        
        Parameters
        ----------
        filename: str
            Name of file the user wants to analyse.
        write_to_file: str
            If this parameter is not None the resultant dataframe will be written to file with name of this parameter.
            For example, is write_to_file == 'total_summary_project_1.csv', 
            then resultant summary dataframe will be written to file 'total_summary_project_1.csv'.
            Default is None

        Returns
        -------
        summary_data: pandas.DataFrame
            The result dataframe, containing a summary for every project separately and full summary.
            For every sum up it makes separate line in a result dataframe with the following columns:
                project_name
                total duration(s)
                total power_consumption(kWTh)
                total CO2_emissions(kg)
                total electricity cost
    
    """
    if not os.path.exists(filename):
        raise FileDoesNotExistsError(f'File \'{filename}\' does not exist')
    if not filename.endswith('.csv'):
        raise NotNeededExtensionError('File need to be with extension \'.csv\'')
    df = pd.read_csv(filename)
    if df.empty:
        raise ValueError("CSV file is empty, cannot summarize.")
    projects = np.unique(df['project_name'].values)
    summary_data = []
    columns = [
            'project_name', 
            'total duration(s)', 
            'total power_consumption(kWh)', 
            'total CO2_emissions(kg)',
            'total electricity cost',
        ]
    summ = np.zeros(4)
    for project in projects:
        values = df[df['project_name'] == project][
                ['duration(s)', 'power_consumption(kWh)', 'CO2_emissions(kg)', 'cost']
            ].values.sum(axis=0)
        summ += values
        values = list(values)
        values.insert(0, project)
        summary_data.append(values)
        
    summ = list(summ)
    summ.insert(0, 'All the projects')
    summary_data.append(summ)
    summary_data = pd.DataFrame(
        summary_data,
        columns=columns
    )
    if write_to_file:
        summary_data.to_csv(write_to_file)
    return summary_data