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

var urlCodeRegexp = regexp.MustCompile(`.+/(\d*)$`)
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

type RegHttpClient interface {
	PostRegistration(reserveUrl string) error
	FindReserveUrl(eventTime time.Time) (string, error)
}

type registerWorker struct {
	wg         *sync.WaitGroup
	doneChan   chan bool
	config     RegisterWorkerConfig
	codeCache  map[time.Weekday]string
	httpClient RegHttpClient
}

func NewRegisterWorker(config RegisterWorkerConfig, codeCache map[time.Weekday]string) RegisterWorker {
	return newRegisterWorker(config, codeCache, &httpClientImpl{})
}

func NewRegHttpClient() RegHttpClient {
	return &httpClientImpl{}
}

func NewEventRegistrar() EventRegistrar {
	return newRegisterWorker(NewConfigBuilder().Build(), make(map[time.Weekday]string), &httpClientImpl{})
}

func newRegisterWorker(config RegisterWorkerConfig, codeCache map[time.Weekday]string, httpClient RegHttpClient) *registerWorker {
	return &registerWorker{
		&sync.WaitGroup{},
		make(chan bool),
		config,
		codeCache,
		httpClient,
	}
}

func (w *registerWorker) Work(ticker WeeklyTicker) {

	go func() {

		w.wg.Add(1)
		defer w.wg.Done()

		seelog.Infof("registerWorker starting with codeCache: %v", w.codeCache)

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

func (w *registerWorker) Close() error {
	seelog.Infof("registerWorker closing...")
	w.doneChan <- true
	w.wg.Wait()
	seelog.Infof("registerWorker closed")

	return nil
}

func (w *registerWorker) registerForEvent(event time.Time) {

	seelog.Debugf("registering with codeCache: %v", w.codeCache)
	for i := 0; i < w.config.RegisterRetryMax(); i++ {

		err := w.register(event)
		isSuccess := err == nil
		if isSuccess {
			seelog.Debugf("completed registration with codeCache: %v", w.codeCache)
			return
		}

		seelog.Errorf("register error: %v", err)

		delete(w.codeCache, event.Weekday())
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

func (w *registerWorker) register(eventTime time.Time) error {

	seelog.Infof("register event: %v", eventTime)

	var reserveUrl, cachedCode string
	var ok bool
	var err error

	cachedCode, ok = w.codeCache[eventTime.Weekday()]
	if !ok {
		reserveUrl, err = w.httpClient.FindReserveUrl(eventTime)
		if err != nil {
			return err
		}

		urlCodeParse := urlCodeRegexp.FindStringSubmatch(reserveUrl)
		if len(urlCodeParse) == 2 {
			w.codeCache[eventTime.Weekday()] = urlCodeParse[1]
		} else {
			seelog.Warnf("failed to parse code from reserveUrl: %s", reserveUrl)
		}

		seelog.Infof("posting with scraped reserveUrl: %s", reserveUrl)
	} else {
		reserveUrl = fmt.Sprintf(ymcaReserveUrl, eventTime.Format(urlDateFormat), cachedCode)
		seelog.Infof("posting with cached reserveUrl: %s", reserveUrl)
	}

	return w.httpClient.PostRegistration(reserveUrl)
}

func (w *registerWorker) EventRegister(eventTime time.Time) error {
	return w.register(eventTime)
}

type httpClientImpl struct {}

func (w *httpClientImpl) PostRegistration(reserveUrl string) error {

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

func (w *httpClientImpl) FindReserveUrl(eventTime time.Time) (string, error) {

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
	}

	return reserveUrl, err
}

func (w *httpClientImpl) isEventNameMatch(title string) bool {
	titleLower := strings.ToLower(title)
	return strings.Contains(titleLower, "adult") &&
		strings.Contains(titleLower, "pick") &&
		!strings.Contains(titleLower, "goal")
}
