
import threading, logging
from time import sleep
from os import system, listdir
from os.path import isdir

logging.basicConfig(format="%(asctime)s (%(levelname)s) : %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.INFO)


class CmdLineThread(threading.Thread):
    def __init__(self, cmd:str, args:list =[]):
        threading.Thread.__init__(self)
        self.__cmd = cmd
        self.__args = " ".join(args)
        self.__statusCode = -1

    def run(self):
        self.start_info()
        self.__statusCode = system(f"{self.__cmd} {self.__args}")

    def start_info(self):
        logging.info(f"CmdLineThread() - Execute command `{self.__cmd} {self.__args}`")

    def isSuccess(self):
        if self.__statusCode == -1:
            logging.warning('CmdLineThread() - Thread not executed')
        return (self.__statusCode == 0)


def getRunningThreads(Threads):
    Running = 0
    for Th in Threads:
        alive = False
        try:
            alive = Th.isAlive()
        except Exception:
            alive = Th.is_alive()
        if alive:
            Running += 1
    return Running


def executeThreads(Threads, MaxCurrent=16, MaxExec=-1, verbose=True, sleep_time=0.02):
    nExecuted = 0
    nThreads = len(Threads)
    N_Prompt = min([100, int(nThreads / 100)])
    if N_Prompt == 0:
        N_Prompt = int(nThreads / 10) if int(nThreads / 10) > 0 else 1
    while nExecuted != nThreads:
        if nExecuted == MaxExec:
            break
        while getRunningThreads(Threads) < MaxCurrent and nThreads != nExecuted:
            Threads[nExecuted].start()
            nExecuted += 1
            sleep(sleep_time)
            if nExecuted == MaxExec:
                break
            if verbose and nExecuted % N_Prompt == 0:
                logging.info(f"Executed {nExecuted - getRunningThreads(Threads)} out of {nThreads} threads")
        waitCounter = 0
        while getRunningThreads(Threads) >= MaxCurrent:
            if verbose:
                waitCounter += 1
            if waitCounter == 5000:
                logging.info(f"At the moment {getRunningThreads(Threads)} threads are active. Executed {nExecuted - getRunningThreads(Threads)} out of {len(Threads)} threads")
                waitCounter = 0
            sleep(sleep_time)
    waitCounter = 0
    while getRunningThreads(Threads) > 0:
        if waitCounter == 5000:
            logging.info("Wait until the last %d threads are going to finish ", getRunningThreads(Threads))
            waitCounter = 0
        sleep(0.01)
        if verbose:
            waitCounter += 1




def executeCommands(ListOfCmds, MaxCurrent=4, MaxExec=-1, skipExec=0, verbose=True, sleep_time=0.01):
    Threads = []
    logging.info("executeCommands() - Execute the follow commands:{cmds}".format(cmds = "\n **** ".join([""]+ListOfCmds)))
    for Cmd in ListOfCmds[skipExec:]:
        Threads.append(CmdLineThread(Cmd))
    executeThreads(Threads=Threads, MaxCurrent=MaxCurrent, MaxExec=MaxExec, verbose=verbose, sleep_time=sleep_time)
    return len([0 for th in Threads  if th.isSuccess()]) == len(Threads)

def recursiveLS(directory: str, data_types=[]):
    n_data_types = len(data_types)
    if not isdir(directory):
        logging.warning(f"Not a directory {directory}",)
        return []
    LS = []
    for item in listdir(directory):
        full_path = f"{directory}/{item}"
        full_path = full_path.replace("//", "/")
        if isdir(full_path): LS += RecursiveLS(directory = full_path, data_types = data_types)
        if n_data_types == 0 or len([0 for d in data_types if item.endswith(f".{d}")]) > 0:
            LS += [full_path]
    return LS

if __name__ == "__main__":

    listOfCmds = []
    for db_file in sorted(recursiveLS("data_records", ["json"])):
        dev_name = db_file[db_file.rfind("/")+ 1 : db_file.rfind(".")]
        listOfCmds+=[f"python read_sensor.py --downloadOnly {dev_name}"]
    
    if not executeCommands(ListOfCmds = listOfCmds, sleep_time=15):
        logging.error("Encountered execution failure")
        exit(1)

    logging.info("Successful update")
    # logging.info("DIE CASSY")