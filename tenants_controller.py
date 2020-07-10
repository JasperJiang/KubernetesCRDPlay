import json
from kubernetes import client, config, watch
import kubernetes
import os
import yaml
import json
import kopf
import logging 

_logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)

kubernetes.config.load_kube_config()

@kopf.on.create('ip.pwc.com', 'v1', 'tenants')
def create_fn_1(name, meta, spec, retry=None, **kwargs):
    print(f"new tenant created name: {name}, spec:{spec}")
    create_namespace(name)
    
@kopf.on.delete('ip.pwc.com', 'v1', 'tenants')
def delete(name, **kwargs):
    print(f"delete tenant name: {name}")
    del_namespce(name)

def create_namespace(name):
    data_yaml = f'''
        apiVersion: v1
        kind: Namespace
        metadata:
          name: {name}
    '''
    data_dic= yaml.safe_load(data_yaml)
    print(data_dic)
    api = kubernetes.client.CoreV1Api()
    api.create_namespace(data_dic)

def del_namespce(name):
    api = kubernetes.client.CoreV1Api()
    api.delete_namespace(name)