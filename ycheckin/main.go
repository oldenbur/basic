package main

import (
	"github.com/cihub/seelog"
	"github.com/urfave/cli"
	"github.com/vrecan/death"
	"os"
	"syscall"
	"time"
	"fmt"
)

const (
	scheduleTimeFormat = "3:04 PM"
	regtimesFlag       = "regtimes"
	regUrlFlag         = "url"
)

func main() {
	setupLogging()
	defer seelog.Flush()

	seelog.Infof("ycheckin started")
	app := cli.NewApp()

	app.Commands = []cli.Command{
		{
			Name:  "regloop",
			Usage: fmt.Sprintf("registration schedule loop - e.g. regloop --%s MON_06:00:00.000,THU_06:00:00.000", regtimesFlag),
			Flags: []cli.Flag{
				cli.StringFlag{
					Name:  regtimesFlag,
					Usage: "comma-delimited local times to register in DAY_HH:MM:SS.000 format",
				},
			},
			Action: yregister,
		},
		{
			Name:  "post",
			Usage: "post a single registration on a specified form url",
			Flags: []cli.Flag{
				cli.StringFlag{
					Name:  regUrlFlag,
					Usage: "registration url",
				},
			},
			Action: postRegistration,
		},
	}

	err := app.Run(os.Args)
	if err != nil {
		seelog.Errorf("cli.Run error: %v", err)
	}
	seelog.Infof("ycheckin complete")
}

func yregister(c *cli.Context) error {

	sched := c.String(regtimesFlag)
	if sched == "" {
		return seelog.Errorf("%s must be specified", regtimesFlag)
	}

	var loc *time.Location
	var err error
	loc, err = time.LoadLocation("America/Denver")
	if err != nil {
		return seelog.Errorf("time.LoadLocation error: %v", err)
	}

	death := death.NewDeath(syscall.SIGINT, syscall.SIGTERM)

	s := NewWeeklyTickerScheduler(loc)
	ticker, err := s.ScheduleWeekly(sched)
	if err != nil {
		return seelog.Errorf("ScheduleWeekly error: %v", err)
	}
	seelog.Infof("scheduled events: %v", s)

	w := NewRegisterWorker(loc)
	w.Work(ticker)

	death.WaitForDeath(s, w)

	return nil
}

func postRegistration(c *cli.Context) error {

	url := c.String(regUrlFlag)
	if url == "" {
		return seelog.Errorf("%s must be specified", regUrlFlag)
	}

	p := NewRegisterUrlPoster()
	return p.PostRegistration(url)
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
