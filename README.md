# COMP90020 - Distributed Algorithms - Team Double-J

This repository holds the source files of the project of Team Double-J (James Sammut and Joel Kenna) for COMP90020: Distributed Algorithms - for Semetser 1, 2024.

The main topic that the team has picked for investigation is Logical Time - and in particular, the implementation of **Dynamic Vector Clocks**. Initially - the choice of **Matrix Clocks** was elected on the team's first choice of algorithm to implemented; however the team opted for the former based on the real-world application of a multi-tenant chat application which primarily orients around broadcasting messages between peers - and additionally (most importantly), the dynamic nature of Dynamic Vector Clocks not needing to know how many peers are in the system initially. Furthermore, the _space_ that is required when storing Matrix Clocks far outweighs that of Dynamic Vector Clocks - which is better suited for this need.

The repository consists of two main directories - `phase1_mpi` and `phase2_sockets`. The first phase built upon the base implementation of the algorithm within Python that was then referenced and implemented in the second. Each phase is described below - the design, approach and invocation of the algorithm within each.

## Phase 1 - `phase1_mpi`

### Approach

The first phase of this project is implementing the Dynamic Vector Clock (DVC) Algorithm using **Message Passing Interface** - or MPI for short. 

This is achieved around the _known_ input of a distributed system's processes's and events; where said events are sent and received between these processes. Both Dynamic Vector Clock (`dynamic_vector_clocks.py`) and Matrix Clock (MC) (`/matrix_clock.py`) implementations have been developed in this phase - the logic for checking for causal delivery in each slightly different, but applied in a similar way; shared functionality exists in the `/shared` directory.

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

The process of Phase 1 and both these implementations are as follows:
1. Either `dynamic_vc.sh` or `matrix_clock.sh` are called from within their respective directories with Phase 1's invocation file to utilise. For example, `./phase1_invoke.sh -f examples/dynamic_vector_clocks/b1_3_node_simple_valid.txt -a dvc`: requiring `-f <file>` (flag and value) `-a <algorithm>` (flag and value); this example running the DVC implementation for an invalid/causal queueing scenario using 4 nodes. The shell script will calculate how much processes are needed to run the MPI program initially, and execute the `mpiexec` command dynamically for the specific implementation pased in.
2. The main algorithm is invoked; Process `0` is responsible for splitting the input line for each process (`1` to `N`) - which is sent at the start of the program.
3. After receiving the event list from Process `0` in Step 2: the main `process_loop` is executed by process `N` corresponding to the input row - and each event is determined and actioned upon. Each process holds onto a local clock, message/hold-back queue and floating-point number to add with message deliveries. On the latter - whenever a process is to send a broadcast/unicast message, it will generate a random floating-point number to add for corresponding receives and eventual deliveries.
4. Messages are thus sent and received - but **not** delivered unless the specific causal deliverability condition is met for either algorithm. Both algorithms implement a similar check on the incoming messages' clock. If both of these conditions are met, the message is delivered and the message's number is added to the process's number. Otherwise it is enqueued in a message/hold back queue:
    - The sender's value at its index in the message clock needs to be **exactly greater than 1** comparative to the value of its' value in the process's local clock.
    - Every other value in the message clock that is not of the sender is **less than or equal** to the receiving process's local clock value.
5. No matter on deliverability, both algorithms invoke checking the message queue on attempted message delivery after receiving a message. Until there are no messages in the queue (will exit if none were added on first pass), the process's local vector clock is checked against each message enqueued. If the message can be enqueued, the clocks are updated, the process's number is added with the message's number - and the loop starts again (this ensures re-checks are done on all messages when one is delivered for subsequent deliveries).
6. The `process_loop` is continually invoked until all events received in 2. are exhausted, and the process stops.

### Invocation

