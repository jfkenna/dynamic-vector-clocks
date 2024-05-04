# COMP90020 - Distributed Algorithms - Team Double-J

This repository holds the source files of the project of Team Double-J (James Sammut and Joel Kenna) for COMP90020: Distributed Algorithms - for Semetser 1, 2024.

The main topic that the team has picked for investigation is Logical Time - and in particular, the implementation of **Dynamic Vector Clocks**. Initially - the choice of **Matrix Clocks** was elected on the team's first choice of algorithm to implemented; however the team opted for the former based on the real-world application of a multi-tenant chat application which primarily orients around broadcasting messages between peers - and additionally (most importantly), the dynamic nature of Dynamic Vector Clocks not needing to know how many peers are in the system initially. Furthermore, the _space_ that is required when storing Matrix Clocks far outweighs that of Dynamic Vector Clocks - which is better suited for this need.

The repository consists of two main directories - `phase1_mpi` and `phase2_sockets`. The first phase built upon the base implementation of the algorithm within Python that was then referenced and implemented in the second. Each phase is described below - the design, approach and invocation of the algorithm within each.

## Phase 1 - `phase1_mpi`

### Approach

The first phase of this project is implementing the Dynamic Vector Clock Algorithm using **Message Passing Interface** - or MPI for short. 

This is achieved around the _known_ input of a distributed system's processes's and events; where said events are sent and received between these processes. Both Dynamic Vector Clock (`dynamic_vector_clocks.py`) and Matrix Clock (`/matrix_clock.py`) implementations have been developed in this phase - the logic for checking for causal delivery in each slightly different, but applied in a similar way; shared functionality exists in the `/shared` directory.

Example input files live in this phases' `/examples` directory - this containing subdirectories for each `/dynamic_vector_clocks` and `/matrix_clocks` with specific examples. Unicast/broadcast examples are inclusive for both - and are line-by-line seperated with the events that happen at each process. For example, the below file denotes a 3 process system where:
- Process 1 **broadcasts** message 1, and **receives** message 2 (from Process 2).
- Process 2 **receives** message 1 (from Process 1), and **broadcasts** message 2.
- Process 3 **receives** message 1 (from Process 1), then **receives** message 2 (from Process 2).

```
b1, r2
r1, b2
r1, r2
```

In these examples, broadcast messages are denoted by `b<integer>`, unicast messages by `s<integer>`, receive events by `r<integer>` and internal events with an alphabetical character. Important to note is that for send event targeting on the receiving process end, the same integer must be used (i.e `s1` for the sender, `r1` for the receiver).

### Implementation

The process of these implementations are as follows:
1. Either `dynamic_vc.sh` or `matrix_clock.sh` are called from within their respective directories with Phase 1's invocation file to utilise. For example, `./phase1_invoke.sh -f examples/dynamic_vector_clocks/broadcast3.txt -a dvc` to run Example 5 (`-f` flag and value) for Dynamic Vector clocks (`-a` flag and value) with 4 nodes. The shell script will calculate how much processes are needed to run the MPI program initially, and execute the `mpiexec` command dynamically for the specific implementation pased in.
2. The main algorithm is invoked; Process `0` is responsible for splitting the input line for each process (`1` to `N`) - which is sent at the start of the program.
3. After receiving the event list from Process `0` in Step 2: the main `process_loop` is executed by process `N` corresponding to the input row - and each event is determined and actioned upon. Each process holds onto a local clock, message/hold-back queue and floating-point number to add with message deliveries. On the latter - whenever a process is to send a broadcast/unicast message, it will generate a random floating-point number to add for corresponding receives and eventual deliveries.
4. Messages are thus sent and received - but **not** delivered unless the specific causal deliverability condition is met for either algorithm. Both algorithms implement a similar check on the incoming messages' clock. If both of these conditions are met, the message is delivered and the message's number is added to the process's number. Otherwise it is enqueued in a message/hold back queue:
    - The sender's value at its index in the message clock needs to be **exactly greater than 1** comparative to the value of its' value in the process's local clock.
    - Every other value in the message clock that is not of the sender is **less than or equal** to the receiving process's local clock value.
5. No matter on deliverability, both algorithms invoke checking the message queue on attempted message delivery after receiving a message. Until there are no messages in the queue (will exit if none were added on first pass), the process's local vector clock is checked against each message enqueued. If the message can be enqueued, the clocks are updated, the process's number is added with the message's number - and the loop starts again (this ensures re-checks are done on all messages when one is delivered for subsequent deliveries).
6. The `process_loop` is continually invoked until all events received in 2. are exhausted, and the process stops.

### Invocation

Invocating either algorithms' implementation is achieved by running the shell script that is provided within Phase 1's root directory - `phase1_invoke.sh`. This script expects two flag and valies `-f <file>` - the example input file you'd like to run the implementation against - and `-a <dvc|matrix>` - either `dvc` or `matrix` to invoke each algorithm's implementation respectfully. The script will calculate the number of processes needed based on the file given and will run `mpiexec` dynamically based on your input.

For example - running `broadcast1.txt` for Dynamic Vector Clocks after cloning the repository:

```
git clone git@gitlab.eng.unimelb.edu.au:jsammut/comp90020-double-j.git
cd comp90020-double-j/phase1_mpi/<implementation>
./phase1_invoke.sh -f examples/dynamic_vector_clocks/broadcast1.txt -a dvc
```

