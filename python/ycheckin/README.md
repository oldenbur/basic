## ycheckin \[python\]

This folder contains a uv python project for signing up for YMCA of Northern Colorado
drop-in hockey through the SignUpGenius portal web page.

### Development Environment

The development environment includes the following tools:

* VirtualBox ubuntu-ssd VM: run in headless
* vscode remote: paul@127.0.0.1

Build the docker image:

```
docker build -t oldenbur/ycheckin:0.1 .
```

Run the docker image locally:
```
docker run --rm -d -p 8080:8080 oldenbur/checkin:0.1
```

Configure docker to talk to gcloud artifact registry:

```
gcloud auth configure-docker us-central1-docker.pkg.dev
```

Give the local image a registry tag and push to the registry:
```
docker tag oldenbur/ycheckin:0.1 us-central1-docker.pkg.dev/morningcoffee-189913/default/oldenbur/ycheckin:0.1
docker push us-central1-docker.pkg.dev/morningcoffee-189913/default/oldenbur/ycheckin:0.1
```

Deploy the image to cloud run:
```
gcloud run deploy ycheckin \
  --image=us-central1-docker.pkg.dev/morningcoffee-189913/default/oldenbur/ycheckin:0.1 \
  --no-allow-unauthenticated \
  --port=8080 \
  --service-account=304290747571-compute@developer.gserviceaccount.com \
  --region=us-central1 \
  --project=morningcoffee-189913
```