Invocating either algorithms' implementation is achieved by running the shell script that is provided within Phase 1's root directory - `phase1_invoke.sh`. This script expects two flag and valies `-f <file>` - the example input file you'd like to run the implementation against - and `-a <dvc|matrix>` - either `dvc` or `matrix` to invoke each algorithm's implementation respectfully. The script will calculate the number of processes needed based on the file given and will run `mpiexec` dynamically based on your input.

For example - running `b8_4_node_invalid.txt` for DVCs after cloning the repository:

```
git clone git@gitlab.eng.unimelb.edu.au:jsammut/comp90020-double-j.git
cd comp90020-double-j/phase1_mpi/
./phase1_invoke.sh -f examples/dynamic_vector_clocks/b8_4_node_invalid.txt -a dvc
```

The output of the script is the MPI logs and the event timeline for each process. Note the ordering may not always be in order due to the nature of the parallel nature of MPI programs!

```
|----- Process 4: ['r1', 'r3', 'r2'] -----|
-----------------------
Event #0 -> r1: (0)
-----------------------
Process 4 received number 9.444 from Process 1 @ 16:27:16.548878
This message satisfied the DVC causal deliverability condition. Delivering.
9.444 (message number) + 0 (current sum). Process 4's sum = 9.444

Checking messages in the message/hold back queue for deliverability
No messages are in the message/hold back queue
DVC after r1:	[[1, 1], [2, 0], [3, 0], [4, 0]]
Number Sum:	 9.444
-----------------------
Event #1 -> r3: (9.444)
-----------------------
Process 4 received number 4.01 from Process 3 @ 16:27:16.549633
This message did not satisfy the DVC causal deliverability condition. Will be enqueued.

Checking messages in the message/hold back queue for deliverability
This was the message that was just added - skipping it on first pass
Exhausted all messages. Breaking
DVC after r3:	[[1, 1], [2, 0], [3, 0], [4, 0]]
Number Sum:	 9.444
-----------------------
Event #2 -> r2: (9.444)
-----------------------
Process 4 received number 6.632 from Process 2 @ 16:27:16.549716
This message satisfied the DVC causal deliverability condition. Delivering.
6.632 (message number) + 9.444 (current sum). Process 4's sum = 16.076

Checking messages in the message/hold back queue for deliverability
This queued message satisfied the causal deliverability condition. Will be delivered.
4.01 (message number) + 16.076 (current sum). Process 4's sum = 20.086
No messages are in the message/hold back queue
DVC after r2:	[[1, 1], [2, 1], [3, 1], [4, 0]]
Number Sum:	 20.086
```

## Phase 2 - `phase2_sockets`

### Approach

