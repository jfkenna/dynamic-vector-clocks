#! /bin/bash

# Obtain number of processes from file
VALIDOPS=":f"

function invoke_mpi() {
    file_name=$1
    file_lines=$(cat $file_name | wc -l)
    procs=$(($file_lines+2))

    mpiexec -n $procs python3 matrix-clocks.py $file_name
}

while getopts ${VALIDOPS} option; do
  case ${option} in
    f)
      invoke_mpi $2
      ;;
    ?)
      echo "You passed an invalid option. Valid options are -f <filename>"
      exit 1
      ;;
  esac
done