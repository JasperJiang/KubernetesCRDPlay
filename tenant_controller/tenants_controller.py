import json
from kubernetes import client, config, watch
import kubernetes
import os
import yaml
import json
import kopf
import logging 
from retry import retry
import re
from config import constants

_logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)

kubernetes.config.load_kube_config()

core_api = kubernetes.client.CoreV1Api()
rbac_api = kubernetes.client.RbacAuthorizationV1Api()
custom_obj_api = kubernetes.client.CustomObjectsApi()

system_user = constants['system_user']
kubeflow_admin = constants['kubeflow_admin']
kubeflow_edit = constants['kubeflow_edit']
kubeflow_viewer = constants['kubeflow_viewer']
system_tenant = constants['system_tenant']

@kopf.on.create('ip.pwc.com', 'v1', 'tenants')
def create_fn_1(body, name, meta, spec, retry=None, **kwargs):
    tenant = body
    namespace_name = tenant.metadata.name
    tenant_name = tenant.metadata.name
    users = tenant.spec['users']
    _logger.info(f"start tenant creatation name: {name}, spec:{spec}, users:{users}")
    if tenant_name == system_tenant:
        # for system tenant
        binding_system_tenant_user(users)
    else:
        create_namespace(namespace_name)
        # TODO
        update_istio_rbac(namespace_name)
        # Update service accounts
	    # Create service account "default-editor" in target namespace.
	    # "default-editor" would have kubeflowEdit permission: edit all resources in target namespace except rbac.
        update_service_account(namespace_name, "default-editor", kubeflow_edit)
        # Create service account "default-viewer" in target namespace.
	    # "default-viewer" would have k8s default "view" permission: view all resources in target namespace.
        update_service_account(namespace_name, "default-viewer", kubeflow_viewer)
        # Update owner rbac permission
	    # When ClusterRole was referred by namespaced roleBinding, the result permission will be namespaced as well.
        role_binding_str = f'''
        apiVersion: rbac.authorization.k8s.io/v1
        kind: RoleBinding
        metadata:
            annotations:
                user: {system_user}
                role: admin
            name: namespaceAdmin
            namespace: {namespace_name}
        roleRef:
            apiGroup: rbac.authorization.k8s.io
            kind: ClusterRole
            name: {kubeflow_admin}
        subjects:
          - apiGroup: rbac.authorization.k8s.io
            kind: User
            name: {system_user}
        '''
        role_binding_dic= yaml.safe_load(role_binding_str)
        kopf.adopt(role_binding_dic)
        update_role_binding(namespace_name, role_binding_dic)
        # Create resource quota for target namespace if resources are specified in profile.
        create_quota(namespace_name)
        # assign new users
        binding_users(namespace_name, tenant.spec['users'])
        # new ns created we need to update the binding to all system admins
        update_system_tenant_user_binding(namespace_name)

def update_system_tenant_user_binding(namespace_name):
    tenants = custom_obj_api.list_cluster_custom_object('ip.pwc.com', 'v1', 'tenants')
    for tenant in tenants['items']:
        if tenant['metadata']['name'].lower() == system_tenant:
            binding_users(namespace_name, tenant['spec']['users'])
        else:
            pass
    

def binding_system_tenant_user(users):
    tenants = custom_obj_api.list_cluster_custom_object('ip.pwc.com', 'v1', 'tenants')
    for tenant in tenants['items']:
        if tenant['metadata']['name'].lower() == system_tenant:
            pass
        else:
            namespace_name = tenant['metadata']['name']
            binding_users(namespace_name, users)

def unbinding_system_tenant_user(users):
    tenants = custom_obj_api.list_cluster_custom_object('ip.pwc.com', 'v1', 'tenants')
    for tenant in tenants['items']:
        if tenant['metadata']['name'].lower() == system_tenant:
            pass
        else:
            namespace_name = tenant['metadata']['name']
            unbinding_users(namespace_name, users)

def binding_users(namespace_name, users):
    _logger.info(f"binding users {users}")
    for user in users:
        create_k8s_role_binding(namespace_name, user)
        create_istio_role_binding(namespace_name, user)

def get_role_binding_name(user):
    return f"user-{re.sub(r'[^a-z0-9]+', '-', user.strip())}-clusterrole-edit"

def create_k8s_role_binding(namespace_name, user):
    role_biding_name = get_role_binding_name(str(user))
    print(role_biding_name)
    role_binding_str = f'''
    apiVersion: rbac.authorization.k8s.io/v1
    kind: RoleBinding
    metadata:
        annotations:
            role: edit
            user: {user}
        name: {role_biding_name}
        namespace: {namespace_name}
    roleRef:
        apiGroup: rbac.authorization.k8s.io
        kind: ClusterRole
        name: {kubeflow_edit}
    subjects:
      - apiGroup: rbac.authorization.k8s.io
        kind: User
        name: {user}
    '''
    role_binding_dic= yaml.safe_load(role_binding_str)
    kopf.adopt(role_binding_dic)
    update_role_binding(namespace_name, role_binding_dic)

