package main

import (
	"fmt"
	"testing"
	"time"

	"github.com/cihub/seelog"
	"github.com/jasonlvhit/gocron"
	"github.com/stretchr/testify/assert"
)

func init() { setupLogging() }

func TestParseSchedule(t *testing.T) {
	s := NewWeeklyTickerScheduler()

	future := time.Now().Add(time.Minute)
	pat := fmt.Sprintf(`%s_%s:00.000`, weekdayToPat(future.Weekday()), future.Format("15:04"))

	ticker, err := s.ParseSchedule(pat)
	assert.Nil(t, err)
	assert.NotNil(t, ticker)

	tick := <-ticker
	assert.Equal(t, tick, future)
}

func TestGocron(t *testing.T) {
	c := make(chan int)
	seelog.Infof("now: %v", time.Now())
	gocron.Every(1).Sunday().At("10:19").Do(func() {
		seelog.Infof("gocron1 works: %v", time.Now())
		c <- 1
	})
	gocron.Every(1).Sunday().At("11:19").Do(func() {
		seelog.Infof("gocron2 works: %v", time.Now())
		c <- 2
	})
	gocron.Every(1).Sunday().At("12:19").Do(func() {
		seelog.Infof("gocron3 works: %v", time.Now())
		c <- 3
	})
	gocron.Start()
	job, nextTime := gocron.NextRun()
	seelog.Infof("nextTime: %v  job: %v", nextTime, job)
	<-c
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
