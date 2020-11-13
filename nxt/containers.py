
import docker
from pyats.connections import BaseConnection
from kubernetes.client.configuration import Configuration
from kubernetes.config import kube_config
from kubernetes.client import api_client
from kubernetes.client.api import core_v1_api
from kubernetes.stream import stream, portforward
from kubernetes.stream.ws_client import ERROR_CHANNEL
from kubernetes.client import AppsV1Api


def docker_run(cname, cmd):
    try:
        client = docker.from_env()
        container = client.containers.get(cname)
        out = container.exec_run(['sh', '-c', cmd])
        return out.output.decode("utf-8")
    except:
        pass
        return ""


def kube_get_pod(cluster, namespace, pod):
    try:
        config = Configuration()
        kube_config.load_kube_config(
            context=cluster, client_configuration=config)
        config.assert_hostname = False
        client = api_client.ApiClient(configuration=config)
        api = core_v1_api.CoreV1Api(client)
        ret = api.list_namespaced_pod(namespace)
        podname = None
        for item in ret.items:
            if pod in item.metadata.name:
                podname = item.metadata.name

        return podname
    except Exception as e:
        pass
        return None


def kube_run(cluster, namespace, container, pod, cmd):
    try:
        config = Configuration()
        kube_config.load_kube_config(
            context=cluster, client_configuration=config)
        config.assert_hostname = False
        client = api_client.ApiClient(configuration=config)
        api = core_v1_api.CoreV1Api(client)
        ret = api.list_namespaced_pod(namespace)
        podname = None
        for item in ret.items:
            if pod in item.metadata.name:
                podname = item.metadata.name
        exec_command = ['/bin/sh',
                        '-c',
                        cmd]
        resp = stream(api.connect_get_namespaced_pod_exec, podname, namespace,
                      container=container,
                      command=exec_command,
                      stderr=False, stdin=False,
                      stdout=True, tty=False)
        return resp
    except Exception as e:
        pass
        return ""


class DockerConnection(BaseConnection):
    '''DockerConnection

    Implementation of docker exec -it <container> <command>
    '''

    nxt = {}

    def __init__(self, *args, **kwargs):
        '''__init__

        instantiate a single connection instance.
        '''

        # instantiate parent BaseConnection
        super().__init__(*args, **kwargs)

    def connect(self):
        '''connect

        Nothing to do for docker.
        '''
        return

    def connected(self):
        return

    def send(self, text):
        '''send

        low-level api: sends raw text through session, no-op for docker.
        '''
        return

    def receive(self):
        '''receive

        low-level api: reads from the  session and returns whatever is
        currently in the buffer, no-op for docker
        '''
        return

    def execute(self, command):
        '''execute

        high-level api: sends a command through the session, expect it to
        be executed, and return back to prompt.
        '''

        return docker_run(self.connection_info['name'], command)

    def configure(self, *args, **kwargs):
        for k, v in kwargs.items():
            self.nxt[k] = v

    def stop(self):
        client = docker.from_env()
        container = client.containers.get(self.connection_info['name'])
        container.kill()

    def start(self):
        client = docker.from_env()
        container = client.containers.get(self.connection_info['name'])
        container.start()

    def restart(self):
        client = docker.from_env()
        container = client.containers.get(self.connection_info['name'])
        container.kill()
        container.start()


class KubernetesConnection(BaseConnection):
    '''KubernetesConnection

    Implementation of kubectl exec -it <container> -- <command>
    '''

    def __init__(self, *args, **kwargs):
        '''__init__

        instantiate a single connection instance.
        '''

        # instantiate parent BaseConnection
        super().__init__(*args, **kwargs)
        self.nxt = {}

    def connect(self):
        '''connect

        Nothing to do for kubernetes.
        '''
        return

    def connected(self):
        return

    def send(self, text):
        '''send

        low-level api: sends raw text through session, no-op for docker.
        '''
        return

    def receive(self):
        '''receive

        low-level api: reads from the  session and returns whatever is
        currently in the buffer, no-op for docker
        '''
        return

    def execute(self, command):
        '''execute

        high-level api: sends a command through the session, expect it to
        be executed, and return back to prompt.
        '''

        cluster, pod = self.details()
        return kube_run(cluster, self.nxt['namespace'], self.nxt['container'], pod, command)

    def configure(self, *args, **kwargs):
        for k, v in kwargs.items():
            self.nxt[k] = v

    def details(self):
        cluster_pod = self.connection_info['name'].split(":")
        return cluster_pod[0], cluster_pod[1]

    def stop(self):
        cluster, pod = self.details()
        config = Configuration()
        kube_config.load_kube_config(
            context=cluster, client_configuration=config)
        config.assert_hostname = False
        client = api_client.ApiClient(configuration=config)
        api = AppsV1Api(client)
        body = {"spec": {"replicas": 0}}
        api.patch_namespaced_deployment_scale(
            name=pod, namespace=self.nxt['namespace'], body=body)

    def start(self):
        cluster, pod = self.details()
        config = Configuration()
        kube_config.load_kube_config(
            context=cluster, client_configuration=config)
        config.assert_hostname = False
        client = api_client.ApiClient(configuration=config)
        api = AppsV1Api(client)
        body = {"spec": {"replicas": 1}}
        api.patch_namespaced_deployment_scale(
            name=pod, namespace=self.nxt['namespace'], body=body)

    def restart(self):
        cluster, pod = self.details()
        config = Configuration()
        kube_config.load_kube_config(
            context=cluster, client_configuration=config)
        config.assert_hostname = False
        client = api_client.ApiClient(configuration=config)
        api = AppsV1Api(client)
        body = {"spec": {"replicas": 0}}
        api.patch_namespaced_deployment_scale(
            name=pod, namespace=self.nxt['namespace'], body=body)
        body = {"spec": {"replicas": 1}}
        api.patch_namespaced_deployment_scale(
            name=pod, namespace=self.nxt['namespace'], body=body)
