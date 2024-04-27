def increment_vector_clock(process_vc, processId):
    for clock in process_vc:
        if clock[0] == processId:  # Obtain this process's clock within the vector clock (first index)
            clock[1] += 1           # Increment by 1
            break                   # Exit the loop
    return process_vc