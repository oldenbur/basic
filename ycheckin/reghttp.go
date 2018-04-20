package main

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/cihub/seelog"
	"io"
	"net/http"
)

type RegHttp interface {
	io.Closer
	Start() error
}

func NewRegHttp(addr string, sched WeeklyTickerScheduler, reg RegisterWorker) RegHttp {
	return &regHttp{
		addr:  addr,
		sched: sched,
		reg:   reg,
	}
}

type regHttp struct {
	srv   *http.Server
	addr  string
	sched WeeklyTickerScheduler
	reg   RegisterWorker
}

func (r *regHttp) Start() error {

	mux := http.NewServeMux()
	mux.HandleFunc("/pending", r.handlePending)

	r.srv = &http.Server{Handler: mux}

	return nil
}

func (r *regHttp) Close() error {

	if r.srv != nil {
		r.srv.Shutdown(context.Background())
	}

	return nil
}

func (r *regHttp) handlePending(w http.ResponseWriter, req *http.Request) {

	pendings := r.sched.Pending()
	pendingRegs := []pendingRegItem{}
	for _, pending := range pendings {
		pendingRegs = append(pendingRegs, pendingRegItem{fmt.Sprintf("%v", pending)})
	}

	json, err := json.Marshal(pendingRegs)
	if err != nil {
		errStr := fmt.Sprintf(`json.Marshal('%v') returned error: %v`, pendingRegs, err)
		seelog.Errorf(errStr)
		json = []byte(fmt.Sprintf(`{"error": "%s"}`, errStr))
	}

	io.WriteString(w, string(json))
}

type pendingRegItem struct {
	PendingReg string `json:"pendingReg"`
}
