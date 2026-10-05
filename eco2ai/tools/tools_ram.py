import psutil
import time
import os


FROM_WATTs_TO_kWATTh = 1000*3600


class RAM():
    """
        This class is the interface for tracking RAM power consumption.
        The RAM class is not intended for separate usage, outside the Tracker class

    """
    def __init__(self, ignore_warnings=False):
        """
            This class method initializes RAM object.
            Creates fields of class object. All the fields are private variables

            Parameters
            ----------
            ignore_warnings: bool
                If True, warnings are not shown. If False, warnings are shown.
                The default is False.

            Returns
            -------
            No returns

        """
        self._consumption = 0
        self._ignore_warnings = ignore_warnings
        self._start = time.time()


    def get_consumption(self):
        """
            This class method returns RAM power consupmtion amount.

            Parameters
            ----------
            No parameters

            Returns
            -------
            self._consumption: float
                RAM power consumption

        """
        self.calculate_consumption()
        return self._consumption
    

    def _get_memory_used(self,):
        """
            Resident memory of the current process and its child processes.
            The result is gigabytes of RSS, not virtual address space
            and not memory used by other processes.

            Parameters
            ----------
            No parameters

            Returns
            -------
            total_memory_used: float
                Resident memory of this process tree, in gigabytes.

        """
        try:
            proc = psutil.Process(os.getpid())
            rss_bytes = proc.memory_info().rss
            for child in proc.children(recursive=True):
                try:
                    rss_bytes += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return 0
        return rss_bytes / (1024 ** 3)


    def calculate_consumption(self) -> float:
        """
            This class method calculates RAM power consumption.
            
            Parameters
            ----------
            No parameters
            
            Returns
            -------
            consumption: float
                RAM power consumption
        
        """
        time_period = time.time() - self._start
        self._start = time.time()
        consumption = self._get_memory_used() * (3 / 8) * time_period / FROM_WATTs_TO_kWATTh
        if consumption < 0:  # ensure no negative values
            consumption = 0
        self._consumption += consumption
        # print(self._consumption)
        return consumption