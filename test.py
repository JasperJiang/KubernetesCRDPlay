import yaml
import kopf

if __name__ == "__main__":
    data_yaml = '''
        apiVersion: v1
        kind: Namespace
        metadata:
          name: test
    '''

    data_json = yaml.safe_dump(data_yaml)

    print(data_json)

    kopf.adopt(data_json)

    print(data_json)

    config.load_kube_config()    
    custome_object_api = client.CustomObjectsApi()
    mycrd_yaml = '''
    apiVersion: "ip.pwc.com/v1"
    kind: MyCrd
    metadata:
        name: mycrd-test
    spec:
        element1: 
            - testelement
            - testelement2
    '''

    mycrd_dic = yaml.safe_load(mycrd_yaml)


    print(mycrd_dic)

    # create the resource
    custome_object_api.create_cluster_custom_object(
        group="ip.pwc.com",
        version="v1",
        plural="mycrds",
        body=mycrd_dic,
    )
    print("Resource created")

    # # create the resource
    # api.create_namespaced_custom_object(
    #     group="stable.example.com",
    #     version="v1",
    #     namespace="default",
    #     plural="crontabs",
    #     body=my_resource,
    # )
    # print("Resource created")