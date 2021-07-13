from pyats.easypy import run
import subprocess

def main():
    try:
        subprocess.check_output("docker container rm curl -f", shell=True)   
    except:
        pass
    # Start a curl container to run curl accesses from
    subprocess.check_output("docker run -it --network kind --name curl -d --user 0:0 --cap-add=NET_ADMIN curlimages/curl /bin/sh", shell=True)   
    # The ip address 1.1.1.1 is just some random IP, its not advertised anywhere, nextensio doesnt care about IP addresses
    subprocess.check_output("docker exec -it  curl sh -c \"echo 1.1.1.1 foobar.com >> /etc/hosts\"", shell=True)   
    subprocess.check_output("docker exec -it  curl sh -c \"echo 1.1.1.1 kismis.org >> /etc/hosts\"", shell=True)   
    # run api launches a testscript as an individual task.
    run('connectivity_checks.py')
    subprocess.check_output("docker container rm curl -f", shell=True)   
