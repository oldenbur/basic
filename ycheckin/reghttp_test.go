package main

import (
	"testing"
	"time"

	"github.com/cihub/seelog"
	"github.com/stretchr/testify/assert"
)

func init() { setupLogging() }

func TestHandlePending(t *testing.T) {
	defer seelog.Flush()
	ticker := &mockTicker{}
	//	s := NewRegHttp("", ticker, nil)

	ticker.pending = []time.Time{
		time.Date(2018, 4, 3, 5, 30, 0, 0, time.Local),
	}
}

type mockTicker struct {
	pending []time.Time
}

func (t *mockTicker) Close() error                                      { return nil }
func (t *mockTicker) ScheduleWeekly(sched string) (WeeklyTicker, error) { return nil, nil }
func (t *mockTicker) Pending() []time.Time                              { return t.pending }
