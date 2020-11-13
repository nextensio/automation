# Nextensio Automation, THE MOTTO

The motto is "DO DETERMINISTIC TESTING". What it means is simple. Lets say we configure something
on the controller and we want to wait to ensure all the pods have got that config. One approach
is just to sleep for a random period of time after configuration, and then run our test cases.
That is something we SHOULD NOT DO. We should make whatever code changes required in the pods
to give the scripts some feedback that "ok I got the config", so the scripts are waiting on a
deterministic event rather than random period of time.

The above applies to code that WE WRITE and WE CONTROL. There are times when we have to check
for things in code we dont control. For example when we add a consul entry, it takes time to
propagate through kubernetes coredns. And we dont have any control or indication of how long it
takes or when its complete, so in those cases we do "check for dns, sleep 1 second if not ready",
that is not a great thing to do, if we could control every piece of code in the system we would

## nxt

### Software installation

At some point we will have a docker container pre-installed with all the required images for
automation, till that point, the below is what you need to install on your laptop to run the
automation scripts

1. pip3 install pyats[full]
2. pip3 install requests 
3. pip3 install dotenv

### Running automation

This directory contains the automation code. To run automaton on your linux environment, first
create a testbed as described in the next section testbed/kind. Once the testbed is created on
your laptop, go to the nxt directory and type the below 

```PYTHONPATH=$PYTHONPATH:. pyats run job sanity_jobs.py --testbed-file yamls/testbed.yaml```

## testbed/kind

The testbed directory has utilities to create the testbed used for nextensio automation and for development/testing



