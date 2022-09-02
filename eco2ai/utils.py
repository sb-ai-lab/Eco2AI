import os
import psutil
from pkg_resources import resource_stream
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


def available_devices():
    """
        This function prints all the available CPU & GPU devices

        Parameters
        ----------
        No paarameters

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


def define_carbon_index(
    emission_level=None, 
    alpha_2_code=None,
    region=None
):
    """
        This function get an IP of user, defines country and region.
        Then, it searchs user emission level by country and region in the emission level database.
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
    carbon_index_table_name = resource_stream('eco2ai', 'data/carbon_index.csv').name
    if alpha_2_code is None:
        ip_dict = eval(requests.get("https://ipinfo.io/").content.decode('ascii'))
        country = ip_dict['country']
        region = ip_dict['region']
    else:
        country = alpha_2_code
    if emission_level is not None:
        return (emission_level, f'({country}/{region})') if region is not None else (emission_level, f'({country})')
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
    Your 'region' parameter value, which is '{region}', is not found in our region database for choosed country. 
    Please, check, if your region name is written correctly
    """
                )
                result = result[result['region'] == 'Whole country']
    result = result.values[0][-1]
    return (result, f'{country}/{region}') if region is not None else (result, f'{country}')


class IncorrectPricingDict(Exception):
    pass


def electricity_pricing_check( 
    electricity_pricing,
):
    """
    This function takes electricity pricing dictionary and
    check it if the dictionary is consctructed correctly.
    Rules for 'electricity_pricing' parameter construction is written below.        
    
    Parameters
    ----------
    electricity_pricing: dict
        Dictionary with time intervals as keys and electricity price during that intervals as values.
        Electricity price should be set without any currency designation.
        Every interval must be constructed as follows:
            1) "hh:mm-hh:mm", hh - hours, mm - minutes. hh in [0, ..., 23], mm in [0, ..., 59]
            ) Intervals should be consistent: they mustn't overlap and they should in chronological order.
            Instantce of consistent intervals: "8:30-19:00", "19:00-6:00", "6:00-8:30"
            Instantce of inconsistent intervals: "8:30-20:00", "18:00-3:00", "6:00-12:30"
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
            Instantce of consistent intervals: "8:30-19:00", "19:00-6:00", "6:00-8:30"
            Instantce of inconsistent intervals: "8:30-20:00", "18:00-3:00", "6:00-12:30"
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


def set_params(**params):
    """
        This function sets default Tracker attributes values to internal file:
        project_name = ...
        experiment_description = ...
        file_name = ...
        measure_period = ...
        pue = ...
        
        Parameters
        ----------
        params: dict
            Dictionary of Tracker parameters: project_name, experiment_description, file_name. 
            Other parameters in dictionary are ignored
        
        Returns
        -------
        No return

    """
    dictionary = dict()
    filename = resource_stream('eco2ai', 'data/config.txt').name
    for param in params:
        dictionary[param] = params[param]
    if "project_name" not in dictionary:
        dictionary["project_name"] = "default project name"
    if "experiment_description" not in dictionary:
        dictionary["experiment_description"] = "default experiment description"
    if "file_name" not in dictionary:
        dictionary["file_name"] = "emission.csv"
    if "measure_period" not in dictionary:
        dictionary["measure_period"] = 10
    if "pue" not in dictionary:
        dictionary["pue"] = 1
    with open(filename, 'w') as json_file:
        json_file.write(json.dumps(dictionary))


def get_params():
    """
        This function returns default Tracker attributes values:
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
    filename = resource_stream('eco2ai', 'data/config.txt').name
    if not os.path.isfile(filename):
        with open(filename, "w"):
            pass
    with open(filename, "r") as json_file:
        if os.path.getsize(filename):
            dictionary = json.loads(json_file.read())
        else:
            dictionary = {
                "project_name": "Deafult project name",
                "experiment_description": "no experiment description",
                "file_name": "emission.csv",
                "measure_period": 10,
                "pue": 1,
                }
    return dictionary


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
        This function encodes every value of a two-dimentional array

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