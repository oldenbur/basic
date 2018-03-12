package main

import (
	"fmt"
	"testing"
	"time"

	"github.com/cihub/seelog"
	"github.com/stretchr/testify/assert"
	"math"
)

func init() { setupLogging() }

func TestParseSchedule(t *testing.T) {
	defer seelog.Flush()
	s := NewWeeklyTickerScheduler()

	future := time.Now().Add(500 * time.Millisecond)
	pat := fmt.Sprintf(`%s_%s`, weekdayToPat(future.Weekday()), future.Format("15:04:05.000"))

	ticker, err := s.ScheduleWeekly(pat)
	assert.Nil(t, err)
	assert.NotNil(t, ticker)

	seelog.Infof("pendingEvents: %v", s)

	tick := <-ticker
	delta := tick.Sub(future)
	seelog.Infof("delta: %v", delta)
	assert.True(t, math.Abs(float64(delta)) < float64(10*time.Millisecond))

	s.Close()
}

func weekdayToPat(w time.Weekday) string {
	switch w {
	case time.Sunday:
		return "SUN"
	case time.Monday:
		return "MON"
	case time.Tuesday:
		return "TUE"
	case time.Wednesday:
		return "WED"
	case time.Thursday:
		return "THU"
	case time.Friday:
		return "FRI"
	case time.Saturday:
		return "SAT"
	default:
		return "ERROR"
	}
}
