package main

import (
	"fmt"
	"regexp"
	"strings"
	"time"

	"strconv"

	"github.com/cihub/seelog"

	"io"
	"sort"
	"sync"
)

const oneMinuteTimeout = 61 * time.Second

var regexpSched = regexp.MustCompile(`(SUN|MON|TUE|WED|THU|FRI|SAT)_(\d{2})\:(\d{2}):(\d{2})\.(\d{3})`)

// sched should have the format: TUE_07:00:00.000,FRI_07:00:00.000
type WeeklyTicker chan time.Time

type WeeklyTickerScheduler interface {
	io.Closer
	fmt.Stringer
	ScheduleWeekly(sched string) (WeeklyTicker, error)
}

type weeklyTickerScheduler struct {
	mutex         *sync.Mutex
	wg            *sync.WaitGroup
	pendingEvents timeSlice
	closeChan     chan bool
	loc           *time.Location

	delayer func(time.Duration) <-chan time.Time
	firer   func(t WeeklyTicker, eventTime time.Time)
}

func NewWeeklyTickerScheduler() WeeklyTickerScheduler {
	s := &weeklyTickerScheduler{
		mutex:         &sync.Mutex{},
		wg:            &sync.WaitGroup{},
		pendingEvents: timeSlice{},
		closeChan:     make(chan bool),
		delayer: func(d time.Duration) <-chan time.Time {
			return time.After(d)
		},
		firer: func(t WeeklyTicker, eventTime time.Time) {
			t <- eventTime
		},
	}

	var err error
	s.loc, err = time.LoadLocation("America/Denver")
	if err != nil {
		seelog.Errorf("time.LoadLocation error: %v", err)
		s.loc = time.Local
	}

	return s
}

func (s *weeklyTickerScheduler) ScheduleWeekly(sched string) (WeeklyTicker, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	ticker := make(WeeklyTicker)
	var err error

	s.pendingEvents, _ = s.buildPendingEventQueue(sched)

	if len(s.pendingEvents) < 1 {
		return ticker, fmt.Errorf("schedule contains no events")
	}

	go func() {
		s.wg.Add(1)
		defer s.wg.Done()

		for {

			event := s.rollEvent()
			delay := event.Sub(time.Now())
			eventChan := s.delayer(delay)
			seelog.Infof("waiting %v for next event: %v", delay, event)

			select {
			case eventTime := <-eventChan:
				seelog.Infof("firing event at %v", eventTime)
				s.firer(ticker, eventTime)
				break

			case <-s.closeChan:
				seelog.Infof("closing event loop")
				return
			}
		}

	}()

	return ticker, err
}

func (s *weeklyTickerScheduler) String() string {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	return fmt.Sprintf("%v", s.pendingEvents)
}

func (s *weeklyTickerScheduler) rollEvent() time.Time {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	t := s.pendingEvents[0]
	s.pendingEvents = append(
		s.pendingEvents[1:],
		time.Date(t.Year(), t.Month(), t.Day()+7, t.Hour(), t.Minute(), t.Second(), t.Nanosecond(), s.loc),
	)

	return t
}

func (s *weeklyTickerScheduler) buildPendingEventQueue(sched string) (timeSlice, error) {

	var err error
	events := timeSlice{}

	for _, pat := range strings.Split(sched, ",") {

		seelog.Infof(`adding ticker for pattern %v`, pat)

		regexpMat := regexpSched.FindStringSubmatch(pat)
		if len(regexpMat) != 6 {
			err = seelog.Warnf(`unexpected structure parsing schedule component '%s' matches: %v`, pat, regexpMat)
		}

		var event time.Time
		if event, err = s.buildPendingDate(regexpMat[1], regexpMat[2], regexpMat[3], regexpMat[4], regexpMat[5]); err != nil {
			err = seelog.Warnf(`buildPendingDate error: %v`, err)
		}

		events = append(events, event)
	}

	sort.Sort(events)

	return events, err
}

func (s *weeklyTickerScheduler) Close() error {

	seelog.Infof("scheduler closing...")
	s.closeChan <- true
	s.wg.Wait()
	seelog.Infof("scheduler closed")

	return nil
}

func (s *weeklyTickerScheduler) dayStringToWeekday(day string) (time.Weekday, error) {
	switch day {
	case "SUN":
		return time.Sunday, nil
	case "MON":
		return time.Monday, nil
	case "TUE":
		return time.Tuesday, nil
	case "WED":
		return time.Wednesday, nil
	case "THU":
		return time.Thursday, nil
	case "FRI":
		return time.Friday, nil
	case "SAT":
		return time.Saturday, nil
	default:
		return time.Sunday, fmt.Errorf("invalid day string: %s", day)
	}
}

func (s *weeklyTickerScheduler) buildPendingDate(dayStr, hourStr, minStr, secStr, msStr string) (time.Time, error) {

	var err error
	var t time.Time
	var targetDay time.Weekday

	if targetDay, err = s.dayStringToWeekday(dayStr); err != nil {
		return t, fmt.Errorf(`dayString '%s' error: %v`, dayStr, err)
	}

	var hour, min, sec, ms int
	if hour, err = strconv.Atoi(hourStr); err != nil {
		return t, fmt.Errorf(`hour '%s' error: %v`, hourStr, err)
	}
	if min, err = strconv.Atoi(minStr); err != nil {
		return t, fmt.Errorf(`min '%s' error: %v`, minStr, err)
	}
	if sec, err = strconv.Atoi(secStr); err != nil {
		return t, fmt.Errorf(`sec '%s' error: %v`, secStr, err)
	}
	if ms, err = strconv.Atoi(msStr); err != nil {
		return t, fmt.Errorf(`ms '%s' error: %v`, msStr, err)
	}

	now := time.Now().In(s.loc)
	t = time.Date(now.Year(), now.Month(), now.Day(), hour, min, sec, ms*1000000, s.loc)
	for t.Weekday() != targetDay {
		seelog.Tracef(`seeking %v: %v`, targetDay, t)
		t = time.Date(t.Year(), t.Month(), t.Day()+1, t.Hour(), t.Minute(), t.Second(), t.Nanosecond(), s.loc)
	}
	seelog.Debugf(`pending date %v: %v`, targetDay, t)

	return t, nil
}

type timeSlice []time.Time

func (s timeSlice) Len() int           { return len(s) }
func (s timeSlice) Less(i, j int) bool { return s[i].Before(s[j]) }
func (s timeSlice) Swap(i, j int)      { t := s[i]; s[i] = s[j]; s[j] = t }
