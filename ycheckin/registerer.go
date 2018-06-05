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
	eventTitle        = "Adult Pick-Up Hockey"
	registrationName  = "Paul Oldenburg"
	registrationEmail = "oldenbur@gmail.com"

	regPostAlert_Reserved = "Your spot has been reserved" // "Your spot has been reserved and an email with more information has been sent to your email"
	regPostAlert_24hours  = "Reservations may not be made until 24 hours prior"
	regPostAlert_WaitList = "you have been added to the waitlist"
	regPostAlert_OneReg   = "one reservation per individual may be made"
)

var wsRegexp = regexp.MustCompile(`(?: {2,}|\n)`)

var dayReservationCodes = map[time.Weekday]string{
	time.Tuesday:   "4578", // 5806
	time.Wednesday: "4579", // 4580
	time.Thursday:  "4570",
	time.Friday:    "4587",
}

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
	wg       *sync.WaitGroup
	doneChan chan bool
	config   RegisterWorkerConfig
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
	return &registerWorker{&sync.WaitGroup{}, make(chan bool), config}
}

func (w *registerWorker) Work(ticker WeeklyTicker) {

	go func() {

		w.wg.Add(1)
		defer w.wg.Done()

		seelog.Infof("registerWorker starting")

		for {
			select {
			case event := <-ticker:
				event = event.In(w.config.RegisterLocation())
				seelog.Infof("registerWorker event: %v", event)

				w.registerForEvent(event.Add(w.config.ScheduleAheadDuration()))

			case <-w.doneChan:
				return
			}
		}
	}()
}

func (w *registerWorker) registerForEvent(event time.Time) {

	for i := 0; i < w.config.RegisterRetryMax(); i++ {

		err := w.register(event)
		if err != nil {
			if (i % w.config.RegisterRetryLogIntvl()) == 0 {
				seelog.Errorf("register error: %v", err)
			}
		} else {
			return
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
	//reserveUrl, err := w.inferReserveUrl(eventTime)
	reserveUrl, err := w.findReserveUrl(eventTime)
	if err != nil {
		return err
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

			eventTime := s.Children().First().Text()
			if !strings.HasPrefix(eventTime, startTime) {
				return
			}

			title := s.Find("td > button").Text()
			if title != eventTitle {
				return
			}

			var exists bool
			reserveUrl, exists = s.Find("td > a").Attr("href")
			if !exists {
				err = fmt.Errorf("reserveUrl does not exist for %s %s", eventTime, title)
				seelog.Error(err.Error())
				return
			}

			seelog.Infof("found %s %s %s", eventTime, title, reserveUrl)
		})

	if reserveUrl == "" {
		err = errors.New("failed to find reserveUrl")
	}

	return reserveUrl, err
}

func (w *registerWorker) inferReserveUrl(eventTime time.Time) (string, error) {

	var dayCode string
	var ok bool
	if dayCode, ok = dayReservationCodes[eventTime.Weekday()]; !ok {
		return "", fmt.Errorf("unable to infer reserve url for date: %v  weekday: %v", eventTime, eventTime.Weekday())
	}

	return fmt.Sprintf(ymcaReserveUrl, eventTime.Format(urlDateFormat), dayCode), nil
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
		!strings.Contains(alertText, regPostAlert_WaitList) {

		return fmt.Errorf("registration failed: %v", alertText)
	}

	return nil
}

func (w *registerWorker) EventRegister(eventTime time.Time) error {
	return w.register(eventTime)
}
