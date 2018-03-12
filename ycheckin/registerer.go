package main

import (
	"fmt"
	"github.com/PuerkitoBio/goquery"
	"gopkg.in/headzoo/surf.v1"
	"time"

	"errors"
	"github.com/cihub/seelog"
	"io"
	"strings"
	"sync"
)

const (
	ymcaSchedulesUrl  = "https://bouldervalley.consoria.com/%s"
	urlDateFormat     = "2006-01-02"
	eventTitle        = "Adult Pick-Up"
	registrationName  = "Paul Oldenburg"
	registrationEmail = "oldenbur@gmail.com"
	registerRetries   = 5
)

type RegisterWorker interface {
	io.Closer
	Work(ticker WeeklyTicker)
}

type registerWorker struct {
	wg       *sync.WaitGroup
	doneChan chan bool
	loc      *time.Location
}

func NewRegisterWorker(loc *time.Location) RegisterWorker {
	return &registerWorker{&sync.WaitGroup{}, make(chan bool), loc}
}

func (w *registerWorker) Work(ticker WeeklyTicker) {

	go func() {

		w.wg.Add(1)
		defer w.wg.Done()

		seelog.Infof("registerWorker starting")

		for {
			select {
			case event := <-ticker:
				event = event.In(w.loc)
				seelog.Infof("registerWorker event: %v", event)

				success := false
				for i := 0; (i < registerRetries) && !success; i++ {
					err := w.register(event.Add(24 * time.Hour))
					if err != nil {
						seelog.Errorf("register error: %v", err)
					} else {
						success = true
					}
				}

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

func (r *registerWorker) register(eventTime time.Time) error {

	seelog.Infof("register event: %v", eventTime)
	reserveUrl, err := r.findReserveUrl(eventTime)
	if err != nil {
		return err
	}

	return r.postRegistration(reserveUrl)
}

func (r *registerWorker) findReserveUrl(eventTime time.Time) (string, error) {

	var reserveUrl string
	var err error

	schedUrl := fmt.Sprintf(ymcaSchedulesUrl, eventTime.Format(urlDateFormat))
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

func (r *registerWorker) postRegistration(reserveUrl string) error {

	browser := surf.NewBrowser()
	err := browser.Open(reserveUrl)
	if err != nil {
		return fmt.Errorf("browser.Open(reserveUrl) error: %v", err)
	}

	form, _ := browser.Form("form.form")
	form.Input("name", registrationName)
	form.Input("email", registrationEmail)
	if form.Submit() != nil {
		return fmt.Errorf("form.Submit error: %v", err)
	}

	return nil
}
