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
	s := NewWeeklyTickerScheduler(time.Local)

	future := time.Now().Add(500 * time.Millisecond)
	pat := fmt.Sprintf(`%s_%s`, weekdayToPat(future.Weekday()), future.Format("15:04:05.000"))
	seelog.Infof("pat: %s", pat)

	ticker, err := s.ScheduleWeekly(pat)
	defer s.Close()
	assert.Nil(t, err)
	assert.NotNil(t, ticker)

	seelog.Infof("pendingEvents: %v", s.Pending())

	tick := <-ticker
	delta := tick.Sub(future)
	seelog.Infof("delta: %v", delta)
	assert.True(t, math.Abs(float64(delta)) < float64(10*time.Millisecond))
}

func TestPending(t *testing.T) {
	defer seelog.Flush()
	s := newWeeklyTickerScheduler(time.Local)

	c := make(chan bool)
	s.progRolled = func() { c <- true }

	future := time.Now().Add(500 * time.Millisecond).Truncate(time.Millisecond)
	pat := fmt.Sprintf(`%s_%s`, weekdayToPat(future.Weekday()), future.Format("15:04:05.000"))
	future2 := future.Add(48 * time.Hour).Truncate(time.Millisecond)
	pat = fmt.Sprintf(`%s,%s_%s`, pat, weekdayToPat(future2.Weekday()), future2.Format("15:04:05.000"))
	seelog.Infof("pat: %s", pat)

	_, err := s.ScheduleWeekly(pat)
	defer s.Close()
	assert.Nil(t, err)

	<-c
	seelog.Infof("pendingEvents: %v", s.Pending())
	assert.Equal(t, []time.Time{future, future2, future.Add(7 * 24 * time.Hour)}, s.Pending())
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