The second phase of this project takes forward the Dynamic Vector Clock Algorithm using the MPI implementation from Phase 1 as the basis, now using **sockets** as the main means of integration in Python - with a Graphical User Interface (GUI) utilising [Kivy](https://kivy.org/) - a cross platform and open source library for developing Python applications with visual elements (including components such as windows, images, audio, buttons and more).

Unlinke the known quantity and expected send/receives of processes in the first phase, the invocation of this approach is more true to life and expected in multi-tenant chat applications that are seen in many social media sites and applications of the modern technological society. It's part and parcel that users expect to join in (and conversely drop away) from a chat room; the former with an unbound ceiling of "peers" - whether its just a 1:1 conversation, or a room with more than 1000 people in it. Expectations of ordered messaging between all involved is key to a functional experience achieving the underlying causal delivery guarantee of messages.

True to causality - if there's a network partition at one of the peers - or perhaps that peer itself is under heavy load; it _may_ receive messages out-of-order akin to the examples shown in Phase 1. The DVC algorithm integrated with this part of our project will ensure that messages queued are sent in causal ordering. 

### Implementation

The process of Phase 2's implementations is based as follows:
1. Based on the local `dotenv` file (`.env`) within the `/phase2_sockets` directory - peers can elect to join the network based two main scenarios. The options are where peers elect to chat _without_ a central peer registry server handling automatic peer registration/deregistration within the network, or _with_ the server enabled (**started previously**) - which will automatically connect pre-registered peers together. This is set through the `ENABLE_PEER_SERVER` variable as above. <br/> Other environment variables are exposed in the `.env` file; namely the following:
    - `CLIENT_WORKER_THREADS`: the number of `networkWorder` threads a client will utilise.
    - `PROTOCOL_PORT`: The port number that a client/peer will utilise for connecting to others.
    - `REGISTRY_PROTOCOL_PORT`: The peer registry server's port number it will utilise.
    - `ENABLE_PEER_SERVER`: Whether to enable the peer registry server to manage peer registration.
    - `ENABLE_NETWORK_DELAY`: Whether to enable simulated networking delay.
    - `MOCK_NETWORK_DELAY_MIN`: The minimum network delay length in ms. (100 mininum)
    - `MAX_NETWORK_DELAY_MIN`: The maximum network delay length in ms. (2500 maximum)
2.  - When `ENABLE_PEER_SERVER` is set as `0`: peers will need to specify each peer they would like to connect with on joining the network. Once they're done, they'll need to specifying `f` or `finished` to connect to the network. 
    - When `ENABLE_PEER_SERVER` is set as `1`: peers will connect with the central server that has been started at a specific IP address. The connecting peer will try to fetch the peers from the server with a `RegistryMessageType.GET_PEERS`, which the server will reply with a `RegistryMessageType.PEER_RESPONSE` with a peer list. If they're the first peer connected, they'll register themselves to the server's peer list with a `RegistryMessageType.REGISTER_PEER` message to the server and then register themselves to the server via the internal `registerAndCompleteInitialisation` function. Otherwise - the connecting peer will broadcast a `MessageType.HELLO` to all the known peers. Each active peer thus returns a `MessageType.HELLO_RESPONSE` back to the registering peer. The connecting process then join messages captured prior to initialisation with any undelivered messages from the other processes - and then completes its registration by `registerAndCompleteInitialisation`.
3. In the registration and peer startup process above - each peer constructs a `networkWorker` (for handling connection queue and incoming messages from other peers), a `sendWorker` (for handling outgoing messages) and a `acceptWorker` (for accepting connections from other peers).
4. From both cases explained in #2 - peers will now have a Kivy window open for broadcasting messages to one another. Constructing a message in the presented input box will boradcast messages out via the `sendWorker` - where from Phase #1; a vector clock is affixed to the message for checking deliverability. Peers ingest this message from their own `networkWorker` - where upon receiving a regular message that is not of the typed setup as explained above - will be checked for deliverability as Phase 1. If a message is able to be delivered, it is - otherwise it's put on the peers' `processMessageQueue` where they'll be attempted to be delivered upon another message arriving.
5. Peers can disconnect/connect dynamically at this point: the registration process in #1 and #2 yields - as expected from realistic P2P chat applications t qhat are used extensively today.

### Invocation

As explained in [the implementation phase](#implementation-1), the P2P message application developed for our real-world example of Dynamic Vector Clocks works on the premise that _multiple_ peers will be joining the system at any given time, whether thats utilising a central peer registry server; or without. Both cases are showcased below: 

#### Without a Peer Registration Server

Within a new terminal - clone the codebase (if not already done from phase 1) and change the working directory to `/phase2_sockets`. Ensure that in the `.env` file, `ENABLE_PEER_SERVER` is set to `0` (this is the default value)/

From there - you'll need to invoke a new client/peer via `client.py` with a specific IP address that it should listen on. For example - below is starting up a client/peer with `127.0.0.1` as its listining IP:

```
git clone git@gitlab.eng.unimelb.edu.au:jsammut/comp90020-double-j.git
cd comp90020-double-j/phase1_mpi/
python3 client.py 127.0.0.1
```

The running client/peer will then start its respective workers; and then loop for other client/peer IPs/hostnames to connect to. Once completed with the respective client/peers - enter `f` or `finished`:

```
╰─ python3 client.py 127.0.0.1
[INFO   ] [Logger      ] Record log in /Users/juma/.kivy/logs/kivy_24-05-05_27.txt
[INFO   ] [Kivy        ] v2.3.0
[INFO   ] [Kivy        ] Installed at "/usr/local/lib/python3.12/site-packages/kivy/__init__.py"
[INFO   ] [Python      ] v3.12.3 (main, Apr  9 2024, 08:09:14) [Clang 15.0.0 (clang-1500.3.9.4)]
[INFO   ] [Python      ] Interpreter at "/usr/local/opt/python@3.12/bin/python3.12"
[INFO   ] [Logger      ] Purge log fired. Processing...
[INFO   ] [Logger      ] Purge finished!
[INFO   ] [Factory     ] 195 symbols loaded
[INFO   ] [Image       ] Providers: img_tex, img_imageio, img_dds, img_sdl2 (img_pil, img_ffpyplayer ignored)
[INFO   ] [Text        ] Provider: sdl2
[INFO   ] [Window      ] Provider: sdl2
[INFO   ] [GL          ] Using the "OpenGL ES 2" graphics system
[INFO   ] [GL          ] Backend used <sdl2>
[INFO   ] [GL          ] OpenGL version <b'2.1 ATI-5.5.17'>
[INFO   ] [GL          ] OpenGL vendor <b'ATI Technologies Inc.'>
[INFO   ] [GL          ] OpenGL renderer <b'AMD Radeon Pro 560X OpenGL Engine'>
[INFO   ] [GL          ] OpenGL parsed version: 2, 1
[INFO   ] [GL          ] Shading version <b'1.20'>
[INFO   ] [GL          ] Texture max size <16384>
[INFO   ] [GL          ] Texture max units <16>
[INFO   ] [Window      ] auto add sdl2 input provider
[INFO   ] [Window      ] virtual keyboard not allowed, single mode, not docked
Combined env and argv config: {'CLIENT_WORKER_THREADS': '1', 'PROTOCOL_PORT': '9876', 'REGISTRY_PROTOCOL_PORT': '9877', 'ENABLE_PEER_SERVER': '0', 'ENABLE_NETWORK_DELAY': '1', 'MOCK_NETWORK_DELAY_MIN': '100', 'MOCK_NETWORK_DELAY_MAX': '2500', 'CLIENT_LISTEN_IP': '127.0.0.1'}
Enter peer IPs/hostnames [enter 'finished' or 'f' to continue]
Enter hostname: 127.0.0.2
Added peer at 127.0.0.2
Enter hostname: f
Client listening at 127.0.0.1 on port 9876
Process ID is 4ef09c8a-f962-48f4-a161-72f748201046
[a0] Started
[w0] Started
[s0] Started
Error connecting to adr: <class 'OSError'>
Failed to broadcast message to any of our peers. We may be disconnected from the network...
Failed to send HELLO message to any of our peers. Registering and starting with an empty clock
connecting to the network, please wait...
[INFO   ] [Base        ] Start application main loop
[INFO   ] [GL          ] NPOT texture support is available
```

Other clients/peers that wish to connect to the network will need to be connected in a similar fashion - and **with a different IP/hostname**. 

Upon a client/peer starting - a local Kivy window will appear where they can enter in messages to other clients/peers. Sending/receiving messages works as expected - clients/peers that join the network will be included when they join - and can drop off when they so desire. Vector clocks are incremented on message send via a client/peer's `sendWorker` - and the receiving client/peers' `networkWorker` handles deliverability:

![P2P Messaging App - Without a central peer registry server](/phase2_sockets/images/phase2-no-server.png)

#### With a Peer Registration Server

Within a new terminal - clone the codebase (if not already done from phase 1) and change the working directory to `/phase2_sockets`. Ensure that in the `.env` file, `ENABLE_PEER_SERVER` is set to `1` to enable the central peer registry server. You might want to also change its port via `REGISTRY_PROTOCOL_PORT` in `.env`

From there - you'll need to start the server **first** by `server.py` with a specific IP address that it should should listen on. For example - below is starting up the server with `127.0.0.1` as its listining IP:

```
git clone git@gitlab.eng.unimelb.edu.au:jsammut/comp90020-double-j.git
cd comp90020-double-j/phase1_mpi/
python3 server.py 127.0.0.1
```

The server will then start up and start listening on the respective IP and port specified:

```
╰─ python3 server.py 127.0.0.1
Server listening at 127.0.0.1 on port 9877
```

From here - similar to the case where [clients/peers connect without a central peer registry server](#without-a-peer-registration-server), new clients/peers will need to be started and thus will register with the server and join the network. Unlike the above though, `client.py` now expects **two** arguments: the first as the client/peer's IP, and the second as the server's IP. For example - starting a client/peer with address `127.0.0.2` connecting to the central peer registry server at `127.0.0.1`: 

```
python3 client.py 127.0.0.2 127.0.0.1
```

Running the above will map this client/peer's IP: and based on if this is the first peer (or not) as explored in the [invocation](#invocation-1) section will either register with the server and await new client/peer connections - or say `hello` to all other client/peers (message merging) and then register itself with the server (and thus network). There is **no need** to specify IPs for other client/peers in this scenario - as this is the job of the server to direct to client/peers that join in at any time:

```
╰─ python3 client.py 127.0.0.2 127.0.0.1
[INFO   ] [Logger      ] Record log in /Users/juma/.kivy/logs/kivy_24-05-05_32.txt
[INFO   ] [Kivy        ] v2.3.0
[INFO   ] [Kivy        ] Installed at "/usr/local/lib/python3.12/site-packages/kivy/__init__.py"
[INFO   ] [Python      ] v3.12.3 (main, Apr  9 2024, 08:09:14) [Clang 15.0.0 (clang-1500.3.9.4)]
[INFO   ] [Python      ] Interpreter at "/usr/local/opt/python@3.12/bin/python3.12"
[INFO   ] [Logger      ] Purge log fired. Processing...
[INFO   ] [Logger      ] Purge finished!
[INFO   ] [Factory     ] 195 symbols loaded
[INFO   ] [Image       ] Providers: img_tex, img_imageio, img_dds, img_sdl2 (img_pil, img_ffpyplayer ignored)
[INFO   ] [Text        ] Provider: sdl2
[INFO   ] [Window      ] Provider: sdl2
[INFO   ] [GL          ] Using the "OpenGL ES 2" graphics system
[INFO   ] [GL          ] Backend used <sdl2>
[INFO   ] [GL          ] OpenGL version <b'2.1 ATI-5.5.17'>
[INFO   ] [GL          ] OpenGL vendor <b'ATI Technologies Inc.'>
[INFO   ] [GL          ] OpenGL renderer <b'AMD Radeon Pro 560X OpenGL Engine'>
[INFO   ] [GL          ] OpenGL parsed version: 2, 1
[INFO   ] [GL          ] Shading version <b'1.20'>
[INFO   ] [GL          ] Texture max size <16384>
[INFO   ] [GL          ] Texture max units <16>
[INFO   ] [Window      ] auto add sdl2 input provider
[INFO   ] [Window      ] virtual keyboard not allowed, single mode, not docked
Combined env and argv config: {'CLIENT_WORKER_THREADS': '1', 'PROTOCOL_PORT': '9876', 'REGISTRY_PROTOCOL_PORT': '9877', 'ENABLE_PEER_SERVER': '1', 'ENABLE_NETWORK_DELAY': '1', 'MOCK_NETWORK_DELAY_MIN': '100', 'MOCK_NETWORK_DELAY_MAX': '2500', 'CLIENT_LISTEN_IP': '127.0.0.2', 'PEER_REGISTRY_IP': '127.0.0.1'}
Retrieving peers from registry server...
Received peers from registry:  []
Registry had no peers, registering self
Client listening at 127.0.0.2 on port 9876
Process ID is 619bef31-ccfe-4fe4-9cde-58c06edacecf
[a0] Started
[w0] Started
waiting for at least one other peer to establish connection...
[s0] Started
[INFO   ] [Base        ] Start application main loop
[INFO   ] [GL          ] NPOT texture support is available
```

Just like the previous implementation without the central peer registry server -  a local Kivy window will appear where it can enter in messages to other registered peers. Sending/receiving messages works as expected - client/peers that join the network will be included when they join - and can drop off when they so desire. Vector clocks are incremented on message send via a client/peer's `sendWorker` - and the receiving client/peers' `networkWorker` handles deliverability.

![P2P Messaging App - With a central peer registry server](/phase2_sockets/images/phase2-with-central-server.png)

## Presentation

Team Double-J's presentation presented on this project can be found in the `/presentation` directory.

## Bibliography
[1] N. Meghanathan. Module 6.2.3 Matrix Algorithm Causal Delivery of Messages. (Nov. 12, 2013). Accessed: Mar. 13, 2024. [Online video]. Available: https://www.youtube.com/watch?v=WgTx7BHWzts.<br/>
[2] T. Landes. "Dynamic Vector Clocks for Consistent Ordering of Events in Dynamic Distributed Applications." in International Conference on Parallel and Distributed Processing Techniques and Applications, Las Vegas, Nevada, USA, 2006, pp.1-7.<br/>
[3] L. Lafayette. (2021). The Spartan HPC System at the University of Melbourne [PDF]. Available: https://canvas.lms.unimelb.edu.au/courses/105440/files/7018506/download?download_frd=1.<br/>
[4] L. Dalcin. "Tutorial". MPI for Python. https://mpi4py.readthedocs.io/en/stable/tutorial.html (accessed Mar. 13, 2024).<br/>
[5] Jurudocs. "Format a datetime into a string with milliseconds". Stack Overflow. https://stackoverflow.com/questions/7588511/format-a-datetime-into-a-string-with-milliseconds (accessed Mar. 13, 2024).<br/>
[6] M. Toboggan. "How to get a random number between a float range?". Stack Overflow. https://stackoverflow.com/questions/6088077/how-to-get-a-random-number-between-a-float-range (accessed Mar. 15, 2024).<br/>
[7] NumPy Developers. "numpy.zeros". NumPy. https://numpy.org/doc/stable/reference/generated/numpy.zeros.html (accessed Mar. 16, 2024).<br/>
[8] New York University. "Non-blocking Communication". GitHub Pages. https://nyu-cds.github.io/python-mpi/03-nonblocking/ (accessed Mar. 24, 2024).<br/>
[9] L. Dalcin. "mpi4py.MPI.Message". MPI for Python. https://mpi4py.readthedocs.io/en/stable/reference/mpi4py.MPI.Message.html (accessed Mar. 30, 2024).<br/>
[10] W3Schools. "Python String split() Method". W3Schools. https://www.w3schools.com/python/ref_string_split.asp (accessed Mar. 30, 2024).<br/>
[11] C. Kolade. "Python Switch Statement - Switch Case Example". freeCodeCamp. https://www.freecodecamp.org/news/python-switch-statement-switch-case-example/ (accessed Mar. 30, 2024).<br/>
[12] spiderman. "How to find string that start with one letter then numbers". FME Community. https://community.safe.com/general-10/how-to-find-string-that-start-with-one-letter-then-numbers-23880?tid=23880&fid=10 (accessed Mar. 30, 2024).<br/>
[13] TutorialsTeacher. "Grouping in Regex". TutorialsTeacher. https://www.tutorialsteacher.com/regex/grouping (accessed Mar. 30, 2024).<br/>
[14] hoju. "Extract part of a regex match". Stack Overflow. https://stackoverflow.com/questions/1327369/extract-part-of-a-regex-match (accessed Mar. 30, 2024).<br/>
[15] M. Breuss. "How to Check if a Python String Contains a Substring". Real Python. https://realpython.com/python-string-contains-substring/ (accessed Mar. 30, 2024).<br/>
[16] Python Principles. "How to convert a string to int in Python". Python Principles. https://pythonprinciples.com/blog/python-convert-string-to-int/ (accessed Mar. 30, 2024).<br/>
[17] TransparenTech LLC. "Generate a UUID in Python". UUID Generator. https://www.uuidgenerator.net/dev-corner/python/ (accessed Mar. 30, 2024).<br/>
[18] W3Schools. "Python - List Comprehension". W3Schools. https://www.w3schools.com/python/python_lists_comprehension.asp (accessed Mar. 30, 2024).<br/>
[19] greye. "Get loop count inside a for-loop [duplicate]". Stack Overflow. https://stackoverflow.com/questions/3162271/get-loop-count-inside-a-for-loop (accessed Mar. 30, 2024).<br/>
[20] G. Ramuglia. "Using Bash to Count Lines in a File: A File Handling Tutorial". I/O Flood. https://ioflood.com/blog/bash-count-lines/ (accessed Mar. 30, 2024).<br/>
[21] H. Sundaray. "How to Use Bash Getopts With Examples". KodeKloud. https://kodekloud.com/blog/bash-getopts/ (accessed Mar. 30, 2024).<br/>
[22] Linuxize. "Bash Functions". Linuxize. https://linuxize.com/post/bash-functions/ (accessed Mar. 30, 2024).<br/>
[23] Nick. "How can I add numbers in a Bash script?". Stack Overflow. https://stackoverflow.com/questions/6348902/how-can-i-add-numbers-in-a-bash-script (accessed Mar. 30, 2024).<br/>
[24] GeeksForGeeks. "Command Line Arguments in Python". GeeksForGeeks. https://www.geeksforgeeks.org/command-line-arguments-in-python/ (accessed Mar. 30, 2024).<br/>
[25] V. Hule. "Generate Random Float numbers in Python using random() and Uniform()". PYnative. https://pynative.com/python-get-random-float-numbers/ (accessed Apr. 1, 2024).<br/>
[26] bhaskarc. "Iterating over a 2 dimensional python list [duplicate]". Stack Overflow. https://stackoverflow.com/questions/16548668/iterating-over-a-2-dimensional-python-list (accessed Apr. 1, 2024).<br/>
[27] note.nkmk.me. "How to return multiple values from a function in Python". note.nkmk.me. https://note.nkmk.me/en/python-function-return-multiple-values/ (accessed Apr. 2, 2024).<br/>
[28] A. Luiz. "How do you extract a column from a multi-dimensional array?". Stack Overflow. https://stackoverflow.com/questions/903853/how-do-you-extract-a-column-from-a-multi-dimensional-array (accessed Apr. 2, 2024).<br/>
[29] W3Schools. "Python Remove Array Item". W3Schools. https://www.w3schools.com/python/gloss_python_array_remove.asp (accessed Apr. 2, 2024).<br/>
[30] nobody. "Python regular expressions return true/false". Stack Overflow. https://stackoverflow.com/questions/6576962/python-regular-expressions-return-true-false (accessed May. 6, 2024).<br/>
[31] A. Jalli. "Python Switch Case -- Comprehensive Guide". Medium. https://medium.com/@artturi-jalli/python-switch-case-9cd0014759e4 (accessed May. 4, 2024).<br/>
[32] Linuxize. "Bash if..else Statement". Linuxize. https://stackoverflow.com/questions/67428689/how-to-pass-multiple-flag-and-multiple-arguments-in-getopts-in-shell-script (accessed May. 4, 2024).<br/>
[33] Kivy. "Kivy: The Open Source Python App Development Framework.". Kivy. https://kivy.org/ (accessed May. 4, 2024).<br/>
[34] R. Strahl. "Getting Images into Markdown Documents and Weblog Posts with Markdown Monster". Medium. https://medium.com/markdown-monster-blog/getting-images-into-markdown-documents-and-weblog-posts-with-markdown-monster-9ec6f353d8ec (accessed May. 5, 2024).<br/>