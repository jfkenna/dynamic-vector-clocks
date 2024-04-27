# COMP90020 - Distributed Algorithms - Team Double-J

This repository holds the source files of the project of Team Double-J (James Sammut and Joel Kenna) for COMP90020: Distributed Algorithms - for Semetser 1, 2024.

The main topic that the team has picked for investigation is Logical Time - and in particular, the implementation of **Dynamic Vector Clocks**. Initially - the choice of **Matrix Clocks** was elected; however the team opted for implementing the former based on the real-world application of a multi-tenant chat application which primarily orients around broadcasting messages between peers - and additionally (most importantly), the dynamic nature of Dynamic Vector Clocks not needing to know how many peers are in the system initially.

The repository consists of two main directories - `phase1_mpi` and `phase2_sockets`. The first phase built upon the base implementation of the algorithm within Python that was then referenced and implemented in the second. Each phase is described below - the design, approach and invocation of the algorithm within each.

## Phase 1 - `phase1_mpi`

### Approach

The first phase of this project is implementing the Dynamic Vector Clock Algorithm using **Message Passing Interface** - or MPI for short. 

This is achieved around the _known_ input of a distributed system's processes's and events; where said events are sent and received between these processes. Both Dynamic Vector Clock and Matrix Clock implementations have been developed in this phase -  the logic for checking for causal delivery in each slightly different, but applied in a similar way.

### Implementation

The process of these implementations are as follows:
1. Either `dynamic_vc.sh` or `matrix_clock.sh` are called from within their respective repositories with a example input file to utilise (for example, `./dynamic_vc.sh -f examples/broadcast5.txt` to run Example 5 for Dynamic Vector clocks with 4 nodes). The shell script will calculate how much processes are needed to run the MPI program initially, and execute the `mpiexec` command dynamically.
2. The main algorithm is invoked; Process `0` is responsible for splitting the input line for each process (`1` to `N`) - which is sent at the start of the program.
3. After receiving the event list from Process `0` in Step 2: the main `process_loop` is executed by process `N` corresponding to the input row. Broadcast messages are denoted by `b<integer>`, unicast messages by `s<integer>`, receive events by `r<integer>` and internal events with an alphabetical character. Important to note is that for an event to send a message picked up by another, the same integer must be used (i.e `s1` for the sender, `r1` for the receiver). Each send event in this example generates a random floating point number to add for corresponding receive/deliveries.
4. Messages are thus sent and received - but **not** delivered unless the specific causal deliverability condition is met for either algorithm. Both algorithms implement a similar check on the incoming messages' clock. If both of these conditions are met, the message is delivered and the message's number is added to the process's number. Otherwise it is enqueued in a message/hold back queue:
    - The sender's value at its index in the message clock needs to be **exactly greater than 1** comparative to the value of its' value in the process's local clock.
    - Every other value in the message clock that is not of the sender is **less than or equal** to the receiving process's local clock value.
5. No matter on deliverability, both algorithms invoke checking the message queue on attempted message delivery after receiving a message. Until there are no messages in the queue (will exit if none were added on first pass), the process's local vector clock is checked against each message enqueued. If the message can be enqueued, the clocks are updated, the process's number is added with the message's number - and the loop starts again (this ensures re-checks are done on all messages when one is delivered for subsequent deliveries).
6. The `process_loop` is continually invoked until all events received in 2. are exhausted, and the process stops.

### Invocation

## Phase 2 - `phase2_sockets`

### 

- [ ] [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
- [ ] [Add files using the command line](https://docs.gitlab.com/ee/gitlab-basics/add-file.html#add-a-file-using-the-command-line) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.eng.unimelb.edu.au/jsammut/comp90020-double-j.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

- [ ] [Set up project integrations](https://gitlab.eng.unimelb.edu.au/jsammut/comp90020-double-j/-/settings/integrations)

## Collaborate with your team

- [ ] [Invite team members and collaborators](https://docs.gitlab.com/ee/user/project/members/)
- [ ] [Create a new merge request](https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html)
- [ ] [Automatically close issues from merge requests](https://docs.gitlab.com/ee/user/project/issues/managing_issues.html#closing-issues-automatically)
- [ ] [Enable merge request approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
- [ ] [Set auto-merge](https://docs.gitlab.com/ee/user/project/merge_requests/merge_when_pipeline_succeeds.html)

## Test and Deploy

Use the built-in continuous integration in GitLab.

- [ ] [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/index.html)
- [ ] [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
- [ ] [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
- [ ] [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
- [ ] [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
