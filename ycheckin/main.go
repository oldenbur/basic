package main

import (
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"

	"time"

	"strings"

	"errors"

	"github.com/PuerkitoBio/goquery"
	"github.com/urfave/cli"
)

const (
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

	registerUrl, err := findReserveUrl(eventTime)
	if err != nil {
		return err
	}

	registrationInfo, err := findRegistrationInfo(registerUrl)
	if err != nil {
		return err
	}

	return postRegistration(registrationInfo)
}

func findReserveUrl(eventTime time.Time) (string, error) {

	var reserveUrl string
	var err error

	schedUrl := fmt.Sprintf("https://bouldervalley.consoria.com/%s", eventTime.Format("2006-01-02"))
	doc, err := goquery.NewDocument(schedUrl)
	if err != nil {
		return reserveUrl, err
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

type registrationInfo struct {
	Action string
	Token  string
}

func findRegistrationInfo(registerUrl string) (*registrationInfo, error) {

	var err error
	var action, token string

	doc, err := goquery.NewDocument(registerUrl)
	if err != nil {
		return nil, fmt.Errorf("NewDocument(registerUrl) error: %v", err)
	}

	doc.Find("form.form").Each(
		func(i int, s *goquery.Selection) {

			var exists bool
			action, exists = s.Attr("action")
			if !exists {
				err = errors.New("form action not found")
				log.Print(err.Error())
				return
			}

			token, exists = s.Find("input[name=_token]").Attr("value")
			if !exists {
				err = errors.New("form token not found")
				log.Print(err.Error())
				return
			}

			log.Printf("action: %s  token: %s", action, token)
		})

	return &registrationInfo{action, token}, err
}

func postRegistration(info *registrationInfo) error {

	resp, err := http.PostForm(info.Action,
		url.Values{
			"_token": {info.Token},
			"name":   {registrationName},
			"email":  {registrationEmail},
		})
	if err != nil {
		return fmt.Errorf("PostForm error: %v", err)
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("PostForm resp.Body ReadAll error: %v", err)
	}

	log.Printf("registration post response: %v", string(body))

	return nil
}
