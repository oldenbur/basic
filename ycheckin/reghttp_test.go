package main

import (
	"testing"
	"time"

	"bytes"
	"github.com/cihub/seelog"
	"github.com/stretchr/testify/assert"
	"net/http"
)

func init() { setupLogging() }

func TestHandlePending(t *testing.T) {
	defer seelog.Flush()
	ticker := &mockTicker{}
	ticker.pending = []time.Time{
		time.Date(2018, 4, 3, 5, 30, 0, 0, time.Local),
		time.Date(2018, 4, 6, 5, 45, 0, 0, time.Local),
	}

	resp := &mockResponseWriter{}
	s := newRegHttp(nil, ticker, nil)
	s.handlePending(resp, &http.Request{Method: "GET"})

	assert.Equal(t,
		`[{"pendingReg":"2018-04-03 05:30:00 -0600 MDT"},{"pendingReg":"2018-04-06 05:45:00 -0600 MDT"}]`,
		resp.response.String(),
	)
}

type mockTicker struct {
	pending []time.Time
}

func (t *mockTicker) Close() error                                      { return nil }
func (t *mockTicker) ScheduleWeekly(sched string) (WeeklyTicker, error) { return nil, nil }
func (t *mockTicker) Pending() []time.Time                              { return t.pending }

type mockResponseWriter struct {
	response bytes.Buffer
}

func (w *mockResponseWriter) Header() http.Header { return nil }
func (w *mockResponseWriter) Write(r []byte) (int, error) {
	w.response.Write(r)
	return len(r), nil
}
func (w *mockResponseWriter) WriteHeader(statusCode int) {}

type mockConfigMarshaler struct{}

func (c *mockConfigMarshaler) MarshalJSON() string { return `{"mockConfig": "true"}` }
func (c *mockConfigMarshaler) HttpAddr() string    { return `httpAddr` }