The output of the script is the MPI logs and the event timeline for each process. Note the ordering may not always be in order due to the nature of the parallel nature of MPI programs!

```
|----- Process 2: ['r1'] -----|
-----------------------
Event #0 -> r1: (0)
-----------------------
Process 2 received number 1.934 from Process 1 @ 10:21:05.536975
This message satisfied the DVC causal deliverability condition. Delivering.
1.934 (message number) + 0 (current sum). Process 2's sum = 1.934

Checking messages in the message/hold back queue for deliverability
No messages are in the message/hold back queue
DVC after r1:	[[1, 1], [2, 0], [3, 0]]
Number Sum:	 1.934
```

## Phase 2 - `phase2_sockets`

### Approach

The second phase of this project takes forward the Dynamic Vector Clock Algorithm using the MPI implementation from Phase 1 as heavy inspiration - with **sockets** as the basis of integration in Python within a OS's terminal.

Unlinke the known quantity and expected send/receives of processes in the first phase, the invocation of this approach is more true to life and expected in multi-tenant chat applications that are seen in many social media sites and phone/tablet apps of the modern age. It's part and parcel that users expect to join in on a chat room with an unbound number of "peers" - whether its just a 1:1 conversation, or a room with more than 1000 people in it - the expectation of ordered messaging between all involved is key to a functional experience achieving the underlying causal delivery guarantee of messages.

### Implementation

_To be filled once we know the concrete implementation!_

### Invocation

This phases' implementation of Dynamic Vector Clocks works on the premise that _multiple_ peers will be joining the system at any given time, and thus - multiple terminal instances will be required.

Within a new terminal - clone the codebase (if not already done from phase 1) and change the working directory to `/phase2_sockets`. Within this directory, running `client.py` with a system argument of the client's IP address will be required.

In the below example, after cloning the repository - we map the first client with the IP address of `127.0.0.1` as its listening IP: 

```
git clone git@gitlab.eng.unimelb.edu.au:jsammut/comp90020-double-j.git # If not cloned already
cd comp90020-double-j/phase2_sockets
python3 client.py 127.0.0.1
```

Running the above will map this peer's IP: and will then further prompt the user to enter the _other_ peer IPs that it should connect to. Once other peer IPs have been added, either type `finished` or `f` for the client to register into the system and start polling/awaiting broadcast messages between connected peers.

```
Combined env and argv config: {'CLIENT_WORKER_THREADS': '1', 'PROTOCOL_PORT': '9876', 'CLIENT_LISTEN_IP': '127.0.0.1'}
Enter peer IPs/hostnames [enter 'finished' or 'f' to continue]
Enter hostname: 127.0.0.2
Added peer at 127.0.0.2
Enter hostname: f
Client listening at 127.0.0.1 on port 9876
Process ID is fc345072-7e51-49b8-b936-bdc1c9ce168e
[a0] Started
[w0] Started
[s0] Started
[UI0] Started
```

Of course - for the algorithm to fully function - more than just one peer needs to connect; thus in the above example - another peer process should be started with `127.0.0.2` as its listening IP and connect with the already started `127.0.0.1`. 

An example run of two peers communicating with each-other is show below. Every message that is sent between these peers is causing its own clock on the process to get icremented; and receives are being checked for deliverability as in phase 1. Alike phase 1 - if causality is not met; messages are enqueued and are delivered later upon another message receive event:

#### Peer 1

```
// python3 client.py 127.0.0.1
Combined env and argv config: {'CLIENT_WORKER_THREADS': '1', 'PROTOCOL_PORT': '9876', 'CLIENT_LISTEN_IP': '127.0.0.1'}
Enter peer IPs/hostnames [enter 'finished' or 'f' to continue]
Enter hostname: 127.0.0.2
Added peer at 127.0.0.2
Enter hostname: f
Client listening at 127.0.0.1 on port 9876
Process ID is fc345072-7e51-49b8-b936-bdc1c9ce168e
[a0] Started
[w0] Started
[s0] Started
[UI0] Started
Hello!
[9a583352-1dc9-4390-9f1d-496d49221004]: Hi - how are you?
I'm doing great - love this application from Team Double-J!
[9a583352-1dc9-4390-9f1d-496d49221004]: Agreed - every message we send is getting vector clock incremented and causal delivery checked, right?
Thats correct! :)
```

#### Peer 2

```
// python3 client.py 127.0.0.2 
Combined env and argv config: {'CLIENT_WORKER_THREADS': '1', 'PROTOCOL_PORT': '9876', 'CLIENT_LISTEN_IP': '127.0.0.2'}
Enter peer IPs/hostnames [enter 'finished' or 'f' to continue]
Enter hostname: 127.0.0.1
Added peer at 127.0.0.1
Enter hostname: f
Client listening at 127.0.0.2 on port 9876
Process ID is 9a583352-1dc9-4390-9f1d-496d49221004
[a0] Started
[w0] Started
[s0] Started
[UI0] Started
[fc345072-7e51-49b8-b936-bdc1c9ce168e]: Hello!
Hi - how are you?
[fc345072-7e51-49b8-b936-bdc1c9ce168e]: I'm doing great - love this application from Team Double-J!
Agreed - every message we send is getting vector clock incremented and causal delivery checked, right?
[fc345072-7e51-49b8-b936-bdc1c9ce168e]: Thats correct! :)
```