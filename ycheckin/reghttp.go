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

type RegHttpConfig interface {
	HttpAddr() string
	MarshalJSON() string
}

func NewRegHttp(config RegHttpConfig, sched WeeklyTickerScheduler, reg RegisterWorker) RegHttp {
	return newRegHttp(config, sched, reg)
}

func newRegHttp(config RegHttpConfig, sched WeeklyTickerScheduler, reg RegisterWorker) *regHttp {
	return &regHttp{
		config: config,
		sched:  sched,
		reg:    reg,
	}
}

type regHttp struct {
	config RegHttpConfig
	srv    *http.Server
	sched  WeeklyTickerScheduler
	reg    RegisterWorker
}

func (r *regHttp) Start() error {

	mux := http.NewServeMux()
	mux.HandleFunc("/pending", r.handlePending)
	mux.HandleFunc("/config", r.handleConfig)

	r.srv = &http.Server{Handler: mux}
	go func() {
		err := r.srv.ListenAndServe()
		if err != nil {
			seelog.Errorf("ListenAndServe error: %v", err)
		}
	}()

	return nil
}

func (r *regHttp) Close() error {

	if r.srv != nil {
		r.srv.Shutdown(context.Background())
	}

	return nil
}

func (r *regHttp) handlePending(w http.ResponseWriter, req *http.Request) {

	seelog.Info("method: %v", req.Method)

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

func (r *regHttp) handleConfig(w http.ResponseWriter, req *http.Request) {

	seelog.Info("method: %v", req.Method)
	io.WriteString(w, string(r.config.MarshalJSON()))
}
