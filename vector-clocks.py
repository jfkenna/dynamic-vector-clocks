from mpi4py import MPI
from datetime import datetime
import random
from time import sleep
# MPI World Setup (Lafayette 2021) (Dalcin 2020).
comm = MPI.COMM_WORLD
iproc = comm.Get_rank()
nproc = comm.Get_size()

def main():
    if iproc == 0:
        print("Root process @ {0}".format(str(datetime.now().strftime("%H:%M:%S.%f"))))
    else:
        sleeper = random.uniform(0, 10)
        print("Process {0} decided at {1} to sleep for {2} seconds".format(
            iproc, 
            datetime.now().strftime("%H:%M:%S.%f"), 
            sleeper
        ))
        sleep(sleeper)
        print("Process {0} @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))

main()

'''
Refs
https://stackoverflow.com/questions/7588511/format-a-datetime-into-a-string-with-milliseconds 13th March
https://stackoverflow.com/questions/6088077/how-to-get-a-random-number-between-a-float-range 15th March
'''