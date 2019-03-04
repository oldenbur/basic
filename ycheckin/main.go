package main

import (
	"fmt"
	"github.com/cihub/seelog"
	"github.com/urfave/cli"
	"github.com/vrecan/death"
	"os"
	"regexp"
	"strings"
	"syscall"
	"time"
)

const (
	scheduleTimeFormat          = "3:04 PM"
	regtimesFlag                = "regtimes"
	regtimesEnv                 = "YC_REG_TIMES"
	scheduleAheadDurationMsFlag = "schedaheadms"
	scheduleAheadDurationMsEnv  = "YC_SCHED_AHEAD_MS"
	registerRetryWaitMsFlag     = "regretrywaitms"
	registerRetryWaitMsEnv      = "YC_REG_RETRY_WAIT_MS"
	registerRetryMaxFlag        = "regretrymax"
	registerRetryMaxEnv         = "YC_REG_RETRY_MAX"
	registerRetryLogIntvlFlag   = "regretrylog"
	registerRetryLogIntvlEnv    = "YC_REG_RETRY_LOG"
	cachedCodesFlag             = "cachedcodes"
	cachedCodesEnv              = "YC_CACHED_CODES"
	regUrlFlag                  = "url"
	regHttpAddrFlag             = "addr"
	regHttpAddrEnv              = "YC_ADDR"
	regEventTime                = "regtime"
	appVersion                  = "0.3"
)

var codeCacheRegexp = regexp.MustCompile(`(SUN|MON|TUE|WED|THU|FRI|SAT):(\d+)`)

func main() {
	setupLogging()
	defer seelog.Flush()

	seelog.Infof("ycheckin v%s started", appVersion)
	app := cli.NewApp()
	app.Version = appVersion
	app.Commands = []cli.Command{
		{
			Name:  "regloop",
			Usage: fmt.Sprintf("registration schedule loop - e.g. regloop --%s MON_06:00:00.000,THU_06:00:00.000", regtimesFlag),
			Flags: []cli.Flag{
				cli.StringFlag{
					Name:   regtimesFlag,
					Usage:  "comma-delimited local times to register in DAY_HH:MM:SS.000 format",
					EnvVar: regtimesEnv,
				},
				cli.IntFlag{
					Name:   scheduleAheadDurationMsFlag,
					Usage:  "duration, in milliseconds, between registration and the event, e.g. 172800000 for 48 hours",
					EnvVar: scheduleAheadDurationMsEnv,
				},
				cli.IntFlag{
					Name:   registerRetryWaitMsFlag,
					Usage:  "duration, in milliseconds, to wait between registration attempts",
					EnvVar: registerRetryWaitMsEnv,
				},
				cli.IntFlag{
					Name:   registerRetryMaxFlag,
					Usage:  "maximum number of registration attempts per event",
					EnvVar: registerRetryMaxEnv,
				},
				cli.IntFlag{
					Name:   registerRetryLogIntvlFlag,
					Usage:  "number of attempts between logged registration failures",
					EnvVar: registerRetryLogIntvlEnv,
				},
				cli.StringFlag{
					Name:   regHttpAddrFlag,
					Usage:  "host/port pair on which to bind the http API",
					EnvVar: regHttpAddrEnv,
				},
				cli.StringFlag{
					Name:   cachedCodesFlag,
					Usage:  "host/port pair on which to bind the http API, e.g. 0.0.0.0:80",
					EnvVar: cachedCodesEnv,
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
		{
			Name:  "event",
			Usage: "post a single registration for a specified event time",
			Flags: []cli.Flag{
				cli.StringFlag{
					Name:  regEventTime,
					Usage: "event time in the format YYYYmmdd_HHMM",
				},
			},
			Action: eventRegistration,
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

	var config *ycheckinConfig
	var err error
	config, err = buildConfig(c)
	if err != nil {
		return seelog.Errorf("buildConfig error: %v", err)
	}

	s := NewWeeklyTickerScheduler(config.RegisterLocation())
	ticker, err := s.ScheduleWeekly(sched)
	if err != nil {
		return seelog.Errorf("ScheduleWeekly error: %v", err)
	}

	var codeCache map[time.Weekday]string
	codeCache, err = buildCodeCache(c)
	if err != nil {
		return seelog.Errorf("buildCodeCache error: %v", err)
	}

	w := NewRegisterWorker(config, codeCache)
	w.Work(ticker)

	h := newRegHttp(config, s, w)
	err = h.Start()
	if err != nil {
		return seelog.Errorf("regHttp.Start error: %v", err)
	}

	death.NewDeath(syscall.SIGINT, syscall.SIGTERM).WaitForDeath(s, w)

	return nil
}

func buildConfig(c *cli.Context) (*ycheckinConfig, error) {

	var loc *time.Location
	var err error
	loc, err = time.LoadLocation("America/Denver")
	if err != nil {
		return nil, seelog.Errorf("time.LoadLocation error: %v", err)
	}

	configBuilder := NewConfigBuilder().WithLocation(loc)
	if c.Int(scheduleAheadDurationMsFlag) != 0 {
		configBuilder.WithScheduleAheadDuration(time.Duration(c.Int(scheduleAheadDurationMsFlag)) * time.Millisecond)
	}
	if c.Int(registerRetryWaitMsFlag) != 0 {
		configBuilder.WithRegisterRetryWait(time.Duration(c.Int(registerRetryWaitMsFlag)) * time.Millisecond)
	}
	if c.Int(registerRetryMaxFlag) != 0 {
		configBuilder.WithRegisterRetryMax(c.Int(registerRetryMaxFlag))
	}
	if c.Int(registerRetryLogIntvlFlag) != 0 {
		configBuilder.WithRegisterRetryLogIntvl(c.Int(registerRetryLogIntvlFlag))
	}
	if c.String(regHttpAddrFlag) != "" {
		configBuilder.WithHttpAddr(c.String(regHttpAddrFlag))
	}

	return configBuilder.Build(), nil
}

func buildCodeCache(c *cli.Context) (map[time.Weekday]string, error) {
	cache := map[time.Weekday]string{}

	codesCacheVal := c.String(cachedCodesFlag)
	if codesCacheVal != "" {

		codes := strings.Split(codesCacheVal, ",")
		for _, codeVal := range codes {

			codeParse := codeCacheRegexp.FindStringSubmatch(codeVal)
			if len(codeParse) != 3 {
				return cache, fmt.Errorf("buildCodeCache unexpected parse result '%v' for cacheVal: %s", codeParse, codeVal)
			}

			weekday, err := DayStringToWeekday(codeParse[1])
			if err != nil {
				return cache, fmt.Errorf("buildCodeCache DayStringToWeekday(%s) error: %v", codeParse[1], err)
			}

			cache[weekday] = codeParse[2]
		}
	}


	return cache, nil
}

func postRegistration(c *cli.Context) error {

	url := c.String(regUrlFlag)
	if url == "" {
		return seelog.Errorf("%s must be specified", regUrlFlag)
	}

	p := NewRegHttpClient()
	return p.PostRegistration(url)
}

func eventRegistration(c *cli.Context) error {

	eventVal := c.String(regEventTime)
	if eventVal == "" {
		return seelog.Errorf("%s must be specified", regEventTime)
	}

	event, err := time.Parse("20060102_1504", eventVal)
	if err != nil {
		return seelog.Errorf("error parsing timestamp %s: %v", err)
	}

	p := NewEventRegistrar()
	return p.EventRegister(event)
}

func DayStringToWeekday(day string) (time.Weekday, error) {
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
