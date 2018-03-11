package main

import (
	"fmt"
	"regexp"
	"strings"
	"time"

	"strconv"

	"github.com/cihub/seelog"

	"io"

	"github.com/jasonlvhit/gocron"
)

const oneMinuteTimeout = 61 * time.Second

var regexpSched = regexp.MustCompile(`(SUN|MON|TUE|WED|THU|FRI|SAT)_(\d{2}\:\d{2}):(\d{2})\.(\d{3})`)

// sched should have the format: TUE_07:00:00.000,FRI_07:00:00.000
type WeeklyTicker chan time.Time

type WeeklyTickerScheduler interface {
	io.Closer
	ParseSchedule(sched string) (WeeklyTicker, error)
}

type weeklyTickerScheduler struct {
	stopCron  chan bool
	delayer   func(time.Duration) <-chan time.Time
	timeouter func() <-chan time.Time
	firer     func(t WeeklyTicker, eventTime time.Time)

	progTimeout func()
}

func NewWeeklyTickerScheduler() WeeklyTickerScheduler {
	return &weeklyTickerScheduler{
		delayer: func(d time.Duration) <-chan time.Time {
			return time.After(d)
		},
		timeouter: func() <-chan time.Time {
			return time.NewTicker(oneMinuteTimeout).C
		},
		firer: func(t WeeklyTicker, eventTime time.Time) {
			t <- eventTime
		},
		progTimeout: func() {},
	}
}

func (s *weeklyTickerScheduler) ParseSchedule(sched string) (WeeklyTicker, error) {

	var err error
	ticker := make(WeeklyTicker)

	for i, pat := range strings.Split(sched, ",") {

		seelog.Infof(`adding ticker for pattern %v`, pat)

		regexpMat := regexpSched.FindStringSubmatch(pat)
		if len(regexpMat) != 5 {
			err = fmt.Errorf(`failed to parse schedule component %d "%s"  matches: %v`, i, pat, regexpMat)
		}

		var job *gocron.Job
		job, err = s.createJobByDay(regexpMat[1])
		if err != nil {
			seelog.Warnf(`createJobByDay for %s error: %v`, pat, err)
			continue
		}
		seelog.Debugf(`created job on day %s`, regexpMat[1])

		job, err = s.setJobTime(job, regexpMat[2])
		if err != nil {
			seelog.Warnf(`setJobTime(%s) for %s error: %v`, regexpMat[2], pat, err)
			continue
		}
		seelog.Debugf(`set job time to %s`, regexpMat[2])

		var delay time.Duration
		delay, err = s.buildSubMinuteDelay(regexpMat[3], regexpMat[4])
		if err != nil {
			seelog.Warnf(`buildSubMinuteDelay(%s, %s) for %s error: %v`, regexpMat[3], regexpMat[4], pat, err)
			continue
		}
		seelog.Debugf(`added job delay %v`, delay)

		job.Do(s.fireWeeklyTicker, ticker, delay)
	}

	// TODO: do not ignore the return value, do cleanup properly
	s.stopCron = gocron.Start()

	return ticker, err
}

func (s *weeklyTickerScheduler) Close() error {
	timeoutC := s.timeouter()

	select {
	case s.stopCron <- true:
		seelog.Infof("stopped gocron")
	case <-timeoutC:
		return seelog.Warn("timed out stopping gocron")
	}

	return nil
}

func (s *weeklyTickerScheduler) createJobByDay(dayCode string) (*gocron.Job, error) {

	job := gocron.Every(1)

	switch dayCode {
	case "SUN":
		return job.Sunday(), nil
	case "MON":
		return job.Monday(), nil
	case "TUE":
		return job.Tuesday(), nil
	case "WED":
		return job.Wednesday(), nil
	case "THU":
		return job.Thursday(), nil
	case "FRI":
		return job.Friday(), nil
	case "SAT":
		return job.Saturday(), nil
	}

	return nil, fmt.Errorf("unrecognized dayCode: %s", dayCode)
}

func (s *weeklyTickerScheduler) setJobTime(job *gocron.Job, tod string) (*gocron.Job, error) {

	var err error
	var ok bool

	func() {
		defer func() {
			if r := recover(); r != nil {
				if err, ok = r.(error); !ok {
					seelog.Warnf(`setJobTime(%s) unexpected recover artifact: %v`, tod, r)
				} else {
					err = fmt.Errorf(`setJobTime(%s) error: %v`, tod, err)
				}
			}
		}()

		job.At(tod)
	}()

	return job, err
}

func (s *weeklyTickerScheduler) buildSubMinuteDelay(secsStr, millisStr string) (time.Duration, error) {

	var dur time.Duration
	var secs, millis int
	var err error

	if secs, err = strconv.Atoi(secsStr); err != nil {
		return dur, fmt.Errorf("Atoi(%s) error: %v", secsStr, err)
	}

	if millis, err = strconv.Atoi(millisStr); err != nil {
		return dur, fmt.Errorf("Atoi(%s) error: %v", millisStr, err)
	}

	dur = time.Duration(secs)*time.Second + time.Duration(millis)*time.Millisecond

	return dur, nil
}

func (s *weeklyTickerScheduler) fireWeeklyTicker(ticker WeeklyTicker, delay time.Duration) {

	delayC := s.delayer(delay)
	timeoutC := s.timeouter()

	seelog.Infof(`firing ticker in %v...`, delay)

	if delay <= time.Duration(0) {

		now := time.Now()
		seelog.Infof(`firing ticker at %v`, now)
		s.firer(ticker, now)

	} else {

		select {
		case now := <-delayC:
			seelog.Infof(`firing ticker at %v`, now)
			s.firer(ticker, now)

		case now := <-timeoutC:
			seelog.Warnf(`fireWeeklyTicker(%v) timed out at: %v`, delay, now)
			s.progTimeout()
		}
	}
}
