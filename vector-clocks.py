from mpi4py import MPI
from datetime import datetime

# MPI World Setup (Lafayette 2021) (Dalcin 2020).
comm = MPI.COMM_WORLD
iproc = comm.Get_rank()
nproc = comm.Get_size()

def main():
    if iproc == 0:
        print("Root process @ {0}".format(str(datetime.now().strftime("%H:%M:%S.%f"))))
    else:
        print("Process {0} @ {1}".format(iproc, datetime.now().strftime("%H:%M:%S.%f")))

main()

'''
Refs
https://stackoverflow.com/questions/7588511/format-a-datetime-into-a-string-with-milliseconds 13th March
'''