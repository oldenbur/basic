### Docker image

To build, run and test the ycheckin container:

```
$ docker build -t oldenbur/ycheckin .
$ docker run -e "YC_REG_TIMES=SUN_07:00:00.000" -p 8989:8989 --rm oldenbur/ycheckin
$ curl ${HOST_IP}:8989/config
```


### Kubernetes Service

```
# start with a fresh minikube instance
$ minikube delete
$ minikube start

# deploy the ycheckin container in a minikube service
$ kubectl apply -f deployment.yaml
$ kubectl apply -f service.yaml
$ minikube service ycheckin --url
$ curl http://${MINIKUBE_URL}/config
```

