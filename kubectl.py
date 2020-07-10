import kubernetes


if __name__ == "__main__":
    kubernetes.config.load_kube_config()
    api = kubernetes.client.CoreV1Api()
    # a = api.read_namespace('default')
    # print(a.metadata.name)
    custom_obj_api = kubernetes.client.CustomObjectsApi()

    tenants = custom_obj_api.list_cluster_custom_object('ip.pwc.com', 'v1', 'tenants')
    print(tenants['items'])
    # old = ['user1@pwc.com', 'user2@pwc.com']
    # new = ['user1@pwc.com', 'user3@pwc.com']

    # print(f"new: {set(new) - set(old)}")
    
    # print(f"removed: {set(old) - set(new)}")