def create_istio_role_binding(namespace_name, user):
    pass

def create_namespace(namespace_name):
    namespace_str = f'''
        apiVersion: v1
        kind: Namespace
        spec:
            finalizers:
            - kubernetes
        metadata:
          name: {namespace_name}
          annotations:
            owner: {system_user}
          labels: 
            istioInjectionLabel: enabled
            katib-metricscollector-injection: enabled
            serving.kubeflow.org/inferenceservice: enabled
    '''
    namespace_dic= yaml.safe_load(namespace_str)
    kopf.adopt(namespace_dic)
    _logger.info(f"namespace_dic: {namespace_dic}")
    # check if namespace exists
    try:
        namespace = core_api.read_namespace(namespace_name)
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            namespace = None
        else:
            raise e
    if namespace == None:
        _logger.info(f"creating new namespace")
        core_api.create_namespace(namespace_dic)
        # wait 15 seconds for new namespace creation.
        namespace = wait_get_namepsace(namespace_name)
        _logger.info(f"Created Namespace: {namespace.metadata.name}, status: {namespace.status.phase}")
    else:
        _logger.info(f"updating namespace")
        core_api.patch_namespace(namespace_name, namespace_dic)

@retry(tries= 3, delay= 5)
def wait_get_namepsace(namespace_name):
    return core_api.read_namespace(namespace_name)

def update_istio_rbac(namespace_name):
    pass

def update_service_account(namespace_name, sa_name, cluster_role_name):
    # create service account
    sa_str = f'''
    apiVersion: v1
    kind: ServiceAccount
    metadata:
      name: {sa_name}
      namespace: {namespace_name}
    '''
    sa_dic= yaml.safe_load(sa_str)
    kopf.adopt(sa_dic)
    _logger.info(f"sa_dic: {sa_dic}")
    # check if sa exists
    try:
        sa = core_api.read_namespaced_service_account(sa_name, namespace_name)
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            sa = None
        else:
            raise e
    if sa == None:
        _logger.info(f"creating new service account")
        core_api.create_namespaced_service_account(namespace_name, sa_dic)
    else:
        _logger.info(f"updating service account")
        core_api.patch_namespaced_service_account(sa_name, namespace_name, sa_dic)
    # create rolebinding
    role_binding_str = f'''
    apiVersion: rbac.authorization.k8s.io/v1
    kind: RoleBinding
    metadata:
        name: {sa_name}
        namespace: {namespace_name}
    roleRef:
        apiGroup: rbac.authorization.k8s.io
        kind: ClusterRole
        name: {cluster_role_name}
    subjects:
      - kind: ServiceAccount
        name: {sa_name}
        namespace: {namespace_name}
    '''
    role_binding_dic= yaml.safe_load(role_binding_str)
    kopf.adopt(role_binding_dic)
    update_role_binding(namespace_name, role_binding_dic)

def update_role_binding(namespace_name, role_binding_dic):
    kopf.adopt(role_binding_dic)
    _logger.info(f"role_binding_dic: {role_binding_dic}")
    # check if rolebinding exists
    try:
        role_binding = rbac_api.read_namespaced_role_binding(role_binding_dic['metadata']['name'], namespace_name)
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            role_binding = None
        else:
            raise e
    if role_binding == None:
        _logger.info(f"creating new rolebinding")
        rbac_api.create_namespaced_role_binding(namespace_name, role_binding_dic)
    else:
        _logger.info(f"updating rolebinding")
        rbac_api.patch_cluster_role_binding(namespace_name, role_binding_dic)

def create_quota(namespace_name):
    pass

@kopf.on.field('ip.pwc.com', 'v1', 'tenants', field='spec.users')
def update_lst(body, old, new, **kwargs):
    namespace_name = body.metadata.name
    tenant_name = body.metadata.name
    if old != None:
        add_users = set(new) - set(old)
        del_users = set(old) - set(new)
        if tenant_name.lower() == system_tenant:
            binding_system_tenant_user(add_users)
            unbinding_system_tenant_user(del_users)
        else:  
            binding_users(namespace_name, add_users)
            unbinding_users(namespace_name, del_users)

# delete users from tenant
def unbinding_users(namespace_name, users):
    _logger.info(f"unbinding users {users}")
    for user in users:
        del_k8s_role_binding(namespace_name, user)
        del_istio_role_binding(namespace_name, user)

def del_k8s_role_binding(namespace_name, user):
    role_binding_name = get_role_binding_name(str(user))
    _logger.info(f"deleting role binding name: {role_binding_name}, namespace: {namespace_name}")
    try:
        rbac_api.delete_namespaced_role_binding(role_binding_name, namespace_name)
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            _logger.info(f"role binding {role_binding_name} is already deleted")
        else:
            raise e

def del_istio_role_binding(namespace_name, user):
    pass