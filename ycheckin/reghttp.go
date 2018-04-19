package main

import (
	"io"
	"net/http"
)

type RegHttp interface {
	io.Closer
	Start() error
}

func NewRegHttp(addr string) RegHttp {
	return &regHttp{addr: addr}
}

type regHttp struct {
	srv  *http.Server
	addr string
}

func (r *regHttp) Start() error {

	mux := http.NewServeMux()
	mux.HandleFunc("/pending", r.handlePending)

	r.srv = &http.Server{Handler: mux}

	return nil
}

func (r *regHttp) Close() error {

	return nil
}

func (r *regHttp) handlePending(w http.ResponseWriter, req *http.Request) {
	io.WriteString(w, "hello world\n")
}
