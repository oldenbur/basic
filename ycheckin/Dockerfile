# $ docker build -t oldenbur/ycheckin .
# $ docker run -e "YC_REG_TIMES=SUN_07:00:00.000" -p 8989:8989 --rm oldenbur/ycheckin
# $ curl 192.168.1.5:8989/config

FROM golang:latest

WORKDIR /go/src/github.com/oldenbur/linux-util/ycheckin
COPY . .

RUN go get -d -v ./...
RUN go install -v ./...

ENV YC_REG_TIMES ${YC_REG_TIMES}

EXPOSE 8989

CMD ["ycheckin","regloop"]
