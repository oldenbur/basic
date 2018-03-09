package main

import (
	"fmt"
	"log"
	"os"

	"time"

	"strings"

	"errors"

	"github.com/PuerkitoBio/goquery"
	"github.com/urfave/cli"
	"gopkg.in/headzoo/surf.v1"
)

const (
	ymcaSchedulesUrl = "https://bouldervalley.consoria.com/%s"
	urlDateFormat = "2006-01-02"
scheduleTimeFormat = "3:04 PM"

regtimesFlag = "regtimes"
	//eventTitle        = "Adult Pick-Up"
	eventTitle        = "Adult Pick-Up Hockey (Advanced)"
	argDateFormat     = "2006-01-02T15:04:05"
	registrationName  = "Paul Oldenburg"
	registrationEmail = "oldenbur@gmail.com"
)

func main() {
	log.Printf("ychecking started")
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
		log.Fatal(err)
	}
	log.Printf("ychecking complete")
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
	log.Printf("looking for startTime %s", startTime)
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
				log.Print(err.Error())
				return
			}

			log.Printf("found %s %s %s", eventTime, title, reserveUrl)
		})

	if reserveUrl == "" {
		err = errors.New("failed to find reserveUrl")
	}

	return reserveUrl, err
}

func postRegistration(registerUrl string) error {

	browser := surf.NewBrowser()
	err := browser.Open(registerUrl)
	if err != nil {
		return fmt.Errorf("browser.Open(registerUrl) error: %v", err)
	}

	form, _ := browser.Form("form.form")
	form.Input("name", registrationName)
	form.Input("email", registrationEmail)
	if form.Submit() != nil {
		return fmt.Errorf("form.Submit error: %v", err)
	}


	return nil
}
