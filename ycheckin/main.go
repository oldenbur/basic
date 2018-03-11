package main

import (
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/cihub/seelog"
	"github.com/urfave/cli"
	"gopkg.in/headzoo/surf.v1"
)

const (
	ymcaSchedulesUrl   = "https://bouldervalley.consoria.com/%s"
	urlDateFormat      = "2006-01-02"
	scheduleTimeFormat = "3:04 PM"
	regtimesFlag       = "regtimes"
	eventTitle         = "Adult Pick-Up"
	argDateFormat      = "2006-01-02T15:04:05"
	registrationName   = "Paul Oldenburg"
	registrationEmail  = "oldenbur@gmail.com"
)

func main() {
	setupLogging()
	defer seelog.Flush()

	seelog.Infof("ycheckin started")
	app := cli.NewApp()

	app.Flags = []cli.Flag{
		cli.StringFlag{
			Name:  regtimesFlag,
			Usage: "comma-delimited local times to register in YYYY-mm-ddTHH:MM:SS format",
		},
	}

	app.Action = yregister

	err := app.Run(os.Args)
	if err != nil {
		seelog.Errorf("cli.Run error: %v", err)
	}
	seelog.Infof("ycheckin complete")
}

func yregister(c *cli.Context) error {

	t, err := time.Parse(argDateFormat, "2018-03-09T11:00:00")
	if err != nil {
		return err
	}

	return registerDate(t)
}

func registerDate(eventTime time.Time) error {

	reserveUrl, err := findReserveUrl(eventTime)
	if err != nil {
		return err
	}

	return postRegistration(reserveUrl)
}

func findReserveUrl(eventTime time.Time) (string, error) {

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

func postRegistration(reserveUrl string) error {

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

func setupLogging() {
	logger, err := seelog.LoggerFromConfigAsString(`
	<?xml version="1.0"?>
	<seelog type="asynctimer" asyncinterval="1000000" minlevel="debug">
	  <outputs formatid="all">
		<console/>
		<rollingfile type="size" filename="ycheckin.log" maxsize="20000000" maxrolls="5"/>
	  </outputs>
	  <formats>
		<format id="all" format="%Date %Time [%LEVEL] [%FuncShort @ %File.%Line] - %Msg%n"/>
	  </formats>
	</seelog>
	`)
	if err != nil {
		panic(err)
	}

	err = seelog.ReplaceLogger(logger)
	if err != nil {
		panic(err)
	}
}
