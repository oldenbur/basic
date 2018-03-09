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
)

const (
	regtimesFlag = "regtimes"
	eventTitle   = "Adult Pick-Up"
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

	t, err := time.Parse("2006-01-02T15:04:05", "2018-03-09T07:00:00")
	if err != nil {
		return err
	}

	return registerDate(t)
}

func registerDate(eventTime time.Time) error {

	return nil
}

func findRegisterUrl(eventTime time.Time) (string, error) {

	var registerUrl string
	var err error

	schedUrl := fmt.Sprintf("https://bouldervalley.consoria.com/%s", eventTime.Format("2006-01-02"))
	doc, err := goquery.NewDocument(schedUrl)
	if err != nil {
		return registerUrl, err
	}

	startTime := eventTime.Format("3:04 PM")
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

			reserveUrl, exists := s.Find("td > a").Attr("href")
			if !exists {
				err = fmt.Errorf("reserveUrl does not exist for %s %s", eventTime, title)
				log.Print(err.Error())
				return
			}

			log.Printf("found %s %s %s", eventTime, title, reserveUrl)
		})

	if registerUrl == "" {
		err = errors.New("failed to find registerUrl")
	}

	return registerUrl, err
}
