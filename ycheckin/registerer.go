package main

import (
	"fmt"
	"github.com/PuerkitoBio/goquery"
	"gopkg.in/headzoo/surf.v1"
	"time"

	"errors"
	"github.com/cihub/seelog"
	"io"
	"regexp"
	"strings"
	"sync"
)

const (
	ymcaSchedulesUrl  = "https://bouldervalley.consoria.com/%s"
	ymcaReserveUrl    = "https://bouldervalley.consoria.com/%s/reserve/%s"
	urlDateFormat     = "2006-01-02"
	registrationName  = "Paul Oldenburg"
	registrationEmail = "oldenbur@gmail.com"

	regPostAlert_Reserved = "Your spot has been reserved" // "Your spot has been reserved and an email with more information has been sent to your email"
	regPostAlert_24hours  = "Reservations may not be made until 24 hours prior"
	regPostAlert_WaitList = "you have been added to the waitlist"
	regPostAlert_OneReg   = "one reservation per individual may be made"
)

var urlDateRegexp = regexp.MustCompile(`\d{4}\-\d{2}\-\d{2}`)

var wsRegexp = regexp.MustCompile(`(?: {2,}|\n)`)

type RegisterWorkerConfig interface {
	RegisterLocation() *time.Location
	ScheduleAheadDuration() time.Duration
	RegisterRetryWait() time.Duration
	RegisterRetryMax() int
	RegisterRetryLogIntvl() int
}

type RegisterWorker interface {
	io.Closer
	Work(ticker WeeklyTicker)
}

type EventRegistrar interface {
	EventRegister(event time.Time) error
}

type UrlRegistrar interface {
	PostRegistration(reserveUrl string) error
}

type registerWorker struct {
	wg           *sync.WaitGroup
	doneChan     chan bool
	config       RegisterWorkerConfig
	registerUrls map[time.Weekday]string
}

func NewRegisterWorker(config RegisterWorkerConfig) RegisterWorker {
	return newRegisterWorker(config)
}

func NewUrlRegistrar() UrlRegistrar {
	return newRegisterWorker(NewConfigBuilder().Build())
}

func NewEventRegistrar() EventRegistrar {
	return newRegisterWorker(NewConfigBuilder().Build())
}

func newRegisterWorker(config RegisterWorkerConfig) *registerWorker {
	return &registerWorker{
		&sync.WaitGroup{},
		make(chan bool),
		config,
		make(map[time.Weekday]string),
	}
}

func (w *registerWorker) Work(ticker WeeklyTicker) {

	go func() {

		w.wg.Add(1)
		defer w.wg.Done()

		seelog.Infof("registerWorker starting")

		for {
			select {
			case regTime := <-ticker:
				regTime = regTime.In(w.config.RegisterLocation())
				eventTime := regTime.Add(w.config.ScheduleAheadDuration())
				seelog.Infof("registerWorker regTime: %v  eventTime: %v", regTime, eventTime)

				w.registerForEvent(eventTime)

			case <-w.doneChan:
				return
			}
		}
	}()
}

func (w *registerWorker) registerForEvent(event time.Time) {

	seelog.Debugf("registering with registerUrls: %v", w.registerUrls)
	for i := 0; i < w.config.RegisterRetryMax(); i++ {

		err := w.register(event)
		isSuccess := err == nil
		if isSuccess {
			seelog.Debugf("completed registration with registerUrls: %v", w.registerUrls)
			return
		}

		seelog.Errorf("register error: %v", err)

		delete(w.registerUrls, event.Weekday())
		if i == 0 {
			err = w.register(event)
			isSuccess := err == nil
			if isSuccess {
				seelog.Debugf("completed registration retry")
				return
			}

			seelog.Errorf("register retry error: %v", err)
		}

		time.Sleep(w.config.RegisterRetryWait())
	}

	seelog.Warnf("giving up registration after %d attempts", w.config.RegisterRetryMax())
}

func (w *registerWorker) Close() error {
	seelog.Infof("registerWorker closing...")
	w.doneChan <- true
	w.wg.Wait()
	seelog.Infof("registerWorker closed")

	return nil
}

func (w *registerWorker) register(eventTime time.Time) error {

	seelog.Infof("register event: %v", eventTime)

	var reserveUrl, cachedUrl string
	var ok bool
	var err error

	if cachedUrl, ok = w.registerUrls[eventTime.Weekday()]; !ok {
		reserveUrl, err = w.findReserveUrl(eventTime)
		if err != nil {
			return err
		}
		seelog.Infof("posting with scraped reserveUrl: %s", reserveUrl)
	} else {
		reserveUrl = urlDateRegexp.ReplaceAllString(cachedUrl, eventTime.Format(urlDateFormat))
		seelog.Infof("posting with cached reserveUrl: %s", reserveUrl)
	}

	return w.PostRegistration(reserveUrl)
}

func (w *registerWorker) findReserveUrl(eventTime time.Time) (string, error) {

	var reserveUrl string
	var err error

	schedUrl := fmt.Sprintf(ymcaSchedulesUrl, eventTime.Format(urlDateFormat))
	seelog.Debugf("finding reservation on schedUrl: %s", schedUrl)
	doc, err := goquery.NewDocument(schedUrl)
	if err != nil {
		return reserveUrl, err
	}

	startTime := eventTime.Format(scheduleTimeFormat)
	seelog.Infof("looking for startTime %s", startTime)
	doc.Find("tr.session-list").Each(
		func(i int, s *goquery.Selection) {

			eventTimeCur := s.Children().First().Text()
			if !strings.HasPrefix(eventTimeCur, startTime) {
				return
			}

			title := s.Find("td > button").Text()
			if !w.isEventNameMatch(title) {
				return
			}

			var exists bool
			reserveUrl, exists = s.Find("td > a").Attr("href")
			if !exists {
				err = fmt.Errorf("reserveUrl does not exist for %s %s", eventTimeCur, title)
				seelog.Error(err.Error())
				return
			}

			seelog.Infof("found %s %s %s", eventTimeCur, title, reserveUrl)
		})

	if reserveUrl == "" {
		err = errors.New("failed to find reserveUrl")
	} else {
		w.registerUrls[eventTime.Weekday()] = reserveUrl
	}

	return reserveUrl, err
}

func (w *registerWorker) isEventNameMatch(title string) bool {
	titleLower := strings.ToLower(title)
	return strings.Contains(titleLower, "adult") &&
		strings.Contains(titleLower, "pick") &&
		!strings.Contains(titleLower, "goal")
}

func (w *registerWorker) PostRegistration(reserveUrl string) error {

	seelog.Debugf("posting registration at %s", reserveUrl)
	browser := surf.NewBrowser()
	err := browser.Open(reserveUrl)
	if err != nil {
		return fmt.Errorf("browser.Open(reserveUrl) error: %v", err)
	}

	form, _ := browser.Form("form.form")
	form.Input("name", registrationName)
	form.Input("email", registrationEmail)
	if err = form.Submit(); err != nil {
		return fmt.Errorf("form.Submit error: %v", err)
	}

	alertText := browser.Dom().Find("div.alert").First().Text()
	alertText = wsRegexp.ReplaceAllString(alertText, "")
	seelog.Debugf("post alert text: %v", alertText)

	if !strings.Contains(alertText, regPostAlert_Reserved) &&
		!strings.Contains(alertText, regPostAlert_WaitList) &&
		!strings.Contains(alertText, regPostAlert_OneReg) {

		return fmt.Errorf("registration failed: %v", alertText)
	}

	return nil
}

func (w *registerWorker) EventRegister(eventTime time.Time) error {
	return w.register(eventTime)
}
